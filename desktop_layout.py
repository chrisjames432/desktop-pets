"""Monitor work areas and taskbar-height transitions, independent of Tk."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import math


def get_monitors():
    """Read each monitor's own work area (the area outside reserved taskbars)."""
    class MonitorInfo(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("screen", wintypes.RECT),
                    ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR,
                                       wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                          callback_type, wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    monitors = []

    def collect(handle, hdc, rect, data):
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            monitors.append({"left": info.work.left, "top": info.work.top,
                             "right": info.work.right, "bottom": info.work.bottom,
                             "screen": (info.screen.left, info.screen.top,
                                        info.screen.right, info.screen.bottom),
                             "primary": bool(info.flags & 1)})
        return True

    if not user32.EnumDisplayMonitors(None, None, callback_type(collect), 0) or not monitors:
        raise OSError("Could not read display work areas")
    return monitors


def nearest_monitor(monitors, x, feet_y):
    def distance(m):
        left, top, right, bottom = m["screen"]
        dx = max(left - x, 0, x - (right - 1))
        dy = max(top - feet_y, 0, feet_y - (bottom - 1))
        return dx * dx + dy * dy
    return min(monitors, key=distance)


def floor_at(monitors, x, width, feet_y, foot_offset=96):
    """Support the whole sprite on the highest surface it overlaps.

    Looking at the whole width makes a pet jump before its leading edge hits
    the taskbar, and wait for its trailing edge to clear before dropping.
    The reference height keeps vertically stacked screens in their own row.
    """
    anchor = nearest_monitor(monitors, x + width / 2, feet_y)
    row_top, row_bottom = anchor["screen"][1], anchor["screen"][3]
    covered = [m for m in monitors
               if m["left"] < x + width and m["right"] > x
               and m["screen"][1] < row_bottom and m["screen"][3] > row_top]
    return min(m["bottom"] for m in covered or [anchor]) - foot_offset


def _on_screen(monitors, x, y, width, height):
    """True when work areas cover the whole rectangle. Work areas never overlap each other."""
    covered = sum(max(0, min(x + width, m["right"]) - max(x, m["left"]))
                  * max(0, min(y + height, m["bottom"]) - max(y, m["top"])) for m in monitors)
    return covered >= width * height - 0.5


def keep_inside(monitors, x, y, width, height):
    """Nearest position that keeps a free-moving sprite fully on screen.

    A sprite may straddle monitors that share an edge; that is how a swimmer crosses from one
    to the next. Neighbours rarely line up exactly, so a straddling sprite slides into the
    span they share. Anything else is pulled back into the nearest monitor.
    """
    if _on_screen(monitors, x, y, width, height):
        return x, y
    touched = [m for m in monitors if m["left"] < x + width and m["right"] > x
               and m["top"] < y + height and m["bottom"] > y]
    if len(touched) > 1:
        slid_y = max(max(m["top"] for m in touched), min(min(m["bottom"] for m in touched) - height, y))
        if _on_screen(monitors, x, slid_y, width, height):
            return x, slid_y
        slid_x = max(max(m["left"] for m in touched), min(min(m["right"] for m in touched) - width, x))
        if _on_screen(monitors, slid_x, y, width, height):
            return slid_x, y
    m = nearest_monitor(monitors, x + width / 2, y + height / 2)
    return (max(m["left"], min(m["right"] - width, x)), max(m["top"], min(m["bottom"] - height, y)))


def horizontal_bounds(monitors, width):
    left = min(m["left"] for m in monitors) + 10
    right = max(m["right"] for m in monitors) - width - 10
    return left, max(left, right)


@dataclass
class FloorTransition:
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    elapsed: float = 0.0

    def advance(self, dt):
        distance = abs(self.end_y - self.start_y)
        duration = max(0.35, min(0.9, math.sqrt(distance / 500)))
        self.elapsed += dt
        t = min(1.0, self.elapsed / duration)
        if self.end_y < self.start_y:
            # Lift in place before advancing across the raised surface.
            lift_t = min(1.0, t / 0.7)
            y = self.start_y + (self.end_y - 12 - self.start_y) * (1 - (1-lift_t)**2)
            cross_t = max(0.0, (t - 0.7) / 0.3)
            x = self.start_x + (self.end_x - self.start_x) * cross_t
            y += 12 * cross_t * cross_t
        else:
            x = self.end_x
            y = self.start_y + (self.end_y - self.start_y) * t * t
        if t == 1:
            return self.end_x, self.end_y, True
        return round(x), round(y), False
