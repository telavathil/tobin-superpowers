---
name: html-companion
description: Use after a superpowers design spec, implementation plan, code review report, or subagent run summary is final - offers once to create a self-contained, shareable HTML companion next to the markdown, and generates it only if the user says yes
---

# HTML Companion

Turns a finished superpowers markdown artifact into a self-contained `.html`
page a human teammate can open by double-click and skim in under a minute.
The markdown stays the artifact of record; the HTML is an optional extra.

This skill is standalone: it works with the official `superpowers` skills and
does not depend on this plugin's forked copies. Everything you need is in
this file — do not go looking for other plugin files.

## When to Offer

Offer at the moment the artifact is final, never earlier and never between
steps of a run:

| Artifact | Offer when | Section below |
| --- | --- | --- |
| design spec (`brainstorming`) | after the user approves the written spec, before handing off to writing-plans | Companion: Design Spec |
| implementation plan (`writing-plans`) | after the plan's self-review is clean, before the execution handoff | Companion: Implementation Plan |
| code review report (`requesting-code-review`) | after the review is in and Critical/Important issues are fixed or deferred | Companion: Code Review Report |
| run summary (`subagent-driven-development`) | once, after the final review approves, before finishing the branch | Companion: Run Summary |

## Consent Rules

1. Ask once per artifact, as its own short message (not bundled with another
   question such as the execution handoff), using the exact question from the
   artifact's section below:
   "Would you like an HTML companion for this <artifact> to share with your team? (yes/no)"
   (the run summary wording says "as an async team update").
2. Only generate after an explicit yes. Silence, "maybe", or a non-interactive
   run is not a yes.
3. If the user says no, continue the normal workflow and do not ask again for
   that artifact.
4. If another skill already asked for this artifact (for example a forked
   tobin-superpowers skill), do not ask a second time.

## On Yes

1. Use the artifact's "Companion: …" section below for timing details and its
   rendering priorities, and the "Shared Output Guide" at the end for output
   rules, style, palette, and the HTML skeleton.
2. Code review reports and run summaries are not saved by default: first write
   the markdown to `docs/superpowers/reviews/` or
   `docs/superpowers/run-summaries/` exactly as the section describes.
3. Write the companion with the same base name as the markdown, `.html`
   extension, same directory, re-laid-out for human reading (not a markdown
   dump), self-contained (no CDN, web fonts, external scripts, or relative
   assets; images only as `data:` URIs). Footer:
   `Source: <project-relative path to the .md>`.
   Never modify the source Markdown — not even whitespace.
4. Validate:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate-html-companion.py <file>.html --source <file>.md
   ```

   Fix every `error` and re-run until it exits 0. Fix `warning`s when they
   are real; the validator is structural and cannot judge layout quality.
   If the validator cannot run (permission denied or not found), say so and
   check by hand: no external URLs or relative assets, header with title,
   date and "Companion to …", footer with the relative source path.
5. Never stage or commit the HTML (no `git add`); leave it untracked for the
   user to decide.
6. Confirm both paths to the user in one short message, then continue the
   workflow where it left off.

## Companion: Design Spec

Migrated from the fenced HTML companion block in this plugin's forked `brainstorming` skill; wording kept.

### When to Offer

Run this step **after** the user has reviewed and approved the written spec
(the user-review gate) and **before** transitioning to the writing-plans skill.
The markdown is the artifact of record; the HTML
companion exists only to make it easier to share with a human teammate.

### The Offer

Ask exactly once, as its own message:

> "Would you like an HTML companion for this design spec to share with your
> team? (yes/no)"

- If **no**: continue to the writing-plans transition with no changes.
- If **yes**: generate the companion per the rendering priorities below, save it next to the
  markdown, then confirm both file paths in a single short message before
  transitioning to writing-plans.

### Source Markdown

`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, already written by `brainstorming`. Read it; never modify it.

### Rendering Priorities for a Design Spec

A design spec is read by a teammate trying to understand *what was decided
and why* in under a minute. Lay the companion out for that reader.

- **Decisions summary at the top.** Pull the key choices out of the spec —
  what was picked, what was rejected, why. This is the most important block
  and should sit above any approach comparison or architectural detail.
