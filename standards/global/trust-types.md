# Trust the Types

Validate untyped data once, where it enters. After that, trust the type.

Entry points that must validate (schema parse, DTO validation):
- HTTP request bodies, params, query
- Database reads of loosely-typed or legacy fields
- Queue/stream/event payloads
- Third-party API responses, env vars, files

Everywhere else, forbidden:
- Runtime checks for values the type rules out: `if (mapped == null)` on a total `Record<Enum, T>`
- Tests that cast to reach those checks: `fn('BANANA' as Status)`
- Hand-written type guards (`value is X`) for data that already has a schema - parse it with that schema instead
- Identity maps that map each enum value to itself, plus tests asserting `map[x] === x`

If an impossible case still needs handling for exhaustiveness, use a `never` check in the `switch` default - the compiler proves it, no test needed.
