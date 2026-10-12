# Type Safety (TypeScript)

Applies to new and changed lines. Don't rewrite untouched code to comply.

Forbidden:
- `any` - use `unknown` and parse it
- `as Type`, including `as never` and `as unknown as T` - parse at the boundary or fix the upstream type (see `global/trust-types.md`)
- `!` non-null assertion - handle the null
- `@ts-ignore`, `@ts-expect-error`, `eslint-disable`

Prefer discriminated unions over objects with many optional fields:

```ts
// weak
type Actor = { kind: 'user' | 'system'; userId?: string; service?: string };
// strong
type Actor = { kind: 'user'; userId: string } | { kind: 'system'; service: string };
```

Exceptions:
- `as const`
- In specs, a partial mock of a large framework or SDK type (request context, ORM document, AWS client) may be cast. Domain objects come from typed builders (`global/testing.md`), never casts.
