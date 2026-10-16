# Plan Validation

## Automatic (PostToolUse hook)

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

## Manual (CLI)

```bash
python3 scripts/validate-plan.py docs/superpowers/plans/2026-10-10-feature.md [--json]
```

Exit codes: `0` no errors (warnings allowed), `1` errors, `2` bad
arguments or an unreadable file.

## What Is Checked

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

## Limitations

- Only `Write` and `Edit` trigger the hook. Plans written through `Bash`
  (e.g. a heredoc), MCP tools, or editors outside Claude Code are not
  validated automatically — run the CLI.
- Plans saved outside `docs/superpowers/plans/` are not validated
  automatically.
- Heuristics can produce occasional false positives or misses.
