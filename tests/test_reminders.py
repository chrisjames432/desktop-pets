from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from desktop_pet.paths import migrate_legacy
from desktop_pet.reminders import ReminderService, parse_due, as_utc
from desktop_pet.storage import StorageError

NOW = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "reminders.json"
        self.changed = Mock()
        self.service = ReminderService(self.path, self.changed, now=lambda: NOW)

    def test_dismiss_and_snooze_persist(self):
        first = self.service.add("One", NOW-timedelta(minutes=1))
        second = self.service.add("Two", NOW)
        self.service.snooze(first["id"], 1)
        self.service.delete(second["id"])
        loaded = ReminderService(self.path, now=lambda: NOW)
        self.assertEqual(len(loaded.list()), 1)
        self.assertEqual(as_utc(loaded.list()[0]["due"]), NOW+timedelta(hours=1))
        self.assertIsNone(loaded.next_due())

    def test_undismissed_alert_is_recovered_after_restart(self):
        rec = self.service.add("Pending", NOW-timedelta(days=1))
        self.assertEqual(self.service.next_due()["id"], rec["id"])
        self.service.mark_presented(rec["id"])
        self.assertIsNone(self.service.next_due())
        restarted = ReminderService(self.path, now=lambda: NOW)
        self.assertEqual(restarted.next_due()["id"], rec["id"])

    def test_due_order_is_chronological(self):
        newer = self.service.add("Newer", NOW)
        older = self.service.add("Older", NOW-timedelta(hours=1))
        self.assertEqual(self.service.next_due()["id"], older["id"])
        self.service.mark_presented(older["id"])
        self.assertEqual(self.service.next_due()["id"], newer["id"])

    def test_ids_are_not_reused_after_deletion_or_restart(self):
        first = self.service.add("First", NOW)
        self.service.delete(first["id"])
        restarted = ReminderService(self.path)
        self.assertGreater(restarted.add("Next", NOW)["id"], first["id"])

    def test_legacy_naive_dates_and_notified_flag_migrate(self):
        data = {"reminders": [{"id": 4, "text": "Legacy", "due": "2020-01-01T12:00:00", "notified": True}]}
        self.path.write_text(json.dumps(data), encoding="utf-8")
        migrated = ReminderService(self.path)
        self.assertEqual(migrated.next_due()["id"], 4)
        self.assertEqual(as_utc(migrated.list()[0]["due"]), datetime(2020, 1, 1, 12).astimezone(timezone.utc))

    def test_failed_save_does_not_change_memory_or_publish_event(self):
        with patch.object(self.service.store, "save", side_effect=StorageError("disk full")):
            with self.assertRaises(StorageError):
                self.service.add("Must not exist", NOW)
        self.assertEqual(self.service.list(), [])
        self.changed.assert_not_called()

    def test_reads_do_not_reopen_file(self):
        self.service.add("Cached", NOW)
        with patch.object(Path, "open", side_effect=AssertionError("Unexpected disk read")):
            for _ in range(10):
                self.service.list()
                self.service.next_due()

    def test_corrupt_primary_recovers_backup_and_preserves_evidence(self):
        first = self.service.add("First", NOW)
        self.service.add("Second", NOW)
        self.path.write_text("damaged data", encoding="utf-8")
        recovered = ReminderService(self.path)
        self.assertEqual(recovered.list()[0]["id"], first["id"])
        self.assertTrue(list(self.path.parent.glob("*.corrupt-*")))
        self.assertEqual(json.loads(self.path.read_text())["reminders"][0]["text"], "First")

    def test_corrupt_file_without_backup_is_not_silently_overwritten(self):
        self.path.write_text("broken", encoding="utf-8")
        with self.assertRaises(StorageError):
            ReminderService(self.path)
        self.assertEqual(self.path.read_text(), "broken")

    def test_exact_utc_and_offset_times_are_preserved(self):
        self.assertEqual(parse_due({"due": "2026-09-16T12:00:00Z"}), NOW)
        self.assertEqual(parse_due({"due": "2026-09-16T05:00:00-07:00"}), NOW)
        self.assertEqual(parse_due({"in_minutes": 30}, NOW), NOW+timedelta(minutes=30))

    def test_invalid_inputs_rejected(self):
        for payload in ({}, {"in_minutes": True}, {"in_hours": "nan"}, {"in_days": -1},
                        {"due": "garbage"}, {"in_hours": 1, "in_days": 1}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_due(payload)

    def test_migration_copies_once_without_changing_source(self):
        source = self.path.parent / "legacy"
        source.mkdir()
        (source / "reminders.json").write_text('{"reminders": []}', encoding="utf-8")
        target = self.path.parent / "appdata"
        with patch.dict("os.environ", {}, clear=True):
            migrate_legacy(target, source)
            (target / "reminders.json").write_text("existing user data", encoding="utf-8")
            migrate_legacy(target, source)
        self.assertEqual((target / "reminders.json").read_text(), "existing user data")
        self.assertEqual((source / "reminders.json").read_text(), '{"reminders": []}')

    def test_frozen_release_never_imports_developer_reminders(self):
        with patch("sys.frozen", True, create=True):
            migrate_legacy(self.path.parent / "clean", self.path.parent)
        self.assertFalse((self.path.parent / "clean" / "reminders.json").exists())