- **Section navigation.** Render an in-page table of contents with anchor
  links to each `h2`-level section. Use the `.toc` pattern from the shared
  guide skeleton.
- **Approach comparison (if the spec contains multiple approaches).** Render
  the 2–3 approaches side by side. Use a two- or three-column layout with the
  same row structure for each approach (overview, trade-offs, recommendation).
  The selected approach should be visually distinguished — a `success` pill
  or a tinted card background is enough.
- **Open questions, callouts.** Any "TBD", "open question", or "decision
  needed" item from the spec should be lifted into a `warning` callout near
  the top. Do not bury them inside body text.
- **Body sections** (architecture, components, data flow, error handling,
  testing) follow the summary. Use `h2` headings matching the spec
  structure. Keep paragraphs short; use bullets and tables wherever the spec
  lists items.
- **Footer.** The relative path to the source markdown spec, per the shared
  guide.

## Companion: Implementation Plan

Migrated from the fenced HTML companion block in this plugin's forked `writing-plans` skill; wording kept.

### When to Offer

Run this after the Self-Review loop is clean and before the Execution Handoff
prompt. The plan is finalized at that point, so the companion will not be
stale by the time the user shares it.

### The Offer

Ask exactly once, as its own message:

> "Would you like an HTML companion for this implementation plan to share
> with your team? (yes/no)"

- If **no**: continue to Execution Handoff with no changes.
- If **yes**: generate the companion per the rendering priorities below, save it next to
  the markdown, then confirm both file paths in a single short message
  before proceeding to Execution Handoff.

### Source Markdown

`docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`, already written by `writing-plans`. Read it; never modify it.

### Rendering Priorities for an Implementation Plan

A plan is read by a teammate trying to understand *what is being built, in
what order, and where the risks sit*. Optimize for skimmability.

- **Plan summary header.** Feature name, total task count, and an estimated
  scope cue (e.g. "12 tasks across 3 phases"). Sits directly under the
  document header. Pull the feature name and task count from the plan.
- **Phase or subsystem grouping.** If the plan organizes tasks under phases
  or subsystems, render those as collapsible-feeling sections with clear
  headings. If the plan is flat, render a single task list.
- **Tasks as a structured checklist.** Each task becomes one row in a
  checklist. The row should surface, at a glance:
  - Task title and number
  - Files touched (Create / Modify / Test) as inline `code` chips
  - Verification command (the `Run:` line) as inline `code`
  - Status pill if the plan tracks status
  Do not bury this metadata inside paragraph prose — it should be readable
  without reading the surrounding text.
- **Risk and dependency callouts.** Any task with a flagged risk, a
  cross-task dependency, or a "watch out" note should render as a `warning`
  callout in the row, visually distinct from regular tasks.
- **Body content** (code blocks per step) is preserved per task — render
  multi-line code in `<pre>` blocks with the system monospace stack.
- **Footer.** The relative path to the source markdown plan, per the shared
  guide.

## Companion: Code Review Report

Migrated from the fenced HTML companion block in this plugin's forked `requesting-code-review` skill; wording kept.

### When to Offer

Run this after the reviewer subagent has returned its report and after any
Critical or Important issues have been addressed (or explicitly deferred).
The report is stable at that point and worth sharing.

### The Offer

Ask exactly once, as its own message:

> "Would you like an HTML companion for this code review report to share
> with your team? (yes/no)"

- If **no**: continue with the normal post-review workflow with no changes.
- If **yes**: write the report to markdown, generate the HTML companion per
  the rendering priorities below, and confirm both file paths in a single short message.

### Persist the Markdown First (only after yes)

If the report has not already been written to a markdown file, write it to:

```
docs/superpowers/reviews/YYYY-MM-DD-<feature-or-task-slug>-review.md
```

The markdown file is the canonical artifact. Structure it with the same
sections the reviewer produced (Strengths, Critical, Important, Minor,
Assessment) and include the BASE_SHA / HEAD_SHA range, the description, and
the plan or requirements reference at the top.

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

## Companion: Run Summary

