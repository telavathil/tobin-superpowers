# tobin-superpowers

A personal fork of [obra/superpowers](https://github.com/obra/superpowers)
that adds an optional **HTML companion** step to four skills:

- `brainstorming`
- `writing-plans`
- `requesting-code-review`
- `subagent-driven-development`

## What and Why

Superpowers skills produce markdown specs, plans, and reports. Markdown is
the right format for agent consumption — it stays the artifact of record
and is never modified by this fork.

But markdown is awkward to share with a human teammate in Slack or email.
This fork adds one optional step at the end of each of the four skills:
*"Would you like an HTML companion to share with your team?"*. If accepted,
a self-contained `.html` file is written next to the markdown.

The HTML companion is:

- Self-contained (no CDN, no external fonts, no relative assets)
- Opens correctly by double-clicking in a file browser
- Re-laid-out for human reading (not a markdown-to-HTML dump)
- Left unstaged — the user decides whether to commit it

The shared rules for HTML output — output paths, style, color palette, and
the HTML skeleton — live in
[`skills/shared/html-companion-guide.md`](skills/shared/html-companion-guide.md).
Skill-specific rendering priorities now live in the standalone
`html-companion` skill (see [HTML Companions](#html-companions)); the copies
inside the four forked `SKILL.md` files remain until Phase 4.

## Installation

In Claude Code, with [`superpowers`](https://github.com/obra/superpowers)
already installed.

### Option A — install from GitHub (after pushing)

```
/plugin marketplace add telavathil/tobin-superpowers
/plugin install tobin-superpowers@tobin-superpowers-dev
```

The first command registers this repo's `.claude-plugin/marketplace.json`
as a marketplace named `tobin-superpowers-dev`. The second installs the
`tobin-superpowers` plugin from that marketplace.

### Option B — install from a local clone (for dogfooding)

```
/plugin marketplace add ~/dev/tobin-superpowers
/plugin install tobin-superpowers@tobin-superpowers-dev
```

Same flow, but the marketplace points at a local working tree. Useful
while iterating on the fork before pushing.

After install: when this plugin is active alongside `superpowers`, the
four modified skills override their upstream equivalents. The other ten
superpowers skills are unchanged and continue to come from upstream.

## How the Fork Is Structured

Each modified `SKILL.md` is the upstream version *verbatim* except for a
clearly fenced HTML companion block. The block is delimited by:

```
<!-- tobin-superpowers:html-companion:start -->
...added content...
<!-- tobin-superpowers:html-companion:end -->
```

Two such blocks may exist per file: one short reference in the procedural
flow (the checklist item or the new section heading), and one full
"HTML Companion (Personal Fork)" section containing the offer text and
rendering priorities.

To pull an upstream update for a forked skill: replace everything *outside*
the fenced blocks with the new upstream content. The fenced blocks remain
unchanged unless the shared HTML companion guide also evolves.

## Repo Layout

```
tobin-superpowers/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── hooks/
│   └── hooks.json                 # SessionStart + PostToolUse registration
├── scripts/
│   ├── session-context.py         # injects planning + HTML companion preferences
│   ├── validate-plan.py           # standalone plan validator (CLI + library)
│   ├── validate-plan-hook.py      # PostToolUse adapter for the validator
│   └── validate-html-companion.py # HTML companion validator (CLI + library)
├── skills/
│   ├── hybrid-planning/
│   │   └── SKILL.md               # lean, human-executable plan contract
│   ├── html-companion/
│   │   └── SKILL.md               # offer workflow, per-artifact priorities, embedded guide
│   ├── shared/
│   │   └── html-companion-guide.md
│   ├── brainstorming/
│   │   ├── SKILL.md
│   │   ├── visual-companion.md
│   │   ├── spec-document-reviewer-prompt.md
│   │   └── scripts/
│   ├── writing-plans/
│   │   ├── SKILL.md
│   │   └── plan-document-reviewer-prompt.md
│   ├── requesting-code-review/
│   │   ├── SKILL.md
│   │   └── code-reviewer.md
│   └── subagent-driven-development/
│       ├── SKILL.md
│       ├── implementer-prompt.md
│       ├── spec-reviewer-prompt.md
│       └── code-quality-reviewer-prompt.md
├── tests/                         # python3 -m unittest discover -s tests -v
│   ├── test_session_context.py
│   ├── test_validate_plan.py
│   ├── test_validate_plan_hook.py
│   ├── test_validate_html_companion.py
│   ├── test_html_companion_skill.py
│   └── fixtures/                  # plan fixtures; companions/ HTML fixtures
├── MAINTAINING.md
└── README.md
```

## Hybrid Planning Hook

A `SessionStart` hook (`hooks/hooks.json` → `scripts/session-context.py`)
injects concise planning preferences on startup, resume, clear, compact,
and fork. They point Claude at the `tobin-superpowers:hybrid-planning`
skill, which layers a lean, human-executable plan contract on top of
upstream `superpowers:writing-plans`. The contract takes precedence over
any instruction to include complete code in every implementation step.

Requires `python3` on `PATH` (macOS, Linux, WSL). The `fork` source needs
Claude Code v2.1.214 or later; older versions report forks as `resume`,
which is also matched.

### Upstream compatibility

Tested with `superpowers` **7.0.0** (from the `obra/superpowers`
marketplace) and Claude Code 2.1.296. In 7.0.0, `writing-plans` already
favours signatures and test assertions over full code, so it agrees with
the hybrid contract.

Older `superpowers` releases — including the copy forked into this repo at
`skills/writing-plans/` — still require "complete code in every step".
The injected precedence wording overrides that, but if you see plans with
full code listings for routine changes, check which `writing-plans` was
invoked and which upstream version is installed.

## Plan Validation

Implementation plans get an advisory structural check automatically — no
skill to invoke.

### Automatic (PostToolUse hook)

After Claude uses the `Write` or `Edit` tool on a Markdown file under
`<project>/docs/superpowers/plans/`, `scripts/validate-plan-hook.py` runs
the validator on the file as it now exists on disk.

- **Clean plan:** no output at all.
- **Warnings only:** the findings are added to Claude's context
  (`additionalContext`) so it can tighten the plan.
- **Errors:** the same, plus a one-line notice for you
  (`Plan validation: N errors … (advisory; details sent to Claude)`).

The feedback is **advisory**. PostToolUse runs after the write has
happened, so it cannot prevent or undo it, and the hook never modifies or
deletes the plan. Unrelated files are ignored; an unexpected internal
error shows a one-line non-blocking notice and never stops your session.

The project root is `$CLAUDE_PROJECT_DIR` (falling back to the hook's
`cwd`). Paths are resolved (`..`, symlinks) before matching, and only
`docs/superpowers/plans/` directly under the root counts — look-alikes such
as `docs/superpowers/plans-old/` or `vendor/docs/superpowers/plans/` are
ignored.

### Manual (CLI)

```bash
python3 scripts/validate-plan.py docs/superpowers/plans/2026-10-10-feature.md
python3 scripts/validate-plan.py docs/superpowers/plans/2026-10-10-feature.md --json
```

Output is one line per finding — `path:LINE: severity [rule] Task N: message`
followed by `fix: suggestion` — and a summary. Exit codes: `0` no errors
(warnings allowed), `1` errors, `2` bad arguments or an unreadable /
non-UTF-8 file. The CLI validates any path you give it and adds an `info`
note if the file is outside `docs/superpowers/plans/`.

### What is checked

Each `Task N` heading (levels 2–4) is checked on its own:

| Rule | Severity | Requires |
| --- | --- | --- |
| `files` | error | Backticked Create/Modify/Test paths, or `Files: none` |
| `interfaces` | error | Interfaces/Signatures/Produces/Consumes, or "no new interfaces" |
| `steps` | error | At least two ordered steps (checkboxes, numbered list, `Step N`) |
| `tests` | error (warning for docs-only tasks) | A concrete assertion or input → output case, or `No tests: <reason>` |
| `verification` | error | A runnable command (`pytest`, `python3 -m …`, `npm test`, a shell block …) |
| `expected-result` | warning | What success looks like (`Expected: …`, `3 passed`, `PASS`) |
| `pattern` | warning | An existing code pattern to follow, or an explicit "none" |
| `inexact-path` | warning | No wildcards or `<placeholders>` in file paths |
| `placeholder` | error | No `TBD`/`TODO`/`FIXME`, "implement later", "write tests for the above" |
| `vague-instruction` | warning | No "handle edge cases", "add appropriate error handling", "similar to Task N" |
| `no-tasks` | error | At least one `Task N` section |
| `long-code` | info (CLI only) | Flags code blocks over 40 lines |

**Errors** mean a skilled developer could not execute or verify the task
from the text alone. **Warnings** mean the task is executable but weaker
than the hybrid planning contract asks for. **Info** is never sent to
Claude by the hook.

Equivalent phrasing is accepted (e.g. `Signatures:` for `Interfaces:`, a
numbered list for checkboxes). Complete code listings are never required,
and pseudocode passes. Placeholders inside code blocks and inline code are
ignored.

**Structural, not semantic:** the validator checks that the information is
present, not that the plan is correct, the paths exist, or the tests are
meaningful. Review still matters.

### Coverage limitations

- Only `Write` and `Edit` tool calls trigger the hook. Plans created or
  changed through `Bash` (e.g. `cat > plan.md <<EOF`, `sed -i`), MCP tools,
  subagents in other sessions, or editors outside Claude Code are **not**
  validated automatically — run the CLI by hand. (Claude has been observed
  writing plans with a Bash heredoc first.)
- Plans saved somewhere other than `docs/superpowers/plans/` (upstream lets
  user preferences override the location) are not validated automatically.
- Heuristics are regex-based. Unusual formatting can produce a false
  positive or miss; the feedback says "advisory" for that reason.

### Disable or troubleshoot

- **Disable:** there is no per-hook switch in Claude Code. Disable the whole
  plugin (`/plugin` → `tobin-superpowers` → Disable, or
  `claude plugin disable tobin-superpowers@tobin-superpowers-dev`), or set
  `"disableAllHooks": true` in settings to turn off every hook.
- **Check registration:** `/hooks` should list `PostToolUse` (`Write|Edit`)
  and `SessionStart` from this plugin.
- **See hook runs:** start `claude --debug` (or `--debug hooks`) and look for
  `validate-plan-hook.py`.
- **Reproduce by hand:** pipe a payload into the adapter —
  `echo '{"tool_name":"Write","cwd":"'"$PWD"'","tool_input":{"file_path":"docs/superpowers/plans/x.md"}}' | python3 scripts/validate-plan-hook.py`.
- Requires `python3` on `PATH`.

## HTML Companions

The standalone `tobin-superpowers:html-companion` skill turns a finished
superpowers artifact into a self-contained `.html` page next to its
markdown. It works with the official `superpowers` skills; it does not need
the forked copies in this repo.

| Artifact | Offered when |
| --- | --- |
| Design spec | after you approve the written spec |
| Implementation plan | after the plan's self-review, before execution handoff |
| Code review report | after review fixes (the report is saved to `docs/superpowers/reviews/` only if you accept) |
| Subagent run summary | once, after the final review (saved to `docs/superpowers/run-summaries/` only if you accept) |

The skill is a single `SKILL.md`: the workflow, a "Companion: …" section per
artifact with the rendering priorities migrated from the forked skills, and
a verbatim copy of `skills/shared/html-companion-guide.md` (a test keeps the
copy in sync). It is deliberately self-contained — Claude Code delivers a
skill's own text without a file-read permission, but reading other plugin
files from outside the project needs one, which headless runs deny.

### How the offer happens

The `SessionStart` hook adds a short instruction to every session: when one
of those artifacts is final, ask once — *"Would you like an HTML companion
for this … to share with your team? (yes/no)"* — and only on **yes** use the
skill. There is no file-write hook for offers.

This is instruction-following, not enforcement. Claude may skip the offer,
ask at a slightly different moment, or bundle it with another question;
with a forked skill also active it sees two copies of the instruction and is
told to ask only once per artifact. You can always ask directly: *"make an
HTML companion for docs/superpowers/plans/x.md"*.

Observed in headless integration runs (Claude Code 2.1.296, superpowers
7.0.0) — a small sample, not a guarantee:

| Scenario | Result |
| --- | --- |
| `writing-plans`, 3 runs | offered 3/3; 1/3 as its own message, 2/3 bundled with the execution-handoff question; no HTML generated unasked |
| `requesting-code-review`, 2 runs | offered 1/2 (the other held back while an Important finding was unresolved); no HTML generated |
| answered "no" | no HTML, workflow continued |
| answered "yes" | HTML written next to the plan, plan unchanged, HTML untracked and unstaged, validator 0 errors |

### Guarantees the skill enforces

- Generated only after an explicit yes.
- Same base name and directory as the markdown, `.html` extension.
- The source markdown is never modified; the HTML is never staged or
  committed.
- Self-contained: no CDN, web fonts, external scripts, or relative assets.

### Validating a companion

The skill runs this after generating (Claude Code may ask you to approve the
command; if it cannot run, Claude checks the key rules by hand). You can run
it yourself:

```bash
python3 scripts/validate-html-companion.py docs/superpowers/plans/x.html --source docs/superpowers/plans/x.md
```

Exit codes match the plan validator (`0` no errors, `1` errors, `2` bad
input); `--json` gives machine-readable output.

| Rule | Severity | Checks |
| --- | --- | --- |
| `external-resource` | error | No `<link href>`, `<script src>`, `@import`, `url(…)`, `@font-face`, `<img>/<iframe>/<object>/<source>` assets, or `<base>` — only `data:` URIs and `#` anchors |
| `doctype`, `charset`, `title` | error | `<!DOCTYPE html>`, `<meta charset>`, non-empty `<title>` |
| `header` | error | `<header>` with `<h1>`, a "Companion to …" label, and an ISO date |
| `footer-source` | error | Footer `Source: <relative path>.md` naming this companion's markdown |
| `filename` | error with `--source`, else warning | Same base name and directory as the markdown |
| `viewport`, `script` | warning | Viewport meta present; no inline JavaScript |
| `markdown-dump` | warning | No single `<pre>` holding most of the page, no raw markdown syntax |
| `type-structure` | warning | Elements the artifact's rendering priorities call for (`.toc`, `.checklist`, `.pill`) |

The validator is structural: it cannot judge layout quality, accuracy, or
whether the rendering priorities were followed well.

## Versioning

Versioned independently from upstream `superpowers`. When a superpowers
release updates one of the four modified skills, review the upstream diff
and merge non-companion changes by hand.

See [`MAINTAINING.md`](MAINTAINING.md) for the full step-by-step upstream
merge workflow, including the verification commands and the one known
brainstorming-checklist gotcha.

## License

MIT. Upstream `superpowers` is also MIT.
