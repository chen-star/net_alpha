# net_alpha — Product Requirements Document

**Version:** 0.2.0
**Date:** 2026-04-12  
**Status:** Approved  

---

## 1. Problem Statement

Active retail traders who operate across multiple brokerage accounts have no reliable, open-source tool to detect and prevent IRS wash sale violations in real time. Existing broker platforms only track wash sales within their own account — meaning a loss sale on Schwab can be silently neutralized by a repurchase on Robinhood, resulting in unexpected tax liability discovered only at year-end.

**The core pain:** A trader who thinks they harvested a $5,000 loss may owe taxes on $0 of actual deductible loss — and not find out until February.

This problem is compounded when the trader holds options or ETFs alongside equities: a stock loss can be negated by an option purchase on the same underlying, or an ETF sale can be matched against a purchase of a substantially identical fund — rules that brokers do not cross-track.

---

## 2. Goal

Build an open-source, local-first Python tool that gives self-directed traders a single, cross-account view of wash sale exposure across equities, options, and ETFs — before it's too late to act.

**One-line pitch:**  
*"The only open-source tool that detects wash sales across multiple brokerage accounts — including options and ETFs."*

---

## 3. Target Users

**Primary:** Self-directed retail traders with 2+ brokerage accounts (e.g., Schwab + Robinhood), who:
- Trade equities, options, and/or ETFs actively (10–500 trades/year)
- Are tax-aware and practice or want to practice tax-loss harvesting
- Have some technical comfort (can run a CLI tool, manage API keys)

**Secondary:** Developer-traders who want to integrate wash sale logic into their own portfolio tooling.

**Not targeted (v1):** Professional traders, institutional accounts, non-US investors.

---

## 4. Success Metrics

| Metric | Target |
|---|---|
| GitHub Stars (6 months post-launch) | 300+ |
| Supported brokers at launch | 2 (Schwab, Robinhood) |
| Brokers supported via CSV (any format) | Unlimited via LLM parser |
| False positive rate on wash sale detection | < 5% |
| Time to first wash sale report (new user) | < 5 minutes |

---

## 5. Core Features

### F1 — Universal CSV Importer (LLM-powered)
Import trade history from any broker CSV without hard-coded column mappings.

- Use Claude API to detect CSV schema on first import (one-time per file format)
- **Show detected schema to user for confirmation before any data is stored**
- Cache confirmed schema mapping locally — subsequent imports are fully offline
- Support equities, options, and ETF rows in the same file
- Graceful handling of missing optional columns (proceeds, cost basis)

**Rationale:** Hard-coded CSV parsers break when brokers change column names. LLM-based schema detection makes the importer resilient and infinitely extensible. Schema confirmation before import builds user trust and catches LLM errors.

### F2 — Cross-Account Wash Sale Detector
Identify IRS wash sale violations across all imported accounts, covering equities, options, and ETFs.

- 30-day look-back and look-forward window (calendar days, per IRS Publication 550)
- **Equities:** Exact ticker match across all accounts
- **Options:** Match loss sale against purchase of option on same underlying within window; flag stock purchase on same underlying as potential wash sale with disclaimer
- **ETFs:** Flag purchases of ETFs with same underlying index (e.g., SPY → VOO) as *potential* wash sales with note that IRS has not issued definitive guidance
- Report: which trades triggered the violation, which account each was in, disallowed loss amount
- Flag open potential violations (triggering trade within look-forward window still possible)

### F3 — Adjusted Cost Basis Tracker
Track how disallowed losses roll into the cost basis of replacement shares/contracts.

- Per-lot adjusted basis after wash sale adjustments
- Running total of disallowed losses YTD
- Export adjusted basis report as CSV for tax filing reference

### F4 — CLI & TUI Interface
Clean, fast command-line interface as the primary UX, supplemented by a real-time interactive simulation dashboard (TUI).

```bash
net-alpha
net-alpha tui
net-alpha import schwab trades_2024.csv
net-alpha import robinhood trades_2024.csv
net-alpha check
net-alpha check --ticker TSLA
net-alpha check --type options
net-alpha simulate sell TSLA 10
net-alpha rebuys
net-alpha report --year 2024
```

---

## 6. Non-Goals (v1)

- **No web UI** — Local-first CLI only. Reduces security surface, removes hosting cost, builds trust with traders who won't give a random web app their account data.
- **No real-time brokerage sync** — Users import CSV manually. Live API integration is v2.
- **No tax filing integration** — This tool informs the user; it does not generate tax forms.
- **No financial advice** — All output carries disclaimer that this is informational only.
- **No mutual funds** — Out of scope; mutual fund wash sale rules involve additional complexity.

---

## 7. Options & ETF Wash Sale — Design Detail

This is the technically and legally complex part of v1. We cover it with a tiered confidence model:

### Options
| Scenario | Treatment | Confidence Label |
|---|---|---|
| Sold option at loss, bought same option (same strike/expiry) within 30d | Definite wash sale | `Confirmed` |
| Sold option at loss, bought option on same underlying (different strike/expiry) | Probable wash sale | `Probable` |
| Sold stock at loss, bought call option on same stock within 30d | Probable wash sale (IRS Rev. Rul. 2008-5) | `Probable` |
| Sold stock at loss, sold put option on same stock within 30d | Gray area | `Unclear` |

### ETFs
| Scenario | Treatment | Confidence Label |
|---|---|---|
| Sold ETF at loss, bought same ETF ticker | Definite wash sale | `Confirmed` |
| Sold ETF at loss, bought ETF with same underlying index (known pairs) | Potential wash sale, IRS guidance unclear | `Unclear` |
| Sold ETF at loss, bought constituent stock | Not a wash sale | — |

