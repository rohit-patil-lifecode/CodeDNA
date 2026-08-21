# CodeDNA commands

Invoke as `/codedna <command>` or equivalent natural language.

## setup

1. Read the existing root `CLAUDE.md`, `README`, package manifests, `CODEOWNERS`.
2. Create `.codedna/` if missing. Write `config.json` from `assets/config.json` without overwriting user edits.
3. Detect modules (see `references/module-detection.md`). Write `.codedna/modules.json`.
4. **Show the list once and ask.** One confirmation, not a questionnaire. Print each module with its path and why it was detected, and let the user strike any line they do not want. Scaffold whatever survives.
5. **One subagent per module.** Do not read sixteen modules in one context and write thirty-two files from what survives. Give each confirmed module its own subagent, scoped to that module alone, and run them in parallel. See "Per-module subagent" below.
6. Collect what came back. Write the Responsibility lines directly. Put the **proposed rules in front of the user grouped by module, each with its evidence**, and write only what they confirm. A rule nobody confirmed is a rule nobody verified.
7. Merge CodeDNA rules into root `CLAUDE.md` between `<!-- codedna:start -->` and `<!-- codedna:end -->`. If the markers exist, replace what is between them — never append a second copy.
8. Summarize what was created and what was skipped, name any directory not scanned because it sits outside `moduleRoots`, and list the modules the subagents judged self-evident so the user can delete those docs if they agree.

### Per-module subagent

One subagent, one module, clean context. It reads only that module's code — entry points, imports, call sites, tests — which is the whole reason to spawn it: a context holding one module reads it properly, and a context holding sixteen skims all of them.

Each returns four things and writes nothing:

- **Responsibility** — one or two lines: what this module owns, where that stops. Derivable, so state it plainly.
- **Candidate rules** — constraints a caller could break, each with `file:line` evidence. A rule with no evidence is not a candidate, it is a guess. Prefer the checkable form, naming the symbol in backticks, so `verify` can test it later.
- **Candidate gotchas — hunt for these, do not wait for them.** The code carries evidence of every bug someone already hit. Go looking:
  - defensive code that should not be necessary — a null check on something that cannot be null, a `try/catch` around a call that does not throw, a re-read after a write
  - retries, timeouts, `setTimeout(…, 0)`, a `sleep`, an `await` that looks gratuitous — each one is a race someone lost
  - `HACK`, `FIXME`, `XXX`, `NOTE`, "do not remove", "must run before", "workaround for" — read every one and say what it is protecting against
  - explicit ordering: a call that must precede another, an init that must run first, a listener registered before something fires
  - shared or global state: a module-level mutable, a singleton, a registry two things write to
  - anything crossing a boundary the platform enforces — an iframe, a worker, a process, a request boundary
  Each gets `file:line` and states **the consequence**: what breaks if you do not know this. A rule says what to do; a gotcha says what happens when you do not, which is the part that stops a plausible-looking fix.
- **Open questions** — what the code implies but cannot confirm: an ordering that looks required, a key that looks like it must match. These go to the human, not into the doc.
- **A verdict**: *docs will help here*, or *this module is self-evident* — with a reason. A thin wrapper or a folder of presentational components is self-evident; a registry, an event bus, or anything with non-obvious wiring is not.

The verdict is the honest version of the triage: made after reading the module, backed by evidence, and shown to the user — never guessed from a directory listing before anyone has looked.

Subagents write no files, and every proposal carries evidence. The line is evidence, not category: a gotcha traced to a workaround in the source is exactly as solid as a rule traced to an import, and both are worth having. A gotcha with no evidence — "this might race", "could be a problem under load" — is speculation and must not be proposed at all.

**No section is silently left blank.** If a hunt genuinely turns up nothing, say so in the report — "no defensive code, no ordering dependencies, no workaround comments" is a finding, and it tells the user this module is simple rather than unexamined. Do not write `UNKNOWN` into the file; report the absence to the human and leave the section out.

**Scaffold what is detected. Do not decide for the user which modules are worth documenting.** A folder is a module because it is a bounded piece of the system, not because someone has already thought of a rule for it. Whether a doc earns its place is a question for `measure` after a few weeks of real use, not a guess at setup time.

