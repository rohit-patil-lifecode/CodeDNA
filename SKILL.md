---
name: codedna
description: Keep Claude Code module context fresh with CodeDNA. Use when setting up per-module CLAUDE.md and architecture.md, scanning a repo for modules, auditing codebase architecture for gaps and coupling, syncing docs after code changes, recording an architecture decision as an ADR, checking documentation drift, reducing architecture hallucinations, or running codedna setup, analyze, map, flow, sync, adr, audit, check, review, session, verify, or doctor.
metadata:
  type: workflow
  version: "1.0"
  audience: claude-code
---

# CodeDNA

Maintain a living, module-scoped knowledge base for Claude Code. Code is the source of truth. The docs hold only what reading the code cannot tell you. Never invent architecture.

Read [references/commands.md](references/commands.md) for command details.
Read [references/module-detection.md](references/module-detection.md) before scanning a repo.
Copy templates from [assets/](assets/).

## Goal

For each real module, keep two short files next to the code:

- `CLAUDE.md` — rules and gotchas: anything Claude would get wrong without it. **Auto-loads** (see below), so it is present at the moment it is needed.
- `architecture.md` — what the module owns, and why it is shaped that way. Read on demand.

Neither file lists files, exports, or dependencies. Claude reads those from the code. A stale copy of a derivable fact is worse than no copy: it gets repeated with confidence.

## Match the unit of documentation to the unit of risk

A module is not always a directory. The knowledge worth writing down often lives
in a **seam** — between a backend layer and the frontend that calls it, an event
producer and its consumers, a schema and the code on both ends of it. That invariant belongs to no
single folder, so a nested `CLAUDE.md` cannot hold it.

Claude Code gives three loading surfaces. Pick by where the knowledge is true:

| Knowledge is true… | Put it in | Loads when |
|---|---|---|
| everywhere in the repo | root `CLAUDE.md` | every session |
| inside one directory | that directory's `CLAUDE.md` | Claude reads a file there |
| across several directories | `.claude/rules/<id>.md` with `paths:` globs | Claude reads a file matching any glob |

An architect maintains three things, and they need three artifacts:

| Dimension | Artifact | Answers |
|---|---|---|
| what each part owns | module `CLAUDE.md` + `architecture.md` | "what am I allowed to do here?" |
| what belongs together | subsystem rule (`paths` globs) | "what else does this touch?" |
| **how something travels** | **flow rule** ([assets/flow.md](assets/flow.md)) | **"where did this come from, what runs next?"** |

The third is what a fix needs and what a module doc structurally cannot hold — a module doc describes a box, never the path through it. Write two or three flows, not one per function.

So CodeDNA has two kinds of module:

- **directory module** — `path`, with `CLAUDE.md` + `architecture.md` beside the code
- **subsystem module** — `paths` globs, with one path-scoped rule from
  [assets/subsystem-rule.md](assets/subsystem-rule.md). Declare these in
  `.codedna/config.json`; no filesystem heuristic can infer a seam. **Not a
  setup question** — reach for it later, when you catch yourself writing the
  same rule into two module docs.

```json
{"modules": [
  "inc/abilities",
  {"id": "ability-bridge", "paths": ["inc/abilities/**", "assets/js/core/**"]}
]}
```

A file can belong to both, and both sets of rules apply. If you catch yourself
writing the same invariant into two module docs because it spans them, that is a
subsystem — say so instead of duplicating it.

## How module context actually reaches Claude

This matters more than any instruction in this file, because it is the part that works without anyone invoking anything.

