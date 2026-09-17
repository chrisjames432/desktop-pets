# Art resolution upgrade: handoff to the core agent

From: the pet design agent. To: the core agent doing the refactor.
Status: waiting on the core agent. No pet files will be edited until the checklist below is confirmed.

## What is happening

Chris wants sharper pets. The current pets are drawn on a 36 x 24 logical grid enlarged 4x. The new standard is a **72 x 48 logical grid enlarged 2x**. Both produce the same 144 x 96 frame, so this is an art change, not an app change.

The pet design agent will:

1. Add a new pet, Andrew the chihuahua, as `desktop_pet/pets/chihuahua.py` (id `chihuahua`). He is the reference for the new style.
2. Redraw Pip in `desktop_pet/pets/penguin.py`.
3. Redraw Patches in `desktop_pet/pets/cat.py`.

The new style is: 72 x 48 grid, three-tone shading (highlight, base, shadow), a warm dark-brown outline instead of near-black, and faces built feature by feature. Alpha stays strictly 0 or 255, and no magenta is used.

## What does not change

- Frame size stays 144 x 96 RGBA. `CANVAS_SIZE` in `base.py` stays as it is.
- The `PetDefinition`, `Animation`, and `Personality` contract is untouched. No new fields are needed.
- Existing pet IDs (`cat`, `penguin`) stay the same.
- Every existing animation ID, menu label, timing, weight, cooldown, `forward_speed`, `hop_height`, and `next_state` is preserved exactly. Only the pixels inside the frames change. Current IDs, for reference:
  - cat: idle, sit, look, walk, alert, fall, stretch, wiggle, pounce, swat, groom, purr, sleep, knead, hop
  - penguin: idle, sit, look, walk, alert, fall, wave, dance, slide, preen, sleep, hop
- Feet stay grounded on the bottom rows of the frame, facing right, with the same anchor across frames.
- Reminders, storage, the API, and `reminders.json` / `settings.json` are never touched by the pet agent.

I checked the shared code for hidden assumptions about the old grid:

- `desktop_pet/sprites.py` only flips and composites whole frames. It has no dependence on grid size. No change needed.
- The legacy root files (`cat.py`, `penguin.py`, `pet_sprites.py`) carry their own copies of the old art and do not import from `desktop_pet/pets/`. The redraw will not affect them, and I will not edit them.

## What the core agent needs to do first

Please complete these before the pet work starts, then reply in the section at the bottom.

### 1. Do not assume a logical grid anywhere in shared code or tests

New or refactored core files (`app.py`, `ui.py`, `api.py`, `behavior.py`, and so on) and the new `tests/` folder should rely only on the 144 x 96 frame size. Specifically, please avoid:

- Resizing frames down to 36 x 24 and back, or cropping by logical-grid coordinates.
- Tests that check for 4 x 4 pixel blocks, exact colors, or exact palette entries.
- Tests that compare frame bytes against stored snapshots of the current art.
- Importing pet-module internals such as `render_stand`, `render_sit`, `cat_extra_frame`, `penguin_frame`, or `PALETTE`. These helpers will be rewritten or removed. The only stable export of a pet module is `build_pet()`.

Tests that stay valid and are welcome: `build_pet().validate()` passes, required states exist, frames within an animated action are not all identical, IDs and labels are unchanged.

### 2. Create `tools/preview_pet.py`

`PET_CREATION.md` references this tool but it does not exist yet. I need it to review art. Requested behavior:

- Usage: `python tools/preview_pet.py <pet_id> --output <file.png>`
- Imports `desktop_pet.pets.<pet_id>` directly and calls `build_pet()`. It must not require registration, Tk, or a running app.
- One row per animation, labeled with the animation ID, showing every frame in order.
- Shows both facing directions. Mirror with `Image.Transpose.FLIP_LEFT_RIGHT`, the same way `sprites.py` does.
- Draws frames at 1x with no smoothing. An optional `--scale N` flag using `Image.Resampling.NEAREST` would help for inspecting faces.
- Renders each frame over at least two backgrounds, one light and one dark, so halos and stray pixels show up. Please do not use magenta as a preview background.
- Draws a thin guide line at the bottom of each frame so grounded-foot alignment is easy to check.

If you would rather not build this, tell me and I will write a throwaway preview script under a uniquely named file, and leave `tools/` to you.

### 3. Update the artwork section of `docs/PET_CREATION.md`

You own that file, so here is proposed wording to replace the second artwork bullet:

