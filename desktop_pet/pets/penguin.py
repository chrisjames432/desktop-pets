"""Pip artwork and personality. No application or reminder dependencies.

Pip is a round little penguin: dark slate-blue back, cream belly and heart-shaped
face mask, a small orange beak, separate orange feet, and busy little flippers.

Art standard: 72 x 48 logical grid enlarged 2x to the 144 x 96 canvas, three-tone
shading, a dark navy outline, hard alpha only. Pip stands face-on, turned a touch
to the right; the belly slide faces right.
"""
from functools import lru_cache
from .base import Animation, Personality, PetDefinition
from .pixelkit import GROUND, H, W, YO, Mask, Ramp, edge_pass, new_grid, outline, paint, px, rgb, to_image


SLATE = Ramp("#6d87a8", "#435873", "#2f3e55", "#1d2738")
CREAM = Ramp("#fffdf4", "#fbf0d9", "#e2cfb0", "#b9a585")
GLOW = Ramp("#fffdf4", "#fffdf4", "#fffdf4", "#fffdf4")     # belly highlight
ORANGE = Ramp("#ffc766", "#f29a38", "#c96f22", "#8f4a18")
NAVY = rgb("#141a28")        # outline: cool and dark, suits the slate coat
EYE = rgb("#161c2a")
GLINT, GLINT_SOFT = rgb("#ffffff"), rgb("#7f96b8")
BLUSH = rgb("#f4a79b")
MOUTH_IN, TONGUE = rgb("#7a2d2f"), rgb("#ee8b8f")
SHINE = rgb("#9db4d1")       # little specular on the crown
ZZZ = rgb("#7f9fb5")
SPRAY = rgb("#9fc3dc")


