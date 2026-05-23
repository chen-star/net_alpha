<div align="center">

<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/logo.svg" alt="net-alpha" width="440">

**Cross-account wash sale detection for stocks, options, and ETFs — local-first, IRS Pub 550, with a tax-harvest planner and pre-trade simulator.**

[![CI](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml/badge.svg)](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wash-alpha.svg?label=PyPI)](https://pypi.org/project/wash-alpha/)
[![Downloads](https://static.pepy.tech/badge/wash-alpha)](https://pepy.tech/project/wash-alpha)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Coverage](https://codecov.io/github/chen-star/net_alpha/graph/badge.svg?token=XETFUGJO3L)](https://codecov.io/github/chen-star/net_alpha)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)

[Why](#why-net-alpha) · [Quickstart](#quickstart) · [Features](#features) · [Usage](#usage) · [IRS Rules](#how-the-rules-work) · [Service](#always-on-service) · [Architecture](#architecture) · [Development](#development)

</div>

---

## Why net-alpha

Every brokerage tracks wash sales only **within its own ecosystem**. A loss sale on Schwab can be silently neutralized by a repurchase on Fidelity — and you won't know until well after tax season, long after the 30-day window to act has closed. The problem compounds when you trade **options alongside the underlying**, or hold **ETFs that track the same index** in separate accounts.

**net-alpha** gives you a single, unified view of your wash sale exposure across every account, asset class, and tax year — _before_ it's too late to act.

> [!NOTE]
> The package is published to PyPI as **`wash-alpha`** but the CLI command is **`net-alpha`**. Both names refer to the same project.

---

## See it in action

> All screenshots use the built-in demo dataset: TSLA, NVDA, AAPL, SPY puts, an SPX §1256 call, plus open holdings (MSFT, AMZN, GOOGL, META, AMD, VOO). Pick **"Try the demo"** on the welcome screen — or run `net-alpha ui --demo`.

**Wash-sale ledger** — every match across accounts, with confidence label and rule citation. The NVDA row is the case no single broker would flag: a loss closed in `schwab/taxable` silently neutralized by a buy in `schwab/ira` 14 days later, shown as a `Cross-account` source pill. SPY shows an exact-strike options match with a `-8d` lag because the replacement leg opened _before_ the loss close.

<p align="center">
<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/screenshots/wash-sales.png" alt="Wash-sale ledger across accounts" width="900">
</p>

**Per-symbol drilldown** — NVDA's timeline combines lots from both accounts in one view. KPIs (open lots, realized P/L vs. broker, disallowed loss, last trade) sit above; every row deep-links to the source trade so the chain stays auditable.

<p align="center">
<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/screenshots/ticker-nvda.png" alt="NVDA per-symbol drilldown" width="900">
</p>

**Pre-trade simulator** — propose `Sell 20 AAPL @ market` and see realized P&L, FIFO lot consumption, and per-account wash-sale verdict _before_ placing the order. The lot-strategy table compares FIFO / LIFO / HIFO / MIN\_TAX / MAX\_LOSS side-by-side with each strategy's after-tax P&L and wash-sale verdict.

<p align="center">
<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/screenshots/sim.png" alt="Pre-trade simulator with lot-strategy comparison" width="900">
</p>

**Portfolio dashboard** — KPIs, equity curve with brush-strip drag-to-reperiod, cash-deployment stacked-area chart, monthly P/L bars, allocation donut, top movers, and wash-sale watch — all accounts in one view. Tiles are drag-to-reorder and hideable via the "Edit layout" toolbar.

<p align="center">
<img src="https://raw.githubusercontent.com/chen-star/net_alpha/master/assets/screenshots/portfolio.png" alt="Portfolio dashboard" width="900">
</p>

---

## Quickstart

**Requires Python 3.11+** and [`uv`](https://docs.astral.sh/uv/).

### Web UI (recommended)

```bash
# Install with web UI support
uv tool install 'wash-alpha[ui]'

# (Optional) Install the always-on background service
net-alpha service install

# Open the dashboard — browser launches automatically
net-alpha ui
```

The UI runs at `http://127.0.0.1:18765` (auto-picks the next free port in 18765–18775). With the service installed, prices refresh every 4 hours, forward-looking wash-sale checks run daily, and a snapshot backup runs at 03:30 UTC. Without it, `net-alpha ui` runs ephemerally until Ctrl-C.

> [!TIP]
> First run? Pick **"Try the demo"** on the welcome screen for a guided tour — no CSV required. Replay any time from `/tour`.

### CLI (no UI extras)

```bash
uv tool install wash-alpha
net-alpha schwab.csv --account personal --detail
```

---

## Features

### Detection

| Capability | Coverage |
| :--- | :--- |
| **Cross-account wash sales** | Match a loss sale on one broker against a repurchase on another in a single pass |
| **§1091 — equities, options, ETFs** | Exact ticker, exact contract, same-underlying option, or same-index ETF pair |
| **Rev. Rul. 2008-5 IRA traps** | Taxable-account loss replaced by IRA/Roth/401(k)/HSA buy → permanently disallowed, no basis rollover possible |
| **§1256 contracts** | SPX, NDX, RUT, VIX, OEX, XSP… exempt from §1091, 60/40 LT/ST split, year-end MTM |
| **§1092 straddles** | Literal straddles, married puts, non-qualified covered calls, vertical spreads |
| **ETF substantially-identical pairs** | Bundled index-tracking groups (S&P 500, Nasdaq-100, Russell 2000…); extend at `~/.net_alpha/etf_pairs.yaml` |

Every match carries a **Confirmed / Probable / Unclear** confidence label with rule citation and inline explanation.

### Planning

- **Pre-trade simulator** — `/sim` shows lot consumption, realized P&L, and wash-sale verdict _before_ you execute. Suggestion chips surface the largest unrealized loss, wash-sale risk, and largest gain for one-click sims.
- **Lot-selection strategies** — compare FIFO / LIFO / HIFO / MIN\_TAX / MAX\_LOSS side-by-side on any Sell sim, each with its own independent wash-sale verdict.
- **Tax-harvest planner** — `/tax/harvest/plan` builds a ranked, editable harvest plan (greedy by tax saved, capped by §1211's $3,000 ordinary-loss limit). Honors user-declared PositionTargets so it never closes a position you want to keep.
- **Forward-looking watchlist** — the always-on service forward-simulates every PositionTarget daily, surfacing deferred vs. permanent IRA-trap risk as colored pills on the Plan view.
- **Action Inbox** — urgent items (imminent wash-sale tripwires, §1092 holding-period suspensions, broken reconciliation, missing basis) in one panel.
- **Verify** — a global "Data check" badge in the site header that audits live KPIs against pure-function recomputes and one-click jumps to any divergence.

### Reporting

- **After-tax performance** — realized P&L after estimated taxes, with tax-drag breakdown and ST/LT/§1256 mix bar.
- **Capital-loss carryforward** — auto-derived from prior years honoring §1212(b) cross-category netting and §1211 $3K cap, with hand-editable overrides.
- **Auditable explanations** — every wash-sale flag includes rule citation, source trades, match reason, math, and confidence reasoning — inline in the UI or via `--detail` on the CLI.
- **Per-symbol reconciliation** — cross-checks computed P&L against your broker's Realized G/L file (Schwab supported).
- **Data hygiene rollup** — Imports page groups missing-basis / no-quote / missing-date rows so you can fix them in one pass.

### Local & Private

> [!IMPORTANT]
> Your trade data, account information, and P&L **never leave your machine**. Only ticker symbols are sent to Yahoo Finance for live quotes — and that can be disabled with `prices.enable_remote: false` in `~/.net_alpha/config.yaml`.

- **Zero-knowledge, zero telemetry** — everything runs on your local SQLite database at `~/.net_alpha/net_alpha.db`.
- **No CDN at runtime, no Node toolchain** — htmx, Alpine.js, ApexCharts, Lucide icons, and fonts are fully vendored under `web/static/`.
- **WAL-safe backups with optional encryption** — `net-alpha backup` snapshots via SQLite's online `.backup()` API (safe while the service writes), with optional AES-256-GCM encryption. Daily automated snapshots + inline pre-mutation backups before every import or removal.
- **Manual trade CRUD** — add, edit, transfer, or delete trades from the web UI; wash sales recompute over the affected window automatically.

---

## Usage

### Web UI

```bash
net-alpha ui [--port 18765] [--no-browser] [--reload]
```

| Page | Highlights |
| :--- | :--- |
| `/` Portfolio | KPIs, equity curve (brush-strip, click-to-explain daily drivers, optional SPY benchmark), cash-deployment area chart, monthly P/L bars, allocation donut, top movers, wash-sale watch, drag-to-reorder layout |
| `/positions` | All / stocks / options / at-loss / closed views; drag-to-reorder Plan view; multi-lot basis editor; per-row side pane with lot ladder, ST→LT clock, and wash-sale outlook |
| `/sim` | Pre-trade simulator, suggestion chips, FIFO/LIFO/HIFO/MIN\_TAX/MAX\_LOSS strategy comparison |
| `/tax` | After-tax performance, harvest queue, plan-builder, projection setup, wash-sale + exempt-match listings |
| `/imports` | Drop-zone upload (trades or positions CSV), preview/commit, per-import detail, data-hygiene buckets |
| `/ticker/{symbol}` | Per-symbol timeline, lot ladder, reconciliation vs. broker, lot edit and add-trade forms |
| `/verify` | Findings table (BasisRecon, RealizedRecon, StaleReference…) with inline "Why?" explainer and one-click suppress |
| `/settings` | Profile, density, ETF pairs, carryforward, account types, backups, service controls, about |

### CLI

```bash
# Import a CSV → recompute wash sales → print watchlist + YTD impact
net-alpha schwab.csv --account personal [--detail]

# Pre-trade simulation across every account holding the ticker
net-alpha sim TSLA 10 --price 180

# §1092 straddles currently open
net-alpha straddles [--detail]

# Manage past imports (recomputes wash sales on removal)
net-alpha imports
net-alpha imports rm 3 --yes

# Backups — manual snapshot, list all bundles, restore
net-alpha backup [--encrypt] [--note "before tax-day cleanup"]
net-alpha backups
net-alpha restore <bundle-id> --yes

# v1 → v2 schema migration (v2.0.x line only)
net-alpha migrate-from-v1 --yes
```

### Supported Brokers

| Broker | Trade import | Realized G/L reconciliation |
| :--- | :---: | :---: |
| **Schwab** (transactions CSV + Realized G/L CSV) | ✅ | ✅ |
| Additional brokers | planned | planned |

To add a broker: implement the `BrokerParser` protocol at `src/net_alpha/brokers/<name>.py`, register it in `brokers/registry.py`, and optionally add a Realized G/L parser at `src/net_alpha/audit/brokers/`.

---

## How the Rules Work

`net-alpha` strictly follows [IRS Publication 550](https://www.irs.gov/publications/p550). A wash sale is triggered when you sell at a loss and buy a substantially identical security within 30 days before or after the sale.

### Confidence labels

| Label | Meaning |
| :--- | :--- |
| 🟥 **Confirmed** | Definite wash sale under IRS Pub 550 |
| 🟨 **Probable** | Likely; CPA review recommended before filing |
| 🟦 **Unclear** | Ambiguous; flag for professional review |

### §1091 — equities, options, ETFs

| Scenario | Confidence |
| :--- | :--- |
| Sold ticker X at a loss → bought ticker X within 30 days | 🟥 Confirmed |
| Sold option at a loss → bought same option (exact strike + expiry) | 🟥 Confirmed |
| Sold option at a loss → bought option on the same underlying | 🟨 Probable |
| Sold ETF at a loss → bought the same ETF ticker | 🟥 Confirmed |
| Sold ETF at a loss → bought ETF tracking the same index (e.g., SPY → VOO) | 🟦 Unclear |

### §1256 contracts

Broad-based equity index options (SPX, NDX, RUT, VIX, OEX, XSP, …) are **exempt from §1091**. Their closed P&L is split 60/40 long-term/short-term per §1256(a)(3), regardless of holding period. Open positions at year-end are **marked-to-market** per §1256(a)(1), with FMV sourced via a cascade: Yahoo option close → Black-Scholes (underlying close + 30-day historical vol) → intrinsic if expired.

### IRA-trap violations — Rev. Rul. 2008-5

When a loss in a **taxable** account is replaced by a substantially-identical buy in a **tax-advantaged** account (IRA / Roth / 401(k) / HSA) within ±30 days, §1091(a) still disallows the loss, but §1091(d)'s basis rollover cannot apply — the loss is **permanently lost**. These are classified as `permanent_ira` violations, distinct from `deferred` wash sales where the basis rolls into the replacement lot.

### §1092 straddles

Same-underlying offsetting positions caught by IRC §1092:

- **Literal straddles** — long call + long put on the same underlying
- **Married puts** — long stock + long put on the same underlying
- **Non-qualified covered calls** — long stock + short call that fails the §1092(c)(4) QCC test
- **Vertical spreads** — long + short option of the same series, opposite legs

> [!NOTE]
> The QCC test is a conservative approximation of IRS Notice 2003-31 — it errs on the side of flagging deeper-ITM calls. Loss-deferral computation, the §1092(b) modified wash-sale rule, and identified-straddle elections are deferred to a future release.

---

## Always-on Service

`net-alpha service` is an opt-in launchd-supervised process that hosts the FastAPI app and runs four background jobs:

| Job | Schedule | What it does |
| :--- | :--- | :--- |
| `price_refresh` | Every 4 hours | Refreshes quotes for all held and targeted tickers |
| `washsale_watch` | Daily 04:00 + on every import | Forward-simulates PositionTargets and surfaces §1091 risk pills on the Plan view |
| `backup` | Daily 03:30 UTC | WAL-safe snapshot of `~/.net_alpha/`; prunes to 14 daily + 10 pre-mutation + 2 GB cap |
| `verify` | Weekly Sunday 04:30 | Audits live KPIs against pure-function recomputes; surfaces divergences in the Verify badge |

### Lifecycle commands

| Command | Effect |
| :--- | :--- |
| `net-alpha service install` | Provision runtime venv, write launchd plist + sandbox profile, load the agent. Idempotent. |
| `net-alpha service start` / `stop` / `restart` | Lifecycle control. `stop` survives reboots until `start`. |
| `net-alpha service pause` / `resume` | Freeze background jobs while keeping the dashboard reachable. |
| `net-alpha service status [--json]` | Health report. |
| `net-alpha service logs [-f]` | View or tail the service log. |
| `net-alpha service uninstall` | Remove plist, sandbox, and runtime venv. **Data at `~/.net_alpha/net_alpha.db` is preserved.** |

The `/settings/service` page exposes the same controls in the UI, plus a recent-runs history and a live status pill in the site header.

> [!IMPORTANT]
> The runtime venv lives at `~/.net_alpha/venv/` — outside `~/Documents/` so launchd's TCC identity can reach it. To make the running service reflect code changes, re-run `net-alpha service install`. For active development, run `net-alpha …` directly from your editable `.venv`.

---

## Architecture

```
CSV → BrokerParser → Trade (Pydantic) ──► SQLite (~/.net_alpha/net_alpha.db)
                                              │
                                              ├─► Wash-sale engine  (incremental ±30-day window, deferred + permanent_ira)
                                              ├─► §1256 classifier  (60/40 LT/ST split + year-end MTM)
                                              ├─► §1092 straddle detector
                                              ├─► Reconciliation    (vs. broker Realized G/L)
                                              └─► Portfolio / planner / pricing  (pure functions)
                                                                │
                                                  ┌─────────────┴─────────────┐
                                                  ▼                           ▼
                                            Typer CLI                 FastAPI + HTMX UI
                                                                              │
                                                                launchd-supervised service
                                                          (price_refresh · washsale_watch · backup · verify)
```

| Layer | Technology |
| :--- | :--- |
| Language | Python 3.11+ |
| Package management | `uv` |
| Data models | `pydantic` v2 |
| ORM / storage | `sqlmodel` over SQLite |
| CLI | `typer[all]` |
| Web framework | `fastapi` + Jinja2 (optional) |
| Frontend | HTMX, Alpine.js, ApexCharts, SortableJS (all vendored) |
| Styling | Tailwind CSS + Lucide icons (vendored) |
| Background jobs | APScheduler |
| Encryption | `cryptography` AES-256-GCM |
| Linting / formatting | `ruff` |
| Testing | `pytest` + `factory-boy` |

**Key design decisions:**

- **Incremental recompute** — only the ±30-day window around affected trade dates is recalculated on import or removal; no full-table scans.
- **Single SQLite DB** — all trades, all years, all accounts in one file enables cross-year window detection without joins across files.
- **Pure engine functions** — wash-sale logic is fully decoupled from storage and UI; every emitted violation is reproducible from source trades alone.
- **No business logic in `web/`** — the web layer calls existing public seams only (`Repository`, engine functions, audit/portfolio/planner pure functions).
- **Schema versioning** — hand-written `ALTER TABLE` migrations tracked via a `meta` table; currently at v26.

---

## Development

```bash
# Clone and install everything
git clone https://github.com/chen-star/net_alpha.git
cd net_alpha
uv sync --extra ui --extra dev

# Run tests
uv run pytest                            # full suite
uv run pytest tests/engine/             # by directory
uv run pytest -k "test_wash_sale"       # by pattern

# Lint and format
uv run ruff check .
uv run ruff format .

# Rebuild frontend assets (optional)
make build-css                           # Tailwind bundle
make vendor-lucide                       # Lucide icons
make vendor-apex                         # ApexCharts
```

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for the full setup guide, [`docs/TESTING.md`](docs/TESTING.md) for coverage thresholds and Playwright snapshot tests, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a deeper dive into the component model.

---

## Disclaimer

> [!IMPORTANT]
> **This tool is for informational purposes only and does not constitute tax or legal advice.**
> Wash sale rules — especially around options and ETFs — involve unsettled areas of tax law. Any match labeled **Probable** or **Unclear** should be reviewed with a qualified CPA before making filing decisions.

<br>

<div align="center">

<sub>If <code>net-alpha</code> saves you a CPA call this tax season, consider <a href="https://github.com/chen-star/net_alpha">starring the repo</a> — it's the best signal for other traders looking for a tool they can trust with their tax data.</sub>

</div>
