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
├── skills/
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
└── README.md
```

## Versioning

Versioned independently from upstream `superpowers`. When a superpowers
release updates one of the four modified skills, review the upstream diff
and merge non-companion changes by hand.

## License

MIT. Upstream `superpowers` is also MIT.
