# Cold-Cache Guard

A `UserPromptSubmit` hook (`scripts/cold-cache-guard.py`) checks the session's
last response before each prompt. If it was older than the cache lifetime (5
minutes, or 1 hour when the last write used the 1-hour cache), the prompt cache
has expired and the next request re-writes the whole context to it. When
that would cost $1 or more on the session's model, the hook stops the prompt
once and shows the size and cost, suggesting `/clear` with a short handoff
(PR, branch, plan path).

Send the prompt again to go ahead: the guard blocks once per cold period,
remembered per session under the plugin's data directory. It blocks again only
after a later response goes cold.

`/compact` doesn't help once the cache is cold: its summary request re-sends
the whole history as uncached input, so it costs about the same as the prompt.
Compact while the cache is still warm instead.

The hook never blocks a prompt that starts with `/`, and lets everything
through if it can't read the transcript. It can also stop a turn Claude Code
starts on its own (a `/loop` iteration, a background agent's report) once per
cold period; the hook input doesn't say who sent the prompt.

Cost uses Anthropic list input prices (`INPUT_USD`: Opus $4, Sonnet $2, Haiku
$0.10 per 1M tokens; unknown models price as Opus) times the cache-write
multiplier for the lifetime (`WRITE_MULTIPLIER`: 1.25× for 5 minutes, 2× for 1
hour). `BLOCK_USD` sets the threshold, at the top of the script.

The lifetime comes from the last response that wrote to the cache. If no
response in the last 2 MB of the transcript wrote to it, the guard assumes 5
minutes, so a miss can only over-warn. A response that wrote to both tiers
counts as 5 minutes. Reading only the tail keeps it fast on large transcripts.

## Recommended: the 1-hour prompt cache

Set `"promptCacheTtl": "1h"` in `~/.claude/settings.json`. Plugins can't set it.
A 1-hour write costs 2× input against 1.25× for 5 minutes. At the Opus price in
the script, a session that grows to 150K pays about $0.45 more in writes. One
avoided cold re-write at 150K ($0.75 on the 5-minute tier) covers that. See
https://code.claude.com/docs/en/prompt-caching.
