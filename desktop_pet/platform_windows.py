"""Windows process ownership. No second app may write the same user's data."""
import ctypes
from ctypes import wintypes
import hashlib
import struct


class SingleInstance:
    def __init__(self, data_path):
        key = hashlib.sha256(str(data_path.resolve()).casefold().encode()).hexdigest()[:20]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateMutexW(None, False, "Local\\DesktopPets-" + key)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.already_running = ctypes.get_last_error() == 183

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def show_message(text, error=False):
    ctypes.windll.user32.MessageBoxW(None, text, "Desktop Pets", 0x10 if error else 0x40)


# ---------------------------------------------------------------- desktop layering
# Windows draws the desktop as Progman -> SHELLDLL_DefView (the icon list). A window parented
# behind that list shows through the icons' transparent background, so a pet can swim behind
# the folders. This is the technique animated-wallpaper apps use. Clicks never reach a window
# back there, so a pet must come to the front on its own.
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowW.restype = wintypes.HWND
_user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowExW.restype = wintypes.HWND
_user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
_user32.SetParent.restype = wintypes.HWND
_user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
_user32.SetWindowPos.restype = wintypes.BOOL
_user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
_user32.ClientToScreen.restype = wintypes.BOOL
_user32.IsWindow.argtypes = [wintypes.HWND]
_user32.IsWindow.restype = wintypes.BOOL
_user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ulong)]
_user32.SendMessageTimeoutW.restype = wintypes.LPARAM
_user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD]
_user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
_user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
_user32.SetWindowRgn.restype = ctypes.c_int
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL
_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.ReleaseDC.restype = ctypes.c_int
_user32.PaintDesktop.argtypes = [wintypes.HDC]
_user32.PaintDesktop.restype = wintypes.BOOL
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_gdi32.IntersectClipRect.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
_gdi32.IntersectClipRect.restype = ctypes.c_int
_gdi32.ExtCreateRegion.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_char_p]
_gdi32.ExtCreateRegion.restype = wintypes.HANDLE
_gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
_gdi32.DeleteObject.restype = wintypes.BOOL
_ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumWindows.argtypes = [_ENUM, wintypes.LPARAM]
_user32.EnumWindows.restype = wintypes.BOOL

HWND_BOTTOM = 1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20
GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_POPUP, WS_CHILD, WS_EX_LAYERED = 0x80000000, 0x40000000, 0x00080000
LWA_COLORKEY, LWA_ALPHA = 0x1, 0x2
RDH_RECTANGLES = 1
WM_SPAWN_WORKER = 0x052C


def find_behind_icons_window():
    """The window to parent a pet to so it renders behind the desktop icons, or None."""
    progman = _user32.FindWindowW("Progman", None)
    if not progman:
        return None
    result = ctypes.c_ulong()
    _user32.SendMessageTimeoutW(progman, WM_SPAWN_WORKER, 0, 0, 0, 1000, ctypes.byref(result))
    worker = _user32.FindWindowExW(progman, None, "WorkerW", None)   # Windows 11 24H2 and later
    if worker:
        return worker
    found = []

    @_ENUM
    def visit(hwnd, _lparam):
        if _user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            found.append(_user32.FindWindowExW(None, hwnd, "WorkerW", None))  # classic layout
            return False
        return True

    _user32.EnumWindows(visit, 0)
    if found and found[0]:
        return found[0]
    return progman   # Parented at the bottom of Progman, a window still sits behind the icon list.


