---
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging to verify work meets requirements
---

# Requesting Code Review

Dispatch a code reviewer subagent to catch issues before they cascade. The reviewer gets precisely crafted context for evaluation — never your session's history. This keeps the reviewer focused on the work product, not your thought process, and preserves your own context for continued work.

**Core principle:** Review early, review often.

## When to Request Review

**Mandatory:**
- After each task in subagent-driven development
- After completing major feature
- Before merge to main

**Optional but valuable:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After fixing complex bug

## How to Request

**1. Get git SHAs:**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # or origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**2. Dispatch code reviewer subagent:**

Use Task tool with `general-purpose` type, fill template at `code-reviewer.md`

**Placeholders:**
- `{DESCRIPTION}` - Brief summary of what you built
- `{PLAN_OR_REQUIREMENTS}` - What it should do
- `{BASE_SHA}` - Starting commit
- `{HEAD_SHA}` - Ending commit

**3. Act on feedback:**
- Fix Critical issues immediately
- Fix Important issues before proceeding
- Note Minor issues for later
- Push back if reviewer is wrong (with reasoning)

<!-- tobin-superpowers:html-companion:start -->

## HTML Companion Offer (Personal Fork)

> This section is added by the `tobin-superpowers` fork and is not present in
> the upstream `superpowers` skill. It defines an optional step that
> persists the reviewer's report as markdown and produces a shareable HTML
> companion alongside it.

### When to Run

Run this after the reviewer subagent has returned its report and after any
Critical or Important issues have been addressed (or explicitly deferred).
The report is stable at that point and worth sharing.

### The Offer

Ask exactly once, as its own message:

> "Would you like an HTML companion for this code review report to share
> with your team? (yes/no)"

- If **no**: continue with the normal post-review workflow with no changes.
- If **yes**: write the report to markdown, generate the HTML companion per
  the rules below, and confirm both file paths in a single short message.

### Persisting the Report

If the report has not already been written to a markdown file, write it to:

```
docs/superpowers/reviews/YYYY-MM-DD-<feature-or-task-slug>-review.md
```

The markdown file is the canonical artifact. Structure it with the same
sections the reviewer produced (Strengths, Critical, Important, Minor,
Assessment) and include the BASE_SHA / HEAD_SHA range, the description, and
the plan or requirements reference at the top.

### How to Generate the HTML

Read `skills/shared/html-companion-guide.md` for output rules, style
guidelines, the color palette, and the HTML skeleton. Treat that guide as
authoritative for everything not specified here.

### Rendering Priorities for a Code Review Report

A review report is read by the author of the code (or a teammate) trying to
understand *what was found, how severe it is, and where to look*. Optimize
for severity scanning.

- **Summary bar at the top.** Total findings broken down by severity, each
  rendered as a status pill: `critical`, `warning` (Important), `info`
  (Minor / Suggestion), `success` (Strengths). The bar should be the first
  thing the reader sees after the header.
- **Jump links.** An in-page table of contents linking to each individual
  finding (anchored by finding id). Use the `.toc` pattern from the shared
  guide skeleton. Keeps long reports navigable.
- **Findings as severity-coded rows.** Each finding becomes a card with:
  - A severity pill on the left (using the semantic palette from the shared
    guide — `critical`, `warning`, `info`, `success`)
  - The finding title
  - The file path and line range as inline `code`
  - The finding body (description, suggested fix)
  Do not interleave findings of different severity arbitrarily — group by
  severity, critical first.
- **Annotated diff (if available).** If the report includes a diff, render
  it in a `<pre>` block with system monospace, and place inline margin notes
  (rendered as right-aligned callouts or footnote-style annotations) next to
  the relevant lines. Keep the diff readable without horizontal scroll on a
  laptop.
- **Assessment at the bottom.** The reviewer's overall verdict (Ready /
  Not ready / Blocked) rendered as a single prominent callout using the
  appropriate semantic color.
- **Footer.** The relative path to the source markdown report, per the
  shared guide.

### Output

- Filename: same base name as the markdown report, with `.html` extension.
  - Example: `docs/superpowers/reviews/2026-05-11-auth-redesign-review.html`
- Do not stage or commit the HTML. Leave it unstaged for the user to decide
  whether to track it.
- Do not modify the markdown file in any way after writing it.

<!-- tobin-superpowers:html-companion:end -->

## Example

```
[Just completed Task 2: Add verification function]

You: Let me request code review before proceeding.

BASE_SHA=$(git log --oneline | grep "Task 1" | head -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse HEAD)

[Dispatch code reviewer subagent]
  DESCRIPTION: Added verifyIndex() and repairIndex() with 4 issue types
  PLAN_OR_REQUIREMENTS: Task 2 from docs/superpowers/plans/deployment-plan.md
  BASE_SHA: a7981ec
  HEAD_SHA: 3df7661

[Subagent returns]:
  Strengths: Clean architecture, real tests
  Issues:
    Important: Missing progress indicators
    Minor: Magic number (100) for reporting interval
  Assessment: Ready to proceed

You: [Fix progress indicators]
[Continue to Task 3]
```

## Integration with Workflows

**Subagent-Driven Development:**
- Review after EACH task
- Catch issues before they compound
- Fix before moving to next task

**Executing Plans:**
- Review after each task or at natural checkpoints
- Get feedback, apply, continue

**Ad-Hoc Development:**
- Review before merge
- Review when stuck

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore Critical issues
- Proceed with unfixed Important issues
- Argue with valid technical feedback

**If reviewer wrong:**
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification

See template at: requesting-code-review/code-reviewer.md
