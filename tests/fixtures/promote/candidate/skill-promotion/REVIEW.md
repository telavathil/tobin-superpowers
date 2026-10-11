# Skill Promotion Review: diagram-as-code

## Purpose

Keep diagrams as Mermaid code inside the Markdown they illustrate, choose a
diagram type, follow a short style guide, and check blocks with a small
standard-library script.

## Inventory

| File | Role |
|------|------|
| `SKILL.md` | Workflow and diagram-type guidance |
| `references/style.md` | Generic style rules |
| `scripts/check_mermaid.py` | Checker for unknown types and unbalanced brackets |
| `tests/test_check_mermaid.py` | Functional tests for the checker |

## Preserved

- The diagram-as-code rule (Mermaid source, never exported images).
- The diagram-type choices and the four-step workflow.
- The checker's behaviour (known types, bracket balance, exit codes).

## Portability Changes

- Replaced the internal style-guide link with `references/style.md`.
- Removed the absolute template path; templates are optional and local.
- Replaced the private registry with the public mermaid-cli package.
- Removed the internal chat channel and the confidentiality marker.
- Made the checker importable (`check()`) and added functional tests.

## Exclusions

- The employer's service catalog naming rule (company-specific).
- Shared templates directory (not portable, not authorized).
- Review-channel posting step.

## Remaining Dependencies

- Python 3.11 or later (standard library only).
- mermaid-cli, optional, for previews only.

## Validation Results

- Structure, frontmatter, references, dependencies: pending.
- Portability scan: pending.
- Functional tests (`python3 -m unittest discover -s tests -v`): pending.

## Risks

- Automated checks are heuristics; they do not prove the absence of
  confidential material or establish ownership.

## Approval

Status: pending
Transfer authorized: no
Publication authorized: no
