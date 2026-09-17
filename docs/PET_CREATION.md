# Creating and updating Desktop Pets

Contract version: 1. The executable's main purpose is reliable reminders. Pets supply art and personality; the shared app owns reminders, windows, movement, monitor/taskbar handling, storage, and the API.

## Instructions to give another AI agent

> Work in `C:\Users\Chris\Desktop\desktop-pets`. Read `docs/PET_CREATION.md` and `desktop_pet/pets/base.py` first. Build or improve only the requested pet. Implement `build_pet() -> PetDefinition` in `desktop_pet/pets/<pet_id>.py`, following the existing cat and penguin modules. Supply transparent animation frames and personality settings. Use the shared animation/movement contract; do not create a separate app, timer, API, storage system, or reminder handler. Run the pet validation and tests below. Deliver the module, a contact sheet, and a short handoff describing animation IDs, personality, and registration. During the core refactor, do not edit shared files or `registry.py`; provide the two registration lines for the integrating agent. Preserve all existing work and personal reminders.

## Ownership while agents work in parallel

- The core agent owns `app.py`, `ui.py`, `api.py`, `reminders.py`, `storage.py`, `behavior.py`, `sprites.py`, `platform_windows.py`, `paths.py`, `pets/base.py`, and `pets/registry.py` under `desktop_pet/`, plus launchers/build scripts.
- A pet agent owns its specific `desktop_pet/pets/<pet_id>.py` and any uniquely named assets or tests it adds.
- Updating Patches means editing `desktop_pet/pets/cat.py`; updating Pip means editing `desktop_pet/pets/penguin.py`.
- Do not edit the root `cat.py` or `penguin.py`: these are launchers, not pet implementations.
- Coordinate before two agents edit the same pet. Make no changes to `reminders.json`, `settings.json`, or files in a user's app-data directory.
- New core capabilities require a proposal in the handoff. Do not add species-name branches to shared code.

## Module contract

Each pet module exports `build_pet()`. It returns `PetDefinition` from `desktop_pet.pets.base`.

| Field | Meaning |
| --- | --- |
| `id` | Stable lowercase snake_case ID, such as `red_panda`; never rename an existing ID casually |
| `name` | Character name, such as Patches |
| `label` | Species/display label, such as Calico Cat |
| `description` | One short sentence for the chooser |
| `animations` | Dictionary mapping state IDs to `Animation` objects |
| `personality` | `Personality` values used by the shared behavior engine |

`build_pet()` must work without creating Tk or any windows. It must not read user settings, access the network, start threads, or change files. Generate Pillow frames in memory or load bundled artwork relative to `__file__`.

## Required animations

Every pet supplies **idle, sit, look, walk, alert, fall**. These names are reserved shared states. Optional tricks can have descriptive IDs such as `preen`, `knead`, or `tail_chase`.

| Animation field | Default | Behavior |
| --- | --- | --- |
| `frames` | Required | Nonempty tuple of Pillow RGBA images |
| `frame_seconds` | 0.2 | Time for each frame; the sequence loops |
| `duration` | 3.0 | Typical time in this state before the engine chooses another |
| `label` | None | A string exposes the action in the menu and API |
| `weight` | 0 | Positive relative weight enables spontaneous selection |
| `cooldown` | 15.0 | Minimum seconds between spontaneous uses of this action |
| `forward_speed` | 0 | Positive pixels/second in the facing direction; respects Stay and monitor surfaces |
| `hop_height` | 0 | Vertical lift in pixels; handled by moving the whole window |
| `next_state` | None | Optional follow-up, e.g. wiggle followed by pounce |

Manual actions may bypass spontaneous cooldowns. Dragging and reminder alerts take priority over autonomous actions. Never play a sound or create a speech bubble inside an animation renderer.

## Artwork requirements

