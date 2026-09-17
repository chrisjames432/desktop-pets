"""Reusable cat rig. A breed is a CatSpec plus a build_pet(); see cat.py (Patches) for a full one.

The rig owns every generic piece of cat construction on the 72 x 48 art standard: torso,
legs and paws, tail, head with ears / eyes / nose / mouth / whiskers, the named faces, six
poses, a cached frame renderer, and the standard cat animation set. No Tk, files, threads,
or network; frames are pure functions of (spec, pose, parameters).

Quick start
-----------
    from dataclasses import replace
    from .base import Animation, Personality, PetDefinition
    from .feline import CatSpec, frame, standard_animations
    from .pixelkit import Mask, Ramp, patch

    GREY = Ramp("#b9c3cf", "#93a0b0", "#6f7c8d", "#4d5866")
    FAR = Ramp("#6f7c8d", "#6f7c8d", "#5c6878", "#4d5866")
    SOCK = Ramp("#ffffff", "#f3eee6", "#d6cdbf", "#ab9f8d")

    def _marks(g, part):                      # optional; called while the cat is being drawn
        if part.name == "torso":              # a chest bib that keeps the body shading
            cx, cy = part.C
            patch(g, Mask().ellipse(cx + 3, cy + 2, 5, 6), SOCK, part.ramp, within=part.mask)

    SPEC = CatSpec("smokey", coat=GREY, far=FAR, paws=SOCK, marking_ramps=(SOCK,), marks=_marks,
                   rest_face="serious", mouth="soft", girth=0.9, leg_len=1)

    def build_pet():
        anims = standard_animations(SPEC)                        # six core states + shared tricks
        anims["chatter"] = Animation(                            # a new trick from rig poses/faces
            tuple(frame(SPEC, "sit", face=f, fx=("meow", i)) for i, f in enumerate(("meow", "ajar", "meow", "serious"))),
            0.18, 2.4, "Chatter", 2)
        anims["purr"] = replace(anims["purr"], weight=4)         # tune a standard entry
        del anims["knead"]                                       # or drop one
        return PetDefinition("smokey", "Smokey", "Grey Cat", "A talkative grey cat.", anims,
                             Personality(walk_speed=70, trick_chance=0.3))

frame(spec, pose, zzz=-1, fx=None, **params)
--------------------------------------------
Poses and their parameters (all optional; every pose also takes the face parameters):
    "stand"   dy (0/1 body bob), tail_i (0..2 index into spec.tail_stand), legs, hdx, hdy, arm
              legs = (near hind, near fore, far hind, far fore), each (stride dx, lift); see gait().
              arm = points for a reaching near fore leg, in Patches' coordinates (the rig moves
              them with the body), e.g. ((47, 33), (57, 29), (64, 24)).
    "sit"     dy, tail_i (index into spec.tail_sit), hdx, hdy, arm (raised paw, drawn over the face)
    "loaf"    dy (breathing); eyes closed unless face= is given
    "bow"     deep (0/1), tail_i          play-bow stretch
    "crouch"  wig (-1/0/1)                hunting crouch with a rump wiggle
    "leap"    phase (0 rising, 1 landing) airborne; pair with Animation(forward_speed=...)
Face parameters: face, look (-1/0/1 pupil direction), blink, tilt (0/1), ear (0 up, 1 lowered),
tongue (little lick).
zzz >= 0 draws drifting sleep Z's; fx is any hashable value handed to spec.effects.

Faces
-----
face= is a name from FACES (overridable per breed through spec.faces) or an ad hoc tuple
(eyes, mouth, brow). Omitted, it is spec.rest_face. A mouth of None means spec.mouth.
    eyes:   "open", "wide" (dilated), "squint" (^ ^), "closed", "level" (straight upper lid),
            "lidded" (heavy half lid)
    mouths: "w" (the :3), "soft" (small upturned smile), "flat", "frown", "open" (meow with
            fangs and tongue), "ajar" (half open, for chatter)
    names:  "smile", "play", "happy", "closed", "serious", "grumpy", "meow", "ajar"

Hooks (both optional, both must be pure)
----------------------------------------
spec.marks(g, part) is called right after each of these is painted, so patch() / clipped
paint() markings sit under everything drawn later and follow the shading:
    part.name  "tail"    + pts, r0, r1 (final path and radii)
               "torso"   + R, M, C (rump, middle, chest points), u (unit vector rump -> chest),
                           at(a, b) -> point a px along the spine from M, b px toward the belly
               "haunch"  near thigh (mask already clipped to the body)
               "leg"     + which ("near_hind", "near_fore", "far_hind", "far_fore"), near;
                           straight legs, bent limbs, and tucked paws alike
               "neck"
               "head"    + cx, cy, hs (head scale); the skull dome, before eyes / nose / mouth
    every part has: name, pose, mask, ramp (the ramp it was painted with; pass it to patch() as
    the base), spec.
spec.effects(g, fx, info) runs after the outline pass, so small marks stay clean. info has
pose, hx, hy (head centre), spec. The default, default_effects, understands fx=("heart", step)
and fx=("meow", step); draw_heart / draw_z / draw_ticks are there for custom ones.

Proportions
-----------
Numeric CatSpec fields, defaults are Patches. They hold in every pose: paws stay on design row
GROUND - 1, heads are kept under the top edge, tails and reaching paws are kept inside a 1 px
side margin. Ranges that were checked in all poses:
    head_scale 0.85..1.1   head_w 0.9..1.1    muzzle 0.8..1.15   head_dx -2..2   head_dy -2..3
    ear_h 0.8..1.25        ear_w 0.8..1.3     ear_spread 0..2    ear_lean -1..2
    girth 0.85..1.3        belly 0..3         body_len -4..3     leg_len -3..3   leg_w 2..4
    tail_r 0.8..1.7        tail_len 0.8..1.15 eye_spread -1..1   eye_dy -1..1
Patches already fills the canvas top to bottom, so height is the scarce resource. Tall ears on
a long-legged cat run out of room: the rig then lowers the head (shortening the neck) and
shrinks a too-tall tail curl rather than clipping, so prefer wider ears (ear_w, ear_spread) or
a smaller head over ear_h, and keep leg_len + big heads modest (leg_len 3 with head_scale 1.1
leaves no neck). Small or narrow heads pull the eyes a pixel closer; eye_spread widens them.
head_dy is ignored in the loaf, where the chin rests on the paws.
Tail curl paths (tail_stand, tail_sit, tail_loaf) are written in Patches' coordinates; the rig
moves their root with the body and applies tail_len / tail_r.

Colours
-------
Coat ramps: coat, far, and the optional part ramps tail, hind, fore, ear_near, ear_far, paws,
far_paws, ear_in (pointed or bicolour cats need no hook at all). Flat colours: iris (light,
base, dark), rim, lids, brow, glint, nose (leather, shade), line, mouth_in, fang, tongue, blush
(None for none), bean, whisker, zzz, heart, outline. List every ramp your marks() hook paints
with in marking_ramps so the interior crease lines pick up its deep tone.
"""
from dataclasses import dataclass, field
from functools import lru_cache
import math
from types import SimpleNamespace
from .base import Animation
from .pixelkit import (GROUND, H, OUT, W, YO, Mask, Ramp, crease, deeper_map, new_grid, outline,
                       paint, px, rgb, to_image)


