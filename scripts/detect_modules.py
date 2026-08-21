#!/usr/bin/env python3
"""Detect CodeDNA modules and optionally write .codedna/modules.json."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path

DEFAULT_ROOTS = [
    "src",
    "app",
    "apps",
    "packages",
    "services",
    "modules",
    "internal",
    "libs",
    "backend",
    "frontend",
]

# never a module, never walked into
BUILD_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "out",
    "coverage",
    "vendor",
    ".next",
    ".nuxt",
    "target",
    "__pycache__",
    "generated",
    "gen",
    ".venv",
    "bin",
    "obj",
    ".codedna",
}

# support folders: not a module *unless* they carry their own manifest.
# a workspace package legitimately named docs/ or tests/ is a real module.
SUPPORT_DIRS = {"docs", "contracts", "tests", "test", "__tests__"}

# technical layers of an MVC-convention repo (Laravel, Rails, Django). These are
# not bounded modules — one "Services" folder holds 60 unrelated concerns — so
# they are forced to low confidence and setup must ask before scaffolding them.
LAYER_DIRS = {
    "http",
    "controllers",
    "services",
    "models",
    "views",
    "middleware",
    "providers",
    "console",
    "exceptions",
    "repositories",
    "entities",
    "serializers",
    "helpers",
    "utils",
}

IGNORE = BUILD_DIRS | SUPPORT_DIRS

MANIFESTS = {
    "package.json": "ts",
    "go.mod": "go",
    "pyproject.toml": "py",
    "setup.py": "py",
    "Cargo.toml": "rust",
    "composer.json": "php",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "java",
}

ENTRYPOINTS = {
    "index.ts",
    "index.tsx",
    "index.js",
    "main.go",
    "main.ts",
    "main.py",
    "lib.rs",
    "__init__.py",
}

SOURCE_EXT = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".py",
    ".rs",
    ".java",
    ".kt",
    ".php",
    ".cs",
    ".rb",
}


def load_config(root: Path) -> dict:
    path = root / ".codedna" / "config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def has_manifest(folder: Path) -> bool:
    return any((folder / name).exists() for name in MANIFESTS)


def should_ignore(
    name: str, extra: list[str], folder: Path | None = None, rel: str | None = None
) -> bool:
    if name.startswith(".") and name != ".codedna":
        return True
    if name in BUILD_DIRS or name in extra:
        return True
    # an ignore entry with a slash or a star is a path pattern, not a folder name
    if rel and any(fnmatch(rel, pat) for pat in extra if "/" in pat or "*" in pat):
        return True
    if name in SUPPORT_DIRS:
        return not (folder is not None and has_manifest(folder))
    return False


EXT_LANG = {
    ".ts": "ts",
    ".jsx": "ts",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".tsx": "ts",
    ".js": "ts",
    ".go": "go",
    ".py": "py",
    ".rs": "rust",
    ".java": "java",
    ".php": "php",
    ".cs": "csharp",
}


def language_for(folder: Path) -> str:
    for manifest, lang in MANIFESTS.items():
        if (folder / manifest).exists():
            return lang
    counts = Counter(
        EXT_LANG[p.suffix] for p in source_files(folder) if p.suffix in EXT_LANG
    )
    return counts.most_common(1)[0][0] if counts else "unknown"


@lru_cache(maxsize=None)
def source_files(folder: Path) -> tuple[Path, ...]:
    # filter on the path *below* folder: a package named tests/ still has sources,
    # but a tests/ subfolder inside a package is not that package's source.
    return tuple(
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.suffix in SOURCE_EXT
        and not any(part in IGNORE for part in path.relative_to(folder).parts)
    )


def package_id(folder: Path) -> str:
    pkg = folder / "package.json"
    if pkg.exists():
        try:
            name = json.loads(pkg.read_text(encoding="utf-8")).get("name") or folder.name
            return str(name).split("/")[-1]
        except json.JSONDecodeError:
            pass
    return folder.name


@lru_cache(maxsize=None)
def score_folder(folder: Path) -> tuple[str, str]:
    """Return (confidence, reason)."""
    has_entry = any((folder / name).exists() for name in ENTRYPOINTS) or (folder / "cmd").is_dir()
    files = source_files(folder)
    has_docs = (folder / "CLAUDE.md").exists() or (folder / "architecture.md").exists()
    if has_manifest(folder):
        return "high", "manifest"
    if folder.name.lower() in LAYER_DIRS:
        # a technical layer, whatever its file count. Never scaffold silently.
        return "low", "layer-smell"
    if has_entry and len(files) >= 2:
        return "high", "entrypoint"
    if has_docs:
        return "high", "existing-docs"
    if len(files) >= 4:
        return "medium", "source-cluster"
    if len(files) >= 1:
        return "low", "thin-folder"
    return "skip", "no-source"


def iter_candidates(root: Path, module_roots: list[str], extra_ignore: list[str]) -> list[Path]:
    """Folders that might be modules. `root` anchors relative paths for glob ignores."""
    candidates: list[Path] = []
    found_root = False
    for name in module_roots:
        base = root / name
        if not base.is_dir():
            continue
        found_root = True
        for child in sorted(base.iterdir()):
            if not child.is_dir() or should_ignore(
                child.name, extra_ignore, child, child.relative_to(root).as_posix()
            ):
                continue
            # workspace packages nest one extra level (packages/@scope/name). Descend
            # when the child is not itself a package but holds ones — otherwise a
            # scope folder is reported as a module and the real packages are lost.
            conf, _ = score_folder(child)
            nested = [
                g
                for g in child.iterdir()
                if g.is_dir()
                and not should_ignore(
                    g.name, extra_ignore, g, g.relative_to(root).as_posix()
                )
            ]
            inner = [g for g in nested if has_manifest(g)]
            if inner:
                # workspace packages nested one level down. Keep the parent too
                # when it is a package in its own right, rather than dropping
                # either side silently.
                if has_manifest(child):
                    candidates.append(child)
                candidates.extend(g for g in inner if score_folder(g)[0] != "skip")
                continue
            if conf == "skip":
                if nested and any(score_folder(g)[0] != "skip" for g in nested):
                    candidates.extend(nested)
                continue
            candidates.append(child)
    if not found_root:
        # No module root matched, so the whole repo is the only candidate. That
        # is a guess, not a finding — one doc over an entire polyglot repo is
        # the cohesion-invention this tool exists to prevent. Always ask.
        if score_folder(root)[0] != "skip":
            candidates.append(root)
    return candidates


def subsystem_module(entry: dict) -> dict:
    """A module whose code spans directories.

    Its knowledge cannot live in a nested CLAUDE.md — no single directory
    contains the subsystem — so it goes in a path-scoped rule, which Claude Code
    loads whenever it reads a file matching any of the globs. This is the shape
    for a contract between a PHP layer and its JS counterpart, an event producer
    and its consumers, or anything else whose invariants span folders.
    """
    mid = entry["id"]
    return {
        "id": mid,
        "paths": list(entry["paths"]),
        "rule": entry.get("rule", f".claude/rules/{mid}.md"),
        "kind": "subsystem",
        "confidence": "high",
        "reason": "pinned",
    }


def detect(root: Path) -> dict:
    cfg = load_config(root)
    # Extend, never replace: a config naming one root used to silently drop the
    # other nine, and the config setup itself writes was the first victim.
    # Roots that do not exist are skipped anyway, so a union costs nothing.
    # Narrowing is what `ignore` is for.
    module_roots = DEFAULT_ROOTS + [
        r for r in (cfg.get("moduleRoots") or []) if r not in DEFAULT_ROOTS
    ]
    extra_ignore = cfg.get("ignore") or []

    # A pinned list wins outright: some repos have real boundaries no filesystem
    # heuristic can find, and this is the only way to say so. An entry is either
    # a path string (a directory module) or an object with `paths` globs (a
    # subsystem that spans directories — see subsystem_module).
    pinned = cfg.get("modules") or []
    spanning = [m for m in pinned if isinstance(m, dict)]
    pinned_dirs = [m for m in pinned if isinstance(m, str)]
    folders = (
        [root / rel for rel in pinned_dirs if (root / rel).is_dir()]
        if pinned
        else iter_candidates(root, module_roots, extra_ignore)
    )

    modules = [subsystem_module(m) for m in spanning]
    seen = set()
    for folder in folders:
        conf, reason = score_folder(folder)
        if pinned_dirs:
            conf, reason = "high", "pinned"
        elif conf == "skip":
            continue
        rel = folder.relative_to(root).as_posix()
        if rel == "." and not pinned:
            conf, reason = "low", "whole-repo-fallback"
        if rel in seen:
            continue
        seen.add(rel)
        mid = package_id(folder)
        modules.append(
            {
                "id": mid,
                "path": rel,
                "claude": f"{rel}/CLAUDE.md" if rel != "." else "CLAUDE.md",
                "architecture": f"{rel}/architecture.md" if rel != "." else "architecture.md",
                "language": language_for(folder),
                "confidence": conf,
                "reason": reason,
            }
        )

    # services/auth and packages/auth both yield "auth". Fall back to the path
    # for any duplicate — paths are unique by construction, so this always
    # resolves, and "services-auth" still reads like a name.
    counts: dict[str, int] = {}
    for mod in modules:
        counts[mod["id"]] = counts.get(mod["id"], 0) + 1
    for mod in modules:
        if counts[mod["id"]] > 1 and mod.get("path") not in (".", None):
            mod["id"] = mod["path"].replace("/", "-")

    # Sorted, and with no timestamp: two developers regenerating this on
    # different days must produce byte-identical output, or every branch
    # carries a merge conflict in a field nobody reads.
    return {"modules": sorted(modules, key=lambda m: m.get("path") or m["id"])}


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect CodeDNA modules")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--write", help="Write JSON to this path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result = detect(root)
    text = json.dumps(result, indent=2)

    if args.write:
        out = Path(args.write)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {out} ({len(result['modules'])} modules)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
