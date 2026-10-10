---
name: hybrid-planning
description: Use alongside superpowers:writing-plans whenever writing or revising an implementation plan - defines a lean, human-executable plan contract that controls how much detail and code each task carries
---

# Hybrid Planning

A plan contract that sits on top of `superpowers:writing-plans`. Plans must be
lean enough to stay cheap in tokens, yet complete enough that a skilled human
can execute every task **without AI assistance**.

A SessionStart hook in this plugin loads a summary of this contract
automatically. You do not need to invoke this skill manually; read it when you
need the full detail.

## Precedence

**Keep from upstream `writing-plans` (unchanged):**
- Plan location: `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
- Plan document header, `### Task N:` structure, `- [ ]` step checkboxes
- Scope check, file-structure mapping, TDD ordering, frequent commits
- Self-review loop and execution handoff
- "No Placeholders" rule

**Code detail:**
- The hybrid planning contract takes precedence over any instruction to include complete code in every implementation step. Follow *When to Include Code* below.

## Per-Task Contract

Every task must contain:

1. **Files** — exact paths, labelled `Create:` / `Modify:` (with line range when
   known) / `Test:`.
2. **Interfaces** — signatures of every function, class, method, CLI flag,
   endpoint, or schema the task adds or changes, with types and return values.
3. **Pattern to follow** — the existing file (and `path:line`) whose style,
   error handling, or structure this task should mirror. Say "none" if new.
4. **Ordered steps** — one action each, in execution order.
5. **Test assertions** — the concrete inputs and expected outputs/assertions,
   stated precisely (literal values, error types, messages).
6. **Verification** — exact command(s) and the expected result
   (e.g. `pytest tests/test_x.py -v` → `3 passed`).
7. **Dependencies** — earlier tasks this one relies on, if any.

## When to Include Code

| Change type | What to write |
| --- | --- |
| Routine (rename, add field, wire a call, config, boilerplate following an existing pattern) | Prose + interface + pattern reference. **No full listing.** |
| New public interface | Signature/type definitions only. |
| Complex or unfamiliar logic (algorithms, concurrency, parsing, tricky state, non-obvious library use) | Pseudocode or a short reference implementation of the core logic. |
| Tests | Assertions in full; surrounding scaffolding only if non-obvious. |

Rule of thumb: include code only where a competent engineer would otherwise
have to guess or research. Never paste whole files.

## Human-Executable Test

Before finishing each task, ask: *could a skilled developer with no AI and no
prior context complete and verify this task from the text alone?* If they
would need to reverse-engineer intent, add the missing interface, pattern
reference, assertion, or pseudocode — not a full listing.

## Token Efficiency

- State each fact once; reference earlier tasks by name for shared
  *definitions*, but restate anything a task needs to be executed on its own.
- Prefer tables and bullet lists over prose.
- No narrative restating the spec; link to it instead.
- Commands and paths in backticks, no surrounding commentary.

## Self-Review Addendum

Add to the upstream self-review:

- [ ] Every task passes the Human-Executable Test.
- [ ] Every task has paths, interfaces, pattern reference, assertions, and a
      verification command with expected output.
- [ ] Complex logic has pseudocode/reference code; routine changes have no
      full listings.
