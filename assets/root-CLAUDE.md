<!-- codedna:start — managed section. Edit freely; keep the markers so a
     teammate running `setup` updates this block instead of duplicating it. -->
# CodeDNA

This repository keeps engineering context next to the code. Each module folder
has a `CLAUDE.md` (rules and gotchas, auto-loaded when you read files there)
and an `architecture.md` (what it owns, and why it is that way).

## Before changing a module

1. Read that module's `architecture.md`. Its `CLAUDE.md` has already loaded.
2. Read the existing implementation, tests, and any linked ADRs or contracts.
3. Use only what those sources and the code show. If something is missing,
   write UNKNOWN or ask. Do not invent APIs, modules, or dependencies.

## While changing code

- Reuse existing services and follow existing boundaries.
- Do not bypass a module's public entrypoint.
- Do not add dependencies without justification.

**Never guess a shape.** If this repo has a schema, contract, or type for what
you are touching — an OpenAPI spec, a JSON Schema, a protobuf, a migration, a
type definition — open it and use it. Field names, payload shapes, enum values,
and endpoint paths are the things a model invents most confidently and most
wrongly, and every one of them is written down somewhere in here.

## After changing code

Update the module's docs in the same change when knowledge shifts. Which file:

- a rule or a gotcha — something Claude would get wrong without it → `CLAUDE.md`
- why the module is shaped this way, or what it owns → `architecture.md`

Never write the same fact in both.

Do not update it for renames, formatting, or internal refactors that change
nothing a caller can observe. Do not add a timestamp: git already records when
the file changed, and a hand-written date can be bumped without saying anything.

New architectural decision? Add an ADR under `docs/decisions/`. Do not rewrite
existing ADRs — supersede them.

## Merge conflicts in these files

- **Rules and Gotchas are append-only. Keep both sides**, never the shorter one
  — dropping a rule silently removes a constraint the code still depends on.
- Two rules that *contradict* each other are a disagreement, not a conflict:
  keep both, mark the module `Needs review`, let the authors settle it.

## Context budget

Load only the affected module's files. Do not read every module's docs for a
local change.
<!-- codedna:end -->
