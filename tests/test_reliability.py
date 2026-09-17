"""Regression checks for reminder persistence, time handling, and API hardening."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from desktop_pet.api import ApiServer, StatusSnapshot
from desktop_pet.reminders import ReminderService, as_utc, human_time, local_label, parse_due
from desktop_pet.storage import JsonFile, StorageError

NOW = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)


class TempCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "reminders.json"


class StorageTests(TempCase):
    def test_file_saved_with_byte_order_mark_still_loads(self):
        data = {"reminders": [{"id": 1, "text": "Edited in Notepad", "due": "2026-09-20T09:00:00+00:00"}]}
        self.path.write_text(json.dumps(data), encoding="utf-8-sig")
        self.assertEqual(ReminderService(self.path).list()[0]["text"], "Edited in Notepad")
        self.assertFalse(list(self.path.parent.glob("*.corrupt-*")))

    def test_briefly_locked_file_is_retried(self):
        store = JsonFile(self.path)
        store.load({})
        real, calls = os.replace, []
        def flaky(src, dst):
            calls.append(dst)
            if len(calls) <= 2:
                raise PermissionError(13, "locked by another program")
            return real(src, dst)
        with patch("desktop_pet.storage.os.replace", side_effect=flaky), patch("desktop_pet.storage.time.sleep"):
            store.save({"value": 1})
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"value": 1})
        self.assertEqual(len(calls), 3)

    def test_permanently_locked_file_reports_and_keeps_previous_data(self):
        service = ReminderService(self.path, now=lambda: NOW)
        service.add("Keep", NOW)
        before = self.path.read_text(encoding="utf-8")
        with patch("desktop_pet.storage.os.replace", side_effect=PermissionError(13, "locked")), \
             patch("desktop_pet.storage.time.sleep"):
            with self.assertRaises(StorageError):
                service.add("Lost", NOW)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertEqual([rec["text"] for rec in service.list()], ["Keep"])
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_recovered_backup_is_used_even_when_the_rewrite_fails(self):
        service = ReminderService(self.path, now=lambda: NOW)
        service.add("First", NOW)
        service.add("Second", NOW)
        self.path.write_text("damaged", encoding="utf-8")
        with patch.object(JsonFile, "save", side_effect=StorageError("read-only disk")), \
             self.assertLogs("desktop_pet.storage", "WARNING"):
            recovered = ReminderService(self.path, now=lambda: NOW)
        self.assertEqual([rec["text"] for rec in recovered.list()], ["First"])

    def test_missing_primary_recovers_from_backup(self):
        service = ReminderService(self.path, now=lambda: NOW)
        service.add("First", NOW)
        service.add("Second", NOW)
        self.path.rename(self.path.with_name("moved-away.json"))
        with self.assertLogs("desktop_pet.storage", "WARNING"):
            recovered = ReminderService(self.path, now=lambda: NOW)
        self.assertEqual([rec["text"] for rec in recovered.list()], ["First"])
        self.assertTrue(self.path.exists())

    def test_crash_between_backup_and_primary_write_loses_nothing(self):
        service = ReminderService(self.path, now=lambda: NOW)
        service.add("First", NOW)
        real = JsonFile._replace
        def crash_on_primary(path, data):
            if path == self.path:
                raise OSError("power loss")
            real(path, data)
        with patch.object(JsonFile, "_replace", side_effect=crash_on_primary):
            with self.assertRaises(StorageError):
                service.add("Second", NOW)
        self.assertEqual([rec["text"] for rec in ReminderService(self.path).list()], ["First"])


class ReminderTimeTests(TempCase):
    def setUp(self):
        super().setUp()
        self.service = ReminderService(self.path, now=lambda: NOW)

    def test_stale_or_missing_next_id_is_repaired_without_losing_reminders(self):
        for next_id in (1, "7", None, True):
            with self.subTest(next_id=next_id):
                data = {"reminders": [{"id": 5, "text": "Keep", "due": "2026-09-20T09:00:00+00:00"}], "next_id": next_id}
                self.path.write_text(json.dumps(data), encoding="utf-8")
                service = ReminderService(self.path, now=lambda: NOW)
                self.assertEqual(service.list()[0]["text"], "Keep")
                self.assertEqual(service.add("New", NOW)["id"], 6)
                self.path.unlink()
                self.path.with_name("reminders.json.bak").unlink(missing_ok=True)

    def test_times_windows_cannot_convert_are_rejected_not_crashes(self):
        for due in ("1960-01-01T00:00:00", "9999-12-31T23:59:59", "9999-12-31T23:59:59Z", "0001-01-01T00:00:00Z"):
            with self.subTest(due=due), self.assertRaises(ValueError):
                self.service.add("Out of range", parse_due({"due": due}))
        self.assertEqual(self.service.list(), [])

    def test_far_future_time_already_on_disk_still_displays(self):
        self.assertIn("UTC", local_label("9999-12-31T23:59:59+00:00"))
        self.assertNotIn("UTC", local_label(NOW))

    def test_human_time_grammar(self):
        with patch("desktop_pet.reminders.utc_now", return_value=NOW):
            self.assertEqual(human_time(NOW+timedelta(hours=1, minutes=5)), "in 1 hour")
            self.assertEqual(human_time(NOW+timedelta(hours=2, minutes=5)), "in 2 hours")
            self.assertEqual(human_time(NOW-timedelta(seconds=1)), "overdue")

    def test_reminder_missed_while_closed_fires_once_per_session_oldest_first(self):
        self.service.add("Later", NOW-timedelta(minutes=1))
        self.service.add("Missed yesterday", NOW-timedelta(days=1))
        self.service.add("Future", NOW+timedelta(minutes=1))
        restarted = ReminderService(self.path, now=lambda: NOW)
        order = []
        while (rec := restarted.next_due()):
            order.append(rec["text"])
            restarted.mark_presented(rec["id"])
        self.assertEqual(order, ["Missed yesterday", "Later"])

    def test_next_due_returns_a_copy(self):
        rec = self.service.add("Original", NOW)
        self.service.next_due()["text"] = "Mutated"
        self.assertEqual(self.service.list()[0]["text"], "Original")
        self.assertEqual(self.service.next_due()["id"], rec["id"])

    def test_snoozed_reminder_fires_again_in_the_same_session(self):
        clock = [NOW]
        service = ReminderService(self.path, now=lambda: clock[0])
        rec = service.add("Snooze me", NOW)
        service.mark_presented(service.next_due()["id"])
        service.snooze(rec["id"], 1)
        self.assertIsNone(service.next_due())
        clock[0] = NOW+timedelta(hours=1)
        self.assertEqual(service.next_due()["id"], rec["id"])
        self.assertEqual(as_utc(service.list()[0]["due"]), NOW+timedelta(hours=1))


class ApiHardeningTests(TempCase):
    def setUp(self):
        super().setUp()
        self.service = ReminderService(self.path)
        self.status = StatusSnapshot()
        self.status.set({"pet_id": "cat"})
        self.api = ApiServer(self.service, queue.Queue(), {}, self.status, port=0)
        self.api.start()
        self.addCleanup(self.api.stop)

    def request(self, path, body=None, headers=None):
        raw = json.dumps(body).encode() if body is not None else None
        req = Request(f"http://127.0.0.1:{self.api.port}"+path, raw, headers or {})
        try:
            response = urlopen(req, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_web_pages_cannot_create_or_dismiss_reminders(self):
        rec = self.service.add("Private", NOW)
        body = {"text": "Injected", "in_minutes": 1}
        self.assertEqual(self.request("/reminders", body, {"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request(f"/reminders/{rec['id']}/dismiss", {}, {"Origin": "null"})[0], 403)
        self.assertEqual(self.request("/reminders", body, {"Host": "attacker.example:8766"})[0], 403)
        self.assertEqual([r["text"] for r in self.service.list()], ["Private"])
        self.assertEqual(self.request("/reminders", body, {"Host": f"localhost:{self.api.port}"})[0], 201)

    def test_unusable_due_time_is_a_client_error(self):
        for due in ("1960-01-01T00:00:00", "9999-12-31T23:59:59Z"):
            code, body = self.request("/reminders", {"text": "Bad time", "due": due})
            self.assertEqual(code, 400, body)
        self.assertEqual(self.service.list(), [])


if __name__ == "__main__":
    unittest.main()
