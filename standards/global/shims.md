# Compatibility Shims

When removing or renaming something, update every caller in the same change and delete the old form.

Forbidden:
- An alias kept for a renamed export: `export { newName as oldName }`
- A parameter widened to accept the old and new shape
- A dead optional field kept "for compatibility"
- A Go deprecated wrapper func that forwards to the new one
- Python `**kwargs` swallowing a removed argument

Allowed:
- A shim for callers that can't be updated (external clients, published APIs, LLM clients sending a removed argument), with those callers named in a comment that meets `global/comments.md`

```ts
// no: nothing says who still needs it
export { createInvoice as makeInvoice }
// yes: callers named
// the public SDK v1 still calls makeInvoice; keep until v1 is retired
export { createInvoice as makeInvoice }
```