REST = (0, 0)
WALK = (((3, 0), (-3, 0), 1), ((0, 2), (0, 0), 0), ((-3, 0), (3, 0), 1), ((0, 0), (0, 2), 0))
TAIL_STAND = (
    ((13, 25), (9, 21), (7, 15), (8, 9), (11, 5), (15, 4), (17, 7)),
    ((13, 25), (10, 21), (9, 15), (10, 9), (13, 5), (17, 4), (19, 7)),
    ((13, 25), (8, 21), (5, 15), (6, 9), (9, 5), (13, 4), (15, 7)),
)
TAIL_SIT = (
    ((15, 42.5), (9, 42.5), (5, 39), (5, 33), (8, 29)),
    ((15, 42.5), (9, 42.5), (5, 40), (4.5, 35), (6, 30)),
)
TAIL_LOAF = ((11, 39), (11, 43.1), (22, 43.2), (33, 43.1))

# name -> (eyes, mouth, brow). A mouth of None is the breed's own resting mouth.
FACES = {
    "smile": ("open", None, False),
    "play": ("wide", None, False),
    "happy": ("squint", None, False),
    "closed": ("closed", None, False),
    "serious": ("level", "flat", False),
    "grumpy": ("lidded", "frown", True),
    "meow": ("open", "open", False),
    "ajar": ("open", "ajar", False),
}
EYES = ("open", "wide", "squint", "closed", "level", "lidded")
# Mouth pixels relative to the head centre: L line, M mouth interior, F fang, T tongue.
MOUTHS = {
    "w": ((1, 5, "L"), (-2, 5, "L"), (-1, 6, "L"), (0, 6, "L"), (2, 6, "L"), (3, 6, "L"), (4, 5, "L")),
    "soft": ((1, 5, "L"), (-1, 5, "L"), (0, 6, "L"), (1, 6, "L"), (2, 6, "L"), (3, 5, "L")),
    "flat": ((1, 5, "L"), (-1, 6, "L"), (0, 6, "L"), (1, 6, "L"), (2, 6, "L"), (3, 6, "L")),
    "frown": ((0, 5, "L"), (1, 5, "L"), (2, 5, "L"), (-1, 6, "L"), (3, 6, "L")),
    "open": ((-1, 5, "L"), (0, 5, "F"), (1, 5, "M"), (2, 5, "F"), (3, 5, "L"),
             (-1, 6, "L"), (0, 6, "M"), (1, 6, "T"), (2, 6, "T"), (3, 6, "L"),
             (0, 7, "L"), (1, 7, "L"), (2, 7, "L")),
    "ajar": ((-1, 5, "L"), (0, 5, "F"), (1, 5, "M"), (2, 5, "F"), (3, 5, "L"),
             (0, 6, "L"), (1, 6, "L"), (2, 6, "L")),
}


