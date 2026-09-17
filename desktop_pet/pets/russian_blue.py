"""Anya artwork and personality. No application or reminder dependencies.

Anya is a Russian Blue: a solid, plush blue-grey coat with a silvery sheen, vivid green
eyes, big wide-set ears lined in mauve, a fine-boned body on long legs, a long tapering
tail, mauve nose leather and paw beans, and the breed's faint upturned "Russian smile".
She is serious (a composed, level gaze and a judging stare), silly (zoomies, a play
crouch, a tongue blep), and very talkative (she meows at everything, reminders included).

The cat itself is drawn by the shared rig in feline.py; this module is only Anya's spec
(colours and proportions), her curated animation set, and her personality.
"""
from dataclasses import replace
from .base import Animation, Personality, PetDefinition
from .feline import CatSpec, default_effects, draw_ticks, draw_z, frame, gait, standard_animations
from .pixelkit import W, Ramp, rgb


BLUE = Ramp("#c9d2de", "#8995a8", "#616d81", "#3d4656")      # silver sheen, blue-grey, deep slate
FAR = Ramp("#66728a", "#66728a", "#515c70", "#3d4656")       # far-side limbs, in shadow
MAUVE = Ramp("#e0b3c6", "#cb95ad", "#a8748f", "#80566c")     # inner ear
PLUSH = Ramp("#c9d2de", "#a7b2c4", "#616d81", "#3d4656")     # base = the soft band under the silver highlight
SHEEN_ROWS = {"torso": 2, "head": 2, "haunch": 2, "tail": 1}


def _sheen(g, part):
    """The breed's silvery sheen: a soft half-tone band under the top highlight of each big form."""
    rows = SHEEN_ROWS.get(part.name, 0)
    if not rows:
        return
    m, d = part.mask, part.mask.d
    for x in range(m.x0, m.x1 + 1):
        for y in range(m.y0, m.y1 + 1):
            i = y * W + x
            if not d[i] or g[i] != BLUE.base:
                continue
            for t in range(1, rows + 1):        # a highlight (or the form's top edge) within `rows` px above
                j = i - t * W
                if j < 0 or not d[j] or g[j] == BLUE.hi:
                    if part.name != "haunch" or t == 1:
                        g[i] = PLUSH.base
                    break
                if g[j] != BLUE.base and g[j] != PLUSH.base:
                    break


SOUND = rgb("#7d90b0")        # meow ticks and sleep Z's: readable on light and dark desktops


def _effects(g, fx, info):
    """Meow ticks in a tone that shows on any wallpaper, and sleep Z's set clear of her big ears."""
    kind, step = fx
    if kind == "meow":
        draw_ticks(g, min(info.hx + 16, W - 5), info.hy + 1, SOUND, 1 + step % 3)
    elif kind == "zzz":
        draw_z(g, min(info.hx + 15, W - 8), max(info.hy - 18 - step, -1), 3, SOUND)
        if step >= 2:
            draw_z(g, min(info.hx + 17, W - 6), max(info.hy - 26 - (step - 2), -1), 4, SOUND)
    else:
        default_effects(g, fx, info)


ANYA = CatSpec(
    "anya", coat=BLUE, far=FAR, ear_in=MAUVE, marking_ramps=(PLUSH,), marks=_sheen, effects=_effects,
    iris=(rgb("#b9f58a"), rgb("#55d663"), rgb("#1f9448")), rim=rgb("#141821"),
    lids=(rgb("#232936"), rgb("#232936")), nose=(rgb("#c08aa4"), rgb("#8c6079")),
    line=rgb("#2c3342"), mouth_in=rgb("#4a2433"), tongue=rgb("#ee8fa6"), blush=None,
    bean=rgb("#c398ae"), whisker=rgb("#aab3c1"), zzz=SOUND, outline=rgb("#232936"),
    rest_face="serious", mouth="soft",
    faces={"serious": ("level", None, False), "judge": ("lidded", None, False), "yowl": ("wide", "open", False)},
    head_scale=0.92, head_w=0.95, muzzle=0.8, ear_h=1.0, ear_w=1.3, ear_spread=2, ear_lean=1,
    girth=0.9, body_len=3, leg_len=2, leg_w=3, tail_r=1.0, tail_len=1.12,
)

