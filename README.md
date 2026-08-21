# CodeDNA

A Claude Code skill that writes down the things Claude **can't** read off your code — the rules, the traps, and the reasoning — and keeps them next to the code.

## Why

Claude reads your code fine. It can't read what was never written down:

- *"never import the mailer here — emit an event instead"*
- *"the Stripe webhook can arrive before our own commit lands"*
- *"payments was split from orders because refunds outlived the order row"*

So it guesses, confidently. CodeDNA puts those where Claude will actually see them.

It **won't** document file lists, exports, or dependencies. Claude reads those from the code, and a stale copy is worse than none.

## Install

In Claude Code:

```text
/plugin marketplace add rohit-patil-lifecode/CodeDNA
/plugin install codedna@codedna
```

Or paste this and let Claude do it:

```text
Install the Claude Code plugin at https://github.com/rohit-patil-lifecode/CodeDNA
```

Prefer it committed to the repo instead of installed?

```bash
git clone --depth 1 https://github.com/rohit-patil-lifecode/CodeDNA.git .claude/skills/codedna
rm -rf .claude/skills/codedna/.git
```

Then run:

```text
/codedna:setup
```

It shows you the modules it found before writing anything. **Start with one module you know well** — a 50-file first PR just gets rubber-stamped.

## Where a line goes

Knowledge is worth writing down where it's *true*, which is not always one folder. Three surfaces:

| True… | Goes in | Loads when |
|---|---|---|
| everywhere | root `CLAUDE.md` | every session |
| in one directory | that folder's `CLAUDE.md` | Claude reads a file there |
| across directories | `.claude/rules/<id>.md` with `paths:` globs | Claude reads any matching file |

That third row matters more than it looks. The invariant that bites hardest usually lives in a **seam** — a PHP layer and its JS counterpart, an event producer and its consumers. It belongs to neither folder, so declare it as a subsystem:

```json
{"modules": [
  "inc/abilities",
  {"id": "ability-bridge", "paths": ["inc/abilities/**", "assets/js/core/**"]}
]}
```

If you're about to write the same rule into two module docs, that's a seam — say so once instead.

## Inside one module

A directory module gets two files. Which one a line goes in:

> **Would Claude do something wrong without this line?**

**Yes → `CLAUDE.md`.** This file loads by itself whenever Claude touches the folder, so the line is there when it matters.

```markdown
# Module: payments

## Rules
- never import the mailer; emit `PaymentSettled` instead
- amounts are integer minor units, never floats

## Gotchas
- the Stripe webhook can arrive before our transaction commits
```

**No, it just explains why → `architecture.md`.** Read only when asked for.

```markdown
## Responsibility
- owns capture and refund; not invoicing

## Why it is this way
- split from orders in ADR-0003 because refunds outlived the order row
```

**Neither** — anything Claude can read from the code: file lists, exports, dependencies, timestamps.

Never put the same fact in both. Leave a section empty rather than inventing something; an empty section is honest.

## Commands

Type `/codedna` and they autocomplete.

### Setting up

**`/codedna:setup`** — detects your modules, shows the list, asks once, then gives each module its own subagent to read it properly and propose rules with `file:line` evidence. Writes only what you confirm.
*Use it when:* adopting CodeDNA, or after adding a module.

**`/codedna:flow`** — traces how one thing travels end to end (request → handler → store → response) and writes it as a path-scoped rule, so editing *any* step loads the whole path.
*Use it when:* people keep asking "where does X actually go?", or a bug took an hour to trace. Two or three flows cover a system.

**`/codedna:adr`** — records a decision and the reasoning behind it.
*Use it when:* you chose something non-obvious and the next person will wonder why. Not for routine choices.

### While working

**`/codedna:session`** — end-of-session capture. Asks what the code left unexplained while it's still in your head.
*Use it when:* wrapping up, especially after debugging something surprising. **This is where gotchas come from** — the highest-value habit in the whole tool.

**`/codedna:sync`** — re-reads the code and checks whether each documented rule still holds.
*Use it when:* you've refactored, or you suspect the docs have drifted.

**`/codedna:check`** — the drift gate: code changed under a module, docs didn't. Warns by default.
*Use it when:* before opening a PR. Also what runs in CI.

### Checking on it

**`/codedna:verify`** — finds claims that are no longer **true**: a rule the code now breaks, a doc citing a superseded ADR, a flow step pointing at a file that's gone.
*Use it when:* monthly, or after a big refactor. `check` catches *untouched* docs; only this catches *untrue* ones.

**`/codedna:measure`** — token cost against payload, per module, plus whether the docs are reaching Claude at all.
*Use it when:* deciding whether this is earning its keep, or before turning CI to `--enforce`. Start with the "Reaching Claude" section.

**`/codedna:doctor`** — health dashboard: coverage, staleness, open questions.
*Use it when:* you want the one-screen status.

### Reviewing the architecture

**`/codedna:audit`** — reviews the **system**, not the docs. Finds modules that always change together (an undeclared seam), hubs where the design concentrates, boundaries the code violates, and **traps the code shows but the docs never mention** — every workaround, retry and "do not remove" that nobody wrote up.
*Use it when:* adopting, after a big change, or quarterly. Slow and thorough; not a per-PR check.

---

Four more — `analyze`, `map`, `module <name>`, `review` — overlap the above and aren't registered as their own commands. Ask for them in plain language. Full detail for everything in [references/commands.md](references/commands.md).

## Is it worth it?

```bash
python3 scripts/measure.py --root .   # --json to track the trend
```

```text
module        auto-load  on-demand  payload  verdict
shared                4         38        0  OVERHEAD — delete
payments             21         90        5  22 tok/item
```

**Payload** is how many things a doc carries that the code can't say. Zero payload with real token cost means delete the file. It also counts docs being *touched* rather than written, which is the tell that a CI gate is being gamed.

## CI

```bash
curl -sSfL -o .github/workflows/codedna.yml \
  https://raw.githubusercontent.com/rohit-patil-lifecode/CodeDNA/v1.0.0/assets/ci-workflow.yml
```

- Runs on PRs and **warns instead of failing**. Add `--enforce` once you trust the module list.
- A gate that blocks a hotfix on day one gets bypassed — and a bypassed gate is green forever.
- Skip one with a line reading `codedna: skip-docs <reason>` in the commit message — it must start the line and give a reason, so merely mentioning it doesn't turn the gate off.

## On a team

- Regenerating `modules.json` gives identical output, so it never conflicts
- Docs carry no timestamps — git already knows, and a date can be bumped without saying anything
- Re-running `setup` scaffolds only what's missing
- Two people both add a rule and it conflicts? **Keep both sides, never the shorter one**

## Worth knowing

- **Rules are prose, not enforced.** "Don't import the mailer" is a sentence, not a lint rule. Add `eslint no-restricted-imports`, ArchUnit, or deptrac if you want teeth — that's the biggest upgrade available.
- **The drift check is path-based.** It knows a module changed, not whether its public API did.
- **Layer folders need you.** `app/Services` and friends get flagged, not scaffolded — CodeDNA can't guess your real boundaries.
- **It doesn't prove fewer hallucinations.** `measure` shows cost exactly and content honestly; proving the rest needs an A/B eval.

Python 3, standard library only. Self-checks: `scripts/test_*.py`.
