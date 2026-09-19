"""Shared Tk application: coordinates services, pet behavior, and desktop movement."""
import logging
from logging.handlers import RotatingFileHandler
import math
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

from desktop_layout import get_monitors, nearest_monitor, floor_at, horizontal_bounds, FloorTransition
from .api import API_PORT, ApiServer, StatusSnapshot
from .behavior import PetBehavior
from .paths import data_directory, migrate_legacy, pending_legacy_files
from .pets.base import CANVAS_SIZE
from .pets.registry import load_pets
from .platform_windows import DesktopLayer, NoLayer, SingleInstance, show_message
from .reminders import ReminderService
from .sprites import SpriteCache, TRANS_KEY
from .storage import JsonFile, StorageError
from .ui import PetUI

log = logging.getLogger(__name__)
ERROR_DIALOG_GAP = 60  # Seconds; a failing 50 ms timer must never stack message boxes.
DIVE_CHANCE = 0.4      # A swimmer's chance, at each rest, of slipping behind the desktop icons.
BEHIND_SECONDS = (10, 30)  # How long a swimmer stays back there before surfacing on its own.


class DesktopPet(PetUI, tk.Tk):
    def __init__(self, reminders, settings, pets, events=None, status=None, pet_id="cat", choose=False, start_loops=True):
        super().__init__()
        self.withdraw()
        self.reminders, self.settings, self.pets = reminders, settings, pets
        self.events = events if events is not None else queue.Queue()
        self.status = status or StatusSnapshot()
        self.reminders.on_change = lambda: self.events.put(("refresh", None))
        self._closed = False
        self._sprites = None
        self._error_dialog_open = False
        self._next_error_dialog = 0.0
        self._list_refreshers = {}
        self.speech_bubble = self.alert_win = self.alert_id = self.chooser = None
        self._control_open = False
        self._dragging = self._has_dragged = False
        self._drag_start_x = self._drag_start_y = 0
        self._floor_transition = None
        self._next_display_check = time.monotonic() + 2
        self._last_position = self._last_image = None
        self.pet_w, self.pet_h = CANVAS_SIZE
        self.pet_id, self.definition = self._usable_pet(pet_id)
        self.behavior = PetBehavior(self.definition)
        self.roam_enabled = True
        self.facing = 1
        self.vy = 0.0
        try:
            self.monitors = get_monitors()
        except OSError:
            # Reminders matter more than placement; the two-second refresh corrects this later.
            log.warning("Display enumeration unavailable at startup; using the primary screen")
            width, height = self.winfo_screenwidth(), self.winfo_screenheight()
            self.monitors = [{"left": 0, "top": 0, "right": width, "bottom": height,
                              "screen": (0, 0, width, height), "primary": True}]
        self.min_x, self.max_x = horizontal_bounds(self.monitors, self.pet_w)
        primary = next((m for m in self.monitors if m["primary"]), self.monitors[0])
        self.x = max(self.min_x, min(self.max_x, primary["left"] + 300))
        self.floor_y = floor_at(self.monitors, self.x, self.pet_w, primary["bottom"] - 1, self.pet_h)
        self.y = self.floor_y
        self.target_x = self.x
        self.target_y = self.y
        self.swimmer = self.definition.movement == "swim"
        self.layer = NoLayer()
        self._surface_at = 0.0
        if self.swimmer:
            self.y = self.target_y = (primary["top"] + primary["bottom"] - self.pet_h) / 2
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-transparentcolor", TRANS_KEY)
        self.configure(bg=TRANS_KEY)
        self.geometry(f"{self.pet_w}x{self.pet_h}+{round(self.x)}+{round(self.y)}")
        self.canvas = tk.Canvas(self, width=self.pet_w, height=self.pet_h, bg=TRANS_KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.sprite_item = self.canvas.create_image(0, 0, anchor="nw")
        for event, callback in (("<Button-1>", self.on_click), ("<B1-Motion>", self.on_drag),
                                ("<ButtonRelease-1>", self.on_release), ("<Button-3>", self.on_right_click)):
            self.canvas.bind(event, callback)
        self.menu = tk.Menu(self, tearoff=0)
        self.build_menu()
        self.pick_new_destination()
        self.render()
        self.publish_status()
        self.last_tick = time.monotonic()
        if start_loops:
            self.deiconify()
            try:
                self.layer = DesktopLayer(self)
            except Exception:
                log.exception("Desktop layering unavailable; swimmers will stay in front")
            self.tick_pet()
            self.tick_reminders()
            if choose:
                self.after(100, self.choose_pet)

    @property
    def state(self):
        return self.behavior.state

    def _usable_pet(self, preferred):
        """A pet that fails to build must not stop reminders; fall back to another one."""
        error = None
        for pet_id in dict.fromkeys([preferred, *self.pets]):
            if pet_id in self.pets:
                try:
                    return pet_id, self.pets[pet_id]
                except Exception as exc:
                    log.exception("Pet %s could not be loaded", pet_id)
                    error = exc
        raise error or ValueError("No pets are registered")

    def _position(self):
        position = round(self.x), round(self.y)
        if position != self._last_position:
            if not self.layer.move(*position):
                self.geometry(f"+{position[0]}+{position[1]}")
            self._last_position = position

    # ---- swimming pets: free movement inside the work area, no floor, two desktop layers
    def _clamp_swimmer(self):
        m = nearest_monitor(self.monitors, self.x + self.pet_w / 2, self.y + self.pet_h / 2)
        self.x = max(m["left"], min(m["right"] - self.pet_w, self.x))
        self.y = max(m["top"], min(m["bottom"] - self.pet_h, self.y))

    def _at_target(self):
        if self.swimmer:
            return math.hypot(self.target_x - self.x, self.target_y - self.y) < 20
        return abs(self.target_x - self.x) < 20

    def dive(self):
        """Swim behind the desktop icons for a while. Ignored while busy or while a popup is open."""
        if not self.swimmer or self._dragging or self.speech_bubble or self.alert_win or self.chooser:
            return False
        if self.layer.set_behind():
            self._surface_at = time.monotonic() + random.uniform(*BEHIND_SECONDS)
            self._last_position = None
            self._position()
            return True
        return False

    def surface(self):
        if self.layer.behind:
            self.layer.set_front()
            self._last_position = None
            self._position()

    def _maybe_change_layer(self):
        if self.layer.behind:
            if random.random() < 0.5:
                self.surface()
        elif random.random() < DIVE_CHANCE:
            self.dive()

    def _step_swim(self, dt):
        blocked = bool(self.speech_bubble or self.alert_win or self.chooser)
        if blocked or self._dragging:
            self.surface()
        if self._dragging:
            return
        if self.alert_win and self.state != "alert":
            self.enter_state("alert")
        elif blocked and self.state == "walk":
            self.enter_state("sit")
        elif self.state == "fall":
            self.enter_state("sit")          # no gravity under water
        self.behavior.advance(dt)
        animation = self.definition.animations[self.state]
        if self.layer.behind and time.monotonic() >= self._surface_at:
            self.surface()
        if self.state == "walk" and self.roam_enabled and not blocked:
            dx, dy = self.target_x - self.x, self.target_y - self.y
            distance = math.hypot(dx, dy)
            if distance > 1:
                step = min(distance, self.definition.personality.walk_speed * dt)
                self.x += dx / distance * step
                self.y += dy / distance * step
                if abs(dx) > 8:
                    self.facing = 1 if dx > 0 else -1
            else:
                self.behavior.rest()
                self._maybe_change_layer()
                self.pick_new_destination()
        elif not self.alert_win and animation.forward_speed and self.roam_enabled and not blocked:
            self.x += self.facing * animation.forward_speed * dt
        if self.state != "alert" and self.behavior.elapsed >= self.behavior.duration:
            self.behavior.next(self.roam_enabled, self._at_target(), blocked)
            if self.state == "walk":
                if self._at_target():
                    self.pick_new_destination()
                self.facing = 1 if self.target_x > self.x else -1
            elif not blocked:
                self._maybe_change_layer()
        self._clamp_swimmer()

    def render(self):
        if self._sprites is None or self._sprites.definition is not self.definition:
            self._sprites = SpriteCache(self.definition, self)  # Releases the previous pet's Tk images.
        state = "fall" if self._dragging or self._floor_transition else self.state
        index = 0 if self._dragging or self._floor_transition else self.behavior.frame_index()
        image = self._sprites.get(state, index, self.facing)
        if image is not self._last_image:
            self.canvas.itemconfig(self.sprite_item, image=image)
            self._last_image = image

    def publish_status(self):
        self.status.set({"pet": self.definition.label, "pet_id": self.pet_id,
                         "actions": list(self.definition.actions), "state": self.state,
                         "facing": self.facing, "x": round(self.x), "y": round(self.y),
                         "roam_enabled": self.roam_enabled, "status": "online",
                         "layer": "behind" if self.layer.behind else "front"})

    def select_pet(self, pet_id):
        if pet_id not in self.pets:
            raise ValueError("Unknown pet")
        definition = self.pets[pet_id]
        try:
            self.settings.save({"pet": pet_id})
        except StorageError:
            log.exception("Pet preference was not saved")  # A preference never blocks the switch.
        self.surface()
        self.pet_id, self.definition = pet_id, definition
        self.swimmer = definition.movement == "swim"
        self.behavior = PetBehavior(self.definition)
        self._floor_transition = None
        self._dragging = False
        self.vy = 0
        if self.swimmer:
            self._clamp_swimmer()
            self.target_x, self.target_y = self.x, self.y
        else:
            self.floor_y = self.local_floor(self.x)
            self.y = self.floor_y
        self.enter_state("alert" if self.alert_win else "sit")
        if self.speech_bubble:
            self._close_bubble(self.speech_bubble)
        if self.chooser:
            self.chooser.destroy()
            self.chooser = None
        self.build_menu()
        self.render()
        self._position()
        self.publish_status()

    def enter_state(self, state, duration=None):
        if not self.swimmer and not self._dragging and not self._floor_transition and self.state != "fall":
            self.y = self.floor_y
        self.behavior.enter(state, duration)
        if state == "walk":
            if self._at_target():
                self.pick_new_destination()
            self.facing = 1 if self.target_x > self.x else -1

    def do_action(self, action):
        if self.alert_win or self._dragging:
            return False
        if action == "silly":
            choices = list(self.definition.actions)
            action = random.choice(choices) if choices else "look"
        allowed = set(self.definition.actions) | {"idle", "sit", "look", "walk"}
        if action not in allowed:
            return False
        if action == "walk" and not self.roam_enabled:
            return False
        self.enter_state(action)
        return True

    def local_floor(self, x):
        return floor_at(self.monitors, x, self.pet_w, self.y+self.pet_h-1, self.pet_h)

    def refresh_displays(self):
        if time.monotonic() < self._next_display_check:
            return
        self._next_display_check = time.monotonic() + 2
        try:
            monitors = get_monitors()
        except OSError:
            log.warning("Display enumeration temporarily unavailable")
            return
        if monitors == self.monitors:
            return
        self.monitors = monitors
        self.min_x, self.max_x = horizontal_bounds(monitors, self.pet_w)
        self.target_x = max(self.min_x, min(self.max_x, self.target_x))
        if self._floor_transition:
            self.floor_y = self.y
        self._floor_transition = None
        if self.swimmer:
            self._clamp_swimmer()
            self.target_x, self.target_y = self.x, self.y
            self._position()
        elif not self._dragging:
            m = nearest_monitor(monitors, self.x+self.pet_w/2, self.y+self.pet_h-1)
            if not any(m["left"] <= self.x+self.pet_w/2 < m["right"] for m in monitors):
                self.x = max(m["left"], min(m["right"]-self.pet_w, self.x))
            self.move_on_surface(self.x)
            self._position()

    def move_on_surface(self, next_x):
        next_x = max(self.min_x, min(self.max_x, next_x))
        floor = self.local_floor(next_x)
        if floor != self.floor_y:
            self.floor_y = floor
            self._floor_transition = FloorTransition(self.x, self.y, next_x, floor)
        else:
            self.x = next_x

    def pick_new_destination(self):
        if not self.roam_enabled:
            return
        if self.swimmer:
            here = nearest_monitor(self.monitors, self.x + self.pet_w / 2, self.y + self.pet_h / 2)
            m = random.choice(self.monitors) if len(self.monitors) > 1 and random.random() < 0.25 else here
            self.target_x = random.uniform(m["left"] + 10, max(m["left"] + 10, m["right"] - self.pet_w - 10))
            self.target_y = random.uniform(m["top"] + 10, max(m["top"] + 10, m["bottom"] - self.pet_h - 10))
            self.facing = 1 if self.target_x > self.x else -1
            return
        span = self.max_x-self.min_x
        if span > 1200 and random.random() < 0.65:
            midpoint = (self.min_x+self.max_x)//2
            low, high = (self.min_x+40, midpoint-100) if self.x > midpoint else (midpoint+100, self.max_x-40)
            self.target_x = random.uniform(low, high)
        else:
            self.target_x = max(self.min_x, min(self.max_x, self.x+random.choice((-1, 1))*random.uniform(250, 700)))
        self.facing = 1 if self.target_x > self.x else -1

    def process_events(self):
        refreshed = False
        for _ in range(100):
            try:
                event, data = self.events.get_nowait()
            except queue.Empty:
                break
            try:
                if event == "refresh":
                    refreshed = True
                elif event == "select_pet":
                    self.select_pet(data)
                elif event == "speak":
                    self.show_speech_bubble(data)
                elif event == "action":
                    self.do_action(data)
                elif event == "set_roam":
                    self.set_roam(data)
            except Exception:
                # One bad command must not drop the reminder refresh queued behind it.
                log.exception("Queued %s command failed", event)
        if refreshed:
            self.refresh_reminder_views()

    def step(self, dt):
        """Advance one frame; deterministic dt enables movement tests without sleeping."""
        self.refresh_displays()
        self.process_events()
        if self.swimmer:
            self._step_swim(dt)
        elif self._dragging:
            pass
        elif self._floor_transition:
            self.x, self.y, landed = self._floor_transition.advance(dt)
            if landed:
                self._floor_transition = None
        elif self.state == "fall":
            self.floor_y = self.local_floor(self.x)
            self.vy += 380 * dt
            self.y += self.vy * dt
            if self.y >= self.floor_y:
                self.y, self.vy = self.floor_y, 0
                self.enter_state("alert" if self.alert_win else "sit")
        else:
            blocked = bool(self.speech_bubble or self.alert_win or self.chooser)
            if self.alert_win and self.state != "alert":
                self.enter_state("alert")
            elif blocked and self.state == "walk":
                self.enter_state("sit")
            self.behavior.advance(dt)
            animation = self.definition.animations[self.state]
            self.y = self.floor_y
            if self.state == "walk" and self.roam_enabled and not blocked:
                self.facing = 1 if self.target_x > self.x else -1
                distance = min(abs(self.target_x-self.x), self.definition.personality.walk_speed*dt)
                self.move_on_surface(self.x+self.facing*distance)
                if abs(self.target_x-self.x) < 1 and not self._floor_transition:
                    self.behavior.rest()
                    self.pick_new_destination()
            elif not self.alert_win:
                if animation.forward_speed and self.roam_enabled and not blocked:
                    self.move_on_surface(self.x+self.facing*animation.forward_speed*dt)
                if animation.hop_height and not blocked and not self._floor_transition:
                    period = animation.frame_seconds*len(animation.frames)
                    self.y = self.floor_y-animation.hop_height*abs(math.sin(math.pi*self.behavior.elapsed/period))
            if not self._floor_transition and self.state != "alert" and self.behavior.elapsed >= self.behavior.duration:
                self.behavior.next(self.roam_enabled, self._at_target(), blocked)
                if self.state == "walk":
                    self.facing = 1 if self.target_x > self.x else -1
                self.y = self.floor_y
        self._position()
        self.render()
        self.publish_status()

    def tick_pet(self):
        if self._closed:
            return
        now = time.monotonic()
        dt, self.last_tick = min(0.1, max(0.001, now-self.last_tick)), now
        try:
            self.step(dt)
        finally:
            if not self._closed:
                self._pet_timer = self.after(50, self.tick_pet)

    def tick_reminders(self):
        if self._closed:
            return
        try:
            if not self.alert_win:
                rec = self.reminders.next_due()
                if rec:
                    self.alert_popup(rec)
                    self.reminders.mark_presented(rec["id"])
        finally:
            if not self._closed:
                self._reminder_timer = self.after(1000, self.tick_reminders)

    def set_roam(self, enabled):
        self.roam_enabled = enabled
        if enabled:
            self.pick_new_destination()
        if not self.alert_win and not self._dragging:
            self.enter_state("walk" if enabled else "sit")

    def toggle_roam(self):
        self.set_roam(not self.roam_enabled)

    def on_click(self, event):
        self._drag_start_x, self._drag_start_y = event.x_root-self.x, event.y_root-self.y
        self._has_dragged = False

    def on_drag(self, event):
        self._has_dragged = self._dragging = True
        self._floor_transition = None
        self.x, self.y = event.x_root-self._drag_start_x, event.y_root-self._drag_start_y
        if self.speech_bubble:
            self._close_bubble(self.speech_bubble)
        self._position()

    def on_release(self, event):
        if self._dragging and self.swimmer:
            self._dragging = False
            self._clamp_swimmer()
            self.target_x, self.target_y = self.x, self.y
            self.enter_state("alert" if self.alert_win else "sit")
            if self.alert_win:
                self.place_popup(self.alert_win)
        elif self._dragging:
            self._dragging = False
            self.floor_y = self.local_floor(self.x)
            self.vy = 0
            if self.y < self.floor_y:
                self.behavior.enter("fall")
            else:
                self.y = self.floor_y
                self.enter_state("alert" if self.alert_win else "sit")
            if self.alert_win:
                self.place_popup(self.alert_win)
        elif not self._has_dragged:
            self.toggle_control_bubble()

    def on_right_click(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def report_callback_exception(self, exc, value, traceback):
        now = time.monotonic()
        if self._error_dialog_open or now < self._next_error_dialog:
            return  # Already reported; timers keep running while a message box is open.
        log.error("UI callback failed", exc_info=(exc, value, traceback))
        self._error_dialog_open = True
        try:
            messagebox.showerror("Desktop Pets", f"{value}\n\nDetails were saved to app.log.", parent=self)
        finally:
            self._error_dialog_open = False
            self._next_error_dialog = time.monotonic() + ERROR_DIALOG_GAP

    def destroy(self):
        self._closed = True
        for timer in (getattr(self, "_pet_timer", None), getattr(self, "_reminder_timer", None)):
            if timer:
                self.after_cancel(timer)
        super().destroy()


def guard_stdio():
    """A windowed EXE has no console: sys.stdout/stderr are None and any write would raise."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def start_logging(directory):
    """Rotating file log in the data folder. Returns None when the folder is not writable."""
    logging.raiseExceptions = False  # A logging failure must never interrupt reminders.
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / "app.log", maxBytes=500_000, backupCount=2, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    return handler


def load_settings(settings):
    """A damaged preference file falls back to defaults; it never blocks reminders."""
    def validate(data):
        if not isinstance(data, dict) or not isinstance(data.get("pet", "cat"), str):
            raise ValueError("Invalid settings")
        return data
    try:
        return settings.load({"pet": "cat"}, validate)
    except StorageError:
        log.warning("Settings were unreadable; using defaults", exc_info=True)
        return {"pet": "cat"}


def api_port():
    """Fixed for integrations; DESKTOP_PETS_API_PORT exists only for isolated development runs."""
    try:
        port = int(os.environ["DESKTOP_PETS_API_PORT"])
        return port if 0 <= port <= 65535 else API_PORT
    except (KeyError, ValueError):
        return API_PORT


def main(pet_id=None, choose=False):
    guard_stdio()
    directory = data_directory()
    instance = api = app = handler = None
    hooks = sys.excepthook, threading.excepthook
    try:
        instance = SingleInstance(directory)
        if instance.already_running:
            show_message("Desktop Pets is already running. Right-click your pet to choose a pet or quit.")
            return
        handler = start_logging(directory)
        sys.excepthook = lambda *info: log.critical("Unhandled error", exc_info=info)
        threading.excepthook = lambda args: log.error(
            "Unhandled error in %s", args.thread.name if args.thread else "a thread",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        events = queue.Queue()
        status = StatusSnapshot()
        port = api_port()
        try:
            # Reserve the public API port before migrating data or displaying alerts.
            api = ApiServer(None, events, {}, status, port=port)
        except OSError as exc:
            # The mutex above already guarantees one owner of this data folder, so a busy
            # port means another program or Windows account. Reminders still run.
            if pending_legacy_files(directory):
                raise RuntimeError(f"Port {port} is in use, possibly by an older Desktop Pets. "
                                   "Quit it, then start again.") from exc
            log.warning("Local API disabled: port %s is unavailable (%s)", port, exc)
            events.put(("speak", f"Reminders are on. The local API is off because port {port} is busy."))
        migrate_legacy(directory)
        pets = load_pets(lazy=True)
        settings = JsonFile(directory / "settings.json")
        selected = pet_id or load_settings(settings).get("pet", "cat")
        reminders = ReminderService(directory / "reminders.json")
        app = DesktopPet(reminders, settings, pets, events=events, status=status, pet_id=selected, choose=choose)
        if api:
            api.reminders, api.pets = reminders, pets
            api.start()
        log.info("Started Desktop Pets (%s); data folder %s; API %s",
                 "EXE" if getattr(sys, "frozen", False) else "source", directory,
                 f"localhost:{api.port}" if api else "disabled")
        app.mainloop()
    except Exception as exc:
        log.exception("Desktop Pets stopped after an error")
        show_message(f"Desktop Pets could not start: {exc}\n\nData folder: {directory}", error=True)
    finally:
        if api:
            api.stop()
        if app and not app._closed:
            app.destroy()
        if instance:
            instance.close()
        sys.excepthook, threading.excepthook = hooks
        if handler:
            logging.getLogger().removeHandler(handler)
            handler.close()
