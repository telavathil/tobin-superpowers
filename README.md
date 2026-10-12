# tobin-superpowers

[![CI](https://github.com/telavathil/tobin-superpowers/actions/workflows/ci.yml/badge.svg)](https://github.com/telavathil/tobin-superpowers/actions/workflows/ci.yml)

An extension for the official
[superpowers](https://github.com/obra/superpowers) plugin for Claude Code.

## Purpose

superpowers provides the development workflows — brainstorming, writing
plans, code review, subagent-driven development, and the rest. This plugin
does not replace or copy any of them. It adds the features below, and
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
  gaps back to Claude. Once a plan has no errors, and whenever a spec is
  written, the same hook reminds Claude to offer the HTML companion at the
  handoff.
- **Optional HTML companions.** At the end of a spec, plan, code review, or
  subagent run, Claude offers a self-contained `.html` version to share with
  your team, and creates it only if you say yes.
- **Skill promotion.** A manual `tobin-superpowers:promote-skill` workflow
  turns an existing or described skill into a portable candidate, reviews it
  with you, and guides a local import into this plugin after your explicit
  approval. It never commits, pushes, or opens a pull request.
- **Code standards at plan time.** When a plan-writing skill runs, your
  code standards are injected so the plan follows them. The first plan in
  a repo also gets a one-off lint baseline check.
- **New-package prompt.** Before an install command adds a package that
  isn't in the project's manifest, Claude Code asks you to confirm it. This
  guards against hallucinated (slopsquatted) package names.

## Installation

Requires Claude Code with plugin support and `python3` (3.11+) on `PATH`
(macOS, Linux, WSL). No other dependencies. CI runs the test suite on Linux,
macOS, and Windows; on native Windows the hooks still need a `python3`
executable on `PATH`.

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
  you expect (this plugin: `1.2.0`). From a shell: `claude plugin list` and
  `claude plugin details tobin-superpowers@tobin-superpowers-dev`.
- `tobin-superpowers` shows its three skills (`hybrid-planning`,
  `html-companion`, `promote-skill`), plus any you promoted, and three hook
  events (`SessionStart`, `PreToolUse`, `PostToolUse`). All workflow skills
  come from `superpowers`.
- `/hooks` lists these hooks from this plugin: `SessionStart`, `PreToolUse`
  on `Skill` (two commands) and on `Bash`, and `PostToolUse` on
  `Write|Edit`.

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
   For a spec, asking to move on ("write the plan", "go ahead") counts as
   approval: Claude asks the question first and waits for your answer.

**HTML offers are best-effort.** They come from instructions Claude
follows, not from a hook that guarantees completion. Since 1.0.2 the plan
and spec reminders also arrive through the PostToolUse hook, right next to
the handoff, because session-start instructions can lose to a freshly
loaded workflow script in long sessions. Claude may skip an
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

## Code Standards

`standards/` holds personal code standards (`index.yml` plus
`global/*.md`). A `PreToolUse` hook on the `Skill` tool injects them into
context whenever a plan-writing skill (`writing-plans` or `plan`, with or
without a plugin prefix) is invoked. Plans are written against them and copy
the binding rules into Global Constraints. The hook only informs and always
exits 0.

Claude Code moves any single hook's context over 10,000 characters to a
file and shows Claude only a preview, so `hooks.json` runs
`inject-plan-standards.py` twice: `1` sends the header, `index.yml` and the
first half of `global/`, and `2` sends the rest.

### Lint baseline check

The first plan in a repo also tells Claude to follow `lint/check.md`: compare
the repo's lint configs with the baselines in `lint/`, ask once where
out-of-scope work is recorded (the debt location), and report the gaps.
Claude then writes the result to a per-repo marker file:

```
${CLAUDE_PLUGIN_DATA}/repos/<repo-path-with-dashes>.md
```

`CLAUDE_PLUGIN_DATA` is usually
`~/.claude/plugins/data/tobin-superpowers-tobin-superpowers-dev`. Later plans
inject the marker instead of the check. Git worktrees share their main
repo's marker. Outside a git repo, or without `CLAUDE_PLUGIN_DATA`, the
check is skipped. To run the check again, delete the repo's marker file.

## New-Package Prompt

A `PreToolUse` hook on `Bash` (`scripts/ask-new-package.py`) reads install
commands and asks you to confirm any package that isn't in the nearest
manifest:

| Commands | Manifest |
| --- | --- |
| `npm install`/`i`/`add`, `pnpm add`/`install`, `yarn add` | `package.json` (all dependency sections) |
| `go get` | `go.mod` (subpackages of a listed module count as listed) |
| `pip`/`pip3 install`, `python -m pip install`, `uv add`, `uv pip install`, `poetry add` | `pyproject.toml` and `requirements*.txt` |

It handles chained commands (`&&`, `;`, `|`), `sudo`, `env` and `NAME=value`
prefixes, and normalises Python names. The manifest is searched upward from
the session's working directory. The hook only ever answers "ask": it never
blocks or approves a command, and it stays silent for listed packages and
other commands. If the check itself fails, it asks.

Not covered: `npx`, `bunx`, `uvx`, `pipx`, `go install`, `bun add`,
`yarn global add`, a `cd` earlier in the same command, and commands hidden
behind `bash -c`, `time` or `nohup`.

## Plan Validation

### Automatic (PostToolUse hook)

After Claude uses `Write` or `Edit` on a Markdown file under
`<project>/docs/superpowers/plans/`, `scripts/validate-plan-hook.py`
validates the file as it now exists on disk.

- **Errors:** findings go to Claude (`additionalContext`), plus a one-line
  notice for you (`Plan validation: N errors … (advisory; details sent to
  Claude)`).
- **No errors** (clean, or warnings only): any warnings go to Claude, followed
  by a reminder — *"Plan has no validation errors. Run the self-review, then
  offer the HTML companion as its own message before the execution handoff
  (skip if already offered for this plan)."* No notice for you.

The same hook reacts to Markdown writes under
`<project>/docs/superpowers/specs/` with one line for Claude: *"When the user
approves this spec, or asks to continue to the plan, offer the HTML
companion as its own message first and wait for the answer before starting
the plan (skip if already offered for this spec)."* Specs are not validated.

The feedback is **advisory**: PostToolUse runs after the write, so it
cannot prevent or undo it, and the hook never modifies the plan or spec.
Other files produce no output. The project root is `$CLAUDE_PROJECT_DIR` (falling back
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
| `dependencies` | warning | Tasks after the first: a `Dependencies:` line (or "none"), "depends on Task N", or a `Consumes:` line naming an earlier task |
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
| Brainstorming (spec written, user says "approved") | at the right handoff, as its own message (2/2) |
| Brainstorming, implicit approval (user says "write the plan") | 1.0.2: offer as its own message, then waits for the answer before writing-plans (2/2); an intermediate wording that said "then continue" offered but did not wait (2/2). 1.0.1: not offered (real session) |
| Writing plans | 1.0.2: as its own message before the execution handoff, after the hook's reminder (5/5). 1.0.1: bundled with the execution-handoff question (4/5) |
| Writing plans, long session | 1.0.2: offered before the handoff after 30 prior tool calls (1/1) and after `/compact` (1/1). 1.0.1: missed in a real ~420-entry session |
| Code review | 1.0.1: right after the user defers the findings, own message (2/2); not while findings are open. 1.0.0 wording: 1/4 |
| Subagent-driven development | 1.0.1: in the run-completion message (2/2). 1.0.0 wording: 1/3 |
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

## Skill Promotion

`promote-skill` turns one Claude Code skill — an existing local skill or a
description of one — into a portable, company-independent candidate, reviews
it with you, and, only after your explicit approval and a separate transfer
authorization, guides a local import into a tobin-superpowers checkout. It
is manual: it has no hook and Claude never loads it on its own.

```
/tobin-superpowers:promote-skill
```

### Modes

- **Source mode** — you name a local skill folder. Claude reads only that
  folder, read-only, and writes the candidate fresh; the source is never
  modified and its scripts are never run.
- **Personal mode** — no source files. Claude works from a description you
  are authorized to give, a public reference, or material you confirm you
  may use. This is also the clean-room route Claude offers whenever
  permission to reuse the source is unclear.

Both follow the same lifecycle: Discover → Assess → Design → Prepare →
Validate → Review → Approve → Guided Import.

### Staging and review

The candidate is built in a staging folder you choose (keep it outside work
repositories and outside the destination checkout):

```
skill-promotion/
├── manifest.json   # schema_version 1: name, description, mode, requires, files,
│                   # validation_commands, status, approval
├── REVIEW.md       # purpose, inventory, preserved, portability changes, exclusions,
│                   # remaining dependencies, validation results, risks, approval
└── skill/
    ├── SKILL.md
    └── references/ scripts/ tests/   # only when needed
```

The manifest never holds source paths, employer names, internal URLs or
credentials. Check a candidate (or, read-only, a source skill folder) with:

```bash
python3 scripts/validate-portable-skill.py path/to/skill-promotion [--deny-terms private-terms.txt] [--json]
```

It checks structure and frontmatter, name rules (no official superpowers or
built-in names), listed and referenced files, symlinks and path escapes,
undeclared Python dependencies, the manifest schema, REVIEW.md sections, and
that the approval record still matches the files. Its portability scan flags
absolute machine paths, private hosts and internal URLs, credential-like
strings (values are never printed), organisation config such as private
registries, and confidentiality notices; `--deny-terms` adds your own
employer or project names from a file kept outside the candidate. It reads
files only — it never runs candidate scripts or the manifest's
`validation_commands`; Claude asks before running those.

Review ends in `approved`, `needs-changes` or `blocked`, and the outcome is
yours.

### Approval and transfer

Approval is explicit and recorded only after you say so; a passing
validator never sets it. Claude then asks two more, separate questions: may
the candidate be copied into your tobin-superpowers checkout (transfer), and
may it be published (push or pull request, default no). Approval does not
imply either. The manifest stores a SHA-256 digest of the approved files;
any later change invalidates the approval.

### Guided import

```bash
python3 scripts/import-portable-skill.py path/to/skill-promotion --dest /path/to/tobin-superpowers           # plan only
python3 scripts/import-portable-skill.py path/to/skill-promotion --dest /path/to/tobin-superpowers --apply   # after you confirm
```

Claude asks for the checkout path and has you confirm it. The importer
refuses unless the candidate validates, is approved, matches its digest and
has transfer authorization; it also refuses a destination that is not a
tobin-superpowers checkout root, has uncommitted changes (use
`--worktree PATH` to work in a separate git worktree instead), already has
the branch, or already has `skills/<name>/` (`--allow-overwrite` only after
you approve replacing it; built-in and official superpowers skills are never
replaced). With `--apply` it creates `promote-skill/<name>`, copies exactly
the manifest's files into `skills/<name>/`, and runs the candidate
validator, the repository test suite and `claude plugin validate --strict`
(when `claude` is on `PATH`). It never commits, pushes, tags, opens a pull
request, or changes versions — those stay with you. If the checkout is
unavailable, the candidate stays in staging with instructions to re-run.

### Limitations

- The portability scan is pattern-based and advisory. It misses what it has
  no pattern for (people, project code words, paraphrased internal details)
  and can flag harmless text; read every file yourself.
- Portability does not establish permission to reuse employer-owned
  material, and no automated check establishes ownership or guarantees
  confidentiality.
- The digest proves the files are unchanged since approval was recorded; a
  script cannot prove that a human approved.
- Imported skills with `references/` or `scripts/` need read or command
  permissions when they run, which headless sessions deny by default.
- An imported skill reaches installed copies only after you commit it and,
  if you choose, bump the plugin version.

## Disable or Troubleshoot

- **Disable:** Claude Code has no per-hook switch. Disable the plugin
  (`/plugin` → `tobin-superpowers` → Disable, or
  `claude plugin disable tobin-superpowers@tobin-superpowers-dev`); superpowers
  keeps working. `"disableAllHooks": true` in settings turns off every
  plugin's hooks.
- **See hook runs:** `claude --debug hooks`, then look for
  `session-context.py`, `inject-plan-standards.py`, `ask-new-package.py` and
  `validate-plan-hook.py`.
- **Reproduce plan validation:** (a plan without errors shows the offer reminder)
  `echo '{"tool_name":"Write","cwd":"'"$PWD"'","tool_input":{"file_path":"docs/superpowers/plans/x.md"}}' | python3 scripts/validate-plan-hook.py`
- **Reproduce the spec reminder:** (the file must exist)
  `echo '{"tool_name":"Write","cwd":"'"$PWD"'","tool_input":{"file_path":"docs/superpowers/specs/x.md"}}' | python3 scripts/validate-plan-hook.py`
- **Reproduce the standards injection:** (run with `2` for the second half)
  `echo '{"tool_input":{"skill":"writing-plans"},"cwd":"'"$PWD"'"}' | python3 scripts/inject-plan-standards.py 1`
- **Reproduce the new-package prompt:**
  `echo '{"tool_input":{"command":"npm i left-padd"},"cwd":"'"$PWD"'"}' | python3 scripts/ask-new-package.py`
- **No offers or preferences?** Check `/hooks` and that `python3` is on
  `PATH`.

## Repository Layout

```
tobin-superpowers/
├── .claude-plugin/
│   ├── plugin.json                # plugin manifest (1.2.0)
│   └── marketplace.json           # tobin-superpowers-dev marketplace
├── hooks/
│   └── hooks.json                 # SessionStart + PreToolUse (Skill, Bash) + PostToolUse (Write|Edit)
├── scripts/
│   ├── session-context.py         # injects planning + HTML companion preferences
│   ├── inject-plan-standards.py   # injects standards/ when a plan skill runs
│   ├── ask-new-package.py         # asks before installing a package not in the manifest
│   ├── task-brief.sh              # task brief helper
│   ├── validate-plan.py           # plan validator (CLI + library)
│   ├── validate-plan-hook.py      # PostToolUse adapter for the plan validator
│   ├── validate-html-companion.py # HTML companion validator (CLI + library)
│   ├── validate-portable-skill.py # promote-skill candidate checks (read-only)
│   └── import-portable-skill.py   # guided local import (plan, then --apply)
├── standards/                     # code standards injected at plan time
│   ├── index.yml
│   └── global/*.md
├── lint/                          # lint baselines, read on demand (never injected)
│   └── check.md, typescript.md, go.md, python.md
├── skills/
│   ├── hybrid-planning/SKILL.md   # lean, human-executable plan contract
│   ├── html-companion/SKILL.md    # offer workflow, priorities, embedded guide
│   ├── promote-skill/SKILL.md     # manual skill promotion workflow
│   └── shared/html-companion-guide.md  # source of the embedded guide
├── tests/                         # python3 -m unittest discover -s tests -v
│   └── fixtures/                  # promote/: synthetic diagram-as-code skill
├── MAINTAINING.md
└── README.md
```

See [MAINTAINING.md](MAINTAINING.md) for updates, compatibility testing, and
the guide synchronization process.

## License

MIT. superpowers is also MIT.
