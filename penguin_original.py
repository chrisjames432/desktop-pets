"""Emperor Penguin Desktop Pet & Reminder Assistant.

A desktop pet that waddles along your Windows taskbar, looks around,
blinks, flaps its flippers, and alerts you to reminders with speech bubbles
and a local REST API.

Run:
    pythonw penguin.py      (no console window)
    python  penguin.py      (with console output)
    start_penguin.bat       (double-click launcher)

API on 127.0.0.1:8766:
    GET    /reminders                 list all
    POST   /reminders                 body: {"text": "...", "due": "2026-09-22T09:00"}
                                         or {"text": "...", "in_days": 7}
                                         or {"text": "...", "in_hours": 3}
                                         or {"text": "...", "in_minutes": 30}
    POST   /reminders/<id>/dismiss    dismiss / remove
    DELETE /reminders/<id>            delete
    GET    /pet/status                get current pet status
    POST   /pet/speak                 body: {"text": "..."} show speech bubble
    POST   /pet/roam                  body: {"roam": true/false}
"""

import os
import sys
import json
import queue
import random
import socket
import threading
import tkinter as tk
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import ctypes
from ctypes import wintypes

try:
    import winsound
except ImportError:
    winsound = None


def attach_to_interactive_desktop():
    """Attaches thread to the user's interactive desktop (WinSta0\\Default)."""
    try:
        hDesk = ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if hDesk:
            ctypes.windll.user32.SetThreadDesktop(hDesk)
    except Exception:
        pass


from PIL import Image, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "reminders.json")
SPRITE_PATH = os.path.join(HERE, "penguin_sheet.png")

HOST = "127.0.0.1"
DEFAULT_PORT = 8766

# Chroma key color for Windows transparency
TRANS_KEY = "#ff00ff"
TRANS_RGB = (255, 0, 255)

_lock = threading.Lock()
_events = queue.Queue()
_active_port = DEFAULT_PORT


# ------------------------------------------------------------------ storage

def load():
    if not os.path.exists(STORE):
        return {"reminders": []}
    try:
        with open(STORE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"reminders": []}
    data.setdefault("reminders", [])
    return data


def save(data):
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, STORE)


def add_reminder(text, due):
    with _lock:
        data = load()
        rec = {
            "id": max([r["id"] for r in data["reminders"]] + [0]) + 1,
            "text": text,
            "due": due.replace(microsecond=0).isoformat(),
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "notified": False,
        }
        data["reminders"].append(rec)
        save(data)
    _events.put(("refresh", rec))
    return rec


def update_reminder(rid, **fields):
    with _lock:
        data = load()
        for rec in data["reminders"]:
            if rec["id"] == rid:
                rec.update(fields)
                save(data)
                _events.put(("refresh", rec))
                return rec
    return None


def delete_reminder(rid):
    with _lock:
        data = load()
        before = len(data["reminders"])
        data["reminders"] = [r for r in data["reminders"] if r["id"] != rid]
        if len(data["reminders"]) == before:
            return False
        save(data)
    _events.put(("refresh", None))
    return True


def parse_due(payload):
    if "due" in payload:
        raw = str(payload["due"]).replace("Z", "").strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        raise ValueError("unparseable due value: " + raw)
    now = datetime.now()
    for key, unit in (("in_days", "days"), ("in_hours", "hours"),
                      ("in_minutes", "minutes")):
        if key in payload:
            return now + timedelta(**{unit: float(payload[key])})
    raise ValueError("need one of: due, in_days, in_hours, in_minutes")


