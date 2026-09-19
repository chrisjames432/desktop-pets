"""Windows process ownership. No second app may write the same user's data."""
import ctypes
from ctypes import wintypes
import hashlib


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
_user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
_user32.GetAncestor.restype = wintypes.HWND
_user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
_user32.SetWindowPos.restype = wintypes.BOOL
_user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
_user32.ClientToScreen.restype = wintypes.BOOL
_user32.IsWindow.argtypes = [wintypes.HWND]
_user32.IsWindow.restype = wintypes.BOOL
_user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ulong)]
_user32.SendMessageTimeoutW.restype = wintypes.LPARAM
_ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumWindows.argtypes = [_ENUM, wintypes.LPARAM]
_user32.EnumWindows.restype = wintypes.BOOL

GA_ROOT = 2
HWND_BOTTOM = 1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x2, 0x4, 0x10
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
    """Moves one Tk toplevel between the normal always-on-top layer and behind the desktop icons."""

    def __init__(self, root):
        self.root = root
        self.hwnd = _user32.GetAncestor(root.winfo_id(), GA_ROOT)
        self.parent = None
        self.behind = False

    def set_behind(self):
        if self.behind:
            return True
        target = find_behind_icons_window()
        if not target:
            return False
        self.root.attributes("-topmost", False)
        self.root.update_idletasks()
        if not _user32.SetParent(self.hwnd, target):
            self.root.attributes("-topmost", True)
            return False
        self.parent, self.behind = target, True
        _user32.SetWindowPos(self.hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        return True

    def set_front(self):
        if not self.behind:
            return True
        _user32.SetParent(self.hwnd, None)
        self.parent, self.behind = None, False
        self.root.attributes("-topmost", True)
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
        _user32.SetWindowPos(self.hwnd, None, int(x - origin.x), int(y - origin.y), 0, 0,
                             SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        return True


class NoLayer:
    """Used when layering is unavailable; the pet simply stays in front."""
    behind = False

    def set_behind(self):
        return False

    def set_front(self):
        return True

    def move(self, x, y):
        return False
