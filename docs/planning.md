# Planning: Hybrid Plans and Code Standards

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

## Lint Baseline Check

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
