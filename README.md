# tobin-superpowers

An extension for the official
[superpowers](https://github.com/obra/superpowers) plugin for Claude Code.

## Purpose

superpowers provides the development workflows — brainstorming, writing
plans, code review, subagent-driven development, and the rest. This plugin
does not replace or copy any of them. It adds three things on top, and
superpowers keeps working (and updating) exactly as published.

## Features

- **Hybrid implementation planning.** Every session starts with concise
  planning preferences: plans stay lean, yet each task is executable by a
  skilled developer without AI help — exact paths, interfaces, ordered
  steps, the codebase pattern to follow, concrete test assertions, and
  verification commands. Full detail lives in the
  `tobin-superpowers:hybrid-planning` skill.
- **Automatic plan validation.** When Claude writes or edits a plan in
  `docs/superpowers/plans/`, an advisory structural check runs and sends any
  gaps back to Claude.
- **Optional HTML companions.** At the end of a spec, plan, code review, or
  subagent run, Claude offers a self-contained `.html` version to share with
  your team, and creates it only if you say yes.

## Installation

Requires Claude Code with plugin support and `python3` on `PATH` (macOS,
Linux, WSL). No other dependencies.

1. Install official superpowers first (skip if you already have it):

   ```
   /plugin marketplace add obra/superpowers
   /plugin install superpowers@superpowers-dev
   ```

   If you use a different superpowers marketplace (for example the official
   Claude plugins directory), install it from there instead — this plugin
   only needs the `superpowers:*` skills to exist.

2. Install this extension:

   ```
   /plugin marketplace add telavathil/tobin-superpowers
   /plugin install tobin-superpowers@tobin-superpowers-dev
   ```

3. Restart Claude Code (or run `/reload-plugins`).

### Updating

The two plugins update independently; updating superpowers never requires
a change here.

```
/plugin marketplace update superpowers-dev
/plugin marketplace update tobin-superpowers-dev
/plugin update
```

Then restart Claude Code.

### Verifying

- `/plugin` lists `superpowers` and `tobin-superpowers` with the versions
  you expect (this plugin: `1.0.0`). From a shell: `claude plugin list` and
  `claude plugin details tobin-superpowers@tobin-superpowers-dev`.
- `tobin-superpowers` shows exactly two skills (`hybrid-planning`,
  `html-companion`) and two hooks (`SessionStart`, `PostToolUse`). All
  workflow skills come from `superpowers`.
- `/hooks` lists the `SessionStart` and `PostToolUse` (`Write|Edit`) hooks
  from this plugin.

## Workflow

1. Start Claude Code. The `SessionStart` hook loads the planning and HTML
   companion preferences (also after resume, `/clear`, compaction, and fork).
2. Use the superpowers workflows as normal — `superpowers:brainstorming`,
   `superpowers:writing-plans`, `superpowers:subagent-driven-development`,
   `superpowers:requesting-code-review`, and so on.
3. Hybrid planning preferences apply automatically whenever a plan is
   written; you do not invoke any skill.
4. Plans saved under `docs/superpowers/plans/` get advisory validation
   feedback after each `Write`/`Edit`.
5. At supported handoffs Claude asks once: *"Would you like an HTML
   companion for this … to share with your team? (yes/no)"*. Say yes to get
   a `.html` file next to the markdown; say no and the workflow continues.

**HTML offers are best-effort.** They come from instructions Claude
follows, not from a hook that guarantees completion. Claude may skip an
offer, ask at a slightly different moment, or bundle it with another
question. You can always ask directly: *"make an HTML companion for
docs/superpowers/plans/x.md"*.

## Hybrid Planning

`scripts/session-context.py` injects the preferences; the
`hybrid-planning` skill holds the full contract. It keeps superpowers'
workflow, plan location, task structure, TDD, and self-review, and takes
precedence over any instruction to include complete code in every
implementation step: pseudocode or reference code appears only for complex
or unfamiliar logic.

Tested with superpowers 7.0.0, whose `writing-plans` already favours
signatures and test assertions over full code. Older superpowers releases
asked for complete code in every step; the precedence wording covers that
case.

## Plan Validation

### Automatic (PostToolUse hook)

After Claude uses `Write` or `Edit` on a Markdown file under
`<project>/docs/superpowers/plans/`, `scripts/validate-plan-hook.py`
validates the file as it now exists on disk.

- **Clean plan:** no output at all.
- **Warnings only:** findings go to Claude (`additionalContext`).
- **Errors:** the same, plus a one-line notice for you
  (`Plan validation: N errors … (advisory; details sent to Claude)`).

The feedback is **advisory**: PostToolUse runs after the write, so it
cannot prevent or undo it, and the hook never modifies the plan. Unrelated
files are ignored. The project root is `$CLAUDE_PROJECT_DIR` (falling back
to the hook's `cwd`); paths are resolved (`..`, symlinks) before matching,
so look-alikes such as `docs/superpowers/plans-old/` are ignored.

### Manual (CLI)

```bash
python3 scripts/validate-plan.py docs/superpowers/plans/2026-10-10-feature.md [--json]
```

Exit codes: `0` no errors (warnings allowed), `1` errors, `2` bad
arguments or an unreadable file.

### What is checked

Each `Task N` section is checked on its own:

| Rule | Severity | Requires |
| --- | --- | --- |
| `files` | error | Backticked Create/Modify/Test paths, or `Files: none` |
| `interfaces` | error | Interfaces/Signatures/Produces/Consumes, or "no new interfaces" |
| `steps` | error | At least two ordered steps |
| `tests` | error (warning for docs-only tasks) | A concrete assertion or input → output case, or `No tests: <reason>` |
| `verification` | error | A runnable command (with arguments, or after a Run/Verify label) |
| `expected-result` | warning | What success looks like (`Expected: …`, `3 passed`, `PASS`) |
| `pattern` | warning | An existing code pattern to follow, or an explicit "none" |
| `inexact-path` | warning | No wildcards or `<placeholders>` in file paths |
| `placeholder` | error | No `TBD`/`TODO`/`FIXME`, "implement later", "write tests for the above" |
| `vague-instruction` | warning | No "handle edge cases", "add appropriate error handling", "similar to Task N" |
| `no-tasks` | error | At least one `Task N` section |
| `long-code` | info (CLI only) | Code blocks over 40 lines |

**Errors** mean a skilled developer could not execute or verify the task
from the text alone; **warnings** mean it is executable but weaker than the
contract asks. The checks are structural, not semantic: they confirm the
information is present, not that the plan is correct.

### Limitations

- Only `Write` and `Edit` trigger the hook. Plans written through `Bash`
  (e.g. a heredoc), MCP tools, or editors outside Claude Code are not
  validated automatically — run the CLI.
- Plans saved outside `docs/superpowers/plans/` are not validated
  automatically.
- Heuristics can produce occasional false positives or misses.

## HTML Companions

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

### Observed offer behaviour

Headless integration runs, Claude Code 2.1.296 with superpowers 7.0.0 — a
small sample, not a guarantee:

| Workflow | Offer |
| --- | --- |
| Brainstorming (spec written) | at the right handoff, as its own message (1/1) |
| Writing plans | at the right handoff (4/4), usually bundled with the execution-handoff question (3/4) |
| Code review | 1/3 runs; skipped after findings were deferred |
| Subagent-driven development | not in the standard form (0/2); once asked late in other wording |
| After "yes" (all four types) | companion written, validator 0 errors, markdown unchanged, HTML untracked |
| After "no" | no HTML; workflow continued |

### Validating a companion

```bash
python3 scripts/validate-html-companion.py docs/superpowers/plans/x.html --source docs/superpowers/plans/x.md [--json]
```

The skill runs this after generating (Claude Code may ask you to approve the
command; if it cannot run, Claude checks the key rules by hand). Errors:
external resources, missing doctype/charset/title, header (title, ISO date,
"Companion to"), footer `Source:` path, filename. Warnings: viewport,
inline script, markdown dumps, missing per-artifact structure. Exit codes
match the plan validator.

## Disable or Troubleshoot

- **Disable:** Claude Code has no per-hook switch. Disable the plugin
  (`/plugin` → `tobin-superpowers` → Disable, or
  `claude plugin disable tobin-superpowers@tobin-superpowers-dev`); superpowers
  keeps working. `"disableAllHooks": true` in settings turns off every
  plugin's hooks.
- **See hook runs:** `claude --debug hooks`, then look for
  `session-context.py` and `validate-plan-hook.py`.
- **Reproduce plan validation:**
  `echo '{"tool_name":"Write","cwd":"'"$PWD"'","tool_input":{"file_path":"docs/superpowers/plans/x.md"}}' | python3 scripts/validate-plan-hook.py`
- **No offers or preferences?** Check `/hooks` and that `python3` is on
  `PATH`.

## Repository Layout

```
tobin-superpowers/
├── .claude-plugin/
│   ├── plugin.json                # plugin manifest (1.0.0)
│   └── marketplace.json           # tobin-superpowers-dev marketplace
├── hooks/
│   └── hooks.json                 # SessionStart + PostToolUse (Write|Edit)
├── scripts/
│   ├── session-context.py         # injects planning + HTML companion preferences
│   ├── validate-plan.py           # plan validator (CLI + library)
│   ├── validate-plan-hook.py      # PostToolUse adapter for the plan validator
│   └── validate-html-companion.py # HTML companion validator (CLI + library)
├── skills/
│   ├── hybrid-planning/SKILL.md   # lean, human-executable plan contract
│   ├── html-companion/SKILL.md    # offer workflow, priorities, embedded guide
│   └── shared/html-companion-guide.md  # source of the embedded guide
├── tests/                         # python3 -m unittest discover -s tests -v
│   └── fixtures/
├── MAINTAINING.md
└── README.md
```

See [MAINTAINING.md](MAINTAINING.md) for updates, compatibility testing, and
the guide synchronization process.

## License

MIT. superpowers is also MIT.
