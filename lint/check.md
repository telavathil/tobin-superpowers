# Lint baseline check

Run once per repo, on the first plan, then for newly touched configs on later plans. Baselines: `typescript.md`, `go.md`, `python.md` in this directory.

1. Find the languages of the files the plan touches, and the lint config each one falls under. Check per config, not per repo: a monorepo can have several.
2. Compare each config against the matching baseline. Note missing rules, rules set to `warn`, and a missing ratchet (suppressions file, baseline, or merge-base setting).
3. Ask the user once for the repo's debt location (usually Jira): where out-of-scope work gets recorded.
4. Report the gaps in one message. Offer the gap PR as separate work outside the feature plan, then continue writing the plan.
5. Write the marker file at the path named in the injected context, creating its directory:

```
Checked: YYYY-MM-DD
Debt location: <text>

## Configs
- <config path>: <status>
```

Status is one of `baseline`, `gap PR offered`, `can't ratchet (ESLint < 9.24)`, `typed lint too slow`.

6. On later plans, the marker is injected as the repo's recorded state. For touched configs that aren't listed in it, run steps 2, 4 and 5, and append them to the marker.