# ---------------------------------------------------------------- shading
def shade(g, m, ramp, hi=2, sh=3, clip=False, edge=False, edge_if=None):
    """Like pixelkit.paint, but the bands follow a light from the top right, so round
    forms get a highlight rim on the upper right and a shadow rim on the lower left."""
    if m.x1 < 0:
        return
    d = m.d
    if clip:
        for i in range(W * H):
            if d[i] and g[i] is None:
                d[i] = 0
    if edge:
        edge_pass(g, m, ramp.deep, edge_if)

    def inside(x, y):
        return 0 <= x < W and 0 <= y < H and d[y * W + x]

    for y in range(m.y0, m.y1 + 1):
        for x in range(m.x0, m.x1 + 1):
            i = y * W + x
            if not d[i]:
                continue
            c = ramp.base
            for k in range(1, sh + 1):
                if not inside(x - (k + 1) // 2, y + k):
                    c = ramp.sh
                    break
            for k in range(1, hi + 1):
                if not inside(x + (k + 1) // 2, y - k):
                    c = ramp.hi
                    break
            g[i] = c


# ---------------------------------------------------------------- parts
FLIPPER = {     # polyline relative to the shoulder; x is mirrored for the left flipper
    "down": ((0, 0), (3, 6), (3, 11)),
    "out": ((0, 0), (5, 4), (8, 7)),
    "mid": ((0, 0), (6, -1), (10, -3)),
    "up": ((0, 0), (5, -5), (7, -10)),
    "cheer": ((0, 0), (6, -3), (10, -6)),
    "belly": ((0, 0), (2, 6), (-1, 10)),
    "preen": ((0, 0), (6, -3), (4, -8)),
    "preen2": ((0, 0), (6, -2), (5, -6)),
}
RAISED = ("up", "cheer", "mid")


def flipper(g, sx, sy, side, pose, front=True):
    a, b, c = [(sx + side * x, sy + y) for x, y in FLIPPER[pose]]
    m = Mask().path([a, b], 2.8, 3.3).path([b, c], 3.3, 2.0)       # a paddle: widest at the elbow
    shade(g, m, SLATE, hi=1, sh=2, edge=front,
          edge_if=lambda x, y: y > sy + 2 or y < sy - 3 or abs(x - sx) > 4)


def foot(g, cx, lift=0, big=False):
    rx, ry = (5.2, 2.3) if big else (4.6, 2.0)
    m = Mask().ellipse(cx, GROUND - ry - lift, rx, ry)
    paint(g, m, ORANGE, hi=1, sh=1, edge=True, edge_color=SLATE.deep)
    for tx in (-2, 1):      # toe notches
        px(g, round(cx) + tx, GROUND - 1 - lift, ORANGE.deep)


def eye(g, x, y, style, look=0):
    if style == "closed":       # sleepy u
        for i, j in ((0, 1), (1, 2), (2, 2), (3, 1)):
            px(g, x + i, y + j, EYE)
    elif style == "happy":      # smiling ^
        for i, j in ((0, 2), (1, 1), (2, 1), (3, 2)):
            px(g, x + i, y + j, EYE)
    elif style == "wide":
        for j in range(5):
            for i in range(4):
                if (i, j) not in ((0, 0), (3, 0), (0, 4), (3, 4)):
                    px(g, x + i, y - 1 + j, EYE)
        px(g, x + 1, y, GLINT); px(g, x + 2, y, GLINT); px(g, x + 1, y + 1, GLINT)
    else:
        x += look
        for j in range(4):
            for i in range(3):
                px(g, x + i, y + j, EYE)
        px(g, x + 1 + look, y, GLINT)
        px(g, x + (2 if look <= 0 else 0), y + 3, GLINT_SOFT)


def face(g, cx, cy, look=0, eyes="open", beak=0):
    """Heart-shaped cream mask, shiny eyes, blush, and the little beak. cx is the face centre."""
    m = Mask().ellipse(cx - 3.5, cy, 5.5, 5.5).ellipse(cx + 4.5, cy, 5.5, 5.5).ellipse(cx + 0.5, cy + 3.5, 8, 4.5)
    shade(g, m, CREAM, hi=0, sh=1, clip=True)
    lx, rx = cx - 5, cx + 3
    if eyes == "open":
        eye(g, lx, cy - 1, eyes, look); eye(g, rx, cy - 1, eyes, look)
    else:
        eye(g, lx - 1, cy - 1, eyes); eye(g, rx, cy - 1, eyes)
    for x in (lx - 2, lx - 1, rx + 3, rx + 4):      # blush, only where the mask is showing
        if 0 <= x < W and g[(cy + 4 + YO) * W + x] in (CREAM.base, CREAM.sh):
            px(g, x, cy + 4, BLUSH)
    bx, by = cx - 1 + look, cy + 3
    if beak == 2:       # turned to the side for preening
        for i in range(5):
            px(g, bx + 2 + i, by, ORANGE.hi if i < 3 else ORANGE.base)
        for i in range(4):
            px(g, bx + 2 + i, by + 1, ORANGE.base)
        for i in range(2):
            px(g, bx + 2 + i, by + 2, ORANGE.sh)
        return
    for i in range(4):
        px(g, bx + i, by, ORANGE.hi)
    if beak == 1:       # open and happy
        for i in range(4):
            px(g, bx + i, by + 1, MOUTH_IN); px(g, bx + i, by + 2, MOUTH_IN)
            px(g, bx + i, by + 3, ORANGE.base)
        px(g, bx + 1, by + 2, TONGUE); px(g, bx + 2, by + 2, TONGUE)
        px(g, bx + 1, by + 4, ORANGE.sh); px(g, bx + 2, by + 4, ORANGE.sh)
    else:
        for i in range(4):
            px(g, bx + i, by + 1, ORANGE.base)
        px(g, bx + 1, by + 2, ORANGE.sh); px(g, bx + 2, by + 2, ORANGE.sh)


# ---------------------------------------------------------------- poses
REST = (0, 0)


def _stand(g, dy, lean, fl, fr, feet, look, eyes, beak, turn, nod, hdx, sit):
    """dy squashes him toward the ground (breathing, crouching, sitting); lean tips the
    upper body sideways over planted feet for the waddle."""
    bx, hx = 36 + lean, 36 + 2 * lean + hdx
    hy = 13 + dy + nod
    by, bry, brx = 29 + dy / 2, 14 - dy / 2, 13.5 + dy / 3
    sy = 24 + dy
    sides = ((-1, fl), (1, fr))
    for s, p in sides:      # raised flippers tuck behind the shoulder
        if p in RAISED:
            flipper(g, bx + s * 11, sy, s, p, front=False)
    if sit:                 # stubby tail poking out behind
        paint(g, Mask().poly([(bx - brx + 3, 39), (bx - brx - 3, 44.5), (bx - brx + 5, 44.5)]), SLATE, sh=1)
    body = Mask().ellipse(hx, hy, 11, 10.5).ellipse(bx, by, brx, bry)
    shade(g, body, SLATE, hi=2, sh=3)
    shade(g, Mask().ellipse(bx + 1, by + 2.5, brx - 4, bry - 3.5), CREAM, hi=0, sh=2, clip=True)
    paint(g, Mask().ellipse(bx + (1 if sit else 3.5), by - 2, 3 if sit else 3.5, 3), GLOW, clip=True)
    for i in range(3):      # specular on the crown
        px(g, hx + 3 + i, hy - 8, SHINE)
    px(g, hx + 6, hy - 7, SHINE)
    face(g, hx + 1 + turn + (3 * look if look < 0 else look), hy + 1 + min(nod, 2), look, eyes, beak)
    spread = 3 if sit else 0
    (ldx, llift), (rdx, rlift) = feet
    foot(g, 30 - spread + ldx, llift, sit)
    foot(g, 43 + spread + rdx, rlift, sit)
    for s, p in sides:
        if p not in RAISED:
            flipper(g, bx + s * 11, sy, s, p)


def _slide(g, p):
    """Belly slide, facing right: flipper paddling, feet kicking, beak open with joy."""
    k = p % 2
    for y0, y1 in ((37.5, 36 - k), (41.5, 42.5 - 2 * k)):      # feet trailing behind
        paint(g, Mask().path([(14, y0), (7, y1)], 2.3, 1.9), ORANGE, hi=1, sh=1)
    paint(g, Mask().poly([(15, 30), (8, 27 + k), (13, 36)]), SLATE, sh=1)       # tail
    hy = 31 - k
    body = Mask().ellipse(29, 36, 17, 9).ellipse(49, hy, 10, 9.5)
    shade(g, body, SLATE, hi=2, sh=2)
    shade(g, Mask().ellipse(32, 42.5, 16, 5).ellipse(51, hy + 8, 7, 5), CREAM, hi=0, sh=1, clip=True)
    shade(g, Mask().ellipse(52.5, hy + 1, 5.5, 5.5), CREAM, hi=0, sh=0, clip=True)    # cheek
    for i in range(3):
        px(g, 50 + i, hy - 8, SHINE)
    px(g, 53, hy - 7, SHINE)
    for i, j in ((0, 1), (1, 0), (2, 0), (3, 1)):           # happy eye
        px(g, 51 + i, hy - 2 + j, EYE)
    px(g, 53, hy + 3, BLUSH); px(g, 54, hy + 3, BLUSH)
    beak = Mask().poly([(58, hy - 0.5), (65.5, hy + 2), (58, hy + 4.5)])
    paint(g, beak, ORANGE, hi=1, sh=1, edge=True, edge_color=SLATE.deep)
    if k:
        for x in range(59, 63):
            px(g, x, hy + 2, MOUTH_IN)
    root, mid, tip = (35, 33), (28, 30 if k else 34), (22, 26 if k else 35)
    m = Mask().path([root, mid], 2.8, 3.3).path([mid, tip], 3.3, 2.0)
    shade(g, m, SLATE, hi=1, sh=1, edge=True)


SPRAY_MARKS = (((1, 38), (2, 38), (3, 33)), ((2, 36), (3, 36), (1, 41)),
               ((1, 35), (2, 35), (3, 40)), ((2, 39), (3, 39), (1, 33)))


def _z(pixels, x, y, size):
    for i in range(size):
        pixels.append((x + i, y)); pixels.append((x + i, y + size - 1))
        pixels.append((x + size - 1 - i, y + i))


@lru_cache(maxsize=None)
def frame(pose="stand", p=0, dy=0, lean=0, fl="down", fr="down", feet=(REST, REST), look=0,
          eyes="open", beak=0, turn=0, nod=0, hdx=0, sit=False, zzz=-1):
    g = new_grid()
    if pose == "slide":
        _slide(g, p)
    else:
        _stand(g, dy, lean, fl, fr, feet, look, eyes, beak, turn, nod, hdx, sit)
    g = outline(g, NAVY)
    if pose == "slide":                 # snow spray behind him, drawn after the outline
        for x, y in SPRAY_MARKS[p % 4]:
            px(g, x, y, SPRAY)
    if zzz >= 0:                        # sleep marks drift up, drawn after the outline so they stay clean
        marks = []
        _z(marks, 52, 10 - zzz, 4)
        if zzz >= 2:
            _z(marks, 58, 3 - (zzz - 2), 5)
        for x, y in marks:
            px(g, x, y, ZZZ)
    return to_image(g)


# ---------------------------------------------------------------- animations
def build_pet():
    idle = tuple(frame(dy=(i // 4) % 2, eyes="closed" if i == 14 else "open") for i in range(16))
    sit = tuple(frame(dy=5 + (i // 4) % 2, fl="belly", fr="belly", sit=True,
                      eyes="closed" if i == 13 else "open") for i in range(16))
    look = tuple(frame(look=d) for d in (0, -1, -1, 0, 1, 1, 0))
    walk = (frame(lean=-1, fl="out", feet=(REST, (2, 2))),
            frame(dy=1, feet=(REST, (1, 0))),
            frame(lean=1, fr="out", feet=((2, 2), REST)),
            frame(dy=1, feet=((1, 0), REST)))
    wave = tuple(frame(fr="up" if i % 2 == 0 else "cheer", lean=i % 2, eyes="happy" if i >= 2 else "open", beak=1)
                 for i in range(4))
    dance = (frame(lean=-1, fl="up", fr="out", feet=(REST, (1, 2)), eyes="happy", beak=1),
             frame(dy=2, fl="mid", fr="mid", eyes="happy"),
             frame(lean=1, fl="out", fr="up", feet=((-1, 2), REST), eyes="happy", beak=1),
             frame(dy=2, fl="mid", fr="mid", eyes="happy"))
    slide = tuple(frame("slide", p=i) for i in range(4))
    preen = (frame(turn=3, nod=1, eyes="closed", beak=2, fr="out"),                 # turn toward the flipper
             frame(lean=1, turn=4, nod=2, eyes="closed", beak=2, fr="preen"),       # nibble up
             frame(lean=1, turn=4, nod=3, eyes="closed", beak=2, fr="preen2"),      # nibble down
             frame(lean=1, turn=4, nod=2, eyes="closed", beak=2, fr="preen"))
    sleep = tuple(frame(dy=5 + (i // 2) % 2, fl="belly", fr="belly", sit=True, eyes="closed", nod=3, hdx=-2, zzz=i)
                  for i in range(4))
    hop = (frame(dy=3, fl="out", fr="out", eyes="happy"),
           frame(dy=-1, fl="up", fr="up", eyes="happy", beak=1),
           frame(dy=-1, fl="cheer", fr="cheer", eyes="happy", beak=1),
           frame(dy=3, fl="out", fr="out", eyes="happy"))
    fall = (frame(dy=-1, fl="up", fr="cheer", feet=((-3, 1), (3, 3)), eyes="wide", beak=1),)

    animations = {
        "idle": Animation(idle, 0.22),
        "sit": Animation(sit, 0.3),
        "look": Animation(look, 0.45),
        "walk": Animation(walk, 0.18),
        "alert": Animation(wave, 0.3),
        "fall": Animation(fall),
    }
    tricks = {"wave": wave, "dance": dance, "slide": slide, "preen": preen, "sleep": sleep, "hop": hop}
    for state, label, weight in (("wave", "Flipper wave", 2), ("dance", "Happy dance", 1),
                                 ("slide", "Belly slide", 1), ("preen", "Preen feathers", 3),
                                 ("sleep", "Sleepy tuck", 2), ("hop", "Happy hop", 1)):
        animations[state] = Animation(tricks[state],
                                      0.8 if state == "sleep" else 0.18,
                                      9 if state == "sleep" else 3, label, weight,
                                      cooldown=30 if state == "sleep" else 15,
                                      forward_speed=100 if state == "slide" else 0,
                                      hop_height=16 if state == "hop" else 0)
    return PetDefinition("penguin", "Pip", "Penguin", "A round little penguin with busy flippers.",
                         animations, Personality(walk_speed=50, roam_chance=0.55, trick_chance=0.2))
