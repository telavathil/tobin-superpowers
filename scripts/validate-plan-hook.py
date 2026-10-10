#!/usr/bin/env python3
"""PostToolUse hook: advisory validation of superpowers implementation plans.

Thin adapter between Claude Code's hook input (JSON on stdin) and
validate-plan.py. Only Markdown files under <project>/docs/superpowers/plans/
written by Write or Edit are validated. The file has already been written
when this runs; feedback is advisory and the plan is never modified.

Output: nothing when the file is not a plan, cannot be read, or has no errors
or warnings. Otherwise hookSpecificOutput.additionalContext for Claude, plus a
one-line systemMessage for the user when there are errors. Always exits 0,
except for unexpected internal errors (one stderr line, exit 1, non-blocking).
"""

import importlib.util
import json
import os
import sys

TOOLS = {"Write", "Edit"}
PLAN_DIR_PARTS = ("docs", "superpowers", "plans")
REPORTED = ("error", "warning")


def load_validator():
    # Importing would otherwise write __pycache__ into the installed plugin.
    sys.dont_write_bytecode = True
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate-plan.py")
    spec = importlib.util.spec_from_file_location("tobin_validate_plan", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_payload(raw):
    try:
        data = json.loads(raw) if raw.strip() else None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def resolve_plan(payload, environ):
    """Return (real_path, display_path) for a plan file, or None to ignore."""
    if payload.get("tool_name") not in TOOLS:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    root = environ.get("CLAUDE_PROJECT_DIR") or cwd
    path = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    real, real_root = os.path.realpath(path), os.path.realpath(root)
    try:
        rel = os.path.relpath(real, real_root)
    except ValueError:  # different drives on Windows
        return None
    parts = rel.split(os.sep)
    if parts[0] == os.pardir or len(parts) <= len(PLAN_DIR_PARTS):
        return None
    if tuple(os.path.normcase(p) for p in parts[:len(PLAN_DIR_PARTS)]) != PLAN_DIR_PARTS:
        return None
    if not parts[-1].lower().endswith(".md"):
        return None
    return real, "/".join(parts)


def build_output(validator, display, findings):
    reported = [f for f in findings if f.severity in REPORTED]
    if not reported:
        return None
    summary = validator.format_summary(reported, include_info=False)
    context = "\n".join([
        "Plan validation (advisory, tobin-superpowers hybrid-planning): %s has %s."
        % (display, summary),
        "The file has already been written; this feedback cannot undo it. Revise the plan "
        "to address these findings, or tell the user why they do not apply.",
        "",
        validator.format_text(display, reported, include_info=False),
        "",
        "Checks are structural (paths, interfaces, steps, tests, verification), "
        "not semantic correctness.",
    ])
    output = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}
    if validator.errors(reported):
        output["systemMessage"] = (
            "Plan validation: %s in %s (advisory; details sent to Claude)" % (summary, display))
    return output


def main(stdin=None, stdout=None, stderr=None, environ=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    environ = os.environ if environ is None else environ
    try:
        try:
            raw = stdin.read()
        except (OSError, ValueError):
            return 0
        payload = parse_payload(raw)
        target = resolve_plan(payload, environ) if payload else None
        if target is None or not os.path.isfile(target[0]):
            return 0
        validator = load_validator()
        read_error = getattr(validator, "PlanReadError", ())
        try:
            findings = validator.validate_file(target[0])
        except read_error:
            return 0
        output = build_output(validator, target[1], [f for f in findings if f.rule != "location"])
        if output:
            stdout.write(json.dumps(output) + "\n")
        return 0
    except Exception as exc:  # never break the session with a traceback
        stderr.write("tobin-superpowers validate-plan hook failed: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