- A new cat breed is a small module on the reusable rig in `desktop_pet/pets/feline.py`: a `CatSpec` (coat ramps, proportions, faces), an optional markings hook, and a curated trick list. Read the rig's module docstring, then copy `cat.py`, `russian_blue.py`, or `orange_tabby.py`.
- New-style pets draw with the shared kit in `desktop_pet/pets/pixelkit.py` (masks, three-tone ramps, outline, `to_image`). Use `chihuahua.py` as the reference module.
- Grounded feet rest on the last art row so their outline lands on the bottom pixel row of the frame (`frame.getbbox()[3] == 96`). All pets share this floor line.
- Version 1 canvas is **144 x 96 pixels for every frame**. Keep grounded feet near the bottom and the body in the same anchor position across frames.
- The pixel style uses a **72 x 48 logical grid enlarged 2x** with `Image.Resampling.NEAREST`. Pets use three-tone shading (highlight, base, shadow) and a warm dark-brown outline. Older pets drawn on a 36 x 24 grid at 4x remain valid until they are redrawn. Shared code must depend only on the final 144 x 96 frame, never on the logical grid.
- Use mode `RGBA`, with alpha values only 0 or 255. Smooth translucent outlines produce halos with Windows color-key transparency.
- Opaque magenta `#ff00ff` is reserved for window transparency; do not use it in the pet.
- Draw the canonical pet facing right. The shared renderer mirrors it when facing left; face-on artwork is also supported.
- Keep ears, tails, paws, and effects inside the canvas. Use `hop_height` for physical jumps rather than drawing the pet partly outside its frame.
- Idle should include subtle breathing/blinks. Walking should have visible foot changes. Tricks should have readable preparation/action/recovery poses.
- Reuse frames when useful, but do not mutate an image after adding it to a definition.
- For artwork-only updates, preserve animation IDs, labels, and metadata. Increasing frame count while keeping `frame_seconds` changes the loop length; keep the original frame count for timing-sensitive motion/chains, or explicitly flag that tradeoff in the handoff. `hop_height` motion currently follows the animation's full loop duration.
- Prefer code-drawn Pillow artwork for current pets. If adding PNG assets, keep them under `desktop_pet/pets/assets/<pet_id>/` and mention them in the handoff so the EXE build can bundle them.

## Personality

`Personality` defaults: `walk_speed=65`, `roam_chance=0.65`, `trick_chance=0.25`, `trick_gap=12`, `rest_min=3`, `rest_max=7`.

Probabilities range from 0 to 1. Times are seconds; speed is pixels/second. `trick_gap` spaces out all spontaneous tricks. Individual animation cooldowns prevent repetition. Start with calm behavior and distinct preferences, then tune after watching it for several minutes. Personality never changes reminder delivery or API semantics.

## Minimal construction example

```python
from desktop_pet.pets.base import Animation, Personality, PetDefinition

def build_pet():
    # Your own draw_frame() returns an RGBA image sized 144 x 96.
    animations = {
        state: Animation(tuple(draw_frame(state, i) for i in range(4)))
        for state in ("idle", "sit", "look", "walk", "alert", "fall")
    }
    animations["wave"] = Animation(
        tuple(draw_frame("wave", i) for i in range(6)),
        frame_seconds=0.15, duration=2.7,
        label="Friendly wave", weight=1, cooldown=25,
    )
    return PetDefinition(
        id="your_pet", name="Your Name", label="Your Species",
        description="One short character description.",
        animations=animations,
        personality=Personality(walk_speed=55, trick_chance=0.2),
    )
```

## Registration

The integrating agent adds an explicit import and factory entry to `desktop_pet/pets/registry.py`:

```python
from .your_pet import build_pet as build_your_pet
# Add to FACTORIES:
"your_pet": build_your_pet,
```

The chooser, menus, API action list, animation renderer, and behavior engine use the definition automatically. Explicit imports keep PyInstaller builds predictable. During simultaneous work, put these lines in the handoff instead of editing the registry.

## Validation and handoff checklist

1. Validate without opening the desktop app:
   `python -c "from desktop_pet.pets.your_pet import build_pet; build_pet().validate(); print('OK')"`
2. Generate a contact sheet:
   `python tools/preview_pet.py your_pet --output your_pet-preview.png`
   This imports the module directly, so registration is not required.
3. Inspect every row for clipping, stray pixels, inconsistent scale, and grounded foot alignment. Preview both facing directions.
4. Run `python -m unittest discover -s tests -v` after integration.
5. With the integrating agent, verify switching, walking, Stay, dragging, taskbar crossings, all menu actions, and a reminder interruption.
6. Deliver the pet module/assets, preview, test results, animation IDs, personality settings, and proposed registration lines. List remaining limitations honestly.

Definition of done: the pet validates, the artwork has been visually reviewed, all common controls work through shared code, and no reminder/API/core changes are needed for its ordinary behavior.
