# Incomplete Plan

**Goal:** Demonstrate validator findings.

### Task 1: Config loader

**Files:**
- Create: `app/config.py`
- Test: `tests/test_config.py`

**Pattern to follow:** `app/settings.py:10`

- [ ] **Step 1: Write failing test**: `load_config("x.toml")` raises `FileNotFoundError`.
- [ ] **Step 2: Implement** `load_config`.
- [ ] **Step 3: Verify** `python3 -m unittest tests.test_config -v` → Expected: PASS.

### Task 2: Cache layer

**Files:**
- Create: `app/cache.py`

**Interfaces:**
- Produces: `Cache.get(key: str) -> bytes | None`

**Pattern to follow:** none

- [ ] **Step 1: Write tests**: `Cache().get("missing") is None`.
- [ ] **Step 2: Implement** the cache. TBD: eviction policy.

### Task 3: Wire everything

**Files:**
- Modify: `app/main.py`

**Interfaces:** No new interfaces.

- [ ] **Step 1:** Update main and handle edge cases.
- [ ] **Step 2:** Write tests for the above.