@dataclass(frozen=True, eq=False)
class CatSpec:
    """Everything breed-specific. Instances hash by identity, so frame caches never mix breeds;
    make one module-level spec per breed and reuse it."""
    key: str                                  # short name, for debugging only
    coat: Ramp                                # base coat
    far: Ramp                                 # far-side limbs, in shadow
    # part ramps; None falls back to coat (far_paws to far)
    tail: Ramp = None
    hind: Ramp = None                         # near thigh and near hind leg
    fore: Ramp = None                         # near fore leg
    ear_near: Ramp = None                     # left ear in the frame
    ear_far: Ramp = None
    paws: Ramp = None                         # near paws (socks)
    far_paws: Ramp = None
    ear_in: Ramp = Ramp("#f4b4b4", "#e99a9f", "#c97a82", "#a05c66")
    marking_ramps: tuple = ()                 # ramps used by marks(), so creases follow them
    # colours
    iris: tuple = (rgb("#b5e08a"), rgb("#7fc15f"), rgb("#4d8c3f"))      # light, base, dark
    rim: tuple = rgb("#24170f")               # eye rims and pupils
    lids: tuple = (rgb("#24170f"), rgb("#24170f"))   # closed-eye / brow line: near eye, far eye
    brow: tuple = None                        # grumpy brow line; None uses the lid colours
    glint: tuple = rgb("#ffffff")
    nose: tuple = (rgb("#ee8f98"), rgb("#c96a78"))   # leather, shade
    line: tuple = rgb("#6b4a3a")              # mouth line
    mouth_in: tuple = rgb("#5a2a2a")
    fang: tuple = rgb("#ffffff")
    tongue: tuple = rgb("#e9808c")
    blush: tuple = rgb("#f6cfc6")             # None for no blush
    bean: tuple = rgb("#ee9aa2")              # paw pads
    whisker: tuple = rgb("#9c8f80")
    zzz: tuple = rgb("#7f9fb5")
    heart: tuple = rgb("#e9607a")
    outline: tuple = OUT
    # faces
    rest_face: str = "smile"
    mouth: str = "w"
    faces: dict = field(default_factory=dict)  # name -> (eyes, mouth, brow); overrides FACES
    # hooks
    marks: object = None
    effects: object = None                    # None -> default_effects
    # proportions
    head_scale: float = 1.0
    head_w: float = 1.0                       # skull width only
    muzzle: float = 1.0                       # cheek / whisker pads
    head_dx: int = 0
    head_dy: int = 0
    ear_h: float = 1.0
    ear_w: float = 1.0
    ear_spread: float = 0
    ear_lean: float = 0                       # tips lean outward
    eye_spread: int = 0
    eye_dy: int = 0
    girth: float = 1.0
    belly: float = 0                          # px of belly sag
    body_len: int = 0                         # px the chest, fore legs and head move forward
    leg_len: int = 0
    leg_w: int = 3
    tail_r: float = 1.0
    tail_len: float = 1.0
    tail_stand: tuple = TAIL_STAND            # three curl paths
    tail_sit: tuple = TAIL_SIT                # two curl paths
    tail_loaf: tuple = TAIL_LOAF              # one path along the ground

    def __post_init__(self):
        for name, fallback in (("tail", self.coat), ("hind", self.coat), ("fore", self.coat),
                               ("ear_near", self.coat), ("ear_far", self.coat), ("paws", self.coat),
                               ("far_paws", self.far)):
            if getattr(self, name) is None:
                object.__setattr__(self, name, fallback)
        for name in (self.rest_face, *self.faces):
            eyes, mouth, _brow = self.face(name)
            if eyes not in EYES or mouth not in MOUTHS:
                raise ValueError(f"{self.key}: unknown eyes or mouth in face {name!r}")

    def face(self, name):
        """Resolve a face name or (eyes, mouth[, brow]) tuple to (eyes, mouth, brow)."""
        if name is None:
            name = self.rest_face
        eyes, mouth, brow = (tuple(name) + (False,))[:3] if isinstance(name, tuple) else (self.faces.get(name) or FACES[name])
        return eyes, mouth or self.mouth, brow


@lru_cache(maxsize=None)
def _deeper(spec):
    ramps = (spec.coat, spec.far, spec.tail, spec.hind, spec.fore, spec.ear_near, spec.ear_far,
             spec.paws, spec.far_paws) + tuple(spec.marking_ramps)
    return deeper_map(*dict.fromkeys(ramps))


# ---------------------------------------------------------------- geometry helpers
def _about(pts, k, dx=0, dy=0):
    """Scale a path about its first point, then shift it. Identity leaves the numbers untouched."""
    if k != 1:
        ox, oy = pts[0]
        pts = [(ox + (x - ox) * k, oy + (y - oy) * k) for x, y in pts]
    if dx or dy:
        pts = [(x + dx, y + dy) for x, y in pts]
    return list(pts)


def _fit(pts, r, pad=0.0):
    """Keep a stroke of radius r inside the frame: 1 px side margin, top edge, ground line."""
    x0, x1, y0, y1 = 2 + r + pad, W - 2 - r - pad, r - 1, GROUND + 0.25 - r
    return [(min(max(x, x0), x1), min(max(y, y0), y1)) for x, y in pts]


def _stretch(v, anchor, k):
    return v if k == 1 else anchor + (v - anchor) * k


