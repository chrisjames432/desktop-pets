"""Persistent user data is separate from source files and EXE extraction paths."""
import os
from pathlib import Path
import shutil
import sys

LEGACY_FILES = ("reminders.json", "settings.json")


def data_directory():
    """Stable per-user folder; never the working directory or a PyInstaller temp folder."""
    override = os.environ.get("DESKTOP_PETS_DATA_DIR")
    if override:
        return Path(override).resolve()
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base).resolve() / "DesktopPets"


def pending_legacy_files(directory, source=None):
    """Developer data that a source launch would copy; always empty for an EXE or an override."""
    if getattr(sys, "frozen", False) or os.environ.get("DESKTOP_PETS_DATA_DIR"):
        return []
    directory = Path(directory)
    source = Path(source) if source else Path(__file__).resolve().parent.parent
    return [(source / name, directory / name) for name in LEGACY_FILES
            if (source / name).exists() and not (directory / name).exists()
            and not (directory / (name + ".bak")).exists()]


def migrate_legacy(directory, source=None):
    """Copy this developer's existing data once; never ship or import it in an EXE."""
    Path(directory).mkdir(parents=True, exist_ok=True)
    for old, new in pending_legacy_files(directory, source):
        shutil.copy2(old, new)