A directory is a module whether it holds backend code, frontend code, or anything else. `backend/`, `frontend/`, `src/`, `apps/`, `packages/`, `services/` are all just places code lives.

Mark low-confidence and layer-smell candidates in the list so the user can strike them, then move on. Do not open a separate round of questions about them.

Do not rewrite existing module docs on setup unless they are empty stubs.

Do not write an index file listing the modules. `.codedna/modules.json` is that index.

**`setup` runs more than once, by more than one person.** If `.codedna/` already exists, say so and scaffold only what is missing — "3 new modules scaffolded, 9 already documented", never a diff that rewrites nine files nobody asked about.

## analyze

Read-only.

Report:

- module count
- CLAUDE.md coverage
- architecture.md coverage
- files with `UNKNOWN` still present
- docs older than the newest source file in the module (`git log -1 --format=%cs -- <path>` for both)
- missing ADR references (link points at a file that does not exist)
- folders that look like modules but are not in `modules.json`

No file writes.

## map

Build a module graph from `modules.json` plus import/path evidence.

Output:

- table of module → depends on
- mermaid `flowchart LR` of those edges
- optionally write `docs/architecture/map.md` if the user asked to save it

Do not invent edges. Unproven dependents stay off the graph or marked `UNKNOWN`.

## module <name>

Read-only deep dive.

Resolve the name from `modules.json`. Then report purpose, path, owner, key files, verified dependencies, dependents, related ADRs, tests, and whether CLAUDE.md / architecture.md need edits.

If the name is unknown, list close matches. Do not create files.

## sync [--changed] [modules...]

Re-check what the docs claim against the code. `--changed` limits it to modules touched by the current diff; a module list limits it to those. (This replaces the old separate `update` command — same operation, different scope.)

Across more than two or three modules, use the same per-module subagent as `setup` — one module per context, each returning findings and proposed edits, nothing written until collected. Re-checking whether a rule still holds needs the module read properly, which is the thing a shared context cannot do.

For each module:

1. Read the code, then read the docs. Ask of every Rule and Gotcha in `CLAUDE.md`: *is this still true?*
2. Report anything the code now contradicts. Do not silently rewrite it — a contradicted invariant is a finding, not a typo.
3. Add a rule or gotcha only when the user states it or the code plainly proves it. A pattern you noticed once is not an invariant.
4. Do not rewrite prose that is still accurate.
5. Never add a timestamp. Git records when the file changed; a written date is derivable, forgeable, and conflicts on every concurrent edit.

If a responsibility clearly changed, add a `Needs review` note instead of silently editing the Responsibility section.

Do not re-add file lists, exports, or dependency lists. If a previous version of the doc had them, deleting them is a valid sync result.

## adr <title>

Record a decision whose reasoning the code cannot carry.

1. Find the next id in `docs/decisions/` (`NNNN-kebab-title.md`).
2. Copy `assets/adr-template.md`. Fill Context, Decision, Alternatives, Consequences.
3. Ask the user for the parts you cannot know: what forced this, what else was considered, what was given up. Do not invent alternatives to look thorough.
4. Link it from the affected module's `architecture.md` under Related ADRs.
5. Superseding an old ADR? Add a new one and mark the old one `superseded by`. Never edit the original's decision.

## check

Read-only drift gate. Intended for CI and PR.

Findings:

- module in `modules.json` missing `CLAUDE.md` or `architecture.md`
- module in `modules.json` whose folder no longer exists — prune it
- knowledge-changing paths under a module changed, and neither module doc changed
- the module's docs were touched but say nothing new (whitespace only)
- architecture.md references an ADR file that does not exist
- frontmatter missing `module`

Knowledge-changing paths: source files, contracts, module entrypoints. Not: lockfiles, dependency manifests, formatting-only, generated code (`*.pb.go`, `*_pb2.py`, `*.generated.*`), tests (`*_test.*`, `*.spec.*`, anything under `tests/`), snapshots, docs. Only the module's own `CLAUDE.md`/`architecture.md` count as its docs — a nested one elsewhere in the tree does not.

**Warns by default and exits 0.** `--enforce` exits 1 instead. Stay on warn until the module list is trusted; a gate that blocks a hotfix on day one gets bypassed, and a bypassed gate reports green forever. `mode: manual` in config never enforces.

