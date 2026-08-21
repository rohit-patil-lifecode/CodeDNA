---
paths:
  - "{{PATH_GLOB}}"
---

# {{SUBSYSTEM_ID}}

<!--
This is a path-scoped rule. Claude Code loads it whenever it reads a file
matching any glob above, no matter which directory that file is in. That is why
it exists: this subsystem's code spans folders, so no single nested CLAUDE.md
could ever hold its rules.

Use this shape when an invariant is only true across a seam — a PHP layer and
its JS counterpart, an event producer and its consumers, a schema and the code
on both ends of it. A rule that belongs to one directory belongs in that
directory's CLAUDE.md instead.

Keep it under 40 lines: it loads on every session that touches any of these
paths, so its length is a recurring cost.
-->

{{PURPOSE}}

## Rules

<!-- Invariants that hold ACROSS the seam. The ones neither side owns alone. -->

- {{RULES}}

## Gotchas

<!-- What breaks when the two sides disagree: ordering, a key that must match,
     a call that fires twice. Empty until someone has been bitten. -->

- {{GOTCHAS}}

## The contract

<!-- Point at the schema, type, or spec that defines what crosses the seam.
     If there isn't one, say so — that absence is the finding. -->

- {{CONTRACT}}
