# Fallbacks

Required values fail fast. Don't invent defaults.

Forbidden:
- `value ?? 'default'` / `value || fallback` on a value that should always be present
- `.catch(() => {})` or `catch {}` that swallows an error
- Returning `[]`/`null`/`{}` to hide a missing upstream value

Allowed:
- A default the spec or API contract actually defines (a schema or DTO field with a documented default)
- Legacy data that is genuinely optional - name it at the type level (`field?: T`), then handle both cases explicitly
