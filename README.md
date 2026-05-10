<div align="center">

<img src="assets/logo.svg" alt="net-alpha" width="420">

**Cross-account wash sale detection for stocks, options, and ETFs — local-first, IRS Pub 550 rules, with a tax-harvest planner and pre-trade simulator.**

[![CI](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml/badge.svg)](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/wash-alpha.svg)](https://pypi.org/project/wash-alpha/)
[![Downloads](https://static.pepy.tech/badge/wash-alpha)](https://pepy.tech/project/wash-alpha)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![codecov](https://codecov.io/github/chen-star/net_alpha/graph/badge.svg?token=XETFUGJO3L)](https://codecov.io/github/chen-star/net_alpha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Overview](#overview) ·
[Quickstart](#quickstart) ·
[Service management](#service-management) ·
[Features](#features) ·
[Usage](#usage) ·
[How the rules work](#how-the-rules-work) ·
[Architecture](#architecture)

</div>

---

## Overview

When you trade across multiple brokerages, each platform tracks wash sales **only within its own ecosystem**. A loss sale on Schwab can be silently neutralized by a repurchase on Fidelity, and you won't find out until tax season — long after the window to act has closed.

The problem compounds when you trade **options** alongside the underlying, or **ETFs** that track the same index.

**net-alpha** is a local-first Python tool that gives you a single, unified view of your wash sale exposure across every account, asset class, and tax year — *before* it's too late to act.

> [!NOTE]
> The package is published to PyPI as **`wash-alpha`** but the CLI command is **`net-alpha`**. Both names refer to the same project.

## Quickstart

`net-alpha` requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install with the local web UI
uv tool install 'wash-alpha[ui]'

# One-time: install the always-on background service
net-alpha service install

# Open the dashboard (browser opens automatically)
net-alpha ui
```

The service runs locally at http://127.0.0.1:8765. It refreshes prices every 4 hours
and re-runs forward-looking wash-sale + §1091 detection daily. Stop it any time with
`net-alpha service stop` (data at `~/.net_alpha/` is left untouched).

Prefer a one-shot launch without the background service? `net-alpha ui` still works in
ephemeral mode (Ctrl-C to stop). The service is opt-in.

Prefer the terminal? The CLI works without UI extras:

```bash
uv tool install wash-alpha
net-alpha schwab.csv --account personal --detail
```

## Service management

| Command | Effect |
|---|---|
| `net-alpha service install` | Provision the runtime venv at `~/.net_alpha/venv/`, write the launchd plist + sandbox profile, and (re)load the agent. Idempotent — safe to re-run. |
| `net-alpha service start` | Start (or reload) the service |
| `net-alpha service stop` | Stop the service. Survives reboots until `start` |
| `net-alpha service restart` | Restart |
| `net-alpha service pause` | Freeze background jobs but keep the dashboard reachable |
| `net-alpha service resume` | Unfreeze jobs |
| `net-alpha service status` | Health report (also `--json` for scripting) |
| `net-alpha service logs -f` | Tail the service log |
| `net-alpha service uninstall` | Remove plist, sandbox profile, and runtime venv. Your data at `~/.net_alpha/net_alpha.db` is preserved. |

The dashboard at `/settings/service` exposes the same controls in a UI surface, plus
recent-runs history and a status pill in the site header.

### What `install` does

Everything the running service needs lives inside `~/.net_alpha/`, the only path
the sandbox profile allows the service to write to:

- `~/.net_alpha/venv/` — a dedicated runtime venv (homebrew Python 3.11 via `uv`) with `wash-alpha` installed from your local project source.
- `~/.net_alpha/bin/net-alpha-wrap` — the launchd wrapper script.
- `~/.net_alpha/run/sandbox.sb` — the sandbox-exec profile applied to the running service.
- `~/Library/LaunchAgents/com.netalpha.service.plist` — the LaunchAgent registration.

The runtime venv intentionally lives outside `~/Documents/`. Under launchd, the
service runs with a TCC identity that can't read user-data folders, so the
project's own `.venv/` is unreadable; `~/.net_alpha/` is TCC-clear.

Re-running `install` is safe — it bootouts a stale plist before re-bootstrapping
and reinstalls `wash-alpha` with `uv pip install --reinstall-package wash-alpha`
(deps stay cached, so the refresh is fast).

### Re-installing after code changes

The runtime venv is a non-editable snapshot of your project source at install
time. To make the running service reflect new code or `pyproject.toml` changes,
re-run `net-alpha service install`.

For active development, run `net-alpha …` directly from your project's editable
`.venv` — the LaunchAgent is for the always-on background service, not for the
dev edit-run loop.

## Features

- **Cross-account intelligence** — match a loss sale on one broker against a repurchase on another in a single pass. The whole point of the tool.
- **Bundled broker parsers** — Schwab transactions and Schwab Realized G/L are supported out of the box. Other brokers can be added by contributing a parser.
- **Local web UI** — Portfolio · Positions · Tax · Sim · Imports · per-ticker drill-down, all rendered server-side via HTMX. No Node, no npm, no CDN at runtime, dependencies vendored.
- **Pre-trade simulation** — `net-alpha sim TSLA 10 --price 180` shows FIFO lot consumption, realized P&L, and a cross-account wash-sale verdict per account *before* you execute. The Sim page surfaces one-click suggestion chips (largest unrealized loss, wash-sale risk, largest unrealized gain).
- **Tax-harvest planner** — a forward-looking, plan-builder assistant turns the harvest queue into a ranked, editable plan (greedy by tax saved, capped by §1211's $3,000 ordinary-loss limit). Honors user-declared position targets so it never closes something you want to keep.
- **§1256 awareness** — index options (SPX, NDX, RUT, VIX, etc.) are recognized as §1256 contracts: wash-sale-exempt with statutory 60/40 LT/ST classification.
- **Auditable explanations** — every wash-sale flag includes rule citation, source trades, match reason, math, and confidence reasoning — inline in the UI or via `--detail` on the CLI. Per-symbol reconciliation cross-checks computed P&L against your broker's Realized G/L file.
- **After-tax performance** — the Tax → Performance view shows realized P&L *after* estimated taxes, with a tax-drag breakdown and an ST/LT/§1256 mix bar.
- **Manual trade CRUD** — add, edit, transfer, or delete trades by hand from the web UI; wash sales recompute automatically over the affected window.
- **100% local & zero-knowledge** — your trade data, accounts, and P&L never leave the box. Symbols are sent to Yahoo Finance for live quotes only; disable with `prices.enable_remote: false`.

## Usage

### Local web UI

```bash
net-alpha ui [--port 8765] [--no-browser] [--reload]
```

Drop CSVs onto the dashboard, drill into any ticker, build a harvest plan, hand-enter trades, run pre-trade sims with suggested chips. Server-side HTMX, dies on Ctrl-C.

### Import + check from the CLI

```bash
net-alpha schwab.csv --account personal
```

Imports the CSV, recomputes wash sales over the affected window, and prints a watch list plus a YTD impact summary. Add `--detail` for a per-violation breakdown.

### Pre-trade simulation

```bash
net-alpha sim TSLA 10 --price 180
```

Lists every account that holds the ticker, with FIFO lot consumption, realized P&L, and a cross-account wash-sale verdict per account.

### Manage past imports

```bash
net-alpha imports                # list
net-alpha imports rm 3 --yes     # remove (recomputes wash sales)
```

### Migrate from v0.x

```bash
net-alpha migrate-from-v1 --yes
```

Reads `~/.net_alpha/net_alpha.db` (v1 schema) and writes a fresh v2 DB at `~/.net_alpha/net_alpha.db.v2`. Helper exists only on the v2.0.x line.

## How the rules work

`net-alpha` strictly follows IRS Publication 550. A wash sale is triggered when you sell a security at a loss and buy a *substantially identical* security within 30 days before or after the sale.

| Asset type | Scenario | Confidence |
| :--- | :--- | :--- |
| **Equities** | Sold ticker `X` at a loss, bought ticker `X` within 30 days | 🟢 **Confirmed** |
| **Options** | Sold option at a loss, bought same option (exact strike + expiry) | 🟢 **Confirmed** |
| **Options** | Sold option at a loss, bought option on the same underlying | 🟡 **Probable** |
| **ETFs** | Sold ETF at a loss, bought the exact same ETF ticker | 🟢 **Confirmed** |
| **ETFs** | Sold ETF at a loss, bought ETF tracking the same index (e.g., `SPY` → `VOO`) | 🔵 **Unclear** |

Bundled "substantially identical" pairs cover the major index-tracking ETFs (S&P 500: SPY/VOO/IVV/SPLG, Nasdaq-100: QQQ/QQQM, etc.). Extend with your own pairs by editing `~/.net_alpha/etf_pairs.yaml` — your file *adds* to the bundled defaults, never replaces them.

### §1092 Straddles

`net-alpha` also surfaces same-underlying offsetting positions caught by
**IRC §1092** (the "straddle" rule). v1 detects:

- **Literal straddles** — long call + long put on the same underlying
- **Married puts** — long stock + long put on the same underlying
- **Non-qualified covered calls** — long stock + short call that fails the
  §1092(c)(4) Qualified Covered Call test
- **Vertical spreads** — long + short option of the same series, opposite legs

Run `net-alpha straddles` (add `--detail` for rule citations and per-leg
breakdown). When you simulate a sell, any §1092 straddle still active on the
ticker is surfaced inline.

The QCC test in v1 is a conservative approximation of IRS Notice 2003-31's
lowest-qualified-benchmark step table — it errs on the side of flagging
deeper-ITM calls. Loss-deferral computation, the §1092(b) modified wash-sale
rule, identified-straddle elections, and correlation-based stock/ETF offsets
are deferred to v2.

### Adding a broker

Contribute a parser at `src/net_alpha/brokers/<name>.py` — implement the `BrokerParser` Protocol and register it in `brokers/registry.py`. Realized G/L parsers go in `src/net_alpha/audit/brokers/`.

## Architecture

```
CSV → BrokerParser → Trade (Pydantic) ──► SQLite (~/.net_alpha/net_alpha.db)
                                              │
                                              ├─► Wash-sale engine  (incremental ±30-day window)
                                              ├─► §1256 classifier  (60/40 LT/ST split)
                                              ├─► Reconciliation    (against broker Realized G/L)
                                              └─► Portfolio / planner / pricing  (pure functions)
                                                                │
                                                  ┌─────────────┴─────────────┐
                                                  ▼                           ▼
                                            Typer CLI                 FastAPI + HTMX UI
```

- **Stack** — Python 3.11+, `pydantic` v2, `sqlmodel` over SQLite, `typer` CLI, optional `fastapi` + Jinja + HTMX UI, `ruff`, `pytest`. Managed with `uv`.
- **Storage** — single SQLite DB at `~/.net_alpha/net_alpha.db`; cross-year window detection works because all trades live in one place. Schema versioned via a `meta` table; hand-written `ALTER TABLE` migrations.
- **Engine** — wash-sale recompute is incremental, only the ±30-day window around affected trade dates is recalculated on import or removal. Every emitted violation is reproducible from source trades.
- **Web UI** — optional subpackage at `src/net_alpha/web/`. Calls only existing public seams (`Repository`, engine functions, audit/portfolio/planner pure functions); no business logic in `web/`. Static assets vendored — no CDN at runtime, no Node toolchain.

## Development

```bash
uv sync --extra ui --extra dev      # install everything
uv run pytest                       # tests (or: make test)
uv run ruff check .                 # lint
uv run ruff format .                # format
make build-css                      # rebuild the Tailwind bundle
```

## Disclaimer

> [!IMPORTANT]
> **This tool is for informational purposes only and does not constitute tax or legal advice.**
> Wash sale rules — especially around options and ETFs — involve unsettled areas of tax law. Anything labeled `Probable` or `Unclear` should be reviewed with a qualified CPA before making filing decisions.

<br>

<div align="center">

<sub>If <code>net-alpha</code> saves you a CPA call this tax season, consider <a href="https://github.com/chen-star/net_alpha">starring the repo</a> — it's the best signal for other traders looking for a tool they can trust with their tax data.</sub>

</div>
