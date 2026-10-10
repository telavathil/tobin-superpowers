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
Skill-specific rendering priorities live inside each modified `SKILL.md`.

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
│   └── hooks.json                 # SessionStart hook registration
├── scripts/
│   └── session-context.py         # injects hybrid planning preferences
├── skills/
│   ├── hybrid-planning/
│   │   └── SKILL.md               # lean, human-executable plan contract
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
├── tests/
│   └── test_session_context.py    # python3 -m unittest discover -s tests -v
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

## Versioning

Versioned independently from upstream `superpowers`. When a superpowers
release updates one of the four modified skills, review the upstream diff
and merge non-companion changes by hand.

See [`MAINTAINING.md`](MAINTAINING.md) for the full step-by-step upstream
merge workflow, including the verification commands and the one known
brainstorming-checklist gotcha.

## License

MIT. Upstream `superpowers` is also MIT.
