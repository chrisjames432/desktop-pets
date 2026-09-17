import json
from pathlib import Path
import queue
import tempfile
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from desktop_pet.api import ApiServer, StatusSnapshot
from desktop_pet.pets.registry import load_pets
from desktop_pet.reminders import ReminderService


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pets = load_pets()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = ReminderService(Path(self.temp.name) / "reminders.json")
        self.events = queue.Queue()
        self.status = StatusSnapshot()
        self.status.set({"pet_id": "cat", "status": "online"})
        self.api = ApiServer(self.service, self.events, self.pets, self.status, port=0)
        self.api.start()
        self.addCleanup(self.api.stop)

    def request(self, path, body=None, method=None):
        raw = json.dumps(body).encode() if body is not None else None
        req = Request(f"http://127.0.0.1:{self.api.port}"+path, raw,
                      {"Content-Type": "application/json"}, method=method)
        try:
            response = urlopen(req, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_api_and_manual_ui_share_reminder_service(self):
        code, rec = self.request("/reminders", {"text": "API reminder", "in_minutes": 10})
        self.assertEqual(code, 201)
        self.assertEqual(self.service.list()[0]["id"], rec["id"])
        self.assertEqual(self.request("/reminders")[1][0]["text"], "API reminder")
        code, result = self.request(f"/reminders/{rec['id']}/dismiss", {}, "POST")
        self.assertEqual((code, result), (200, {"dismissed": True}))
        self.assertEqual(self.service.list(), [])

    def test_invalid_json_shapes_and_delays(self):
        for body in ([], 123, {"text": "Bad", "in_minutes": "nan"}, {"in_days": 1}):
            self.assertEqual(self.request("/reminders", body)[0], 400)
        self.assertEqual(self.request("/pet/roam", {"roam": "false"})[0], 400)

    def test_pet_commands_only_queue_ui_work(self):
        for pet_id, definition in self.pets.items():
            self.status.set({"pet_id": pet_id})
            action = next(iter(definition.actions))
            self.assertEqual(self.request("/pet/action", {"action": action})[0], 200)
            self.assertEqual(self.events.get_nowait(), ("action", action))
            self.assertEqual(self.request("/pet/select", {"pet": pet_id})[0], 202)
            self.assertEqual(self.events.get_nowait(), ("select_pet", pet_id))
        self.assertEqual(self.request("/pet/action", {"action": "nonexistent"})[0], 400)

    def test_status_does_not_require_tk(self):
        self.assertEqual(self.request("/pet/status")[1]["api_port"], self.api.port)

    def test_shutdown_releases_port(self):
        port = self.api.port
        self.api.stop()
        self.api.thread = None
        second = ApiServer(self.service, self.events, self.pets, self.status, port=port)
        second.stop()

    def test_second_server_cannot_share_public_port(self):
        with self.assertRaises(OSError):
            ApiServer(self.service, self.events, self.pets, self.status, port=self.api.port)
