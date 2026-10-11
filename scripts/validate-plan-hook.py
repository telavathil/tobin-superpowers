#!/usr/bin/env python3
"""PostToolUse hook: advisory plan validation and HTML-companion reminders.

Thin adapter between Claude Code's hook input (JSON on stdin) and
validate-plan.py. Acts only on Markdown files written by Write or Edit under
<project>/docs/superpowers/plans/ or <project>/docs/superpowers/specs/. The
file has already been written when this runs; output is advisory and the file
is never modified.

Output (hookSpecificOutput.additionalContext for Claude):
- plan with errors: the findings, plus a one-line systemMessage for the user;
- plan without errors: any warnings, then a reminder to run the self-review
  and offer the HTML companion before the execution handoff;
- spec: a reminder to offer the HTML companion when the user approves the
  spec or asks to continue to the plan;
- anything else, unreadable plans, missing files: nothing.
Always exits 0, except for unexpected internal errors (one stderr line,
exit 1, non-blocking).
"""

import importlib.util
import json
import os
import sys

TOOLS = {"Write", "Edit"}
PLAN_DIR_PARTS = ("docs", "superpowers", "plans")
SPEC_DIR_PARTS = ("docs", "superpowers", "specs")
REPORTED = ("error", "warning")

# Reminders sit next to the handoff because session-start context loses to a
# freshly loaded upstream skill script in long sessions (seen with 1.0.1).
PLAN_REMINDER = ("Plan has no validation errors. Run the self-review, then offer the HTML "
                 "companion as its own message before the execution handoff "
                 "(skip if already offered for this plan).")
SPEC_REMINDER = ("When the user approves this spec, or asks to continue to the plan, offer "
                 "the HTML companion as its own message first and wait for the answer "
                 "before starting the plan (skip if already offered for this spec).")


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


def resolve_target(payload, environ):
    """Return (kind, real_path, display_path) for a plan or spec, or None to ignore."""
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
    if not parts[-1].lower().endswith(".md"):
        return None
    head = tuple(os.path.normcase(p) for p in parts[:len(PLAN_DIR_PARTS)])
    kind = {PLAN_DIR_PARTS: "plan", SPEC_DIR_PARTS: "spec"}.get(head)
    if kind is None:
        return None
    return kind, real, "/".join(parts)


def reminder_output(display, reminder):
    return {"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": "tobin-superpowers (%s): %s" % (display, reminder),
    }}


def build_output(validator, display, findings):
    reported = [f for f in findings if f.severity in REPORTED]
    if not reported:
        return reminder_output(display, PLAN_REMINDER)
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
    ] + ([] if validator.errors(reported) else ["", PLAN_REMINDER]))
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
        target = resolve_target(payload, environ) if payload else None
        if target is None or not os.path.isfile(target[1]):
            return 0
        kind, real, display = target
        if kind == "spec":
            output = reminder_output(display, SPEC_REMINDER)
        else:
            validator = load_validator()
            read_error = getattr(validator, "PlanReadError", ())
            try:
                findings = validator.validate_file(real)
            except read_error:
                return 0
            output = build_output(validator, display, [f for f in findings if f.rule != "location"])
        if output:
            stdout.write(json.dumps(output) + "\n")
        return 0
    except Exception as exc:  # never break the session with a traceback
        stderr.write("tobin-superpowers validate-plan hook failed: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
