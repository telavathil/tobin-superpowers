# Cold-Cache Guard

A `UserPromptSubmit` hook (`scripts/cold-cache-guard.py`) checks the session's
last response before each prompt. If it was more than 5 minutes ago, the prompt
cache has expired and the next request re-writes the whole context to it. When
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

Cost uses Anthropic list cache-write prices (`WRITE_USD`: Opus $5, Sonnet $2.50,
Haiku $0.125 per 1M tokens; unknown models price as Opus). Thresholds are
`CACHE_MINUTES` and `BLOCK_USD` at the top of the script. It reads only the last
2 MB of the transcript, so it stays fast on large ones.
