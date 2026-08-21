#!/usr/bin/env python3
"""Find doc claims that are no longer TRUE, not merely untouched.

    python3 scripts/verify_claims.py --root . [--json] [--stale-after 10]

check_drift.py only fires when code under a module changed, so a rule that went
wrong because the world moved — an upstream fix, a superseded decision, a
boundary that relocated — is invisible to it. This looks at the claims
themselves.

Three checks, in descending order of certainty:

  violated    a rule says never touch X, and the module touches X.
  superseded  a doc cites an ADR that another ADR has superseded.
  unreviewed  a claim has not been edited across N commits of code change.
              A heuristic — unreviewed is not the same as wrong — so it is
              reported separately and never the only reason to fail.

Rules stated in prose ("never import the mailer") carry no token to check.
Those are counted and reported as unchecked rather than silently passed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path

CLAIM_SECTIONS = ("rules", "gotchas", "why it is this way", "boundaries", "invariants")
NEGATION = re.compile(r"\b(never|do not|don't|must not|no longer|avoid)\b", re.I)
ACTION = re.compile(r"\b(import|call|use|access|query|touch|depend|reach|read|write)\b", re.I)
TOKEN = re.compile(r"`([A-Za-z_][\w./-]{2,})`")
SUPERSEDED = re.compile(r"superseded\s+by\s+ADR[-\s]?(\d+)", re.I)
# ADRs are named NNNN-kebab-title.md, so the id is the leading number
ADR_FILE_ID = re.compile(r"^(\d+)")
ADR_ID = re.compile(r"ADR[-\s]?(\d+)", re.I)
# a numbered step naming a file, and optionally a symbol:  1. `a/b.js` -> `fn()`
FLOW_STEP = re.compile(r"^\s*\d+\.\s*`([^`]+)`(?:\s*(?:->|→)\s*`([^`]+)`)?")
SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".go", ".py", ".rs", ".java", ".kt",
              ".php", ".cs", ".rb"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "vendor", "__pycache__", ".venv"}


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def claims(text: str) -> list[tuple[int, str]]:
    """(line number, claim text) for every bullet under a claim section."""
    out, active = [], False
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            active = line.lstrip("#").strip().lower() in CLAIM_SECTIONS
            continue
        body = line.strip().lstrip("-* ").strip()
        if active and line.strip().startswith(("-", "*")) and body:
            out.append((lineno, body))
    return out


def module_sources(root: Path, mod: dict) -> list[Path]:
    """Source files this module owns — a directory, or globs for a subsystem
    whose code spans directories."""
    if mod.get("paths"):
        return [
            p
            for p in root.rglob("*")
            if p.is_file()
            and p.suffix in SOURCE_EXT
            and not any(part in SKIP_DIRS for part in p.relative_to(root).parts)
            and any(fnmatch(p.relative_to(root).as_posix(), pat) for pat in mod["paths"])
        ]
    base = root / mod["path"]
    if not base.is_dir():
        return []
    return [
        p
        for p in base.rglob("*")
        if p.is_file()
        and p.suffix in SOURCE_EXT
        and not any(part in SKIP_DIRS for part in p.relative_to(base).parts)
    ]


def superseded_adrs(root: Path) -> dict[str, str]:
    """{superseded id: the ADR that replaced it}"""
    out = {}
    decisions = root / "docs" / "decisions"
    for adr in sorted(decisions.glob("*.md")) if decisions.is_dir() else []:
        match = SUPERSEDED.search(read(adr))
        mine = ADR_FILE_ID.match(adr.name)
        if match and mine:
            # the file declares its OWN status, so this file is the dead one and
            # the id it names is the replacement
            out[mine.group(1).lstrip("0") or "0"] = match.group(1).lstrip("0") or "0"
    return out


def module_docs(mod: dict) -> list[str]:
    if mod.get("rule"):
        return [mod["rule"]]
    return [d for d in (mod.get("claude"), mod.get("architecture")) if d]


def check_violated(root: Path, mod: dict, text: str, where: str) -> tuple[list[dict], int, int]:
    """Rules saying 'never touch X' where the module touches X anyway."""
    findings, checkable, total = [], 0, 0
    sources = None
    for lineno, claim in claims(text):
        if not (NEGATION.search(claim) and ACTION.search(claim)):
            continue
        total += 1
        tokens = TOKEN.findall(claim)
        if not tokens:
            continue  # stated in prose; nothing to grep for
        checkable += 1
        if sources is None:
            sources = [(p, read(p)) for p in module_sources(root, mod)]
        for token in tokens:
            hits = [p for p, body in sources if token in body]
            if hits:
                findings.append({
                    "type": "violated",
                    "module": mod["id"],
                    "where": f"{where}:{lineno}",
                    "detail": f"rule says never {ACTION.search(claim).group(0)} `{token}`, "
                              f"but {hits[0].name} references it",
                })
                break
    return findings, checkable, total


def check_superseded(mod: dict, text: str, dead: dict[str, str], where: str) -> list[dict]:
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for adr in ADR_ID.findall(line):
            key = adr.lstrip("0") or "0"
            if key in dead:
                out.append({
                    "type": "superseded",
                    "module": mod["id"],
                    "where": f"{where}:{lineno}",
                    "detail": f"cites ADR-{adr}, superseded by ADR-{dead[key]}",
                })
    return out


def check_flow(root: Path, doc: str) -> list[dict]:
    """A flow step pointing at a file or symbol that no longer exists.

    This is how a flow rots: the code moves, the path in the doc does not, and
    Claude follows a route through the system that is no longer there.
    """
    out = []
    for lineno, line in enumerate(read(root / doc).splitlines(), 1):
        match = FLOW_STEP.match(line)
        if not match:
            continue
        target, symbol = match.group(1), match.group(2)
        path = root / target
        if not path.exists():
            out.append({
                "type": "broken-flow", "module": doc, "where": f"{doc}:{lineno}",
                "detail": f"step points at {target}, which does not exist",
            })
            continue
        if symbol:
            name = re.split(r"[(.\s]", symbol.strip())[0]
            if name and name not in read(path):
                out.append({
                    "type": "broken-flow", "module": doc, "where": f"{doc}:{lineno}",
                    "detail": f"step names `{symbol}` but {target} no longer contains it",
                })
    return out


def check_unreviewed(root: Path, mod: dict, doc: str, stale_after: int) -> list[dict]:
    """Claims not edited while the module's code moved on."""
    blame = git(root, "blame", "--line-porcelain", "--", doc)
    if not blame:
        return []
    line_commit: dict[int, str] = {}
    lineno = 0
    for line in blame.splitlines():
        match = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", line)
        if match:
            lineno = int(match.group(2))
            line_commit[lineno] = match.group(1)
    text = read(root / doc)
    out = []
    for claim_line, claim in claims(text):
        sha = line_commit.get(claim_line)
        if not sha:
            continue
        scope = mod.get("path") or "."
        since = git(root, "rev-list", "--count", f"{sha}..HEAD", "--", scope)
        if since.isdigit() and int(since) >= stale_after:
            out.append({
                "type": "unreviewed",
                "module": mod["id"],
                "where": f"{doc}:{claim_line}",
                "detail": f"{since} code commits since this claim was last edited: "
                          f"\"{claim[:60]}\"",
            })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify doc claims against code")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--stale-after", type=int, default=10,
                        help="code commits before a claim counts as unreviewed (0 = off)")
    parser.add_argument("--enforce", action="store_true",
                        help="exit 1 on violated/superseded findings (never on unreviewed)")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    manifest = root / ".codedna" / "modules.json"
    if not manifest.exists():
        print("No .codedna/modules.json. Run `/codedna setup` first.")
        return 0
    modules = json.loads(read(manifest)).get("modules") or []
    dead = superseded_adrs(root)

    findings, checkable, total = [], 0, 0

    # flows live as path-scoped rules and are checked wherever they are
    rules_dir = root / ".claude" / "rules"
    for rule in sorted(rules_dir.rglob("*.md")) if rules_dir.is_dir() else []:
        findings += check_flow(root, rule.relative_to(root).as_posix())

    for mod in modules:
        for doc in module_docs(mod):
            text = read(root / doc)
            if not text:
                continue
            found, c, n = check_violated(root, mod, text, doc)
            findings += found
            checkable += c
            total += n
            findings += check_superseded(mod, text, dead, doc)
            if args.stale_after:
                findings += check_unreviewed(root, mod, doc, args.stale_after)

    hard = [f for f in findings if f["type"] in ("violated", "superseded", "broken-flow")]
    if args.json:
        print(json.dumps({
            "findings": findings,
            "rulesChecked": checkable,
            "rulesStatedInProse": total - checkable,
        }, indent=2))
        return 1 if hard and args.enforce else 0

    print("CodeDNA / verify")
    print(f"Modules: {len(modules)}")
    print(f"Rules checked against code: {checkable} of {total} "
          f"({total - checkable} stated in prose, nothing to check)")
    if not findings:
        print("Claims: pass")
        return 0
    for kind in ("violated", "broken-flow", "superseded", "unreviewed"):
        group = [f for f in findings if f["type"] == kind]
        if group:
            print(f"\n{kind} ({len(group)}):")
            for f in group:
                print(f"  {f['where']} — {f['detail']}")
    if [f for f in findings if f["type"] == "unreviewed"]:
        print("\nunreviewed is a heuristic: it means nobody re-checked the claim "
              "while the code moved, not that the claim is wrong.")
    return 1 if hard and args.enforce else 0


if __name__ == "__main__":
    raise SystemExit(main())
