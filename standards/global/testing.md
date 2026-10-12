# Testing

## Shared builders

- One builder per domain object, in a shared test helper file next to the module - not a copy per spec file.
- Builders return a complete valid object and take a typed `Partial<T>` of overrides.
- Before writing a builder, search for an existing one and extend it.
- In plans: the task that creates a builder lists it under **Produces**; every later task that needs it lists it under **Consumes**.

```ts
export const buildInvoice = (overrides: Partial<Invoice> = {}): Invoice => ({
  invoiceId: 'doc-1',
  accountId: 1,
  sections: [],
  ...overrides,
});
```

## Expected values

- Assert literal expected values. Don't show the derivation in a comment.
- If the meaning of the number matters, put it in the test name: `it('wraps a 298-char h4 onto 15 lines', ...)`.
- Don't re-implement the formula under test to compute the expectation.

## Casts

- No `as` / `as never` / `as any` on domain data in specs - use the builder. See `global/type-safety.md` for the framework-mock exception.
