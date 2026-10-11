# Greeting Service Plan (missing dependencies)

**Goal:** Add a greeting helper and expose it through the CLI.

### Task 1: Greeting helper

**Files:**
- Modify: `src/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: `greet(name: str) -> str`

**Pattern to follow:** `src/util.py:5`

- [ ] **Step 1: Write failing test**: `greet("Ann") == "Hi Ann"`
- [ ] **Step 2: Implement** `greet` with an f-string.
- [ ] **Step 3: Verify** `python3 -m unittest tests.test_app -v` → Expected: PASS

### Task 2: CLI flag

**Files:**
- Modify: `src/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: CLI flag `--name NAME`

**Pattern to follow:** `build_parser` at `src/cli.py:8`

- [ ] **Step 1: Write failing test**: stdout of `main(["--name", "Ann"])` == `"Hi Ann\n"`
- [ ] **Step 2: Implement** the flag and call `greet`.
- [ ] **Step 3: Verify** `python3 -m unittest tests.test_cli -v` → Expected: PASS

### Task 3: README usage

**Files:**
- Modify: `README.md`

**Interfaces:** No new interfaces.

**Pattern to follow:** none (first usage section).

- [ ] **Step 1:** No tests: documentation-only change.
- [ ] **Step 2:** Add a usage example for `--name`.
- [ ] **Step 3: Verify** `grep -n -- "--name" README.md` → Expected: one match
