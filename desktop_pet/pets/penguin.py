"""Pip artwork and personality. No application or reminder dependencies.

Pip is a small emperor penguin: black head, chin and throat, golden ear patches that
fade into a lemon wash on the upper chest, a white front edged with a dark border, a
blue-grey back, long narrow flippers, a long slender down-curved bill with a pink-orange
stripe on the lower mandible, and charcoal feet.

Art standard: 72 x 48 logical grid enlarged 2x to the 144 x 96 canvas, three-tone
shading, a dark navy outline, hard alpha only. Pip stands with his body toward the
viewer and his head in profile facing right; the belly slide faces right.
"""
from functools import lru_cache
from .base import Animation, Personality, PetDefinition
from .pixelkit import GROUND, H, W, YO, Mask, Ramp, edge_pass, new_grid, outline, paint, px, rgb, to_image


SLATE = Ramp("#7d95b4", "#50647f", "#38475e", "#1d2738")      # blue-grey back
BLACK = Ramp("#5d6a83", "#2f3748", "#1f2532", "#10131b")      # head, chin, throat
FLIP = Ramp("#6a7d9b", "#3a475d", "#273142", "#141a26")       # flippers, dark on top
WHITE = Ramp("#ffffff", "#f8f5ec", "#d9d3c6", "#b3ab9b")
FOOT = Ramp("#8a94a6", "#434957", "#2a2e39", "#0f1117")       # charcoal feet with a light top
GLOW = Ramp("#ffffff", "#ffffff", "#ffffff", "#ffffff")       # belly highlight
BORDER = rgb("#1c2230")      # the clean dark line between the back and the white front
GOLD = (rgb("#f5951c"), rgb("#fbb62a"), rgb("#fbd65e"))       # ear patch, top to bottom
LEMON = (rgb("#fbe48a"), rgb("#fcefb8"), rgb("#fbf4d8"))      # chest wash, top to bottom
BILL, BILL_HI, STRIPE = rgb("#262a36"), rgb("#56607a"), rgb("#f4876a")
NAVY = rgb("#141a28")        # outline: cool and dark, suits the coat
EYE, RING = rgb("#07080d"), rgb("#a3afc4")
LID = rgb("#c9d2e2")         # closed and smiling eyes, light so they show on the black head
GLINT = rgb("#ffffff")
MOUTH_IN = rgb("#8a3438")
SHINE = rgb("#8c9ab3")       # little specular on the crown
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


def tint(g, m, color_at, over):
    """Recolour the pixels of a mask that currently hold one of the `over` colours."""
    for y in range(max(0, m.y0), m.y1 + 1):
        for x in range(max(0, m.x0), m.x1 + 1):
            i = y * W + x
            if m.d[i] and g[i] in over:
                c = color_at(x, y - YO)
                if c is not None:
                    g[i] = c


