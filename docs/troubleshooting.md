# Disable or Troubleshoot

## Verifying the Install

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

## Disabling

Claude Code has no per-hook switch. Disable the plugin (`/plugin` →
`tobin-superpowers` → Disable, or
`claude plugin disable tobin-superpowers@tobin-superpowers-dev`); superpowers
keeps working. `"disableAllHooks": true` in settings turns off every
plugin's hooks.

## Debugging Hooks

- **See hook runs:** `claude --debug hooks`, then look for
  `session-context.py`, `inject-plan-standards.py`, `ask-new-package.py`,
  `cold-cache-guard.py` and `validate-plan-hook.py`.
- **Reproduce plan validation:** (a plan without errors shows the offer reminder)
  `echo '{"tool_name":"Write","cwd":"'"$PWD"'","tool_input":{"file_path":"docs/superpowers/plans/x.md"}}' | python3 scripts/validate-plan-hook.py`
- **Reproduce the spec reminder:** (the file must exist)
  `echo '{"tool_name":"Write","cwd":"'"$PWD"'","tool_input":{"file_path":"docs/superpowers/specs/x.md"}}' | python3 scripts/validate-plan-hook.py`
- **Reproduce the standards injection:** (run with `2` for the second half)
  `echo '{"tool_input":{"skill":"writing-plans"},"cwd":"'"$PWD"'"}' | python3 scripts/inject-plan-standards.py 1`
- **Reproduce the new-package prompt:**
  `echo '{"tool_input":{"command":"npm i left-padd"},"cwd":"'"$PWD"'"}' | python3 scripts/ask-new-package.py`
- **Reproduce the cold-cache guard:** (silent unless the last response is over 5
  minutes old and re-writing its context costs $1 or more; blocks once per cold period)
  `echo '{"session_id":"test","prompt":"hi","transcript_path":"'"$(ls -t ~/.claude/projects/*/*.jsonl | head -1)"'"}' | python3 scripts/cold-cache-guard.py`
- **No offers or preferences?** Check `/hooks` and that `python3` is on
  `PATH`.