Escape hatch: a line starting with `codedna: skip-docs <reason>` in the commit message, or the `CODEDNA_SKIP_DOCS` env var — use the env var in PR CI, where the checked-out HEAD is a synthetic merge commit whose message nobody wrote. The marker must start its own line and state a reason, so a PR template mentioning it does not silently disable the gate; the reason is echoed into the check output.

`--json` emits the findings as a JSON object (`status`, `modules`, `changedFiles`, `findings`) for a CI step to consume.

If `scripts/check_drift.py` exists, prefer running it.

## flow <name>

Trace how one thing actually travels through the system, and write it down where Claude will see it.

A module doc says what a box owns. It never says the path. When Claude is *fixing* something it needs the path — where this came from, what runs next, what is downstream of the line being changed — and tracing it across modules every time is both expensive and where it starts guessing.

1. Ask what the flow is, if not given. Good candidates are the ones a newcomer asks about: how a request is served, how a job runs, how an event reaches its handlers.
2. **Trace it in the code.** Follow it from trigger to end. Do not reconstruct it from the module docs — they describe boxes, and a flow reconstructed from boxes is a guess.
3. Write it from [assets/flow.md](assets/flow.md) into `.claude/rules/<name>.md`, with `paths:` covering **every** directory the flow touches. That is what makes editing any step load the whole path.
4. Every step names a real file, and a symbol where there is one. A step with no file is prose, not a flow, and `verify` cannot check it.
5. Record the invariants that hold **across** steps — a key that must match between two of them, an ordering, a step that may run twice. Rules true inside one step belong in that module's `CLAUDE.md`.
6. Leave "When it breaks" empty until someone has actually debugged it.

Two or three flows usually cover a system. Do not write one per function — a flow nobody would have had to trace is cost with no payload.

`verify` checks every step still resolves. A step naming a file or symbol that has gone is a flow that has silently drifted, which is worse than no flow: Claude follows a route through the system that no longer exists.

## audit

Read-only. An architecture review of the codebase itself, not of the docs. Everything else here audits whether the docs are honest; this asks whether the **system** is.

Run it when adopting, after a big change, or quarterly. It is slow and thorough — not a per-PR check.

**Evidence first.** Start with what can be computed, before forming any opinion:

```bash
python3 scripts/coupling.py --root . --since 200
python3 scripts/gaps.py --root .
python3 scripts/verify_claims.py --root .
python3 scripts/measure.py --root .
```

`coupling.py` is the one that finds things a code read misses: modules that keep changing in the same commit are one unit whatever the folders say. That is evidence, not inference.

**Then read for context, in this order:**

1. `README`, root `CLAUDE.md`, and any product docs — *what is this system for?* An architecture is only good or bad relative to what it has to do. A design that is over-built for a prototype is correct for a payments system.
2. `.codedna/modules.json` and every module's `CLAUDE.md` — the boundaries the team believes it has.
3. The code at the boundaries the evidence flagged. Not everywhere — the hubs and seams `coupling.py` named.

**Report each finding in this shape**, and nothing that does not fit it:

```text
<finding>
  evidence:   <file:line, a coupling number, a violated rule — something checkable>
  matters because: <the consequence, tied to what this project is for>
  option:     <the smallest change that would address it>
```

Look for:

- **undeclared seams** — modules that change as one. Either they are one module, or the contract between them needs writing down.
- **hubs** — where the design concentrates. Not automatically wrong; undocumented concentration is.
- **violated boundaries** — a rule the code breaks (`verify_claims.py` finds the checkable ones).
- **knowledge concentration** — a high-churn, high-coupling module with no rules and no rationale. This is where the bus factor is, and it is CodeDNA's own signal.
- **unwritten traps** — `gaps.py` lists modules whose code is full of workarounds, retries and ordering warnings while their Gotchas section is empty. That module is not simple, it is unread, and the next person pays the same afternoon again. **Fill these in as part of the audit**: read each line it points at, say what it is protecting against, and propose it as a gotcha with its `file:line`. This is the highest-value output of an audit, because it converts evidence already sitting in the repo into the content that stops a plausible-looking fix.
- **boundaries that exist only in the docs** — declared in `CLAUDE.md`, contradicted by how the code actually changes.

