---
module: {{MODULE_ID}}
owner: {{OWNER}}
---

# {{MODULE_ID}}

<!--
Read on demand, not automatically — CLAUDE.md in this folder points here.
So this file answers "what is true here, and why", while CLAUDE.md carries
the things that must be obeyed. Never write the same fact in both.

Keep it under 60 lines.
-->

## Responsibility

<!-- What this module owns, and the edge of what it owns. One or two lines.
     Fill this in at scaffold time — it reads straight off the folder. -->

- {{RESPONSIBILITY}}

## Why it is this way

<!-- The reasoning a reader cannot recover from the code: what forced the
     design, what was tried and abandoned, what constraint it is bending to.
     This is the section that has no other home — the code cannot hold it,
     and the person who knows it will leave.

     Leave it EMPTY until someone can actually say. Not "UNKNOWN": empty means
     nothing to say yet, which is normal for a new module, while UNKNOWN means
     someone owes an answer and gets counted as an open question. -->

## Related ADRs

<!-- Delete this section if there are no ADRs yet. "None" is an answer; UNKNOWN
     is not. -->

<!--
Deliberately not here:

- rules and gotchas — they belong in CLAUDE.md, which auto-loads, so they
  are present at the moment Claude would otherwise break them
- file lists, public surface, dependencies, dependents, test commands,
  last_updated — all derivable from the code or from git. A stale copy of a
  derivable fact is worse than no copy: it gets repeated with confidence.
-->
