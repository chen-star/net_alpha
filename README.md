<div align="center">

<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/logo.svg" alt="net-alpha" width="420">

**Cross-account wash sale detection for stocks, options, and ETFs — local-first, IRS Pub 550 rules, with a tax-harvest planner and pre-trade simulator.**

[![CI](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml/badge.svg)](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/wash-alpha.svg)](https://pypi.org/project/wash-alpha/)
[![Downloads](https://static.pepy.tech/badge/wash-alpha)](https://pepy.tech/project/wash-alpha)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![codecov](https://codecov.io/github/chen-star/net_alpha/graph/badge.svg?token=XETFUGJO3L)](https://codecov.io/github/chen-star/net_alpha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Why](#why-net-alpha) ·
[Quickstart](#quickstart) ·
[Features](#features) ·
[Usage](#usage) ·
[Rules](#how-the-rules-work) ·
[Service](#always-on-service) ·
[Architecture](#architecture) ·
[Development](#development)

</div>

---

## Why net-alpha

When you trade across multiple brokerages, each platform tracks wash sales **only within its own ecosystem**. A loss sale on Schwab can be silently neutralized by a repurchase on Fidelity — you won't find out until tax season, long after the window to act has closed. The problem compounds when you trade **options** alongside the underlying, or **ETFs** that track the same index.

**net-alpha** is a local-first Python tool that gives you a single, unified view of your wash sale exposure across every account, asset class, and tax year — _before_ it's too late to act.

> [!NOTE]
> The package is published to PyPI as **`wash-alpha`** but the CLI command is **`net-alpha`**. Both names refer to the same project.

## See it in action

> Screenshots below use the built-in demo dataset — TSLA, NVDA, AAPL, SPY puts, an SPX §1256 call, plus a handful of open holdings (MSFT, AMZN, GOOGL, META, AMD, …). Pick **"Try the demo"** on the welcome screen to play with the same scenarios live.

**Wash-sale ledger** — every match across accounts, with confidence label and rule citation. The **NVDA** row is the case no single broker would ever flag: a loss closed in `schwab/taxable` is silently neutralized by a buy in `schwab/ira` 14 days later. **TSLA** and **AAPL** are confirmed same-account round-trips. **SPY** is an exact-strike-and-expiry options match — the lag is `-8d` because the _replacement_ leg was opened 8 days _before_ the loss close.

<p align="center">
<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/screenshots/wash-sales.png" alt="Wash-sale ledger across accounts" width="900">
</p>

**Per-symbol drilldown** — NVDA's timeline pulls lots from both accounts into one view, with realized / disallowed KPIs and the cross-account violation pinned underneath. Every row links back to the source trade so the chain is always auditable.

<p align="center">
<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/screenshots/ticker-nvda.png" alt="NVDA per-symbol drilldown" width="900">
</p>

**Pre-trade simulator** — propose `Sell 20 AAPL @ $170` and see realized P&L, FIFO lot consumption, and the wash-sale verdict _before_ you place the order. The lot-strategy table compares FIFO / LIFO / HIFO / MIN_TAX / MAX_LOSS side-by-side, with each strategy's wash-sale verdict computed independently. Suggestion chips at the top surface the largest unrealized loss (`NVDA −$3,098`) and gain (`AMD +$4,503`) for one-click sims.

<p align="center">
<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/screenshots/sim.png" alt="Pre-trade simulator with lot-strategy comparison" width="900">
</p>

**Portfolio dashboard** — KPIs, equity curve, cash & contributions overlay, monthly realized P&L bars, allocation rollup, and top movers — every account combined in one view, with toggles to drill in per-account.

<p align="center">
<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/screenshots/portfolio.png" alt="Portfolio dashboard" width="900">
</p>

## Quickstart

`net-alpha` requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install with the local web UI
uv tool install 'wash-alpha[ui]'

# 2. (Optional) Install the always-on background service
net-alpha service install

# 3. Open the dashboard (browser opens automatically)
net-alpha ui
```

The UI runs locally at `http://127.0.0.1:18765` (auto-picks the next free port in 18765–18775). With the service installed, prices refresh every 4 hours, forward-looking wash-sale checks run daily, and a snapshot backup runs at 03:30 UTC; without it, `net-alpha ui` runs ephemerally (Ctrl-C to stop).

> [!TIP]
> First run? Pick **"Try the demo"** on the welcome screen for a guided tour with sample data — no CSV needed. Replay any time from `/tour`.

Prefer the terminal? The CLI works without UI extras:

```bash
uv tool install wash-alpha
net-alpha schwab.csv --account personal --detail
```

## Features

### Detection

- **Cross-account intelligence** — match a loss sale on one broker against a repurchase on another in a single pass. The whole point of the tool.
- **§1091 wash sales** — equities, options (exact contract or same underlying), and ETFs (same ticker or same-index pair). Every match has a **Confirmed / Probable / Unclear** confidence label with rule citation.
- **Rev. Rul. 2008-5 IRA traps** — a loss in a taxable account replaced by a substantially-identical buy in an IRA / Roth / 401(k) / HSA is flagged as a `permanent_ira` violation: the loss is disallowed under §1091(a) but §1091(d)'s basis rollover cannot apply, so the loss is **permanently lost**. Surfaced inline on the Plan view as a red watch pill.
- **§1256 contracts** — index options (SPX, NDX, RUT, VIX, …) are recognized as §1256: wash-sale-exempt, statutory 60/40 LT/ST split per §1256(a)(3), and year-end **mark-to-market** per §1256(a)(1) (FMV cascade: Yahoo option close → Black-Scholes → intrinsic).
- **§1092 straddles** — `net-alpha straddles` surfaces literal straddles, married puts, non-qualified covered calls (with QCC test), and vertical spreads. Holding-period suspension warnings attach to affected lots.
- **Bundled "substantially identical" pairs** — major index-tracking ETFs (S&P 500, Nasdaq-100, Russell 2000, …). Extend with your own at `~/.net_alpha/etf_pairs.yaml` (additive, never replaces defaults).

### Planning

- **Pre-trade simulator** — `/sim` shows FIFO lot consumption, realized P&L, and a per-account cross-account wash-sale verdict _before_ you execute. Suggestion chips surface the largest unrealized loss, wash-sale risk, and largest unrealized gain.
- **Lot-selection strategies** — compare **FIFO / LIFO / HIFO / MIN_TAX / MAX_LOSS** side-by-side on a Sell sim, with each strategy's wash-sale verdict computed independently.
- **Tax-harvest planner** — `/tax/harvest/plan` turns the harvest queue into a ranked, editable plan (greedy by tax saved, capped by §1211's $3,000 ordinary-loss limit). Honors user-declared **PositionTargets** so it never closes something you want to keep.
- **Forward-looking watchlist** — the always-on service forward-simulates every PositionTarget daily and surfaces wash-sale / §1091 risk inline as colored pills on the Plan view, distinguishing deferred basis-rollover sales from permanent IRA-trap losses.
- **Action Inbox** — a single panel rolls urgent items (imminent wash-sale tripwires, §1092 holding-period suspensions, broken reconciliation, missing basis) into one place.
- **Verify** — a global "Data check" pill in the site header that audits live KPIs against pure-function recomputes (Realized P/L, after-tax, lot counts, per-account basis vs broker positions CSV) and offers one-click jumps to any divergence. Findings carrying `expected_section_1256` or `expected_cross_account` render a muted "· expected" badge so genuine errors stand out. Suppressible per finding; refreshed by a weekly Sunday 04:30 service job.

### Reporting

- **After-tax performance** — `/tax?view=performance` shows realized P&L _after_ estimated taxes, with a tax-drag breakdown and an ST/LT/§1256 mix bar.
- **Capital-loss carryforward** — auto-derived from prior years honoring §1212(b) cross-category netting and §1211 $3K cap, with hand-editable overrides at `/settings/carryforward`.
- **Auditable explanations** — every wash-sale flag includes rule citation, source trades, match reason, math, and confidence reasoning — inline in the UI or via `--detail` on the CLI.
- **Per-symbol reconciliation** — cross-checks computed P&L against your broker's Realized G/L file (Schwab supported); discrepancies surface inline on the ticker page.
- **Data hygiene rollup** — Imports page groups missing-basis / no-quote / missing-date rows so you can fix them in one pass.

### Local & private

- **100% local, zero-knowledge** — your trade data, accounts, and P&L never leave the box. Symbols are sent to Yahoo Finance for live quotes only; disable with `prices.enable_remote: false`.
- **No CDN at runtime, no Node** — htmx, Alpine, ApexCharts, Lucide icons, and fonts are vendored under `web/static/`.
- **Manual trade CRUD** — add, edit, transfer, or delete trades from the web UI; wash sales recompute over the affected window automatically.
- **Account-typed multi-select** — every toolbar (Portfolio, Positions, Sim, Tax, Imports) has an account multi-select with OR-semantic filtering. Each account carries a `type` (taxable / IRA / Roth / 401(k) / HSA / other) so IRA-trap detection knows which side is tax-advantaged.
- **Local backups, WAL-safe** — `net-alpha backup` snapshots `~/.net_alpha/` via SQLite's online `.backup()` API (safe while the service writes), with optional AES-256-GCM encryption (`--encrypt`). Daily 03:30 UTC snapshots + inline pre-mutation snapshots before every CSV import, `imports rm`, and `migrate-from-v1`. `net-alpha restore` is CLI-only and never auto-restarts the service.

## Usage

### Local web UI (primary surface)

```bash
net-alpha ui [--port 18765] [--no-browser] [--reload]
```

| Page               | Highlights                                                                                              |
| :----------------- | :------------------------------------------------------------------------------------------------------ |
| `/` Portfolio      | KPIs, equity curve with brush-strip drag-to-reperiod, cash curve, monthly P/L bars with lifetime-avg reference line, allocation, top movers, options & short-options panels, wash-sale watch. Rows are drag-to-reorder + hideable via the "Edit layout" toolbar. |
| `/positions`       | Holdings (all / stocks / options / at-loss / closed), drag-to-reorder Plan view, multi-lot basis editor                                                                                                                                                         |
| `/sim`             | Pre-trade simulator with suggestion chips and lot-strategy comparison table                                                                                                                                                                                     |
| `/tax`             | After-tax performance, harvest queue, plan-builder, projection setup, wash-sale + exempt-match listings                                                                                                                                                         |
| `/imports`         | Drop-zone upload (trades CSV or Schwab positions CSV — all-accounts or per-account header), preview/commit, per-import detail, data-hygiene buckets                                                                                                             |
| `/ticker/{symbol}` | Per-symbol timeline, lots, reconciliation, lot edit + add-trade forms                                                                                                                                                                                           |
| `/verify`          | Findings table (BasisRecon, RealizedRecon, StaleReference, …) with inline "Why?" explainer, one-click suppress, and freshness banner                                                                                                                            |
| `/settings`        | Profile, density, ETF pairs, carryforward, accounts + types, backups, service controls, about                                                                                                                                                                   |

Server-side HTMX + Alpine, dies on Ctrl-C.

### CLI

```bash
# Import a CSV → recompute wash sales → print watchlist + YTD impact
net-alpha schwab.csv --account personal [--detail]

# Pre-trade simulation across every account holding the ticker
net-alpha sim TSLA 10 --price 180

# §1092 straddles currently open
net-alpha straddles [--detail]

# Manage past imports (recomputes wash sales on remove)
net-alpha imports
net-alpha imports rm 3 --yes

# v1 → v2 schema migration helper (v2.0.x line only)
net-alpha migrate-from-v1 --yes

# Backups — manual snapshot (encrypted optional), list, restore
net-alpha backup [--encrypt] [--note "before tax-day cleanup"]
net-alpha backups
net-alpha restore <bundle-id> --yes
```

### Adding a broker

Bundled at launch: **Schwab** (transactions + Realized G/L for audit reconciliation). To add another:

1. Implement the `BrokerParser` Protocol at `src/net_alpha/brokers/<name>.py`.
2. Register it in `brokers/registry.py`.
3. (Optional) Add a Realized G/L parser at `src/net_alpha/audit/brokers/`.

## How the rules work

`net-alpha` strictly follows IRS Publication 550. A wash sale is triggered when you sell a security at a loss and buy a _substantially identical_ security within 30 days before or after the sale.

| Asset type   | Scenario                                                                     | Confidence       |
| :----------- | :--------------------------------------------------------------------------- | :--------------- |
| **Equities** | Sold ticker `X` at a loss, bought ticker `X` within 30 days                  | 🟢 **Confirmed** |
| **Options**  | Sold option at a loss, bought same option (exact strike + expiry)            | 🟢 **Confirmed** |
| **Options**  | Sold option at a loss, bought option on the same underlying                  | 🟡 **Probable**  |
| **ETFs**     | Sold ETF at a loss, bought the exact same ETF ticker                         | 🟢 **Confirmed** |
| **ETFs**     | Sold ETF at a loss, bought ETF tracking the same index (e.g., `SPY` → `VOO`) | 🔵 **Unclear**   |

### §1256 contracts

Broad-based equity index options (SPX, NDX, RUT, VIX, OEX, XSP, …) are exempt from §1091. Closed §1256 P&L is split 60/40 LT/ST per §1256(a)(3), regardless of holding period. Open positions at year-end are **marked-to-market** per §1256(a)(1), with prior-year MTM used as the new basis per §1256(a)(2). FMV cascade: Yahoo option close → Black-Scholes from underlying + 30-day historical vol → intrinsic if expired. §1256(c) loss-carryback election is out of scope — Form 6781 line 6 directly.

### IRA-trap wash sales (Rev. Rul. 2008-5)

When you sell at a loss in a **taxable** account and buy a substantially-identical security in a **tax-advantaged** account (IRA / Roth / 401(k) / HSA) within ±30 days, §1091(a) still disallows the loss, but §1091(d)'s basis rollover cannot apply (no IRA basis ledger). The detector classifies these as `permanent_ira` violations and surfaces them with their own watch pill — distinct from the deferred-basis `deferred` kind that rolls into the replacement lot.

### §1092 straddles

Same-underlying offsetting positions caught by IRC §1092:

- **Literal straddles** — long call + long put on the same underlying
- **Married puts** — long stock + long put on the same underlying
- **Non-qualified covered calls** — long stock + short call that fails the §1092(c)(4) Qualified Covered Call test
- **Vertical spreads** — long + short option of the same series, opposite legs

> [!NOTE]
> The QCC test in v1 is a conservative approximation of IRS Notice 2003-31's lowest-qualified-benchmark step table — it errs on the side of flagging deeper-ITM calls. Loss-deferral computation, the §1092(b) modified wash-sale rule, identified-straddle elections, and correlation-based stock/ETF offsets are deferred to v2.

## Always-on service

`net-alpha service` is an opt-in launchd-supervised process that hosts the FastAPI app and runs four background jobs:

- **`price_refresh`** — every 4 hours, refreshes quotes for held + targeted tickers.
- **`washsale_watch`** — daily 04:00 + on every manual import. Forward-simulates each PositionTarget and surfaces wash-sale / §1091 risk in the Plan view (deferred vs. `permanent_ira`).
- **`backup`** — daily at 03:30 UTC. Snapshots `~/.net_alpha/` via SQLite online `.backup()`, prunes per retention (14 daily + 10 pre-mutation + 2 GB cap). Manual bundles are never auto-pruned.
- **`verify`** — weekly Sunday 04:30. Audits the UI's cached KPIs against pure-function recomputes; surfaces divergences in the Verify badge.

### Lifecycle

| Command                                        | Effect                                                                                         |
| :--------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| `net-alpha service install`                    | Provision runtime venv, write launchd plist + sandbox profile, (re)load the agent. Idempotent. |
| `net-alpha service start` / `stop` / `restart` | Lifecycle. `stop` survives reboots until `start`.                                              |
| `net-alpha service pause` / `resume`           | Freeze background jobs but keep the dashboard reachable.                                       |
| `net-alpha service status [--json]`            | Health report.                                                                                 |
| `net-alpha service logs [-f]`                  | View / tail the service log.                                                                   |
| `net-alpha service uninstall`                  | Remove plist, sandbox, and runtime venv. **Data at `~/.net_alpha/net_alpha.db` is preserved.** |

The dashboard at `/settings/service` exposes the same controls in a UI surface, plus recent-runs history and a status pill in the site header.

### What `install` does

Everything the running service needs lives inside `~/.net_alpha/`, the only path the sandbox profile allows the service to write to:

- `~/.net_alpha/venv/` — dedicated runtime venv with `wash-alpha` installed from your local project source.
- `~/.net_alpha/bin/net-alpha-wrap` — the launchd wrapper script.
- `~/.net_alpha/run/sandbox.sb` — the sandbox-exec profile applied to the running service.
- `~/Library/LaunchAgents/com.netalpha.service.plist` — the LaunchAgent registration.

> [!IMPORTANT]
> The runtime venv intentionally lives outside `~/Documents/`. Under launchd, the service runs with a TCC identity that cannot read user-data folders, so the project's own `.venv/` is unreadable; `~/.net_alpha/` is TCC-clear.

The runtime venv is a **non-editable snapshot** of your project source at install time. To make the running service reflect new code or `pyproject.toml` changes, re-run `net-alpha service install`. For active development, run `net-alpha …` directly from your editable `.venv` — the LaunchAgent is for the always-on service, not the dev edit-run loop.

## Architecture

```
CSV → BrokerParser → Trade (Pydantic) ──► SQLite (~/.net_alpha/net_alpha.db)
                                              │
                                              ├─► Wash-sale engine  (incremental ±30-day window, deferred + permanent_ira)
                                              ├─► §1256 classifier  (60/40 LT/ST split + year-end MTM)
                                              ├─► §1092 straddle detector
                                              ├─► Reconciliation    (against broker Realized G/L)
                                              └─► Portfolio / planner / pricing  (pure functions)
                                                                │
                                                  ┌─────────────┴─────────────┐
                                                  ▼                           ▼
                                            Typer CLI                 FastAPI + HTMX UI
                                                                              │
                                                                launchd-supervised service
                                                          (price_refresh + washsale_watch + backup + verify)
```

- **Stack** — Python 3.11+, `pydantic` v2, `sqlmodel` over SQLite, `typer` CLI, optional `fastapi` + Jinja + HTMX UI, APScheduler for the service, `ruff`, `pytest`. Managed with `uv`.
- **Storage** — single SQLite DB at `~/.net_alpha/net_alpha.db`; cross-year window detection works because all trades live in one place. Schema versioned via a `meta` table; hand-written `ALTER TABLE` migrations.
- **Engine** — wash-sale recompute is incremental: only the ±30-day window around affected trade dates is recalculated on import or removal. Every emitted violation is reproducible from source trades.
- **Web UI** — optional subpackage at `src/net_alpha/web/`. Calls only existing public seams (`Repository`, engine functions, audit/portfolio/planner pure functions); **no business logic in `web/`**. Static assets vendored — no CDN at runtime, no Node toolchain.

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
