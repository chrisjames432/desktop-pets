"""Swimming pets: free movement inside the work area, no floor, and two desktop layers."""
from dataclasses import replace
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from desktop_pet import app as app_module
from desktop_pet.app import DesktopPet
from desktop_pet.pets.registry import FACTORIES, PetCatalog
from desktop_pet.reminders import ReminderService
from desktop_pet.storage import JsonFile

DISPLAY = [{"left": 0, "top": 0, "right": 1600, "bottom": 860, "screen": (0, 0, 1600, 900), "primary": True}]


class FakeLayer:
    """Records layer switches without touching real desktop windows."""

    def __init__(self):
        self.behind = False
        self.switches = []
        self.moves = []
        self.allow = True

    def set_behind(self):
        if not self.allow:
            return False
        self.behind = True
        self.switches.append("behind")
        return True

    def set_front(self):
        self.behind = False
        self.switches.append("front")
        return True

    def move(self, x, y):
        if self.behind:
            self.moves.append((x, y))
            return True
        return False


class SwimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cat = FACTORIES["cat"]()
        # Any pet becomes a swimmer through the contract field; the art is irrelevant here.
        cls.fish = replace(cat, id="fish", name="Fish", label="Fish", movement="swim")
        cls.pets = PetCatalog({"fish": lambda: cls.fish, "cat": FACTORIES["cat"]})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name)
        self.reminders = ReminderService(folder / "reminders.json")
        self.settings = JsonFile(folder / "settings.json")
        self.display_mock = patch.object(app_module, "get_monitors", return_value=DISPLAY).start()
        self.addCleanup(patch.stopall)
        random.seed(7)

    def make_app(self, pet_id="fish"):
        app = DesktopPet(self.reminders, self.settings, self.pets, start_loops=False, pet_id=pet_id)
        app.layer = FakeLayer()
        self.addCleanup(app.destroy)
        return app

    def inside_work_area(self, app):
        m = DISPLAY[0]
        return (m["left"] <= app.x <= m["right"] - app.pet_w) and (m["top"] <= app.y <= m["bottom"] - app.pet_h)

    def test_swimmer_starts_mid_screen_and_targets_are_two_dimensional(self):
        app = self.make_app()
        self.assertTrue(app.swimmer)
        self.assertTrue(self.inside_work_area(app))
        self.assertNotEqual(app.y, DISPLAY[0]["bottom"] - app.pet_h)     # not on the floor
        ys = set()
        for _ in range(20):
            app.pick_new_destination()
            ys.add(round(app.target_y))
            self.assertTrue(DISPLAY[0]["top"] <= app.target_y <= DISPLAY[0]["bottom"] - app.pet_h)
        self.assertGreater(len(ys), 3)

    def test_swimmer_moves_diagonally_toward_its_target_and_arrives(self):
        app = self.make_app()
        app.target_x, app.target_y = app.x + 300, app.y - 200
        app.enter_state("walk", 60)
        start = (app.x, app.y)
        for _ in range(40):
            app.step(0.05)
        moved = (app.x - start[0], app.y - start[1])
        self.assertGreater(moved[0], 0)
        self.assertLess(moved[1], 0)
        self.assertEqual(app.facing, 1)
        for _ in range(400):
            app.step(0.05)
            self.assertTrue(self.inside_work_area(app))
        self.assertNotEqual(app.state, "fall")

    def test_swimmer_never_falls_and_stays_where_it_is_dropped(self):
        app = self.make_app()
        app._dragging = True
        app.x, app.y = 700, 100
        app.on_release(None)
        self.assertEqual((app.x, app.y), (700, 100))
        self.assertEqual(app.state, "sit")
        for _ in range(30):
            app.step(0.05)
        self.assertEqual(app.y, 100)

    def test_dive_moves_behind_icons_and_surfaces_on_its_own(self):
        app = self.make_app()
        self.assertTrue(app.dive())
        self.assertTrue(app.layer.behind)
        app._position()
        app.x += 5
        app._position()
        self.assertTrue(app.layer.moves)                       # positioned through the layer while behind
        app._surface_at = 0                                    # time is up
        app.step(0.05)
        self.assertFalse(app.layer.behind)
        self.assertEqual(app.layer.switches, ["behind", "front"])

    def test_popups_and_dragging_force_the_swimmer_to_the_front(self):
        app = self.make_app()
        app.dive()
        app.alert_win = object()
        app.step(0.05)
        self.assertFalse(app.layer.behind)
        app.alert_win = None
        self.assertFalse(app.dive() if (app.chooser or app.speech_bubble) else False)
        app.dive()
        app._dragging = True
        app.step(0.05)
        self.assertFalse(app.layer.behind)

    def test_dive_is_refused_while_a_popup_is_open(self):
        app = self.make_app()
        app.alert_win = object()
        self.assertFalse(app.dive())
        self.assertFalse(app.layer.behind)

    def test_layer_changes_happen_over_time_and_always_come_back(self):
        app = self.make_app()
        with patch.object(app_module.time, "monotonic", side_effect=lambda: app.behavior.clock):
            seen = set()
            for _ in range(6000):
                app.step(0.05)
                seen.add(app.layer.behind)
                self.assertTrue(self.inside_work_area(app))
            self.assertEqual(seen, {True, False})
        # Every dive is followed by a surface: the fish never gets stuck back there.
        self.assertTrue(app.layer.switches[0] == "behind")
        for a, b in zip(app.layer.switches, app.layer.switches[1:]):
            self.assertNotEqual(a, b)

    def test_unavailable_layering_keeps_the_swimmer_in_front(self):
        app = self.make_app()
        app.layer.allow = False
        self.assertFalse(app.dive())
        for _ in range(200):
            app.step(0.05)
        self.assertFalse(app.layer.behind)

    def test_switching_to_a_ground_pet_surfaces_and_lands_on_the_floor(self):
        app = self.make_app()
        app.dive()
        app.select_pet("cat")
        self.assertFalse(app.swimmer)
        self.assertFalse(app.layer.behind)
        self.assertEqual(app.y, app.floor_y)
        app.select_pet("fish")
        self.assertTrue(app.swimmer)
        self.assertTrue(self.inside_work_area(app))

    def test_ground_pets_are_unchanged(self):
        app = self.make_app("cat")
        self.assertFalse(app.swimmer)
        self.assertEqual(app.y, app.floor_y)
        self.assertFalse(app.dive())
        self.assertIn("Walk / Stay", [app.menu.entrycget(i, "label") for i in range(app.menu.index("end") + 1)
                                      if app.menu.type(i) == "command"])


if __name__ == "__main__":
    unittest.main()
