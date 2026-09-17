"""Patches artwork and personality. No application or reminder dependencies.

Patches is a cheerful calico cat: white coat, an orange saddle, a black flank patch,
an orange rump and near hind leg, a slender black tail with an orange tip, and the
classic split calico face (black over one ear and eye, orange over the other, white
blaze and muzzle) with green eyes, a pink nose, and a permanent ":3" smile.

Art standard: 72 x 48 logical grid enlarged 2x to the 144 x 96 canvas, three-tone
shading, warm brown outline, hard alpha only. The pet faces right.
"""
from functools import lru_cache
import math
from .base import Animation, Personality, PetDefinition
from .pixelkit import GROUND, H, W, YO, Mask, Ramp, new_grid, outline, paint, px, rgb, to_image


WHITE = Ramp("#ffffff", "#f6efe2", "#d8ccb8", "#ad9f8a")
FARW = Ramp("#d7cbb7", "#d7cbb7", "#b9ab95", "#978a76")      # far-side limbs, in shadow
ORANGE = Ramp("#f7b465", "#e8913f", "#c26d29", "#93501d")
BLACK = Ramp("#6e6260", "#4b4140", "#352c2b", "#221b1a")
EARIN = Ramp("#f4b4b4", "#e99a9f", "#c97a82", "#a05c66")
LINE = rgb("#6b4a3a")        # mouth
RIM = rgb("#24170f")         # eye rims, pupils, closed-eye arcs
LID_PALE = rgb("#b3a49e")    # closed-eye arc over the black face patch
GREEN_HI, GREEN, GREEN_DK = rgb("#b5e08a"), rgb("#7fc15f"), rgb("#4d8c3f")
GLINT = rgb("#ffffff")
NOSE, NOSE_SH = rgb("#ee8f98"), rgb("#c96a78")
BLUSH = rgb("#f6cfc6")
BEAN = rgb("#ee9aa2")
TONGUE = rgb("#e9808c")
WHISKER = rgb("#9c8f80")
ZZZ = rgb("#7f9fb5")

# Any coat tone -> the deep tone of the same coat, for interior lines that follow the patches.
DEEPER = {}
for _r in (WHITE, FARW, ORANGE, BLACK):
    for _c in (_r.hi, _r.base, _r.sh):
        DEEPER[_c] = _r.deep


# ---------------------------------------------------------------- local kit helpers
def both(a, b):
    """Intersection of two masks."""
    m = Mask()
    for y in range(max(a.y0, b.y0), min(a.y1, b.y1) + 1):
        for x in range(max(a.x0, b.x0), min(a.x1, b.x1) + 1):
            if a.d[y * W + x] and b.d[y * W + x]:
                m.set(x, y - YO)
    return m


def patch(g, m, ramp, within=None):
    """Calico patch: recolor white fur under the mask tone for tone, so it keeps the body shading."""
    if within is not None:
        m = both(m, within)
    if m.x1 < 0:
        return
    tones = {WHITE.hi: ramp.hi, WHITE.base: ramp.base, WHITE.sh: ramp.sh, WHITE.deep: ramp.deep}
    for y in range(m.y0, m.y1 + 1):
        for x in range(m.x0, m.x1 + 1):
            i = y * W + x
            if m.d[i] and g[i] in tones:
                g[i] = tones[g[i]]


def crease(g, m, edge_if=None):
    """Interior line around a part about to be drawn, using the deep tone of whatever coat is underneath."""
    d = m.d
    for y in range(max(0, m.y0 - 1), min(H - 1, m.y1 + 1) + 1):
        for x in range(max(0, m.x0 - 1), min(W - 1, m.x1 + 1) + 1):
            i = y * W + x
            if d[i] or g[i] not in DEEPER:
                continue
            if ((x > 0 and d[i - 1]) or (x < W - 1 and d[i + 1]) or
                    (y > 0 and d[i - W]) or (y < H - 1 and d[i + W])):
                if edge_if is None or edge_if(x, y - YO):
                    g[i] = DEEPER[g[i]]


