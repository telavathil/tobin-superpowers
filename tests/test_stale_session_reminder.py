"""Tests for scripts/stale-session-reminder.py.

Run: python3 -m unittest discover -s tests -v
"""

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "stale-session-reminder.py")
NOW = datetime(2026, 10, 26, 15, 0, tzinfo=timezone.utc)


def load_module():
    spec = importlib.util.spec_from_file_location("stale_session_reminder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assistant(ago, context, msg_id="m1"):
    ts = (NOW - ago).isoformat().replace("+00:00", "Z")
    return {"type": "assistant", "timestamp": ts, "message": {"id": msg_id, "usage": {
        "input_tokens": 2, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": context - 1002}}}


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "session.jsonl")

    def write(self, *lines):
        with open(self.path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write((line if isinstance(line, str) else json.dumps(line)) + "\n")

    def run_main(self, payload=None):
        payload = {"transcript_path": self.path} if payload is None else payload
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out):
            code = self.mod.main(now=NOW)
        return code, out.getvalue()

    def test_idle_and_large_reminds(self):
        self.write(assistant(timedelta(hours=3), 640_000))
        code, out = self.run_main()
        self.assertEqual(code, 0)
        message = json.loads(out)["systemMessage"]
        self.assertIn("640K", message)
        self.assertIn("3h", message)
        self.assertIn("/compact", message)
        self.assertNotIn("hookSpecificOutput", json.loads(out))

    def test_recent_is_silent(self):
        self.write(assistant(timedelta(minutes=10), 640_000))
        self.assertEqual(self.run_main(), (0, ""))

    def test_idle_but_small_is_silent(self):
        self.write(assistant(timedelta(hours=3), 80_000))
        self.assertEqual(self.run_main(), (0, ""))

    def test_uses_last_assistant_turn(self):
        self.write(assistant(timedelta(hours=5), 900_000, "old"),
                   {"type": "user", "timestamp": NOW.isoformat()},
                   assistant(timedelta(minutes=2), 900_000, "new"))
        self.assertEqual(self.run_main(), (0, ""))

    def test_minutes_shown_under_an_hour_threshold(self):
        self.mod.IDLE_MINUTES = 30
        self.write(assistant(timedelta(minutes=45), 200_000))
        self.assertIn("45m", json.loads(self.run_main()[1])["systemMessage"])

    def test_bad_input_is_silent(self):
        for payload in ({}, {"transcript_path": "/no/such/file"}, {"transcript_path": 42}):
            with self.subTest(payload=payload):
                self.assertEqual(self.run_main(payload), (0, ""))
        self.write("not json", {"type": "assistant", "message": {}})
        self.assertEqual(self.run_main(), (0, ""))
        with mock.patch("sys.stdin", io.StringIO("not json")):
            self.assertEqual(self.mod.main(now=NOW), 0)


if __name__ == "__main__":
    unittest.main()
