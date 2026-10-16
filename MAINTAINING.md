# Maintaining tobin-superpowers

tobin-superpowers is an independent extension. It owns only its own files —
`hooks/`, `scripts/`, `standards/`, `lint/`, `skills/hybrid-planning/`, `skills/html-companion/`,
`skills/promote-skill/`, `skills/shared/`, and `tests/` — plus any skills you
import with `promote-skill`, each in its own `skills/<name>/`. Official superpowers is installed and updated
separately; nothing here is copied from it or merged with it.

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
├── docs/                          # per-feature user docs linked from the README
├── tests/                         # python3 -m unittest discover -s tests -v
│   └── fixtures/                  # promote/: synthetic diagram-as-code skill
├── MAINTAINING.md
└── README.md
```

## Updating This Plugin

1. Make the change with tests first, then run the full suite:

   ```bash
   python3 -m unittest discover -s tests -v
   ```

2. Bump the version in **both** `.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json` (the plugin entry). Claude Code caches
   plugins by version, so an unchanged version may not reach existing
   installs. `tests/test_independent_extension.py` checks the two agree and
   pins the current version — update that expectation in the same change.
3. Push, then on each machine:

   ```
   /plugin marketplace update tobin-superpowers-dev
   /plugin update
   ```

   Restart Claude Code and confirm the version in `/plugin`.

## Testing Compatibility With a New superpowers Release

superpowers updates on its own schedule and should never require a change
here. When a new release lands, confirm that in an isolated Claude Code
configuration, so your real setup is untouched:

```bash
export CLAUDE_CONFIG_DIR="$(mktemp -d)"
claude plugin marketplace add obra/superpowers
claude plugin marketplace add /path/to/tobin-superpowers      # or telavathil/tobin-superpowers
claude plugin install superpowers@superpowers-dev
claude plugin install tobin-superpowers@tobin-superpowers-dev
claude plugin list
claude plugin details superpowers@superpowers-dev
claude plugin details tobin-superpowers@tobin-superpowers-dev
```

Then check, in a scratch git repository:

1. **Skill resolution.** `superpowers:brainstorming`, `superpowers:writing-plans`,
   `superpowers:requesting-code-review`, and
   `superpowers:subagent-driven-development` still exist (the workflow names
   this plugin's instructions refer to), and `tobin-superpowers` lists
   `hybrid-planning`, `html-companion` and `promote-skill` (plus any skills
   you promoted).
2. **SessionStart.** Run
   `claude -p "Reply ok" --output-format stream-json --verbose --include-hook-events`
   and confirm the `SessionStart` hook response contains
   `<tobin-superpowers-planning-preferences>` and
   `<tobin-superpowers-html-companion>`.
3. **Plan format.** Run `superpowers:writing-plans` on a small spec. The plan
   should land in `docs/superpowers/plans/`, follow the hybrid contract, and
   pass `python3 scripts/validate-plan.py <plan>`. If upstream changed the
   plan format, also run the validator over upstream's own
   `docs/superpowers/plans/*.md`: `interfaces` and `pattern` findings there
   are expected (those plans predate the hybrid contract), but a
   `placeholder` error or a `files` error on a task that clearly lists files
   is a validator bug — fix the heuristic and add a regression test.
4. **Plan validation hook.** Write a deliberately incomplete plan (for
   example `tests/fixtures/incomplete-plan.md`) into `docs/superpowers/plans/`
   with the `Write` tool and confirm the feedback arrives.
5. **HTML companions.** For each of the four workflows, note whether the
   offer appears at the handoff, once, without derailing the workflow; answer
   "yes" once and run `python3 scripts/validate-html-companion.py <html>
--source <md>`, confirm the markdown is unchanged and the HTML untracked.
   Offers are best-effort — record the results in the "Observed offer
   behaviour" table in `docs/html-companions.md` rather than treating a miss
   as a release blocker.
6. **Artifact paths.** If upstream moves specs or plans out of
   `docs/superpowers/specs/` and `docs/superpowers/plans/`, update the hook's
   `PLAN_DIR_PARTS` / `SPEC_DIR_PARTS`, the `html-companion` skill, and the
   docs (`README.md`, `docs/`) together.
7. **Implicit spec approval.** In `superpowers:brainstorming`, answer the
   spec-review handoff with "write the plan" (no "approved"). The design-spec
   offer should come first, as its own message, before writing-plans starts.
8. **Long session.** Reach the plan handoff after many tool calls (or run
   `/compact` mid-plan). The plan offer should still appear before the
   execution handoff — the PostToolUse reminder is what carries it there.

Record steps 5, 7 and 8 in the "Observed offer behaviour" table in
`docs/html-companions.md`.

## Claude Code Requirements

The plugin relies on these documented hook and skill behaviours; re-check
them against the [hooks reference](https://code.claude.com/docs/en/hooks)
when Claude Code changes:

- **SessionStart** command hook whose stdout JSON
  `hookSpecificOutput.additionalContext` is added to Claude's context. The
  matcher `startup|resume|clear|compact|fork` uses exact-name matching; the
  `fork` source needs Claude Code v2.1.214+ (older versions report forks as
  `resume`, which is also matched). Output must stay under the 10,000
  character context cap (tests enforce 2,000).
- **PostToolUse** command hook with matcher `Write|Edit` (exact names), input
  `tool_input.file_path` and `cwd`, and feedback via
  `hookSpecificOutput.additionalContext` plus `systemMessage`. It is
  advisory: the write has already happened. It must exit 0 for plan
  findings, never write to the plan or spec, and stay silent for files
  outside `docs/superpowers/plans/` and `docs/superpowers/specs/` (plans
  without errors and specs get a one-line offer reminder).
- **PreToolUse** command hooks. Matcher `Skill`: input `tool_input.skill`
  and `cwd`; output `hookSpecificOutput.additionalContext`. Claude Code
  saves any one hook's context over 10,000 characters to a file and shows
  only a 2,000-character preview, so the standards are split across two
  commands (`inject-plan-standards.py 1` and `2`). Tests keep each part under
  9,000. Matcher `Bash`: input `tool_input.command` and `cwd`; output
  `permissionDecision: "ask"` with a reason, never `deny` or `allow`. Both
  always exit 0 and print nothing for input they don't handle.
- **Exec-form commands** (`"command": "python3"` with `args`) and
  `${CLAUDE_PLUGIN_ROOT}` for portable paths; `python3` must be on `PATH`.
- **Skills:** `${CLAUDE_PLUGIN_ROOT}` is substituted in plugin skill content.
  Keep each skill self-contained in its `SKILL.md` and without
  `allowed-tools` — supporting files need a read permission and
  `allowed-tools` needs a load permission, both denied in headless runs.

## Synchronizing the Embedded HTML Guide

`skills/shared/html-companion-guide.md` is the source of truth for HTML
output rules. `skills/html-companion/SKILL.md` embeds a verbatim copy in its
"Shared Output Guide" section (everything after the guide's `# H1`).

1. Edit `skills/shared/html-companion-guide.md`.
2. Replace the body of the skill's "Shared Output Guide" section with the
   guide's text after its first line.
3. Run `python3 -m unittest tests.test_html_companion_skill -v`;
   `test_embeds_shared_guide_verbatim` fails until the copies match.
4. If the change affects what can be checked mechanically, update
   `scripts/validate-html-companion.py` and its tests.

The per-artifact "Companion: …" sections (offer question, timing, rendering
priorities) are pinned by `tests/test_html_companion_skill.py`; change the
test expectations deliberately when you change them.

## Skill Promotion

`skills/promote-skill/SKILL.md` drives the workflow; two stdlib scripts do
the mechanical parts:

- `scripts/validate-portable-skill.py` reads a staging folder or a bare skill
  folder and never executes, modifies, or echoes secrets from it. Its
  `MANIFEST_KEYS`, `REVIEW_SECTIONS`, statuses and reserved names are the
  contract; `tests/test_promote_skill.py` checks that the manifest and
  REVIEW.md templates embedded in the skill still match them, so change both
  together.
- `scripts/import-portable-skill.py` plans by default, applies only with
  `--apply`, and never commits, pushes, tags or opens a pull request (a test
  greps its source for those git verbs). Its post-import checks run the
  repository suite with `PROMOTE_SKILL_NESTED_CHECK=1`; the two end-to-end
  tests that themselves run an import skip under that variable to avoid
  recursion.
- When official superpowers adds or renames a skill, update
  `UPSTREAM_SKILLS` in the validator as well as in
  `tests/test_independent_extension.py`.
- A new built-in skill belongs in `EXTENSION_SKILLS` (validator and
  architecture test) and `BUILT_IN_SKILL_DIRS` (`tests/promote_helpers.py`).
  Skills imported with `promote-skill` need no test changes: the
  architecture test accepts any skill folder whose name matches its
  frontmatter and does not shadow an official skill.
- Fixtures under `tests/fixtures/promote/` are synthetic. Never add a real
  work skill, and never store a credential-shaped literal: tests build them
  at runtime (`promote_helpers.fake_secrets`).

## Continuous Integration

`.github/workflows/ci.yml` runs on every pull request and on pushes to
`main`:

- **Tests:** `python -W error::ResourceWarning -m unittest discover -s tests -v`
  on Linux, macOS, and Windows with Python 3.11 and 3.13 (plus 3.12 on
  Linux). No dependencies are installed — a failure here usually means a
  non-stdlib import or a platform assumption.
- **Plugin validation:** `claude plugin validate --strict` on the
  marketplace and plugin manifests, using a pinned Claude Code version
  (`@anthropic-ai/claude-code@…` in the workflow). Bump that pin when you
  test against a newer Claude Code release.

Actions are pinned to full commit SHAs with the release tag in a comment,
and the workflow token is read-only; `tests/test_independent_extension.py`
enforces both. To update an action, resolve the new tag's commit with
`git ls-remote https://github.com/<owner>/<action> refs/tags/<tag>^{}` and
replace the SHA and comment together.

## Test Commands

Regression (no network, standard library only):

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-plan.py tests/fixtures/valid-plan.md             # exit 0
python3 scripts/validate-plan.py tests/fixtures/incomplete-plan.md        # exit 1
python3 scripts/validate-html-companion.py tests/fixtures/companions/plans/2026-01-01-demo.html   # exit 0
python3 scripts/validate-html-companion.py tests/fixtures/companions/plans/external-assets.html   # exit 1
python3 scripts/validate-portable-skill.py tests/fixtures/promote/candidate/skill-promotion          # exit 0
python3 scripts/validate-portable-skill.py tests/fixtures/promote/source/diagram-as-code            # exit 0, 8 warnings
echo '{"source":"startup"}' | python3 scripts/session-context.py
```

`tests/test_independent_extension.py` guards the architecture: no upstream
skill directories or shadowing skill names, no references to removed
paths, only existing `tobin-superpowers:` and `superpowers:` skill names,
matching manifests, resolvable hook paths, and standard-library-only
scripts.

Integration (live Claude Code, isolated configuration as above): steps 1–5,
7 and 8 of the compatibility checklist. Headless runs (`claude -p … --continue`)
work for all four workflows; they deny reads of plugin files and
unapproved commands, which the skills already tolerate.
