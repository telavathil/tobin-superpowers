# Skill Promotion

`promote-skill` turns one Claude Code skill — an existing local skill or a
description of one — into a portable, company-independent candidate, reviews
it with you, and, only after your explicit approval and a separate transfer
authorization, guides a local import into a tobin-superpowers checkout. It
is manual: it has no hook and Claude never loads it on its own.

```
/tobin-superpowers:promote-skill
```

## Modes

- **Source mode** — you name a local skill folder. Claude reads only that
  folder, read-only, and writes the candidate fresh; the source is never
  modified and its scripts are never run.
- **Personal mode** — no source files. Claude works from a description you
  are authorized to give, a public reference, or material you confirm you
  may use. This is also the clean-room route Claude offers whenever
  permission to reuse the source is unclear.

Both follow the same lifecycle: Discover → Assess → Design → Prepare →
Validate → Review → Approve → Guided Import.

## Staging and Review

The candidate is built in a staging folder you choose (keep it outside work
repositories and outside the destination checkout):

```
skill-promotion/
├── manifest.json   # schema_version 1: name, description, mode, requires, files,
│                   # validation_commands, status, approval
├── REVIEW.md       # purpose, inventory, preserved, portability changes, exclusions,
│                   # remaining dependencies, validation results, risks, approval
└── skill/
    ├── SKILL.md
    └── references/ scripts/ tests/   # only when needed
```

The manifest never holds source paths, employer names, internal URLs or
credentials. Check a candidate (or, read-only, a source skill folder) with:

```bash
python3 scripts/validate-portable-skill.py path/to/skill-promotion [--deny-terms private-terms.txt] [--json]
```

It checks structure and frontmatter, name rules (no official superpowers or
built-in names), listed and referenced files, symlinks and path escapes,
undeclared Python dependencies, the manifest schema, REVIEW.md sections, and
that the approval record still matches the files. Its portability scan flags
absolute machine paths, private hosts and internal URLs, credential-like
strings (values are never printed), organisation config such as private
registries, and confidentiality notices; `--deny-terms` adds your own
employer or project names from a file kept outside the candidate. It reads
files only — it never runs candidate scripts or the manifest's
`validation_commands`; Claude asks before running those.

Review ends in `approved`, `needs-changes` or `blocked`, and the outcome is
yours.

## Approval and Transfer

Approval is explicit and recorded only after you say so; a passing
validator never sets it. Claude then asks two more, separate questions: may
the candidate be copied into your tobin-superpowers checkout (transfer), and
may it be published (push or pull request, default no). Approval does not
imply either. The manifest stores a SHA-256 digest of the approved files;
any later change invalidates the approval.

## Guided Import

```bash
python3 scripts/import-portable-skill.py path/to/skill-promotion --dest /path/to/tobin-superpowers           # plan only
python3 scripts/import-portable-skill.py path/to/skill-promotion --dest /path/to/tobin-superpowers --apply   # after you confirm
```

Claude asks for the checkout path and has you confirm it. The importer
refuses unless the candidate validates, is approved, matches its digest and
has transfer authorization; it also refuses a destination that is not a
tobin-superpowers checkout root, has uncommitted changes (use
`--worktree PATH` to work in a separate git worktree instead), already has
the branch, or already has `skills/<name>/` (`--allow-overwrite` only after
you approve replacing it; built-in and official superpowers skills are never
replaced). With `--apply` it creates `promote-skill/<name>`, copies exactly
the manifest's files into `skills/<name>/`, and runs the candidate
validator, the repository test suite and `claude plugin validate --strict`
(when `claude` is on `PATH`). It never commits, pushes, tags, opens a pull
request, or changes versions — those stay with you. If the checkout is
unavailable, the candidate stays in staging with instructions to re-run.

## Limitations

- The portability scan is pattern-based and advisory. It misses what it has
  no pattern for (people, project code words, paraphrased internal details)
  and can flag harmless text; read every file yourself.
- Portability does not establish permission to reuse employer-owned
  material, and no automated check establishes ownership or guarantees
  confidentiality.
- The digest proves the files are unchanged since approval was recorded; a
  script cannot prove that a human approved.
- Imported skills with `references/` or `scripts/` need read or command
  permissions when they run, which headless sessions deny by default.
- An imported skill reaches installed copies only after you commit it and,
  if you choose, bump the plugin version.
