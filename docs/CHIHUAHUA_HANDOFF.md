# Andrew the chihuahua: pet handoff

From: the pet design agent. To: the core agent. Status: registered and shipped in v2.0.0. Drawing helpers now live in `pixelkit.py`; Patches and Pip were redrawn in the same style with feet flush to the frame bottom.

## Delivered

- `desktop_pet/pets/chihuahua.py` (new file, code-drawn, no PNG assets to bundle)
- `docs/previews/chihuahua-preview.png`, made with `tools/preview_pet.py`
- No shared files, registry, launchers, or user data were edited.

## Registration lines

```python
from .chihuahua import build_pet as build_chihuahua
# Add to FACTORIES:
"chihuahua": build_chihuahua,
```

## Definition

- id `chihuahua`, name `Andrew`, label `Chihuahua`
- Art: 72 x 48 logical grid at 2x, three-tone shading, warm brown outline, hard alpha, no magenta, faces right.
- `build_pet()` is pure Pillow. It builds in about 0.3 seconds. Frames are cached by pose, so repeated frames share one image and are never mutated.

| ID | Frames | frame_seconds | duration | Label | weight | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| idle | 16 | 0.22 | 3.0 | | | breathing, tail wag, blink on frame 14 |
| sit | 16 | 0.25 | 3.0 | | | blink on frame 13 |
| look | 7 | 0.4 | 3.0 | | | glances back, then ahead; the lazy eye only half follows |
| walk | 4 | 0.13 | 3.0 | | | diagonal gait with lifted paws |
| alert | 4 | 0.14 | 3.0 | | | front-paw tippy taps, open mouth |
| fall | 1 | 0.2 | 3.0 | | | legs splayed, ears down |
| tippy_taps | 4 | 0.14 | 2.4 | Tippy taps | 3 | same frames as alert |
| bark | 4 | 0.16 | 1.9 | Little bark | 2 | silent; head lifts, mouth opens |
| zoomies | 4 | 0.09 | 1.8 | Zoomies | 1 | forward_speed 150, cooldown 25 |
| hop | 4 | 0.18 | 2.8 | Happy hop | 1 | hop_height 16; same frame count and timing as the other pets' hop |
| sleep | 4 | 0.8 | 9 | Curl up for a nap | 2 | cooldown 30; same timing as the other pets' sleep |

Personality: `walk_speed=60, roam_chance=0.55, trick_chance=0.25, trick_gap=12, rest_min=3, rest_max=8`. Calm starting values, to be tuned after watching him on the desktop.

## Validation

- `build_pet().validate()` passes.
- Walk and every labeled action have more than one distinct frame.
- `PetBehavior` plays every state without an index error.
- `tools/preview_pet.py` builds his sheet without registration or Tk.
- `python -m unittest discover -s tests`: 42 pass, 1 fails. The failure is the known Patches `groom` identical-frames issue, which is scheduled for the Patches redraw. It is unrelated to this module.

## Things to know

- **Feet sit flush on the bottom row of the frame.** Patches and Pip currently stop 4 pixels above the bottom. On the desktop Andrew will stand 4 pixels lower than they do, touching the floor line. The redrawn Patches and Pip will be flush too, so this evens out. If you would rather keep the 4 pixel gap as the standard, tell me and I will adjust all three.
- The sitting pose uses the full frame height. The outline above the ear is on the top row and is not clipped.
- `alert` and `tippy_taps` share one frame tuple on purpose.

## Limitations

- Not yet seen running in the real app. Switching, walking, Stay, dragging, taskbar crossings, menu actions, and a reminder interruption still need the joint check from the creation doc.
- `fall` is a single frame.
- The hop is mostly carried by the window movement. The drawn change is a leg tuck and ear flop.
- Turning is a mirror flip, so the lazy eye swaps sides when he faces left. This is the same trade-off the other pets make.

## Next from the pet agent

Pip redraw, then Patches redraw, in the same style, keeping every existing ID, label, and timing. The Patches redraw will give `groom` distinct frames.

## Core integration reply

- Reviewed the module and contact sheet; `build_pet().validate()` passes.
- Registered `chihuahua` in the explicit factory catalog. No species branches or asset-build changes were needed.
- Feet flush with the final canvas bottom are correct. Keep that baseline for the redraws; the shared engine already reserves the full 96-pixel canvas above the taskbar.
- The common integration suite exercises all registered pets for switching, animation rendering, Stay, drag/drop, taskbar crossings, and API actions. These are automated hidden-Tk checks; a live visual check by Chris remains useful.
- The core agent has not modified this pet module and will continue leaving cat/penguin artwork files to the pet agent.
