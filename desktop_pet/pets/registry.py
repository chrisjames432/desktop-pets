"""Explicit imports make pet registration predictable in frozen EXE builds."""
from collections.abc import Mapping
import threading

from .cat import build_pet as build_cat
from .penguin import build_pet as build_penguin
from .chihuahua import build_pet as build_chihuahua
from .russian_blue import build_pet as build_russian_blue
from .orange_tabby import build_pet as build_orange_tabby
from .koi import build_pet as build_koi

FACTORIES = {
    "cat": build_cat,
    "chihuahua": build_chihuahua,
    "penguin": build_penguin,
    "russian_blue": build_russian_blue,
    "orange_tabby": build_orange_tabby,
    "koi": build_koi,
}


class PetCatalog(Mapping):
    """Read-only mapping that builds and validates each pet on first use.

    Startup only pays for the selected pet. Keys (for the API and settings) are
    available without building anything. Lookups are safe from any thread, and a
    pet that is already built is returned without waiting for another build.
    """

    def __init__(self, factories=None):
        self._factories = dict(FACTORIES if factories is None else factories)
        self._built = {}
        self._failed = set()
        self._build_locks = {}
        self._lock = threading.Lock()
        self._warmer = None

    def __getitem__(self, key):
        factory = self._factories[key]
        with self._lock:
            if key in self._built:
                return self._built[key]
            build_lock = self._build_locks.setdefault(key, threading.Lock())
        with build_lock:                      # one build per pet; other pets stay available
            with self._lock:
                if key in self._built:
                    return self._built[key]
            try:
                pet = factory().validate()
                if key != pet.id:
                    raise ValueError("Registry key must match pet.id: " + key)
            except Exception:
                with self._lock:
                    self._failed.add(key)
                raise
            with self._lock:
                self._built[key] = pet
                self._failed.discard(key)
            return pet

    def __iter__(self):
        return iter(self._factories)

    def __len__(self):
        return len(self._factories)

    def __contains__(self, key):
        return key in self._factories

    def ready(self):
        """True once every pet has either been built or has failed to build."""
        with self._lock:
            return all(key in self._built or key in self._failed for key in self._factories)

    def warm(self):
        """Build the remaining pets on a background thread so the chooser never stalls the UI."""
        with self._lock:
            if self._warmer is not None or all(k in self._built or k in self._failed for k in self._factories):
                return
            self._warmer = threading.Thread(target=self._warm, name="pet-catalog-warm", daemon=True)
            self._warmer.start()

    def _warm(self):
        for key in self._factories:
            try:
                self[key]
            except Exception:
                pass                          # recorded in _failed; the chooser logs and skips it


def load_pets(lazy=False):
    """Return every registered pet. Tests and tools build eagerly; the app builds lazily."""
    pets = PetCatalog()
    if not lazy:
        for key in pets:
            pets[key]
    return pets
