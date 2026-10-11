---
name: diagram-as-code
description: Draft and check Mermaid diagrams that live as code next to the docs they illustrate
---

# Diagram as Code

Keep every diagram as Mermaid source in a fenced `mermaid` block inside the
Markdown file it illustrates. Never paste exported images: code diffs, reviews,
and stays in sync with the text around it.

## Workflow

1. Pick the diagram type: `flowchart` for processes, `sequenceDiagram` for
   request flows, `erDiagram` for data models.
2. Write the block, following `references/style.md`.
3. Check it: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/diagram-as-code/scripts/check_mermaid.py" docs/architecture.md`
   (exit 0 means every block passed).
4. Optional: if `mmdc` (the public mermaid-cli package) is installed, render a
   preview with `mmdc -i docs/architecture.md -o preview.svg`. Do not
   commit the rendered file.
