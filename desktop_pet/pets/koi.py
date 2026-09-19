"""Koi artwork and personality. No application or reminder dependencies.

A Kohaku koi seen from the side: a white body with bold red-orange patches on the
head, back, and tail root, a big dark eye with a catchlight, a pair of barbels at
the mouth, and long pale fins: a dorsal fin, a near-side pectoral, small pelvic and
anal fins, and a forked tail. The body flexes along a travelling spine wave so the
swim cycle reads as a real tail beat.

Art standard: 72 x 48 logical grid enlarged 2x to the 144 x 96 canvas, three-tone
shading, warm brown outline, hard alpha only. The fish faces right, floats in the
middle of the canvas, and keeps a one pixel margin on every side. It is a swimmer
(movement="swim"), so nothing rests on the ground line.
"""
from functools import lru_cache
import math
from .base import Animation, Personality, PetDefinition
from .pixelkit import H, OUT, W, YO, Mask, Ramp, new_grid, paint, patch, px, rgb, to_image


WHITE = Ramp("#ffffff", "#f6f0e8", "#ddd3c8", "#b8a898")
RED = Ramp("#f7703f", "#e04524", "#b12f18", "#7d1f10")
FIN = Ramp("#fff2ef", "#f6dcd8", "#dcb9b8", "#b8949a")
FIN_OUT = rgb("#9a7370")                # softer outline so the fins read as thin
GILL = {WHITE.hi: rgb("#ece3d9"), WHITE.base: rgb("#e6dcd0"), WHITE.sh: rgb("#cdc1b4"),
        RED.hi: RED.base, RED.base: RED.sh, RED.sh: RED.deep}     # scale arcs and the gill line
RAY = {FIN.hi: FIN.base, FIN.base: FIN.sh, FIN.sh: FIN.deep}      # fin rays
PUPIL, IRIS, IRIS_LIGHT = rgb("#14100e"), rgb("#4a3220"), rgb("#8a6a48")
GLINT = rgb("#ffffff")
MOUTH_IN, LIP = rgb("#5e2a30"), rgb("#f0c6c0")
BARBEL = rgb("#cfa49e")
MOUTH_LINE = rgb("#9a7a66")
BUBBLE, BUBBLE_HI = rgb("#8ecbee"), rgb("#ffffff")

CY = 22                                 # spine row at rest: the middle of the canvas
NOSE = 66
TAIL_ROOT = 19
# Body silhouette: (x, half height above the spine, half height below the spine).
PROFILE = ((19, 2.4, 2.4), (23, 3.2, 3.0), (28, 5.0, 4.6), (34, 6.9, 6.3), (40, 8.3, 7.6),
           (47, 9.0, 8.4), (54, 8.8, 8.3), (59, 7.6, 7.4), (63, 5.4, 5.6), (65.5, 2.8, 3.6), (66.6, 0.0, 0.0))


def prof(x):
    """Cosine-smoothed body half heights at a column."""
    if x < PROFILE[0][0] or x > PROFILE[-1][0]:
        return 0.0, 0.0
    for (x0, a0, b0), (x1, a1, b1) in zip(PROFILE, PROFILE[1:]):
        if x0 <= x <= x1:
            t = (1 - math.cos(math.pi * (x - x0) / (x1 - x0))) / 2
            return a0 + (a1 - a0) * t, b0 + (b1 - b0) * t
    return 0.0, 0.0


def top(x):
    return CY - prof(x)[0]


def bottom(x):
    return CY + prof(x)[1]


# ---------------------------------------------------------------- the spine wave
def spine(phase, amp, curve, tilt, flick):
    """Vertical offset of every column: a wave travelling from the nose to the tail whose
    amplitude grows toward the tail, plus a static arch (curve), a nose tilt, and an
    extra tail flick. Returned as a list indexed by column."""
    s = []
    for x in range(W):
        back = (NOSE - x) / 45                       # 0 at the nose, 1 at the tail root
        a = amp * (0.35 + 2.2 * back)
        v = a * math.sin(2 * math.pi * phase - 2 * math.pi * back * 0.72)
        v += curve * (1 - ((x - 40) / 28) ** 2)
        if x > 44:
            v += tilt * ((x - 44) / 22) ** 2
        if x < TAIL_ROOT:
            v += flick * (TAIL_ROOT - x) / 16
        s.append(v)
    return s


