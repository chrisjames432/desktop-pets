"""Andrew artwork and personality. No application or reminder dependencies.

Andrew is a small, chunky fawn chihuahua: folded airplane ears, a small white
forehead mark, white bib and toes, a red plaid collar with a gold tag, an
underbite tooth, and a lazy near eye that does not quite track with the other.

Art standard: 72 x 48 logical grid enlarged 2x to the 144 x 96 canvas, three-tone
shading, warm brown outline, hard alpha only. The pet faces right.
"""
from functools import lru_cache
from .base import Animation, Personality, PetDefinition
from .pixelkit import GROUND, W, YO, Mask, Ramp, new_grid, outline, paint, px, rgb, sphere, to_image


TAN = Ramp("#ebb97e", "#d89c5e", "#b57a43", "#8c5a30")
FAR = Ramp("#b57a43", "#b57a43", "#96612f", "#7a4d25")      # far-side limbs and ear
WHITE = Ramp("#fffaf0", "#f7efe1", "#ddcfb8", "#b9a88e")
MUZ = Ramp("#f3cf9f", "#e8b985", "#cf9a62", "#a97643")
EARIN = Ramp("#d9a07f", "#c98a6a", "#a86a50", "#8c5a30")
RED = Ramp("#e0645a", "#c8443d", "#97302c", "#6e201e")
LINE = rgb("#5a3a2a")       # mouth and lids
RIM = rgb("#2e1a10")        # eye rims and pupils
NOSE, NOSE_HI, NOSTRIL = rgb("#a9656b"), rgb("#d59aa0"), rgb("#6b3a40")
IRIS_DARK, IRIS_LIGHT = rgb("#9a621f"), rgb("#c08a36")
EYE_WHITE, GLINT, DIM_GLINT = rgb("#f4ecde"), rgb("#ffffff"), rgb("#d9c9a8")
MOUTH_IN, TONGUE = rgb("#5a2a2a"), rgb("#e0808a")
TAG = (rgb("#f0cb58"), rgb("#e6b93c"), rgb("#a87f1e"))
ZZZ = rgb("#7f9fb5")


# ---------------------------------------------------------------- body parts
def leg(g, x, top, dx, lift, ramp, near):
    bottom = GROUND - 1 - lift
    if near:    # soft line up the body so the leg reads in front of it
        for y in range(top + 2, bottom + 1):
            for ex in (x - 1, x + 4):
                i = (y + YO) * W + ex
                if 0 <= ex < W and g[i] is not None and g[i] != WHITE.base:
                    g[i] = TAN.deep
    for y in range(top, bottom + 1):
        xo = round(dx * (y - top) / (bottom - top))
        paw = y >= bottom - 1
        for i in range(5 if paw else 4):
            c = ramp.sh if i == 0 else ramp.base
            if paw:
                c = (WHITE.sh if (y == bottom and i == 0) else WHITE.base) if near else WHITE.sh
            px(g, x + xo + i, y, c)


def collar(g, pts, tag=None):
    m = Mask().poly(pts)
    paint(g, m, RED, clip=True, hi=1)
    for y in range(m.y0, m.y1 + 1):
        for x in range(m.x0, m.x1 + 1):
            if m.d[y * W + x] and (x + y) % 3 == 0:
                g[y * W + x] = RED.sh            # plaid weave
    if tag:
        tx, ty = tag
        px(g, tx, ty, TAG[0]); px(g, tx + 1, ty, TAG[1])
        px(g, tx, ty + 1, TAG[1]); px(g, tx + 1, ty + 1, TAG[2])


def eye_near(g, x, y, look, blink):
    """The lazy eye: heavy straight lid, pupil drifted back, only half tracking."""
    if blink:
        for i, j in ((0, 2), (1, 3), (2, 3), (3, 3), (4, 2)):
            px(g, x + i, y + j, RIM)
        return
    for i in range(5):
        px(g, x + i, y + 1, RIM)
    for j in (2, 3):
        px(g, x, y + j, RIM); px(g, x + 4, y + j, RIM)
    for i in (1, 2, 3):
        px(g, x + i, y + 4, RIM)
        px(g, x + i, y + 2, IRIS_DARK); px(g, x + i, y + 3, IRIS_LIGHT)
    p = 1 if look > 0 else 0
    px(g, x + 1 + p, y + 2, DIM_GLINT); px(g, x + 2 + p, y + 2, RIM)
    px(g, x + 1 + p, y + 3, RIM);       px(g, x + 2 + p, y + 3, RIM)


