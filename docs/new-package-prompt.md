# New-Package Prompt

A `PreToolUse` hook on `Bash` (`scripts/ask-new-package.py`) reads install
commands and asks you to confirm any package that isn't in the nearest
manifest. This guards against hallucinated (slopsquatted) package names.

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
