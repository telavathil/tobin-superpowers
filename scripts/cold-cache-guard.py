#!/usr/bin/env python3
"""UserPromptSubmit hook: stop a prompt that would re-write a large, cold prompt cache.

When the last response is older than its cache lifetime (5 minutes, or 1 hour when
the last response that wrote to the cache used the 1-hour tier) and re-writing its
context would cost at least BLOCK_USD on that response's model,
blocks the prompt once and suggests /clear. /compact doesn't help once the cache
is cold: its summary request re-sends the whole history uncached. Sending the
prompt again goes through; the guard blocks once per cold period, remembered
per session under CLAUDE_PLUGIN_DATA. Slash commands always pass. Any error
lets the prompt through: always exits 0.
"""

import json
import os
import sys
from datetime import datetime, timezone

BLOCK_USD = 1.00
# Input $/1M tokens (Anthropic list price); unknown models price as Opus.
INPUT_USD = {"haiku": 0.10, "sonnet": 2.0, "opus": 4.0}
# Cache-write cost as a multiple of input price, keyed by cache lifetime in minutes.
WRITE_MULTIPLIER = {5: 1.25, 60: 2.0}
TAIL_BYTES = 2_000_000  # transcripts reach 100 MB+; the last response is near the end


def cache_minutes(usage):
    """Cache lifetime this response wrote, in minutes; None if it wrote nothing.

    5 wins over 60 when both tiers were written: the shorter lifetime governs, so a miss over-warns.
    """
    tiers = usage.get("cache_creation") or {}
    if tiers.get("ephemeral_5m_input_tokens", 0) > 0:
        return 5
    if tiers.get("ephemeral_1h_input_tokens", 0) > 0:
        return 60
    return None


def last_response(path):
    """Return (timestamp, context tokens, model, cache minutes) of the last assistant response, or None.

    Cache minutes come from the latest response that wrote to the cache; with none in the tail, 5.
    """
    with open(path, "rb") as f:
        f.seek(max(0, os.path.getsize(path) - TAIL_BYTES))
        lines = f.read().decode("utf-8", "ignore").splitlines()
    latest = None
    lifetime = None
    for line in reversed(lines):
        try:
            d = json.loads(line)
            message = d["message"] if d.get("type") == "assistant" else {}
            usage = message.get("usage")
            if not usage:
                continue
            if latest is None:
                ts = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
                context = sum(usage.get(k, 0) for k in
                              ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                latest = (ts, context, message.get("model") or "")
            lifetime = cache_minutes(usage)
            if lifetime is not None:
                break
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    if latest is None:
        return None
    return (*latest, 5 if lifetime is None else lifetime)


def write_price(model, minutes):
    family = next((f for f in INPUT_USD if f in model), "opus")
    return INPUT_USD[family] * WRITE_MULTIPLIER[minutes]


def idle_text(minutes):
    return "%dh" % (minutes // 60) if minutes >= 60 else "%dm" % minutes


def already_warned(session, ts):
    """True if this cold period (keyed by the last response time) was already blocked; records it if not."""
    path = os.path.join(os.environ.get("CLAUDE_PLUGIN_DATA") or "/tmp", "cold-cache-guard", session)
    stamp = ts.isoformat()
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == stamp:
                return True
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(stamp)
    except OSError:
        pass  # ponytail: without state the guard may block again on resend; the user can /clear
    return False


def main(now=None):
    try:
        payload = json.loads(sys.stdin.read())
        if str(payload.get("prompt") or "").lstrip().startswith("/"):
            return 0
        found = last_response(payload["transcript_path"])
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        return 0
    if not found:
        return 0
    ts, context, model, lifetime = found
    minutes = int(((now or datetime.now(timezone.utc)) - ts).total_seconds() // 60)
    cost = context * write_price(model, lifetime) / 1_000_000
    if minutes < lifetime or cost < BLOCK_USD:
        return 0
    if already_warned(str(payload.get("session_id") or "unknown"), ts):
        return 0
    json.dump({"decision": "block", "reason": (
        "Cold cache: idle %s, so this prompt re-writes %dK tokens (~$%.2f). To start small, /clear "
        "and give a short handoff (PR, branch, plan path). /compact won't help now: it re-sends the "
        "whole history too. To go ahead anyway, send it again." % (idle_text(minutes), context // 1000, cost))},
        sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
