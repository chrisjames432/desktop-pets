from dataclasses import replace
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch

from desktop_pet.app import DesktopPet
from desktop_pet.pets.registry import load_pets
from desktop_pet.reminders import ReminderService, utc_now
from desktop_pet.storage import JsonFile
from desktop_layout import floor_at


def monitor(left=0, right=1920, bottom=1080, taskbar=0, top=0, primary=False):
    return dict(left=left, right=right, top=top, bottom=bottom-taskbar,
                screen=(left, top, right, bottom), primary=primary)


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pets = load_pets()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.reminders = ReminderService(root / "reminders.json")
        self.settings = JsonFile(root / "settings.json")
        self.settings.load({"pet": "cat"})
        self.displays = [monitor(primary=True), monitor(1920, 3840, taskbar=40)]
        display_patch = patch("desktop_pet.app.get_monitors", return_value=self.displays)
        self.display_mock = display_patch.start()
        self.addCleanup(display_patch.stop)
        self.app = DesktopPet(self.reminders, self.settings, self.pets, start_loops=False)
        self.addCleanup(self.app.destroy)

    def test_switch_keeps_reminders_and_preference(self):
        rec = self.reminders.add("Keep me", utc_now())
        for pet_id in self.pets:
            self.app.select_pet(pet_id)
            self.assertEqual(self.reminders.list()[0]["id"], rec["id"])
            self.assertEqual(self.settings.load({})["pet"], pet_id)
            self.assertEqual(self.app.status.get()["pet_id"], pet_id)

    def test_third_pet_requires_only_registration(self):
        new_pet = replace(next(iter(self.pets.values())), id="test_companion", name="Test companion")
        self.app.pets = dict(self.pets, test_companion=new_pet)
        self.app.choose_pet()
        self.app.select_pet("test_companion")
        self.assertEqual(self.app.definition.name, "Test companion")
        self.assertEqual(self.app.status.get()["actions"], list(new_pet.actions))
        self.app.step(0.05)
        self.assertIsNone(self.app.chooser)

    def test_all_animation_states_render_in_both_directions(self):
        for pet_id, definition in self.pets.items():
            self.app.select_pet(pet_id)
            for state, animation in definition.animations.items():
                for facing in (-1, 1):
                    with self.subTest(pet=pet_id, state=state, facing=facing):
                        self.app.enter_state(state)
                        self.app.facing = facing
                        for i in range(len(animation.frames)):
                            self.app.behavior.elapsed = i*animation.frame_seconds
                            self.app.render()
                            self.assertTrue(self.app.canvas.itemcget(self.app.sprite_item, "image"))

    def test_crossings_never_put_sprite_inside_taskbar(self):
        for pet_id in self.pets:
            self.app.select_pet(pet_id)
            for start, target in ((1774, 2200), (1922, 1500)):
                self.app._floor_transition = None
                self.app.x = start
                self.app.y = self.app.floor_y = floor_at(self.displays, start, 144, 1000)
                self.app.roam_enabled = True
                self.app.target_x = target
                self.app.enter_state("walk", 20)
                crossed = False
                for _ in range(85):
                    self.app.step(0.05)
                    crossed |= self.app._floor_transition is not None
                    self.assertLessEqual(self.app.y, floor_at(self.displays, self.app.x, 144, self.app.y+95))
                self.assertTrue(crossed)
                self.assertIsNone(self.app._floor_transition)
                self.assertEqual(self.app.y, self.app.floor_y)

    def test_stay_blocks_forward_motion_for_every_action(self):
        for pet_id, definition in self.pets.items():
            self.app.select_pet(pet_id)
            self.app.set_roam(False)
            x = self.app.x
            for action in definition.actions:
                self.app.do_action(action)
                for _ in range(20):
                    self.app.step(0.05)
                self.assertEqual(self.app.x, x)

    def test_drag_release_falls_to_destination_surface(self):
        self.app.x, self.app.y = 2500, 500
        self.app._dragging = True
        self.app.on_release(None)
        self.assertEqual(self.app.state, "fall")
        for _ in range(45):
            self.app.step(0.05)
        self.assertEqual(self.app.y, 944)

    def test_display_setting_changes_and_disconnect(self):
        self.app.set_roam(False)
        self.display_mock.return_value = [monitor(primary=True, taskbar=48)]
        self.app.x = 2500
        self.app._next_display_check = 0
        for _ in range(30):
            self.app.step(0.05)
        self.assertLessEqual(self.app.x+self.app.pet_w, 1920)
        self.assertEqual(self.app.y, 936)

    def test_api_changes_refresh_open_reminder_list(self):
        self.app.show_list_dialog()
        win = next(iter(self.app._list_refreshers))
        def texts(widget):
            result = []
            if "text" in widget.keys():
                result.append(widget.cget("text"))
            for child in widget.winfo_children():
                result += texts(child)
            return result
        rec = self.reminders.add("Added through service", utc_now())
        self.app.process_events()
        self.assertIn("Added through service", texts(win))
        self.reminders.delete(rec["id"])
        self.app.process_events()
        self.assertNotIn("Added through service", texts(win))

    def test_existing_alert_waits_for_acknowledgement(self):
        first = self.reminders.add("First", utc_now())
        self.reminders.add("Second", utc_now())
        with patch.object(self.app, "after"), patch("winsound.MessageBeep"):
            self.app.tick_reminders()
            self.app.tick_reminders()
        self.assertEqual(self.app.alert_id, first["id"])
        self.assertFalse(self.app.do_action("silly"))
        self.reminders.delete(first["id"])
        self.app.process_events()
        self.assertIsNone(self.app.alert_win)

    def test_unchanged_frame_does_not_redraw(self):
        self.app.render()
        with patch.object(self.app.canvas, "itemconfig") as update:
            self.app.render()
            update.assert_not_called()
