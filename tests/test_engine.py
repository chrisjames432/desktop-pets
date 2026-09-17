"""Regression checks for the shared engine: memory, lazy pets, and failure containment."""
import gc
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import weakref

from desktop_pet.app import DesktopPet
from desktop_pet.pets.registry import FACTORIES, PetCatalog, load_pets
from desktop_pet.reminders import ReminderService, utc_now
from desktop_pet.storage import JsonFile, StorageError

DISPLAY = [dict(left=0, right=1920, top=0, bottom=1040, screen=(0, 0, 1920, 1080), primary=True)]


class CatalogTests(unittest.TestCase):
    def test_lazy_catalog_builds_only_what_is_used(self):
        built = []
        def counted(key):
            def factory():
                built.append(key)
                return FACTORIES[key]()
            return factory
        catalog = PetCatalog({key: counted(key) for key in FACTORIES})
        self.assertEqual(list(catalog), list(FACTORIES))
        self.assertIn("penguin", catalog)
        self.assertNotIn("dragon", catalog)
        self.assertEqual(built, [])
        self.assertIs(catalog["penguin"], catalog["penguin"])
        self.assertEqual(built, ["penguin"])
        with self.assertRaises(KeyError):
            catalog["dragon"]

    def test_registry_key_must_match_pet_id(self):
        catalog = PetCatalog({"wrong_key": FACTORIES["cat"]})
        with self.assertRaises(ValueError):
            catalog["wrong_key"]

    def test_eager_load_validates_every_registered_pet(self):
        self.assertEqual({key: pet.id for key, pet in load_pets().items()}, {key: key for key in FACTORIES})


class EngineTests(unittest.TestCase):
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
        display_patch = patch("desktop_pet.app.get_monitors", return_value=DISPLAY)
        self.display_mock = display_patch.start()
        self.addCleanup(display_patch.stop)

    def make_app(self, pets=None, **kwargs):
        app = DesktopPet(self.reminders, self.settings, pets or self.pets, start_loops=False, **kwargs)
        self.addCleanup(app.destroy)
        return app

    def render_everything(self, app):
        for state, animation in app.definition.animations.items():
            for facing in (-1, 1):
                for index in range(len(animation.frames)):
                    app._sprites.get(state, index, facing)

    def test_switching_pets_releases_previous_tk_images(self):
        app = self.make_app()
        self.render_everything(app)
        old_cache = weakref.ref(app._sprites)
        old_image = weakref.ref(next(iter(app._sprites.cache.values())))
        app.select_pet("penguin")
        self.render_everything(app)
        gc.collect()
        self.assertIsNone(old_cache())
        self.assertIsNone(old_image())
        self.assertIs(app._sprites.definition, self.pets["penguin"])
        self.assertTrue(app.canvas.itemcget(app.sprite_item, "image"))

    def test_reused_frames_share_one_tk_image(self):
        for pet_id, definition in self.pets.items():
            with self.subTest(pet=pet_id):
                app = self.make_app(pet_id=pet_id)
                self.render_everything(app)
                unique = {id(frame) for animation in definition.animations.values() for frame in animation.frames}
                self.assertEqual(len(app._sprites.cache), 2*len(unique))

    def test_failed_command_does_not_drop_queued_reminder_refresh(self):
        app = self.make_app()
        app.show_list_dialog()
        rec = self.reminders.add("Due now", utc_now())
        with patch("winsound.MessageBeep"):
            app.alert_popup(rec)
        app.events.put(("select_pet", "not_a_pet"))
        self.reminders.delete(rec["id"])
        with self.assertLogs("desktop_pet.app", "ERROR"):
            app.process_events()
        self.assertIsNone(app.alert_win)

    def test_repeating_timer_errors_show_one_dialog(self):
        app = self.make_app()
        with patch("desktop_pet.app.messagebox.showerror") as dialog, self.assertLogs("desktop_pet.app", "ERROR"):
            for _ in range(5):
                try:
                    raise RuntimeError("boom")
                except RuntimeError as exc:
                    app.report_callback_exception(type(exc), exc, exc.__traceback__)
        dialog.assert_called_once()

    def test_pet_switch_survives_unsaved_preference(self):
        app = self.make_app()
        with patch.object(self.settings, "save", side_effect=StorageError("disk full")), \
             self.assertLogs("desktop_pet.app", "ERROR"):
            app.select_pet("penguin")
        self.assertEqual(app.pet_id, "penguin")

    def test_broken_pet_art_falls_back_to_a_working_pet(self):
        def broken():
            raise ValueError("bad art")
        catalog = PetCatalog(dict(FACTORIES, cat=broken))
        with self.assertLogs("desktop_pet.app", "ERROR"):
            app = self.make_app(pets=catalog, pet_id="cat")
        self.assertEqual(app.pet_id, "penguin")
        with self.assertLogs("desktop_pet.ui", "ERROR"):
            app.choose_pet()
        self.assertIsNotNone(app.chooser)

    def test_startup_survives_display_enumeration_failure(self):
        self.display_mock.side_effect = OSError("no desktop yet")
        with self.assertLogs("desktop_pet.app", "WARNING"):
            app = self.make_app()
        self.assertEqual(len(app.monitors), 1)
        self.display_mock.side_effect = None
        app._next_display_check = 0
        app.step(0.05)
        self.assertEqual(app.monitors, DISPLAY)

    def test_unknown_saved_pet_uses_first_registered_pet(self):
        self.assertEqual(self.make_app(pet_id="removed_pet").pet_id, next(iter(self.pets)))


if __name__ == "__main__":
    unittest.main()
