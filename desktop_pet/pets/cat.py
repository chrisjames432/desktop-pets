"""Patches artwork and personality. No application or reminder dependencies.

Patches is a cheerful calico cat: white coat, an orange saddle, a black flank patch,
an orange rump and near hind leg, a slender black tail with an orange tip, and the
classic split calico face (black over one ear and eye, orange over the other, white
blaze and muzzle) with green eyes, a pink nose, and a permanent ":3" smile.

The cat itself is drawn by the shared rig in feline.py; this module is only Patches'
spec (colors and calico markings), animation set, and personality.
"""
from .base import Personality, PetDefinition
from .feline import CatSpec, standard_animations
from .pixelkit import Mask, Ramp, both, paint, patch, path_after, rgb


WHITE = Ramp("#ffffff", "#f6efe2", "#d8ccb8", "#ad9f8a")
FARW = Ramp("#d7cbb7", "#d7cbb7", "#b9ab95", "#978a76")      # far-side limbs, in shadow
ORANGE = Ramp("#f7b465", "#e8913f", "#c26d29", "#93501d")
BLACK = Ramp("#6e6260", "#4b4140", "#352c2b", "#221b1a")
LID_PALE = rgb("#b3a49e")    # closed-eye arc over the black face patch


def _blobs(*ellipses):
    m = Mask()
    for x, y, rx, ry in ellipses:
        m.ellipse(x, y, rx, ry)
    return m


def _calico(g, part):
    """The calico markings, laid over the white coat tone for tone so they keep its shading."""
    m = part.mask
    if part.name == "tail":                 # orange tip
        r = part.r1 + 0.6
        tip = path_after(part.pts, 0.72 if part.pose == "loaf" else 0.7)
        paint(g, both(Mask().path(tip, r, r), m), ORANGE, hi=1, sh=1)
    elif part.name == "head":               # split face with a white blaze
        cx, cy = part.cx, part.cy
        patch(g, _blobs((cx - 8, cy - 4, 7.5, 6.5), (cx - 9, cy + 1, 3, 3)), BLACK, WHITE, m)
        patch(g, _blobs((cx + 9, cy - 4, 6.5, 6.5), (cx + 10, cy + 1, 2.5, 3)), ORANGE, WHITE, m)
    elif part.name != "torso":
        return
    elif part.pose == "sit":
        (hx, hy), (cx, cy) = part.R, part.C
        patch(g, _blobs((cx - 7, cy - 9, 5, 4.5), (cx - 10, cy - 4, 4, 3.5)), ORANGE, WHITE, m)       # saddle
        patch(g, _blobs((hx + 7, hy - 3.5, 4.5, 5)), BLACK, WHITE, m)                                # flank
    elif part.pose == "loaf":
        x, y = part.R
        patch(g, _blobs((x + 15, y - 7.5, 8, 4.5), (x + 21, y - 5.5, 4, 3.5)), ORANGE, WHITE, m)
        patch(g, _blobs((x + 9, y - 0.5, 5.5, 4), (x + 5, y - 3.5, 3, 3)), BLACK, WHITE, m)
        patch(g, _blobs((x - 5, y - 0.5, 5, 6)), ORANGE, WHITE, m)
    else:
        at = part.at
        patch(g, _blobs(at(5, -6) + (7, 4), at(10, -4) + (4, 3.5)), ORANGE, WHITE, m)                # saddle
        patch(g, _blobs(at(-2, 2.5) + (5.5, 4.5), at(-6, -1) + (3.5, 3)), BLACK, WHITE, m)           # flank


PATCHES = CatSpec("patches", coat=WHITE, far=FARW, tail=BLACK, hind=ORANGE, ear_near=BLACK, ear_far=ORANGE,
                  marking_ramps=(ORANGE, BLACK), lids=(LID_PALE, rgb("#24170f")), marks=_calico)


def build_pet():
    return PetDefinition("cat", "Patches", "Calico Cat", "A curious calico with a playful streak.",
                         standard_animations(PATCHES), Personality(walk_speed=70, trick_chance=0.25))
