import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from desktop_pet.platform_windows import SingleInstance
from desktop_pet.app import main, api_port, guard_stdio, load_settings
from desktop_pet.app import DesktopPet
from desktop_pet.api import ApiServer
from desktop_pet.paths import data_directory
from desktop_pet.storage import JsonFile


def free_port_api(*args, **kwargs):
    return ApiServer(*args, **dict(kwargs, port=0))


class LifecycleTests(unittest.TestCase):
    """Every main() call here uses DESKTOP_PETS_DATA_DIR so real user data is never touched."""

    def run_main(self, folder, api_factory, **patches):
        instances = []
        def create_app(*args, **kwargs):
            app = DesktopPet(*args, **kwargs)
            app.withdraw()
            app.after(150, app.destroy)
            instances.append(app)
            return app
        with patch.dict("os.environ", {"DESKTOP_PETS_DATA_DIR": folder}), \
             patch("desktop_pet.app.DesktopPet", side_effect=create_app), \
             patch("desktop_pet.app.ApiServer", side_effect=api_factory), \
             patch("desktop_pet.app.show_message") as message:
            started = [patch("desktop_pet.app." + name, value) for name, value in patches.items()]
            for item in started:
                item.start()
            try:
                main()
            finally:
                for item in started:
                    item.stop()
        return instances, message

    def test_only_one_instance_can_own_a_data_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            first = SingleInstance(Path(folder))
            second = SingleInstance(Path(folder))
            try:
                self.assertFalse(first.already_running)
                self.assertTrue(second.already_running)
            finally:
                second.close()
                first.close()
            third = SingleInstance(Path(folder))
            try:
                self.assertFalse(third.already_running)
            finally:
                third.close()

    def test_second_instance_exits_without_touching_data(self):
        with tempfile.TemporaryDirectory() as folder:
            owner = SingleInstance(Path(folder).resolve())
            try:
                instances, message = self.run_main(folder, Mock(side_effect=AssertionError("must not start")))
            finally:
                owner.close()
            self.assertEqual(instances, [])
            message.assert_called_once()
            self.assertEqual(os.listdir(folder), [])

    def test_busy_port_with_unmigrated_legacy_data_stops_before_migration(self):
        migrate = Mock()
        with tempfile.TemporaryDirectory() as folder:
            instances, message = self.run_main(
                folder, Mock(side_effect=OSError("Port occupied")), migrate_legacy=migrate,
                pending_legacy_files=Mock(return_value=[("old", "new")]))
        migrate.assert_not_called()
        self.assertEqual(instances, [])
        message.assert_called_once()
        self.assertIn("8766", message.call_args.args[0])

    def test_busy_port_keeps_reminders_running_without_api(self):
        with tempfile.TemporaryDirectory() as folder:
            instances, message = self.run_main(folder, Mock(side_effect=OSError("Port occupied")))
            message.assert_not_called()
            self.assertEqual(len(instances), 1)
            self.assertTrue(instances[0]._closed)
            log_text = (Path(folder) / "app.log").read_text(encoding="utf-8")
        self.assertIn("Local API disabled", log_text)

    def test_full_app_start_and_shutdown_with_isolated_data(self):
        servers = []
        def create_api(*args, **kwargs):
            server = free_port_api(*args, **kwargs)
            servers.append(server)
            return server
        with tempfile.TemporaryDirectory() as folder:
            instances, message = self.run_main(folder, create_api)
            message.assert_not_called()
            self.assertTrue(instances[0]._closed)
            self.assertTrue(servers[0]._stopped)
            self.assertFalse(servers[0].thread.is_alive())
            self.assertIn("Started Desktop Pets", (Path(folder) / "app.log").read_text(encoding="utf-8"))
            owner = SingleInstance(Path(folder))
            try:
                self.assertFalse(owner.already_running)
            finally:
                owner.close()

    def test_unreadable_reminders_report_an_error_and_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "reminders.json").write_text("broken", encoding="utf-8")
            instances, message = self.run_main(folder, free_port_api)
            self.assertEqual(instances, [])
            message.assert_called_once()
            self.assertEqual((Path(folder) / "reminders.json").read_text(encoding="utf-8"), "broken")
            self.assertIn("Cannot read reminders.json", (Path(folder) / "app.log").read_text(encoding="utf-8"))

    def test_damaged_settings_never_block_reminders(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("{not json", encoding="utf-8")
            settings = JsonFile(path)
            with self.assertLogs("desktop_pet.app", "WARNING"):
                self.assertEqual(load_settings(settings), {"pet": "cat"})
            settings.save({"pet": "penguin"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"pet": "penguin"})

    def test_windowed_exe_without_console_streams_can_still_write(self):
        with patch.object(sys, "stdout", None), patch.object(sys, "stderr", None):
            guard_stdio()
            try:
                print("no console", file=sys.stderr)
                sys.stdout.write("no console")
            finally:
                sys.stdout.close()
                sys.stderr.close()

    def test_frozen_exe_stores_data_in_the_user_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            profile, bundle = Path(folder, "profile").resolve(), Path(folder, "_MEI12345").resolve()
            with patch.dict("os.environ", {"LOCALAPPDATA": str(profile)}), \
                 patch("sys.frozen", True, create=True), patch("sys._MEIPASS", str(bundle), create=True):
                os.environ.pop("DESKTOP_PETS_DATA_DIR", None)
                directory = data_directory()
            self.assertEqual(directory, profile / "DesktopPets")
            self.assertTrue(directory.is_absolute())
            self.assertNotIn(bundle, directory.parents)

    def test_data_directory_is_absolute_even_with_an_empty_environment(self):
        with patch.dict("os.environ", {"LOCALAPPDATA": ""}):
            os.environ.pop("DESKTOP_PETS_DATA_DIR", None)
            self.assertTrue(data_directory().is_absolute())

    def test_api_port_is_fixed_unless_a_valid_development_override_is_set(self):
        for value, expected in ((None, 8766), ("9123", 9123), ("0", 0), ("abc", 8766), ("70000", 8766)):
            env = {} if value is None else {"DESKTOP_PETS_API_PORT": value}
            with self.subTest(value=value), patch.dict("os.environ", env):
                if value is None:
                    os.environ.pop("DESKTOP_PETS_API_PORT", None)
                self.assertEqual(api_port(), expected)

    def test_main_restores_exception_hooks(self):
        before = sys.excepthook
        with tempfile.TemporaryDirectory() as folder:
            self.run_main(folder, free_port_api)
        self.assertIs(sys.excepthook, before)


if __name__ == "__main__":
    unittest.main()
