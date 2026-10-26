#!/usr/bin/env python3
"""UserPromptSubmit hook: remind before working in a large session whose prompt cache expired.

When the last response is older than IDLE_MINUTES and its context was over
MIN_CONTEXT tokens, prints a systemMessage suggesting /compact. The cache has
expired by then, so every turn re-writes the whole context. Shown to the user
only; never blocks: always exits 0, and unreadable input produces no output.
"""

import json
import os
import sys
from datetime import datetime, timezone

IDLE_MINUTES = 60
MIN_CONTEXT = 150_000
TAIL_BYTES = 2_000_000  # transcripts reach 100 MB+; the last response is near the end


def last_response(path):
    """Return (timestamp, context tokens) of the last assistant response, or None."""
    with open(path, "rb") as f:
        f.seek(max(0, os.path.getsize(path) - TAIL_BYTES))
        lines = f.read().decode("utf-8", "ignore").splitlines()
    for line in reversed(lines):
        try:
            d = json.loads(line)
            usage = d["message"]["usage"] if d.get("type") == "assistant" else None
            if usage:
                ts = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
                return ts, sum(usage.get(k, 0) for k in
                               ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        except (ValueError, KeyError, TypeError):
            continue
    return None


def idle_text(minutes):
    return "%dh" % (minutes // 60) if minutes >= 60 else "%dm" % minutes


def main(now=None):
    try:
        path = json.loads(sys.stdin.read())["transcript_path"]
        found = last_response(path)
    except (ValueError, KeyError, TypeError, OSError):
        return 0
    if not found:
        return 0
    ts, context = found
    minutes = int(((now or datetime.now(timezone.utc)) - ts).total_seconds() // 60)
    if minutes >= IDLE_MINUTES and context >= MIN_CONTEXT:
        json.dump({"systemMessage": (
            "Session is %dK tokens and idle %s, so its prompt cache has expired and every turn "
            "re-writes the whole context. Consider /compact (focus: the PR, branch, plan and open "
            "decisions) before the next turn." % (context // 1000, idle_text(minutes)))}, sys.stdout)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
