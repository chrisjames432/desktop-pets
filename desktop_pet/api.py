"""Local HTTP adapter. UI commands cross a queue; handlers never touch Tk."""
import copy
import json
import logging
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.parse import urlsplit
from .reminders import parse_due
from .storage import StorageError

log = logging.getLogger(__name__)
API_PORT = 8766  # Fixed so integrations never have to discover it.


class Forbidden(Exception):
    pass


class StatusSnapshot:
    def __init__(self):
        self._lock = threading.Lock()
        self._value = {}

    def set(self, value):
        with self._lock:
            self._value = copy.deepcopy(value)

    def get(self):
        with self._lock:
            return copy.deepcopy(self._value)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        # Windows SO_REUSEADDR can allow a second listener on the same port.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(5)
        return sock, address

    def handle_error(self, request, client_address):
        # The default implementation prints to stderr, which does not exist in a windowed EXE.
        log.warning("API connection from %s failed", client_address, exc_info=True)


class ApiServer:
    def __init__(self, reminders, events, pets, status, port=API_PORT):
        self.reminders, self.events, self.pets, self.status = reminders, events, pets, status
        self.http = LocalServer(("127.0.0.1", port), self._handler())
        self.port = self.http.server_port
        self.thread = None
        self._stopped = False

    def start(self):
        self.thread = threading.Thread(target=self.http.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        self.thread.start()

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        if self.thread:
            self.http.shutdown()
            self.thread.join(timeout=2)
        self.http.server_close()

    def _handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def send_json(self, code, body):
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def read_json(self):
                size = int(self.headers.get("Content-Length", 0))
                if not 0 <= size <= 65536:
                    raise ValueError("Request body must be at most 64 KiB")
                data = json.loads(self.rfile.read(size)) if size else {}
                if not isinstance(data, dict):
                    raise ValueError("JSON body must be an object")
                return data

            def check_local_client(self):
                """Web pages must not drive the API: browsers always identify themselves
                with Origin on cross-site writes, and DNS rebinding shows a foreign Host."""
                host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]").lower()
                if host not in ("127.0.0.1", "localhost") or self.headers.get("Origin"):
                    try:  # Consume the refused body so Windows does not reset the connection.
                        self.rfile.read(min(max(int(self.headers.get("Content-Length", 0)), 0), 65536))
                    except (ValueError, OSError):
                        pass
                    raise Forbidden("Local clients only")

            def route(self, method):
                self.check_local_client()
                path = urlsplit(self.path).path.rstrip("/")
                if method == "GET" and path == "/reminders":
                    return 200, api.reminders.list()
                if method == "GET" and path == "/pet/status":
                    return 200, dict(api.status.get(), api_port=api.port, reminders_count=len(api.reminders.list()))
                if method == "POST":
                    body = self.read_json()
                    if path == "/reminders":
                        return 201, api.reminders.add(body.get("text"), parse_due(body))
                    if path == "/pet/select":
                        pet_id = body.get("pet")
                        if not isinstance(pet_id, str) or pet_id not in api.pets:
                            raise ValueError("Unknown pet")
                        api.events.put(("select_pet", pet_id))
                        return 202, {"pet": pet_id}
                    if path == "/pet/roam":
                        enabled = body.get("roam", True)
                        if type(enabled) is not bool:
                            raise ValueError("roam must be a JSON boolean")
                        api.events.put(("set_roam", enabled))
                        return 200, {"roam": enabled}
                    if path == "/pet/speak":
                        message = body.get("text", "Hello!")
                        if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
                            raise ValueError("text must contain 1 to 2000 characters")
                        api.events.put(("speak", message.strip()))
                        return 200, {"status": "ok", "spoke": message.strip()}
                    if path in ("/pet/action", "/pet/state", "/pet/meow"):
                        action = body.get("state" if path == "/pet/state" else "action", "silly")
                        if path == "/pet/meow":
                            action = "silly"
                        current = api.pets[api.status.get()["pet_id"]]
                        allowed = set(current.actions) | {"silly", "idle", "sit", "look", "walk"}
                        if not isinstance(action, str) or action not in allowed:
                            raise ValueError("Action unavailable for this pet")
                        api.events.put(("action", action))
                        return 200, {"status": "ok", "action": action}
                parts = path.strip("/").split("/")
                if len(parts) >= 2 and parts[0] == "reminders":
                    rid = int(parts[1])
                    if (method == "DELETE" and len(parts) == 2) or (method == "POST" and len(parts) == 3 and parts[2] in ("done", "dismiss")):
                        removed = api.reminders.delete(rid)
                        return (200 if removed else 404), {"deleted" if method == "DELETE" else "dismissed": removed}
                return 404, {"error": "not found"}

            def handle_request(self, method):
                try:
                    code, body = self.route(method)
                except (ValueError, TypeError, OverflowError) as exc:
                    code, body = 400, {"error": str(exc)}
                except Forbidden as exc:
                    code, body = 403, {"error": str(exc)}
                except StorageError as exc:
                    log.exception("Reminder persistence failed")
                    code, body = 500, {"error": str(exc)}
                except Exception:
                    log.exception("Unexpected API error")
                    code, body = 500, {"error": "Internal error; see the app log"}
                try:
                    self.send_json(code, body)
                except (OSError, TimeoutError):
                    pass  # Client disconnected; the accepted operation remains valid.

            def do_GET(self):
                self.handle_request("GET")

            def do_POST(self):
                self.handle_request("POST")

            def do_DELETE(self):
                self.handle_request("DELETE")

        return Handler
