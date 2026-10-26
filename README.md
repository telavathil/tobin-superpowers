# tobin-superpowers

[![CI](https://github.com/telavathil/tobin-superpowers/actions/workflows/ci.yml/badge.svg)](https://github.com/telavathil/tobin-superpowers/actions/workflows/ci.yml)

An extension for the official
[superpowers](https://github.com/obra/superpowers) plugin for Claude Code.
superpowers provides the development workflows (brainstorming, writing
plans, code review, subagent-driven development); this plugin adds the
features below without replacing or copying any of them, so superpowers
keeps working and updating exactly as published.

## Features

| Feature                     | What it does                                                                                                                                                            | Details                                                  |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Hybrid planning             | Plans stay lean but each task is executable by a skilled developer without AI help: exact paths, interfaces, ordered steps, test assertions, verification commands.     | [docs/planning.md](docs/planning.md)                     |
| Code standards at plan time | Your standards in `standards/` are injected when a plan-writing skill runs; the first plan in a repo also gets a one-off lint baseline check.                           | [docs/planning.md](docs/planning.md#code-standards)      |
| Plan validation             | An advisory structural check runs whenever Claude writes a plan in `docs/superpowers/plans/`. Also available as a CLI.                                                  | [docs/plan-validation.md](docs/plan-validation.md)       |
| HTML companions             | At the end of a spec, plan, code review, or subagent run, Claude offers a self-contained `.html` version to share, created only if you say yes.                         | [docs/html-companions.md](docs/html-companions.md)       |
| New-package prompt          | Asks you to confirm before an install command adds a package that isn't in the project's manifest (guards against slopsquatting).                                       | [docs/new-package-prompt.md](docs/new-package-prompt.md) |
| Cold-cache guard            | Stops a prompt once when the cache has expired and re-writing the context would cost $1 or more, and suggests `/clear`. Send it again to go ahead.             | [docs/cold-cache-guard.md](docs/cold-cache-guard.md) |
| Skill promotion             | Manual `/tobin-superpowers:promote-skill` workflow that turns a skill into a portable candidate and guides a local import after your approval. Never commits or pushes. | [docs/skill-promotion.md](docs/skill-promotion.md)       |

## Installation

Requires Claude Code with plugin support and `python3` (3.11+) on `PATH`
(macOS, Linux, WSL, or Windows with `python3` on `PATH`). No other
dependencies.

1. Install official superpowers (skip if you already have it, from any
   marketplace — this plugin only needs the `superpowers:*` skills to exist):

   ```
   /plugin marketplace add obra/superpowers
   /plugin install superpowers@superpowers-dev
   ```

2. Install this extension:

   ```
   /plugin marketplace add telavathil/tobin-superpowers
   /plugin install tobin-superpowers@tobin-superpowers-dev
   ```

3. Restart Claude Code (or run `/reload-plugins`). `/plugin` should list
   `tobin-superpowers` `1.2.0` — see
   [verifying the install](docs/troubleshooting.md#verifying-the-install).

To update, run the following and restart. The two plugins update
independently; updating superpowers never requires a change here.

```
/plugin marketplace update superpowers-dev
/plugin marketplace update tobin-superpowers-dev
/plugin update
```

## Usage

There is nothing to invoke. Use the superpowers workflows as normal
(`superpowers:brainstorming`, `superpowers:writing-plans`,
`superpowers:subagent-driven-development`,
`superpowers:requesting-code-review`, …) and the hooks apply the planning
preferences, standards, validation feedback, and HTML companion offers
automatically.

HTML companion offers are best-effort; you can always ask directly:
_"make an HTML companion for docs/superpowers/plans/x.md"_.

To turn everything off, disable the plugin (`/plugin` → `tobin-superpowers`
→ Disable); superpowers keeps working. For debugging hooks, see
[docs/troubleshooting.md](docs/troubleshooting.md).

## Contributing

See [MAINTAINING.md](MAINTAINING.md) for the repository layout, tests,
releasing, and compatibility testing against new superpowers releases.

## License

MIT. superpowers is also MIT.
