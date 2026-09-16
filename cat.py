"""Patches the Calico Cat - Desktop Pet & Reminder Assistant.

A playful pixel-art desktop pet cat ported from calico-cat.html and
enhanced with silly, cheerful cat animations:
- Cheerful smiling face (:3) and bright eyes (no more sad look!)
- The legendary Butt Wiggle & Pounce!
- Morning Yoga Cat Stretch (tail straight up!)
- Grooming: Licking paw and washing ears with happy eyes (^ ^)
- Playful paw swatting (bap bap bap!)
- Cozy purring and loafing
- Walking journeys across dual screens
- Speech bubbles, reminders, and REST API on port 8766.

Run:
    pythonw cat.py          (no console window)
    python  cat.py          (with console output)
    start_cat.bat           (double-click launcher)

API on 127.0.0.1:8766:
    GET    /reminders
    POST   /reminders                 body: {"text": "...", "in_days": 7}
    POST   /reminders/<id>/dismiss
    DELETE /reminders/<id>
    GET    /pet/status
    POST   /pet/speak                 body: {"text": "..."}
    POST   /pet/roam                  body: {"roam": true/false}
    POST   /pet/action                body: {"action": "stretch"|"pounce"|"wiggle"|"groom"|"swat"|"purr"|"silly"}
"""

import os
import sys
import json
import queue
import random
import socket
import threading
import time
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
SPRITE_PATH = os.path.join(HERE, "cat_sheet.png")

HOST = "127.0.0.1"
DEFAULT_PORT = 8766

# Chroma key color for Windows transparency
TRANS_KEY = "#ff00ff"
TRANS_RGB = (255, 0, 255)