def ell(S, cx, cy, rx, ry):
    """Ellipse in straight fish coordinates, bent along the spine column by column."""
    m = Mask()
    for x in range(math.floor(cx - rx) - 1, math.ceil(cx + rx) + 2):
        if not 0 <= x < W:
            continue
        dx = (x + 0.5 - cx) / rx
        if abs(dx) > 1:
            continue
        half = ry * math.sqrt(1 - dx * dx)
        c = cy + S[x]
        for y in range(math.floor(c - half), math.ceil(c + half) + 1):
            if c - half <= y + 0.5 <= c + half:
                m.set(x, y)
    return m


def poly(S, pts):
    """Polygon in straight fish coordinates, bent along the spine column by column."""
    m = Mask()
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    n = len(pts)
    for x in range(math.floor(min(xs)), math.ceil(max(xs)) + 1):
        if not 0 <= x < W:
            continue
        qx, off = x + 0.5, S[x]
        for y in range(math.floor(min(ys) + off) - 1, math.ceil(max(ys) + off) + 2):
            qy, inside, j = y + 0.5 - off, False, n - 1
            for i in range(n):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if (yi > qy) != (yj > qy) and qx < (xj - xi) * (qy - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                m.set(x, y)
    return m


def body_mask(S):
    m = Mask()
    for x in range(TAIL_ROOT, NOSE + 1):
        a, b = prof(x)
        if a + b < 0.8:
            continue
        c = CY + S[x]
        for y in range(math.floor(c - a), math.ceil(c + b) + 1):
            if c - a <= y + 0.5 <= c + b:
                m.set(x, y)
    return m


def put(g, S, x, y, c):
    px(g, x, y + round(S[x]), c)


def tone(g, S, x, y, table):
    """Darken a pixel with the table entry for whatever colour is underneath."""
    yy = y + round(S[x]) + YO
    if 0 <= x < W and 0 <= yy < H:
        i = yy * W + x
        if g[i] in table:
            g[i] = table[g[i]]


def line(g, S, a, b, table):
    x0, y0 = a
    x1, y1 = b
    steps = max(1, math.ceil(2 * max(abs(x1 - x0), abs(y1 - y0))))
    for k in range(steps + 1):
        t = k / steps
        tone(g, S, round(x0 + (x1 - x0) * t - 0.5), round(y0 + (y1 - y0) * t - 0.5), table)


def outline_koi(g):
    """Outline pass: a soft rose line around the fins, the warm brown line elsewhere."""
    fin_tones = {FIN.hi, FIN.base, FIN.sh, FIN.deep, BARBEL}
    out = list(g)
    for y in range(H):
        for x in range(W):
            i = y * W + x
            if g[i] is not None:
                continue
            near = []
            if x > 0 and g[i - 1] is not None: near.append(g[i - 1])
            if x < W - 1 and g[i + 1] is not None: near.append(g[i + 1])
            if y > 0 and g[i - W] is not None: near.append(g[i - W])
            if y < H - 1 and g[i + W] is not None: near.append(g[i + W])
            if near:
                out[i] = FIN_OUT if all(c in fin_tones for c in near) else OUT
    return out


# ---------------------------------------------------------------- parts
def tail_fin(g, S, spread):
    e = 1.5 * spread            # splayed lobes when startled or showing off
    pts = [(21, 19.8), (15, 15), (9, 12.5 - e), (5, 14 - e), (8.5, 21.2), (8.5, 22.8), (5, 30 + e),
           (9, 31.5 + e), (15, 29), (21, 24.2)]
    paint(g, poly(S, pts), FIN, hi=1, sh=1)
    for tip in ((6, 15 - e), (7.5, 18.5 - e / 2), (9, 21.5), (9, 22.5), (7.5, 25.5 + e / 2), (6, 29 + e)):
        line(g, S, (18, 22), tip, RAY)


def dorsal_fin(g, S, ripple):
    r = ripple
    pts = [(53, top(53) + 1), (51, top(51) - 6.5), (45, top(45) - 5.5 + r), (38, top(38) - 4 - r),
           (31, top(31) - 2 + r), (29, top(29) + 1)]
    paint(g, poly(S, pts), FIN, hi=1, sh=1)
    for x, h in ((48, 4.5), (42, 4), (36, 3)):
        line(g, S, (x + 1, top(x + 1) + 0.5), (x, top(x) - h), RAY)


def pelvic_fin(g, S, sweep):
    k = sweep
    paint(g, poly(S, [(47, bottom(47) - 1), (42, bottom(42) - 1), (38 - k, bottom(40) + 3 + k),
                      (43 - k, bottom(43) + 2)]), FIN, hi=1, sh=1)


def anal_fin(g, S, sweep):
    k = sweep
    paint(g, poly(S, [(34, bottom(34) - 1), (29, bottom(29) - 1), (25 - k, bottom(27) + 3 + k),
                      (30 - k, bottom(30) + 2)]), FIN, hi=1, sh=1)


def pectoral_fin(g, S, sweep):
    """Near-side pectoral fin fanning back and down from behind the gill. sweep 0 = trailing
    back, 1 = mid stroke, 2 = swept forward, 3 = splayed out."""
    x0, y0, x1, y1 = ((44.5, 28, 48, 33.5), (45.5, 26, 49, 32.5), (47.5, 24.5, 51, 32), (43.5, 29.5, 49, 35))[sweep]
    root = (55, 23.5)
    m = poly(S, [root, (55, 27.5), (x1, y1), (x0, y0)])
    paint(g, m, FIN, hi=1, sh=1, edge=True, edge_if=lambda x, y: x < 55)
    line(g, S, root, ((x0 + x1) / 2, (y0 + y1) / 2 + 0.5), RAY)


def eye(g, S, blink, look, wide):
    ex, ey = 57, 17
    if blink:
        for i, j in ((0, 2), (1, 3), (2, 3), (3, 3), (4, 2)):
            put(g, S, ex + i, ey + j, OUT)
        return
    for i in range(5):
        for j in range(5):
            if (i, j) in ((0, 0), (4, 0), (0, 4), (4, 4)):
                continue
            put(g, S, ex + i, ey + j, OUT if i in (0, 4) or j in (0, 4) else IRIS)
    if wide:
        for i in (1, 2, 3):
            for j in (1, 2, 3):
                put(g, S, ex + i, ey + j, PUPIL)
        put(g, S, ex + 3, ey + 1, GLINT)
        put(g, S, ex + 1, ey + 3, IRIS_LIGHT)
        return
    p = 2 if look > 0 else 1
    q = 1 if look < 0 else 2
    for i in (p, p + 1):
        for j in (q, q + 1):
            put(g, S, ex + i, ey + j, PUPIL)
    put(g, S, ex + 3, ey + 1, GLINT)
    put(g, S, ex + 1, ey + 3, IRIS_LIGHT)


def mouth(g, S, open_):
    """The blunt koi mouth at the very front: a lip line, or a round gulp with pursed lips."""
    if open_ == 0:
        for x, y in ((66, 23), (65, 24), (64, 24)):
            put(g, S, x, y, MOUTH_LINE)
        return
    if open_ == 1:
        for x, y in ((66, 23), (66, 24), (65, 23), (65, 24)):
            put(g, S, x, y, MOUTH_IN)
        for x, y in ((66, 22), (67, 23), (67, 24), (66, 25)):
            put(g, S, x, y, LIP)
        return
    for x, y in ((66, 22), (66, 23), (66, 24), (66, 25), (65, 22), (65, 23), (65, 24), (65, 25), (64, 23), (64, 24)):
        put(g, S, x, y, MOUTH_IN)
    for x, y in ((66, 21), (67, 22), (67, 23), (67, 24), (67, 25), (66, 26), (65, 21)):
        put(g, S, x, y, LIP)


def barbels(g, S, sway):
    """A short barbel trailing from the corner of the mouth (the far pair is hidden)."""
    for x, y in ((65, 26), (65, 27), (64 - sway, 28)):
        put(g, S, x, y, BARBEL)


SCALES = ((43, 19), (49, 23), (37, 22), (31, 19), (45, 26), (35, 26), (27, 24), (40, 15), (30, 16))


def scales(g, S):
    for x, y in SCALES:
        for i, j in ((0, 0), (1, 1), (2, 0)):
            tone(g, S, x + i, y + j, GILL)
    for x, y in ((53, 15), (52, 17), (51, 19), (51, 21), (51, 23), (52, 25), (53, 27)):   # gill line
        tone(g, S, x, y, GILL)


def markings(g, S, body):
    hi_patch = ell(S, 58.5, 13.5, 8.5, 4.4)
    saddle = ell(S, 43, 16.5, 8, 7)
    saddle_low = ell(S, 39, 21, 4, 5.5)
    tail_patch = ell(S, 26.5, 20.5, 5, 4.4)
    for m in (hi_patch, saddle, saddle_low, tail_patch):
        patch(g, m, RED, WHITE, within=body)


def bubble(g, x, y, big):
    """Drawn after the outline: a light blue ring with a white catch."""
    if big:
        for i, j in ((1, 0), (2, 0), (0, 1), (3, 1), (0, 2), (3, 2), (1, 3), (2, 3)):
            px(g, x + i, y + j, BUBBLE)
        px(g, x + 1, y + 1, BUBBLE_HI)
    else:
        for i, j in ((0, 0), (1, 0), (0, 1), (1, 1)):
            px(g, x + i, y + j, BUBBLE)
        px(g, x, y, BUBBLE_HI)


def bubbles_after(g, mode, stage):
    """Bubbles rise from the mouth after the outline pass. Each mode loops cleanly:
    'stream' cycles three bubbles over six frames, 'puff' two over four, 'one' is a
    single bubble that has just left the lips."""
    if mode == "stream":
        for k in range(3):
            y = 21 - (8 * k + 4 * stage) % 24
            bubble(g, 66 if k == 1 else 67 + k, y, k == 1)
    elif mode == "puff":
        for k in range(2):
            y = 21 - (10 * k + 5 * stage) % 20
            bubble(g, 66 if k else 68, y, bool(k))
    elif mode == "one":
        bubble(g, 67, 21 - 4 * stage, stage > 0)


# ---------------------------------------------------------------- frame
@lru_cache(maxsize=None)
def frame(phase=0.0, amp=0.0, curve=0.0, tilt=0.0, flick=0.0, dorsal=0, pect=0, fins=0,
          blink=False, look=0, wide=False, open_=0, barb=0, spread=0, bub=None):
    g = new_grid()
    S = spine(phase, amp, curve, tilt, flick)
    tail_fin(g, S, spread)
    dorsal_fin(g, S, dorsal)
    pelvic_fin(g, S, fins)
    anal_fin(g, S, fins)
    body = body_mask(S)
    paint(g, body, WHITE, hi=2, sh=3)
    markings(g, S, body)
    scales(g, S)
    eye(g, S, blink, look, wide)
    mouth(g, S, open_)
    barbels(g, S, barb)
    pectoral_fin(g, S, pect)
    g = outline_koi(g)
    if bub is not None:
        bubbles_after(g, *bub)
    return to_image(g)


# ---------------------------------------------------------------- animations
def build_pet():
    idle = tuple(frame(phase=i / 16, amp=0.35, dorsal=(i // 4) % 2, pect=(i // 4) % 2, fins=(i // 8) % 2,
                       blink=i == 13, barb=(i // 6) % 2) for i in range(16))
    sit = tuple(frame(phase=i / 16, amp=0.18, dorsal=(i // 8) % 2, pect=0, open_=(1, 1, 2, 2, 2, 1, 1, 0)[(i // 2) % 8],
                      blink=i == 11) for i in range(16))
    look = tuple(frame(phase=i / 7, amp=0.25, tilt=t, look=d, barb=b, pect=1 if d else 0)
                 for i, (d, t, b) in enumerate(((0, 0, 0), (1, -1, 1), (1, -1.5, 1), (1, -1.5, 0),
                                                (0, -0.5, 0), (-1, 0.5, 1), (0, 0, 0))))
    walk = tuple(frame(phase=i / 6, amp=1.0, pect=(0, 1, 2, 2, 1, 0)[i], dorsal=(i // 3) % 2, fins=i % 2)
                 for i in range(6))
    dart = tuple(frame(phase=i / 4, amp=1.4, tilt=-1, pect=(2, 2, 1, 1)[i], open_=0, fins=1, dorsal=i % 2)
                 for i in range(4))
    wiggle = tuple(frame(phase=i / 4, amp=0.9, curve=(-1, 0, 1, 0)[i], pect=(3, 1, 3, 1)[i], open_=1,
                         dorsal=i % 2, fins=i % 2) for i in range(4))
    alert = tuple(frame(phase=i / 4, amp=0.9, curve=(-1, 0, 1, 0)[i], pect=(3, 1, 3, 1)[i], open_=1,
                        dorsal=i % 2, fins=i % 2, bub=("puff", i)) for i in range(4))
    bubbles = tuple(frame(phase=i / 6, amp=0.3, open_=(1, 2, 2, 1, 1, 2)[i], pect=(i // 3) % 2, bub=("stream", i))
                    for i in range(6))
    flourish = tuple(frame(phase=p, amp=a, flick=f, spread=s, pect=q, dorsal=d, fins=1)
                     for p, a, f, s, q, d in ((0.0, 0.4, 0, 0, 1, 0), (0.15, 0.9, -3, 1, 2, 1), (0.3, 1.3, -6, 1, 3, 1),
                                              (0.5, 1.3, 5, 1, 3, -1), (0.7, 0.9, 3, 1, 2, 0), (0.85, 0.4, 0, 0, 1, 0)))
    gulp = tuple(frame(phase=i / 4, amp=0.25, open_=(1, 2, 2, 1)[i], tilt=(-0.5, -1, -1, -0.5)[i],
                       bub=(None, None, ("one", 0), ("one", 1))[i], pect=(i // 2) % 2) for i in range(4))
    fall = (frame(phase=0.25, amp=0.6, curve=-3, tilt=1.5, flick=4, pect=3, fins=1, spread=1, wide=True, open_=2,
                  dorsal=1),)

    animations = {
        "idle": Animation(idle, 0.22),
        "sit": Animation(sit, 0.3),
        "look": Animation(look, 0.4),
        "walk": Animation(walk, 0.12),
        "alert": Animation(alert, 0.15),
        "fall": Animation(fall),
        "bubbles": Animation(bubbles, 0.2, 2.4, "Blow bubbles", 3),
        "flourish": Animation(flourish, 0.16, 2.0, "Tail flourish", 2),
        "dart": Animation(dart, 0.08, 1.2, "Quick dart", 1, cooldown=20, forward_speed=180),
        "gulp": Animation(gulp, 0.22, 2.6, "Gulp gulp", 2),
        "wiggle": Animation(wiggle, 0.14, 1.7, "Happy wiggle", 2),
    }
    return PetDefinition(
        id="koi", name="Koi", label="Koi Fish",
        description="A calm red-and-white koi that drifts around the desktop and blows the odd bubble.",
        animations=animations,
        personality=Personality(walk_speed=55, roam_chance=0.75, trick_chance=0.2, trick_gap=12, rest_min=3, rest_max=8),
        movement="swim",
    )
