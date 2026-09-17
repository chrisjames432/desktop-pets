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
