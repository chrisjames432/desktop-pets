"""Explicit imports make pet registration predictable in frozen EXE builds."""
from collections.abc import Mapping
import threading

from .cat import build_pet as build_cat
from .penguin import build_pet as build_penguin
from .chihuahua import build_pet as build_chihuahua

FACTORIES = {"cat": build_cat, "penguin": build_penguin, "chihuahua": build_chihuahua}


class PetCatalog(Mapping):
    """Read-only mapping that builds and validates each pet on first use.

    Startup only pays for the selected pet. Keys (for the API and settings) are
    available without building anything. Lookups are safe from any thread.
    """

    def __init__(self, factories=None):
        self._factories = dict(FACTORIES if factories is None else factories)
        self._built = {}
        self._lock = threading.Lock()

    def __getitem__(self, key):
        with self._lock:
            if key not in self._built:
                pet = self._factories[key]().validate()
                if key != pet.id:
                    raise ValueError("Registry key must match pet.id: " + key)
                self._built[key] = pet
            return self._built[key]

    def __iter__(self):
        return iter(self._factories)

    def __len__(self):
        return len(self._factories)

    def __contains__(self, key):
        return key in self._factories


def load_pets(lazy=False):
    """Return every registered pet. Tests and tools build eagerly; the app builds lazily."""
    pets = PetCatalog()
    if not lazy:
        for key in pets:
            pets[key]
    return pets
