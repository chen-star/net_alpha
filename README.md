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

*Stop flying blind. Detect wash sales across Schwab, Robinhood, options, and ETFs in seconds.*

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

- **🤖 AI-Powered Smart Import:** Claude automatically detects and parses your broker's CSV layout. No more manual column mapping or writing brittle regex parsers.
- **🌐 Cross-Account Intelligence:** Seamlessly match a loss sale on one broker against a repurchase on another in a single pass.
- **🔒 100% Local & Zero-Knowledge:** Your financial data is yours. `net-alpha` runs entirely locally. No cloud uploads, no tracking, no telemetry.
- **🧪 Interactive Sell Simulator:** Planning a trade? Test it against your current holdings and recent buys in real-time using our beautiful terminal UI (TUI).
- **🗣️ Natural Language Agent:** Ask questions about your tax positions using plain English (e.g., *"What is my total realized loss this year across all accounts?"*).

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

### 1. The Interactive Wizard
The fastest way to get started. Just run `net-alpha` without arguments to launch the guided setup.

```bash
net-alpha
```

### 2. Import Your Data
Import your trade history from any broker. Our AI-powered engine will detect the schema automatically.

```bash
net-alpha import schwab 2024_transactions.csv
net-alpha import robinhood rh_2024.csv
```

> [!TIP]  
> **How AI Import Works:** On your first import, Claude analyzes your CSV headers and three *anonymized* sample rows to propose a mapping. Once confirmed, the mapping is cached locally. Future imports of the same format are **100% offline and instantaneous**.

### 3. Scan for Wash Sales
Analyze your entire portfolio across all accounts in milliseconds.

```bash
net-alpha check
```

### 4. Simulate Before You Trade
Use the real-time Terminal UI to simulate a trade, or use the CLI for a quick check.

```bash
# Launch the interactive dashboard
net-alpha tui

# Or use the CLI directly
net-alpha simulate sell TSLA 50 --price 185.50
```

### 5. Generate Tax Reports
Export a tax-ready summary for your accountant or tax software.

```bash
net-alpha report --year 2024
```

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

---

## 🛡️ Disclaimer

> [!IMPORTANT]
> **This tool is for informational purposes only and does not constitute tax or legal advice.**
> Wash sale rules—especially concerning options and ETFs—involve unsettled areas of tax law. Scenarios marked as `Probable` or `Unclear` should always be reviewed with a qualified CPA or tax professional before making filing decisions.

<br>

<div align="center">
  <i>Built with ❤️ for traders who want to take control of their taxes.</i><br>
</div>