def eye_far(g, x, y, look, blink):
    """The good eye: wide open, bright catchlight, shows white when glancing back."""
    if blink:
        for i, j in ((0, 2), (1, 3), (2, 3), (3, 2)):
            px(g, x + i, y + j, RIM)
        return
    px(g, x + 1, y, RIM); px(g, x + 2, y, RIM)
    for j in (1, 2, 3):
        px(g, x, y + j, RIM); px(g, x + 3, y + j, RIM)
    px(g, x + 1, y + 4, RIM); px(g, x + 2, y + 4, RIM)
    if look < 0:
        px(g, x + 1, y + 1, RIM); px(g, x + 2, y + 1, EYE_WHITE)
        px(g, x + 1, y + 2, RIM); px(g, x + 2, y + 2, EYE_WHITE)
    else:
        px(g, x + 1, y + 1, GLINT); px(g, x + 2, y + 1, RIM)
        px(g, x + 1, y + 2, RIM);   px(g, x + 2, y + 2, RIM)
    px(g, x + 1, y + 3, IRIS_LIGHT); px(g, x + 2, y + 3, IRIS_LIGHT)


def head(g, cx, cy, look=0, blink=False, mouth=0, ear=0):
    rel = lambda pts: [(cx + x, cy + y) for x, y in pts]
    e = 2 * ear     # ears drop a little when he bounces or sleeps
    # far ear, folded out to the side
    paint(g, Mask().poly(rel([(3, -9), (8, -13 + e), (12, -11 + e), (10, -6)])), FAR, hi=1)
    # apple-dome skull
    sphere(g, cx, cy, 11, 10, TAN, edge=True)
    # near ear: a big leaf swept back with the pink-tan inside showing
    paint(g, Mask().poly(rel([(-4, -9), (-11, -13 + e), (-18, -11 + 2 * e), (-15, -5 + e), (-9, -2)])),
          TAN, hi=1, sh=1, edge=True)
    paint(g, Mask().poly(rel([(-7, -8), (-12, -11 + e), (-16, -10 + 2 * e), (-13, -6 + e), (-9, -4)])),
          EARIN, sh=1)
    # short muzzle, paler than the coat, white around the mouth and chin
    sphere(g, cx + 9, cy + 6, 5.5, 4, MUZ, edge=True, edge_color=TAN.sh)
    paint(g, Mask().ellipse(cx + 9, cy + 8.5, 5, 2.2), WHITE, clip=True, sh=1)
    if mouth:       # happy open mouth with a bit of tongue
        for x in range(cx + 7, cx + 13):
            px(g, x, cy + 9, MOUTH_IN); px(g, x, cy + 10, MOUTH_IN)
            px(g, x, cy + 11, WHITE.sh)
        for x in range(cx + 9, cx + 12):
            px(g, x, cy + 10, TONGUE)
        px(g, cx + 6, cy + 9, LINE)
    # mouth line with the one little underbite tooth
    px(g, cx + 6, cy + 7, LINE)
    for x in range(cx + 7, cx + 14):
        px(g, x, cy + 8, LINE)
    px(g, cx + 11, cy + 8, GLINT)
    # pink-brown nose
    for j in (0, 1):
        for i in (0, 1, 2):
            px(g, cx + 13 + i, cy + 3 + j, NOSE)
    px(g, cx + 13, cy + 3, NOSE_HI)
    px(g, cx + 13, cy + 5, NOSE); px(g, cx + 14, cy + 5, NOSTRIL)
    px(g, cx + 13, cy + 6, LINE); px(g, cx + 13, cy + 7, LINE)
    # small white mark on the forehead, pale brow over the near eye
    for x, y in ((4, -7), (5, -7), (4, -6), (5, -6), (4, -5), (4, -4)):
        px(g, cx + x, cy + y, WHITE.base)
    for i in (-1, 0, 1):
        px(g, cx + i, cy - 3, TAN.hi)
    eye_near(g, cx - 2, cy - 1, look, blink)
    eye_far(g, cx + 6, cy - 2, look, blink)


# ---------------------------------------------------------------- poses
TAIL_STAND = (
    ((12, 24), (8, 19), (7, 13), (10, 8), (15, 7), (19, 10)),
    ((12, 24), (9, 19), (9, 13), (12, 8), (17, 7), (21, 10)),
)
TAIL_SIT = (
    ((13, 42), (8, 41), (5, 37), (6, 32), (9, 29)),
    ((13, 42), (8, 42), (5, 39), (5, 34), (7, 30)),
)
TAIL_LIE = (
    ((12, 41), (8, 42), (5, 39), (7, 35)),
    ((12, 41), (8, 42), (5, 40), (6, 36)),
)
REST = (0, 0)


