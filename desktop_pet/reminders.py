"""One reminder service for manual UI and HTTP requests; no GUI imports."""
import copy
from datetime import datetime, timedelta, timezone
import math
import threading
from .storage import JsonFile


# Windows cannot display local times outside this span; see local_label().
MIN_DUE_YEAR, MAX_DUE_YEAR = 1971, 2999


def utc_now():
    return datetime.now(timezone.utc)


def as_utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("Invalid reminder time")
    # Legacy naive dates and manual date entries represent this PC's local time.
    try:
        return value.astimezone(timezone.utc).replace(microsecond=0)
    except (OSError, OverflowError) as exc:
        # Windows cannot convert naive local times outside roughly 1970-3000.
        raise ValueError("Reminder time is out of range") from exc


def local_label(value, pattern="%b %d, %H:%M"):
    """Local display text that cannot fail for dates Windows is unable to convert."""
    moment = as_utc(value)
    try:
        return moment.astimezone().strftime(pattern)
    except (OSError, OverflowError, ValueError):
        return moment.strftime("%Y-%m-%d %H:%M UTC")


def parse_due(payload, now=None):
    keys = [key for key in ("due", "in_days", "in_hours", "in_minutes") if key in payload]
    if len(keys) != 1:
        raise ValueError("Provide exactly one of due, in_days, in_hours, in_minutes")
    key = keys[0]
    if key == "due":
        return as_utc(payload[key])
    raw = payload[key]
    if isinstance(raw, bool):
        raise ValueError("Reminder delay must be a positive number")
    amount = float(raw)
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Reminder delay must be a positive number")
    return as_utc((now or utc_now()) + timedelta(**{key[3:]: amount}))


def human_time(value):
    seconds = (as_utc(value) - utc_now()).total_seconds()
    if seconds <= 0:
        return "overdue"
    if seconds >= 86400:
        days = int(seconds // 86400)
        return f"in {days} day" + ("s" if days != 1 else "")
    if seconds >= 3600:
        hours = int(seconds // 3600)
        return f"in {hours} hour" + ("s" if hours != 1 else "")
    return f"in {max(1, int(seconds // 60))} min"


def validate_data(data):
    if not isinstance(data, dict) or not isinstance(data.get("reminders"), list):
        raise ValueError("Invalid reminder file")
    result, seen = [], set()
    for rec in data["reminders"]:
        rid = rec["id"]
        if type(rid) is not int or rid < 1 or rid in seen:
            raise ValueError("Reminder IDs must be unique positive integers")
        text = rec["text"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Reminder text is required")
        seen.add(rid)
        result.append({"id": rid, "text": text, "due": as_utc(rec["due"]).isoformat(),
                       "created": as_utc(rec.get("created", rec["due"])).isoformat(), "notified": False})
    # A missing or stale counter is repaired instead of rejecting every reminder in the file.
    next_id = data.get("next_id")
    lowest = max(seen, default=0) + 1
    if type(next_id) is not int or next_id < lowest:
        next_id = lowest
    return {"reminders": result, "next_id": next_id}


class ReminderService:
    def __init__(self, path, on_change=None, now=utc_now):
        self.store = JsonFile(path)
        self._data = self.store.load({"reminders": [], "next_id": 1}, validate_data)
        self._lock = threading.RLock()
        self._shown = set()  # Delivery is session-only; undismissed alerts survive restart.
        self.on_change = on_change or (lambda: None)
        self.now = now

    def list(self):
        with self._lock:
            items = copy.deepcopy(self._data["reminders"])
            for item in items:
                item["notified"] = item["id"] in self._shown
            return sorted(items, key=lambda rec: rec["due"])

    def add(self, text, due):
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > 2000:
            raise ValueError("Reminder text must contain 1 to 2000 characters")
        due = as_utc(due)
        if not MIN_DUE_YEAR <= due.year <= MAX_DUE_YEAR:
            raise ValueError(f"Reminder time must be between {MIN_DUE_YEAR} and {MAX_DUE_YEAR}")
        with self._lock:
            data = copy.deepcopy(self._data)
            rec = {"id": data["next_id"], "text": text.strip(), "due": due.isoformat(),
                   "created": as_utc(self.now()).isoformat(), "notified": False}
            data["next_id"] += 1
            data["reminders"].append(rec)
            self.store.save(data)
            self._data = data
        self.on_change()
        return copy.deepcopy(rec)

    def delete(self, rid):
        with self._lock:
            data = copy.deepcopy(self._data)
            data["reminders"] = [rec for rec in data["reminders"] if rec["id"] != rid]
            if len(data["reminders"]) == len(self._data["reminders"]):
                return False
            self.store.save(data)
            self._data = data
            self._shown.discard(rid)
        self.on_change()
        return True

    def snooze(self, rid, hours):
        due = parse_due({"in_hours": hours}, self.now()).isoformat()
        with self._lock:
            data = copy.deepcopy(self._data)
            rec = next((r for r in data["reminders"] if r["id"] == rid), None)
            if rec is None:
                return False
            rec.update(due=due, notified=False)
            self.store.save(data)
            self._data = data
            self._shown.discard(rid)
        self.on_change()
        return True

    def next_due(self):
        """Earliest outstanding reminder that is due and not yet presented this session."""
        now = as_utc(self.now()).isoformat()
        with self._lock:
            # Stored times are normalized UTC ISO text, so string order is chronological.
            due = [r for r in self._data["reminders"] if r["id"] not in self._shown and r["due"] <= now]
            if not due:
                return None
            return dict(copy.deepcopy(min(due, key=lambda rec: rec["due"])), notified=False)

    def mark_presented(self, rid):
        with self._lock:
            self._shown.add(rid)
