# net-alpha

Cross-account wash sale detection for equities, options, and ETFs.

> The only open-source tool that detects wash sales across multiple brokerage accounts — including options and ETFs.

---

## The Problem

When you trade across multiple brokers, each platform only tracks wash sales within its own account. A loss sale on Schwab can be silently neutralized by a repurchase on Robinhood — and you won't find out until February. This problem compounds when you hold options alongside stocks, or ETFs that track the same underlying index.

**net-alpha** solves this by giving you a single, cross-account view of wash sale exposure — before it's too late to act.

---

## Features

- **Universal CSV importer** — Claude AI detects your broker's column layout on first import; confirmed schema is cached for fully-offline subsequent imports
- **Cross-account detection** — scans all imported accounts together in a single pass
- **Equities, options, and ETFs** — covers substantially-identical security matching per IRS Publication 550
- **3-tier confidence labels** — `Confirmed` (red), `Probable` (yellow), `Unclear` (blue) so you know what needs a CPA
- **Adjusted cost basis tracking** — disallowed losses roll into replacement lots automatically
- **Sell simulator** — checks whether a planned sale would trigger a wash sale against recent buys or open positions
- **Safe-to-rebuy tracker** — shows which sold securities are past the 30-day window
- **Local-first** — all trade data stays on your machine; the only remote call is the one-time LLM schema detection

---

## Installation

Requires Python 3.11+ and [`uv`](https://github.com/astral-sh/uv).

```bash
pip install net-alpha
```

Or run from source:

```bash
git clone https://github.com/your-org/net-alpha
cd net-alpha
uv sync
uv run net-alpha
```

---

## Quick Start

```bash
# First run — wizard prompts for API key and creates ~/.net_alpha/
net-alpha

# Import trade history
net-alpha import schwab   schwab_2024.csv
net-alpha import robinhood robinhood_2024.csv

# Check for wash sale violations (all accounts, current year)
net-alpha check

# Narrow the check
net-alpha check --ticker TSLA
net-alpha check --type options
net-alpha check --year 2023

# Simulate a planned sale before you place the order
net-alpha simulate sell TSLA 10
net-alpha simulate sell TSLA 10 --price 185.50

# See which securities are safe to repurchase
net-alpha rebuys

# Generate a report for your accountant
net-alpha report
net-alpha report --year 2024
net-alpha report --year 2024 --csv
```

---

## How CSV Import Works

On the first import of any broker format:

1. Claude reads your CSV headers and three anonymized sample rows (no account numbers, no real dollar amounts)
2. It proposes a column mapping — you confirm or abort before any data is stored
3. The confirmed mapping is cached locally, keyed by broker name and a SHA-256 hash of the header row
4. All subsequent imports of the same format are fully offline

If your broker changes its export format, the next import triggers a new detection and confirmation step automatically.

---

## Wash Sale Detection

**Rule (IRS Publication 550):** A wash sale occurs when you sell a security at a loss and buy the same or substantially identical security within 30 calendar days before or after the sale.

### Equities

| Scenario                                                               | Confidence  |
| ---------------------------------------------------------------------- | ----------- |
| Sold ticker X at a loss, bought ticker X within 30 days in any account | `Confirmed` |

### Options

| Scenario                                                                                         | Confidence  |
| ------------------------------------------------------------------------------------------------ | ----------- |
| Sold option at a loss, bought same option (same strike + expiry) within 30 days                  | `Confirmed` |
| Sold option at a loss, bought option on same underlying (different strike/expiry) within 30 days | `Probable`  |
| Sold stock at a loss, bought call on the same stock within 30 days (IRS Rev. Rul. 2008-5)        | `Probable`  |
| Sold stock at a loss, sold put on the same stock within 30 days                                  | `Unclear`   |

### ETFs

| Scenario                                                                 | Confidence  |
| ------------------------------------------------------------------------ | ----------- |
| Sold ETF at a loss, bought the same ETF ticker                           | `Confirmed` |
| Sold ETF at a loss, bought ETF tracking the same index (e.g., SPY → VOO) | `Unclear`   |

**Built-in substantially-identical ETF pairs:**

| Category     | Tickers             |
| ------------ | ------------------- |
| S&P 500      | SPY, VOO, IVV, SPLG |
| Nasdaq-100   | QQQ, QQQM           |
| Russell 2000 | IWM, VTWO           |
| Gold         | GLD, IAU            |

Add your own pairs in `~/.net_alpha/etf_pairs.yaml` — your file extends the defaults, never replaces them.

---

## Data & Privacy

- All trade data is stored in `~/.net_alpha/net_alpha.db` (SQLite)
- The only outbound network call is the one-time LLM schema detection per broker format
- No telemetry, no remote storage, no account sync
- Requires `ANTHROPIC_API_KEY` for schema detection only — set via environment variable or prompted on first run

---

## Configuration

| Location                      | Purpose                                  |
| ----------------------------- | ---------------------------------------- |
| `~/.net_alpha/config.toml`    | API key, user preferences                |
| `~/.net_alpha/etf_pairs.yaml` | Custom substantially-identical ETF pairs |
| `~/.net_alpha/net_alpha.db`   | All imported trade data (SQLite)         |

---

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest
# or
make test

# Run linter and formatter
uv run ruff check .
uv run ruff format .
# or
make lint

# Run a single test file
uv run pytest tests/path/to/test_file.py

# Run tests matching a pattern
uv run pytest -k "test_wash_sale"
```

### Tech Stack

| Layer       | Library                              |
| ----------- | ------------------------------------ |
| CLI         | `typer[all]` (includes `rich`)       |
| Prompts     | `questionary`                        |
| Data models | `pydantic` v2                        |
| Storage     | `sqlmodel` over SQLite               |
| LLM         | `anthropic` SDK (`claude-haiku-4-5`) |
| Config      | `pydantic-settings`                  |
| Logging     | `loguru`                             |
| Lint/format | `ruff`                               |
| Tests       | `pytest`, `factory_boy`              |

### Testing

- Wash sale engine has 100% unit test coverage with pure functions and no mocks
- LLM schema detection tests mock the Anthropic client and cover retry logic, caching, and error paths
- Integration tests use anonymized broker CSV fixtures and verify end-to-end `Trade` output

---

## Supported Brokers

| Broker     | Method             | Status                                  |
| ---------- | ------------------ | --------------------------------------- |
| Schwab     | CSV (LLM-parsed)   | Supported                               |
| Robinhood  | CSV (LLM-parsed)   | Supported                               |
| Any broker | CSV (LLM-parsed)   | Works; community-tested formats welcome |
| Schwab     | Official OAuth API | Planned (v2)                            |
| Robinhood  | robin_stocks       | Planned (v2)                            |

---

## Roadmap (v2)

- Schwab OAuth API integration — no more manual CSV downloads
- Tax-loss harvest scanner — find unrealized losses worth taking before year-end
- Replacement security suggester — correlated-but-not-identical alternatives
- Optional local web dashboard (`net-alpha serve`)

---

## Disclaimer

> **This tool is informational only. It does not constitute tax or legal advice. Consult a qualified tax professional before making filing decisions.**

Wash sale rules — especially for options and ETFs — involve unsettled areas of tax law. `Probable` and `Unclear` results should always be reviewed with a CPA.

---

## License

MIT
