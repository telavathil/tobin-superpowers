# Stale-Session Reminder

A `UserPromptSubmit` hook (`scripts/stale-session-reminder.py`) checks the
session's last response before each prompt. If it was more than an hour ago
and its context was over 150K tokens, you see one line suggesting `/compact`
with a focus on the PR, branch, plan and open decisions.

Why: the prompt cache lasts five minutes. After a break, the next turn writes
the whole context to the cache again, and every later turn reads all of it.
Keeping one session per repo and returning to it for review fixes makes both
large. Compacting first keeps what the session knows and drops most of the size.

The message is shown to you only; Claude doesn't see it. The hook never blocks
a prompt and stays silent on recent or small sessions, or if it can't read the
transcript. The turn that shows the reminder has already been sent, so the
saving starts from the next turn.

Thresholds are `IDLE_MINUTES` and `MIN_CONTEXT` at the top of the script. It
reads only the last 2 MB of the transcript, so it stays fast on large ones.
