"""Shared pixel-art kit for the 72 x 48 art standard. Pure Pillow; no Tk, files, or threads.

Every pet in the new style draws on a 72 x 48 logical grid that is enlarged 2x to the
144 x 96 canvas. Pets build masks from ellipses, polygons, and tapered paths, paint them
with a three-tone ramp, and finish with a warm brown outline. Alpha is always 0 or 255.

Coordinates passed to these helpers are "design" rows: design row 0 is grid row YO, which
leaves room for the outline above ears. GROUND is the design row just below the feet, so
feet rest on design row GROUND - 1 and their outline lands on the last row of the frame.
"""
import math
from PIL import Image

W, H, SCALE = 72, 48, 2
YO = 2
GROUND = 45
OUT = (0x3b, 0x24, 0x15)     # warm brown outline, softer than black


def rgb(h):
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))


class Ramp:
    """Highlight, base, shadow, and a deep tone for interior lines."""
    __slots__ = ("hi", "base", "sh", "deep")

    def __init__(self, hi, base, sh, deep):
        self.hi, self.base, self.sh, self.deep = rgb(hi), rgb(base), rgb(sh), rgb(deep)


def new_grid():
    return [None] * (W * H)


class Mask:
    __slots__ = ("d", "x0", "y0", "x1", "y1")

    def __init__(self):
        self.d = bytearray(W * H)
        self.x0, self.y0, self.x1, self.y1 = W, H, -1, -1

    def set(self, x, y):
        y += YO
        if 0 <= x < W and 0 <= y < H:
            self.d[y * W + x] = 1
            if x < self.x0: self.x0 = x
            if x > self.x1: self.x1 = x
            if y < self.y0: self.y0 = y
            if y > self.y1: self.y1 = y

    def ellipse(self, cx, cy, rx, ry):
        for y in range(math.floor(cy - ry) - 1, math.ceil(cy + ry) + 2):
            t = 1 - ((y + 0.5 - cy) / ry) ** 2
            if t < 0:
                continue
            half = rx * math.sqrt(t)
            for x in range(math.ceil(cx - half - 0.5), math.floor(cx + half - 0.5) + 1):
                self.set(x, y)
        return self

    def poly(self, pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        n = len(pts)
        for y in range(math.floor(min(ys)), math.ceil(max(ys)) + 1):
            qy = y + 0.5
            for x in range(math.floor(min(xs)), math.ceil(max(xs)) + 1):
                qx, inside, j = x + 0.5, False, n - 1
                for i in range(n):
                    xi, yi = pts[i]
                    xj, yj = pts[j]
                    if (yi > qy) != (yj > qy) and qx < (xj - xi) * (qy - yi) / (yj - yi) + xi:
                        inside = not inside
                    j = i
                if inside:
                    self.set(x, y)
        return self

    def path(self, pts, r0, r1):
        """A tapered stroke along a polyline; used for the tail and resting legs."""
        lens = [math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts))]
        total, acc = sum(lens) or 1, 0.0
        for i in range(1, len(pts)):
            steps = max(1, math.ceil(lens[i - 1] * 2))
            for s in range(steps + 1):
                t = s / steps
                x = pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t
                y = pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t
                r = r0 + (r1 - r0) * ((acc + lens[i - 1] * t) / total)
                self.ellipse(x, y, r, r)
            acc += lens[i - 1]
        return self


def px(g, x, y, c):
    y += YO
    if 0 <= x < W and 0 <= y < H:
        g[y * W + x] = c


def edge_pass(g, m, color, edge_if):
    """Dark interior line where a new part overlaps what is already drawn."""
    d = m.d
    for y in range(max(0, m.y0 - 1), min(H - 1, m.y1 + 1) + 1):
        for x in range(max(0, m.x0 - 1), min(W - 1, m.x1 + 1) + 1):
            i = y * W + x
            if d[i] or g[i] is None:
                continue
            if ((x > 0 and d[i - 1]) or (x < W - 1 and d[i + 1]) or
                    (y > 0 and d[i - W]) or (y < H - 1 and d[i + W])):
                if edge_if is None or edge_if(x, y - YO):
                    g[i] = color


def paint(g, m, ramp, hi=0, sh=0, clip=False, edge=False, edge_color=None, edge_if=None):
    """Fill a mask with banded shading: a light band along the top, shadow along the bottom."""
    if m.x1 < 0:
        return
    d = m.d
    if clip:
        for i in range(W * H):
            if d[i] and g[i] is None:
                d[i] = 0
    if edge:
        edge_pass(g, m, edge_color or ramp.deep, edge_if)
    for x in range(m.x0, m.x1 + 1):
        for y in range(m.y0, m.y1 + 1):
            i = y * W + x
            if not d[i]:
                continue
            t = 0
            while t < hi and y - 1 - t >= 0 and d[(y - 1 - t) * W + x]:
                t += 1
            b = 0
            while b < sh and y + 1 + b < H and d[(y + 1 + b) * W + x]:
                b += 1
            g[i] = ramp.hi if t < hi else ramp.sh if b < sh else ramp.base


def sphere(g, cx, cy, rx, ry, ramp, edge=False, edge_color=None):
    """A rounded form lit from the top front."""
    m = Mask().ellipse(cx, cy, rx, ry)
    if edge:
        edge_pass(g, m, edge_color or ramp.deep, None)
    for y in range(m.y0, m.y1 + 1):
        for x in range(m.x0, m.x1 + 1):
            i = y * W + x
            if not m.d[i]:
                continue
            nx, ny = (x + 0.5 - cx) / rx, (y - YO + 0.5 - cy) / ry
            v = -ny * 0.85 + nx * 0.3
            g[i] = ramp.hi if v > 0.5 else ramp.sh if v < -0.5 else ramp.base


def outline(g, color=OUT):
    """Wrap every shape in a one-pixel outline."""
    out = list(g)
    for y in range(H):
        for x in range(W):
            i = y * W + x
            if g[i] is not None:
                continue
            if ((x > 0 and g[i - 1] is not None) or (x < W - 1 and g[i + 1] is not None) or
                    (y > 0 and g[i - W] is not None) or (y < H - 1 and g[i + W] is not None)):
                out[i] = color
    return out


def to_image(g):
    """Grid of RGB tuples (None is transparent) to the 144 x 96 RGBA frame."""
    im = Image.new("RGBA", (W, H))
    im.putdata([(0, 0, 0, 0) if c is None else c + (255,) for c in g])
    return im.resize((W * SCALE, H * SCALE), Image.Resampling.NEAREST)
