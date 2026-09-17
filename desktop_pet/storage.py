"""Atomic JSON persistence with a last-known-good backup and explicit recovery."""
import copy
import json
import logging
import os
from pathlib import Path
import shutil
import time

log = logging.getLogger(__name__)

_READ_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError)
# Antivirus, search indexing, and sync clients briefly lock files on Windows.
_REPLACE_ATTEMPTS = 6
_REPLACE_WAIT_SECONDS = 0.05


class StorageError(RuntimeError):
    pass


def _read(path, validate):
    # utf-8-sig also accepts files saved by editors that prepend a byte-order mark.
    with path.open(encoding="utf-8-sig") as fh:
        return validate(json.load(fh))


class JsonFile:
    def __init__(self, path):
        self.path = Path(path)
        self.backup = self.path.with_suffix(self.path.suffix + ".bak")
        self._last_good = None

    def load(self, default, validate=lambda value: value):
        if not self.path.exists() and not self.backup.exists():
            self._last_good = copy.deepcopy(default)
            return copy.deepcopy(default)
        try:
            result = _read(self.path, validate)
        except _READ_ERRORS as original:
            try:
                result = _read(self.backup, validate)
            except _READ_ERRORS:
                raise StorageError(f"Cannot read {self.path.name}; original files were preserved.") from original
            log.warning("Recovered %s from its backup (%s)", self.path.name, original)
            self._last_good = copy.deepcopy(result)
            try:
                if self.path.exists():
                    shutil.copy2(self.path, self.path.with_name(self.path.name + f".corrupt-{time.time_ns()}"))
                self.save(result)
            except (OSError, StorageError):
                # The recovered data is still usable; the damaged primary stays in place untouched.
                log.exception("Could not rewrite %s after recovery", self.path.name)
        self._last_good = copy.deepcopy(result)
        return copy.deepcopy(result)

    @staticmethod
    def _replace(path, data):
        tmp = path.with_name(path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False, allow_nan=False)
                fh.flush()
                os.fsync(fh.fileno())
            for attempt in range(_REPLACE_ATTEMPTS):
                try:
                    os.replace(tmp, path)
                    break
                except PermissionError:
                    if attempt == _REPLACE_ATTEMPTS - 1:
                        raise
                    time.sleep(_REPLACE_WAIT_SECONDS)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass  # Never mask the original failure; the next save overwrites the temp file.

    def save(self, data):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self._last_good is not None and self.path.exists():
                self._replace(self.backup, self._last_good)
            self._replace(self.path, data)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Could not save {self.path.name}: {exc}") from exc
        self._last_good = copy.deepcopy(data)
