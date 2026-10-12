# Reuse Before Writing

Before adding a helper, type, constant or wrapper, search for an existing one.

- Derive types from existing ones: `keyof PayloadMap`, `Extract<...>`, `Pick<...>` - don't redeclare a string union of names that a type map already lists.
- Name an intersection type once and reuse it; don't repeat it inline in each signature.
- No one-line private wrappers that only forward to another call with fixed arguments.
- No hand-maintained list that copies another list (`IMPLEMENTED = new Set([...])` mirroring a registry) - derive it.
- Two functions with the same body are one function.

Limit: share code that changes for the same reason. Code that merely looks alike can stay separate.
