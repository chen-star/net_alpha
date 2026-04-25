<div align="center">

```text
  _   _  _____ _____         ___   _     ____  _   _    _    
 | \ | || ____|_   _|       / _ \ | |   |  _ \| | | |  / \   
 |  \| ||  _|   | |   _____| |_| || |   | |_) | |_| | / _ \  
 | |\  || |___  | |  |_____|  _  || |___|  __/|  _  |/ ___ \ 
 |_| \_||_____| |_|        |_| |_||_____|_|   |_| |_/_/   \_\
```

**The definitive open-source engine for cross-account wash sale detection.**

[![CI](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml/badge.svg)](https://github.com/chen-star/net_alpha/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/wash-alpha.svg)](https://pypi.org/project/wash-alpha/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![codecov](https://codecov.io/github/chen-star/net_alpha/graph/badge.svg?token=XETFUGJO3L)](https://codecov.io/github/chen-star/net_alpha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*Stop flying blind. Detect wash sales across accounts, options, and ETFs in seconds.*

[Installation](#-installation) •
[Features](#-key-features) •
[Usage](#-usage) •
[How it Works](#-how-the-rules-work)

</div>

---

## ⚡ The Problem

When you trade across multiple brokerages, each platform only tracks wash sales **within its own ecosystem**. A loss sale on Schwab can be silently neutralized by a repurchase on Robinhood, and you won't find out until tax season.

The problem compounds when you trade **options** alongside stocks, or **ETFs** that track the same underlying index.

**net-alpha** solves this by providing a single, unified view of your wash sale exposure—*before* it's too late to act.

---

## 🌟 Key Features

- **📂 Bundled Broker Parsers:** Schwab CSV is supported out of the box. Other brokers can be added by contributing a parser — no configuration needed for supported formats.
- **🌐 Cross-Account Intelligence:** Seamlessly match a loss sale on one broker against a repurchase on another in a single pass.
- **🔒 100% Local & Zero-Knowledge:** Your financial data is yours. `net-alpha` runs entirely locally. No cloud uploads, no tracking, no telemetry.
- **🧪 Pre-Trade Simulation:** Planning a trade? Run `net-alpha sim` to see FIFO lot consumption, realized P&L, and a cross-account wash-sale verdict before you execute.

---

## 🚀 Installation

`net-alpha` requires Python 3.11 or higher. We recommend using [`uv`](https://github.com/astral-sh/uv) for lightning-fast installation.

```bash
pip install wash-alpha
```

> [!NOTE]
> While the package is named `wash-alpha` on PyPI, the CLI command is `net-alpha`.

---

## 💻 Usage

### Import + check (the only command you usually run)

```bash
net-alpha schwab.csv --account personal
```

This imports the CSV, recomputes wash sales over the affected window, and prints a watch list plus a year-to-date impact summary. Add `--detail` for a per-violation breakdown.

### Pre-trade simulation

```bash
net-alpha sim TSLA 10 --price 180
```

Lists every account that holds the ticker, with FIFO lot consumption, realized P&L, and a cross-account wash-sale verdict per account.

### Manage past imports

```bash
net-alpha imports                # list
net-alpha imports rm 3 --yes     # remove an import (recomputes wash sales)
```

### Migrate from v0.x

```bash
net-alpha migrate-from-v1 --yes
```

Reads `~/.net_alpha/net_alpha.db` (v1 schema) and writes a fresh v2 DB at `~/.net_alpha/net_alpha.db.v2`. This helper exists only in the v2.0.x line.

---

## 🧠 How the Rules Work

**net-alpha** strictly follows IRS Publication 550. A wash sale is triggered when you sell a security at a loss and buy a *"substantially identical"* security within 30 days before or after the sale.

| Asset Type | Scenario | Confidence |
| :--- | :--- | :--- |
| **Equities** | Sold ticker `X` at a loss, bought ticker `X` within 30 days. | 🟢 **Confirmed** |
| **Options** | Sold option at a loss, bought same option (exact strike + expiry). | 🟢 **Confirmed** |
| **Options** | Sold option at a loss, bought option on the same underlying. | 🟡 **Probable** |
| **ETFs** | Sold ETF at a loss, bought the exact same ETF ticker. | 🟢 **Confirmed** |
| **ETFs** | Sold ETF at a loss, bought ETF tracking the same index (e.g., `SPY` → `VOO`). | 🟠 **Unclear** |

> **Custom ETF Matching:** You can easily add your own "substantially identical" security pairs (like custom ETFs) by editing `~/.net_alpha/etf_pairs.yaml`.

**Supported brokers (v2.0):** Schwab.

Other brokers can be added by contributing a parser at `src/net_alpha/brokers/<name>.py` — implement the `BrokerParser` Protocol and register it in `brokers/registry.py`.

---

## 🛡️ Disclaimer

> [!IMPORTANT]
> **This tool is for informational purposes only and does not constitute tax or legal advice.**
> Wash sale rules—especially concerning options and ETFs—involve unsettled areas of tax law. Scenarios marked as `Probable` or `Unclear` should always be reviewed with a qualified CPA or tax professional before making filing decisions.

<br>

<div align="center">
  <i>Built with ❤️ for traders who want to take control of their taxes.</i><br>
</div>