# Gathered strides of the zoomies gallop (near hind, near fore, far hind, far fore); the reaching
# strides in between are the rig's airborne leap, so she bounds along flat out.
GATHER = (((4, 0), (-3, 1), (5, 1), (-4, 0)), ((4, 1), (-3, 0), (5, 0), (-4, 1)))


def build_pet():
    f = lambda *a, **k: frame(ANYA, *a, **k)
    anims = standard_animations(ANYA)
    for gone in ("swat", "groom", "purr", "knead"):
        del anims[gone]

    def slow_blink(i):          # composed, deliberate: lids lower, close, lift
        return {13: {"face": "judge"}, 14: {"blink": True}, 15: {"face": "judge"}}.get(i, {})

    # core states, with standard frame counts and timings
    anims["idle"] = replace(anims["idle"], frames=tuple(
        f(dy=(i // 4) % 2, tail_i=(i // 2) % 2, **slow_blink(i)) for i in range(16)))
    anims["sit"] = replace(anims["sit"], frames=tuple(
        f("sit", dy=(i // 4) % 2, tail_i=(i // 2) % 2, **slow_blink(i)) for i in range(16)))
    anims["alert"] = Animation(tuple(                      # a reminder: she sits and tells you about it
        f("sit", dy=i % 2, tail_i=i % 2, face=face, fx=("meow", i))
        for i, face in enumerate(("meow", "ajar", "meow", "ajar"))), 0.2)
    anims["fall"] = replace(anims["fall"], frames=(f(tail_i=1, face="yowl", legs=((-3, 0), (3, 0), (-2, 0), (4, 0))),))

    # talkative
    talk = (("meow", 0), ("ajar", 1), ("meow", 2), ("ajar", 0), ("meow", 1), (None, None), ("meow", 2), (None, None))
    anims["chatter"] = Animation(tuple(
        f("sit", tail_i=(i // 2) % 2, dy=1 if face is None else 0, face=face, fx=None if face is None else ("meow", n))
        for i, (face, n) in enumerate(talk)), 0.16, 2.6, "Chatty meows", 5, cooldown=8)
    # serious
    stare = (None, None, None, None, "judge", "closed", "closed", "judge")
    anims["judge"] = Animation(tuple(f("sit", tail_i=1 if i == 2 else 0, face=face) for i, face in enumerate(stare)),
                               0.45, 3.6, "Judge silently", 3, cooldown=20)
    # silly
    anims["blep"] = Animation(tuple(
        f("sit", tongue=True, tail_i=t, tilt=tilt, blink=blink)
        for t, tilt, blink in ((0, 0, False), (1, 0, False), (0, 1, False), (1, 1, False), (0, 1, True), (1, 0, False))),
        0.4, 3.6, "Blep", 3, cooldown=20)
    anims["zoomies"] = Animation((
        f(dy=1, tail_i=1, face="play", ear=1, legs=GATHER[0]), f("leap", phase=0, face="play", ear=1),
        f(dy=1, tail_i=2, face="play", ear=1, legs=GATHER[1]), f("leap", phase=0, face=("wide", "ajar"), ear=1)),
        0.09, 1.6, "Zoomies!", 2, cooldown=25, forward_speed=140)
    anims["wiggle"] = replace(anims["wiggle"], weight=2)
    anims["pounce"] = replace(anims["pounce"], label=None)          # only ever follows the wiggle
    anims["hop"] = replace(anims["hop"], label="Silly hop", hop_height=16, frames=tuple(
        f(tail_i=i % 2, face="play" if i in (1, 2) else None, legs=gait((0, 4), (0, 4)) if i in (1, 2) else gait(),
          dy=0 if i in (1, 2) else 1) for i in range(4)))
    anims["stretch"] = replace(anims["stretch"], label="Long stretch")
    anims["sleep"] = replace(anims["sleep"], label="Cat nap", frames=tuple(
        f("loaf", fx=("zzz", i), dy=(i // 2) % 2) for i in range(4)))
    return PetDefinition("russian_blue", "Anya", "Russian Blue",
                         "A serious Russian Blue who is secretly silly and very talkative.", anims,
                         Personality(walk_speed=70, roam_chance=0.6, trick_chance=0.3, trick_gap=10, rest_min=3, rest_max=7))