**Known substantially-identical ETF pairs (maintained list):**
- SPY / VOO / IVV / SPLG (S&P 500)
- QQQ / QQQM (Nasdaq-100)
- IWM / VTWO (Russell 2000)
- GLD / IAU (Gold)
- (Extensible via config file)

All `Probable` and `Unclear` results include prominent disclaimer recommending CPA consultation.

---

## 8. Technical Requirements

### Architecture
- **Language:** Python 3.11+
- **CLI framework:** Typer
- **Data models:** Pydantic v2
- **LLM integration:** Anthropic Claude API (`claude-3-5-haiku-latest` for cost efficiency on schema detection)
- **Local storage:** SQLite via SQLModel (portable, zero-infrastructure)
- **Packaging:** `pyproject.toml`, installable via `pip install net-alpha`

### Data Privacy
- All trade data stored locally in `~/.net_alpha/`
- Only CSV headers + anonymized sample rows sent to LLM for schema detection (no account numbers, no real dollar amounts)
- Schema cache stored locally; LLM not called again for same broker format after confirmation
- No telemetry, no remote calls except the one-time LLM schema detection

### Broker Support
| Broker | Method | Version |
|---|---|---|
| Schwab | CSV (LLM-parsed) | v1 |
| Robinhood | CSV (LLM-parsed) | v1 |
| Any broker | CSV (LLM-parsed) | v1 (untested, community-contributed) |
| Schwab | Official API (OAuth) | v2 |
| Robinhood | robin_stocks (unofficial) | v2 |

---

## 9. User Flow — Happy Path

```
1. User downloads CSV from Schwab (Accounts > History > Export)
2. User downloads CSV from Robinhood (Account > Statements > Export)

3. net-alpha import schwab schwab_2024.csv
   → LLM detects schema from headers + 3 anonymized sample rows
   → Displays detected mapping for user confirmation:
       date       → "Date"
       ticker     → "Symbol"
       action     → "Action"  [buy values: Buy | Reinvest]  [sell values: Sell]
       quantity   → "Quantity"
       proceeds   → "Amount"
   → User confirms (y/n)
   → "Imported 847 trades from Schwab (612 equities, 198 options, 37 ETFs)"

4. net-alpha import robinhood rh_2024.csv
   → Schema cached from prior Schwab import if same format, else new LLM call
   → "Imported 312 trades from Robinhood"

5. net-alpha check
   → Scans all trades across both accounts
   → Reports violations and warnings with confidence labels

6. net-alpha report --year 2024
   → Exports summary CSV for accountant/tax software
```

---

## 10. Wash Sale Detection Logic

**Rule (IRS Publication 550):**
A wash sale occurs when you sell a security at a loss AND buy the same or substantially identical security within 30 days before or after the sale.

**Detection algorithm:**
1. For each sell trade where `proceeds < cost_basis` (a loss):
   - Identify candidate buy trades using instrument-specific matching (see §7)
   - Filter to buys within window `[sale_date - 30 days, sale_date + 30 days]` across ALL accounts
   - Assign confidence label (`Confirmed` / `Probable` / `Unclear`)
2. Calculate disallowed loss: `min(abs(loss), buy_quantity / sell_quantity * abs(loss))`
3. Add disallowed loss to adjusted cost basis of the triggering buy lot
4. Mark the sell trade as a wash sale with full metadata

**Edge cases handled:**
- Partial wash sales (bought fewer shares/contracts than sold)
- Multiple triggering buys within the window (FIFO allocation — earliest buy absorbs disallowed loss first; this ordering is not IRS-mandated and tax preparers may use a different method)
- Same-day buy and sell (always a wash sale)
- Option expiration (expired worthless = loss, can trigger wash sale on new position)

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Robinhood CSV format changes | High | Medium | LLM parser adapts automatically |
| Schwab CSV format changes | Medium | Medium | LLM parser adapts automatically |
| LLM misidentifies columns | Low | High | Schema confirmation required before import |
| User treats output as legal tax advice | Medium | High | Prominent disclaimers on all output; recommend CPA review |
| IRS issues new guidance on options/ETF wash sales | Low | Medium | Confidence labels + disclaimer design allows graceful updates |
| Anthropic API unavailable | Low | Low | Schema cache; core engine fully offline after first import |

---

## 12. Open Questions

- [x] ~~Should schema confirmation be required?~~ **Decision: Yes, always required before first import of a new format.**
- [x] ~~Should we support multi-year imports in a single database, or one DB per year?~~ **Decision: Single DB, all years.**
- [x] ~~What's the right format for `net-alpha report` output — plain text, CSV, or both?~~ **Decision: Text by default; `--csv` flag optional.**
- [x] ~~Should `simulate` warn about look-back window (past 30 days of buys) in addition to look-forward?~~ **Decision: Yes.**
- [x] ~~ETF similarity pairs: maintain as hardcoded list in repo, or allow user-defined config file?~~ **Decision: Hardcoded defaults + optional user `~/.net_alpha/etf_pairs.yaml` override.**

---

## 13. v2 Roadmap (Post-Launch)

- **Schwab OAuth API integration** — eliminate manual CSV download
- **Tax-loss harvest scanner** — scan portfolio for unrealized losses worth harvesting before year-end
- **Replacement security suggester** — given a position to harvest, suggest correlated-but-not-identical alternatives
- **Robinhood robin_stocks integration** — semi-automated import

---

*This document is a living spec. All decisions are open to revision based on user feedback.*