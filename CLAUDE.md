# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`wash-alpha` (package `net_alpha`) is a local-first Python CLI tool for cross-account wash sale detection, covering equities, options, and ETFs. The v2 design spec lives in `docs/superpowers/specs/2026-04-25-v2-simplification-design.md`.

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
uv run net-alpha

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
net-alpha <csv> [<csv>...] --account <label> [--detail]   # default: import + check + render
net-alpha sim <ticker> <qty> --price P [--account <l>]    # pre-trade what-if planner
net-alpha imports                                          # list past imports
net-alpha imports rm <id> [--yes]                          # remove an import
net-alpha migrate-from-v1 [--yes]                          # v1 → v2 helper (v2.0.x only)
```

### Data Flow

1. **CSV import** → bundled BrokerParser detects from headers (Schwab at launch) → trades parsed → idempotent dedup via natural_key → stored to SQLite
2. **Wash sale engine** → incremental window-based recompute (±30 days around new/removed trade dates) → assigns confidence label → adjusts cost basis of replacement lot

### Key Domain Models (Pydantic v2 + SQLModel)

- `Trade` — canonical trade with `ticker` (underlying), `action`, `quantity`, `proceeds`, `cost_basis`, optional `OptionDetails`
- `OptionDetails` — `strike`, `expiry`, `call_put` (parsed from symbol string via regex)
- `Lot` — buy lot with `adjusted_basis` (updated when a wash sale rolls into it)
- `WashSaleViolation` — links loss sale + triggering buy, stores `confidence`, `disallowed_loss`
- `ImportRecord` — tracks each CSV import with timestamp and account label; used by `net-alpha imports`

### Confidence Labels (3-tier)

| Label       | Color  | Meaning                                 |
| ----------- | ------ | --------------------------------------- |
| `Confirmed` | Red    | Definite wash sale (IRS Pub 550)        |
| `Probable`  | Yellow | Likely; CPA review recommended          |
| `Unclear`   | Blue   | Ambiguous; flag for professional review |

### Option Symbol Parsing

Options are parsed using hand-written regexes within each broker's `BrokerParser` implementation (e.g., Schwab uses `schwab_human` format). Unknown formats fall back to a best-effort OCC-standard cascade with a parse warning.

### ETF Substantially-Identical Pairs

Bundled in `etf_pairs.yaml` (S&P 500: SPY/VOO/IVV/SPLG, Nasdaq-100: QQQ/QQQM, etc.). User can extend with `~/.net_alpha/etf_pairs.yaml` — user file adds to defaults, never replaces them.

### Database

- Single SQLite DB at `~/.net_alpha/net_alpha.db` (all years, cross-year window detection works)
- Schema versioning via `meta` table (`schema_version` integer); hand-written `ALTER TABLE` migrations — no migration framework
- Wash sale recompute is incremental: only the ±30-day window around affected trade dates is recalculated on import or import removal

### Disclaimer Policy

Every command output ends with exactly:

> ⚠ This is informational only. Consult a tax professional before filing.

No exceptions. Not skippable.

## Testing Strategy

- **Wash sale engine:** 100% unit test coverage, pure functions, no mocks. Use `factory_boy` fixtures. Must cover: boundary dates (day 0, 30, 31), partial wash sales, FIFO multi-buy allocation, cross-account matches, all confidence labels, cross-year windows.
- **Broker parsers:** Golden-file tests with anonymized real broker CSV samples → expected `Trade` output.
- **Integration tests:** Import → engine → render pipeline tested end-to-end with fixture CSVs.

## Data Privacy Constraints

All trade data stays local. There are no remote calls. No telemetry.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **net_alpha** (1692 symbols, 3890 relationships, 136 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
