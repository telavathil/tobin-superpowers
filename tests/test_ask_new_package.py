"""Tests for scripts/ask-new-package.py.

Run: python3 -m unittest discover -s tests -v
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "ask-new-package.py")


def load_module():
    spec = importlib.util.spec_from_file_location("ask_new_package", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_main(module, command, cwd):
    payload = json.dumps({"cwd": cwd, "tool_input": {"command": command}})
    out = io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(payload)), contextlib.redirect_stdout(out):
        code = module.main()
    return code, out.getvalue()


class NewPackagesTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = os.path.realpath(tmp.name)

    def write(self, name, text):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_npm_existing_passes(self):
        self.write("package.json", json.dumps({"dependencies": {"lodash": "^4"}}))
        self.assertEqual(self.mod.new_packages("npm i lodash@4", self.dir), [])

    def test_npm_scoped_new_asks(self):
        self.write("package.json", json.dumps({"dependencies": {"lodash": "^4"}}))
        self.assertEqual(
            self.mod.new_packages("pnpm add -D @scope/pkg@1.2", self.dir), ["@scope/pkg"]
        )

    def test_go_get_existing_passes(self):
        self.write("go.mod", "module example.com/app\n\nrequire github.com/x/y v1.0.0\n")
        self.assertEqual(self.mod.new_packages("go get github.com/x/y@v1.2.0", self.dir), [])

    def test_pip_normalized_name_passes(self):
        self.write("requirements.txt", "requests==2.31\n")
        self.assertEqual(self.mod.new_packages("pip install Requests>=2", self.dir), [])

    def test_uv_underscore_dash_passes(self):
        self.write("pyproject.toml", '[project]\nname = "app"\ndependencies = ["my-pkg>=1"]\n')
        self.assertEqual(self.mod.new_packages("uv add my_pkg", self.dir), [])

    def test_manifest_found_in_parent(self):
        self.write("package.json", json.dumps({"dependencies": {"lodash": "^4"}}))
        sub = os.path.join(self.dir, "sub", "dir")
        os.makedirs(sub)
        self.assertEqual(self.mod.new_packages("npm i lodash", sub), [])

    def test_no_manifest_asks(self):
        self.assertEqual(self.mod.new_packages("npm install left-pad", self.dir), ["left-pad"])

    def test_non_install_commands_are_empty(self):
        for command in ("npm test", "go build ./...", "pip list"):
            self.assertEqual(self.mod.new_packages(command, self.dir), [], command)

    def test_chained_command(self):
        self.assertEqual(self.mod.new_packages("cd x && npm i newpkg", self.dir), ["newpkg"])

    def test_bare_install_is_empty(self):
        self.assertEqual(self.mod.new_packages("npm install", self.dir), [])

    def test_unbalanced_quote_is_empty(self):
        self.assertEqual(self.mod.new_packages("npm i 'oops", self.dir), [])

    def test_install_forms_still_checked(self):
        self.write("package.json", "{}")
        for command in (
            "python -m pip install evil", "python3 -m pip install evil", "py -m pip install evil",
            "cd x\nnpm i evil", "npm i evil &", "(npm i evil)",
            "sudo npm i evil", "env FOO=1 npm i evil", "FOO=1 npm i evil",
        ):
            self.assertEqual(self.mod.new_packages(command, self.dir), ["evil"], command)

    def test_redirections_are_not_packages(self):
        self.write("package.json", json.dumps({"dependencies": {"lodash": "^4"}}))
        for command in ("npm i lodash 2>&1", "npm i lodash > /dev/null", "npm i lodash 2>out.txt"):
            self.assertEqual(self.mod.new_packages(command, self.dir), [], command)

    def test_requirements_file_flag_skipped(self):
        self.assertEqual(self.mod.new_packages("pip install -r reqs.txt", self.dir), [])


class MainTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = os.path.realpath(tmp.name)

    def test_malformed_payload_is_silent(self):
        result = subprocess.run(
            [sys.executable, SCRIPT], input="not json", capture_output=True, text=True, timeout=10
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_unexpected_error_after_parse_asks(self):
        with mock.patch.object(self.mod, "read_manifest", side_effect=OSError("boom")):
            with open(os.path.join(self.dir, "package.json"), "w", encoding="utf-8") as f:
                f.write("{}")
            code, out = run_main(self.mod, "npm i x", self.dir)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(code, 0)
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("Package check failed: boom", decision["permissionDecisionReason"])

    def test_main_emits_ask(self):
        manifest = os.path.join(self.dir, "package.json")
        with open(manifest, "w", encoding="utf-8") as f:
            f.write("{}")
        code, out = run_main(self.mod, "npm i newpkg", self.dir)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(code, 0)
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("newpkg", decision["permissionDecisionReason"])
        self.assertIn(manifest, decision["permissionDecisionReason"])

    def test_main_no_manifest_names_it(self):
        code, out = run_main(self.mod, "npm i newpkg", self.dir)
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("no manifest found", reason)

    def test_main_known_package_is_silent(self):
        with open(os.path.join(self.dir, "package.json"), "w", encoding="utf-8") as f:
            f.write('{"dependencies": {"lodash": "1"}}')
        self.assertEqual(run_main(self.mod, "npm i lodash", self.dir), (0, ""))


if __name__ == "__main__":
    unittest.main()
