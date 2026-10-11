---
name: promote-skill
description: Manually invoked workflow that turns an existing or described Claude Code skill into a portable, company-independent candidate, reviews it with the user, and guides a local import into tobin-superpowers
disable-model-invocation: true
---

# Promote Skill

Turn one skill into a portable, company-independent candidate, review it
with the user, and — only after explicit approval and transfer authorization —
guide a local import into a tobin-superpowers checkout. The user invokes this
skill with `/tobin-superpowers:promote-skill`. It never runs automatically.

Each step below needs the user. Ask one question at a time, wait for the
answer, and never treat silence, a passing check, or "continue" as approval.

## Safety Boundaries

Never:

- Automatically scan unrelated directories for skills. Read only the folder
  the user names.
- Synchronize work and personal repositories.
- Upload source files to GitHub without explicit authorization.
- Copy secrets, internal URLs, or confidential examples into personal artifacts.
- Assume company-created material belongs to the user.
- Modify the original source skill.
- Execute untrusted scripts without approval. Never execute untrusted
  candidate scripts simply because they are listed in the manifest.
- Overwrite existing skills silently.
- Automatically commit, push, publish, or open a PR.
- Modify official Superpowers skills.

Do not claim that automated checks establish legal ownership or guarantee
confidentiality. The validator is a heuristic; the user decides what they
may reuse.

## When Permission Is Unclear

If the user cannot say whether they may reuse the material (it was written
for an employer or client, it carries a confidentiality notice, or ownership
is simply unknown), do not adapt the source. Offer a clean-room
implementation instead: the user describes the generic requirements in their
own words, you write a new skill from that description alone (personal mode),
and nothing from the source is read or copied. If they decline, stop.

## Modes

- **Source mode** — the user gives the path of a local skill folder. Read
  only that folder, read-only. Use it to understand behaviour, then write
  the candidate fresh; carry over only generic content the user confirms
  they may reuse.
- **Personal mode** — no source files. Work from an authorized description,
  a public reference, or material the user confirms they may use, and write
  the candidate from that.

Both modes share the same lifecycle, staging layout, validation, review and
import.

## Lifecycle

### 1. Discover

1. Ask which mode. For source mode, ask for the exact skill folder path; for
   personal mode, ask for the description, public reference, or permitted
   material.
2. Ask who created the skill and under which employer, client, or contract,
   and whether the user may reuse it outside that context. Unclear → offer
   the clean-room route above.
3. Ask where to create the staging folder. Recommend a personal location
   outside any work repository and outside the destination checkout (or a
   git-ignored folder). The staging folder is named `skill-promotion/`.

### 2. Assess

- Source mode: list and read the named folder only. Run the validator on it
  in bare-skill mode (read-only; it never executes anything):
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate-portable-skill.py" <source-skill-folder>`.
  Do not run the source skill's scripts.
- Personal mode: restate the requirements and the material's origin.
- Summarize for the user: purpose, file inventory, company-specific details
  (paths, internal links, registries, credentials, confidentiality notices,
  people and team names), and dependencies. Recommend proceed, clean-room,
  or stop, and wait for the answer.

### 3. Design

Propose the candidate and wait for agreement:

- **Name** — lowercase letters, digits and single hyphens, at most 64
  characters, not an official superpowers skill or a tobin-superpowers
  built-in (`hybrid-planning`, `html-companion`, `promote-skill`).
- **Preserved** — the generic behaviour worth keeping.
- **Portability changes** — each company-specific detail and its generic
  replacement.
- **Exclusions** — what stays behind and why.
- **Files** — `SKILL.md` alone unless `references/`, `scripts/` or `tests/`
  are genuinely needed. Prefer the standard library for scripts and declare
  any other dependency.

### 4. Prepare

Write the staging folder; never write inside the source folder.

```
skill-promotion/
├── manifest.json
├── REVIEW.md
└── skill/
    ├── SKILL.md
    ├── references/   # only when needed
    ├── scripts/      # only when needed
    └── tests/        # only when needed
```

Write every file fresh with generic examples. Create `manifest.json` with
`"status": "draft"`, all approval flags `false` and `"digest": null`, and
`REVIEW.md` with `Status: pending` (templates below). Refer to the skill's own
files as `references/…`, `scripts/…`, `tests/…`, or, once imported,
`${CLAUDE_PLUGIN_ROOT}/skills/<name>/…`.

### 5. Validate

