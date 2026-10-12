# Edge Cases

At plan time, for each function whose behaviour the change modifies, list the easy-to-miss inputs its type allows: empty, boundary, partial failure, duplicates/concurrency.

- Inputs a real caller or real data can reach get handling and a test.
- Type-allowed inputs nothing reaches are noted in the plan, not tested.
- If the type rules an input out, add no guard (`global/trust-types.md`).
- If the type is wrong, fix it where the data enters, within the change. Don't add downstream guards. Wrong means:
  - `any` / `Any` / `interface{}`
  - a required field real data omits
  - two copies of the type disagreeing about optionality

Easy to miss:
- TypeScript: an empty `T[]` passed to `items[0]` or `reduce` without an initial value
- Go: a write to a nil map, a zero-value struct treated as "set", an ignored `err`
- Python: `None` from `dict.get`, an iterator consumed twice

```ts
// no
const first = orders[0].id // orders can be empty
// yes
const first = orders.at(0)
if (!first) throw new Error('order list is empty')
```