Migrated from the fenced HTML companion block in this plugin's forked `subagent-driven-development` skill; wording kept.

### When to Offer

Run this **after the final code reviewer subagent has approved the full
implementation** and **before** invoking
`superpowers:finishing-a-development-branch`. The run is complete at that
point and the summary will not change.

This step does not run between individual tasks — only once, after all
tasks have completed and the final review is clean.

### The Offer

Ask exactly once, as its own message:

> "Would you like an HTML companion for this subagent run summary to share
> as an async team update? (yes/no)"

- If **no**: continue to `superpowers:finishing-a-development-branch` with
  no changes.
- If **yes**: write the run summary to markdown, generate the HTML
  companion per the rendering priorities below, and confirm both file paths in a single
  short message before proceeding.

### Persist the Markdown First (only after yes)

Write the summary to:

```
docs/superpowers/run-summaries/YYYY-MM-DD-<feature-or-plan-slug>-summary.md
```

The markdown file is the canonical artifact. Include at minimum:

- Feature / plan name and a link to the source plan file
- Total tasks: completed, completed-with-concerns, blocked
- One entry per task with: title, final status, key files touched, any
  concerns the implementer or reviewer flagged
- Final reviewer's overall assessment

### Rendering Priorities for a Run Summary

A run summary is read by a teammate scanning an async update — they want
*did it ship, did anything go wrong, do I need to look at anything*. The
target read time is 30 seconds.

- **Status summary at the top.** Three pills side by side, using the
  semantic palette from the shared guide:
  - `success` — completed (count)
  - `warning` — completed with concerns (count)
  - `critical` — blocked (count)
  This is the most important block — it sits directly under the header.
- **Concerns and blocked tasks first.** Surface every task that finished
  `DONE_WITH_CONCERNS` or `BLOCKED` as a callout near the top, using the
  matching semantic color. Include the task title, the concern or blocker
  text, and a link or reference to the relevant commit or file. The reader
  should not have to scroll to find what went wrong.
- **Source plan reference.** Below the status summary, include a clear
  reference to the source implementation plan markdown — both as a path
  and (if the plan also has an HTML companion) as a link.
- **Full task list.** A compact checklist of every task with its final
  status pill and a one-line summary. Group by phase if the plan grouped
  by phase. Completed tasks render in the neutral palette; the eye-catching
  rows are the concerns and blockers at the top.
- **Final reviewer assessment.** The overall verdict from the final code
  reviewer rendered as a single prominent callout using the appropriate
  semantic color.
- **Footer.** The relative path to the source markdown summary, per the
  shared guide.

## Shared Output Guide

Verbatim copy of `skills/shared/html-companion-guide.md` (kept in sync by
`tests/test_html_companion_skill.py`). Each skill's "rendering priorities"
mentioned below are the "Companion: …" sections above.

Shared rules for generating self-contained HTML companions alongside the markdown
output of the `brainstorming`, `writing-plans`, `requesting-code-review`, and
`subagent-driven-development` skills.

Each skill references this guide after writing its primary markdown file. The
markdown source is the artifact of record — the HTML companion exists only to
make the same information faster to read and easier to share with a human
teammate.

---

## When to Generate

Generate an HTML companion only when the user explicitly accepts the offer at
the end of the skill. The default is to skip it. If the user declines, the
skill exits its normal flow with no changes.

---

## Output Rules

- **Filename.** Save the HTML next to the markdown with the same base name and
  a `.html` extension.
  - Markdown: `docs/superpowers/specs/2026-05-11-auth-redesign-design.md`
  - Companion: `docs/superpowers/specs/2026-05-11-auth-redesign-design.html`
- **Never modify the markdown.** Treat the markdown as read-only. Do not
  rewrite, reformat, or re-save it as part of generating the companion.
- **Self-contained.** The HTML file must open and render correctly when
  double-clicked from a file browser, with no network access. That means:
  - No `<link rel="stylesheet">` to any URL
  - No `<script src="https://...">`
  - No `@import`, `url(...)` references to remote assets, or relative paths to
    files outside the HTML itself
  - No web fonts — use the system font stack (see Style Guidelines)
  - Any image must be inlined as a base64 data URI or omitted
