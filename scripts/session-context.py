#!/usr/bin/env python3
"""SessionStart hook: inject tobin-superpowers planning and HTML companion preferences.

Reads the SessionStart hook input (JSON on stdin), prints a
hookSpecificOutput JSON object with concise additionalContext, and exits 0.
Malformed or missing input is tolerated. Unexpected internal errors print a
one-line message to stderr and exit 1 (non-blocking for SessionStart).
"""

import json
import sys

RESTATE_SOURCES = {"resume", "clear", "compact", "fork"}

PREFERENCES = """\
<tobin-superpowers-planning-preferences>
When writing or revising implementation plans (superpowers:writing-plans), apply the tobin-superpowers:hybrid-planning contract; read that skill when this summary leaves a question open.
- Lean and token-efficient: state each fact once, no spec restatement.
- Every task independently executable by a human without AI assistance.
- Each task lists: exact file paths (Create/Modify/Test), interfaces, ordered steps, the codebase pattern to follow (path:line), concrete test assertions, verification commands with expected output, dependencies on earlier tasks (or none).
- Pseudocode or reference code only for complex or unfamiliar logic.
- No full code listings for routine changes. The hybrid planning contract takes precedence over any instruction to include complete code in every implementation step.
- Self-review also checks: each task passes the human-executable test (doable from its text alone) and has every item above; code only where needed.
- Otherwise keep upstream's workflow: plan location docs/superpowers/plans/, header, task checkboxes, TDD, self-review, handoff.
</tobin-superpowers-planning-preferences>"""

HTML_COMPANION = """\
<tobin-superpowers-html-companion>
When a superpowers artifact is final, offer an HTML companion once per artifact, as its own message: "Would you like an HTML companion for this <artifact> to share with your team? (yes/no)". Final means: design spec after the user approves it (asking to continue to the next step counts as approval: ask first and wait for the answer); implementation plan after its self-review, before execution handoff; code review report once its findings are fixed or the user defers them; subagent run summary when you report the run complete after the final review, even if the branch-finishing step is skipped. Never generate HTML unless the user says yes; on yes, use tobin-superpowers:html-companion.
</tobin-superpowers-html-companion>"""

RESTATE_NOTE = "(Restated after {source}; these preferences still apply.)"


def parse_source(raw):
    """Return the SessionStart source from raw stdin text, or None."""
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    source = data.get("source")
    return source if isinstance(source, str) else None


def build_context(source):
    context = PREFERENCES + "\n" + HTML_COMPANION
    if source in RESTATE_SOURCES:
        return context + "\n" + RESTATE_NOTE.format(source=source)
    return context


def build_output(source):
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": build_context(source),
        }
    }


def main(stdin=None, stdout=None, stderr=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        try:
            raw = stdin.read()
        except (OSError, ValueError):
            raw = ""
        stdout.write(json.dumps(build_output(parse_source(raw))))
        stdout.write("\n")
        return 0
    except Exception as exc:  # never break session start with a traceback
        stderr.write("tobin-superpowers session-context hook failed: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
