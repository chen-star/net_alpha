# net-alpha

```text
  _   _  _____ _____         ___   _     ____  _   _    _    
 | \ | || ____|_   _|       / _ \ | |   |  _ \| | | |  / \   
 |  \| ||  _|   | |   _____| |_| || |   | |_) | |_| | / _ \  
 | |\  || |___  | |  |_____|  _  || |___|  __/|  _  |/ ___ \ 
 |_| \_||_____| |_|        |_| |_||_____|_|   |_| |_/_/   \_\
```

> **The only open-source tool that detects wash sales across multiple brokerage accounts — including options and ETFs.**

---

### 🤖 AI-Powered Import
Claude automatically detects your broker's CSV layout. No more manual column mapping or broken parsers.

### 🌐 Cross-Account View
Matches a Schwab loss sale against a Robinhood repurchase in a single pass. Total visibility across your portfolio.

### 🔒 100% Local & Private
Your trade data never leaves your machine. No cloud, no tracking, no telemetry. Zero-knowledge by design.

---

[![CI](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml/badge.svg)](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/wash-alpha.svg)](https://pypi.org/project/wash-alpha/)
[![codecov](https://codecov.io/github/chen-star/net_alpha/graph/badge.svg?token=XETFUGJO3L)](https://codecov.io/github/chen-star/net_alpha)

## The Problem

When you trade across multiple brokers, each platform only tracks wash sales within its own account. A loss sale on Schwab can be silently neutralized by a repurchase on Robinhood — and you won't find out until February. This problem compounds when you hold options alongside stocks, or ETFs that track the same underlying index.

**net-alpha** solves this by giving you a single, cross-account view of wash sale exposure — before it's too late to act.

---

## The Workflow

Get from raw CSVs to a tax-ready report in seconds.

### 1. 📂 Smart Import
Claude detects your broker's schema. Confirm once, and it's cached forever for fully offline subsequent imports.

```bash
net-alpha import schwab   schwab_2024.csv
net-alpha import robinhood rh_2024.csv
```

### 2. 🔍 Cross-Account Check
Scan all accounts together. `net-alpha` detects wash sales across different brokers, assets (Equities/Options/ETFs), and dates.

```bash
net-alpha check
```

### 3. 🧪 Sell Simulator
Planning a trade? Test it against your current holdings and recent buys before you place the order.

```bash
net-alpha simulate sell TSLA 10 --price 185.50
```

### 4. 📄 Tax-Ready Reporting
Generate a summary for your accountant or tax software with adjusted cost basis tracking.

```bash
net-alpha report --year 2024
```

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

## Under the Hood

### 🛡️ Zero-Knowledge Privacy
We believe your financial data is your business.
- **Local-First:** All trades are stored in a local SQLite database (`~/.net_alpha/net_alpha.db`).
- **Anonymized AI:** For schema detection, we only send CSV headers and 3 fake, anonymized sample rows to Claude. No account numbers, no real dollar amounts.
- **Offline Core:** Once a schema is mapped, the entire detection engine runs 100% offline.

### 🛠️ Modern Tech Stack
Built with the latest Python ecosystem for speed and reliability:
- **Python 3.11+** with strict Pydantic v2 typing.
- **Typer & Rich** for a premium, color-coded terminal UX.
- **SQLModel** (Pydantic + SQLAlchemy) for local relational storage.
- **uv** for ultra-fast, reproducible builds.

### ⚙️ Extensibility
Add your own substantially-identical security pairs (e.g., custom ETF pairs) in `~/.net_alpha/etf_pairs.yaml`.

```yaml
# Example: Custom ETF matching
- SPY, VOO, IVV, SPLG
- QQQ, QQQM
```

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
