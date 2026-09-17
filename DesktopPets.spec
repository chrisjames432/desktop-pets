# Build on Windows: python -m PyInstaller --clean --noconfirm DesktopPets.spec
from pathlib import Path

root = Path(SPECPATH)
assets = root / "desktop_pet" / "pets" / "assets"
data_files = [(str(assets), "desktop_pet/pets/assets")] if assets.exists() else []

# desktop_layout is a top-level module beside the launcher. Pillow loads _tkinter_finder from
# C code when the first PhotoImage is created, so static analysis cannot see that import.
hidden = ["desktop_layout", "PIL.ImageTk", "PIL._imagingtk", "PIL._tkinter_finder", "winsound"]
# Optional Pillow integrations that may exist on the build machine; the app never uses them.
unused = ["numpy", "matplotlib", "IPython", "PyQt5", "PyQt6", "PySide2", "PySide6"]

a = Analysis([str(root / "desktop_pets.py")], pathex=[str(root)],
             binaries=[], datas=data_files, hiddenimports=hidden, hookspath=[],
             hooksconfig={}, runtime_hooks=[], excludes=unused, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="DesktopPets",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / "packaging" / "DesktopPets.ico"))