# ---------------------------------------------------------------- the rig
class _Rig:
    """One frame being drawn: the grid, the spec, and the pose name handed to the hooks."""

    def __init__(self, spec, pose):
        self.g, self.s, self.pose, self.deep = new_grid(), spec, pose, _deeper(spec)

    def mark(self, name, mask, ramp, **extra):
        if self.s.marks is not None and mask.x1 >= 0:
            self.s.marks(self.g, SimpleNamespace(name=name, pose=self.pose, mask=mask, ramp=ramp, spec=self.s, **extra))

    def lift(self, r):
        """How far the spine rises: longer legs lift it, extra girth grows upward from the belly line."""
        return self.s.leg_len + (self.s.girth - 1) * r

    # ------------------------------------------------------------ parts
    def tail(self, pts, r0=2.0, r1=1.5, dy=0, edge=False):
        s = self.s
        r0, r1 = r0 * s.tail_r, r1 * s.tail_r
        pts, r = _about(pts, s.tail_len, 0, dy), max(r0, r1)
        top = min(y for _, y in pts)
        if top < r - 1:         # too tall for the canvas: shrink the curl about its root, do not flatten it
            pts = _about(pts, (pts[0][1] - (r - 1)) / (pts[0][1] - top))
        pts = _fit(pts, r)
        m = Mask().path(pts, r0, r1)
        if edge:
            crease(self.g, m, self.deep)
        paint(self.g, m, s.tail, hi=1, sh=1)
        self.mark("tail", m, s.tail, pts=pts, r0=r0, r1=r1)

    def leg(self, x, top, dx, lift, which):
        """Straight leg, sheared by dx for the stride, ending in a paw on the ground line."""
        g, s = self.g, self.s
        near = which.startswith("near")
        ramp = (s.hind if which == "near_hind" else s.fore) if near else s.far
        bottom, w = GROUND - 1 - lift, s.leg_w
        top = min(top, bottom - 3)
        if near:    # soft line up the body so the leg reads in front of it
            for y in range(top + 2, bottom + 1):
                for ex in (x - 1, x + w):
                    i = (y + YO) * W + ex
                    if 0 <= ex < W and g[i] in self.deep and g[i] not in (s.far.base, s.far.sh):
                        g[i] = self.deep[g[i]]
        m = Mask()
        for y in range(top, bottom + 1):
            xo = round(dx * (y - top) / (bottom - top))
            paw = y >= bottom - 1
            for i in range(w + 1 if paw else w):
                c = ramp.sh if i == 0 else ramp.base
                if paw:
                    c = (s.paws.sh if (y == bottom and i == 0) else s.paws.base) if near else s.far_paws.base
                else:
                    m.set(x + xo + i, y)
                px(g, x + xo + i, y, c)
        self.mark("leg", m, ramp, which=which, near=near)

    def limb(self, pts, which, r0=1.9, r1=1.9, paw=True, beans=False):
        """A bent or reaching leg drawn as a path, ending in a paw."""
        g, s = self.g, self.s
        near = which.startswith("near")
        ramp = (s.hind if which == "near_hind" else s.fore) if near else s.far
        k = s.leg_w / 3
        r0, r1 = r0 * k, r1 * k
        pts = _fit(_about(pts, 1 + s.leg_len / 11), max(r0, r1), 0.6)
        m = Mask().path(pts, r0, r1)
        ex, ey = pts[-1]
        pm = Mask().ellipse(ex, ey, r1 + 0.6, r1 + 0.3) if paw else Mask()
        if near:
            crease(g, Mask().path(pts, r0, r1).ellipse(ex, ey, r1 + 0.6, r1 + 0.3) if paw else m, self.deep)
        paint(g, m, ramp, sh=1)
        self.mark("leg", m, ramp, which=which, near=near)
        if paw:
            paint(g, pm, s.paws if near else s.far_paws, sh=1)
            if beans:
                px(g, round(ex), round(ey - 0.5), s.bean)
                px(g, round(ex) + 1, round(ey - 0.5) - 1, s.bean)

    def tucked_paw(self, x, y, rx, ry, which):
        m = Mask().ellipse(x, y, rx, ry)
        crease(self.g, m, self.deep)
        paint(self.g, m, self.s.paws, sh=1)
        self.mark("leg", m, self.s.paws, which=which, near=True)

    def torso(self, R, M, C, r, rr=(7, 8), cr=(7, 8.5)):
        """Barrel from rump R through M to chest C."""
        s, k = self.s, self.s.girth
        m = Mask().path([R, M, C], r * k, r * k).ellipse(R[0], R[1], rr[0] * k, rr[1] * k).ellipse(C[0], C[1], cr[0] * k, cr[1] * k)
        if s.belly:
            m.ellipse(M[0] - 1, min(M[1] + s.belly, GROUND - 3 - r * k), 9 * k, r * k)
        self.body(m, R, M, C)
        return m

    def body(self, m, R, M, C):
        paint(self.g, m, self.s.coat, hi=2, sh=3)
        ux, uy = C[0] - R[0], C[1] - R[1]
        n = math.hypot(ux, uy) or 1
        ux, uy = ux / n, uy / n
        at = lambda a, b: (M[0] + ux * a - uy * b, M[1] + uy * a + ux * b)
        self.mark("torso", m, self.s.coat, R=R, M=M, C=C, u=(ux, uy), at=at)

    def haunch(self, x, y, rx=6, ry=6.5, edge_if=None):
        k = self.s.girth
        m = Mask().ellipse(x, y, rx * k, ry * k)
        crease(self.g, m, self.deep, edge_if)
        paint(self.g, m, self.s.hind, clip=True, sh=2)
        self.mark("haunch", m, self.s.hind)

    def neck(self, x, y, rx, ry):
        m = Mask().ellipse(x, y, rx * (1 + self.s.girth) / 2, ry)
        paint(self.g, m, self.s.coat)
        self.mark("neck", m, self.s.coat)

    def head_at(self, x, y, tilt=0, nudge_y=True):
        """Nudge and clamp a head centre so ears stay under the top edge and cheeks inside the sides."""
        s = self.s
        hs = s.head_scale
        top = math.ceil((1 + 13 * s.ear_h) * hs - 1e-9) - 1 + abs(tilt)
        side = math.ceil(max(7 * hs + 4.6 * hs * s.muzzle, 11 * hs + s.ear_spread + max(s.ear_lean, 0)) - 1e-9)
        return min(max(x + s.head_dx, 3 + side), W - 4 - side), max(y + (s.head_dy if nudge_y else 0), top)

    def eye(self, x, y, eyes, look, lid, brow, inner):
        g, s = self.g, self.s
        hi, mid, dk = s.iris
        rim = s.rim
        if brow:        # low flat brow, dipping toward the nose
            for i in range(5):
                px(g, x + i, y - (1 if (i < 2 if inner > 0 else i > 2) else 0), s.brow or lid)
        if eyes == "squint":
            for i, j in ((0, 2), (1, 1), (2, 0), (3, 1), (4, 2)):
                px(g, x + i, y + 1 + j, lid)
            return
        if eyes == "closed":
            for i, j in ((0, 1), (1, 2), (2, 2), (3, 2), (4, 1)):
                px(g, x + i, y + 1 + j, lid)
            return
        if eyes == "wide":      # big round pupils with a thin iris ring
            for i in (1, 2, 3):
                px(g, x + i, y, rim); px(g, x + i, y + 4, hi)
            for j in (1, 2, 3):
                px(g, x, y + j, dk if j == 1 else mid); px(g, x + 4, y + j, dk if j == 1 else mid)
                for i in (1, 2, 3):
                    px(g, x + i, y + j, rim)
            px(g, x + 1, y + 1, s.glint)
            return
        p = 2 + look
        if eyes == "lidded":    # heavy straight lid over the top half, no sparkle
            for i in range(5):
                px(g, x + i, y + 1, rim)
            for i in (1, 2, 3):
                px(g, x + i, y + 2, mid); px(g, x + i, y + 3, hi); px(g, x + i, y + 4, dk)
            for j in (2, 3):
                px(g, x, y + j, rim); px(g, x + 4, y + j, rim); px(g, x + p, y + j, rim)
            return
        for i in (1, 2, 3):
            px(g, x + i, y, rim)
            px(g, x + i, y + 1, mid)
            px(g, x + i, y + 2, mid)
            px(g, x + i, y + 3, hi)
            px(g, x + i, y + 4, dk)
        for j in (1, 2, 3):
            px(g, x, y + j, rim); px(g, x + 4, y + j, rim)
        if eyes == "level":     # straight upper lid for a steady, neutral gaze
            px(g, x, y, rim); px(g, x + 4, y, rim)
        for j in (1, 2, 3):
            px(g, x + p, y + j, rim)
        px(g, x + (p - 1 if p > 1 else p + 1), y + 1, s.glint)

    def head(self, cx, cy, face=None, look=0, blink=False, tilt=0, ear=0, tongue=False):
        g, s = self.g, self.s
        hs, e, t = s.head_scale, ear, tilt
        eyes, mouth, brow = s.face(face)
        if blink and eyes != "squint":
            eyes = "closed"

        def ear_poly(pts, side, tip_dy):
            ax = pts[0][0] if side < 0 else pts[2][0]          # outer base corner
            out = []
            for n, (x, y) in enumerate(pts):
                x, y = _stretch(x, ax, s.ear_w), _stretch(y, -1, s.ear_h)
                if n == 1:
                    x, y = x + side * (e + s.ear_lean), y + e + tip_dy
                out.append((cx + x * hs + side * s.ear_spread, cy + y * hs))
            return out

        # pointed ears behind the skull
        paint(g, Mask().poly(ear_poly([(-10.5, -1), (-9.5, -14), (-1, -6)], -1, -t)), s.ear_near, hi=1)
        paint(g, Mask().poly(ear_poly([(-8.6, -5), (-8.4, -11), (-4, -6.5)], -1, -t)), s.ear_in, sh=1)
        paint(g, Mask().poly(ear_poly([(2.5, -6), (10, -14), (11, -1)], 1, t)), s.ear_far, hi=1)
        paint(g, Mask().poly(ear_poly([(5, -6.5), (9.2, -11), (9.2, -5)], 1, t)), s.ear_in, sh=1)
        # wide-cheeked skull
        mz = hs * s.muzzle
        skull = (Mask().ellipse(cx, cy, 10.5 * hs * s.head_w, 8.5 * hs)
                 .ellipse(cx - 7 * hs, cy + 3.2 * hs, 4.6 * mz, 3.6 * mz).ellipse(cx + 7 * hs, cy + 3.2 * hs, 4.6 * mz, 3.6 * mz))
        crease(g, skull, self.deep)
        paint(g, skull, s.coat, hi=2, sh=1)
        self.mark("head", skull, s.coat, cx=cx, cy=cy, hs=hs)
        # eyes; the head tilt drops the far eye a row
        ew = hs * s.head_w                      # narrow skulls pull the eyes in, off the rim
        lx, rx, ey = cx + round(0.3 - 7 * ew) - s.eye_spread, cx + round(4 * ew - 0.3) + s.eye_spread, cy - 3 + s.eye_dy
        self.eye(lx, ey, eyes, look, s.lids[0], brow, 1)
        self.eye(rx, ey + (1 if t > 0 else 0), eyes, look, s.lids[1], brow, -1)
        if s.blush is not None:
            for x in (lx, lx + 1, rx + 4, rx + 5):
                px(g, x, cy + 3, s.blush)
        for i in (0, 1, 2):
            px(g, cx + i, cy + 3, s.nose[0])
        px(g, cx + 1, cy + 4, s.nose[1])
        ink = {"L": s.line, "M": s.mouth_in, "F": s.fang, "T": s.tongue}
        spots = [(x, y, ink[c]) for x, y, c in MOUTHS[mouth]]
        if tongue:
            spots += [(1, 6, s.tongue), (1, 7, s.tongue), (2, 7, s.tongue)]
        for x, y, c in spots:          # the mouth never leaves the skull, however small the head
            i = (cy + y + YO) * W + cx + x
            if 0 <= cx + x < W and 0 <= cy + y + YO < H and skull.d[i]:
                g[i] = c

    # ------------------------------------------------------------ poses
    def stand(self, dy=0, tail_i=0, legs=(REST, REST, REST, REST), hdx=0, hdy=0, arm=None, **face):
        s, B = self.s, self.s.body_len
        nh, nf, fh, ff = legs
        up = self.lift(7.3)
        iu = round(up)
        y = 28 + dy - up
        self.tail(s.tail_stand[tail_i], dy=dy - up)
        self.leg(21, 32 - iu, fh[0], fh[1], "far_hind")
        self.leg(43 + B, 32 - iu, ff[0], ff[1], "far_fore")
        self.torso((16.5, y), (29 + B / 2, y), (42 + B, y - 0.5), 7.3)
        self.haunch(16.5, y + 3 * s.girth, edge_if=lambda ex, ey: ex > 19 and ey > 27 - iu)
        self.leg(15, 33 - iu, nh[0], nh[1], "near_hind")
        if arm is None:
            self.leg(38 + B, 32 - iu, nf[0], nf[1], "near_fore")
        bx, by = self.head_at(53 + B, 13 + dy - iu)
        self.neck(bx - 7 - s.head_dx / 2, by + 8.5 - s.head_dy / 2, 5.5, 6.5)
        hx, hy = self.head_at(bx - s.head_dx + hdx, by - s.head_dy + hdy, face.get("tilt", 0))
        self.head(hx, hy, **face)
        if arm is not None:
            self.limb([(40 + B, 31 + dy - up)] + _about(arm, 1, B, -iu), "near_fore", 2.0, 1.9, beans=True)
        return hx, hy

    def sit(self, dy=0, tail_i=0, hdx=0, hdy=0, arm=None, **face):
        s, k = self.s, self.s.girth
        rise = s.leg_len + s.body_len / 2           # longer legs or body sit taller
        ir = round(rise)
        self.tail(s.tail_sit[tail_i])
        self.leg(42, 34 - ir, 0, 0, "far_fore")
        hip, chest = (24, 35.5 - (k - 1) * 9), (36, 30 + dy - rise / 2)
        m = Mask().ellipse(hip[0], hip[1], 11 * k + s.belly, 9 * k).ellipse(chest[0], chest[1], 8 * k, 12 + rise / 2)
        self.body(m, hip, (30, (hip[1] + chest[1]) / 2), chest)
        hy_ = 37.5 - (k - 1) * 7
        self.haunch(24, hy_, 8, 7, edge_if=lambda ex, ey: ex > 24 or ey < hy_ - 7 * k + 2.5)    # folded thigh
        self.tucked_paw(30.5, 43.4, 4.5, 1.7, "near_hind")
        if arm is None:
            self.leg(37, 34 - ir, 0, 0, "near_fore")
        bx, by = self.head_at(45, 13 + dy - ir)
        self.neck(bx - 5 - s.head_dx / 2, by + 8 - s.head_dy / 2, 6, 6.5)
        hx, hy = self.head_at(bx - s.head_dx + hdx, by - s.head_dy + hdy, face.get("tilt", 0))
        self.head(hx, hy, **face)
        if arm is not None:                 # raised paw goes over the face, and follows it
            self.limb([(38, 32 + dy - ir)] + _about(arm, 1, bx - 45, by - 13 - dy), "near_fore", 2.0, 2.0)
        return hx, hy

    def loaf(self, dy=0, face=("closed", None), **more):
        """Curled up in a loaf, tail wrapped round the front. dy lifts the back for slow breathing."""
        s, k, B = self.s, self.s.girth, self.s.body_len
        R, M = (15, 37.5 - (k - 1) * 7.5), (28 + B / 2, 37 - dy * 0.5 - (k - 1) * 8)
        m = Mask().ellipse(M[0], M[1], 18 + B / 2, (8 + dy * 0.5) * k).ellipse(R[0], R[1], 8 * k, 7.5 * k)
        self.body(m, R, M, (46 + B, M[1]))
        self.tucked_paw(52 + B, 43.2, 5.5, 1.9, "near_fore")
        self.tail(s.tail_loaf, 2.0, 1.6, edge=True)
        hx, hy = self.head_at(49 + B, 32 + round((1 - s.head_scale) * 8.5), nudge_y=False)     # chin rests on the paws
        self.head(hx, hy, **{"ear": 1, **more, "face": face})
        return hx, hy

    def bow(self, deep=0, tail_i=0, **face):
        """Play-bow stretch: chest down, front legs out along the ground, rump and tail high."""
        s, B, i = self.s, self.s.body_len, tail_i
        up, cu = self.lift(7), (self.s.girth - 1) * 7
        iu = round(up)
        self.tail(((13, 22), (10, 16), (9 + i, 10), (11 + i, 5), (15 + i, 4), (17 + i, 7)), dy=-deep - up)
        self.leg(20, 29 - iu, 1, 0, "far_hind")
        self.limb([(45 + B, 39 + deep), (56 + B, 42.4), (64 + B, 42.6)], "far_fore", 1.9, 1.7)
        R = (17, 26 - deep - up)
        self.torso(R, (30 + B / 2, 31 - (up + cu) / 2), (42 + B, 35.5 + deep - cu), 7, (7, 7.5), (6.5, 7))
        self.haunch(17, R[1] + 3 * s.girth, 6, 6.5, edge_if=lambda ex, ey: ex > 19 and ey > 26 - iu)
        self.leg(15, 31 - deep - iu, 1, 0, "near_hind")
        self.limb([(42 + B, 40 + deep), (54 + B, 43), (65 + B, 43)], "near_fore", 2.0, 1.8)
        hx, hy = self.head_at(52 + B, 28 + deep, face.get("tilt", 0))
        self.head(hx, hy, **face)
        return hx, hy

    def crouch(self, wig=0, **face):
        """Hunting crouch: chest low, rump up and wiggling, tail swishing."""
        s, B, w = self.s, self.s.body_len, wig
        up, cu = self.lift(6.8), (self.s.girth - 1) * 7
        iu = round(up)
        self.tail([(13 + w, 24), (8 + w, 21), (6 + 2 * w, 15), (7 + 3 * w, 9), (10 + 3 * w, 6)], dy=-up)
        self.leg(21 + w, 33 - iu, 0, 0, "far_hind")
        self.limb([(46 + B, 38), (52 + B, 42.6), (58 + B, 42.8)], "far_fore", 1.9, 1.7)
        R = (17 + w, 27 - abs(w) - up)
        self.torso(R, (30 + B / 2, 32 - (up + cu) / 2), (42 + B, 35 - cu), 6.8, (7, 7.5), (6.5, 7))
        self.haunch(17 + w, R[1] + 4 * s.girth, 6.5, 6.5, edge_if=lambda ex, ey: ex > 19 + w and ey > 28 - iu)
        self.leg(16 + w, 34 - iu, 0, 0, "near_hind")
        self.limb([(42 + B, 39), (47 + B, 43), (54 + B, 43)], "near_fore", 2.0, 1.8)
        hx, hy = self.head_at(53 + B, 28, face.get("tilt", 0))
        self.head(hx, hy, **face)
        return hx, hy

    def leap(self, phase=0, **face):
        """Airborne pounce: 0 = rising with paws reaching, 1 = coming down paws first."""
        B = self.s.body_len
        if phase == 0:
            self.tail([(12, 27), (8, 24), (5.5, 19), (6.5, 13)])
            self.limb([(19, 32), (14, 36), (11, 39)], "far_hind", 2.2, 1.6)
            self.limb([(45 + B, 29), (55 + B, 32.5), (63 + B, 34)], "far_fore", 1.8, 1.6)
            self.torso((17.5, 29), (30 + B / 2, 25.5), (42 + B, 21.5), 6.5, (6.5, 7), (6.5, 7.5))
            self.haunch(17, 31, 6, 6, edge_if=lambda ex, ey: ex > 20)
            self.limb([(14.5, 33), (9.5, 36.5), (6, 39)], "near_hind", 2.3, 1.7)
            hx, hy = self.head_at(53 + B, 14, face.get("tilt", 0))
            self.neck(hx - 7, hy + 4, 5.5, 6)
            self.limb([(42 + B, 27), (52 + B, 27.5), (62 + B, 25.5)], "near_fore", 1.9, 1.7, beans=True)
        else:
            self.tail([(13, 18), (9, 15), (7, 10), (8, 5)])
            self.limb([(17, 22), (11, 22.5), (7, 23.5)], "far_hind", 2.2, 1.6)
            self.limb([(46 + B, 31), (55 + B, 35), (62 + B, 37)], "far_fore", 1.8, 1.6)
            self.torso((17, 21), (30 + B / 2, 23), (42 + B, 27), 6.5, (6.5, 7), (6.5, 7.5))
            self.haunch(16, 23, 6, 6, edge_if=lambda ex, ey: ex > 19)
            self.limb([(14, 25), (9, 28), (5.5, 31)], "near_hind", 2.3, 1.7)
            hx, hy = self.head_at(54 + B, 20, face.get("tilt", 0))
            self.neck(hx - 8, hy + 4, 5.5, 6)
            self.limb([(42 + B, 32), (50 + B, 38), (56 + B, 42)], "near_fore", 1.9, 1.7, beans=True)
        self.head(hx, hy, **face)
        return hx, hy

    def whiskers(self, cx, cy):
        """Whisker hints, added after the outline so they stay thin."""
        s, g = self.s, self.g
        hs = s.head_scale
        ext, row = math.floor(max(7 * hs + 4.6 * hs * s.muzzle, 10.5 * hs * s.head_w * 0.9) + 1e-9), round(3.2 * hs)
        for x, y in ((-ext - 3, row), (-ext - 4, row - 1), (-ext - 3, row + 2), (-ext - 4, row + 3),
                     (ext + 2, row), (ext + 3, row - 1), (ext + 2, row + 2), (ext + 3, row + 3)):
            i = (cy + y + YO) * W + cx + x
            if 0 < cx + x < W - 1 and 0 <= cy + y + YO < H and g[i] is None:
                g[i] = s.whisker


