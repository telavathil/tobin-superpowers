# TypeScript lint baseline

Prerequisite: ESLint 9.24 or later with flat config. Otherwise the status is `can't ratchet (ESLint < 9.24)` and an upgrade PR is offered first.

Rules, all at `error`:
- `@typescript-eslint/no-floating-promises`
- `@typescript-eslint/no-misused-promises`
- `@typescript-eslint/no-explicit-any`
- `@typescript-eslint/no-unused-vars` with `{ argsIgnorePattern: '^_' }`
- `max-lines-per-function` with `{ max: 75, skipBlankLines: true, skipComments: true }`
- `complexity` with `15`
- `max-params` with `4`
- `max-depth` with `4`

```js
import tseslint from 'typescript-eslint';

export default tseslint.config(
  ...tseslint.configs.recommended,
  {
    files: ['**/*.ts'],
    languageOptions: { parserOptions: { projectService: true } },
    rules: {
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'max-lines-per-function': ['error', { max: 75, skipBlankLines: true, skipComments: true }],
      complexity: ['error', 15],
      'max-params': ['error', 4],
      'max-depth': ['error', 4],
    },
  },
);
```

Typed linting: the gap PR enables `parserOptions.projectService: true` and times a one-file lint. Over 5s, mark the config `typed lint too slow` and leave out the two promise rules.

Ratchet: run `npx eslint . --suppress-all` and commit `eslint-suppressions.json`. Run `npx eslint . --prune-suppressions` after cleanups, and don't add `--max-warnings` slack.

The gap PR is separate from feature work.