1. **Root `CLAUDE.md` loads at session start**, always. `setup` merges the CodeDNA rules there.
2. **A module's `CLAUDE.md` loads the first time Claude reads a file in that directory** — Claude Code discovers nested `CLAUDE.md` files and includes them on demand. Nothing has to run for this to happen. This is why the module's rules live in `CLAUDE.md` and not only in `architecture.md`.
3. **`architecture.md` does not auto-load.** It is pulled in because the auto-loaded `CLAUDE.md` says to read it. Keep that pointer at the top of every module `CLAUDE.md`. It is also the only thing the optional hook injects — a subsystem rule and a module `CLAUDE.md` arrive on their own, so injecting them again would just spend context twice.
4. **This skill itself only loads when a request matches its description** — "set up CodeDNA", "check drift", `/codedna sync`. It does *not* load on an ordinary "fix the login bug" turn, so nothing here can be relied on to run on every edit. Anything that must always apply belongs in root or module `CLAUDE.md`, not in this file.
5. **For hard enforcement**, CLAUDE.md is context, not configuration — a `PreToolUse` hook on `Edit|Write` is the only thing that fires regardless of what the model decides. See [assets/hook-example.json](assets/hook-example.json). Optional; most repos do not need it.
6. **To see whether any of this happened**, install the `InstructionsLoaded` hook ([assets/hook-log-loads.sh](assets/hook-log-loads.sh)). Steps 1–3 are invisible from outside a transcript, so a doc that silently stopped loading reads exactly like a doc that did not help. `measure` reports the difference.

After `/compact`, nested `CLAUDE.md` files are not re-injected; they reload the next time Claude reads a file in that directory.

## Safety (non-negotiable)

1. **Code wins.** If docs and code disagree, report the conflict. Do not rewrite code to match stale docs.
2. **Do not invent.** If a claim is not visible in code, contracts, ADRs, or existing docs, do not write it. `UNKNOWN` is for one thing only: a specific question you have put to the user and they have not yet answered. It is not a way to fill a section. An empty section means "nothing to say yet", which is the normal state of a new module; `UNKNOWN` means "someone owes an answer", and every one of them is counted as an open question.
3. **Never guess a shape.** Field names, payload shapes, enum values, endpoint paths — read the schema, contract, migration, or type that defines them. These are what a model invents most confidently and most wrongly, and they are always written down somewhere in the repo.
4. **No derivable facts.** Do not add file lists, exports, or dependency lists to module docs, and do not "helpfully" restore them. They rot, and the code already answers them.
5. **Same change.** If a change alters a boundary, invariant, or the reasoning behind one, update `architecture.md` in the same session/PR. Do not touch the docs for an internal refactor that changes nothing a caller can observe.
6. **No timestamps in docs.** Git records when a file changed and cannot be forged by editing it. A hand-written date is derivable, gameable, and conflicts on every concurrent edit.
7. **Minimal context.** When editing module X, read root `CLAUDE.md` + that module's two files + relevant ADRs/contracts. Do not load every module.
8. **Escalate meaning changes.** For a new responsibility, a dropped invariant, or a boundary move, put the module in `Needs review:` in the output block and say so in the turn. Do not treat the doc edit as settled.

## Layout

```text
repo/
├── CLAUDE.md                 # root briefing + CodeDNA rules
├── .codedna/
│   ├── config.json
│   └── modules.json          # generated module map
├── docs/decisions/           # ADRs (why)
├── contracts/                # schemas if present
└── src/<module>/             # or apps/, packages/, services/
    ├── CLAUDE.md
    └── architecture.md
```

Do not create a second copy under `docs/architecture/<module>.md`, and do not generate an index file listing the modules — `.codedna/modules.json` already is that index, and a hand-kept second list drifts from it.

## Default config

If `.codedna/config.json` is missing, create it from [assets/config.json](assets/config.json).

Default mode is `auto`.

## Command router

Ten of these are registered as real commands (`/codedna:setup`, `/codedna:audit`, …) so they autocomplete. The rest — `analyze`, `map`, `module`, `review` — are reachable through this skill or in plain language. Treat all forms as the same commands.

| Command | Writes files? | Purpose |
|---|---|---|
| `setup` | yes | Detect modules, read each with its own subagent, scaffold |
| — | — | (a subsystem spanning directories is declared in config, not detected) |
| `analyze` | no | Coverage and health report |
| `map` | optional | Module map (text + mermaid) |
| `module <name>` | no | Deep-dive one module |
| `sync [--changed]` | yes | Re-check boundaries and gotchas against code; `--changed` limits to the current diff |
| `flow <name>` | yes | Trace how something travels the system, end to end |
| `adr <title>` | yes | Record a decision in `docs/decisions/` |
| `check` | no | Drift report (warns; `--enforce` to fail) |
| `audit` | no | Architecture review; finds unwritten traps and fills them |
| `review` | no | Impact of current diff |
| `session` | yes | End-of-session capture |
| `verify` | no | Claims that are no longer true (runs `verify_claims.py`) |
| `doctor` | no | Health dashboard |

