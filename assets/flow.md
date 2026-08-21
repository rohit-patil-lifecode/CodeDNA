---
paths:
  - "{{PATH_GLOB}}"
---

# Flow: {{FLOW_NAME}}

<!--
A flow is how one thing actually travels through the system, end to end.

It is a path-scoped rule, so Claude Code loads it whenever it reads a file at
ANY step. That is the point: editing step 2 shows you steps 1 and 3, which is
the context a fix needs and the thing a module doc can never give you — a module
doc describes a box, never the path through it.

Write a flow when tracing it costs more than reading it, and getting it wrong
causes a real bug. Two or three flows usually cover a system. Do not write one
per function.

Every step must name a real file, and a symbol where there is one, so `verify`
can check the flow has not silently drifted. A step with no file is prose, not a
flow.

Keep it under 40 lines.
-->

**Trigger:** {{WHAT_STARTS_IT}}

## Path

1. `{{FILE}}` → `{{SYMBOL}}` — {{WHAT_HAPPENS_HERE}}
2. `{{FILE}}` → `{{SYMBOL}}` — {{WHAT_HAPPENS_HERE}}

**Ends:** {{WHERE_IT_FINISHES}}

## Invariants along this path

<!-- What must hold ACROSS steps — the reason the flow is written down rather
     than re-traced. A key that must match between two steps, an ordering, a
     step that may run twice. Rules true inside one step belong in that
     module's CLAUDE.md instead. -->

- {{INVARIANTS}}

## When it breaks

<!-- Where failures actually surface, which is often not where they originate.
     Empty until someone has debugged it. -->

- {{FAILURE_MODES}}