- **Confirm both paths.** After writing the HTML, report both the markdown
  path and the HTML path back to the user in a single short message.

---

## Content Rules

The companion is not a markdown-to-HTML render. Re-structure the content for
how a human reads it on screen, not how an agent parses it as text.

- **Lead with the decisions or the summary**, not with preamble or context. The
  reader is opening this to find out *what was decided* or *what happened*.
- **Use visual hierarchy** to make the document scannable in under 30 seconds:
  clear section headings, callouts for important items, generous whitespace.
- **Header (required)** at the top of every companion:
  - Document title (the same title as the markdown, or its `# H1`)
  - Date the companion was generated (ISO format, e.g. `2026-05-11`)
  - A label identifying it as a companion to the markdown source
    (e.g. *"Companion to the markdown spec — open the .md for the agent-facing
    source"*)
- **Footer (required)** at the bottom:
  - Relative path to the source markdown file (e.g.
    `Source: docs/superpowers/specs/2026-05-11-auth-redesign-design.md`)
  - Optional: generated-by line, e.g. *"Generated by the tobin-superpowers
    HTML companion."*
- **Skill-specific structure.** Each skill's `SKILL.md` includes a "Rendering
  priorities" section. Treat that as authoritative for how the body of the
  companion should be laid out for that skill's output type.

---

## Style Guidelines

The companion should look like something you would not mind pasting a link to
in a work Slack channel or an email. Clean, professional, restrained.

### Layout

- Centered content column, max width around 760–880px
- Body font size 16–18px, line height 1.5–1.6
- Generous vertical rhythm between sections (1.5–2rem)
- Responsive enough to remain readable on a laptop screen — do not require
  horizontal scrolling at standard widths

### Typography

Use the system font stack only:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
             "Helvetica Neue", Arial, sans-serif;
```

For code blocks, use the system monospace stack:

```css
font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
             "Liberation Mono", monospace;
```

Do not load Google Fonts, Adobe Fonts, or any other web font.

### Color

Use color sparingly and only when it carries meaning. Default to a neutral
palette and reserve hue for semantic signals.

Suggested neutral base (adapt as appropriate):

| Role            | Example         |
| --------------- | --------------- |
| Page background | `#ffffff`       |
| Body text       | `#1f2328`       |
| Muted text      | `#656d76`       |
| Borders / rules | `#d0d7de`       |
| Surface / card  | `#f6f8fa`       |

Suggested semantic palette (use only when content carries the meaning):

| Severity / Status | Foreground | Background |
| ----------------- | ---------- | ---------- |
| Critical / blocker | `#82071e` | `#ffebe9` |
| Warning / concern  | `#7d4e00` | `#fff8c5` |
| Suggestion / info  | `#0969da` | `#ddf4ff` |
| Success / done     | `#1a7f37` | `#dafbe1` |

Never apply semantic color decoratively. A critical-red header on a doc with no
critical content is misleading.

### Components to Reuse

These patterns appear across multiple skill companions — use them consistently:

- **Header band.** Title, date, "Companion to …" subtitle.
- **Section anchors.** Each `h2`-level section gets an `id` so the in-page nav
  can link to it.
- **Callout box.** Bordered, tinted background, used for risks, open questions,
  or important notes. Reuse the semantic palette above.
- **Checklist row.** For task or finding lists — checkbox (or status pill) on
  the left, label and detail on the right.
- **Status pill.** Small rounded badge with one of the semantic background
  colors, used for severity, status, or category.

---

## HTML Skeleton

Use this as the starting structure for every companion. Adapt the body content
to the skill's rendering priorities; keep the head and the visual conventions
consistent.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><!-- document title --></title>
  <style>
    :root {
      --bg: #ffffff;
      --fg: #1f2328;
      --muted: #656d76;
      --border: #d0d7de;
      --surface: #f6f8fa;
      --critical-fg: #82071e;
      --critical-bg: #ffebe9;
      --warning-fg: #7d4e00;
      --warning-bg: #fff8c5;
      --info-fg: #0969da;
      --info-bg: #ddf4ff;
      --success-fg: #1a7f37;
      --success-bg: #dafbe1;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg); }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   "Helvetica Neue", Arial, sans-serif;
      font-size: 17px;
      line-height: 1.55;
    }
    .wrap { max-width: 820px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }
    header.companion-header { border-bottom: 1px solid var(--border); padding-bottom: 1.25rem; margin-bottom: 2rem; }
    header.companion-header h1 { margin: 0 0 .35rem; font-size: 1.85rem; line-height: 1.2; }
    header.companion-header .meta { color: var(--muted); font-size: .95rem; }
    h2 { font-size: 1.35rem; margin-top: 2.25rem; margin-bottom: .75rem; padding-top: .25rem; }
    h3 { font-size: 1.1rem; margin-top: 1.5rem; margin-bottom: .5rem; }
    p { margin: .75rem 0; }
    code, pre {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                   "Liberation Mono", monospace;
      font-size: .92em;
    }
    pre { background: var(--surface); padding: .9rem 1rem; border-radius: 6px; overflow-x: auto; }
    code { background: var(--surface); padding: .1em .35em; border-radius: 4px; }
    pre code { background: transparent; padding: 0; }
    .callout { border: 1px solid var(--border); border-left-width: 4px; border-radius: 6px; padding: .85rem 1rem; margin: 1rem 0; background: var(--surface); }
    .callout.critical { border-left-color: var(--critical-fg); background: var(--critical-bg); }
    .callout.warning  { border-left-color: var(--warning-fg);  background: var(--warning-bg); }
    .callout.info     { border-left-color: var(--info-fg);     background: var(--info-bg); }
    .callout.success  { border-left-color: var(--success-fg);  background: var(--success-bg); }
    .pill { display: inline-block; font-size: .78rem; font-weight: 600; padding: .15rem .55rem; border-radius: 999px; text-transform: uppercase; letter-spacing: .03em; }
    .pill.critical { color: var(--critical-fg); background: var(--critical-bg); }
    .pill.warning  { color: var(--warning-fg);  background: var(--warning-bg); }
    .pill.info     { color: var(--info-fg);     background: var(--info-bg); }
    .pill.success  { color: var(--success-fg);  background: var(--success-bg); }
    .pill.neutral  { color: var(--muted);       background: var(--surface); }
    .toc { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: .9rem 1.1rem; margin: 1rem 0 2rem; }
    .toc ul { margin: .25rem 0 0; padding-left: 1.2rem; }
    .toc a { color: var(--info-fg); text-decoration: none; }
    .toc a:hover { text-decoration: underline; }
    .checklist { list-style: none; padding-left: 0; }
    .checklist li { display: flex; gap: .65rem; align-items: flex-start; padding: .4rem 0; border-bottom: 1px solid var(--border); }
    .checklist li:last-child { border-bottom: none; }
    .checklist .marker { flex: 0 0 1.25rem; padding-top: .15rem; color: var(--muted); }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .95rem; }
    th, td { border: 1px solid var(--border); padding: .5rem .7rem; text-align: left; vertical-align: top; }
    th { background: var(--surface); }
    footer.companion-footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: .9rem; }
    footer.companion-footer code { background: transparent; padding: 0; }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="companion-header">
      <h1><!-- document title --></h1>
      <div class="meta">
        <!-- e.g. "Companion to the design spec · 2026-05-11" -->
      </div>
    </header>

    <!-- TOC, summary, skill-specific sections go here -->

    <footer class="companion-footer">
      Source: <code><!-- relative path to source .md --></code><br>
      Generated by the tobin-superpowers HTML companion.
    </footer>
  </div>
</body>
</html>
```

---

## Anti-Patterns

Do not:

- Dump the entire markdown into a single `<pre>` block or run it through a
  markdown-to-HTML converter and call it done. The companion is a re-layout,
  not a rendering.
- Link out to CDN-hosted CSS frameworks, fonts, or syntax highlighters.
- Add JavaScript unless absolutely necessary for the content type. Plain HTML
  and CSS should cover every skill's needs.
- Apply semantic color decoratively. Critical-red on a normal note is noise.
- Modify the source markdown in any way, including reformatting whitespace.
