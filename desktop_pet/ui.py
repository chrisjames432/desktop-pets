"""Shared reminder dialogs and pet controls. All methods run on the Tk thread."""
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from .reminders import human_time, local_label, parse_due
from .storage import StorageError
from desktop_layout import nearest_monitor

BG = "#fffcf7"
log = logging.getLogger(__name__)


class PetUI:
    def build_menu(self):
        self.menu.delete(0, "end")
        self.menu.add_command(label="Choose pet...", command=self.choose_pet)
        self.menu.add_separator()
        self.menu.add_command(label="Add reminder...", command=self.add_dialog)
        self.menu.add_command(label="View reminders", command=self.show_list_dialog)
        self.menu.add_command(label="Walk / Stay", command=self.toggle_roam)
        self.menu.add_separator()
        for action, label in self.definition.actions.items():
            self.menu.add_command(label=label, command=lambda a=action: self.do_action(a))
        self.menu.add_separator()
        self.menu.add_command(label="Quit Desktop Pets", command=self.destroy)

    def place_popup(self, window):
        window.update_idletasks()
        w, h = window.winfo_width(), window.winfo_height()
        m = nearest_monitor(self.monitors, self.x + self.pet_w // 2, self.y + self.pet_h - 1)
        x = max(m["left"], min(round(self.x + self.pet_w/2-w/2), m["right"] - w))
        y = max(m["top"], min(round(self.y-h-8), m["bottom"] - h))
        window.geometry(f"+{x}+{y}")

    def choose_pet(self):
        if self.chooser and self.chooser.winfo_exists():
            self.chooser.lift()
            return
        win = self.chooser = tk.Toplevel(self)
        win.title("Choose your desktop pet")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        tk.Label(win, text="Choose your companion", bg=BG, font=("Segoe UI", 16, "bold")).pack(padx=24, pady=(18, 4))
        tk.Label(win, text="Switch anytime. Your reminders stay with you.", bg=BG).pack(pady=(0, 12))
        cards = tk.Frame(win, bg=BG)
        cards.pack(padx=14, pady=(0, 18))
        win.previews = []
        index = 0
        for pet_id in self.pets:
            try:
                pet = self.pets[pet_id]
            except Exception:
                log.exception("Pet %s could not be loaded for the chooser", pet_id)
                continue
            card = tk.Frame(cards, bg="#f1e9dd", padx=15, pady=12)
            card.grid(row=index // 3, column=index % 3, padx=5, pady=5, sticky="nsew")
            frame = pet.animations["idle"].frames[0]
            preview = ImageTk.PhotoImage(Image.alpha_composite(Image.new("RGBA", frame.size, "#f1e9dd"), frame), master=self)
            win.previews.append(preview)
            tk.Label(card, image=preview, bg="#f1e9dd").pack()
            tk.Label(card, text=f"{pet.name} ({pet.label})", bg="#f1e9dd", font=("Segoe UI", 11, "bold")).pack()
            tk.Label(card, text=pet.description, bg="#f1e9dd", wraplength=185).pack(pady=6)
            tk.Button(card, text="Keep this pet" if pet_id == self.pet_id else "Choose this pet",
                      command=lambda p=pet_id: self.select_pet(p)).pack()
            index += 1
        def close():
            win.destroy()
            self.chooser = None
        win.protocol("WM_DELETE_WINDOW", close)
        self.place_popup(win)

    def _close_bubble(self, bubble):
        if self.speech_bubble == bubble:
            bubble.destroy()
            self.speech_bubble = None
            self._control_open = False

    def _bubble(self):
        if self.speech_bubble:
            self._close_bubble(self.speech_bubble)
        bubble = self.speech_bubble = tk.Toplevel(self)
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.configure(bg=BG, padx=12, pady=10, highlightthickness=1, highlightbackground="#665c55")
        return bubble

    def show_speech_bubble(self, text, timeout=4000):
        bubble = self._bubble()
        tk.Label(bubble, text=text, bg=BG, wraplength=240, font=("Segoe UI", 9)).pack()
        self.place_popup(bubble)
        if timeout:
            self.after(timeout, lambda: self._close_bubble(bubble))

    def toggle_control_bubble(self):
        if self.speech_bubble:
            self._close_bubble(self.speech_bubble)
            return
        bubble = self._bubble()
        self._control_open = True
        tk.Label(bubble, text=f"{self.definition.name} ({self.definition.label})", bg=BG,
                 font=("Segoe UI", 10, "bold")).pack()
        upcoming = [r for r in self.reminders.list() if not r["notified"]]
        text = f"Next: {upcoming[0]['text']} ({human_time(upcoming[0]['due'])})" if upcoming else "All clear."
        tk.Label(bubble, text=text, bg=BG, wraplength=260).pack(pady=8)
        buttons = tk.Frame(bubble, bg=BG)
        buttons.pack()
        def invoke(callback):
            self._close_bubble(bubble)
            callback()
        for label, callback in (("Add", self.add_dialog), ("View", self.show_list_dialog),
                                ("Stay" if self.roam_enabled else "Walk", self.toggle_roam),
                                ("Trick", lambda: self.do_action("silly")), ("Pets", self.choose_pet)):
            tk.Button(buttons, text=label, command=lambda cb=callback: invoke(cb)).pack(side="left", padx=2)
        self.place_popup(bubble)

    def add_dialog(self):
        win = tk.Toplevel(self)
        win.title("New reminder")
        win.configure(bg=BG, padx=16, pady=14)
        win.attributes("-topmost", True)
        tk.Label(win, text="What should I remind you about?", bg=BG).pack(anchor="w")
        text = tk.Entry(win, width=42)
        text.pack(pady=(5, 12))
        text.focus_set()
        row = tk.Frame(win, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text="Remind me in", bg=BG).pack(side="left")
        delay = tk.Entry(row, width=7)
        delay.insert(0, "7")
        delay.pack(side="left", padx=6)
        unit = ttk.Combobox(row, state="readonly", values=("minutes", "hours", "days"), width=9)
        unit.set("days")
        unit.pack(side="left")
        error = tk.Label(win, text="", fg="#b03030", bg=BG, wraplength=300)
        error.pack(pady=8)
        def confirm(_event=None):
            try:
                due = parse_due({"in_" + unit.get(): delay.get()})
                self.reminders.add(text.get(), due)
            except (ValueError, OverflowError, StorageError) as exc:
                error.config(text=str(exc))
                return
            win.destroy()
            self.show_speech_bubble("Reminder saved.")
        tk.Button(win, text="Add reminder", command=confirm).pack(anchor="e")
        win.bind("<Return>", confirm)
        self.place_popup(win)

    def show_list_dialog(self):
        win = tk.Toplevel(self)
        win.title("Reminders")
        win.attributes("-topmost", True)
        win.configure(bg=BG)
        win.geometry("420x350")
        tk.Button(win, text="Add reminder", command=self.add_dialog).pack(anchor="e", padx=10, pady=8)
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        rows = tk.Frame(canvas, bg=BG)
        item = canvas.create_window(0, 0, anchor="nw", window=rows)
        rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
        def refresh():
            for child in rows.winfo_children():
                child.destroy()
            items = self.reminders.list()
            if not items:
                tk.Label(rows, text="No reminders set.", bg=BG).pack(pady=20)
            for rec in items:
                row = tk.Frame(rows, bg=BG, padx=12, pady=8)
                row.pack(fill="x")
                tk.Button(row, text="Dismiss", command=lambda rid=rec["id"]: self.reminders.delete(rid)).pack(side="right")
                tk.Label(row, text=rec["text"], wraplength=280, justify="left", bg=BG, font=("Segoe UI", 9, "bold")).pack(anchor="w")
                tk.Label(row, text=f"{local_label(rec['due'])} ({human_time(rec['due'])})", bg=BG).pack(anchor="w")
        self._list_refreshers[win] = refresh
        def close():
            self._list_refreshers.pop(win, None)
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", close)
        refresh()
        self.place_popup(win)

    def refresh_reminder_views(self):
        for win, refresh in list(self._list_refreshers.items()):
            if win.winfo_exists():
                refresh()
            else:
                self._list_refreshers.pop(win, None)
        if self._control_open:
            self._close_bubble(self.speech_bubble)
            self.toggle_control_bubble()
        if self.alert_win and not any(r["id"] == self.alert_id for r in self.reminders.list()):
            self.close_alert()

    def close_alert(self):
        if self.alert_win:
            self.alert_win.destroy()
        self.alert_win = None
        self.alert_id = None
        self.enter_state("sit")

    def alert_popup(self, rec):
        self.enter_state("alert")
        self.alert_id = rec["id"]
        win = self.alert_win = tk.Toplevel(self)
        win.title("Reminder")
        win.attributes("-topmost", True)
        win.configure(bg=BG, padx=16, pady=14)
        tk.Label(win, text="REMINDER", fg="#b05020", bg=BG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(win, text=rec["text"], bg=BG, wraplength=300, justify="left", font=("Segoe UI", 12, "bold")).pack(pady=12)
        buttons = tk.Frame(win, bg=BG)
        buttons.pack()
        def finish(hours=None):
            try:
                if hours is None:
                    self.reminders.delete(rec["id"])
                else:
                    self.reminders.snooze(rec["id"], hours)
            except StorageError as exc:
                messagebox.showerror("Reminder not saved", str(exc), parent=win)
                return
            self.close_alert()
        for label, hours in (("Dismiss", None), ("1 hour", 1), ("Tomorrow", 24)):
            tk.Button(buttons, text=label, command=lambda h=hours: finish(h)).pack(side="left", padx=4)
        # Closing an alert explicitly snoozes it; it cannot silently disappear.
        win.protocol("WM_DELETE_WINDOW", lambda: finish(1))
        self.place_popup(win)
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except (ImportError, RuntimeError):
            pass
