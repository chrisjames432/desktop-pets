"""Pumpkin artwork and personality. No application or reminder dependencies.

Pumpkin is a chunky orange mackerel tabby: a big round barrel of a body with a sagging belly on
short sturdy legs, a thick ringed tail, and a noticeably small head wearing a permanent
unimpressed look (flat low brow, half-lidded amber eyes, a little frown on a cream muzzle).
She is grumpy on the outside and soft on the inside: her signature move is a slow blink that
lets a heart slip out.

The cat itself is drawn by the shared rig in feline.py; this module is only Pumpkin's spec
(colours, proportions, tabby markings, her heart), her animation set, and personality.

Markings, all painted with patch() so they keep the body shading:
    torso   six mackerel stripes dropping from the spine (alternating long / short), laid out
            with the rig's at(), so they follow the back in stand, bow, crouch and leap; the loaf
            uses the same stripes on a level spine; sitting, short ribs notch the domed back
    haunch  the torso's stripes carry on across the thigh; sitting, a classic-tabby swirl
    legs    darker bands across every near leg (bent and reaching limbs included)
    tail    rings every 5.5 px along the final tail path and a dark tip
    head    forehead "M", two stripes off each eye corner, cream muzzle and chin
    chest   cream bib (standing, sitting, leaping)
Local addition the rig does not offer: a 1-row cream chin painted under the small skull from
the head hook, so the mouth does not sit on the jaw outline at head_scale 0.85.
"""
from dataclasses import replace
import math
from .base import Animation, Personality, PetDefinition
from .feline import CatSpec, default_effects, frame, gait, standard_animations
from .pixelkit import W, YO, Mask, Ramp, paint, patch, path_after, px, rgb

GINGER = Ramp("#f9b765", "#ee9440", "#cf6f26", "#9a4c18")
FAR = Ramp("#cf6f26", "#cf6f26", "#b15b1e", "#8a4315")
STRIPE = Ramp("#d67126", "#b95519", "#964110", "#6e2e0a")
CREAM = Ramp("#fff3df", "#fbe3c4", "#e6c39c", "#b98f68")


def _point(pts, d):
    """Point and unit direction d px along a polyline."""
    for i in range(1, len(pts)):
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        n = math.hypot(x1 - x0, y1 - y0)
        if d <= n or i == len(pts) - 1:
            t = d / (n or 1)
            return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, (x1 - x0) / (n or 1), (y1 - y0) / (n or 1)
        d -= n


def _length(pts):
    return sum(math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts)))


def _rays(m, centre, rx, ry, angles, depth=0.5, r=1.0):
    """Stripes running in from the rim of an ellipse toward its centre."""
    cx, cy = centre
    for a in angles:
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        m.path([(cx + rx * c * 1.05, cy + ry * s * 1.05), (cx + rx * c * (1 - depth), cy + ry * s * (1 - depth))], r, r * 0.5)
    return m


_STATE = {}       # the torso's stripe mask, reused by the haunch drawn right after it so the stripes line up


def _mackerel(at):
    """Six stripes dropping from the spine, alternately long and short. at(a, b) is the rig's torso frame."""
    s = Mask()
    for n, a in enumerate((-15, -10, -5, 0, 5, 10)):
        s.path([at(a, -11), at(a - 1, -3), at(a - 2.5, 2.5)] if n % 2 else [at(a, -11), at(a - 1, -2)], 1.3, 0.6)
    return s


