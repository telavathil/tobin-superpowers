# Word Frequency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--top N` flag and a syllable counter to `textstats`.

**Architecture:** Pure functions in `textstats/core.py`; `textstats/cli.py` only parses and prints.

**Tech Stack:** Python 3 stdlib, `unittest`.

---

### Task 1: `top_words` and `--top` flag

**Files:**
- Modify: `textstats/core.py` (append after `word_count`)
- Modify: `textstats/cli.py:8-23`
- Test: `tests/test_core.py`

**Interfaces:**
- Produces: `top_words(text: str, n: int) -> list[tuple[str, int]]` — count desc, then word asc.
- Produces: CLI flag `--top N`; `positive_int(s: str) -> int` raises `argparse.ArgumentTypeError`.

**Pattern to follow:** `words()` at `textstats/core.py:7`; `build_parser` at `textstats/cli.py:8`.

- [ ] **Step 1: Write failing tests** in `tests/test_core.py`:
  - `top_words("b a b a c", 2) == [("a", 2), ("b", 2)]`
  - `top_words("", 3) == []`
- [ ] **Step 2: Run** `python3 -m unittest tests.test_core -v` → Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `top_words`: `Counter(words(text))`, sort by `(-count, word)`, slice `[:n]`.
- [ ] **Step 4: Wire the CLI**: add `positive_int` and `--top`; print `f"{w}: {c}"` after the `words:` line.
- [ ] **Step 5: Verify** `python3 -m unittest discover -s tests -v` → Expected: all pass, exit 0.
- [ ] **Step 6: Commit** `git commit -am "feat: add --top N"`

---

### Task 2: Syllable counter

**Files:**
- Modify: `textstats/core.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Produces: `count_syllables(word: str) -> int` — always ≥ 1.

**Pattern to follow:** none — new module-level helper.

**Algorithm:**
```
n = number of vowel groups [aeiouy]+ in word
if word ends in "e" and not consonant + "le": n -= 1
return max(n, 1)
```

- [ ] **Step 1: Write failing tests**: `cat→1`, `table→2`, `make→1`, `rhythm→1`.
- [ ] **Step 2: Implement** `count_syllables` per the algorithm.
- [ ] **Step 3: Verify** `python3 -m unittest tests.test_core -v` → Expected: 4 new tests pass.

## Self-Review

- Spec coverage: `--top` (Task 1), syllables (Task 2).