_lock = threading.Lock()
_events = queue.Queue()
_active_port = DEFAULT_PORT
_pet_instance = None


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
        days = int(delta // 3600)
        return "in %d hours" % days
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
            status_data = {
                "pet": "Calico Cat (Patches)",
                "reminders_count": cnt,
                "api_port": _active_port,
                "status": "online"
            }
            if _pet_instance:
                status_data.update({
                    "state": _pet_instance.state,
                    "facing": _pet_instance.facing,
                    "x": _pet_instance.x,
                    "y": _pet_instance.y,
                    "roam_enabled": _pet_instance.roam_enabled
                })
            self._send(200, status_data)
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
                msg = str(payload.get("text") or "Meow! 🐱").strip()
                _events.put(("speak", msg))
                self._send(200, {"status": "ok", "spoke": msg})
                return

            if path == "/pet/action":
                payload = self._read()
                action = str(payload.get("action", "silly")).strip().lower()
                _events.put(("action", action))
                self._send(200, {"status": "ok", "action": action})
                return

            if path == "/pet/meow":
                _events.put(("action", "purr"))
                self._send(200, {"status": "ok", "action": "purr"})
                return

            if path == "/pet/roam":
                payload = self._read()
                roam = bool(payload.get("roam", True))
                _events.put(("set_roam", roam))
                self._send(200, {"roam": roam})
                return

            if path == "/pet/state":
                payload = self._read()
                target_state = str(payload.get("state", "idle")).strip().lower()
                _events.put(("set_state", target_state))
                self._send(200, {"state": target_state})
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


# ------------------------------------------------- calico cat sprite engine

PALETTE = {
    'w': (247, 242, 232),  # white fur
    's': (217, 208, 192),  # far-side fur, in shadow
    'o': (224, 141, 60),   # orange patches
    'k': (58, 50, 46),     # black patches
    'g': (127, 191, 106),  # eyes
    'p': (233, 161, 164),  # nose & inner ear
    'm': (122, 106, 95),   # mouth
    'h': (179, 170, 160),  # whiskers
    'x': (36, 29, 26),     # outline
    'e': (36, 29, 26),     # pupil
}

MAP = {'.': None, 'W': 'w', 'S': 's', 'O': 'o', 'K': 'k', 'G': 'g', 'P': 'p', 'M': 'm', 'X': 'x', 'E': 'e'}

GRID_W, GRID_H, YOFF = 36, 24, 1
SCALE = 4
SPRITE_W = GRID_W * SCALE  # 144
SPRITE_H = GRID_H * SCALE  # 96

# Cheerful Happy Head (:3 smile)
HEAD_SMILE = [
    "..K.....O..",
    ".KKK...OOO.",
    ".KPK...OPO.",
    "..KKWWWOO..",
    ".KKKWWWOOO.",
    "KKKWWWWWOOO",
    "KKGGGWWGGGO",
    "KKGGGWWGGGO",
    "KWWWWWWWWOO",
    "KWWWWPPWWOO",
    ".WWWMWWWMWO.",
    ".WWWWMMWWWO.",
    "..WWWWWWW.."
]

# Wide Dilated Playful Eyes (Excited / Butt wiggle / Swat)
HEAD_PLAYFUL = [
    "..K.....O..",
    ".KKK...OOO.",
    ".KPK...OPO.",
    "..KKWWWOO..",
    ".KKKWWWOOO.",
    "KKKWWWWWOOO",
    "KKEGEWWEGE.",
    "KKEGEWWEGE.",
    "KWWWWWWWWOO",
    "KWWWWPPWWOO",
    ".WWWMWWWMWO.",
    ".WWWWMMWWWO.",
    "..WWWWWWW.."
]

# Happy Squinting Eyes (^ ^) for purring, stretching, loafing
HEAD_HAPPY_EYES = [
    "..K.....O..",
    ".KKK...OOO.",
    ".KPK...OPO.",
    "..KKWWWOO..",
    ".KKKWWWOOO.",
    "KKKWWWWWOOO",
    "KKWEEWWEEOO",
    "KKEEWWWWEE.",
    "KWWWWWWWWOO",
    "KWWWWPPWWOO",
    ".WWWMWWWMWO.",
    ".WWWWMMWWWO.",
    "..WWWWWWW.."
]

BODY_STAND_DATA = [
    "......OOOOOWKKKKWWW...",
    "...KKOOOOOOWKKKKKWWW..",
    ".KKKOOOOOOWWKKKKWWWWW.",
    "KKKOOOOOWWWWKKKWWWWWW.",
    "KKKKOOWWWWWWWWWWWWWWW.",
    "KKKKWWWWWWWWWWWWWWWWW.",
    ".KKWWWWWWWWWWWWWWWWW..",
    "..WWWWWWWWWWWWWWWW....",
    "..WWWWWWWWWWWWWWWW...."
]

BODY_SIT_DATA = [
    "............OOOOWWWWWWW.",
    "........OOOOOOWWWWWWWWW.",
    ".....KKKOOOOOWWWWWWWWWW.",
    "...KKKKKOOOWWWWWWWWWWWW.",
    "..KKKKKKKWWWWWWWWSWWWSS.",
    "..KKKKKKKWWWWWWWWSWWWSS.",
    "..KKKKKKWWWWWWWWWSWWWSS.",
    "..KKKKKWWWWWWWWWWSWWWSS.",
    "...KKKWWWWWWWWWWWSWWWSS.",
    "....WWWWWWWWWWWWWWWWWS.."
]

TAIL_STAND_DATA = [
    [[4, 12], [4, 11], [3, 10], [3, 9], [2, 8], [2, 7], [2, 6], [3, 5], [4, 4], [5, 3]],
    [[4, 12], [4, 11], [3, 10], [3, 9], [2, 8], [2, 7], [1, 6], [1, 5], [2, 4], [3, 3]]
]

WALK_CYCLES = [
    {'A': {'dx': 1, 'dy': 0},  'B': {'dx': -1, 'dy': 0}, 'bob': 1},
    {'A': {'dx': 0, 'dy': -1}, 'B': {'dx': 0, 'dy': 0},  'bob': 0},
    {'A': {'dx': -1, 'dy': 0}, 'B': {'dx': 1, 'dy': 0},  'bob': 1},
    {'A': {'dx': 0, 'dy': 0},  'B': {'dx': 0, 'dy': -1}, 'bob': 0}
]


def make_grid(): return [None] * (GRID_W * GRID_H)
def set_cell(g, x, y, c):
    if 0 <= x < GRID_W and 0 <= y < GRID_H: g[y * GRID_W + x] = c
def box(g, x, y, w, h, c):
    for j in range(h):
        for i in range(w): set_cell(g, x + i, y + j, c)
def stamp(g, rows, ox, oy):
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            c = MAP.get(ch)
            if c: set_cell(g, ox + x, oy + y + YOFF, c)

def outline(g):
    out = list(g)
    for y in range(GRID_H):
        for x in range(GRID_W):
            i = y * GRID_W + x
            if g[i]: continue
            if ((x > 0 and g[i - 1]) or (x < GRID_W - 1 and g[i + 1]) or
                (y > 0 and g[i - GRID_W]) or (y < GRID_H - 1 and g[i + GRID_W])):
                out[i] = 'x'
    return out

def whiskers(out, hx, hy):
    y = hy + 9 + YOFF
    for wx, wy in [(hx - 1, y), (hx - 2, y - 1), (hx + 11, y), (hx + 12, y - 1)]:
        if 0 <= wx < GRID_W and 0 <= wy < GRID_H: out[wy * GRID_W + wx] = 'h'

def grid_to_pil(out):
    img = Image.new('RGBA', (GRID_W, GRID_H), (0, 0, 0, 0))
    pix = img.load()
    for y in range(GRID_H):
        for x in range(GRID_W):
            ck = out[y * GRID_W + x]
            if ck and ck in PALETTE:
                pix[x, y] = PALETTE[ck] + (255,)
    return img.resize((SPRITE_W, SPRITE_H), Image.NEAREST)


def render_stand(dy=0, tail=0, hdx=0, look=0, blink=False, happy=False):
    g = make_grid()
    cells = TAIL_STAND_DATA[tail % 2]
    for i, (tx, ty) in enumerate(cells):
        c = 'o' if i >= len(cells) - 3 else 'k'
        box(g, tx, ty + dy + YOFF, 2, 1, c)
    box(g, 10, 16 + dy + YOFF, 3, 5 - dy, 's')
    box(g, 21, 16 + dy + YOFF, 3, 5 - dy, 's')
    stamp(g, BODY_STAND_DATA, 4, 8 + dy)
    box(g, 6, 16 + dy + YOFF, 3, 5 - dy, 'o')
    box(g, 19, 16 + dy + YOFF, 3, 5 - dy, 'w')
    hx = 23 + hdx
    hy = dy
    head = HEAD_HAPPY_EYES if happy else HEAD_SMILE
    stamp(g, head, hx, hy)
    if not happy:
        y = hy + 6 + YOFF
        for ex in (2, 7):
            if blink:
                box(g, hx + ex, y, 3, 1, 'w')
                box(g, hx + ex, y + 1, 3, 1, 'e')
            else:
                box(g, hx + ex + 1 + look, y, 1, 2, 'e')
    out = outline(g)
    whiskers(out, hx, hy)
    return grid_to_pil(out)


def render_walk(step_idx=0, tail=0):
    g = make_grid()
    w = WALK_CYCLES[step_idx % 4]
    dy = w['bob']
    A = w['A']
    B = w['B']
    cells = TAIL_STAND_DATA[tail % 2]
    for i, (tx, ty) in enumerate(cells):
        c = 'o' if i >= len(cells) - 3 else 'k'
        box(g, tx, ty + dy + YOFF, 2, 1, c)
    box(g, 10 + B['dx'], 16 + B['dy'] + YOFF, 3, 5 - B['dy'], 's')
    box(g, 21 + A['dx'], 16 + A['dy'] + YOFF, 3, 5 - A['dy'], 's')
    stamp(g, BODY_STAND_DATA, 4, 8 + dy)
    box(g, 6 + A['dx'], 16 + A['dy'] + YOFF, 3, 5 - A['dy'], 'o')
    box(g, 19 + B['dx'], 16 + B['dy'] + YOFF, 3, 5 - B['dy'], 'w')
    hx = 23
    hy = dy
    stamp(g, HEAD_SMILE, hx, hy)
    y = hy + 6 + YOFF
    for ex in (2, 7):
        box(g, hx + ex + 1, y, 1, 2, 'e')
    out = outline(g)
    whiskers(out, hx, hy)
    return grid_to_pil(out)


def render_sit(dy=0, tail=0, hdx=0, look=0, blink=False, happy=False):
    g = make_grid()
    stamp(g, BODY_SIT_DATA, 5, 11 + dy)
    box(g, 8, 19 + YOFF, 12, 2, 'k')
    box(g, 20, 16 - (tail % 2) + YOFF, 2, 4 + (tail % 2), 'o')
    hx = 22 + hdx
    hy = dy
    head = HEAD_HAPPY_EYES if happy else HEAD_SMILE
    stamp(g, head, hx, hy)
    if not happy:
        y = hy + 6 + YOFF
        for ex in (2, 7):
            if blink:
                box(g, hx + ex, y, 3, 1, 'w')
                box(g, hx + ex, y + 1, 3, 1, 'e')
            else:
                box(g, hx + ex + 1 + look, y, 1, 2, 'e')
    out = outline(g)
    whiskers(out, hx, hy)
    return grid_to_pil(out)


def render_stretch_frame(phase=0):
    """Cat yoga stretch: front down, paws forward, tail up, happy face!"""
    g = make_grid()
    box(g, 4, 2 + YOFF, 2, 8, 'k')
    box(g, 5, 0 + YOFF, 2, 3, 'o')
    box(g, 8, 15 + YOFF, 3, 6, 's')
    box(g, 5, 15 + YOFF, 3, 6, 'o')
    stamp(g, BODY_STAND_DATA, 4, 9)
    box(g, 22, 19 + YOFF, 6, 2, 'w')
    box(g, 24, 18 + YOFF, 5, 2, 's')
    hx = 23
    hy = 3 if phase == 0 else 4
    stamp(g, HEAD_HAPPY_EYES, hx, hy)
    out = outline(g)
    whiskers(out, hx, hy)
    return grid_to_pil(out)


def render_wiggle_frame(wiggle=0):
    """Butt wiggle: crouching front, tail and butt twitching with excited eyes!"""
    g = make_grid()
    tx = 3 + (wiggle % 3)
    box(g, tx, 5 + YOFF, 2, 7, 'k')
    box(g, tx + 1, 3 + YOFF, 2, 3, 'o')
    box(g, 8, 16 + YOFF, 3, 5, 's')
    box(g, 5, 16 + YOFF, 3, 5, 'o')
    stamp(g, BODY_STAND_DATA, 4, 9 + (wiggle % 2))
    box(g, 18, 18 + YOFF, 4, 3, 'w')
    box(g, 21, 18 + YOFF, 4, 3, 's')
    hx = 23
    hy = 2
    stamp(g, HEAD_PLAYFUL, hx, hy)
    out = outline(g)
    whiskers(out, hx, hy)
    return grid_to_pil(out)


def render_pounce_frame(phase=0):
    """Airborne pounce / leap!"""
    g = make_grid()
    box(g, 1, 14 + YOFF, 6, 2, 'k')
    box(g, 0, 12 + YOFF, 2, 3, 'o')
    stamp(g, BODY_STAND_DATA, 6, 6)
    box(g, 4, 15 + YOFF, 4, 3, 'o')
    box(g, 26, 12 + YOFF, 5, 3, 'w')
    hx = 25
    hy = -1 if phase == 0 else 0
    stamp(g, HEAD_PLAYFUL, hx, hy)
    out = outline(g)
    whiskers(out, hx, hy)
    return grid_to_pil(out)


def render_swat_frame(swat_idx=0):
    """Playful paw swatting in the air!"""
    g = make_grid()
    cells = TAIL_STAND_DATA[0]
    for i, (tx, ty) in enumerate(cells):
        c = 'o' if i >= len(cells) - 3 else 'k'
        box(g, tx, ty + YOFF, 2, 1, c)
    box(g, 10, 16 + YOFF, 3, 5, 's')
    box(g, 6, 16 + YOFF, 3, 5, 'o')
    stamp(g, BODY_STAND_DATA, 4, 8)
    box(g, 18, 16 + YOFF, 3, 5, 's')
    if swat_idx == 0:
        box(g, 25, 11 + YOFF, 5, 3, 'w')
        box(g, 29, 10 + YOFF, 3, 2, 'p')
    elif swat_idx == 1:
        box(g, 27, 14 + YOFF, 5, 3, 'w')
        box(g, 31, 14 + YOFF, 2, 2, 'p')
    else:
        box(g, 25, 17 + YOFF, 5, 3, 'w')
    hx = 23
    hy = 0
    stamp(g, HEAD_PLAYFUL, hx, hy)
    out = outline(g)
    whiskers(out, hx, hy)
    return grid_to_pil(out)


def render_groom_frame(groom_idx=0):
    """Licking paw and washing ear with cute squinty eyes!"""
    g = make_grid()
    stamp(g, BODY_SIT_DATA, 5, 11)
    box(g, 8, 19 + YOFF, 12, 2, 'k')
    box(g, 20, 16 + YOFF, 2, 4, 'o')
    if groom_idx == 0:
        box(g, 23, 11 + YOFF, 3, 4, 'w')
        box(g, 24, 10 + YOFF, 2, 2, 'p')
    else:
        box(g, 25, 6 + YOFF, 3, 4, 'w')
        box(g, 26, 5 + YOFF, 2, 2, 'p')
    hx = 22
    hy = 0
    stamp(g, HEAD_HAPPY_EYES, hx, hy)
    out = outline(g)
    whiskers(out, hx, hy)
    return grid_to_pil(out)


class CatSprites:
    """Pre-renders and caches all animation frames into ImageTk.PhotoImages."""

    def __init__(self):
        self.cache = {}
        self.width = SPRITE_W
        self.height = SPRITE_H

        def to_photo(img_rgba):
            bg = Image.new("RGBA", img_rgba.size, TRANS_RGB + (255,))
            comp = Image.alpha_composite(bg, img_rgba).convert("RGB")
            return ImageTk.PhotoImage(comp)

        # 1. Walk cycles
        for tail in (0, 1):
            for step_idx in range(4):
                img_r = render_walk(step_idx, tail)
                img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
                self.cache[('walk', step_idx, tail, 1)] = to_photo(img_r)
                self.cache[('walk', step_idx, tail, -1)] = to_photo(img_l)

        # 2. Stand & Look (Cheerful :3 smile!)
        for dy in (0, 1):
            for tail in (0, 1):
                for look in (-1, 0, 1):
                    for blink in (False, True):
                        img_r = render_stand(dy=dy, tail=tail, hdx=look, look=look, blink=blink)
                        img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
                        self.cache[('stand', dy, tail, look, blink, 1)] = to_photo(img_r)
                        self.cache[('stand', dy, tail, look, blink, -1)] = to_photo(img_l)

        # 3. Sit (Cheerful :3 smile!)
        for dy in (0, 1):
            for tail in (0, 1):
                for look in (-1, 0, 1):
                    for blink in (False, True):
                        img_r = render_sit(dy=dy, tail=tail, hdx=look, look=look, blink=blink)
                        img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
                        self.cache[('sit', dy, tail, look, blink, 1)] = to_photo(img_r)
                        self.cache[('sit', dy, tail, look, blink, -1)] = to_photo(img_l)

        # 4. Happy Purr (Squinting ^ ^ eyes)
        for dy in (0, 1):
            for tail in (0, 1):
                img_r = render_sit(dy=dy, tail=tail, happy=True)
                img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
                self.cache[('purr', dy, tail, 1)] = to_photo(img_r)
                self.cache[('purr', dy, tail, -1)] = to_photo(img_l)

        # 5. Silly Stretch
        for phase in (0, 1):
            img_r = render_stretch_frame(phase)
            img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
            self.cache[('stretch', phase, 1)] = to_photo(img_r)
            self.cache[('stretch', phase, -1)] = to_photo(img_l)

        # 6. Butt Wiggle
        for w in range(3):
            img_r = render_wiggle_frame(w)
            img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
            self.cache[('wiggle', w, 1)] = to_photo(img_r)
            self.cache[('wiggle', w, -1)] = to_photo(img_l)

        # 7. Pounce Leap
        for p in (0, 1):
            img_r = render_pounce_frame(p)
            img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
            self.cache[('pounce', p, 1)] = to_photo(img_r)
            self.cache[('pounce', p, -1)] = to_photo(img_l)

        # 8. Paw Swat
        for s in (0, 1, 2):
            img_r = render_swat_frame(s)
            img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
            self.cache[('swat', s, 1)] = to_photo(img_r)
            self.cache[('swat', s, -1)] = to_photo(img_l)

        # 9. Groom
        for g in (0, 1):
            img_r = render_groom_frame(g)
            img_l = img_r.transpose(Image.FLIP_LEFT_RIGHT)
            self.cache[('groom', g, 1)] = to_photo(img_r)
            self.cache[('groom', g, -1)] = to_photo(img_l)

    def get_walk(self, step_idx, tail, facing):
        return self.cache[('walk', step_idx % 4, tail % 2, 1 if facing >= 0 else -1)]

    def get_stand(self, dy, tail, look, blink, facing):
        return self.cache[('stand', dy % 2, tail % 2, look, blink, 1 if facing >= 0 else -1)]

    def get_sit(self, dy, tail, look, blink, facing):
        return self.cache[('sit', dy % 2, tail % 2, look, blink, 1 if facing >= 0 else -1)]

    def get_purr(self, dy, tail, facing):
        return self.cache[('purr', dy % 2, tail % 2, 1 if facing >= 0 else -1)]

    def get_stretch(self, phase, facing):
        return self.cache[('stretch', phase % 2, 1 if facing >= 0 else -1)]

    def get_wiggle(self, phase, facing):
        return self.cache[('wiggle', phase % 3, 1 if facing >= 0 else -1)]

    def get_pounce(self, phase, facing):
        return self.cache[('pounce', phase % 2, 1 if facing >= 0 else -1)]

    def get_swat(self, phase, facing):
        return self.cache[('swat', phase % 3, 1 if facing >= 0 else -1)]

    def get_groom(self, phase, facing):
        return self.cache[('groom', phase % 2, 1 if facing >= 0 else -1)]


# ------------------------------------------------------------- desktop pet

def get_desktop_bounds():
    """Gets desktop work area bounds across all monitors."""
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
        return 10, 1800, 940, 1000

    min_x = min(m["left"] for m in monitors) + 10
    max_x = max(m["right"] for m in monitors) - (SPRITE_W + 10)
    floor_y = max(m["bottom"] for m in monitors) - 92

    spawn_x = 2100 if max_x >= 2200 else (min_x + 300)
    return min_x, max_x, floor_y, spawn_x


class CatPet(tk.Tk):

    def __init__(self):
        global _pet_instance
        _pet_instance = self
        attach_to_interactive_desktop()
        super().__init__()

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-transparentcolor", TRANS_KEY)
        self.config(bg=TRANS_KEY)

        # Load & cache sprites
        self.sprites = CatSprites()
        self.pet_w = self.sprites.width
        self.pet_h = self.sprites.height

        # Monitor bounds
        self.min_x, self.max_x, self.floor_y, spawn_x = get_desktop_bounds()

        self.x = spawn_x
        self.y = self.floor_y
        self.geometry(f"{self.pet_w}x{self.pet_h}+{self.x}+{self.y}")

        # Canvas
        self.canvas = tk.Canvas(self, width=self.pet_w, height=self.pet_h,
                                bg=TRANS_KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        init_img = self.sprites.get_stand(0, 0, 0, False, 1)
        self.sprite_item = self.canvas.create_image(0, 0, anchor="nw", image=init_img)

        # State machine
        self.state = "idle"            # 'idle', 'sit', 'look', 'walk', 'stretch', 'wiggle', 'pounce', 'swat', 'groom', 'purr', 'alert', 'fall'
        self.facing = 1                # 1 = right, -1 = left
        self.state_time = 0.0          # seconds in current state
        self.state_duration = 3.5      # seconds
        self.clock = 0.0               # total clock
        self.roam_enabled = True
        self.walk_speed = 70.0         # pixels per second (~3.5 px/50ms tick)

        # Blinking timing
        self.blinking = False
        self.blink_until = 0.0
        self.next_blink = 2.0

        # Wandering AI
        self.target_x = self.x
        self.journey_active = False

        # Dragging & physics
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._has_dragged = False
        self.vy = 0.0

        # Mouse interaction bindings
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # Context Menu with Silly Cat Actions!
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="➕ Add Reminder...", command=self.add_dialog)
        self.menu.add_command(label="📋 View All Reminders", command=self.show_list_dialog)
        self.menu.add_separator()
        self.menu.add_command(label="🚶 Toggle Walking", command=self.toggle_roam)
        self.menu.add_command(label="🛋️ Sit / Stand", command=self.toggle_sit)
        self.menu.add_separator()
        # Silly Cat Actions:
        self.menu.add_command(label="🧘 Big Morning Stretch", command=lambda: self.do_action("stretch"))
        self.menu.add_command(label="🎯 Butt Wiggle & Pounce!", command=lambda: self.do_action("wiggle"))
        self.menu.add_command(label="🧼 Wash Face & Groom", command=lambda: self.do_action("groom"))
        self.menu.add_command(label="🪰 Paw Swat (Bap Bap!)", command=lambda: self.do_action("swat"))
        self.menu.add_command(label="💖 Happy Purr", command=lambda: self.do_action("purr"))
        self.menu.add_separator()
        self.menu.add_command(label="❌ Quit Cat", command=self.destroy)

        # Speech bubble / Alert reference
        self.speech_bubble = None
        self.alert_win = None

        self.lift()
        self.attributes("-topmost", True)

        # Start with initial walk destination
        self.pick_new_destination()

        # Loops
        self.last_tick = time.time()
        self.tick_pet()
        self.tick_reminders()

    # ------------------------------------------------------- wandering & silly AI

    def pick_new_destination(self):
        """Picks a large-scale random destination across both screens."""
        if not self.roam_enabled:
            self.journey_active = False
            return

        roll = random.random()
        total_span = self.max_x - self.min_x

        if roll < 0.65 and total_span > 1200:
            midpoint = (self.min_x + self.max_x) // 2
            if self.x > midpoint:
                self.target_x = random.randint(self.min_x + 60, midpoint - 200)
            else:
                self.target_x = random.randint(midpoint + 200, self.max_x - 60)
        else:
            dist = random.randint(300, 800) * (1 if random.random() < 0.5 else -1)
            self.target_x = max(self.min_x + 40, min(self.max_x - 40, self.x + dist))

        self.journey_active = True
        self.facing = 1 if self.target_x > self.x else -1

    def enter_state(self, new_state, duration=None):
        self.state = new_state
        self.state_time = 0.0

        if new_state == "walk":
            if abs(self.target_x - self.x) < 20:
                self.pick_new_destination()
            self.facing = 1 if self.target_x > self.x else -1
            self.state_duration = duration if duration else random.uniform(5.0, 12.0)

        elif new_state == "sit":
            self.state_duration = duration if duration else random.uniform(4.0, 7.0)

        elif new_state == "idle":
            self.state_duration = duration if duration else random.uniform(2.5, 5.0)

        elif new_state == "look":
            self.state_duration = duration if duration else 3.4

        elif new_state == "stretch":
            self.state_duration = duration if duration else 2.6

        elif new_state == "wiggle":
            self.state_duration = duration if duration else 1.8

        elif new_state == "pounce":
            self.state_duration = duration if duration else 0.8

        elif new_state == "swat":
            self.state_duration = duration if duration else 2.4

        elif new_state == "groom":
            self.state_duration = duration if duration else 3.2

        elif new_state == "purr":
            self.state_duration = duration if duration else 3.5

        else:
            self.state_duration = duration if duration else 3.0

    def choose_spontaneous_action(self):
        """Randomly chooses an activity: calm poses or silly cat behaviors!"""
        # 40% chance of a silly cat antic when taking a break!
        if random.random() < 0.40:
            silly_choice = random.choice(["stretch", "wiggle", "groom", "swat", "purr"])
            return silly_choice

        # Otherwise standard relaxed poses
        opts = [('idle', 3), ('sit', 3), ('look', 2)]
        total = sum(w for _, w in opts)
        r = random.uniform(0, total)
        for s, w in opts:
            r -= w
            if r <= 0:
                return s
        return 'idle'

    def decide_next_action(self):
        """Determines next action when state timer expires."""
        if not self.roam_enabled:
            self.enter_state(self.choose_spontaneous_action())
            return

        # Check if reached destination
        if abs(self.x - self.target_x) <= 20:
            self.journey_active = False
            self.enter_state(self.choose_spontaneous_action())
            self.pick_new_destination()
            return

        # If just finished a silly antic or resting, resume walking 75% of the time
        if self.state in ("idle", "sit", "look", "stretch", "pounce", "groom", "swat", "purr"):
            if random.random() < 0.75:
                self.enter_state("walk")
            else:
                self.enter_state(self.choose_spontaneous_action())
            return

        # If walking expired before reaching, take a short breather / antic
        if random.random() < 0.4:
            self.enter_state(self.choose_spontaneous_action())
        else:
            self.enter_state("walk")

    def do_action(self, action_name):
        """Triggers a specific silly or fun action."""
        if action_name == "silly":
            action_name = random.choice(["stretch", "wiggle", "groom", "swat", "purr"])

        if action_name == "stretch":
            self.enter_state("stretch")
            self.show_speech_bubble("*streeeeetches paws* 🧘", timeout=2500)
        elif action_name in ("wiggle", "pounce"):
            self.enter_state("wiggle")
            self.show_speech_bubble("*butt wiggle... target locked!* 🎯", timeout=2000)
        elif action_name == "groom":
            self.enter_state("groom")
            self.show_speech_bubble("*mlem mlem... washes ears* 🧼", timeout=2500)
        elif action_name == "swat":
            self.enter_state("swat")
            self.show_speech_bubble("*BAP BAP BAP!* 🪰🐾", timeout=2200)
        elif action_name == "purr":
            self.enter_state("purr")
            self.show_speech_bubble("Purrrrrrrrrr... 💖", timeout=3000)
        elif action_name in ("sit", "idle", "look", "walk"):
            self.enter_state(action_name)

    # ---------------------------------------------------- animation tick

    def tick_pet(self):
        now = time.time()
        dt = min(0.1, max(0.01, now - self.last_tick))
        self.last_tick = now

        # Process cross-thread events
        while True:
            try:
                ev, data = _events.get_nowait()
                if ev == "speak":
                    self.show_speech_bubble(str(data))
                elif ev == "action":
                    self.do_action(str(data))
                elif ev == "set_roam":
                    self.roam_enabled = bool(data)
                    if self.roam_enabled:
                        self.pick_new_destination()
                        self.enter_state("walk")
                    else:
                        self.enter_state("sit")
                elif ev == "set_state":
                    self.do_action(str(data))
            except queue.Empty:
                break

        # Dragging
        if self._dragging:
            img = self.sprites.get_stand(0, 0, 0, False, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)
            self.after(50, self.tick_pet)
            return

        # Gravity fall physics
        if self.state == "fall":
            self.vy += 380.0 * dt
            self.y += int(self.vy * dt)
            if self.y >= self.floor_y:
                self.y = self.floor_y
                self.vy = 0.0
                self.enter_state("sit", 3.0)
            self.geometry(f"+{self.x}+{self.y}")
            img = self.sprites.get_stand(1, 0, 0, False, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)
            self.after(30, self.tick_pet)
            return

        self.state_time += dt
        self.clock += dt

        # Blinking logic (140ms blink every 2.5-6.5 seconds)
        if not self.blinking and self.clock >= self.next_blink:
            self.blinking = True
            self.blink_until = self.clock + 0.14
        elif self.blinking and self.clock >= self.blink_until:
            self.blinking = False
            self.next_blink = self.clock + random.uniform(2.5, 6.0)

        # Halt walking if a dialog or speech bubble is active
        if (self.speech_bubble or self.alert_win) and self.state == "walk":
            self.enter_state("sit")

        # ---------------- RENDERING PER STATE ----------------

        # 1. WALKING
        if self.state == "walk":
            step_dist = self.walk_speed * dt
            if self.facing > 0:
                self.x += int(step_dist)
                if self.x >= self.max_x:
                    self.x = self.max_x
                    self.facing = -1
                    self.target_x = random.randint(self.min_x + 100, self.max_x - 400)
                elif self.x >= self.target_x:
                    self.x = self.target_x
                    self.decide_next_action()
            else:
                self.x -= int(step_dist)
                if self.x <= self.min_x:
                    self.x = self.min_x
                    self.facing = 1
                    self.target_x = random.randint(self.min_x + 400, self.max_x - 100)
                elif self.x <= self.target_x:
                    self.x = self.target_x
                    self.decide_next_action()

            self.geometry(f"+{self.x}+{self.y}")
            step_idx = int(self.state_time / 0.13) % 4
            tail = int(self.state_time / 0.39) % 2
            img = self.sprites.get_walk(step_idx, tail, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 2. SITTING
        elif self.state == "sit":
            dy = int(self.state_time / 0.85) % 2
            tail = int(self.state_time / 0.75) % 2
            img = self.sprites.get_sit(dy, tail, 0, self.blinking, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 3. LOOKING AROUND
        elif self.state == "look":
            p = self.state_time
            look = 0 if p < 0.4 else (-1 if p < 1.4 else (0 if p < 1.8 else (1 if p < 2.9 else 0)))
            dy = int(self.state_time / 0.85) % 2
            tail = int(self.state_time / 0.75) % 2
            img = self.sprites.get_stand(dy, tail, look, self.blinking, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 4. BIG YOGA STRETCH
        elif self.state == "stretch":
            phase = 0 if self.state_time < 1.3 else 1
            img = self.sprites.get_stretch(phase, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 5. BUTT WIGGLE (Prep for Pounce)
        elif self.state == "wiggle":
            wiggle_step = int(self.state_time / 0.18) % 3
            img = self.sprites.get_wiggle(wiggle_step, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)
            # When wiggle finishes, launch POUNCE!
            if self.state_time >= self.state_duration:
                self.enter_state("pounce")
                self.after(50, self.tick_pet)
                return

        # 6. POUNCE LEAP
        elif self.state == "pounce":
            # Jump forward
            jump_step = self.facing * int(120 * dt)
            self.x = max(self.min_x, min(self.max_x, self.x + jump_step))
            self.geometry(f"+{self.x}+{self.y}")
            phase = 0 if self.state_time < 0.4 else 1
            img = self.sprites.get_pounce(phase, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 7. PAW SWAT (Bap bap bap!)
        elif self.state == "swat":
            swat_idx = int(self.state_time / 0.15) % 3
            img = self.sprites.get_swat(swat_idx, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 8. GROOMING / FACE WASH
        elif self.state == "groom":
            groom_idx = int(self.state_time / 0.4) % 2
            img = self.sprites.get_groom(groom_idx, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 9. HAPPY PURR
        elif self.state == "purr":
            dy = int(self.state_time / 0.6) % 2
            tail = int(self.state_time / 0.5) % 2
            img = self.sprites.get_purr(dy, tail, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 10. REMINDER ALERT
        elif self.state == "alert":
            dy = int(self.state_time / 0.4) % 2
            tail = int(self.state_time / 0.3) % 2
            img = self.sprites.get_sit(dy, tail, 0, False, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # 11. IDLE STANDING
        else:
            dy = int(self.state_time / 0.85) % 2
            tail = int(self.state_time / 0.75) % 2
            img = self.sprites.get_stand(dy, tail, 0, self.blinking, self.facing)
            self.canvas.itemconfig(self.sprite_item, image=img)

        # State expiration
        if self.state not in ("alert", "wiggle") and self.state_time >= self.state_duration:
            self.decide_next_action()

        self.after(50, self.tick_pet)

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
                self.vy = 0.0
                self.state = "fall"
            else:
                self.y = self.floor_y
                self.geometry(f"+{self.x}+{self.y}")
                self.enter_state("sit", 3.0)
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
            self.enter_state("walk")
            status = "Walking enabled! Exploring the desktop."
        else:
            self.enter_state("sit")
            status = "Sitting comfortably in place."
        self.show_speech_bubble(status, timeout=2500)

    def toggle_sit(self):
        if self.state == "sit":
            self.enter_state("idle", 3.0)
            self.show_speech_bubble("*stands up cheerfully* 🐾", timeout=2000)
        else:
            self.enter_state("sit", 5.0)
            self.show_speech_bubble("*curls up happily* 🐱", timeout=2000)

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
        bubble.configure(bg="#2a2421")

        inner = tk.Frame(bubble, bg="#fffcf7", padx=12, pady=8,
                         highlightbackground="#4a3e39", highlightthickness=1)
        inner.pack(padx=1, pady=1)

        tk.Label(inner, text=text, bg="#fffcf7", fg="#2a2421",
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
        bubble.configure(bg="#2a2421")

        inner = tk.Frame(bubble, bg="#fffcf7", padx=14, pady=10,
                         highlightbackground="#4a3e39", highlightthickness=1)
        inner.pack(padx=1, pady=1)

        hdr = tk.Frame(inner, bg="#fffcf7")
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="🐱 Patches (Calico Cat)", bg="#fffcf7", fg="#2a2421",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        close = tk.Label(hdr, text="✕", bg="#fffcf7", fg="#888", cursor="hand2",
                         font=("Segoe UI", 8))
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self._close_bubble(bubble))

        if upcoming:
            nxt = upcoming[0]
            desc = f"Next: {nxt['text']} ({human_time(nxt['due'])})"
        else:
            desc = "All clear! Ready to play! :3"
        tk.Label(inner, text=desc, bg="#fffcf7", fg="#524842",
                 font=("Segoe UI", 8), wraplength=220, justify="left").pack(anchor="w", pady=(0, 8))

        btns = tk.Frame(inner, bg="#fffcf7")
        btns.pack(fill="x")

        tk.Button(btns, text="+ Add", bg="#f3ede3", fg="#222", relief="groove",
                  font=("Segoe UI", 8), width=6,
                  command=lambda: (self._close_bubble(bubble), self.add_dialog())).pack(side="left", padx=(0, 3))

        tk.Button(btns, text="📋 View", bg="#f3ede3", fg="#222", relief="groove",
                  font=("Segoe UI", 8), width=6,
                  command=lambda: (self._close_bubble(bubble), self.show_list_dialog())).pack(side="left", padx=(0, 3))

        roam_txt = "Stay" if self.roam_enabled else "Walk"
        tk.Button(btns, text=roam_txt, bg="#f3ede3", fg="#222", relief="groove",
                  font=("Segoe UI", 8), width=5,
                  command=lambda: (self.toggle_roam(), self._close_bubble(bubble))).pack(side="left", padx=(0, 3))

        # Silly Trick Button!
        tk.Button(btns, text="🐾 Silly", bg="#f3ede3", fg="#b05020", relief="groove",
                  font=("Segoe UI", 8, "bold"), width=6,
                  command=lambda: (self._close_bubble(bubble), self.do_action("silly"))).pack(side="left")

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
        dlg.geometry(f"320x190+{max(50, self.x - 80)}+{max(50, self.y - 220)}")
        dlg.configure(bg="#f8f6f0")

        tk.Label(dlg, text="What would you like to be reminded of?",
                 bg="#f8f6f0", fg="#222", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        entry_text = tk.Entry(dlg, width=38, font=("Segoe UI", 9))
        entry_text.pack(padx=16)
        entry_text.focus_set()

        tk.Label(dlg, text="Remind me in (days):", bg="#f8f6f0", fg="#444",
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

        btns = tk.Frame(dlg, bg="#f8f6f0")
        btns.pack(fill="x", padx=16, pady=16)
        tk.Button(btns, text="Add Reminder", command=confirm, bg="#2a2421", fg="#fff",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=2).pack(side="left")
        tk.Button(btns, text="Cancel", command=dlg.destroy, bg="#e2ddd5",
                  font=("Segoe UI", 9), padx=10, pady=2).pack(side="left", padx=8)

        dlg.bind("<Return>", confirm)

    def show_list_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("All Reminders")
        dlg.attributes("-topmost", True)
        dlg.geometry(f"360x320+{max(50, self.x - 100)}+{max(50, self.y - 340)}")
        dlg.configure(bg="#f8f6f0")

        hdr = tk.Frame(dlg, bg="#f8f6f0")
        hdr.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(hdr, text="Active Reminders", bg="#f8f6f0", fg="#222",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(hdr, text="+ Add New", command=lambda: (dlg.destroy(), self.add_dialog()),
                  bg="#2a2421", fg="#fff", font=("Segoe UI", 8, "bold")).pack(side="right")

        frame_list = tk.Frame(dlg, bg="#f8f6f0")
        frame_list.pack(fill="both", expand=True, padx=16, pady=6)

        def refresh_list():
            for child in frame_list.winfo_children():
                child.destroy()
            with _lock:
                items = load()["reminders"]
            items.sort(key=lambda r: r["due"])

            if not items:
                tk.Label(frame_list, text="No reminders currently set.",
                         bg="#f8f6f0", fg="#888", font=("Segoe UI", 9)).pack(pady=20)
                return

            now = datetime.now()
            for rec in items:
                overdue = datetime.fromisoformat(rec["due"]) <= now
                row = tk.Frame(frame_list, bg="#fff", highlightbackground="#e2ddd5",
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
        """Displays reminder alert modal with dismiss and snooze buttons."""
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

        self.enter_state("alert")

        win = tk.Toplevel(self)
        self.alert_win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#d9532f")

        inner = tk.Frame(win, bg="#fffdf7", padx=16, pady=12, highlightthickness=0)
        inner.pack(padx=2, pady=2)

        tk.Label(inner, text="🔔 REMINDER ALERT", bg="#fffdf7", fg="#d9532f",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")

        tk.Label(inner, text=rec["text"], bg="#fffdf7", fg="#2a2421",
                 font=("Segoe UI", 12, "bold"), wraplength=280, justify="left").pack(anchor="w", pady=(4, 12))

        btns = tk.Frame(inner, bg="#fffdf7")
        btns.pack(fill="x")

        def finish():
            delete_reminder(rec["id"])
            win.destroy()
            self.alert_win = None
            self.enter_state("sit", 3.0)
            self.show_speech_bubble("Dismissed! Good job! 🐱", timeout=2500)

        def snooze(hours):
            due = (datetime.now() + timedelta(hours=hours)).replace(microsecond=0)
            update_reminder(rec["id"], notified=False, due=due.isoformat())
            win.destroy()
            self.alert_win = None
            self.enter_state("sit", 3.0)
            self.show_speech_bubble(f"Snoozed for {hours} hr(s)! 🐾", timeout=2500)

        tk.Button(btns, text="Dismiss", bg="#d9532f", fg="#fff", font=("Segoe UI", 9, "bold"),
                  command=finish, width=8, relief="flat").pack(side="left", padx=(0, 6))

        tk.Button(btns, text="1 Hour", bg="#eae4d8", fg="#222", font=("Segoe UI", 8),
                  command=lambda: snooze(1), width=7, relief="groove").pack(side="left", padx=(0, 4))

        tk.Button(btns, text="Tomorrow", bg="#eae4d8", fg="#222", font=("Segoe UI", 8),
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
    pet = CatPet()
    pet.mainloop()