POSES = ("stand", "sit", "loaf", "bow", "crouch", "leap")


# ---------------------------------------------------------------- effects
def draw_z(g, x, y, size, color):
    for i in range(size):
        px(g, x + i, y, color); px(g, x + i, y + size - 1, color)
        px(g, x + size - 1 - i, y + i, color)


def draw_heart(g, x, y, color):
    """5 x 4 heart with its top-left corner at (x, y)."""
    for dx, dy in ((1, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (1, 2), (2, 2), (3, 2), (2, 3)):
        px(g, x + dx, y + dy, color)


def draw_ticks(g, x, y, color, n=3):
    """Little sound lines fanning out to the right of (x, y): a meow, a chirp, a grumble."""
    for dx, dy in (((0, 0), (1, -1)), ((0, 0), (1, -1), (0, 3), (1, 3)), ((0, 0), (1, -1), (0, 3), (1, 3), (1, 6), (2, 7)))[min(n, 3) - 1]:
        px(g, x + dx, y + dy, color)


def default_effects(g, fx, info):
    """fx=("heart", step): a heart drifting up beside the head. fx=("meow", step): sound ticks by the mouth."""
    kind, step = fx
    side = math.ceil(12 * info.spec.head_scale)
    if kind == "heart":
        draw_heart(g, min(info.hx + side + 1, W - 7), max(info.hy - 9 - 2 * step, -1), info.spec.heart)
    elif kind == "meow":
        draw_ticks(g, min(info.hx + side + 4, W - 5), info.hy + 1, info.spec.line, 1 + step % 3)


# ---------------------------------------------------------------- frames
@lru_cache(maxsize=None)
def _frame(spec, pose, zzz, fx, params):
    rig = _Rig(spec, pose)
    hx, hy = getattr(rig, pose)(**dict(params))
    rig.g = g = outline(rig.g, spec.outline)
    rig.whiskers(hx, hy)
    if zzz >= 0:                         # sleep marks drift up, drawn after the outline so they stay clean
        x = min(hx + 14, W - 9)
        draw_z(g, x, max(hy - 15 - zzz, -1), 3, spec.zzz)
        if zzz >= 2:
            draw_z(g, x + 3, max(hy - 23 - (zzz - 2), -1), 4, spec.zzz)
    if fx is not None:
        (spec.effects or default_effects)(g, fx, SimpleNamespace(pose=pose, hx=hx, hy=hy, spec=spec))
    return to_image(g)


def frame(spec, pose="stand", zzz=-1, fx=None, **params):
    """One cached 144 x 96 RGBA frame. Treat it as read-only. See the module docstring for parameters."""
    if pose not in POSES:
        raise ValueError(f"unknown pose {pose!r}")
    return _frame(spec, pose, zzz, fx, tuple(sorted(params.items())))


# ---------------------------------------------------------------- animations
def gait(a=REST, b=REST):
    """Diagonal gait: near hind + far fore move together, far hind + near fore together."""
    return (a, b, b, a)


def standard_animations(spec):
    """The six required states plus the shared cat tricks, as a fresh dict the breed may edit:
    replace or dataclasses.replace() entries, add tricks built from frame(), or del some."""
    f = lambda *a, **k: frame(spec, *a, **k)
    rest = spec.rest_face
    idle = tuple(f(dy=(i // 4) % 2, tail_i=(i // 2) % 2, blink=i == 14) for i in range(16))
    sit = tuple(f("sit", dy=(i // 4) % 2, tail_i=(i // 2) % 2, blink=i == 14) for i in range(16))
    look = tuple(f(look=d, hdx=2 * d, tail_i=i % 2) for i, d in enumerate((0, 0, -1, -1, -1, 0, 1, 1, 1, 0)))
    walk = tuple(f(dy=bob, tail_i=i % 2, legs=gait(a, b)) for i, (a, b, bob) in enumerate(WALK))
    alert = tuple(f("sit", dy=i, tail_i=i, face="happy", ear=0) for i in (0, 1))
    fall = (f(tail_i=1, face="play", legs=((-3, 0), (3, 0), (-2, 0), (4, 0))),)
    stretch = tuple(f("bow", deep=i, tail_i=i, face="happy") for i in (0, 1))
    wiggle = tuple(f("crouch", wig=w, face="play") for w in (-1, 0, 1))
    pounce = tuple(f("leap", phase=i, face="play") for i in (0, 1))
    swat = tuple(f(face="play", tail_i=i % 2, arm=a) for i, a in enumerate((
        ((47, 33), (57, 29), (64, 24)), ((48, 33), (58, 32), (66, 30)), ((47, 34), (55, 37), (60, 40)))))
    groom = tuple(f("sit", face="happy", tilt=1, hdx=1, hdy=1 + i, tail_i=i, tongue=i == 0, arm=a)
                  for i, a in enumerate((((46, 30), (50, 22)), ((48, 27), (54, 15)))))
    purr = tuple(f("sit", dy=i, tail_i=0, face="happy") for i in (0, 1))
    nap = tuple(f("loaf", zzz=i, dy=(i // 2) % 2) for i in range(4))
    knead = tuple(f(face="happy", tail_i=(i // 2) % 2, dy=i % 2,
                    legs=(REST, (0, 3) if i == 0 else REST, REST, (0, 3) if i == 2 else REST))
                  for i in range(4))
    hop = tuple(f(tail_i=i % 2, face="happy" if i in (1, 2) else rest,
                  legs=gait((0, 4), (0, 4)) if i in (1, 2) else gait(), dy=0 if i in (1, 2) else 1)
                for i in range(4))
    return {
        "idle": Animation(idle, 0.22),
        "sit": Animation(sit, 0.25),
        "look": Animation(look, 0.35),
        "walk": Animation(walk, 0.13),
        "alert": Animation(alert, 0.4),
        "fall": Animation(fall),
        "stretch": Animation(stretch, 1.3, 2.6, "Big stretch", 2),
        "wiggle": Animation(wiggle, 0.18, 1.8, "Wiggle and pounce", 1, next_state="pounce"),
        "pounce": Animation(pounce, 0.4, 0.8, "Pounce", forward_speed=120),
        "swat": Animation(swat, 0.15, 2.4, "Paw swat", 1),
        "groom": Animation(groom, 0.4, 3.2, "Wash face", 3),
        "purr": Animation(purr, 0.6, 3.5, "Purr", 2),
        "sleep": Animation(nap, 0.8, 9, "Cozy nap", 2, cooldown=30),
        "knead": Animation(knead, 0.2, 3, "Make biscuits", 2),
        "hop": Animation(hop, 0.18, 2.8, "Happy hop", 1, hop_height=18),
    }
