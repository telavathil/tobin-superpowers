---
name: auditing-standards-coverage
description: Use when the user asks whether their coding standards (the standards files referenced from their agent instructions, or a project's own standards folder) were applied to an implementation plan or to generated code - "did my standards apply", "were the planning rules used", "review against my rules".
---

# Auditing Standards Coverage

## Overview

Answers "did my standards apply?" from the standards files themselves, never from a plan's summary of them or a reviewer's verdict. Plan coverage is measured by script; code is checked file by file.

## Inputs

| Input | Where |
|---|---|
| Global standards | the standards folder(s) the user's agent instructions point to; if none, ask |
| Project standards | the project's own standards folder, if it has one (wins on conflict) |
| Plan | path the user gives; if none, ask |
| Code | staged diff; if empty, `git diff <default-branch>...HEAD` - say which you used |

## Steps

1. **Plan coverage (mechanical).** Run:
   `python3 -I scripts/check-coverage.py <plan> <standards-dir> [<standards-dir> ...]`
   (path relative to this skill's folder). Pass every standards folder, global and project. The script prints per-standard `n/m verbatim`, every `MISSING` rule, and flags standards newer than the plan.
2. **Plan code blocks.** Check every code block in the plan against each standard that governs code or comments.
3. **Foreign conventions.** Search plan and diff for instructions or markers that come from neither the spec nor the standards (e.g. comment tags or markers added by other tools or plugins). Check each against the standards.
4. **Code.** List every changed source and test file. Check each one against every standard. Docs, config and IaC files: check only for ticket IDs and comments, and say so under "Not checked". Any file you did not open goes in "Not checked".

## Output contract

Your answer is exactly these parts, in order:

1. **Verdict** - one line each:
   - `Plan: FOLLOWED` only if the script reports n/n; otherwise `Plan: NOT FOLLOWED - x/y rules verbatim`.
   - `Code: n violations, k borderline across m files`. Borderline = matches a rule's pattern but an exception or the spec arguably allows it; list these after the violations table with the reason.
   - If any standard is newer than the plan: `Standards postdate the plan - plan could not have used them`.
2. **Plan coverage table** - standard | verbatim count | missing rules (short form).
3. **Violations** - table: standard | file:line | what | rule text quoted from the standard file.
4. **Foreign conventions** - each one, and whether it conflicts with a standard.
5. **Not checked** - files or areas not opened, and why.

A condensed or paraphrased rules section in the plan counts as missing: implementers only see the plan, so rules absent from it never reached them.

## Common mistakes

| Mistake | Fix |
|---|---|
| "Mostly yes" when coverage < 100% | Verdict comes from the script count |
| Trusting the plan's "(verbatim)" heading | Run the script |
| Grepping a sample of the diff | Every changed file, or list it under Not checked |
| Judging against the plan's restated rules | Judge against the standard files |
