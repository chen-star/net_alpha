# AGENTS.md

This file provides guidance to AI coding agents working with code in this repository.

## Project Overview

`wash-alpha` (package `net_alpha`, current version `0.40.0`) is a local-first Python tool for cross-account wash sale detection, tax-performance analysis, and pre-trade simulation — covering equities, options, and ETFs. It ships a Typer CLI plus an optional FastAPI web UI (`net-alpha ui`) which is now the primary interactive surface.

## Tech Stack

- **Python 3.11+** (pinned in `.python-version`)
- **Package manager:** `uv` — always use `uv run <cmd>`, never activate venv manually
- **Build backend:** `hatch` via `pyproject.toml`
- **CLI framework:** `typer[all]` (bundles `rich` and `click`)
- **Data models:** `pydantic` v2
- **ORM/storage:** `sqlmodel` over SQLite at `~/.net_alpha/net_alpha.db`
- **Date arithmetic:** stdlib `datetime.date` + `timedelta` (trade dates stored as `YYYY-MM-DD` strings as-is from broker CSV; no timezone conversion)
- **Config:** `pyyaml` for `etf_pairs.yaml`
- **Logging:** `loguru`
- **Linter/formatter:** `ruff` (replaces flake8 + black)
- **Tests:** `pytest`, `pytest-cov`, `factory_boy`

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run net-alpha --help

# Run tests
uv run pytest
# or via Makefile:
make test

# Run linter
uv run ruff check .
uv run ruff format .
# or:
make lint

# Run a single test file
uv run pytest tests/path/to/test_file.py

# Run tests matching a pattern
uv run pytest -k "test_wash_sale"
```

## Architecture

### CLI Commands (Typer)

```
net-alpha <csv> [<csv>...] --account <label> [--detail]   # hidden default: import + check + render
net-alpha sim <ticker> <qty> --price P [--account <l>]    # pre-trade what-if planner
net-alpha imports                                          # list past imports
net-alpha imports rm <id> [--yes]                          # remove an import
net-alpha migrate-from-v1 [--yes]                          # v1 → v2 helper (v2.0.x only)
net-alpha ui [--port N] [--no-browser] [--reload]          # launch local web UI in browser
```

The CSV-import default is a hidden `run` subcommand routed via `_FileFirstGroup` (`cli/app.py`) so file paths can sit in the first positional slot. The web UI is the primary interactive surface; the CLI subcommands are kept lean.

### Data Flow

1. **CSV import** → bundled BrokerParser detects from headers (Schwab transactions + Schwab Realized G/L) → trades parsed → idempotent dedup via natural_key → stored to SQLite
2. **Splits sync (optional)** → `splits/apply.py` rewrites lot quantities from canonical inputs (trade qty × cumulative split multiplier); `lot_overrides` is an audit log, not a gate
3. **Wash sale engine** → incremental window-based recompute (±30 days around new/removed trade dates) → assigns confidence label → adjusts cost basis of replacement lot
4. **Audit / reconciliation (optional)** → `audit/reconciliation.py` cross-checks per-trade computed P&L against a broker's Realized G/L file (Schwab supported); `audit/hygiene.py` surfaces missing-basis / missing-quote rows on the Imports page

### Broker Support

**Supported brokers (v2.0):** Schwab — both transaction CSV (`brokers/schwab.py`) and Realized G/L CSV (`brokers/schwab_realized_gl.py`, used for audit reconciliation).

Other brokers can be added by contributing a parser at `src/net_alpha/brokers/<name>.py` — implement the `BrokerParser` Protocol and register it in `brokers/registry.py`. Realized G/L providers go in `audit/brokers/` and register in `audit/brokers/registry.py`.

### Web UI

`src/net_alpha/web/` is an optional FastAPI subpackage providing a local browser UI. Launched via `net-alpha ui`. Top-level pages: `/` (Portfolio), `/positions` (Holdings + Plan), `/sim` (with suggestion chips), `/tax` (performance + harvest planner + projection + wash sales), `/imports`, `/ticker/{symbol}`, `/settings`. Manual trade CRUD lives at `/trades` (POST routes for add / edit-manual / edit-transfer / delete). Templates use Jinja + HTMX + Alpine. Assets (htmx, alpine, ApexCharts, Lucide v0.469.0, Inter, JetBrains Mono) are vendored under `web/static/` — no CDN, no node, no npm.

UI deps are in the `[ui]` optional group; install with `uv sync --extra ui`. The web layer only calls existing public seams (`Repository`, engine functions, portfolio/planner/audit pure functions) — **no business logic lives in `web/`**.

### Disclaimer Policy

Every command output ends with exactly:

> ⚠ This is informational only. Consult a tax professional before filing.

No exceptions. Not skippable.

---

<!-- generated-by: gsd-doc-writer -->
<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **net_alpha** (4382 symbols, 15207 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/net_alpha/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/net_alpha/context` | Codebase overview, check index freshness |
| `gitnexus://repo/net_alpha/clusters` | All functional areas |
| `gitnexus://repo/net_alpha/processes` | All execution flows |
| `gitnexus://repo/net_alpha/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
