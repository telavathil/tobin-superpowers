# Authorized description: diagram-as-code

Written by the user from their own general knowledge. It contains no source
files, internal links, or employer material.

I want a skill that keeps diagrams as Mermaid code inside the Markdown they
illustrate, never as exported images. It should help pick a diagram type
(flowchart for processes, sequenceDiagram for request flows, erDiagram for
data models), follow a short generic style guide, and include a small
standard-library Python checker that flags unknown diagram types and
unbalanced brackets in `mermaid` blocks. Rendering previews is optional and
should use the public mermaid-cli if it is installed.