def _along(pts, frac):
    """Split a polyline at a fraction of its length; returns the trailing part."""
    lens = [math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts))]
    want, acc = sum(lens) * frac, 0.0
    for i, ln in enumerate(lens):
        if acc + ln >= want:
            t = (want - acc) / (ln or 1)
            cut = (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
            return [cut] + list(pts[i + 1:])
        acc += ln
    return list(pts[-2:])


# ---------------------------------------------------------------- body parts
def tail(g, pts, r0=2.0, r1=1.5, tip=0.7, edge=False):
    """Slender black tail with an orange tip."""
    m = Mask().path(pts, r0, r1)
    if edge:
        crease(g, m)
    paint(g, m, BLACK, hi=1, sh=1)
    paint(g, both(Mask().path(_along(pts, tip), r1 + 0.6, r1 + 0.6), m), ORANGE, hi=1, sh=1)


def leg(g, x, top, dx, lift, ramp, near):
    """Straight slim leg, sheared by dx for the stride, with a little white paw."""
    bottom = GROUND - 1 - lift
    if near:    # soft line up the body so the leg reads in front of it
        for y in range(top + 2, bottom + 1):
            for ex in (x - 1, x + 3):
                i = (y + YO) * W + ex
                if 0 <= ex < W and g[i] in DEEPER and g[i] not in (FARW.base, FARW.sh):
                    g[i] = DEEPER[g[i]]
    for y in range(top, bottom + 1):
        xo = round(dx * (y - top) / (bottom - top))
        paw = y >= bottom - 1
        for i in range(4 if paw else 3):
            c = ramp.sh if i == 0 else ramp.base
            if paw:
                c = (WHITE.sh if (y == bottom and i == 0) else WHITE.base) if near else FARW.base
            px(g, x + xo + i, y, c)


def limb(g, pts, ramp, r0=1.9, r1=1.9, paw=True, near=True, beans=False):
    """A bent or reaching leg drawn as a path, ending in a white paw."""
    m = Mask().path(pts, r0, r1)
    ex, ey = pts[-1]
    pm = Mask().ellipse(ex, ey, r1 + 0.6, r1 + 0.3) if paw else Mask()
    if near:
        crease(g, Mask().path(pts, r0, r1).ellipse(ex, ey, r1 + 0.6, r1 + 0.3) if paw else m)
    paint(g, m, ramp, sh=1)
    if paw:
        paint(g, pm, WHITE if near else FARW, sh=1)
        if beans:
            px(g, round(ex), round(ey - 0.5), BEAN)
            px(g, round(ex) + 1, round(ey - 0.5) - 1, BEAN)


def eye(g, x, y, face, look, blink, lid=RIM):
    """One 5-wide eye. face: smile (normal), play (dilated), happy (^ ^ squint).
    lid is the closed-eye line color; the eye on the black patch needs a pale one."""
    if face == "happy":
        for i, j in ((0, 2), (1, 1), (2, 0), (3, 1), (4, 2)):
            px(g, x + i, y + 1 + j, lid)
        return
    if blink:
        for i, j in ((0, 1), (1, 2), (2, 2), (3, 2), (4, 1)):
            px(g, x + i, y + 1 + j, lid)
        return
    if face == "play":      # big round pupils with a thin green ring
        for i in (1, 2, 3):
            px(g, x + i, y, RIM); px(g, x + i, y + 4, GREEN_HI)
        for j in (1, 2, 3):
            px(g, x, y + j, GREEN_DK if j == 1 else GREEN); px(g, x + 4, y + j, GREEN_DK if j == 1 else GREEN)
            for i in (1, 2, 3):
                px(g, x + i, y + j, RIM)
        px(g, x + 1, y + 1, GLINT)
        return
    for i in (1, 2, 3):
        px(g, x + i, y, RIM)
        px(g, x + i, y + 1, GREEN)
        px(g, x + i, y + 2, GREEN)
        px(g, x + i, y + 3, GREEN_HI)
        px(g, x + i, y + 4, GREEN_DK)
    for j in (1, 2, 3):
        px(g, x, y + j, RIM); px(g, x + 4, y + j, RIM)
    p = 2 + look
    for j in (1, 2, 3):
        px(g, x + p, y + j, RIM)
    px(g, x + (p - 1 if p > 1 else p + 1), y + 1, GLINT)


def head(g, cx, cy, face="smile", look=0, blink=False, tilt=0, ear=0, tongue=False):
    rel = lambda pts: [(cx + x, cy + y) for x, y in pts]
    e, t = ear, tilt
    # pointed ears behind the skull: black on the near side, orange on the far side
    paint(g, Mask().poly(rel([(-10.5, -1), (-9.5 - e, -14 + e - t), (-1, -6)])), BLACK, hi=1)
    paint(g, Mask().poly(rel([(-8.6, -5), (-8.4 - e, -11 + e - t), (-4, -6.5)])), EARIN, sh=1)
    paint(g, Mask().poly(rel([(2.5, -6), (10 + e, -14 + e + t), (11, -1)])), ORANGE, hi=1)
    paint(g, Mask().poly(rel([(5, -6.5), (9.2 + e, -11 + e + t), (9.2, -5)])), EARIN, sh=1)
    # wide-cheeked skull
    skull = (Mask().ellipse(cx, cy, 10.5, 8.5)
             .ellipse(cx - 7, cy + 3.2, 4.6, 3.6).ellipse(cx + 7, cy + 3.2, 4.6, 3.6))
    crease(g, skull)
    paint(g, skull, WHITE, hi=2, sh=1)
    # split calico face with a white blaze
    patch(g, Mask().ellipse(cx - 8, cy - 4, 7.5, 6.5).ellipse(cx - 9, cy + 1, 3, 3), BLACK, skull)
    patch(g, Mask().ellipse(cx + 9, cy - 4, 6.5, 6.5).ellipse(cx + 10, cy + 1, 2.5, 3), ORANGE, skull)
    # eyes; the head tilt drops the far eye a row
    eye(g, cx - 7, cy - 3, face, look, blink, LID_PALE)
    eye(g, cx + 4, cy - 3 + (1 if t > 0 else 0), face, look, blink)
    # blush, pink nose, and the :3
    px(g, cx - 7, cy + 3, BLUSH); px(g, cx - 6, cy + 3, BLUSH)
    px(g, cx + 8, cy + 3, BLUSH); px(g, cx + 9, cy + 3, BLUSH)
    for i in (0, 1, 2):
        px(g, cx + i, cy + 3, NOSE)
    px(g, cx + 1, cy + 4, NOSE_SH)
    px(g, cx + 1, cy + 5, LINE)
    for x, y in ((-2, 5), (-1, 6), (0, 6), (2, 6), (3, 6), (4, 5)):
        px(g, cx + x, cy + y, LINE)
    if tongue:
        px(g, cx + 1, cy + 6, TONGUE); px(g, cx + 1, cy + 7, TONGUE); px(g, cx + 2, cy + 7, TONGUE)


def whiskers(g, cx, cy):
    """Whisker hints, added after the outline so they stay thin."""
    for x, y in ((-14, 3), (-15, 2), (-14, 5), (-15, 6), (13, 3), (14, 2), (13, 5), (14, 6)):
        i = (cy + y + YO) * W + cx + x
        if 0 < cx + x < W - 1 and 0 <= cy + y + YO < H and g[i] is None:
            g[i] = WHISKER


def torso(g, R, M, C, r, rr=(7, 8), cr=(7, 8.5)):
    """White barrel from rump R through M to chest C, then the calico patches laid over it."""
    m = Mask().path([R, M, C], r, r).ellipse(R[0], R[1], rr[0], rr[1]).ellipse(C[0], C[1], cr[0], cr[1])
    paint(g, m, WHITE, hi=2, sh=3)
    ux, uy = C[0] - R[0], C[1] - R[1]
    n = math.hypot(ux, uy) or 1
    ux, uy = ux / n, uy / n
    at = lambda p, a, b: (p[0] + ux * a - uy * b, p[1] + uy * a + ux * b)      # a along the spine, b toward the belly
    s1, s2 = at(M, 5, -6), at(M, 10, -4)
    patch(g, Mask().ellipse(s1[0], s1[1], 7, 4).ellipse(s2[0], s2[1], 4, 3.5), ORANGE, m)        # saddle
    f1, f2 = at(M, -2, 2.5), at(M, -6, -1)
    patch(g, Mask().ellipse(f1[0], f1[1], 5.5, 4.5).ellipse(f2[0], f2[1], 3.5, 3), BLACK, m)     # flank
    return m


# ---------------------------------------------------------------- poses
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
REST = (0, 0)


def _haunch(g, x, y, rx=6, ry=6.5, edge_if=None):
    m = Mask().ellipse(x, y, rx, ry)
    crease(g, m, edge_if)
    paint(g, m, ORANGE, clip=True, sh=2)


def _stand(g, dy=0, tail_i=0, legs=(REST, REST, REST, REST), hdx=0, hdy=0, arm=None, **face):
    nh, nf, fh, ff = legs
    tail(g, [(x, y + dy) for x, y in TAIL_STAND[tail_i]])
    leg(g, 21, 32, fh[0], fh[1], FARW, False)
    leg(g, 43, 32, ff[0], ff[1], FARW, False)
    torso(g, (16.5, 28 + dy), (29, 28 + dy), (42, 27.5 + dy), 7.3)
    _haunch(g, 16.5, 31 + dy, edge_if=lambda x, y: x > 19 and y > 27)
    leg(g, 15, 33, nh[0], nh[1], ORANGE, True)
    if arm is None:
        leg(g, 38, 32, nf[0], nf[1], WHITE, True)
    paint(g, Mask().ellipse(46, 21.5 + dy, 5.5, 6.5), WHITE)                     # neck
    head(g, 53 + hdx, 13 + dy + hdy, **face)
    if arm is not None:
        limb(g, [(40, 31 + dy)] + list(arm), WHITE, 2.0, 1.9, beans=True)
    return 53 + hdx, 13 + dy + hdy


def _sit(g, dy=0, tail_i=0, hdx=0, hdy=0, arm=None, **face):
    tail(g, TAIL_SIT[tail_i])
    leg(g, 42, 34, 0, 0, FARW, False)
    body = Mask().ellipse(24, 35.5, 11, 9).ellipse(36, 30 + dy, 8, 12)
    paint(g, body, WHITE, hi=2, sh=3)
    patch(g, Mask().ellipse(29, 21 + dy, 5, 4.5).ellipse(26, 26 + dy, 4, 3.5), ORANGE, body)   # saddle
    patch(g, Mask().ellipse(31, 32, 4.5, 5), BLACK, body)                                       # flank
    _haunch(g, 24, 37.5, 8, 7, edge_if=lambda x, y: x > 24 or y < 33)                           # folded thigh
    hp = Mask().ellipse(30.5, 43.4, 4.5, 1.7)
    crease(g, hp)
    paint(g, hp, WHITE, sh=1)                                                                   # hind paw
    if arm is None:
        leg(g, 37, 34, 0, 0, WHITE, True)
    paint(g, Mask().ellipse(40, 21 + dy, 6, 6.5), WHITE)
    hx, hy = 45 + hdx, 13 + dy + hdy
    if arm is not None:                 # raised paw goes over the face
        head(g, hx, hy, **face)
        limb(g, [(38, 32 + dy)] + list(arm), WHITE, 2.0, 2.0)
    else:
        head(g, hx, hy, **face)
    return hx, hy


def _loaf(g, dy=0, **face):
    """Curled up asleep in a loaf, tail wrapped round the front. dy lifts the back for slow breathing."""
    m = Mask().ellipse(28, 37 - dy * 0.5, 18, 8 + dy * 0.5).ellipse(15, 37.5, 8, 7.5)
    paint(g, m, WHITE, hi=2, sh=3)
    patch(g, Mask().ellipse(30, 30, 8, 4.5).ellipse(36, 32, 4, 3.5), ORANGE, m)
    patch(g, Mask().ellipse(24, 37, 5.5, 4).ellipse(20, 34, 3, 3), BLACK, m)
    patch(g, Mask().ellipse(10, 37, 5, 6), ORANGE, m)
    fp = Mask().ellipse(52, 43.2, 5.5, 1.9)
    crease(g, fp)
    paint(g, fp, WHITE, sh=1)                                                   # tucked front paws
    tail(g, TAIL_LOAF, 2.0, 1.6, 0.72, edge=True)
    head(g, 49, 32, face="smile", blink=True, ear=1)
    return 49, 32


def _bow(g, deep=0, tail_i=0, **face):
    """Play-bow stretch: chest down, front legs out along the ground, rump and tail high."""
    tail(g, [(x, y - deep) for x, y in ((13, 22), (10, 16), (9 + tail_i, 10), (11 + tail_i, 5), (15 + tail_i, 4), (17 + tail_i, 7))])
    leg(g, 20, 29, 1, 0, FARW, False)
    limb(g, [(45, 39 + deep), (56, 42.4), (64, 42.6)], FARW, 1.9, 1.7, near=False)
    torso(g, (17, 26 - deep), (30, 31), (42, 35.5 + deep), 7, (7, 7.5), (6.5, 7))
    _haunch(g, 17, 29 - deep, 6, 6.5, edge_if=lambda x, y: x > 19 and y > 26)
    leg(g, 15, 31 - deep, 1, 0, ORANGE, True)
    limb(g, [(42, 40 + deep), (54, 43), (65, 43)], WHITE, 2.0, 1.8)
    head(g, 52, 28 + deep, **face)
    return 52, 28 + deep


def _crouch(g, wig=0, **face):
    """Hunting crouch: chest low, rump up and wiggling, tail swishing."""
    w = wig
    tail(g, [(13 + w, 24), (8 + w, 21), (6 + 2 * w, 15), (7 + 3 * w, 9), (10 + 3 * w, 6)])
    leg(g, 21 + w, 33, 0, 0, FARW, False)
    limb(g, [(46, 38), (52, 42.6), (58, 42.8)], FARW, 1.9, 1.7, near=False)
    torso(g, (17 + w, 27 - abs(w)), (30, 32), (42, 35), 6.8, (7, 7.5), (6.5, 7))
    _haunch(g, 17 + w, 31 - abs(w), 6.5, 6.5, edge_if=lambda x, y: x > 19 + w and y > 28)
    leg(g, 16 + w, 34, 0, 0, ORANGE, True)
    limb(g, [(42, 39), (47, 43), (54, 43)], WHITE, 2.0, 1.8)
    head(g, 53, 28, **face)
    return 53, 28


def _leap(g, phase=0, **face):
    """Airborne pounce: 0 = rising with paws reaching, 1 = coming down paws first."""
    if phase == 0:
        tail(g, [(12, 27), (8, 24), (5.5, 19), (6.5, 13)])
        limb(g, [(19, 32), (14, 36), (11, 39)], FARW, 2.2, 1.6, near=False)
        limb(g, [(45, 29), (55, 32.5), (63, 34)], FARW, 1.8, 1.6, near=False)
        torso(g, (17.5, 29), (30, 25.5), (42, 21.5), 6.5, (6.5, 7), (6.5, 7.5))
        _haunch(g, 17, 31, 6, 6, edge_if=lambda x, y: x > 20)
        limb(g, [(14.5, 33), (9.5, 36.5), (6, 39)], ORANGE, 2.3, 1.7)
        paint(g, Mask().ellipse(46, 18, 5.5, 6), WHITE)
        limb(g, [(42, 27), (52, 27.5), (62, 25.5)], WHITE, 1.9, 1.7, beans=True)
        head(g, 53, 14, **face)
        return 53, 14
    tail(g, [(13, 18), (9, 15), (7, 10), (8, 5)])
    limb(g, [(17, 22), (11, 22.5), (7, 23.5)], FARW, 2.2, 1.6, near=False)
    limb(g, [(46, 31), (55, 35), (62, 37)], FARW, 1.8, 1.6, near=False)
    torso(g, (17, 21), (30, 23), (42, 27), 6.5, (6.5, 7), (6.5, 7.5))
    _haunch(g, 16, 23, 6, 6, edge_if=lambda x, y: x > 19)
    limb(g, [(14, 25), (9, 28), (5.5, 31)], ORANGE, 2.3, 1.7)
    paint(g, Mask().ellipse(46, 24, 5.5, 6), WHITE)
    limb(g, [(42, 32), (50, 38), (56, 42)], WHITE, 1.9, 1.7, beans=True)
    head(g, 54, 20, **face)
    return 54, 20


def _z(pixels, x, y, size):
    for i in range(size):
        pixels.append((x + i, y)); pixels.append((x + i, y + size - 1))
        pixels.append((x + size - 1 - i, y + i))


POSES = {"stand": _stand, "sit": _sit, "loaf": _loaf, "bow": _bow, "crouch": _crouch, "leap": _leap}


@lru_cache(maxsize=None)
def _frame(pose, zzz, params):
    g = new_grid()
    hx, hy = POSES[pose](g, **dict(params))
    g = outline(g)
    whiskers(g, hx, hy)
    if zzz >= 0:                         # sleep marks drift up, drawn after the outline so they stay clean
        marks = []
        _z(marks, 63, 17 - zzz, 3)
        if zzz >= 2:
            _z(marks, 66, 9 - (zzz - 2), 4)
        for x, y in marks:
            px(g, x, y, ZZZ)
    return to_image(g)


def frame(pose="stand", zzz=-1, **params):
    return _frame(pose, zzz, tuple(sorted(params.items())))


# ---------------------------------------------------------------- animations
def _legs(a=REST, b=REST):
    """Diagonal gait: near hind + far fore move together, far hind + near fore together."""
    return (a, b, b, a)


WALK = (((3, 0), (-3, 0), 1), ((0, 2), (0, 0), 0), ((-3, 0), (3, 0), 1), ((0, 0), (0, 2), 0))


def build_pet():
    idle = tuple(frame(dy=(i // 4) % 2, tail_i=(i // 2) % 2, blink=i == 14) for i in range(16))
    sit = tuple(frame("sit", dy=(i // 4) % 2, tail_i=(i // 2) % 2, blink=i == 14) for i in range(16))
    look = tuple(frame(look=d, hdx=2 * d, tail_i=i % 2) for i, d in enumerate((0, 0, -1, -1, -1, 0, 1, 1, 1, 0)))
    walk = tuple(frame(dy=bob, tail_i=i % 2, legs=_legs(a, b)) for i, (a, b, bob) in enumerate(WALK))
    alert = tuple(frame("sit", dy=i, tail_i=i, face="happy", ear=0) for i in (0, 1))
    fall = (frame(tail_i=1, face="play", legs=((-3, 0), (3, 0), (-2, 0), (4, 0))),)
    stretch = tuple(frame("bow", deep=i, tail_i=i, face="happy") for i in (0, 1))
    wiggle = tuple(frame("crouch", wig=w, face="play") for w in (-1, 0, 1))
    pounce = tuple(frame("leap", phase=i, face="play") for i in (0, 1))
    swat = tuple(frame(face="play", tail_i=i % 2, arm=a) for i, a in enumerate((
        ((47, 33), (57, 29), (64, 24)), ((48, 33), (58, 32), (66, 30)), ((47, 34), (55, 37), (60, 40)))))
    groom = tuple(frame("sit", face="happy", tilt=1, hdx=1, hdy=1 + i, tail_i=i, tongue=i == 0, arm=a)
                  for i, a in enumerate((((46, 30), (50, 22)), ((48, 27), (54, 15)))))
    purr = tuple(frame("sit", dy=i, tail_i=0, face="happy") for i in (0, 1))
    nap = tuple(frame("loaf", zzz=i, dy=(i // 2) % 2) for i in range(4))
    knead = tuple(frame(face="happy", tail_i=(i // 2) % 2, dy=i % 2,
                        legs=(REST, (0, 3) if i == 0 else REST, REST, (0, 3) if i == 2 else REST))
                  for i in range(4))
    hop = tuple(frame(tail_i=i % 2, face="happy" if i in (1, 2) else "smile",
                      legs=_legs((0, 4), (0, 4)) if i in (1, 2) else _legs(), dy=0 if i in (1, 2) else 1)
                for i in range(4))

    animations = {
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
    return PetDefinition("cat", "Patches", "Calico Cat", "A curious calico with a playful streak.",
                         animations, Personality(walk_speed=70, trick_chance=0.25))