def _stand(g, dy, tail, legs, look, hdx, hdy, blink, mouth, ear):
    nh, nf, fh, ff = legs
    paint(g, Mask().path([(x, y + dy) for x, y in TAIL_STAND[tail]], 2.4, 3.1), TAN, hi=2, sh=1)
    leg(g, 21, 33, fh[0], fh[1], FAR, False)
    leg(g, 44, 33, ff[0], ff[1], FAR, False)
    torso = Mask().ellipse(30, 29 + dy, 18, 11).ellipse(17, 28 + dy, 9, 10).ellipse(43, 29 + dy, 8.5, 11)
    paint(g, torso, TAN, hi=3, sh=4)                                            # one long chunky barrel
    paint(g, Mask().ellipse(31, 38.5 + dy, 14, 2.5), WHITE, clip=True, sh=1)    # belly
    paint(g, Mask().ellipse(48, 32 + dy, 3.5, 7), WHITE, clip=True, sh=2)       # bib
    paint(g, Mask().ellipse(16, 32 + dy, 7, 8), TAN, clip=True, sh=2, edge=True,
          edge_if=lambda x, y: x > 19 and y > 28)                               # haunch
    leg(g, 15, 34, nh[0], nh[1], TAN, True)
    leg(g, 38, 33, nf[0], nf[1], TAN, True)
    paint(g, Mask().ellipse(45, 20 + dy, 7, 7), TAN)                            # thick neck
    collar(g, [(38, 20 + dy), (40, 18 + dy), (51, 26 + dy), (49, 28 + dy)], (47, 28 + dy))
    head(g, 52 + hdx, 13 + dy + hdy, look, blink, mouth, ear)


def _sit(g, dy, tail, look, hdx, blink, mouth, ear):
    paint(g, Mask().path(TAIL_SIT[tail], 2.4, 3.1), TAN, hi=2, sh=1)
    leg(g, 41, 34, 0, 0, FAR, False)
    paint(g, Mask().ellipse(23, 35, 11, 9.5).ellipse(36, 30 + dy, 9, 12), TAN, hi=3, sh=3)
    paint(g, Mask().ellipse(41, 31 + dy, 4, 8), WHITE, clip=True, sh=2)         # bib
    paint(g, Mask().ellipse(24, 37, 8, 7.5), TAN, clip=True, sh=2, edge=True,
          edge_if=lambda x, y: x > 24 or y < 33)                                # folded thigh
    paint(g, Mask().ellipse(30, 43.5, 5, 1.8), WHITE, sh=1, edge=True)          # hind paw
    leg(g, 36, 35, 0, 0, TAN, True)
    paint(g, Mask().ellipse(41, 20 + dy, 7, 7), TAN)
    collar(g, [(34, 19 + dy), (36, 17 + dy), (47, 25 + dy), (45, 27 + dy)], (43, 27 + dy))
    head(g, 47 + hdx, 12 + dy, look, blink, mouth, ear)


def _lie(g, dy, tail):
    """Curled up asleep, chin on his front paws. dy lifts the back for slow breathing."""
    paint(g, Mask().path(TAIL_LIE[tail], 2.4, 3.0), TAN, hi=2, sh=1)
    paint(g, Mask().ellipse(27, 37 - dy * 0.5, 17, 8 + dy * 0.5).ellipse(15, 37.5, 8, 7.5), TAN, hi=3, sh=3)
    paint(g, Mask().ellipse(30, 43.3, 12, 1.8), WHITE, clip=True, sh=1)
    paint(g, Mask().ellipse(16, 39, 7, 5.5), TAN, clip=True, sh=2, edge=True,
          edge_if=lambda x, y: x > 17)
    paint(g, Mask().ellipse(25, 43.5, 4, 1.6), WHITE, sh=1, edge=True)          # hind paw
    paint(g, Mask().path([(40, 42.5), (60, 42.8)], 2.2, 2.2), TAN, sh=1, edge=True)
    paint(g, Mask().ellipse(63, 43, 3, 1.9), WHITE, sh=1)                       # front paw, poking out past his nose
    paint(g, Mask().ellipse(42, 34, 7, 6), TAN)
    collar(g, [(36, 31), (38, 29), (46, 36), (44, 38)])
    head(g, 49, 31, 0, True, 0, 1)


