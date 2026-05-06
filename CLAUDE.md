# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`wash-alpha` (package `net_alpha`, current version `0.40.0`) is a local-first Python tool for cross-account wash sale detection, tax-performance analysis, and pre-trade simulation — covering equities, options, and ETFs. It ships a Typer CLI plus an optional FastAPI web UI (`net-alpha ui`) that is now the primary interactive surface.

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
net-alpha <csv> [<csv>...] --account <label> [--detail]   # hidden default: import + check + render
net-alpha sim <ticker> <qty> --price P [--account <l>]    # pre-trade what-if planner
net-alpha imports                                          # list past imports
net-alpha imports rm <id> [--yes]                          # remove an import
net-alpha migrate-from-v1 [--yes]                          # v1 → v2 helper (v2.0.x only)
net-alpha ui [--port N] [--no-browser] [--reload]          # launch local web UI in browser
```

The CSV-import default is a hidden `run` subcommand routed via a custom `_FileFirstGroup` (`cli/app.py`) so file paths can sit in the first positional slot.

### Data Flow

1. **CSV import** → bundled BrokerParser detects from headers (Schwab transactions + Schwab Realized G/L at launch) → trades parsed → idempotent dedup via natural_key → stored to SQLite
2. **Splits sync (optional)** → `splits/` rewrites lot quantities from canonical inputs (trade qty × cumulative split multiplier) — never gated on the audit log
3. **Wash sale engine** → incremental window-based recompute (±30 days around new/removed trade dates) → assigns confidence label → adjusts cost basis of replacement lot
4. **Audit / reconciliation (optional)** → `audit/reconciliation.py` cross-checks per-trade computed P&L against a broker's Realized G/L file (Schwab supported); `audit/hygiene.py` surfaces missing-basis / missing-quote rows on the Imports page

### Key Domain Models (Pydantic v2 + SQLModel)

- `Trade` — canonical trade with `ticker` (underlying), `action`, `quantity`, `proceeds`, `cost_basis`, optional `OptionDetails`; supports a manual-trade source for hand-entered rows and a transfer source for inbound external lots
- `OptionDetails` — `strike`, `expiry`, `call_put` (parsed from symbol string via regex)
- `Lot` — buy lot with `adjusted_basis` (updated when a wash sale rolls into it). Quantity is derived from trade qty × cumulative split multiplier (see `splits/apply.py`); `lot_overrides` is an audit log, not a gate
- `WashSaleViolation` — links loss sale + triggering buy, stores `confidence`, `disallowed_loss`
- `ExemptMatch` — would-have-been wash-sale exempt under a named rule (e.g., `section_1256`); sibling of `WashSaleViolation`
- `Section1256Classification` — per-closed-§1256-trade 60/40 LT/ST split; pure derived data, cleared/rebuilt on recompute
- `ImportRecord` — tracks each CSV import with timestamp and account label; used by `net-alpha imports`
- `RealizedGLLot` (`models/realized_gl.py`) — broker-reported per-lot realized P&L row, used by reconciliation
- `PositionTarget` (`targets/models.py`) — user-declared "what I want to hold" entry (USD or shares) consumed by the harvest plan-builder
- `Split` / `LotOverride` (`models/splits.py`) — corporate action input + audit row written when split adjustment first applies

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

### §1256 Contracts

Broad-based equity index options (SPX, NDX, RUT, VIX, OEX, XSP, MXEF, MXEA — bundled in `section_1256_underlyings.yaml`) are recognized as §1256 contracts. The engine emits an `ExemptMatch` record (not a `WashSaleViolation`) when either side of a wash-sale candidate is §1256 — they are exempt from §1091 under §1256(c). A separate classifier (`section_1256/classifier.py`) splits closed §1256 trade P&L 60/40 LT/ST per §1256(a)(3), regardless of holding period. Open positions at year-end are NOT marked-to-market in v1; users consult their 1099-B / Form 6781.

### Database

- Single SQLite DB at `~/.net_alpha/net_alpha.db` (all years, cross-year window detection works)
- Schema versioning via `meta` table (`schema_version` integer); hand-written `ALTER TABLE` migrations — no migration framework
- Wash sale recompute is incremental: only the ±30-day window around affected trade dates is recalculated on import or import removal
- Schema is at v18 as of 2026-05-05 (added `loss_carryforward` table for prior-year ST/LT carryforward overrides).

### Pricing & Portfolio modules

- Pricing subsystem: `pricing/` — `PriceProvider` ABC, `YahooPriceProvider`, SQLite-backed `PriceCache`, `PricingService` orchestrator.
- Portfolio aggregations: `portfolio/` — pure functions for positions, KPIs, allocation (donut + leaderboard), equity curve, cash flow, lot aging, wash-sale watch (recent loss closes), top movers, calendar P&L, benchmark, after-tax realized P&L (`after_tax.py`), forward tax planner (`tax_planner.py` — harvest queue, offset budget, projection, traffic light), sim suggestions (`sim_suggestions.py` — chip-strip picks for the Sim page), and freshness checks.
- Carryforward subsystem: `portfolio/carryforward.py` — pure-function ST/LT capital-loss carryforward derive (replays prior years honoring §1212(b) cross-category netting and the §1211 $3K cap) with hybrid auto-derive + user-override resolution; consumed by `compute_after_tax` and `compute_offset_budget`. User overrides are edited at `/settings/carryforward`.
- Lot selector: `engine/lot_selector.py` — pure-function `select_lots()` with five strategies (FIFO/LIFO/HIFO/MIN_TAX/MAX_LOSS), wash-sale-aware via `engine/detector.py` and `engine/etf_pairs.py`. Surfaced as a comparison table on the Sim page (Sell action only). MIN_TAX brute-forces ≤12 lots; greedy fallback beyond.
- Audit subsystem: `audit/` — provenance helpers (`provenance.py` encodes/decodes deep links to a metric's source rows), per-broker reconciliation against Realized G/L (`reconciliation.py` + `audit/brokers/`), and data-hygiene rollups (`hygiene.py`) for the Imports page.
- Splits + targets + prefs: `splits/` (corporate-action sync + lot-quantity rewrite), `targets/` (position targets used by harvest plan-builder), `prefs/` (per-profile UI preferences).

### Web UI (optional, v2.1+)

`src/net_alpha/web/` is an optional FastAPI subpackage providing a local browser UI. It only calls existing public seams (`Repository`, engine functions, `csv_loader`, `BrokerParser`, audit/portfolio/planner pure functions) — **no business logic in `web/`**. Templates use Jinja with HTMX for fragment swaps and Alpine for tiny client state. Static assets (htmx, alpine, ApexCharts, Lucide icons, SortableJS, built `app.css`, Inter + JetBrains Mono fonts) are vendored under `web/static/` — no CDN at runtime, no node, no npm.

Launch with `net-alpha ui`. Picks a free port in 8765–8775 (override with `--port`), binds to loopback only, dies on Ctrl-C. UI deps are in the `[ui]` optional group (FastAPI, uvicorn, Jinja2, python-multipart, yfinance); install with `uv sync --extra ui`.

Asset rebuild targets in the `Makefile`: `build-css` (Tailwind via `pytailwindcss`), `vendor-fonts`, `vendor-apex`, `vendor-lucide` (pinned to v0.469.0), `vendor-sortable` (SortableJS pinned to v1.15.2 for Plan-tab drag-to-reorder).

### Web UI surface

Top-level pages (one route file per area in `web/routes/`):

- `/` — Portfolio (KPIs, allocation, equity curve, cash curve, top movers, options/short-options panels, wash-sale watch).
- `/positions` — Holdings views (all / stocks / options / at-loss / closed) plus a Plan view backed by `PositionTarget`s; includes a "Set basis" multi-lot editor, a per-row "↗ Sim" deep link, and a Manual sort mode that lets the user drag rows into a custom order persisted via `position_targets.sort_order` (POST `/positions/plan/reorder`).
- `/sim` — Pre-trade simulator with a `/sim/suggestions` chip strip (largest unrealized loss, wash-sale risk, largest unrealized gain, or a demo chip on empty portfolios) and a recents list.
- `/tax` — Tax performance, harvest queue, harvest plan-builder (`/tax/harvest/plan`), tax-projection setup form (`/tax/projection-config`), wash-sale + exempt-match listings.
- `/imports` — Imports table, drop-zone upload, preview/commit, per-import detail, data-hygiene groups (Missing basis / No price quote / Missing dates as collapsible `<details>` buckets).
- `/ticker/{symbol}` — Per-symbol timeline, lots, and reconciliation views; lot edit + add-trade forms.
- `/settings` — Settings drawer (profile, density, ETF pairs, imports, about) — resizable.
- `/trades` (POST) — Manual trade CRUD: add, edit-manual, edit-transfer, delete; recomputes wash sales over the affected window.
- Misc: `/preferences` (Alpine state persistence), `/quit`, `/provenance/{encoded}`, `/reconciliation/{symbol}`, `/audit/set-basis*`.

### Web UI conventions

Each scoped page uses a top-of-page toolbar: `Period` (YTD / specific year / Lifetime) + `Account` (All / per-account). State is per-page (not global). Heavy panels load lazily as HTMX fragments under stable IDs. The settings drawer is resizable; chart panels support zoom; positions has client-side search.

### Tax Performance Tab

`/tax?view=performance` renders an after-tax realized P&L panel using configured marginal rates from the existing `tax:` config section. Reads pure-function `compute_after_tax(...)` in `portfolio/after_tax.py`. Surfaces 4 KPIs (pre-tax, tax bill, after-tax, tax drag), an ST/LT/§1256 mix bar, a wash-sale cost row, and the effective tax rate. Caveats (capital-loss limitation, MAGI threshold, Lifetime-period bracket assumption) are documented inline. Inline-expand explanations are available on every wash-sale row and exempt match via `tax/violation/{id}/explain` and `tax/exempt/{id}/explain` HTMX fragments; the same content is available via the CLI `--detail` flag.

### Tax Harvest Planner

`portfolio/tax_planner.py` is a forward-looking, pure-function planner over `Repository` + `PricingService` reads (no DB writes). It builds a greedy harvest plan ranked by tax saved, summarizes user-edited picks, applies `ORDINARY_LOSS_CAP = $3,000` (§1211), and projects year-end tax. The planner consumes `PositionTarget`s from `targets/` so users can edit "what I want to hold" inline. The web surface lives at `/tax/harvest/plan` and its `_harvest_plan.html` fragment.

### Disclaimer Policy

Every command output ends with exactly:

> ⚠ This is informational only. Consult a tax professional before filing.

No exceptions. Not skippable.

## Testing Strategy

- **Wash sale engine:** 100% unit test coverage, pure functions, no mocks. Use `factory_boy` fixtures. Must cover: boundary dates (day 0, 30, 31), partial wash sales, FIFO multi-buy allocation, cross-account matches, all confidence labels, cross-year windows.
- **Broker parsers:** Golden-file tests with anonymized real broker CSV samples → expected `Trade` output.
- **Integration tests:** Import → engine → render pipeline tested end-to-end with fixture CSVs.

## Data Privacy Constraints

All trade data stays local. No telemetry.

### Price data (Phase 1+)

Symbols are sent to Yahoo Finance to fetch current quotes for the Portfolio
page. Trade data, accounts, P&L, and any other personally-identifying data
never leave the box. Disable price fetches by setting
`prices.enable_remote: false` in `~/.net_alpha/config.yaml`.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **net_alpha** (4838 symbols, 17109 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
