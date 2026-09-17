# Desktop Pets architecture

The reminder service is the product core. Pets are interchangeable presentations with their own artwork and personality. Use Python/Tkinter, Pillow, standard-library JSON persistence, and a localhost HTTP adapter.

## Ownership and data flow

| Module | Responsibility |
| --- | --- |
| `desktop_pet/reminders.py` | Shared validation, UTC time handling, add/dismiss/snooze, due ordering, and session delivery tracking |
| `desktop_pet/storage.py` | Atomic JSON writes, last-known-good backup, explicit corruption recovery |
| `desktop_pet/paths.py` | Per-user data path and one-time source-data migration |
| `desktop_pet/api.py` | Request validation, stable localhost port, GUI command queue, thread-safe status snapshot |
| `desktop_pet/app.py` | Application lifecycle, input, movement, timers, service coordination |
| `desktop_pet/ui.py` | Species-independent chooser, reminders, alerts, speech bubbles, and menu |
| `desktop_pet/behavior.py` | Animation timing, weighted personality behavior, cooldowns, and state transitions |
| `desktop_pet/sprites.py` | Lazy Tk image cache for the current pet only, shared by reused frames, and left-facing mirrors |
| `desktop_pet/pets/base.py` | Public artwork/personality contract and validation |
| `desktop_pet/pets/registry.py` | Explicit bundled pet factories; the app builds each pet on first use, tests build all eagerly |
| `desktop_layout.py` | Windows monitor work areas and surface transitions |
| `desktop_pet/platform_windows.py` | Per-data-directory process mutex and startup messages |

Manual controls and HTTP handlers both call `ReminderService`. Successful changes enqueue a refresh event; the Tk thread refreshes open views. Pet commands also go through that queue. API handlers read a status snapshot instead of touching the Tk app object. File failures are reported before an in-memory mutation is committed.

Outstanding reminders remain persistent until dismissed or snoozed. Presentation is tracked only in memory, so an unanswered reminder returns after restart. Alert UI completion never depends on finishing an animation. Reminder checks use a separate timer and do not reread JSON every tick.

Pet definitions contain Pillow frames and data. They never create Tk windows, call the API, write files, or choose their own movement loop. The shared engine owns motion, Stay mode, dragging, taskbar transitions, and reminder interruption. Pet behavior uses monotonic time and floating-point positions; drawing changes only when the frame or integer window position changes.

## Adding a pet

Follow `PET_CREATION.md`. Normal integration adds one module and one explicit registry entry. No API/menu/chooser species branches should be necessary. Preview imports the pet module directly so a separate agent can work before registration. The optional bundled asset directory is included by `DesktopPets.spec`.

## Maintenance checklist

1. Preserve any unrelated working-tree changes. Never use real reminder data as a test fixture.
2. Identify whether a change belongs to the reminder service, shared engine/UI, or a pet definition.
3. Add a regression check for behavior with real failure consequences; use pure tests for time/persistence and hidden Tk tests for integration.
4. Run `python -m unittest discover -s tests -v` and `git diff --check`.
5. For artwork changes, generate and inspect a contact sheet; preserve IDs and document cadence changes.
6. For a release, run `build_exe.ps1` and the clean-Windows checklist in README. Do not claim an EXE was tested unless it was actually built and run.

## Current scope

No plugin loader, cloud sync, database server, or custom per-pet application classes. JSON is loaded once and used by a single owned app process. External integrations should use the API instead of modifying JSON while the app runs. Future features should retain these boundaries.