class DesktopLayer:
    """Moves one Tk toplevel between the normal always-on-top layer and behind the desktop icons.

    In front, Tk's transparent colour hides the sprite background. A colour-keyed (layered)
    window does not render at all once it is parented into the desktop, so behind the icons the
    window becomes a plain child cut to the sprite's outline with a window region instead.
    The desktop never repaints what a child window uncovers, so every move and every new
    outline is followed by repainting the wallpaper over the rectangle the pet just occupied.
    """

    def __init__(self, root):
        self.root = root
        self.hwnd = self.parent = None
        self.behind = False

    def _frame(self):
        """Tk's outer frame window, or None until it exists.

        Tk draws into an inner window and only wraps it in a frame once the toplevel is mapped,
        and it may rebuild that frame when window attributes change. Reparenting the inner
        window instead tears it out of its frame: it loses the transparent colour and stops
        following the pet. So the frame is looked up at the moment of use, never cached early.
        """
        inner = self.root.winfo_id()
        frame = int(self.root.wm_frame(), 16)
        return frame if frame and frame != inner else None

    def _restyle(self, child):
        style = _user32.GetWindowLongPtrW(self.hwnd, GWL_STYLE)
        ex_style = _user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        if child:
            style, ex_style = (style & ~WS_POPUP) | WS_CHILD, ex_style & ~WS_EX_LAYERED
        else:
            style, ex_style = (style & ~WS_CHILD) | WS_POPUP, ex_style | WS_EX_LAYERED
        _user32.SetWindowLongPtrW(self.hwnd, GWL_STYLE, style)
        _user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex_style)
        if not child:
            red, green, blue = (v >> 8 for v in self.root.winfo_rgb(self.root.wm_attributes("-transparentcolor")))
            _user32.SetLayeredWindowAttributes(self.hwnd, red | green << 8 | blue << 16, 255, LWA_COLORKEY | LWA_ALPHA)

    def _set_region(self, rects):
        """Show only these (left, top, right, bottom) pixel runs; None shows the whole window."""
        region = None
        if rects is not None:
            bounds = (min(r[0] for r in rects), rects[0][1], max(r[2] for r in rects), rects[-1][3]) if rects else (0, 0, 0, 0)
            data = struct.pack("<4L4l", 32, RDH_RECTANGLES, len(rects), 16 * len(rects), *bounds)
            data += b"".join(struct.pack("<4l", *r) for r in rects)
            region = _gdi32.ExtCreateRegion(None, len(data), data)
            if not region:
                return False
        if _user32.SetWindowRgn(self.hwnd, region, True):
            return True                 # Windows owns the region from here on.
        if region:
            _gdi32.DeleteObject(region)
        return False

    def _rect(self):
        """The pet window's rectangle in the parent's client coordinates."""
        rect, origin = wintypes.RECT(), wintypes.POINT(0, 0)
        _user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        _user32.ClientToScreen(self.parent, ctypes.byref(origin))
        return rect.left - origin.x, rect.top - origin.y, rect.right - origin.x, rect.bottom - origin.y

    def _heal(self, rect):
        """Repaint the wallpaper inside rect. The pet itself is clipped out while it is a child."""
        hdc = _user32.GetDC(self.parent)
        if hdc:
            _gdi32.IntersectClipRect(hdc, *rect)
            _user32.PaintDesktop(hdc)
            _user32.ReleaseDC(self.parent, hdc)

    def set_behind(self, shape):
        """shape: the sprite's opaque pixel runs, from top to bottom."""
        if self.behind:
            return True
        target = find_behind_icons_window()
        if not target:
            return False
        self.root.attributes("-topmost", False)
        self.root.update_idletasks()
        self.hwnd = self._frame()
        if not self.hwnd or not self._set_region(shape):
            self.root.attributes("-topmost", True)
            return False
        self._restyle(child=True)
        if not _user32.SetParent(self.hwnd, target):
            self._restore()
            return False
        self.parent, self.behind = target, True
        _user32.SetWindowPos(self.hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        return True

    def shape(self, shape):
        """Follow the animation while behind the icons. Does nothing in front."""
        if self.behind and _user32.IsWindow(self.parent):
            self._set_region(shape)
            self._heal(self._rect())

    def _restore(self):
        self._restyle(child=False)
        self._set_region(None)
        self.root.attributes("-topmost", True)
        _user32.SetWindowPos(self.hwnd, None, 0, 0, 0, 0,
                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def set_front(self):
        if not self.behind:
            return True
        alive = _user32.IsWindow(self.parent)
        rect = self._rect() if alive else None
        _user32.SetParent(self.hwnd, None)
        if alive:
            self._heal(rect)
        self.parent, self.behind = None, False
        self._restore()
        return True

    def move(self, x, y):
        """Place the window at screen coordinates while behind the icons. Returns False when in front."""
        if not self.behind:
            return False
        if not _user32.IsWindow(self.parent):
            self.set_front()          # Explorer restarted; come back to the normal layer.
            return False
        origin = wintypes.POINT(0, 0)
        _user32.ClientToScreen(self.parent, ctypes.byref(origin))
        vacated = self._rect()
        _user32.SetWindowPos(self.hwnd, None, int(x - origin.x), int(y - origin.y), 0, 0,
                             SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        self._heal(vacated)
        return True


class NoLayer:
    """Used when layering is unavailable; the pet simply stays in front."""
    behind = False

    def set_behind(self, shape):
        return False

    def set_front(self):
        return True

    def shape(self, shape):
        pass

    def move(self, x, y):
        return False
