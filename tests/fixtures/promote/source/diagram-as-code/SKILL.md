---
name: diagram-as-code
description: Draft and check Mermaid diagrams that live as code next to the docs they illustrate
---

# Diagram as Code

Example Corp confidential - internal use only.

Keep every diagram as Mermaid source in a fenced `mermaid` block inside the
Markdown file it illustrates. Never paste exported images.

Follow the house style at https://wiki.examplecorp.internal/eng/diagram-style
and start from the shared templates in /Users/jdoe/work/diagram-templates/.

## Workflow

1. Pick the diagram type: `flowchart` for processes, `sequenceDiagram` for
   request flows, `erDiagram` for data models.
2. Write the block, following `references/style.md`.
3. Check it: `python3 scripts/check_mermaid.py docs/architecture.md`.
4. To render previews, install mermaid-cli from the company registry
   (`.npmrc`: `registry=https://npm.examplecorp.internal/`) and post the
   image in https://chat.examplecorp.internal/channels/arch-review.
