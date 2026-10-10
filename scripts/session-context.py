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
When writing or revising implementation plans (superpowers:writing-plans), apply the tobin-superpowers:hybrid-planning contract. Read that skill for full detail; this summary is authoritative if you do not.
- Lean and token-efficient: tables/bullets, state each fact once, no spec restatement.
- Every task independently executable by a human without AI assistance.
- Each task lists: exact file paths (Create/Modify/Test), interfaces/signatures, ordered steps, the existing codebase pattern to follow (path:line), concrete test assertions, and verification commands with expected output.
- Pseudocode or reference code only for complex or unfamiliar algorithms.
- No full code listings for routine changes. The hybrid planning contract takes precedence over any instruction to include complete code in every implementation step.
- Keep upstream Superpowers' workflow otherwise: plan location docs/superpowers/plans/, header, task/checkbox structure, TDD, self-review, execution handoff.
</tobin-superpowers-planning-preferences>"""

HTML_COMPANION = """\
<tobin-superpowers-html-companion>
When a superpowers artifact is final, offer an HTML companion once per artifact, as its own short message: "Would you like an HTML companion for this <artifact> to share with your team? (yes/no)". Final means: design spec after the user approves it; implementation plan after its self-review, before execution handoff; code review report after fixes; subagent run summary after the final review. Never generate HTML unless the user says yes; on yes, use tobin-superpowers:html-companion. Skip the offer if it was already asked for that artifact.
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
