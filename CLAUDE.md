# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`net_alpha` is a local-first Python CLI tool for cross-account IRS wash sale detection, covering equities, options, and ETFs. It is currently in the pre-implementation phase — the full spec lives in `PRD.md` and `docs/superpowers/specs/2026-04-12-net-alpha-product-design.md`.

## Tech Stack

- **Python 3.11+** (pinned in `.python-version`)
- **Package manager:** `uv` — always use `uv run <cmd>`, never activate venv manually
- **Build backend:** `hatch` via `pyproject.toml`
- **CLI framework:** `typer[all]` (bundles `rich` and `click`)
- **Interactive prompts:** `questionary`
- **Data models:** `pydantic` v2
- **ORM/storage:** `sqlmodel` over SQLite at `~/.net_alpha/net_alpha.db`
- **LLM:** `anthropic` SDK — `claude-haiku-4-5` for CSV schema detection only
- **Date arithmetic:** stdlib `datetime.date` + `timedelta` (trade dates stored as `YYYY-MM-DD` strings as-is from broker CSV; no timezone conversion)
- **Config:** `pydantic-settings` reading `~/.net_alpha/config.toml`
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
net-alpha                          # First-run wizard (when DB is empty)
net-alpha import <broker> <file>   # Import CSV, LLM schema detection
net-alpha check [--ticker X] [--type options] [--year YYYY]
net-alpha simulate sell <ticker> <qty> [--price P]
net-alpha rebuys                   # Safe-to-rebuy tracker
net-alpha report [--year YYYY] [--csv]
```

### Data Flow

1. **CSV import** → LLM detects schema from headers + 3 anonymized sample rows → user confirms → schema cached (`broker_name + SHA256(header_row)`) → trades stored as lots in SQLite
2. **Wash sale engine** → scans all lots for loss sales → 30-day window check (crosses year boundaries) → assigns confidence label → calculates disallowed loss → adjusts cost basis of replacement lot

### Key Domain Models (Pydantic v2 + SQLModel)

- `Trade` — canonical trade with `ticker` (underlying), `action`, `quantity`, `proceeds`, `cost_basis`, optional `OptionDetails`
- `OptionDetails` — `strike`, `expiry`, `call_put` (parsed from symbol string via regex, not LLM)
- `Lot` — buy lot with `adjusted_basis` (updated when a wash sale rolls into it)
- `WashSaleViolation` — links loss sale + triggering buy, stores `confidence`, `disallowed_loss`
- `SchemaCache` — stored per broker, keyed by `broker_name + SHA256(header_row)`

### Confidence Labels (3-tier)

| Label       | Color  | Meaning                                 |
| ----------- | ------ | --------------------------------------- |
| `Confirmed` | Red    | Definite wash sale (IRS Pub 550)        |
| `Probable`  | Yellow | Likely; CPA review recommended          |
| `Unclear`   | Blue   | Ambiguous; flag for professional review |

### Option Symbol Parsing

Options are parsed using hand-written regexes — **not** LLM-generated parsers. The schema cache stores an `option_format` field (e.g., `schwab_human`, `occ_standard`, `robinhood_human`) to select the correct regex. Unknown formats use a best-effort cascade with a parse warning.

### ETF Substantially-Identical Pairs

Bundled in `etf_pairs.yaml` (S&P 500: SPY/VOO/IVV/SPLG, Nasdaq-100: QQQ/QQQM, etc.). User can extend with `~/.net_alpha/etf_pairs.yaml` — user file adds to defaults, never replaces them.

### Database

- Single SQLite DB at `~/.net_alpha/net_alpha.db` (all years, cross-year window detection works)
- Schema versioning via `meta` table (`schema_version` integer); hand-written `ALTER TABLE` migrations — no migration framework
- `check` defaults to current year; `--year YYYY` scopes loss sales only (30-day window still crosses year boundaries)

### LLM Usage

- Called only during first import of a new broker CSV format
- Only CSV headers + 3 anonymized rows sent (no account numbers, no real dollar amounts)
- Retry 3× with exponential backoff on failure, then hard fail
- API key: `ANTHROPIC_API_KEY` env var → `~/.net_alpha/config.toml` (first-run wizard prompts if neither set)
- Schema confirmed by user before any data is stored; cached after confirmation

### Disclaimer Policy

Every command output ends with exactly:

> ⚠ This is informational only. Consult a tax professional before filing.

No exceptions. Not skippable.

## Testing Strategy

- **Wash sale engine:** 100% unit test coverage, pure functions, no mocks. Use `factory_boy` fixtures. Must cover: boundary dates (day 0, 30, 31), partial wash sales, FIFO multi-buy allocation, cross-account matches, all confidence labels, cross-year windows.
- **LLM schema detection:** Anthropic client mocked. Test retry logic, caching, schema confirmation, error handling independently.
- **Integration tests:** Golden-file tests with anonymized real broker CSV samples → expected `Trade` output.

## Data Privacy Constraints

All trade data stays local. The only remote call is the one-time LLM schema detection per broker format. No telemetry.
