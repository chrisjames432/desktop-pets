"""Version 1 pet contract. Pure Pillow images; no Tk, files, threads, or API calls."""
from dataclasses import dataclass, field
import math
import re
from PIL import Image

CANVAS_SIZE = (144, 96)
REQUIRED_STATES = frozenset({"idle", "sit", "look", "walk", "alert", "fall"})
MOVEMENTS = frozenset({"ground", "swim"})


@dataclass(frozen=True)
class Animation:
    frames: tuple[Image.Image, ...]
    frame_seconds: float = 0.2
    duration: float = 3.0
    label: str | None = None  # A label makes this action appear in the menu/API.
    weight: float = 0.0  # Relative chance when choosing a spontaneous trick.
    cooldown: float = 15.0
    forward_speed: float = 0.0  # Pixels/second; the engine enforces Stay/taskbar rules.
    hop_height: float = 0.0  # Window movement, not pixels clipped off the frame.
    next_state: str | None = None


@dataclass(frozen=True)
class Personality:
    walk_speed: float = 65.0
    roam_chance: float = 0.65
    trick_chance: float = 0.25
    trick_gap: float = 12.0
    rest_min: float = 3.0
    rest_max: float = 7.0


@dataclass(frozen=True)
class PetDefinition:
    id: str
    name: str
    label: str
    description: str
    animations: dict[str, Animation]
    personality: Personality = field(default_factory=Personality)
    # "ground": walks on the taskbar line with gravity (default).
    # "swim": moves freely anywhere in the work area, no floor, and may swim behind the desktop icons.
    movement: str = "ground"

    @property
    def actions(self):
        return {key: animation.label for key, animation in self.animations.items() if animation.label}

    def validate(self):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.id):
            raise ValueError("Pet ID must be lowercase snake_case")
        if not all(isinstance(value, str) and value.strip() for value in (self.name, self.label, self.description)):
            raise ValueError("Pet name, label, and description are required")
        if self.movement not in MOVEMENTS:
            raise ValueError(f"{self.id}: movement must be one of {sorted(MOVEMENTS)}")
        if not REQUIRED_STATES <= self.animations.keys():
            raise ValueError(f"{self.id}: missing core states {REQUIRED_STATES - self.animations.keys()}")
        p = self.personality
        values = (p.walk_speed, p.roam_chance, p.trick_chance, p.trick_gap, p.rest_min, p.rest_max)
        if not all(math.isfinite(v) and v >= 0 for v in values) or not (0 <= p.roam_chance <= 1 and 0 <= p.trick_chance <= 1 and 0 < p.rest_min <= p.rest_max):
            raise ValueError("Invalid personality settings")
        for state, animation in self.animations.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", state):
                raise ValueError(f"Invalid animation ID: {state}")
            if not animation.frames or not all(math.isfinite(v) and v > 0 for v in (animation.frame_seconds, animation.duration)):
                raise ValueError(f"{state}: frames and positive timings required")
            if not all(math.isfinite(v) and v >= 0 for v in (animation.weight, animation.cooldown, animation.forward_speed, animation.hop_height)):
                raise ValueError(f"{state}: invalid motion or selection settings")
            if animation.next_state is not None and animation.next_state not in self.animations:
                raise ValueError(f"{state}: unknown next_state")
            for frame in animation.frames:
                if frame.mode != "RGBA" or frame.size != CANVAS_SIZE:
                    raise ValueError(f"{state}: every frame must be RGBA {CANVAS_SIZE}")
                if not frame.getbbox():
                    raise ValueError(f"{state}: empty frame")
                if set(frame.getchannel("A").tobytes()) - {0, 255}:
                    raise ValueError(f"{state}: use hard alpha edges for Windows transparency")
                if any(pixel[:3] == (255, 0, 255) and pixel[3] for _, pixel in frame.getcolors(frame.width*frame.height)):
                    raise ValueError(f"{state}: opaque magenta is reserved for transparency")
        return self