def _arc(m, centre, rx, ry, a0, a1, r):
    cx, cy = centre
    m.path([(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in range(a0, a1 + 1, 15)], r, r)
    return m


def _tabby(g, part):
    """The tabby markings, laid over the ginger coat tone for tone so they keep its shading."""
    m, name, pose = part.mask, part.name, part.pose
    s = Mask()
    if name == "tail":
        pts, total = part.pts, _length(part.pts)
        d = 5.0
        while d < total * 0.8:
            x, y, ux, uy = _point(pts, d)
            r = part.r0 + (part.r1 - part.r0) * d / total + 0.6
            s.path([(x - uy * r, y + ux * r), (x + uy * r, y - ux * r)], 0.95, 0.95)
            d += 5.5
        tip = path_after(pts, 0.86)
        s.path(tip, part.r1 + 0.6, part.r1 + 0.6)
    elif name == "torso":
        if pose == "sit":
            (hx, hy), (cx, cy) = part.R, part.C
            k = part.spec.girth
            _rays(s, (hx, hy), 11 * k + part.spec.belly, 9 * k, (200, 224, 248, 272), 0.33, 1.3)
            patch(g, s, STRIPE, part.ramp, m)
            patch(g, Mask().ellipse(cx + 8, cy + 1, 3.5, 7), CREAM, part.ramp, m)
            return
        elif pose == "loaf":
            x, y = part.M
            s = _mackerel(lambda a, b: (x + a + 1, y + b))
        else:
            s = _STATE["stripes"] = _mackerel(part.at)
            if pose in ("stand", "leap"):       # bowing or crouching, the bib is tucked under her chin
                patch(g, s, STRIPE, part.ramp, m)
                cx, cy = part.C
                patch(g, Mask().ellipse(cx + 8, cy, 3.5, 6), CREAM, part.ramp, m)
                return
    elif name == "haunch":
        if pose == "sit":
            cx, cy = (m.x0 + m.x1 + 1) / 2, (m.y0 + m.y1 + 1) / 2 - YO
            rx, ry = (m.x1 - m.x0 + 1) / 2, (m.y1 - m.y0 + 1) / 2
            _arc(s, (cx, cy), rx * 0.66, ry * 0.66, 180, 330, 1.0)
            _arc(s, (cx, cy), rx * 0.25, ry * 0.25, 190, 310, 1.0)
        else:
            s = _STATE["stripes"]
    elif name == "leg":
        if part.ramp is not GINGER:
            return
        if m.y1 - m.y0 >= m.x1 - m.x0:
            for y in range(m.y1 - YO - 1, m.y0 - YO, -3):
                for x in range(m.x0, m.x1 + 1):
                    s.set(x, y)
        else:
            for x in range(m.x1 - 2, m.x0, -4):
                for y in range(m.y0 - YO, m.y1 - YO + 1):
                    s.set(x, y); s.set(x + 1, y)
    elif name == "head":
        cx, cy = part.cx, part.cy
        patch(g, Mask().ellipse(cx + 1.5, cy + 5.6, 4.2, 2.6), CREAM, part.ramp, m)
        paint(g, Mask().ellipse(cx + 1.5, cy + 6.4, 3.3, 1.6), CREAM, sh=1)      # a chin under the small skull
        for x, y in ((-2, -7), (-1, -6), (1, -7), (1, -6), (1, -5), (4, -7), (3, -6),
                     (-9, 1), (-8, 1), (-9, 3), (-8, 3), (10, 1), (9, 1), (10, 3), (9, 3)):
            s.set(cx + x, cy + y)
    else:
        return
    patch(g, s, STRIPE, part.ramp, m)


HEART = ("-XX-XX-", "XoXXXXX", "XXXXXXX", "-XXXXX-", "--XXX--", "---X---")
HEART_HI = rgb("#ffb3c1")


def _effects(g, fx, info):
    """Her one big tell: a proper heart, larger than the rig's, drifting up from the slow blink."""
    kind, step = fx
    if kind != "heart":
        return default_effects(g, fx, info)
    x0 = min(info.hx + math.ceil(12 * info.spec.head_scale) + 1, W - 9)
    y0 = max(info.hy - 10 - 2 * step, -1)
    for j, row in enumerate(HEART):
        for i, c in enumerate(row):
            if c != "-":
                px(g, x0 + i, y0 + j, HEART_HI if c == "o" else info.spec.heart)


TAIL_SIT = (
    ((14, 40), (8, 35), (6, 28), (6.5, 21), (10, 17)),
    ((14, 40), (8, 35), (5.5, 28), (5.5, 21), (8, 16.5)),
)

SPEC = CatSpec("pumpkin", coat=GINGER, far=FAR, paws=CREAM, marking_ramps=(STRIPE, CREAM), marks=_tabby, effects=_effects,
               iris=(rgb("#ffd874"), rgb("#f0aa2e"), rgb("#b8741a")),
               whisker=rgb("#cdb08a"), blush=None,
               rest_face="grumpy", mouth="frown",
               faces={"grumpy": ("lidded", "frown", True), "soft": ("lidded", "soft", False), "blink": ("closed", "soft", False),
                      "happy": ("squint", "soft", False), "gmeow": ("lidded", "open", True), "huff": ("lidded", "ajar", True),
                      "startled": ("wide", "flat", False)},
               head_scale=0.85, girth=1.3, belly=3, body_len=-2, leg_len=-2, leg_w=4, tail_r=1.6, tail_len=0.95,
               tail_sit=TAIL_SIT)


def build_pet():
    f = lambda *a, **k: frame(SPEC, *a, **k)
    anims = standard_animations(SPEC)
    for gone in ("wiggle", "pounce", "swat", "groom"):
        del anims[gone]
    anims["walk"] = replace(anims["walk"], frame_seconds=0.16)
    anims["alert"] = Animation(tuple(f("sit", dy=i % 2, tail_i=i % 2, face=face, fx=fx) for i, (face, fx) in enumerate(
        (("gmeow", ("meow", 0)), ("gmeow", ("meow", 1)), ("gmeow", ("meow", 2)), ("grumpy", None)))), 0.3)
    anims["fall"] = Animation((f(tail_i=1, face="startled", legs=((-3, 0), (3, 0), (-2, 0), (4, 0))),))
    love = (("grumpy", None), ("soft", None), ("blink", 0), ("blink", 1), ("blink", 2), ("happy", 3), ("happy", 4), ("soft", None))
    anims["love"] = Animation(tuple(f("sit", dy=1 if 2 <= i <= 5 else 0, tail_i=(i // 3) % 2, face=face,
                                      fx=None if h is None else ("heart", h)) for i, (face, h) in enumerate(love)),
                              0.45, 3.5, "Secretly loves you", 5, cooldown=20)
    grumble = (("grumpy", None, 0), ("huff", 0, 1), ("gmeow", 1, 0), ("huff", 2, 1), ("grumpy", None, 0), ("grumpy", None, 1))
    anims["grumble"] = Animation(tuple(f("sit", tail_i=t, face=face, ear=1 if n is not None else 0,
                                         fx=None if n is None else ("meow", n)) for face, n, t in grumble),
                                 0.22, 2.6, "Grumpy grumble", 3)
    flop = ([f(dy=1), f("crouch", wig=0), f("loaf", face="startled"), f("loaf", face="grumpy")]
            + [f("loaf", face="happy", dy=(i // 2) % 2) for i in range(6)])
    anims["flop"] = Animation(tuple(flop), 0.4, 3.9, "Dramatic flop", 3, cooldown=25)
    anims["stretch"] = replace(anims["stretch"], label="Lazy stretch", weight=2)
    anims["knead"] = replace(anims["knead"], weight=3)
    anims["purr"] = Animation(tuple(f("sit", dy=(i // 2) % 2, tail_i=i % 2, face="happy") for i in range(4)),
                              0.3, 3.6, "Rumbly purr", 3)
    anims["sleep"] = replace(anims["sleep"], duration=11, label="Long nap", weight=5)
    anims["hop"] = Animation(tuple(f(tail_i=i % 2, face="startled" if i in (1, 2) else "grumpy",
                                     legs=gait((0, 3), (0, 3)) if i in (1, 2) else gait(), dy=0 if i in (1, 2) else 1)
                                   for i in range(4)), 0.18, 2.8, "Reluctant hop", 1, cooldown=25, hop_height=11)
    return PetDefinition("orange_tabby", "Pumpkin", "Orange Tabby", "A chunky, grumpy tabby with a secretly big heart.",
                         anims, Personality(walk_speed=45, roam_chance=0.4, trick_chance=0.25, trick_gap=14, rest_min=4, rest_max=10))