def human_time(due_iso):
    delta = (datetime.fromisoformat(due_iso) - datetime.now()).total_seconds()
    if delta < 0:
        return "overdue"
    if delta >= 86400:
        days = int(delta // 86400)
        return "in %d day%s" % (days, "" if days == 1 else "s")
    if delta >= 3600:
        return "in %d hours" % int(delta // 3600)
    return "in %d min" % max(1, int(delta // 60))


# ---------------------------------------------------------------------- api

class Handler(BaseHTTPRequestHandler):

    def _send(self, code, obj):
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_GET(self):
        path = self.path.rstrip("/")
        if path == "/reminders":
            with _lock:
                self._send(200, load()["reminders"])
        elif path == "/pet/status":
            with _lock:
                cnt = len(load()["reminders"])
            self._send(200, {
                "pet": "Emperor Penguin",
                "reminders_count": cnt,
                "api_port": _active_port,
                "status": "online"
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.rstrip("/")
        try:
            if path == "/reminders":
                payload = self._read()
                text = str(payload.get("text") or "").strip()
                if not text:
                    self._send(400, {"error": "text is required"})
                    return
                rec = add_reminder(text, parse_due(payload))
                self._send(201, rec)
                return

            if path == "/pet/speak":
                payload = self._read()
                msg = str(payload.get("text") or "Chirp!").strip()
                _events.put(("speak", msg))
                self._send(200, {"status": "ok", "spoke": msg})
                return

            if path == "/pet/roam":
                payload = self._read()
                roam = bool(payload.get("roam", True))
                _events.put(("set_roam", roam))
                self._send(200, {"roam": roam})
                return

            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "reminders" and parts[2] in ("done", "dismiss"):
                ok = delete_reminder(int(parts[1]))
                self._send(200 if ok else 404, {"dismissed": ok})
                return
            self._send(404, {"error": "not found"})
        except Exception as exc:
            self._send(400, {"error": str(exc)})

    def do_DELETE(self):
        parts = self.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "reminders":
            try:
                ok = delete_reminder(int(parts[1]))
            except ValueError:
                self._send(400, {"error": "bad id"})
                return
            self._send(200 if ok else 404, {"deleted": ok})
            return
        self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass


def start_server(port):
    global _active_port
    for p in range(port, port + 10):
        try:
            server = HTTPServer((HOST, p), Handler)
            _active_port = p
            threading.Thread(target=server.serve_forever, daemon=True).start()
            return _active_port
        except OSError:
            continue
    return None


# ----------------------------------------------------------- sprite manager

class PenguinSprites:
    """Loads and slices 128x128 frames from penguin_sheet.png."""

    def __init__(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Sprite sheet not found at: {path}")

        sheet = Image.open(path).convert("RGBA")
        cell_w, cell_h = 128, 128

        def process(img):
            bg = Image.new("RGBA", img.size, TRANS_RGB + (255,))
            comp = Image.alpha_composite(bg, img).convert("RGB")
            return ImageTk.PhotoImage(comp)

        # Row 0: Walk Right (6 frames)
        walk_r = [sheet.crop((i * cell_w, 0, (i + 1) * cell_w, cell_h)) for i in range(6)]
        self.walk_right = [process(f) for f in walk_r]

        # Walk Left (Row 0 flipped horizontally)
        walk_l = [f.transpose(Image.FLIP_LEFT_RIGHT) for f in walk_r]
        self.walk_left = [process(f) for f in walk_l]

        # Row 1: Idle (6 frames)
        idle_raw = [sheet.crop((i * cell_w, cell_h, (i + 1) * cell_w, 2 * cell_h)) for i in range(6)]
        self.idle = [process(f) for f in idle_raw]

        # Row 2: Look around (6 frames)
        look_raw = [sheet.crop((i * cell_w, 2 * cell_h, (i + 1) * cell_w, 3 * cell_h)) for i in range(6)]
        self.look = [process(f) for f in look_raw]

        self.width = cell_w
        self.height = cell_h


# ------------------------------------------------------------- desktop pet

def get_desktop_bounds():
    """Gets desktop monitor bounds across all screens."""
    monitors = []

    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32)
        ]

    def cb(hMonitor, hdc, lprc, dwData):
        mi = MONITORINFOEX()
        mi.cbSize = ctypes.sizeof(MONITORINFOEX)
        ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi))
        monitors.append({
            "left": mi.rcWork.left,
            "right": mi.rcWork.right,
            "top": mi.rcWork.top,
            "bottom": mi.rcWork.bottom,
            "primary": bool(mi.dwFlags & 1)
        })
        return True

    try:
        ctypes.windll.user32.EnumDisplayMonitors(
            0, 0,
            ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)(cb),
            0
        )
    except Exception:
        pass

    if not monitors:
        return 10, 1800, 908, 1000

    min_x = min(m["left"] for m in monitors) + 10
    max_x = max(m["right"] for m in monitors) - 138
    floor_y = max(m["bottom"] for m in monitors) - 124

    # Spawn on the active right monitor near user windows
    spawn_x = 2100 if max_x >= 2200 else (min_x + 300)

    return min_x, max_x, floor_y, spawn_x


class PenguinPet(tk.Tk):

    def __init__(self):
        attach_to_interactive_desktop()
        super().__init__()

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-transparentcolor", TRANS_KEY)
        self.config(bg=TRANS_KEY)

        # Load sprites
        self.sprites = PenguinSprites(SPRITE_PATH)
        self.pet_w = self.sprites.width
        self.pet_h = self.sprites.height

        # Determine monitor bounds
        self.min_x, self.max_x, self.floor_y, spawn_x = get_desktop_bounds()

        self.x = spawn_x
        self.y = self.floor_y
        self.geometry(f"{self.pet_w}x{self.pet_h}+{self.x}+{self.y}")

        # Canvas
        self.canvas = tk.Canvas(self, width=self.pet_w, height=self.pet_h,
                                bg=TRANS_KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.sprite_item = self.canvas.create_image(0, 0, anchor="nw", image=self.sprites.idle[0])

        # State machine
        self.state = "idle"
        self.frame_idx = 0
        self.state_ticks = 0
        self.state_duration = 30
        self.roam_enabled = True
        self.walk_speed = 3

        # Advanced wandering AI (Destination-driven cross-screen walks)
        self.target_x = self.x
        self.journey_active = False
        self.look_direction = 0  # 0=center, -1=left, 1=right

        # Dragging & physics
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._has_dragged = False
        self.vy = 0

        # Interaction bindings
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # Context Menu
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="➕ Add Reminder...", command=self.add_dialog)
        self.menu.add_command(label="📋 View All Reminders", command=self.show_list_dialog)
        self.menu.add_separator()
        self.menu.add_command(label="🚶 Toggle Walking", command=self.toggle_roam)
        self.menu.add_command(label="👋 Wave / Chirp", command=self.chirp)
        self.menu.add_separator()
        self.menu.add_command(label="❌ Quit Penguin", command=self.destroy)

        # Speech bubble / Alert reference
        self.speech_bubble = None
        self.alert_win = None

        self.lift()
        self.attributes("-topmost", True)

        # Start with an initial wandering goal
        self.pick_new_destination()

        # Start loops
        self.tick_pet()
        self.tick_reminders()

    # ------------------------------------------------------- wandering AI

    def pick_new_destination(self):
        """Picks a large-scale random destination across both monitors."""
        if not self.roam_enabled:
            self.journey_active = False
            return

        # 65% chance of a Cross-Screen Journey, 35% chance of a Local Stroll
        roll = random.random()
        total_span = self.max_x - self.min_x

        if roll < 0.65 and total_span > 1200:
            # Cross-Screen Trek: aim for the opposite monitor or far end
            midpoint = (self.min_x + self.max_x) // 2
            if self.x > midpoint:
                # Currently on right side, journey to left monitor!
                self.target_x = random.randint(self.min_x + 60, midpoint - 200)
            else:
                # Currently on left side, journey to right monitor!
                self.target_x = random.randint(midpoint + 200, self.max_x - 60)
        else:
            # Local Stroll: 300 to 800px in a random direction
            dist = random.randint(300, 800) * (1 if random.random() < 0.5 else -1)
            self.target_x = max(self.min_x + 40, min(self.max_x - 40, self.x + dist))

        self.journey_active = True

    def set_state(self, new_state, duration=None):
        self.state = new_state
        self.state_ticks = 0

        if new_state == "look":
            # Calm look: pick a direction (-1 or 1) and hold it
            self.look_direction = random.choice([-1, 1])
            self.frame_idx = 1 if self.look_direction == -1 else 4
            self.state_duration = duration if duration else random.randint(25, 45) # 2.5 to 4.5 seconds

        elif new_state == "idle":
            self.frame_idx = 0
            self.state_duration = duration if duration else random.randint(30, 60) # 3 to 6 seconds

        elif new_state in ("walk_left", "walk_right"):
            self.frame_idx = 0
            self.state_duration = duration if duration else random.randint(50, 120)

        else:
            self.frame_idx = 0
            self.state_duration = duration if duration else 30

    def decide_next_action(self):
        """Determines next action when current state expires."""
        if not self.roam_enabled:
            self.set_state(random.choice(["idle", "look"]))
            return

        # Check if arrived at destination
        if abs(self.x - self.target_x) <= 15:
            self.journey_active = False
            # Arrived! Rest and enjoy the new area
            if random.random() < 0.5:
                self.set_state("idle", random.randint(35, 70))
            else:
                self.set_state("look", random.randint(30, 50))
            # Pick a new destination for next time
            self.pick_new_destination()
            return

        # Continue traveling toward target_x
        # Occasional breather during long walks (25% chance of a 2-second pause)
        if random.random() < 0.25:
            if random.random() < 0.5:
                self.set_state("idle", random.randint(15, 25))
            else:
                self.set_state("look", random.randint(15, 25))
            return

        # Walk toward target_x
        if self.x < self.target_x:
            self.set_state("walk_right")
        else:
            self.set_state("walk_left")

    def tick_pet(self):
        """Main 100ms animation and movement loop."""
        while True:
            try:
                ev, data = _events.get_nowait()
                if ev == "speak":
                    self.show_speech_bubble(str(data))
                elif ev == "set_roam":
                    self.roam_enabled = bool(data)
                    if self.roam_enabled:
                        self.pick_new_destination()
            except queue.Empty:
                break

        # Dragging
        if self._dragging:
            self.canvas.itemconfig(self.sprite_item, image=self.sprites.idle[0])
            self.after(100, self.tick_pet)
            return

        # Gravity fall
        if self.state == "fall":
            self.vy += 3
            self.y += self.vy
            if self.y >= self.floor_y:
                self.y = self.floor_y
                self.vy = 0
                self.set_state("idle", 20)
            self.geometry(f"+{self.x}+{self.y}")
            self.canvas.itemconfig(self.sprite_item, image=self.sprites.look[0])
            self.after(40, self.tick_pet)
            return

        self.state_ticks += 1

        # WALKING LEFT
        if self.state == "walk_left":
            self.frame_idx = (self.frame_idx + 1) % len(self.sprites.walk_left)
            self.canvas.itemconfig(self.sprite_item, image=self.sprites.walk_left[self.frame_idx])
            self.x -= self.walk_speed
            if self.x <= self.min_x:
                self.x = self.min_x
                self.target_x = random.randint(self.min_x + 400, self.max_x - 100)
                self.set_state("walk_right")
            self.geometry(f"+{self.x}+{self.y}")
            if self.x <= self.target_x:
                self.decide_next_action()
                self.after(100, self.tick_pet)
                return

        # WALKING RIGHT
        elif self.state == "walk_right":
            self.frame_idx = (self.frame_idx + 1) % len(self.sprites.walk_right)
            self.canvas.itemconfig(self.sprite_item, image=self.sprites.walk_right[self.frame_idx])
            self.x += self.walk_speed
            if self.x >= self.max_x:
                self.x = self.max_x
                self.target_x = random.randint(self.min_x + 100, self.max_x - 400)
                self.set_state("walk_left")
            self.geometry(f"+{self.x}+{self.y}")
            if self.x >= self.target_x:
                self.decide_next_action()
                self.after(100, self.tick_pet)
                return

        # CALM LOOK (Steady, dignified gaze with occasional blink - NO WIGGLE!)
        elif self.state == "look":
            # Blink midway through the glance (between ticks 14 and 16)
            base_frame = 1 if self.look_direction == -1 else 4
            blink_frame = 2 if self.look_direction == -1 else 5
            if 14 <= self.state_ticks <= 16:
                img = self.sprites.look[blink_frame]
            else:
                img = self.sprites.look[base_frame]
            self.canvas.itemconfig(self.sprite_item, image=img)

        # ALERT (Excited flutter)
        elif self.state == "alert":
            self.frame_idx = (self.frame_idx + 1) % len(self.sprites.idle)
            self.canvas.itemconfig(self.sprite_item, image=self.sprites.idle[self.frame_idx])

        # IDLE (Dignified breathing stance, occasional soft blink)
        else:
            # Frame 0 for calm stance; frame 2 for blink at tick 20-22; frame 3 for soft breath
            if 20 <= (self.state_ticks % 40) <= 22:
                img = self.sprites.idle[2]  # blink
            elif 30 <= (self.state_ticks % 40) <= 34:
                img = self.sprites.idle[3]  # subtle breath
            else:
                img = self.sprites.idle[0]  # noble stance
            self.canvas.itemconfig(self.sprite_item, image=img)

        # Halt walk if dialog or speech bubble is active
        if self.speech_bubble or self.alert_win:
            if self.state not in ("idle", "look", "alert"):
                self.set_state("idle")

        # State expiration
        if self.state != "alert" and self.state_ticks >= self.state_duration:
            self.decide_next_action()

        self.after(100, self.tick_pet)

    # --------------------------------------------------- mouse interactions

    def on_click(self, event):
        self._drag_start_x = event.x_root - self.x
        self._drag_start_y = event.y_root - self.y
        self._has_dragged = False

    def on_drag(self, event):
        self._has_dragged = True
        self._dragging = True
        self.x = event.x_root - self._drag_start_x
        self.y = event.y_root - self._drag_start_y
        self.geometry(f"+{self.x}+{self.y}")
        if self.speech_bubble:
            self.speech_bubble.destroy()
            self.speech_bubble = None

    def on_release(self, event):
        if self._dragging:
            self._dragging = False
            if self.y < self.floor_y:
                self.vy = 0
                self.set_state("fall")
            else:
                self.y = self.floor_y
                self.geometry(f"+{self.x}+{self.y}")
                self.set_state("idle", 20)
            return

        if not self._has_dragged:
            self.toggle_control_bubble()

    def on_right_click(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def toggle_roam(self):
        self.roam_enabled = not self.roam_enabled
        if self.roam_enabled:
            self.pick_new_destination()
            status = "Walking enabled - heading on a journey!"
        else:
            status = "Staying in place."
        self.show_speech_bubble(status, timeout=2500)

    def chirp(self):
        chirps = [
            "Pip pip! 🐧",
            "Waddle waddle!",
            "Brrr! Cozy here!",
            "Keeping watch on your tasks!",
            "Standing by for reminders!"
        ]
        self.show_speech_bubble(random.choice(chirps), timeout=3000)
        self.set_state("look", 30)

    # ------------------------------------------------------- speech bubble

    def show_speech_bubble(self, text, timeout=4000):
        if self.speech_bubble:
            try:
                self.speech_bubble.destroy()
            except Exception:
                pass
            self.speech_bubble = None

        bubble = tk.Toplevel(self)
        self.speech_bubble = bubble
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.configure(bg="#23252e")

        inner = tk.Frame(bubble, bg="#fffef2", padx=12, pady=8, highlightbackground="#333", highlightthickness=1)
        inner.pack(padx=1, pady=1)

        tk.Label(inner, text=text, bg="#fffef2", fg="#222",
                 font=("Segoe UI", 9, "bold"), wraplength=220, justify="center").pack()

        bubble.update_idletasks()
        bw = bubble.winfo_width()
        bh = bubble.winfo_height()
        bx = max(10, min(self.x + (self.pet_w // 2) - (bw // 2), self.max_x - bw))
        by = max(10, self.y - bh - 6)
        bubble.geometry(f"{bw}x{bh}+{bx}+{by}")

        if timeout:
            self.after(timeout, lambda: self._close_bubble(bubble))

    def _close_bubble(self, bubble):
        if self.speech_bubble == bubble:
            try:
                self.speech_bubble.destroy()
            except Exception:
                pass
            self.speech_bubble = None

    def toggle_control_bubble(self):
        if self.speech_bubble:
            self.speech_bubble.destroy()
            self.speech_bubble = None
            return

        with _lock:
            items = load()["reminders"]
        upcoming = [r for r in items if not r.get("notified")]
        upcoming.sort(key=lambda r: r["due"])

        bubble = tk.Toplevel(self)
        self.speech_bubble = bubble
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.configure(bg="#23252e")

        inner = tk.Frame(bubble, bg="#fffdfa", padx=14, pady=10,
                         highlightbackground="#23252e", highlightthickness=1)
        inner.pack(padx=1, pady=1)

        hdr = tk.Frame(inner, bg="#fffdfa")
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="🐧 Penguin Pet", bg="#fffdfa", fg="#1a1c23",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        close = tk.Label(hdr, text="✕", bg="#fffdfa", fg="#888", cursor="hand2",
                         font=("Segoe UI", 8))
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self._close_bubble(bubble))

        if upcoming:
            nxt = upcoming[0]
            desc = f"Next: {nxt['text']} ({human_time(nxt['due'])})"
        else:
            desc = "No pending alerts. All clear!"
        tk.Label(inner, text=desc, bg="#fffdfa", fg="#4a4d57",
                 font=("Segoe UI", 8), wraplength=210, justify="left").pack(anchor="w", pady=(0, 8))

        btns = tk.Frame(inner, bg="#fffdfa")
        btns.pack(fill="x")

        tk.Button(btns, text="+ Add", bg="#f0eee6", fg="#222", relief="groove",
                  font=("Segoe UI", 8), width=7,
                  command=lambda: (self._close_bubble(bubble), self.add_dialog())).pack(side="left", padx=(0, 4))

        tk.Button(btns, text="📋 View", bg="#f0eee6", fg="#222", relief="groove",
                  font=("Segoe UI", 8), width=7,
                  command=lambda: (self._close_bubble(bubble), self.show_list_dialog())).pack(side="left", padx=(0, 4))

        roam_txt = "Stay" if self.roam_enabled else "Walk"
        tk.Button(btns, text=roam_txt, bg="#f0eee6", fg="#222", relief="groove",
                  font=("Segoe UI", 8), width=6,
                  command=lambda: (self.toggle_roam(), self._close_bubble(bubble))).pack(side="left")

        bubble.update_idletasks()
        bw = bubble.winfo_width()
        bh = bubble.winfo_height()
        bx = max(10, min(self.x + (self.pet_w // 2) - (bw // 2), self.max_x - bw))
        by = max(10, self.y - bh - 6)
        bubble.geometry(f"{bw}x{bh}+{bx}+{by}")

    # ---------------------------------------------------- reminder dialogs

    def add_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Reminder")
        dlg.attributes("-topmost", True)
        dlg.geometry(f"320x190+{max(50, self.x - 100)}+{max(50, self.y - 220)}")
        dlg.configure(bg="#f8f7f2")

        tk.Label(dlg, text="What would you like to be reminded of?",
                 bg="#f8f7f2", fg="#222", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        entry_text = tk.Entry(dlg, width=38, font=("Segoe UI", 9))
        entry_text.pack(padx=16)
        entry_text.focus_set()

        tk.Label(dlg, text="Remind me in (days):", bg="#f8f7f2", fg="#444",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(10, 2))
        entry_days = tk.Entry(dlg, width=10, font=("Segoe UI", 9))
        entry_days.insert(0, "7")
        entry_days.pack(anchor="w", padx=16)

        def confirm(_event=None):
            text = entry_text.get().strip()
            if not text:
                return
            try:
                days = float(entry_days.get())
            except ValueError:
                days = 7.0
            add_reminder(text, datetime.now() + timedelta(days=days))
            dlg.destroy()
            self.show_speech_bubble(f"Reminder set for '{text}'!", timeout=3000)

        btns = tk.Frame(dlg, bg="#f8f7f2")
        btns.pack(fill="x", padx=16, pady=16)
        tk.Button(btns, text="Add Reminder", command=confirm, bg="#23252e", fg="#fff",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=2).pack(side="left")
        tk.Button(btns, text="Cancel", command=dlg.destroy, bg="#e0ded7",
                  font=("Segoe UI", 9), padx=10, pady=2).pack(side="left", padx=8)

        dlg.bind("<Return>", confirm)

    def show_list_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("All Reminders")
        dlg.attributes("-topmost", True)
        dlg.geometry(f"360x320+{max(50, self.x - 120)}+{max(50, self.y - 340)}")
        dlg.configure(bg="#f8f7f2")

        hdr = tk.Frame(dlg, bg="#f8f7f2")
        hdr.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(hdr, text="Active Reminders", bg="#f8f7f2", fg="#222",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(hdr, text="+ Add New", command=lambda: (dlg.destroy(), self.add_dialog()),
                  bg="#23252e", fg="#fff", font=("Segoe UI", 8, "bold")).pack(side="right")

        frame_list = tk.Frame(dlg, bg="#f8f7f2")
        frame_list.pack(fill="both", expand=True, padx=16, pady=6)

        def refresh_list():
            for child in frame_list.winfo_children():
                child.destroy()
            with _lock:
                items = load()["reminders"]
            items.sort(key=lambda r: r["due"])

            if not items:
                tk.Label(frame_list, text="No reminders currently set.",
                         bg="#f8f7f2", fg="#888", font=("Segoe UI", 9)).pack(pady=20)
                return

            now = datetime.now()
            for rec in items:
                overdue = datetime.fromisoformat(rec["due"]) <= now
                row = tk.Frame(frame_list, bg="#fff", highlightbackground="#e2e0d8",
                               highlightthickness=1, padx=8, pady=6)
                row.pack(fill="x", pady=3)

                col = tk.Frame(row, bg="#fff")
                col.pack(side="left", fill="x", expand=True)
                tk.Label(col, text=rec["text"], bg="#fff", fg="#111",
                         font=("Segoe UI", 9, "bold")).pack(anchor="w")
                stamp = datetime.fromisoformat(rec["due"]).strftime("%b %d %H:%M")
                tk.Label(col, text=f"{stamp} ({human_time(rec['due'])})",
                         bg="#fff", fg="#b03030" if overdue else "#666",
                         font=("Segoe UI", 8)).pack(anchor="w")

                del_btn = tk.Label(row, text="✕", bg="#fff", fg="#999", cursor="hand2",
                                   font=("Segoe UI", 9, "bold"))
                del_btn.pack(side="right", padx=(6, 0))
                del_btn.bind("<Button-1>", lambda e, rid=rec["id"]: (delete_reminder(rid), refresh_list()))

        refresh_list()

    # ------------------------------------------------------- alert popups

    def alert_popup(self, rec):
        """Displays the reminder alert right over the penguin."""
        if self.alert_win:
            try:
                self.alert_win.destroy()
            except Exception:
                pass

        if winsound:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

        self.set_state("alert")

        win = tk.Toplevel(self)
        self.alert_win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#b03030")

        inner = tk.Frame(win, bg="#fffef8", padx=16, pady=12, highlightthickness=0)
        inner.pack(padx=2, pady=2)

        tk.Label(inner, text="🔔 REMINDER ALERT", bg="#fffef8", fg="#b03030",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")

        tk.Label(inner, text=rec["text"], bg="#fffef8", fg="#1f2229",
                 font=("Segoe UI", 12, "bold"), wraplength=280, justify="left").pack(anchor="w", pady=(4, 12))

        btns = tk.Frame(inner, bg="#fffef8")
        btns.pack(fill="x")

        def finish():
            delete_reminder(rec["id"])
            win.destroy()
            self.alert_win = None
            self.set_state("idle")
            self.show_speech_bubble("Dismissed! Good job! 🐧", timeout=2500)

        def snooze(hours):
            due = (datetime.now() + timedelta(hours=hours)).replace(microsecond=0)
            update_reminder(rec["id"], notified=False, due=due.isoformat())
            win.destroy()
            self.alert_win = None
            self.set_state("idle")
            self.show_speech_bubble(f"Snoozed for {hours} hr(s)!", timeout=2500)

        tk.Button(btns, text="Dismiss", bg="#b03030", fg="#fff", font=("Segoe UI", 9, "bold"),
                  command=finish, width=8, relief="flat").pack(side="left", padx=(0, 6))

        tk.Button(btns, text="1 Hour", bg="#e8e6df", fg="#222", font=("Segoe UI", 8),
                  command=lambda: snooze(1), width=7, relief="groove").pack(side="left", padx=(0, 4))

        tk.Button(btns, text="Tomorrow", bg="#e8e6df", fg="#222", font=("Segoe UI", 8),
                  command=lambda: snooze(24), width=8, relief="groove").pack(side="left")

        win.update_idletasks()
        w = win.winfo_width()
        h = win.winfo_height()
        bx = max(10, min(self.x + (self.pet_w // 2) - (w // 2), self.max_x - w))
        by = max(10, self.y - h - 10)
        win.geometry(f"{w}x{h}+{bx}+{by}")

    def tick_reminders(self):
        """Checks for due reminders every 5 seconds."""
        now = datetime.now()
        with _lock:
            due = [r for r in load()["reminders"]
                   if not r.get("notified")
                   and datetime.fromisoformat(r["due"]) <= now]
        for rec in due:
            update_reminder(rec["id"], notified=True)
            self.alert_popup(rec)
            break

        self.after(5000, self.tick_reminders)


# ----------------------------------------------------------------- launcher

if __name__ == "__main__":
    attach_to_interactive_desktop()
    port = start_server(DEFAULT_PORT)
    pet = PenguinPet()
    pet.mainloop()