def _z(pixels, x, y, size):
    for i in range(size):
        pixels.append((x + i, y)); pixels.append((x + i, y + size - 1))
        pixels.append((x + size - 1 - i, y + i))


@lru_cache(maxsize=None)
def frame(pose="stand", dy=0, tail=0, legs=(REST, REST, REST, REST), look=0, hdx=0, hdy=0,
          blink=False, mouth=0, ear=0, zzz=-1):
    g = new_grid()
    if pose == "sit":
        _sit(g, dy, tail, look, hdx, blink, mouth, ear)
    elif pose == "lie":
        _lie(g, dy, tail)
    else:
        _stand(g, dy, tail, legs, look, hdx, hdy, blink, mouth, ear)
    g = outline(g)
    if zzz >= 0:                         # sleep marks drift up, drawn after the outline so they stay clean
        marks = []
        _z(marks, 62, 20 - zzz, 3)
        if zzz >= 2:
            _z(marks, 66, 12 - (zzz - 2), 4)
        for x, y in marks:
            px(g, x, y, ZZZ)
    return to_image(g)


# ---------------------------------------------------------------- animations
def _legs(a=REST, b=REST):
    """Diagonal gait: near hind + far fore move together, far hind + near fore together."""
    return (a, b, b, a)


WALK = (((3, 0), (-3, 0), 1), ((0, 2), (0, 0), 0), ((-3, 0), (3, 0), 1), ((0, 0), (0, 2), 0))
RUN = (((5, 0), (-5, 0), 1), ((0, 3), (0, 1), 0), ((-5, 0), (5, 0), 1), ((0, 1), (0, 3), 0))


def build_pet():
    idle = tuple(frame(dy=(i // 4) % 2, tail=(i // 2) % 2, blink=i == 14) for i in range(16))
    sit = tuple(frame("sit", dy=(i // 4) % 2, tail=(i // 2) % 2, blink=i == 13) for i in range(16))
    look = tuple(frame(look=d, hdx=2 * d, tail=i % 2) for i, d in enumerate((0, -1, -1, 0, 1, 1, 0)))
    walk = tuple(frame(dy=bob, tail=i % 2, legs=_legs(a, b)) for i, (a, b, bob) in enumerate(WALK))
    run = tuple(frame(dy=bob, tail=i % 2, legs=_legs(a, b), mouth=1, ear=i % 2) for i, (a, b, bob) in enumerate(RUN))
    # Tippy taps: front paws patter in place, mouth open, tail going.
    taps = tuple(frame(tail=i % 2, mouth=1, dy=i % 2,
                       legs=(REST, (0, 2) if i % 2 == 0 else REST, REST, (0, 2) if i % 2 else REST))
                 for i in range(4))
    bark = tuple(frame(tail=i % 2, mouth=m, hdy=-m, ear=m) for i, m in enumerate((0, 1, 0, 1)))
    hop = tuple(frame(tail=i % 2, mouth=1, ear=i % 2, legs=_legs((0, 4), (0, 4)) if i in (1, 2) else _legs(),
                     dy=0 if i in (1, 2) else 1)
                for i in range(4))
    nap = tuple(frame("lie", dy=(i // 2) % 2, tail=0, zzz=i) for i in range(4))
    fall = (frame(tail=1, mouth=1, ear=1, legs=((-3, 0), (3, 0), (-2, 0), (4, 0))),)

    animations = {
        "idle": Animation(idle, 0.22),
        "sit": Animation(sit, 0.25),
        "look": Animation(look, 0.4),
        "walk": Animation(walk, 0.13),
        "alert": Animation(taps, 0.14),
        "fall": Animation(fall),
        "tippy_taps": Animation(taps, 0.14, 2.4, "Tippy taps", 3),
        "bark": Animation(bark, 0.16, 1.9, "Little bark", 2),
        "zoomies": Animation(run, 0.09, 1.8, "Zoomies", 1, cooldown=25, forward_speed=150),
        "hop": Animation(hop, 0.18, 2.8, "Happy hop", 1, hop_height=16),
        "sleep": Animation(nap, 0.8, 9, "Curl up for a nap", 2, cooldown=30),
    }
    return PetDefinition(
        "chihuahua", "Andrew", "Chihuahua",
        "A chunky little chihuahua with a lazy eye and a very busy tail. He's a good boy.",
        animations,
        Personality(walk_speed=60, roam_chance=0.55, trick_chance=0.25, trick_gap=12, rest_min=3, rest_max=8),
    )
