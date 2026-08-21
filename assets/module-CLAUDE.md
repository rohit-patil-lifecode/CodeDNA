# Module: {{MODULE_ID}}

<!--
This file auto-loads: Claude Code includes a subdirectory's CLAUDE.md the first
time it reads a file in that directory. So this is where anything that must be
obeyed goes — it arrives without anyone running a command.

Because it loads on every session that touches this module, its length is a
recurring cost. Keep it under 40 lines. If a line would not change what Claude
does on a typical edit, it belongs in architecture.md instead.

Not re-injected after /compact; reloads next time Claude reads a file here.
-->

{{PURPOSE}}

Read `architecture.md` in this folder before changing this module.

## Rules

<!-- Imperatives: what must, or must not, happen here. Empty until you can
     state one — empty, not UNKNOWN. -->

- {{RULES}}

## Gotchas

<!-- Traps that would produce a bug if you did not know them, each saying what
     BREAKS if you do not. A rule says what to do; a gotcha says what happens
     when you do not, and that is the part that stops a plausible-looking fix.

     Hunt for them rather than waiting to be bitten. The code already records
     every bug someone hit: defensive checks that should not be needed, retries
     and gratuitous awaits, "do not remove" / HACK / FIXME comments, ordering
     that must hold, shared mutable state, anything crossing an iframe, worker
     or process boundary.

     Speculation is not a gotcha. "This might race" with nothing behind it is
     the confident wrongness this file exists to prevent. -->

- {{GOTCHAS}}

## After changes

- Boundary, rule, or reasoning changed? Update `architecture.md` in the same change.
- Not for internal refactors that change nothing a caller can observe.
- New architectural decision? Add an ADR under `docs/decisions/`.
- Run: {{TEST_COMMAND}}