**Rules for this command:**

- No finding without evidence. An architecture opinion with nothing checkable behind it is exactly the confident wrongness this tool exists to prevent, and it is more damaging here than anywhere else because it sounds authoritative.
- Say what the project is optimising for before judging it. A monolith is not a finding. Coupling is not a finding. *Coupling that contradicts a boundary this team says it has* is a finding.
- Rank by consequence, not by how easy it is to say.
- Separate **evidenced** from **judgement** explicitly, and mark which is which.
- Propose the smallest change, not the ideal architecture. Nobody is rewriting the system because of this report.
- Write nothing directly. `audit` proposes; the human confirms. The unwritten-trap findings are the exception worth pushing on — they are evidence already in the repo, so bring them back as ready-to-paste gotchas rather than as a list of file paths for someone else to interpret.

## measure

Read-only. Cost versus payload, per module: what the docs add to a session against how much they carry that the code cannot tell you.

Run `python3 scripts/measure.py --root .`, or `--json` to store a snapshot and track the trend over time.

**Check "Reaching Claude" before anything else.** A doc that never loaded and a doc that did not help look identical from the outside, and only one of them is a documentation problem. If a module shows payload but no loads, the fault is the path, the globs, or `claudeMdExcludes` — not the writing. This needs the `InstructionsLoaded` hook (`assets/hook-log-loads.sh`); without it the report says `unknown`, which is the honest answer rather than zero. Report the zero-payload docs — those cost context and return nothing, and deleting them is the right answer. Also report the trust signals (content-free doc edits, skip-docs commits): docs being *satisfied* rather than written means the gate is being gamed, and enforcing it harder will not fix that.

## review

Read-only impact analysis of the current diff (staged + unstaged, or PR range if given).

For each affected module state:

- what knowledge changed
- whether architecture.md / CLAUDE.md must be updated
- whether a new ADR is warranted (boundary, store, provider, or communication style changed)
- whether a contract file should change
- suggested doc bullets (do not apply unless user asked)

## session

End-of-session capture.

1. Diff against the start of the session if known, else `git status` + `git diff`.
2. Group changes by module.
3. Apply the same conservative updates as `sync --changed`.
4. Ask the user the questions the code left open — a boundary you inferred but could not confirm, a gotcha you hit while working. This is the moment the knowledge exists and is cheap to capture; by tomorrow it is gone.
5. List remaining `UNKNOWN` questions.
6. Remind the user to run tests.

Do this when the user says they are done, asks to commit, or asks to wrap up.

## verify

Read-only consistency.

Check:

- CLAUDE.md rules that contradict architecture.md
- rules that the code clearly violates (e.g. "never import the mailer" but a mailer import exists)
- ADR ids mentioned but missing
- derivable content that crept back in — file lists, export lists, dependency lists, timestamps. Report it for deletion.
- the same fact stated in both files. Report which copy to drop.
- contracts mentioned but missing

Trust code when they conflict. Report contradictions; do not auto-fix on verify.

Run `python3 scripts/verify_claims.py --root .` first — it mechanically catches the three shapes of "no longer true" that `check` cannot see, because `check` only fires when code changed:

- **violated** — a rule says never touch `X` and the module references `X`
- **broken-flow** — a flow step names a file or symbol that no longer exists
- **superseded** — a doc cites an ADR that another ADR has superseded
- **unreviewed** — a claim nobody edited while the module's code moved on (a heuristic; unreviewed is not wrong, and it never fails a build on its own)

The script reports how many rules it could check against code versus how many are stated in prose with no token to grep for. Rules written as ``never import `mailer` `` are checkable; "never import the mailer" is not. Prefer the checkable form when a rule names something real.

Then read what the script cannot: rules that contradict the module's own architecture.md, invariants the code violates in ways no grep can see, and derivable content that crept back in.

## doctor

Read-only dashboard.

```text
CodeDNA Health
Modules: …
CLAUDE.md coverage: …
architecture.md coverage: …
Stale docs: …
UNKNOWN fields: …
Broken ADR links: …
Drift: pass|fail
Mode: auto|manual
```

Include the 5 worst stale modules (name + last doc commit + newest code change, both from git).
