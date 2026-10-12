# Comments

Default: no comment. A comment must explain a *why* that stays true as long as the code does.

Forbidden:
- Narrating the change: `// removed X - no longer needed`, `// now uses Y`
- Ticket/time scope: `// nothing reads this yet`, `// out of scope for this ticket`, `// Task 3 fills this in`
- Pointers that go stale: file paths, `file:line`, "see the design spec"
- Defending a review fix: `// kept as one constant so the call sites can't drift`
- Restating the code, including JSDoc that repeats the signature
- Arithmetic in tests: `// 15 lines x 21.6 = 324` - see `global/testing.md`
- Labels in tests: `// Edge case:`, `// Money rule:` - put it in the `it(...)` name instead

Allowed:
- Non-obvious constraints from outside the code: `// the payment provider retries webhooks for 3 days, so this handler must be idempotent`
- Links to an ADR, or a blocking ticket with a removal condition: `// WARN: remove once PROJ-123 lands`

## Ticket IDs and plan references

No ticket IDs, `Task N`, or `Step N` anywhere in code - not in comments, `describe`/`it` names, error messages, log messages or constant names. The only exception is the `WARN: remove once` comment above.

```ts
// no
describe('clamp floor (PROJ-123)', ...)
throw new Error(`unmapped status ${status}; see PROJ-123`)
// yes
describe('clamp floor', ...)
throw new Error(`unmapped status ${status}`)
```

Rationale for a change belongs in the commit message or PR, not the code.