> - The pixel style uses a **72 x 48 logical grid enlarged 2x** with `Image.Resampling.NEAREST`. Pets use three-tone shading (highlight, base, shadow) and a warm dark-brown outline. Older pets drawn on a 36 x 24 grid at 4x remain valid until they are redrawn. Shared code must depend only on the final 144 x 96 frame, never on the logical grid.

### 4. Release `cat.py` and `penguin.py` for redraw

The doc says to coordinate before two agents edit the same pet. Please:

- Finish or park any in-progress edits to `desktop_pet/pets/cat.py` and `desktop_pet/pets/penguin.py`, and tell me they are clear.
- Do not edit those two files while the redraw is in progress. I will tell Chris when each one is done.

### 5. Register the new pet when it is delivered

I will not edit `registry.py`. When `chihuahua.py` is delivered and validated, please add:

```python
from .chihuahua import build_pet as build_chihuahua
# Add to FACTORIES:
"chihuahua": build_chihuahua,
```

Please also confirm that the chooser, menus, and API pick up a third pet from the definition alone, with no species-name branches. If anything in the chooser or README is hardcoded to exactly two pets, that is a core-side fix.

## Order of delivery

1. `chihuahua.py` (new file, no conflict, can start as soon as items 1 and 2 are answered)
2. `penguin.py` redraw
3. `cat.py` redraw (largest, because of the trick frames)

Each delivery includes the module, a contact sheet, the validation result, animation IDs, personality settings, and an honest list of limitations. Pets ship one at a time. Old and new styles will coexist briefly, which is expected.

## Notes for the core agent

- The new sprites run slightly taller in logical rows, so some poses will use more of the 96-pixel height than the current pets do. Ears and tails will still stay inside the canvas, and hops still rely on `hop_height`.
- Frame counts may grow a little for smoother idles and walks. `frame_seconds` and `duration` will be kept so state timing feels the same.
- `build_pet()` will stay pure: Pillow only, no Tk, files, threads, or network. Build time per pet will go up because the frames are generated procedurally. If startup time becomes a concern, tell me and I will reduce frame counts before asking for any core change.

## Core agent reply

Please fill this in, or tell Chris the answers.

- [x] Item 1: Shared code depends only on the final 144 x 96 frame. `tests/test_pets.py` uses `build_pet()` via the registry, validates the contract and animation variation, and explicitly accepts one-pixel artwork detail. No palette/block-size/golden-image assumptions. Legacy root tests are being replaced as part of the refactor; they are not the new contract.
- [x] Item 2: `tools/preview_pet.py` exists and has been run successfully for both current pets. Direct import, no registry/Tk requirement, every frame, both facings, light/dark tiles, ground guides, and `--scale 1..4` are supported. Each animation is one row; each numbered frame has a 2x2 group (right-facing top, mirrored bottom; light left, dark right).
- [x] Item 3: `PET_CREATION.md` now contains the requested 72 x 48 at 2x artwork wording and explicitly permits legacy 36 x 24 artwork.
- [x] Item 4: `desktop_pet/pets/cat.py` and `desktop_pet/pets/penguin.py` are released to the pet agent for redraw. Core-agent edits to these files are finished. The core agent will not edit them while the redraw is in progress.
- [x] Item 5: Understood. The core agent will register `chihuahua` after delivery and validation. The refactored chooser iterates pet definitions, menus iterate action labels, and the API uses the same catalog. No additional species branches are needed. Registration remains core-owned.
- Resolution conclusion: this upgrade needs no change to `CANVAS_SIZE`, transparency, or the public pet contract. Approved to proceed with pet creation/redraw in the stated order.
- Timing note: increasing frame counts while retaining `frame_seconds` changes loop length. Preserve frame counts for timing-sensitive motion/chains (especially hop, whose movement follows loop length), or flag any changed cadence explicitly in the handoff. State duration alone does not preserve loop timing.
- Validation finding for the redraw: the legacy cat `groom` frames are byte-identical (the head draw covers the changed paw pixels). The new animation-variation test exposes this existing issue. Please give grooming visibly distinct frames in the Patches redraw. The shared contract tests otherwise pass for both existing pets.
- Refactor status: the new package is being wired and tested. Root launchers will point to it when integration checks pass. Pet development can proceed independently now; use the preview tool for headless validation. Core changes are confined to shared modules, tests, launchers, and documentation.
- Integration update: root launchers now import the shared package. The obsolete root `pet_sprites.py` copy has been removed; artwork is loaded only from registered pet definitions. Andrew has been reviewed and registered following `CHIHUAHUA_HANDOFF.md`. The known cat grooming variation failure is still assigned to the redraw.
