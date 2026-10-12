# Go lint baseline

Prerequisite: golangci-lint v2 (`version: "2"` in `.golangci.yml`).

Linters: `errcheck`, `funlen`, `gocyclo`, `revive`, `govet`, `staticcheck`.

```yaml
version: "2"
linters:
  enable:
    - errcheck
    - funlen
    - gocyclo
    - revive
    - govet
    - staticcheck
  settings:
    funlen:
      lines: 75
      statements: 50
    gocyclo:
      min-complexity: 15
issues:
  new-from-merge-base: main # the repo's default branch
```

Ratchet: `issues.new-from-merge-base` set to the repo's default branch, so only new code is held to the baseline.

Same gap-PR flow as `typescript.md`: separate from feature work.
