# Plan Code

Applies when writing an implementation plan. Plan code is copied verbatim by implementers, so it must be final code.

- Code blocks contain no comments unless the comment meets `global/comments.md`. Explanation goes in the plan prose around the block.
- No helpers, constants, types or files a task doesn't need. Three similar lines beat a *new speculative* abstraction, but if a task would copy an existing block, extract it first.
- Follow the best existing pattern for the concern, not the nearest one, and name it in the task (e.g. 'use the existing `Store` interface', 'build responses with `toResult`'). Don't add a new variant.
- Tests cover the behaviour the spec asks for. Don't add speculative edge-case tests just to fill a "Review Focus" quota; each one needs a realistic input that could reach the code.
- Copy the binding rules from every applied standard into the plan's **Global Constraints** section, verbatim. The task reviewer and implementers only see the plan, not these files.
- Shared test builders and helpers created in one task are named in that task's **Produces** and in every later task's **Consumes**, so each implementer reuses them instead of writing their own.

## Refactoring scope

- Refactoring is part of the change, not deferred.
- Scope is measured in *functionality* (the features the change modifies and the tests covering them), not files.
- Never diff into code that unrelated features depend on, even if the refactor is good.
- Weigh the refactor's value against current quality and clean-code principles, and against risk to unrelated features.
- Untested code: add a characterization test first, or report instead of refactoring.
- An in-scope refactor is its own task, with its helper under **Produces**.
- An out-of-scope refactor is reported with its scope, e.g. "4 variants of version dispatch across 7 handlers". Then ask the user whether to record it in the repo's debt location (from the injected repo state) or add it to this plan as Task 0. If no debt location is recorded, ask for one.
- Implementers don't change refactor scope mid-task.
