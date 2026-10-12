# Dependencies and APIs

Check an API against the installed version, not memory.

- Read the installed types or source: `node_modules/<pkg>` types, `go doc`, the installed Python package source or stubs.
- Unknown shapes are parsed at the boundary (`global/trust-types.md`).

Before adding a dependency:
- Check whether an installed one covers the need.
- If not, confirm the package on its registry (npm, pkg.go.dev, PyPI): publisher, downloads, repository.
- Say why it's needed.

A hook asks before a package that isn't in the manifest is installed.
