# Python lint baseline

ruff in `pyproject.toml`:

```toml
[tool.ruff.lint]
select = ["E", "F", "B", "BLE001", "S110", "RUF006", "ANN", "C901", "PLR0913", "PLR0915"]

[tool.ruff.lint.mccabe]
max-complexity = 15

[tool.ruff.lint.pylint]
max-args = 5
max-statements = 50

[tool.basedpyright]
typeCheckingMode = "standard"
reportAny = "error"
```

`PLR0913` is max-args and `PLR0915` is max-statements.

Ratchet: run `ruff check --add-noqa` and `basedpyright --writebaseline`, and commit both the `noqa` comments and `.basedpyright/baseline.json`.

Same gap-PR flow as `typescript.md`: separate from feature work.
