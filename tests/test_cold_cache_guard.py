"""Tests for scripts/cold-cache-guard.py.

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
SCRIPT = os.path.join(REPO_ROOT, "scripts", "cold-cache-guard.py")
NOW = datetime(2026, 10, 26, 15, 0, tzinfo=timezone.utc)


def load_module():
    spec = importlib.util.spec_from_file_location("cold_cache_guard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assistant(ago, context, model="claude-opus-5-5", msg_id="m1"):
    ts = (NOW - ago).isoformat().replace("+00:00", "Z")
    return {"type": "assistant", "timestamp": ts, "message": {"id": msg_id, "model": model, "usage": {
        "input_tokens": 2, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": context - 1002}}}


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.path = os.path.join(tmp.name, "session.jsonl")
        env = mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": os.path.join(tmp.name, "data")})
        env.start()
        self.addCleanup(env.stop)

    def write(self, *lines):
        with open(self.path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write((line if isinstance(line, str) else json.dumps(line)) + "\n")

    def run_main(self, prompt="fix the review comments", payload=None, now=NOW):
        payload = {"session_id": "s1", "transcript_path": self.path, "prompt": prompt} if payload is None else payload
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out):
            code = self.mod.main(now=now)
        return code, (json.loads(out.getvalue()) if out.getvalue() else None)

    def test_cold_and_expensive_blocks_with_cost(self):
        self.write(assistant(timedelta(hours=3), 640_000))
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(out["decision"], "block")
        for text in ("640K", "$3.20", "3h", "/clear", "send it again"):
            self.assertIn(text, out["reason"])
        self.assertNotIn("/compact", out["reason"].split("send it again")[0].split("/clear")[0])

    def test_blocks_once_per_cold_period(self):
        self.write(assistant(timedelta(hours=3), 640_000))
        self.assertEqual(self.run_main()[1]["decision"], "block")
        self.assertEqual(self.run_main(), (0, None))

    def test_new_cold_period_blocks_again(self):
        self.write(assistant(timedelta(hours=3), 640_000))
        self.run_main()
        self.write(assistant(timedelta(hours=1), 700_000, msg_id="m2"))
        self.assertEqual(self.run_main()[1]["decision"], "block")

    def test_warm_cache_passes(self):
        self.write(assistant(timedelta(minutes=4), 900_000))
        self.assertEqual(self.run_main(), (0, None))

    def test_cold_but_cheap_passes(self):
        self.write(assistant(timedelta(hours=3), 150_000))  # $0.75 on Opus
        self.assertEqual(self.run_main(), (0, None))

    def test_price_follows_model(self):
        self.write(assistant(timedelta(hours=3), 300_000))  # Opus $1.50
        self.assertEqual(self.run_main()[1]["decision"], "block")
        self.write(assistant(timedelta(hours=3), 300_000, "claude-sonnet-5-5", "m2"))  # Sonnet $0.75
        self.assertEqual(self.run_main(), (0, None))
        self.write(assistant(timedelta(hours=3), 900_000, "us.anthropic.claude-haiku-5-5", "m3"))
        self.assertEqual(self.run_main(), (0, None))

    def test_slash_commands_pass(self):
        self.write(assistant(timedelta(hours=3), 640_000))
        for prompt in ("/clear", "/compact keep the PR", " /exit"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.run_main(prompt), (0, None))

    def test_uses_last_assistant_turn(self):
        self.write(assistant(timedelta(hours=5), 900_000, msg_id="old"),
                   {"type": "user", "timestamp": NOW.isoformat()},
                   assistant(timedelta(minutes=2), 900_000, msg_id="new"))
        self.assertEqual(self.run_main(), (0, None))

    def test_bad_input_passes(self):
        for payload in ({}, {"transcript_path": "/no/such/file"}, {"transcript_path": 42}):
            with self.subTest(payload=payload):
                self.assertEqual(self.run_main(payload=payload), (0, None))
        self.write("not json", {"type": "assistant", "message": {}})
        self.assertEqual(self.run_main(), (0, None))
        with mock.patch("sys.stdin", io.StringIO("not json")):
            self.assertEqual(self.mod.main(now=NOW), 0)

    def test_unwritable_state_still_blocks_once_per_run(self):
        self.write(assistant(timedelta(hours=3), 640_000))
        os.environ["CLAUDE_PLUGIN_DATA"] = os.path.join(self.path, "nope")  # under a file: unwritable on every OS
        self.assertEqual(self.run_main()[1]["decision"], "block")


if __name__ == "__main__":
    unittest.main()
