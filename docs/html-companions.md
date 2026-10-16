# HTML Companions

`tobin-superpowers:html-companion` turns a finished superpowers artifact
into a self-contained `.html` page next to its markdown:

| Artifact (official workflow) | Offered when |
| --- | --- |
| Design spec (`superpowers:brainstorming`) | after you approve the written spec |
| Implementation plan (`superpowers:writing-plans`) | after the plan's self-review, before execution handoff |
| Code review report (`superpowers:requesting-code-review`) | after findings are fixed or deferred; the report is saved to `docs/superpowers/reviews/` only if you accept |
| Run summary (`superpowers:subagent-driven-development`) | once, after the final review; saved to `docs/superpowers/run-summaries/` only if you accept |

Guarantees in the skill's instructions: generated only after an explicit
yes; same base name and directory as the markdown; the markdown is never
modified; the HTML is never staged or committed; no CDN, web fonts,
external scripts, or relative assets.

The skill is a single, self-contained `SKILL.md` (workflow, per-artifact
rendering priorities, and an embedded copy of
`skills/shared/html-companion-guide.md`), because Claude Code needs a
permission to read other plugin files and headless runs deny it.

## How Offers Work

At supported handoffs Claude asks once: *"Would you like an HTML companion
for this … to share with your team? (yes/no)"*. Say yes to get a `.html`
file next to the markdown; say no and the workflow continues. For a spec,
asking to move on ("write the plan", "go ahead") counts as approval: Claude
asks the question first and waits for your answer.

**Offers are best-effort.** They come from instructions Claude follows, not
from a hook that guarantees completion. Since 1.0.2 the plan and spec
reminders also arrive through the PostToolUse hook, right next to the
handoff, because session-start instructions can lose to a freshly loaded
workflow script in long sessions. Claude may skip an offer, ask at a
slightly different moment, or bundle it with another question. You can
always ask directly: *"make an HTML companion for
docs/superpowers/plans/x.md"*.

## Observed Offer Behaviour

Headless integration runs, Claude Code 2.1.296 with superpowers 7.0.0 — a
small sample, not a guarantee:

| Workflow | Offer |
| --- | --- |
| Brainstorming (spec written, user says "approved") | at the right handoff, as its own message (2/2) |
| Brainstorming, implicit approval (user says "write the plan") | 1.0.2: offer as its own message, then waits for the answer before writing-plans (2/2); an intermediate wording that said "then continue" offered but did not wait (2/2). 1.0.1: not offered (real session) |
| Writing plans | 1.0.2: as its own message before the execution handoff, after the hook's reminder (5/5). 1.0.1: bundled with the execution-handoff question (4/5) |
| Writing plans, long session | 1.0.2: offered before the handoff after 30 prior tool calls (1/1) and after `/compact` (1/1). 1.0.1: missed in a real ~420-entry session |
| Code review | 1.0.1: right after the user defers the findings, own message (2/2); not while findings are open. 1.0.0 wording: 1/4 |
| Subagent-driven development | 1.0.1: in the run-completion message (2/2). 1.0.0 wording: 1/3 |
| After "yes" (all four types) | companion written, validator 0 errors, markdown unchanged, HTML untracked |
| After "no" | no HTML; workflow continued |

## Validating a Companion

```bash
python3 scripts/validate-html-companion.py docs/superpowers/plans/x.html --source docs/superpowers/plans/x.md [--json]
```

The skill runs this after generating (Claude Code may ask you to approve the
command; if it cannot run, Claude checks the key rules by hand). Errors:
external resources, missing doctype/charset/title, header (title, ISO date,
"Companion to"), footer `Source:` path, filename. Warnings: viewport,
inline script, markdown dumps, missing per-artifact structure. Exit codes
match the plan validator.