1. Static checks (structure and frontmatter, names, listed and referenced
   files, symlinks and path escapes, dependencies, manifest schema, REVIEW.md
   sections, and the advisory portability scan):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate-portable-skill.py" <staging>/skill-promotion
   ```

   Optionally pass `--deny-terms <file>` with employer, product, and project
   names. Keep that file outside the staging folder and never copy its terms
   into any artifact; findings never print the matched term.
2. Fix every error. Discuss each warning with the user — fix it or record
   why it stays in REVIEW.md.
3. Functional tests: show the manifest's `validation_commands` and ask before
   running any of them; they execute candidate code. Run them from
   `skill-promotion/skill/` only with the user's approval.
4. Record the results in REVIEW.md "Validation Results".

### 6. Review

Walk the user through REVIEW.md and recommend one outcome:

- `approved` — ready for the user's explicit approval (step 7).
- `needs-changes` — set both statuses to `needs-changes`, go back to Design
  or Prepare.
- `blocked` — set both statuses to `blocked`, keep the staging folder, and
  stop. Blocked candidates are never imported.

The recommendation is yours; the outcome is the user's.

### 7. Approve

Ask three separate questions and record each answer exactly:

1. "Do you approve this candidate as reviewed?" — content approval.
2. "May I copy it into your tobin-superpowers checkout?" — transfer
   authorization, a separate confirmation.
3. "Are you also authorizing publication (push or pull request)?" — default
   no. Approval does not imply publication permission.

Only after an explicit "yes" to question 1:

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate-portable-skill.py" <staging>/skill-promotion --digest`.
2. In `manifest.json` set `"status": "approved"`, `approved_by_user: true`,
   `digest` to that output, and the two authorization flags from questions 2
   and 3. In REVIEW.md "Approval" write `Status: approved`, `Transfer
   authorized: yes|no`, `Publication authorized: yes|no`.
3. Re-run the validator; it must pass. Any later change to `skill/` breaks
   the digest and needs a new review and approval.

A passing validator never sets approval, and you never record approval the
user did not give.

### 8. Guided Import

Only with `status: approved` and transfer authorized.

1. Ask for the tobin-superpowers checkout path. Show it back with its
   current branch and `git -C <path> remote -v`, and ask the user to confirm
   it is the intended destination.
2. Plan (changes nothing; shows git status, the current branch, the new
   branch, the target and every file):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/import-portable-skill.py" <staging>/skill-promotion --dest <checkout>
   ```

3. Resolve refusals with the user:
   - uncommitted changes: the user commits or stashes them, or you add
     `--worktree <new-path>` so the branch lives in a separate worktree;
   - `skills/<name>/` exists: add `--allow-overwrite` only if the user
     approves replacing it;
   - branch exists: choose another with `--branch`.
4. After the user confirms the plan, re-run with `--apply`. It creates the
   feature branch `promote-skill/<name>`, copies only the manifest's files
   into `skills/<name>/`, verifies the digest, and runs the candidate
   validator, the repository test suite and `claude plugin validate --strict`
   (when `claude` is on PATH).
5. Show the summary: branch, copied files, check results, and next steps.
6. Stop. Do not commit, push, or open a pull request; do not change versions
   or release metadata unless the user explicitly asks.

If the destination is unavailable, keep the candidate where it is and tell
the user the exact command to run once the checkout is available.

## Manifest Template

`manifest.json`, schema version 1. Paths in `files` are relative to `skill/`.
Never put source paths, employer names, internal URLs or credentials in it.

```json
{
  "schema_version": 1,
  "name": "example-skill",
  "description": "One sentence: what the skill does and when to use it",
  "mode": "personal",
  "requires": {
    "runtime": ["python3>=3.11"],
    "tools": ["Read", "Write"],
    "dependencies": []
  },
  "files": ["SKILL.md"],
  "validation_commands": [],
  "status": "draft",
  "approval": {
    "approved_by_user": false,
    "digest": null,
    "transfer_authorized": false,
    "publication_authorized": false
  }
}
```

`mode` is `source` or `personal`; `status` is `draft`, `needs-changes`,
`approved` or `blocked`.

## REVIEW.md Template

```markdown
# Skill Promotion Review: example-skill

## Purpose

What the skill does, in one or two sentences.

## Inventory

Every file in skill/ and its role.

## Preserved

Generic behaviour kept from the source or description.

## Portability Changes

Each company-specific detail and its generic replacement.

## Exclusions

What was left out and why.

## Remaining Dependencies

Runtimes, tools and packages the skill still needs.

## Validation Results

Static checks, warnings and their resolution, functional tests run (or not run, and why).

## Risks

Residual risks; automated checks do not establish ownership or confidentiality.

## Approval

Status: pending
Transfer authorized: no
Publication authorized: no
```

`Status` is `pending` (manifest `draft`), `needs-changes`, `approved` or
`blocked`, and always matches the manifest.

## Limitations

- The portability scan is pattern-based and advisory: it misses anything it
  has no pattern for (names, project code words, paraphrased internal
  details) and can flag harmless text. Use `--deny-terms` for known terms and
  read every file yourself.
- The digest proves the files are unchanged since approval was recorded; a
  script cannot prove a human approved. Approval is only as good as the
  conversation that recorded it.
- Portability does not establish permission to reuse employer-owned
  material.
- Imported skills with `references/` or `scripts/` need file-read or command
  permission when they run; headless sessions deny those by default.
- Claude Code caches plugins by version: an imported skill reaches installed
  copies only after the user commits it and, if they choose, bumps the
  plugin version.