Follow the matching section in [references/commands.md](references/commands.md).

## Read each module in its own context

`setup` spawns one subagent per module rather than reading them all in a single context. This is the same principle the docs themselves serve: a context holding one module reads it properly; a context holding sixteen skims all of them, and a Responsibility line written from a skim is worth nothing.

Each subagent returns a Responsibility line, candidate rules with `file:line` evidence, open questions for the human, and a verdict on whether docs will help in that module at all. It writes nothing. The main session collects the proposals, shows them grouped by module, and writes only what the user confirms.

See `setup` in [references/commands.md](references/commands.md) for the full brief.

## When docs must be updated

Update the module's **`CLAUDE.md`** if:

- a rule changed — something that was allowed no longer is, or a new constraint now holds
- a gotcha was discovered: ordering, timing, a shared mutable, a workaround for an upstream bug

Update the module's **`architecture.md`** if:

- what the module owns changed
- the reasoning behind its shape changed, or a decision was made that a future reader could not infer
- a new ADR is required (add a file under `docs/decisions/` from [assets/adr-template.md](assets/adr-template.md); do not rewrite old ADRs)

Do **not** update docs for: typo fixes, formatting, internal refactors that change nothing a caller can observe, a renamed private helper, a new file, a dependency bump, or a changed test command.

If you are unsure whether something qualifies, ask in the turn rather than writing a speculative line. One wrong invariant costs more than a missing one, because Claude repeats it to everyone who touches the module afterward.

## How to write the two files

### Which file does this line go in?

One question decides it:

> **Would Claude do something wrong without this line, on an ordinary edit?**

- **Yes** → module `CLAUDE.md`. It auto-loads, so it is present at the moment Claude would otherwise break the rule.
- **No, but it explains why things are as they are** → `architecture.md`. It is read on demand, which is enough for context but not for constraints.

Never write the same fact in both. A duplicated line is two places to update and two things to disagree with each other.

| Line | Goes in | Because |
|---|---|---|
| "never import the mailer; emit an event" | `CLAUDE.md` | Claude would otherwise import it |
| "the webhook can arrive before our commit" | `CLAUDE.md` | Claude would otherwise write a handler that errors |
| "amounts are integer minor units, never floats" | `CLAUDE.md` | Claude would otherwise use a float |
| "this module owns capture and refunds" | `architecture.md` | Orientation, not a constraint |
| "split from orders because refunds outlived the order row" | `architecture.md` | Explains the shape; changes no edit |
| "superseded ADR-0002 when we dropped the queue" | `architecture.md` | History |
| "pay.py, refund.py are the important files" | **neither** | Derivable — Claude reads the directory |
| "exports charge() and refund()" | **neither** | Derivable — Claude reads the code |
| "depends on stripe and the db" | **neither** | Derivable — Claude reads the imports |
| "last updated 2026-08-20" | **neither** | Derivable from git, and forgeable by hand |

### Module `CLAUDE.md`

Copy [assets/module-CLAUDE.md](assets/module-CLAUDE.md). **Under 40 lines** — it auto-loads into every session that touches the module, so its length is a recurring cost paid whether or not anyone needed it.

- Purpose — one line
- `Read architecture.md in this folder before changing this module.`
- **Rules** — imperatives. What must or must not happen here.
- **Gotchas** — traps that would produce a bug if unknown: ordering, timing, a shared mutable, a workaround for an upstream bug. **Hunt these in the code rather than waiting to be bitten** — defensive checks, retries, `HACK`/`FIXME`/"do not remove" comments and gratuitous awaits are all evidence that someone already was. Each states the consequence, with `file:line`.
- After-change checklist

### Module `architecture.md`

Copy [assets/architecture.md](assets/architecture.md). **Under 60 lines.**

YAML frontmatter (`module`, `owner`) and three sections:

