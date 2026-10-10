# Maintaining the Fork

How to merge updates from upstream [obra/superpowers](https://github.com/obra/superpowers)
into this fork.

## Mental Model

Every modification to a forked skill sits inside markers:

```
<!-- tobin-superpowers:html-companion:start -->
...your changes...
<!-- tobin-superpowers:html-companion:end -->
```

**Outside the fences:** upstream owns the content. Anything that changes
there in a new upstream release should be applied verbatim to your fork.

**Inside the fences:** you own the content. Upstream doesn't know it
exists. Touch this only when *you* decide to change how the HTML companion
behaves.

Sibling prompt files (`visual-companion.md`, `code-reviewer.md`,
`implementer-prompt.md`, etc.) live entirely outside the fenced model —
they are byte-identical copies of upstream and get straight `cp`'d on
merge.

## The Workflow

### 1. See what changed upstream

Claude Code caches every version of every installed plugin. Diff your
fork's base version against the newest cached version:

```bash
# What versions of superpowers does Claude Code have?
ls ~/.claude/plugins/cache/claude-plugins-official/superpowers/

# Pick the version your fork was last synced against (FROM_VER) and the
# new one you want to merge in (TO_VER).
FROM_VER=5.1.0
TO_VER=5.2.0
UP_BASE=~/.claude/plugins/cache/claude-plugins-official/superpowers

for skill in brainstorming writing-plans requesting-code-review subagent-driven-development; do
  echo "=== $skill ==="
  diff -u "$UP_BASE/$FROM_VER/skills/$skill/SKILL.md" \
          "$UP_BASE/$TO_VER/skills/$skill/SKILL.md"
done
```

If a skill shows no diff, skip it. Also check sibling prompt files for
each of the four skills — they may have changed even if `SKILL.md` did not.

### 2. Merge the changes

Three cases, easiest first:

- **Only a sibling prompt file changed** (e.g. `code-reviewer.md`):
  straight copy from new upstream into your fork. No fences to worry
  about.

- **`SKILL.md` changed outside the fenced region:** open old upstream,
  new upstream, and your fork side by side. Apply the upstream changes to
  your fork's `SKILL.md`. Leave the fenced block untouched.

- **`SKILL.md` changed inside or directly adjacent to the fenced region:**
  this is the manual case. Read the upstream diff, decide whether your
  fenced content still makes sense. Example: if upstream renames the
  "Self-Review" section to "Plan Review", your fenced text saying *"Run
  this after the Self-Review loop is clean"* needs an update too.

### 3. Watch for the brainstorming checklist renumber

`brainstorming/SKILL.md` is the one skill where the fork has an
unavoidable non-fenced edit: the original item `9. Transition to
implementation` is renumbered to `10.` because the fenced item 9
("Offer HTML companion") sits between 8 and the original 9.

If upstream adds or removes checklist items, your numbering will drift.
After every merge, eyeball the checklist and confirm:

- All items are sequentially numbered
- The fenced HTML companion item sits between the user-review-gate item
  and the transition-to-implementation item
- The transition-to-implementation item is the last one (renumbered if
  needed)

### 4. Bump the fork's version

Edit `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` —
bump the fork's own version (`0.1.0` → `0.2.0`). The fork versions
independently from upstream. Don't try to mirror upstream's version.

### 5. Verify the diff is still minimal

Strip the fenced blocks out of each forked `SKILL.md` and confirm the
result is identical to new upstream (modulo whitespace and the known
brainstorming renumber):

```bash
TO_VER=5.2.0
UP_NEW=~/.claude/plugins/cache/claude-plugins-official/superpowers/$TO_VER
FORK=~/dev/tobin-superpowers

for skill in brainstorming writing-plans requesting-code-review subagent-driven-development; do
  echo "=== $skill ==="
  awk '/<!-- tobin-superpowers:html-companion:start -->/{skip=1} !skip; /<!-- tobin-superpowers:html-companion:end -->/{skip=0}' \
    "$FORK/skills/$skill/SKILL.md" > /tmp/stripped-$skill.md
  diff -u "$UP_NEW/skills/$skill/SKILL.md" /tmp/stripped-$skill.md
done

echo "=== Sibling file integrity ==="
for f in brainstorming/visual-companion.md \
         brainstorming/spec-document-reviewer-prompt.md \
         writing-plans/plan-document-reviewer-prompt.md \
         requesting-code-review/code-reviewer.md \
         subagent-driven-development/implementer-prompt.md \
         subagent-driven-development/spec-reviewer-prompt.md \
         subagent-driven-development/code-quality-reviewer-prompt.md; do
  diff -q "$UP_NEW/skills/$f" "$FORK/skills/$f" && echo "OK: $f"
done
```

Each skill should come back with either zero diff or only:

- Whitespace differences
- The known `9. → 10.` renumber in `brainstorming`
- In `brainstorming`, three hand-off references qualified as
  `superpowers:writing-plans` (checklist item 10, "The terminal state is
  invoking…", and "Invoke the … skill to create a detailed implementation
  plan"), so the hand-off goes to upstream rather than this fork's copy

Anything else means an upstream change leaked into a place it shouldn't
have. Back out and retry.

### 6. Commit, push, reload

```bash
cd ~/dev/tobin-superpowers
git add -A
git commit -m "chore: merge superpowers $TO_VER upstream"
git push
```

Then in Claude Code:

```
/plugin marketplace update tobin-superpowers-dev
/reload-plugins
```

## When *Not* to Merge

If upstream restructures one of the four skills heavily — splits the
skill in two, removes a section your fenced block depends on, rewrites
the checklist — your fenced block may no longer fit cleanly into the
new flow.

In that case, treat it as a redesign rather than a merge:

1. Re-read the original spec at
   `~/dev/html-companion-plugin-spec.md`
2. Pick a fresh insertion point in the new upstream `SKILL.md`
3. Rewrite the fenced block to fit
4. Re-verify with step 5 above

The fenced markers are a *bookkeeping* tool — they let you find your
changes quickly. They are not a guarantee that the merge is semantically
correct. You still have to read what upstream did and decide whether
your customization still fits.

## Plugin-Owned Hooks and Scripts

`hooks/`, `scripts/`, `skills/hybrid-planning/`, and `tests/` are fully owned
by this repository — upstream merges never touch them, and they are not
fenced. After any change to them, or after an upstream merge:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-plan.py tests/fixtures/valid-plan.md       # exit 0
python3 scripts/validate-plan.py tests/fixtures/incomplete-plan.md  # exit 1
```

When upstream `writing-plans` changes its plan format, re-check the
validator against a freshly generated plan and against upstream's own
`docs/superpowers/plans/*.md`. Those older plans predate the hybrid
contract, so `interfaces` and `pattern` findings there are expected;
anything flagged as a `placeholder` or a `files` error on a task that
clearly lists files is a validator bug — fix the heuristic and add a test.

`skills/html-companion/SKILL.md` is also plugin-owned. Its "Companion: …"
sections were migrated from the fenced HTML companion blocks in Phase 3, and
its "Shared Output Guide" is a verbatim copy of
`skills/shared/html-companion-guide.md`. `tests/test_html_companion_skill.py`
checks that every rendering-priority bullet and offer question in the forks
still appears in the skill, and that the guide copy matches the guide file.

- Changing the guide: edit `skills/shared/html-companion-guide.md`, then
  paste the same text into the skill's "Shared Output Guide" section.
- Changing a fork's fenced block before Phase 4: make the same change in the
  matching "Companion: …" section — the test pins the fenced blocks' hashes
  so the drift is caught. (Upstream merges outside the fences do not affect
  those hashes.)
- Keep everything the skill needs inside `SKILL.md`; separate supporting
  files are unreadable in headless runs.

```bash
python3 scripts/validate-html-companion.py tests/fixtures/companions/plans/2026-01-01-demo.html  # exit 0
```

Keep validation advisory: the PostToolUse hook must exit 0 for plan
findings, must never write to the plan, and must stay silent for
non-plan files.

## What About the Shared HTML Companion Guide?

`skills/shared/html-companion-guide.md` is fully owned by this fork —
upstream doesn't know it exists. You only edit it when *you* want to
change how the HTML output works (e.g. swap the color palette, add a new
component pattern, tighten the style rules).

When you edit it, every skill that references it will pick up the change
on next `/reload-plugins`. No coordination with upstream needed.
