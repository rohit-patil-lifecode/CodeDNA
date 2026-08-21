# Module detection

A module is a bounded folder that owns a coherent responsibility and has a public surface. It is not every directory.

## Detection order

1. Use `.codedna/modules.json` if it already exists and looks valid.
2. Use `.codedna/config.json` `modules` if the user pinned a list — an array of paths, which wins outright over detection. This is the answer for a repo whose real boundaries no filesystem heuristic can find; pinned entries are always scaffolded, no confidence gate.
3. Run `scripts/detect_modules.py`.
4. Heuristic scan below.
5. Ask the user if confidence is low.

## Candidate roots

Scan these if they exist:

- `src/`
- `app/`
- `apps/`
- `packages/`
- `services/`
- `modules/`
- `internal/`
- `libs/`
- `backend/`, `frontend/`

Also treat a repo as a single module when there is no nested package structure and code lives at the root.

## A folder is a module if at least one is true

- it contains `package.json` with a `name` (workspace package)
- it contains `go.mod`, `pyproject.toml`, `Cargo.toml`, `composer.json`, or `*.csproj`
- it contains a clear entrypoint (`index.ts`, `main.go`, `lib.rs`, `__init__.py`, `cmd/`)
- it is a first-level child of a candidate root and has multiple source files plus tests
- `CODEOWNERS` assigns that path to a team
- it already has `CLAUDE.md` or `architecture.md`

## Never treat as modules

`node_modules`, `.git`, `dist`, `build`, `out`, `coverage`, `vendor`, `.next`, `.nuxt`, `target`, `__pycache__`, `generated`, `gen`, `.venv`, `bin`, `obj`, fixtures, snapshots, stories-only folders.

Exception: a folder named `docs`, `tests`, or `contracts` **is** a module when it carries its own manifest — `apps/docs` ships in the default Turborepo starter and is a real app. Judge by the manifest, not the name.

## Technical layers are not modules

A folder named `Http`, `Controllers`, `Services`, `Models`, `Views`, `Middleware`, `Providers`, `Repositories`, `Entities`, `Serializers`, `Helpers`, or `Utils` is a technical layer of a conventional MVC-style tree, not a bounded module. One `app/Services/` holds sixty unrelated concerns; a single `architecture.md` over it invents a cohesion that does not exist, and the drift gate then fires on every PR that touches any of the sixty.

The detector marks these `low` / `layer-smell`. Never scaffold one silently — ask which boundaries the team actually recognises. In a layer-organised codebase the real modules usually are not directories at all, and the honest answer may be "document three of these by hand, skip the rest."

## Naming

- directory name, lowercased
- if `package.json` name is `@org/payments`, module id is `payments`
- keep ids stable; do not rename on later scans unless the folder moved
- when two modules would share an id (`services/auth` and `packages/auth`), both fall back to their path (`services-auth`), so an id always names exactly one module

## modules.json shape

```json
{
  "generated_at": "2026-08-20",
  "modules": [
    {
      "id": "payments",
      "path": "src/payments",
      "claude": "src/payments/CLAUDE.md",
      "architecture": "src/payments/architecture.md",
      "language": "ts",
      "confidence": "high"
    }
  ]
}
```

`confidence` is `high` | `medium` | `low`, and `reason` says how it was judged (`manifest`, `entrypoint`, `existing-docs`, `source-cluster`, `thin-folder`, `layer-smell`, `pinned`, `whole-repo-fallback`). Setup must ask before scaffolding anything `low`, and always for `layer-smell`.

## Language hints

Infer from files:

- `*.ts`/`*.tsx`/`package.json` → ts
- `*.go`/`go.mod` → go
- `*.py`/`pyproject.toml` → py
- `*.rs`/`Cargo.toml` → rust
- `*.java`/`pom.xml`/`build.gradle` → java
- `*.php`/`composer.json` → php
- `*.cs` → csharp

Used only to pick which files to inspect for public surface and imports.

## Import evidence (conservative)

Only record a module→module dependency when a source file in A imports a path that resolves into B's folder or B's public package name.

Do not use comments, TODOs, or docs as dependency evidence.

## CODEOWNERS

If a rule matches the module path, use that team as `owner`. Otherwise `UNKNOWN`.