- **Responsibility** — what it owns and the edge of what it owns
- **Why it is this way** — the reasoning no reader can recover from the code. This is the section with no other home: the code cannot hold it, and the person who knows it will leave.
- **Related ADRs**

Every section gets **attempted with evidence** before it is left out. A blank section should mean "we looked and found nothing", not "nobody looked" — and those read identically in the file, so say which one it was in the report. If a hunt finds nothing, drop the heading rather than shipping an empty one.

What must never happen is filling a section with something plausible, or with `UNKNOWN`, which claims a question is open when nobody asked one. An invented line is a trap that outlives whoever wrote it. Evidence is the test, not the section: a gotcha traced to a workaround in the source is as solid as a rule traced to an import.

The exception is **Responsibility**: fill it at scaffold time. One or two lines saying what the module owns and where that ownership stops is readable straight off the folder, it is the line that orients every later reader, and it changes rarely. `Responsibility: UNKNOWN` on a module whose code is right there is not caution, it is a gap.

An `architecture.md` holding only a Responsibility line is a normal outcome — most modules have no interesting rationale. Leave it; `measure` will show it as overhead once the module has seen real use, and deleting it then is an informed decision. Do not skip scaffolding a module because you cannot yet think of a rule for it.

### Root `CLAUDE.md`

If missing or lacking a CodeDNA section, merge [assets/root-CLAUDE.md](assets/root-CLAUDE.md) into the existing file. Do not wipe a good existing root file. Keep the root file under 200 lines. CodeDNA rules go in a short section; stack/commands stay as they are.

## Module detection

Use [scripts/detect_modules.py](scripts/detect_modules.py) when available:

```bash
python3 scripts/detect_modules.py --root . --write .codedna/modules.json
```

If the script cannot run, follow [references/module-detection.md](references/module-detection.md) and write `.codedna/modules.json` yourself.

Never treat `node_modules`, `dist`, `build`, `.git`, vendor, or generated folders as modules.

**Stop and ask before scaffolding** any module the detector marked `low` confidence, and always for `layer-smell` — a folder named `Services`, `Controllers`, `Models`, `Http` is a technical layer holding many unrelated concerns, not a bounded module. Writing one `architecture.md` over 60 unrelated services invents a cohesion that is not there. Ask which real boundaries exist, or scaffold nothing.

If more than 12 candidates come back, confirm the list, then scaffold in batches the user can actually review — not one 50-file change.

The detector only reads the filesystem. It cannot see a boundary that lives in someone's head, so for any repo whose structure is conventional-by-layer rather than bounded-by-domain, ask before you write.

## Drift check

Use [scripts/check_drift.py](scripts/check_drift.py) when available:

```bash
python3 scripts/check_drift.py --root . --base origin/main   # warns
python3 scripts/check_drift.py --root . --enforce            # fails the build
```

Otherwise inspect the git diff and apply the same rule: module code changed + knowledge-changing diff + docs unchanged, or docs changed by nothing but whitespace.

## Claims that went wrong

`check` only fires when code under a module changed, so a rule that became false because the world moved — an upstream fix, a superseded ADR, a boundary that relocated — is invisible to it. That is what `verify` is for:

```bash
python3 scripts/verify_claims.py --root .   # --enforce to fail on violated/superseded
```

Write rules with the thing they name in backticks — ``never import `mailer` `` is checkable against the code, "never import the mailer" is not. The script reports how many of each it found.

Each script has a self-check beside it (`scripts/test_*.py`); run them after editing any of them.

## CI

Optional workflow template: [assets/ci-workflow.yml](assets/ci-workflow.yml). It warns by default. Leave it warning until the module list is trusted — a gate that blocks a hotfix on day one gets bypassed, and a bypassed gate reports green forever.

CI should fail on missing module files and on knowledge-changing diffs that skip docs. It must not require a doc edit for every whitespace change.

## Output style

When reporting, use this shape:

```text
CodeDNA / <command>
Modules: N
Wrote: <paths or none>
Needs review: <paths>
UNKNOWN: <questions>
Drift: <pass|fail>
```

Do not dump entire generated files into chat unless the user asked to see them. Write the files, then summarize.