def bands(colors, start, step):
    """Three colour bands that step along an axis, then nothing."""
    def pick(v):
        n = int((v - start) // step)
        return colors[max(0, n)] if n < len(colors) else None
    return pick


WHITES = (WHITE.hi, WHITE.base, WHITE.sh)
DARKS = (BLACK.hi, BLACK.base, BLACK.sh, SLATE.hi, SLATE.base, SLATE.sh, BORDER)


# ---------------------------------------------------------------- parts
FLIPPER = {     # polyline relative to the shoulder; x is mirrored for the left flipper
    "down": ((0, 0), (3, 8), (2, 16)),
    "out": ((0, 0), (6, 6), (10, 12)),
    "mid": ((0, 0), (7, -1), (13, -3)),
    "up": ((0, 0), (5, -6), (8, -13)),
    "cheer": ((0, 0), (7, -4), (12, -8)),
    "belly": ((0, 0), (2, 8), (-1, 14)),
    "preen": ((0, 0), (6, 0), (8, -6)),
    "preen2": ((0, 0), (6, 1), (9, -4)),
}
RAISED = ("up", "cheer", "mid")


def flipper(g, sx, sy, side, pose, front=True):
    a, b, c = [(sx + side * x, sy + y) for x, y in FLIPPER[pose]]
    m = Mask().path([a, b], 2.5, 2.9).path([b, c], 2.9, 1.7)       # long and narrow, widest at the elbow
    shade(g, m, FLIP, hi=1, sh=2, edge=front,
          edge_if=lambda x, y: y > sy + 2 or y < sy - 3 or abs(x - sx) > 4)


def foot(g, cx, lift=0, big=False):
    rx, ry = (5.2, 2.3) if big else (4.6, 2.0)
    m = Mask().ellipse(cx, GROUND - ry - lift, rx, ry)
    paint(g, m, FOOT, hi=1, sh=1, edge=True, edge_color=BORDER)
    for tx in (-2, 1):      # toe notches
        px(g, round(cx) + tx, GROUND - 1 - lift, FOOT.deep)
        px(g, round(cx) + tx, GROUND - 2 - lift, FOOT.sh)


def head(g, hx, hy, d=1, eyes="open", bill=0):
    """Black head in profile. d is +1 facing right, -1 facing left. bill: 0 closed, 1 open, 2 pointing down."""
    X = (lambda o: hx + o) if d > 0 else (lambda o: hx - 1 - o)
    nx = hx - d
    shade(g, Mask().ellipse(hx, hy, 7.5, 7).ellipse(nx, hy + 6.5, 6.8, 6), BLACK, hi=2, sh=2)
    for o in (0, 1, 2):     # specular on the crown
        px(g, X(o), hy - 5, SHINE)
    px(g, X(3), hy - 4, SHINE)
    # bill: long, slender, tip drooping; pink-orange stripe along the lower mandible
    if bill == 2:
        for i in range(7):
            px(g, X(5 + i), hy + 1 + i, BILL_HI if i < 4 else BILL)
            px(g, X(4 + i), hy + 1 + i, STRIPE if 0 < i < 5 else BILL)
    else:
        for o in range(6, 13):
            px(g, X(o), hy, BILL_HI if o < 10 else BILL)
        low = hy + 1 + bill
        if bill:
            for o in range(6, 12):
                px(g, X(o), hy + 1, MOUTH_IN)
        for o in range(6, 15 - 2 * bill):
            px(g, X(o), low, STRIPE if 6 < o < 12 else BILL)
        if not bill:
            px(g, X(14), hy + 2, BILL)
    # small dark eye made readable with a catchlight and a soft ring
    if eyes == "closed":
        for o, j in ((1, -2), (2, -1), (3, -1), (4, -2)):
            px(g, X(o), hy + j, LID)
    elif eyes == "happy":
        for o, j in ((1, -1), (2, -2), (3, -2), (4, -1)):
            px(g, X(o), hy + j, LID)
    elif eyes == "wide":
        for o in (1, 2, 3, 4):
            for j in (-3, -2, -1, 0):
                if (o, j) not in ((1, -3), (4, -3), (1, 0), (4, 0)):
                    px(g, X(o), hy + j, GLINT)
        for o in (2, 3):
            for j in (-2, -1):
                px(g, X(o), hy + j, EYE)
    else:
        for o in (2, 3):
            for j in (-3, -2, -1):
                px(g, X(o), hy + j, EYE)
        px(g, X(3), hy - 3, GLINT)
        for o, j in ((1, -3), (1, -2), (1, -1), (2, 0), (3, 0), (4, -1), (4, -2), (4, -3), (2, -4), (3, -4)):
            px(g, X(o), hy + j, RING)


def ear_patch(g, hx, hy, d=1):
    """Golden auricular patch: orange behind the eye, sweeping down the neck toward the chest."""
    pts = [(hx - d * 3, hy + 1.5), (hx - d * 3.5, hy + 6), (hx - d * 1.5, hy + 10)]
    m = Mask().path(pts, 1.8, 2.5)
    tint(g, m, lambda x, y: GOLD[0] if y < hy + 4 else GOLD[1] if y < hy + 7 else GOLD[2], DARKS + WHITES + LEMON)


# ---------------------------------------------------------------- poses
REST = (0, 0)


def _stand(g, dy, lean, fl, fr, feet, look, eyes, bill, nod, hdx, sit):
    """dy squashes him toward the ground (breathing, crouching, sitting); lean tips the
    upper body sideways over planted feet for the waddle."""
    d = -1 if look < 0 else 1
    bx = 35 + lean
    hx = 35 + 2 * lean + hdx + 2 * d + (2 if look > 0 else 0)
    hy = 8 + dy + nod
    cy = 21 + dy
    by, bry, brx = 31 + dy / 2, 13 - dy / 2, 13 + dy / 3
    sy = 20 + dy
    sides = ((-1, fl), (1, fr))
    for s, p in sides:      # raised flippers tuck behind the shoulder
        if p in RAISED:
            flipper(g, bx + s * 9, sy, s, p, front=False)
    if sit:                 # stubby tail poking out behind
        paint(g, Mask().poly([(bx - brx + 3, 39), (bx - brx - 3, 44.5), (bx - brx + 5, 44.5)]), SLATE, sh=1)
    body = Mask().ellipse(bx + lean / 2, cy, 9.5, 8).ellipse(bx, by, brx, bry)
    shade(g, body, SLATE, hi=2, sh=3)
    head(g, hx, hy, d, eyes, bill)
    fx = bx + 1
    front = lambda grow: (Mask().ellipse(fx, by + 1, brx - 3.2 + grow, bry - 2.2 + grow)
                          .ellipse(fx + lean / 2, cy + 3.5, 6.3 + grow, 6.5 + grow))
    paint(g, front(1), Ramp("#1c2230", "#1c2230", "#1c2230", "#1c2230"), clip=True)      # dark border line
    shade(g, front(0), WHITE, hi=0, sh=2, clip=True)
    tint(g, front(0), lambda x, y: bands(LEMON, cy - 3, 3)(y), WHITES)                   # lemon wash on the chest
    paint(g, Mask().ellipse(fx + (0 if sit else 2.5), by - 1, 3, 3), GLOW, clip=True)
    ear_patch(g, hx, hy, d)
    spread = 3 if sit else 0
    (ldx, llift), (rdx, rlift) = feet
    foot(g, 29 - spread + ldx, llift, sit)
    foot(g, 42 + spread + rdx, rlift, sit)
    for s, p in sides:
        if p not in RAISED:
            flipper(g, bx + s * 9, sy, s, p)


def _slide(g, p):
    """Belly slide, facing right: flipper paddling, feet kicking, bill open with joy."""
    k = p % 2
    for y0, y1 in ((37.5, 36 - k), (41.5, 42.5 - 2 * k)):      # feet trailing behind
        paint(g, Mask().path([(14, y0), (7, y1)], 2.3, 1.9), FOOT, hi=1, sh=1)
    paint(g, Mask().poly([(16, 30), (8, 27 + k), (13, 37)]), SLATE, sh=1)       # tail
    hy = 26 - k
    shade(g, Mask().ellipse(28, 36.5, 16, 8.5).ellipse(38, 35, 10, 10), SLATE, hi=2, sh=2)
    under = lambda grow: Mask().ellipse(29, 42.5, 14 + grow, 5 + grow).ellipse(42, 40.5, 6.5 + grow, 5 + grow)
    paint(g, under(1), Ramp("#1c2230", "#1c2230", "#1c2230", "#1c2230"), clip=True)
    shade(g, under(0), WHITE, hi=0, sh=1, clip=True)
    tint(g, under(0), lambda x, y: bands(LEMON, -47, 3)(-x), WHITES)            # lemon strongest by the neck
    shade(g, Mask().path([(43, 34), (50, hy + 2)], 6.4, 6.4).ellipse(51, hy, 7.5, 7), BLACK, hi=2, sh=2)
    # golden patch behind the eye, running down the neck to the chest
    m = Mask().path([(48, hy + 1.5), (46, hy + 6), (45.5, 39)], 1.8, 2.6)
    tint(g, m, lambda x, y: GOLD[0] if y < hy + 4 else GOLD[1] if y < hy + 8 else GOLD[2], DARKS + WHITES + LEMON)
    for o in (0, 1, 2):
        px(g, 51 + o, hy - 5, SHINE)
    px(g, 54, hy - 4, SHINE)
    for o, j in ((1, -1), (2, -2), (3, -2), (4, -1)):          # happy eye
        px(g, 51 + o, hy + j, LID)
    for o in range(6, 13):
        px(g, 51 + o, hy, BILL_HI if o < 10 else BILL)
    if k:
        for o in range(6, 12):
            px(g, 51 + o, hy + 1, MOUTH_IN)
    for o in range(6, 15 - 2 * k):
        px(g, 51 + o, hy + 1 + k, STRIPE if 6 < o < 12 else BILL)
    if not k:
        px(g, 65, hy + 2, BILL)
    root, mid, tip = (35, 32), (27, 29 if k else 33), (20, 25 if k else 35)
    m = Mask().path([root, mid], 2.5, 2.9).path([mid, tip], 2.9, 1.7)
    shade(g, m, FLIP, hi=1, sh=1, edge=True)


SPRAY_MARKS = (((1, 38), (2, 38), (3, 33)), ((2, 36), (3, 36), (1, 41)),
               ((1, 35), (2, 35), (3, 40)), ((2, 39), (3, 39), (1, 33)))


def _z(pixels, x, y, size):
    for i in range(size):
        pixels.append((x + i, y)); pixels.append((x + i, y + size - 1))
        pixels.append((x + size - 1 - i, y + i))


@lru_cache(maxsize=None)
def frame(pose="stand", p=0, dy=0, lean=0, fl="down", fr="down", feet=(REST, REST), look=0,
          eyes="open", bill=0, nod=0, hdx=0, sit=False, zzz=-1):
    g = new_grid()
    if pose == "slide":
        _slide(g, p)
    else:
        _stand(g, dy, lean, fl, fr, feet, look, eyes, bill, nod, hdx, sit)
    g = outline(g, NAVY)
    if pose == "slide":                 # snow spray behind him, drawn after the outline
        for x, y in SPRAY_MARKS[p % 4]:
            px(g, x, y, SPRAY)
    if zzz >= 0:                        # sleep marks drift up, drawn after the outline so they stay clean
        marks = []
        _z(marks, 52, 12 - zzz, 4)
        if zzz >= 2:
            _z(marks, 58, 5 - (zzz - 2), 5)
        for x, y in marks:
            px(g, x, y, ZZZ)
    return to_image(g)


# ---------------------------------------------------------------- animations
def build_pet():
    idle = tuple(frame(dy=(i // 4) % 2, eyes="closed" if i == 14 else "open") for i in range(16))
    sit = tuple(frame(dy=6 + (i // 4) % 2, fl="belly", fr="belly", sit=True,
                      eyes="closed" if i == 13 else "open") for i in range(16))
    look = tuple(frame(look=d) for d in (0, -1, -1, 0, 1, 1, 0))
    walk = (frame(lean=-1, fl="out", feet=(REST, (2, 2))),
            frame(dy=1, feet=(REST, (1, 0))),
            frame(lean=1, fr="out", feet=((2, 2), REST)),
            frame(dy=1, feet=((1, 0), REST)))
    # He waves the flipper behind his head so it never crosses the long bill.
    wave = tuple(frame(fl="up" if i % 2 == 0 else "cheer", lean=-(i % 2), eyes="happy" if i >= 2 else "open", bill=1)
                 for i in range(4))
    dance = (frame(lean=-1, fl="up", fr="out", feet=(REST, (1, 2)), eyes="happy", bill=1),
             frame(dy=2, fl="mid", fr="mid", eyes="happy"),
             frame(lean=1, fl="out", fr="cheer", feet=((-1, 2), REST), eyes="happy", bill=1),
             frame(dy=2, fl="mid", fr="mid", eyes="happy"))
    slide = tuple(frame("slide", p=i) for i in range(4))
    preen = (frame(nod=1, eyes="closed", fr="out"),                                 # turn toward the flipper
             frame(lean=1, nod=2, eyes="closed", bill=2, fr="preen"),               # nibble up
             frame(lean=1, nod=3, eyes="closed", bill=2, fr="preen2"),              # nibble down
             frame(lean=1, nod=2, eyes="closed", bill=2, fr="preen"))
    sleep = tuple(frame(dy=6 + (i // 2) % 2, fl="belly", fr="belly", sit=True, eyes="closed", bill=2,
                        nod=3, hdx=-2, zzz=i) for i in range(4))
    hop = (frame(dy=3, fl="out", fr="out", eyes="happy"),
           frame(dy=-1, fl="up", fr="cheer", eyes="happy", bill=1),
           frame(dy=-1, fl="cheer", fr="mid", eyes="happy", bill=1),
           frame(dy=3, fl="out", fr="out", eyes="happy"))
    fall = (frame(dy=-1, fl="up", fr="cheer", feet=((-3, 1), (3, 3)), eyes="wide", bill=1),)

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
    return PetDefinition("penguin", "Pip", "Emperor Penguin", "A stately little emperor penguin with busy flippers.",
                         animations, Personality(walk_speed=50, roam_chance=0.55, trick_chance=0.2))
