# CHANGELOG



## v0.14.0 (2026-04-26)

### Chore

* chore: sync uv.lock wash-alpha version to 0.13.1 ([`6162d66`](https://github.com/chen-star/net_alpha/commit/6162d6632e20779687d1a9f2957411166451dee3))

* chore: apply ruff format to phase 1 files

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0b63a93`](https://github.com/chen-star/net_alpha/commit/0b63a93d00241c8d07488b75dabb97a792de21ac))

* chore(web): remove obsolete dashboard route, templates, and tests ([`1de3ee7`](https://github.com/chen-star/net_alpha/commit/1de3ee74acb6d107a71f31c6d3bd503532682729))

* chore(deps): add yfinance to [ui] extras for portfolio pricing

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9e1111d`](https://github.com/chen-star/net_alpha/commit/9e1111d0249aa1bf34fe9e629caaafd0eefabe6b))

### Documentation

* docs(plan): add Phase 1 implementation plan — pricing foundation + portfolio

25 bite-sized TDD tasks covering: yfinance dependency, ~/.net_alpha/config.yaml
loader, schema v3 migration for price_cache, Pricing subsystem (Quote, ABC, cache,
Yahoo provider, service), Portfolio modules (positions, P&amp;L/KPIs/wash-impact,
treemap, equity curve, lot aging), Portfolio page shell + 5 HTMX fragments,
disclaimer footer, dashboard removal, CLAUDE.md updates, and an end-to-end test.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`c969619`](https://github.com/chen-star/net_alpha/commit/c969619ff4f6cef5cd5ad12c5152ddda13d4dd1d))

* docs(spec): add UI/UX redesign design (portfolio + calendar + imports + sim + detail)

Three-phase plan: pricing foundation + portfolio rebuild, calendar dual-ribbon
+ imports relocation/notes, sim buy support + detail enhancements. Documents
the no-remote-prices policy relaxation (symbols only, configurable).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b799929`](https://github.com/chen-star/net_alpha/commit/b7999294fda0f7d63498e400592416d586c03b24))

* docs(claude.md): document price-data privacy + portfolio modules + UI conventions ([`b402bf0`](https://github.com/chen-star/net_alpha/commit/b402bf075c1581cb6b6f716ac593c11c35925669))

* docs(plan): add Phase 1 implementation plan — pricing foundation + portfolio

25 bite-sized TDD tasks covering: yfinance dependency, ~/.net_alpha/config.yaml
loader, schema v3 migration for price_cache, Pricing subsystem (Quote, ABC, cache,
Yahoo provider, service), Portfolio modules (positions, P&amp;L/KPIs/wash-impact,
treemap, equity curve, lot aging), Portfolio page shell + 5 HTMX fragments,
disclaimer footer, dashboard removal, CLAUDE.md updates, and an end-to-end test.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`5bfe284`](https://github.com/chen-star/net_alpha/commit/5bfe28497d8d36cde6070a1b7b3276da5018418d))

* docs(spec): add UI/UX redesign design (portfolio + calendar + imports + sim + detail)

Three-phase plan: pricing foundation + portfolio rebuild, calendar dual-ribbon
+ imports relocation/notes, sim buy support + detail enhancements. Documents
the no-remote-prices policy relaxation (symbols only, configurable).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b5fcf92`](https://github.com/chen-star/net_alpha/commit/b5fcf92928a454c74315658143bbaaa77ccab8ba))

### Feature

* feat(web): add &#39;Prices via Yahoo Finance&#39; footer line when remote prices enabled

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f37b4d2`](https://github.com/chen-star/net_alpha/commit/f37b4d2fa2e5f87520bc64ca1d73ac450f8e523e))

* feat(web): treemap, equity curve, wash-impact, lot-aging fragments ([`5778838`](https://github.com/chen-star/net_alpha/commit/5778838522e7ec65f5d6e347bf3d232395c4b07e))

* feat(web): /portfolio/positions fragment + per-symbol table

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4f7b111`](https://github.com/chen-star/net_alpha/commit/4f7b11102af4c1c7a95ffb12369aca01147c6c5c))

* feat(web): /portfolio/kpis fragment + KPI partial

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c620f5d`](https://github.com/chen-star/net_alpha/commit/c620f5da874dd30003cfa568fb87a1218558753b))

* feat(web): portfolio page shell with HTMX-loaded fragments + empty state

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`98b8dd6`](https://github.com/chen-star/net_alpha/commit/98b8dd657d259932af20dfaafa827359180dbea8))

* feat(portfolio): compute_wash_impact for portfolio mini-grid

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f478ef4`](https://github.com/chen-star/net_alpha/commit/f478ef49cec45b22ecd79dbb9cedb325e65e3b17))

* feat(portfolio): lot_aging — top-N lots crossing LTCG threshold ([`08fd319`](https://github.com/chen-star/net_alpha/commit/08fd319fcd7653a16d3000589975273a3765d363))

* feat(portfolio): equity curve — realized cumulative + present-day point

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b2ef8d0`](https://github.com/chen-star/net_alpha/commit/b2ef8d0a0be1130f7e050a27d9111649ae47efb8))

* feat(portfolio): slice-and-dice treemap layout

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0f03adf`](https://github.com/chen-star/net_alpha/commit/0f03adfac8c4f30e9ad73536fffc6560aa433370))

* feat(portfolio): compute_kpis (period + lifetime, account-scoped)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`76c4614`](https://github.com/chen-star/net_alpha/commit/76c4614ab50dc3a882e907538fdb268fc50b8f34))

* feat(portfolio): compute_open_positions with account/period scoping

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f040f04`](https://github.com/chen-star/net_alpha/commit/f040f0487cc296115b1586f7738b9db750f7896f))

* feat(portfolio): view-model dataclasses for positions/KPIs/charts ([`7ae3fef`](https://github.com/chen-star/net_alpha/commit/7ae3fefdaa83d678c80de6a34420462e5f545b38))

* feat(web): POST /prices/refresh — invalidate + refetch quotes

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8c0746c`](https://github.com/chen-star/net_alpha/commit/8c0746cb31d897fb77e07dd55765b84da141af5a))

* feat(web): wire PricingService into FastAPI app state and DI

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`39bfff0`](https://github.com/chen-star/net_alpha/commit/39bfff03a62061df2457b0f92880eb5f1048d3bc))

* feat(pricing): PricingService orchestrating provider + cache

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`598acfe`](https://github.com/chen-star/net_alpha/commit/598acfe5648b34227908bab6f2ac4119ee2e34da))

* feat(pricing): YahooPriceProvider via yfinance + network test marker

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`310479d`](https://github.com/chen-star/net_alpha/commit/310479db6bf52397d25a451c4b22b558f60e3d78))

* feat(pricing): SQLite-backed PriceCache with TTL + stale detection

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ee90fbb`](https://github.com/chen-star/net_alpha/commit/ee90fbb030bc0e0a87becf2ed17520aaf723ecce))

* feat(pricing): Quote model and PriceProvider ABC

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3b812a3`](https://github.com/chen-star/net_alpha/commit/3b812a36d5c9bdd50d12b7660d53721c4bfb1c82))

* feat(db): schema v3 — add price_cache table for pricing subsystem

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`93baf24`](https://github.com/chen-star/net_alpha/commit/93baf24f15d46fa3bed748fb7d58bde44679198d))

* feat(config): PricingConfig + YAML loader from ~/.net_alpha/config.yaml

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2d80b15`](https://github.com/chen-star/net_alpha/commit/2d80b1563c894ad30265e78fce1dca46f7882bd6))

### Fix

* fix(web): pre-merge polish — refresh ALL, dead dropdown, status text, equity curve scope

- /prices/refresh?symbols=ALL now resolves open-position tickers from the
  repository instead of passing the literal string to Yahoo (which returned
  Allstate); empty-lot edge case returns early with no error
- Remove the non-functional &#34;Show separately&#34; Options dropdown from the
  toolbar; group_options route param stays as a no-op default
- Replace the stuck &#34;Prices: loading…&#34; span with a static accurate label
  (&#34;Prices via Yahoo (~15 min delay)&#34;); id attribute dropped since nothing
  targets it
- Equity curve title changed to &#34;Equity curve · YEAR (YTD only)&#34; to make
  it visually clear the chart is year-scoped regardless of toolbar period
- Update test assertion to match new title-case heading text

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5de5ca0`](https://github.com/chen-star/net_alpha/commit/5de5ca05c3af771fe0ec58693125c81f7517a763))

### Test

* test(integration): end-to-end portfolio page render with mocked prices

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`094b30c`](https://github.com/chen-star/net_alpha/commit/094b30c73a5c6a1faeb8947a50eaff2ea7e268a1))

### Unknown

* Merge branch &#39;feat/portfolio-phase1&#39; — Phase 1 portfolio + pricing subsystem ([`1f481cf`](https://github.com/chen-star/net_alpha/commit/1f481cf84391dadc32c1a24994422c9afd2ebe9a))


## v0.13.1 (2026-04-26)

### Fix

* fix(engine): trust Schwab when it explicitly clears a same-ticker lot

Previously, when the engine flagged a same-account exact-ticker wash sale
candidate that Schwab had already evaluated and cleared (Wash Sale=No),
we surfaced the engine&#39;s verdict as &#34;Unclear&#34;. This inflated the watch list
with cases the IRS would not disallow (e.g. a CRCL 06/18 150C loss whose
nearby buy was a different-strike CRCL contract that Schwab correctly does
not consider substantially identical), and counted them in YTD Disallowed
Loss totals.

Per the original brainstorm decision (&#34;trust Schwab for closed Schwab
positions&#34;), drop these contradictions instead of surfacing them. The one
exception preserved is when the engine&#39;s original confidence was already
&#34;Unclear&#34; — that label only comes from the substantially-identical/ETF-pair
matcher branch, which Schwab cannot model and which still needs human review.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b997555`](https://github.com/chen-star/net_alpha/commit/b9975554ee67e1d5aab6d7144e23d3b497500b5e))


## v0.13.0 (2026-04-26)

### Feature

* feat(web): redesign watch list columns and add period filter

Watch list columns are now Loss date · Ticker · Buy date · Account(s) ·
Disallowed · Confidence. The Account(s) column collapses to a single label
when both sides match and shows &#34;loss → buy&#34; only on cross-account violations,
removing the redundant duplication users were seeing.

Dashboard now defaults to the current year with a year dropdown above the
watch list (years derived from existing violations, plus the current year
and All time). KPI labels switch between YTD/FY&lt;year&gt;/All time accordingly.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b9c38c8`](https://github.com/chen-star/net_alpha/commit/b9c38c8f5719c1c3e05512366541b75536a64ec5))

### Fix

* fix(engine): correct stale violations and per-sell G/L allocation

Two bugs were producing wrong dashboard output:

1. Per-import incremental recompute leaves stale Confirmed/Probable labels.
   Each upload only re-evaluated the ±30-day window of its own affected dates,
   so when G/L data arrived in a later upload the merge step never re-checked
   engine violations from earlier uploads outside that narrow window.

   Add engine/recompute.py::recompute_all_violations which re-runs detection
   and merge over the union of all trade and G/L dates. Wire it into both
   the upload and delete routes in place of the per-window recompute block.

2. stitch._try_gl summed cost basis across every G/L lot sharing the same
   (account, symbol, closed_date) tuple, even when several distinct sells
   existed on that date. A user with two PL sells (proceeds $279.33 and
   $429.33) and two G/L lots (cost $150.66 + $185.66) saw both sells get
   cost_basis=$336.32, manufacturing a phantom $56.99 loss.

   When multiple lots match, narrow to lots whose proceeds match this
   specific sell&#39;s proceeds (within $0.01). Fall back to the full set if
   none match individually, preserving behavior for the case where Schwab
   splits a single sell across multiple cost-basis lots.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3504075`](https://github.com/chen-star/net_alpha/commit/3504075c97fb80921b1e306b00aaf8a7a418184d))


## v0.12.1 (2026-04-26)

### Chore

* chore: sync uv.lock to v0.12.0 ([`c50b56d`](https://github.com/chen-star/net_alpha/commit/c50b56d92d0efd343445a54af492e5a8154868bc))

* chore: sync uv.lock with v0.11.0 release version bump

After pulling the v0.11.0 release commit, uv sync re-generated the lock
to reflect wash-alpha&#39;s new version.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`deb44bf`](https://github.com/chen-star/net_alpha/commit/deb44bfb750264ca7878a24769c18fb125f65e8c))

### Fix

* fix(web): drop zone — include #csv-input in HTMX request

The drop-zone div is not a &lt;form&gt;, so HTMX did not auto-include the file
input when posting to /imports/preview, causing FastAPI to return 422
Unprocessable Entity (missing &#39;files&#39; field). Adding hx-include=&#34;#csv-input&#34;
explicitly tells HTMX to serialize that input into the request body.

Web tests pass (42/42) — they don&#39;t catch this because they POST directly
without going through HTMX. ([`8ec2bef`](https://github.com/chen-star/net_alpha/commit/8ec2bef20296a99b0f049cb18a55c5645a0d51ba))

### Unknown

* Merge branch &#39;master&#39; of https://github.com/chen-star/net_alpha ([`f8e1ce8`](https://github.com/chen-star/net_alpha/commit/f8e1ce817a68c5dc7444dab13df323391416cb81))


## v0.12.0 (2026-04-26)

### Chore

* chore: gitignore private/, drop PRD.md, refresh GitNexus stats, bump uv.lock

- .gitignore: add private/ for local-only Schwab CSVs (not for distribution)
- PRD.md: remove (now superseded by docs/superpowers/specs/)
- AGENTS.md / CLAUDE.md: refresh auto-managed GitNexus stats
- uv.lock: pull in lock churn from feature branch dependencies

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3ffa602`](https://github.com/chen-star/net_alpha/commit/3ffa602cdf34e0cd1f1b4c0a4b5b087b0bf606be))

* chore(web): rebuild Tailwind CSS for new G/L hydration UI elements

Rebuilt via &#39;npx tailwindcss@3&#39; to capture the new utility classes
introduced by the violation source badges, Schwab lot detail panel,
and imports table G/L lots column. (pytailwindcss 0.1.4 now downloads
a Tailwind v4 binary at runtime, which is incompatible with our v3
config. Using npx pins the v3 tooling explicitly.) ([`8f2ce1d`](https://github.com/chen-star/net_alpha/commit/8f2ce1dfd157d47bb05d7682f8248de018493aed))

### Documentation

* docs: add Schwab Realized G/L hydration implementation plan

13 tasks across 7 phases (foundation, parser, engine, web, polish, CLI,
smoke). TDD with bite-sized steps, exact code per step, no placeholders.
Maps directly to the design spec at
docs/superpowers/specs/2026-04-25-schwab-gl-hydration-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`33d1354`](https://github.com/chen-star/net_alpha/commit/33d1354d70bcf7dcd58c1b061ef631a3772faca6))

* docs: add Schwab Realized G/L hydration design spec

Captures the brainstormed design for ingesting Schwab&#39;s Realized G/L
CSV alongside Transaction History to populate cost basis on Sell trades,
unblocking wash-sale detection. Covers parser, stitch algorithm,
engine+Schwab merge rules, schema migration, UI changes, and tests.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`167bf82`](https://github.com/chen-star/net_alpha/commit/167bf82f4c6bf4952f20c85fd96ae5de6eded2ee))

### Feature

* feat(cli): G/L hydration + merge in default import command

CLI accepts mixed Transaction History + Realized G/L files in a single
invocation. Same stitch + merge pipeline as the web UI. Reports
hydration counts and warnings on stdout. Now uses init_db() to ensure
schema migrations run.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f85e585`](https://github.com/chen-star/net_alpha/commit/f85e5858e265b2b94d975b7e63fe40e1407fde3a))

* feat(web): show G/L lot count on imports list

ImportSummary gains gl_lot_count. The imports table renders it as a
new column so G/L-only imports are no longer confusing zero-trade rows. ([`0cabc88`](https://github.com/chen-star/net_alpha/commit/0cabc88458cee9cdeeea240ff48611d4a5bfc85e))

* feat(web): Schwab lot detail panel on ticker drilldown

Read-only table showing closed/opened dates, quantity, cost basis,
wash sale flag, and disallowed loss for each G/L lot in this ticker.
Lets users verify our hydrated cost basis against Schwab&#39;s source data.
Hidden when no G/L rows exist for the ticker.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`6172304`](https://github.com/chen-star/net_alpha/commit/6172304e573547f9952ace27e79f306761a0a1e4))

* feat(web): violation source badges (Schwab / Cross-account / Engine)

Renders next to the existing confidence pill so the user knows whether
a violation came from Schwab&#39;s 1099-B reporting, engine cross-account
detection, or engine-only substantially-identical inference.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7cc86ed`](https://github.com/chen-star/net_alpha/commit/7cc86edda57d3dc1dbbb279f4b079c8afbce91a3))

* feat(web): multi-file upload with G/L hydration + merge

Drop zone accepts multiple CSVs (Schwab Transactions, Realized G/L,
or any combination). Per-file detection cards in preview modal.
Upload route runs each file through its parser, then stitch +
detect + merge end-to-end, scoped to the affected ±30-day window.
Flash message reports counts: trades, dups, G/L lots, hydrated sells,
warnings. ([`6d85d7d`](https://github.com/chen-star/net_alpha/commit/6d85d7d9f16582cdb277456569e405dce67f626b))

* feat(engine): merge_violations — combine engine output with Schwab verdicts

Rules:
  1. Schwab wash_sale=Yes  -&gt; Confirmed/schwab_g_l violation
  2. Engine + Schwab agree -&gt; keep Schwab&#39;s
  3. Engine same-acct cleared by Schwab -&gt; downgrade engine to Unclear
  4. Engine cross-account  -&gt; Probable/engine
  5. Engine same-acct without matching Schwab row (substantially identical)
                          -&gt; Unclear/engine
  6. No G/L for account    -&gt; engine output unchanged

WashSaleViolation gains a source field; round-tripped via repository.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c79ef7d`](https://github.com/chen-star/net_alpha/commit/c79ef7dccca29df20133cda886fe0d0f589a74fc))

* feat(engine): stitch — hydrate Sell cost_basis from G/L or FIFO

stitch_account walks every Sell trade in an account and populates
cost_basis from realized_gl_lots (preferred, by symbol+closed_date)
or FIFO buy-lot consumption (fallback). Records basis_source on
each Sell so the UI can surface confidence/source. Returns a
StitchSummary with counts and any quantity-mismatch warnings. ([`52bacc6`](https://github.com/chen-star/net_alpha/commit/52bacc6576c98347bb633ca07665686a6808b358))

* feat(brokers): SchwabRealizedGLParser produces RealizedGLLot rows

Recognizes Realized G/L CSV by headers (Symbol, Closed Date, Opened Date,
Quantity, Proceeds, Cost Basis (CB), Wash Sale?). Parses both stock and
option lots, money columns with \$/comma, Yes/No flags, and empty
Disallowed Loss as 0.0. Registered after SchwabParser in the registry.
BrokerParser Protocol relaxed to list[Any] since parsers may emit
different value-object types.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8e1370b`](https://github.com/chen-star/net_alpha/commit/8e1370b2a0ef0b3638c8919ec0f7deee0d311253))

* feat(db): repository methods for G/L lots and stitch helpers

Adds add_gl_lots, get_gl_lots_for_match, get_gl_lots_for_ticker,
get_sells_for_account, get_buys_before_date, update_trade_basis.
Idempotent insert dedups on RealizedGLLot.compute_natural_key().
Trade Pydantic gains basis_source field; round-tripped via repository. ([`1c52964`](https://github.com/chen-star/net_alpha/commit/1c5296492449a1a746c4eecb472fc3798791db6c))

* feat(db): schema v2 — realized_gl_lots table + basis_source/source columns

Adds RealizedGLLotRow table, Trade.basis_source column (default &#39;unknown&#39;),
and WashSaleViolation.source column (default &#39;engine&#39;). Wires
migrate(session) into init_db() so v1 DBs upgrade in place. Migration
is additive and idempotent. ([`2ad08de`](https://github.com/chen-star/net_alpha/commit/2ad08de29dc50e5116b42450fd912050ed778dc7))

* feat(models): add RealizedGLLot domain model

Pydantic value object for one tax-lot row from Schwab&#39;s Realized G/L
CSV. Includes Schwab&#39;s per-lot wash sale flag and disallowed loss for
later merge with engine output. compute_natural_key() supports
idempotent dedup on re-imports. ([`1db4b62`](https://github.com/chen-star/net_alpha/commit/1db4b62b969749606a22f4108be2153a7518804b))

* feat(ingest): smart header detection in load_csv

Skips up to 5 preamble rows (title rows, blank rows) before the real
header row. Required for Schwab Realized G/L CSVs which have a
&#39;Realized Gain/Loss - Lot Details ...&#39; title above the column headers.
Falls back to row 0 when no plausible header row is found, preserving
backwards compat for files that already had headers on row 0. ([`76b4fd0`](https://github.com/chen-star/net_alpha/commit/76b4fd0f87661304aa65ed50beeff36adbdcf20b))

### Fix

* fix(db): cascade-delete G/L lots on remove_import + re-stitch

Without this, removing an import that contained G/L data leaves orphan
RealizedGLLotRow rows behind. Subsequent stitch_account calls would
silently hydrate sells using stale cost basis from those orphans,
corrupting wash-sale results.

The web DELETE /imports/{id} route now also runs stitch_account before
re-running detect_in_window, so sells that were hydrated from now-removed
G/L data get demoted to FIFO/unknown as appropriate. ([`401dbfe`](https://github.com/chen-star/net_alpha/commit/401dbfecbcbd9c28e4d9d6e5ebe6b020dab2a5c8))

* fix(db): resolve real trade IDs for Schwab G/L violations

Schwab G/L violations carry synthetic &#39;schwab_gl_&lt;hash&gt;&#39; trade IDs
that can&#39;t be int()-cast for the FK column. _violation_to_row now
detects source=&#39;schwab_g_l&#39; and resolves loss_trade_id by looking
up the matching Sell trade (account+ticker+date). When no matching
Sell trade exists, raises LookupError; replace_violations_in_window
catches and silently skips, supporting G/L-only imports without
Transaction History. ([`a9efd42`](https://github.com/chen-star/net_alpha/commit/a9efd421b089c320305a294a9141289ed8816d8b))

* fix(ingest): apply ruff format + clarify load_csv docstring

Address code-review feedback for Task 1:
  - ruff format collapsed implicit string concatenation in tests
    (same lint rule that blocked d8deb63 on master)
  - load_csv docstring references _HEADER_SCAN_LIMIT instead of
    hardcoding the value 5 ([`2d62568`](https://github.com/chen-star/net_alpha/commit/2d62568e878f8e045cfe3389871238fea8ae10e4))

### Unknown

* Merge branch &#39;master&#39; of https://github.com/chen-star/net_alpha ([`1f97f51`](https://github.com/chen-star/net_alpha/commit/1f97f5118ef86b980240f11e33cbdc109c88709b))

* Merge feature/schwab-gl-hydration — Schwab Realized G/L hydration (v2.2)

Adds Schwab Realized G/L CSV ingestion alongside Transaction History so the
wash-sale engine can detect violations on Schwab data.

Architecture: a new realized_gl_lots table stores Schwab&#39;s per-lot G/L
verbatim. SchwabRealizedGLParser produces those rows from G/L CSVs. After
every import a stitch pass walks each Sell trade and populates cost_basis
from G/L (preferred) or FIFO buy lots (fallback). Engine output is then
merged with Schwab&#39;s per-lot wash-sale verdict — Schwab is authoritative
for closed Schwab positions, our engine adds cross-account and
substantially-identical detections.

UI: multi-file upload (any combination of CSVs), per-file detection cards,
violation source badges (Schwab / Cross-account / Engine), Schwab lot
detail panel on ticker drilldown, G/L lots column on imports list. CLI
gets the same pipeline. Schema bumped 1→2 with idempotent migration.

249 tests passing. Spec: docs/superpowers/specs/2026-04-25-schwab-gl-hydration-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`cdea0c8`](https://github.com/chen-star/net_alpha/commit/cdea0c89ddf234bdfa17374032a44c97f8bd4b1e))


## v0.11.0 (2026-04-26)

### Build

* build(web): tailwind config, source css, and built app.css; add make build-css ([`9ebd80d`](https://github.com/chen-star/net_alpha/commit/9ebd80d5c421dfb885ce228a0feb30b9ae89ce0d))

### Documentation

* docs(plan): local UI implementation plan (20 tasks, TDD)

20-task subagent-ready plan covering Phase A foundation (deps, app
factory, conftest, Tailwind, static, base.html), Phase B repository
extensions, Phase C read-only views (dashboard, imports, detail, sim),
Phase D drag-drop import (drop zone, preview, upload), Phase E
visualizations (calendar ribbon + focus, ticker drilldown), Phase F
polish (errors, CLI ui command, docs). Each task carries the failing
test, exact code, run command, expected output, and commit step.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`55df40d`](https://github.com/chen-star/net_alpha/commit/55df40dcb5d2479cb21187c81383e32532c4ac74))

* docs(spec): local UI design — net-alpha ui (v2.1.0)

Adds the design spec for an optional, ephemeral, local-only web UI that
wraps the existing v2 engine. Drag-drop CSV import, wash-sale calendar
(annual ribbon + ±30-day focus strip), ticker drilldown, and CLI parity
views (sim, imports management, detail). Stack: FastAPI + Jinja + HTMX +
Alpine + Tailwind, vendored static assets, no node/npm/Docker. Optional
dependency group keeps CLI-only installs lean.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7373ea7`](https://github.com/chen-star/net_alpha/commit/7373ea79c8274242ba9320954a5ee5bff01c0a6e))

* docs: document net-alpha ui command + web subsystem in README and CLAUDE.md ([`2b3e56e`](https://github.com/chen-star/net_alpha/commit/2b3e56eb63976f524324c0392803d0cd517e9dc7))

* docs(plan): local UI implementation plan (20 tasks, TDD)

20-task subagent-ready plan covering Phase A foundation (deps, app
factory, conftest, Tailwind, static, base.html), Phase B repository
extensions, Phase C read-only views (dashboard, imports, detail, sim),
Phase D drag-drop import (drop zone, preview, upload), Phase E
visualizations (calendar ribbon + focus, ticker drilldown), Phase F
polish (errors, CLI ui command, docs). Each task carries the failing
test, exact code, run command, expected output, and commit step.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9792dfb`](https://github.com/chen-star/net_alpha/commit/9792dfb10670b1e90c4e977169abec08ee7c75c7))

* docs(spec): local UI design — net-alpha ui (v2.1.0)

Adds the design spec for an optional, ephemeral, local-only web UI that
wraps the existing v2 engine. Drag-drop CSV import, wash-sale calendar
(annual ribbon + ±30-day focus strip), ticker drilldown, and CLI parity
views (sim, imports management, detail). Stack: FastAPI + Jinja + HTMX +
Alpine + Tailwind, vendored static assets, no node/npm/Docker. Optional
dependency group keeps CLI-only installs lean.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`c558b2a`](https://github.com/chen-star/net_alpha/commit/c558b2a6c13bfb707da68f8534dea7b0ae67ec0b))

### Feature

* feat(cli): net-alpha ui command (port picker, uvicorn boot, browser open) ([`b050e0d`](https://github.com/chen-star/net_alpha/commit/b050e0d50c5f8880a1fd6cf51e4d69edfbfed5cd))

* feat(web): 404/500 handlers render error.html with traceback toggle ([`a27cfeb`](https://github.com/chen-star/net_alpha/commit/a27cfeb1808bd838a1c9374483f5bf39475494a9))

* feat(web): GET /ticker/{symbol} drilldown with KPIs, timeline, lots, violations ([`56c5330`](https://github.com/chen-star/net_alpha/commit/56c5330639cb16372c2ea14988d019e5cb988651))

* feat(web): GET /calendar/focus/{id} renders ±30-day strip + violation card ([`367c201`](https://github.com/chen-star/net_alpha/commit/367c2010680d135a8337c66dfb0478e534da46fe))

* feat(web): GET /calendar with annual ribbon (per-year violation markers) ([`4fb8f69`](https://github.com/chen-star/net_alpha/commit/4fb8f69cc303bac3c0cfe40c860d574eccb55b40))

* feat(web): POST /imports/preview + POST /imports for drag-drop upload flow ([`e16f065`](https://github.com/chen-star/net_alpha/commit/e16f0658f8e383ad77f3a122ee53cb4e470be3c5))

* feat(web): drag-drop zone partial on dashboard with Alpine drag-over highlight ([`d6ca656`](https://github.com/chen-star/net_alpha/commit/d6ca656734a9c5ad6a7a19d78502680a6c36b887))

* feat(web): GET/POST /sim with HTMX-driven per-account result cards ([`9e9e94d`](https://github.com/chen-star/net_alpha/commit/9e9e94dd9a66092914df349c971628154a76b7c3))

* feat(web): GET /detail page with ticker/account/year/confidence filters ([`51f397f`](https://github.com/chen-star/net_alpha/commit/51f397f6615816b096d43582bc65b2cca3b1d900))

* feat(web): DELETE /imports/{id} removes import + recomputes wash sales ([`74086fd`](https://github.com/chen-star/net_alpha/commit/74086fdb732ea71af4f01e656e5f4d105babc92e))

* feat(web): GET /imports management page with HTMX-ready remove button ([`9ad18b0`](https://github.com/chen-star/net_alpha/commit/9ad18b08c442326eb5708d39758f629dab2e7fb5))

* feat(web): dashboard route with watch list + YTD KPI cards ([`76b6ae2`](https://github.com/chen-star/net_alpha/commit/76b6ae25680ad8f435ebb2ce2cd17635268a77fe))

* feat(db): repository read methods for UI (list_distinct_tickers, get_*_for_ticker) ([`cfa6357`](https://github.com/chen-star/net_alpha/commit/cfa6357ce04d9b36f169fbc9e53cba5ba78ef3eb))

* feat(web): base.html with nav and disclaimer footer; jinja env + etf pairs in app state ([`27fbbb3`](https://github.com/chen-star/net_alpha/commit/27fbbb377a0c868dbb0c279402391f469779a69d))

* feat(web): vendor htmx + alpine static assets, mount /static via StaticFiles ([`4d19694`](https://github.com/chen-star/net_alpha/commit/4d19694265b77d099f798601542a081b15aed3ec))

* feat(web): create web package skeleton with FastAPI app factory ([`c533b7d`](https://github.com/chen-star/net_alpha/commit/c533b7d9ddc5c0bb164ec02371c23d00e47ec40e))

### Fix

* fix(web): correct tailwind palette to match design spec (primary, secondary, accent, bg) ([`ce14d2a`](https://github.com/chen-star/net_alpha/commit/ce14d2a8db0bd2be10ff51aaca3bc7af34d59611))

* fix(build): pin pytailwindcss to v3, restore @apply with custom color tokens

Downgrade pytailwindcss to v3.4.1 and restore v3-style CSS with @apply
directives using custom color tokens (primary, secondary, confirmed,
probable, unclear). Manually installed v3 via pytailwindcss.install(),
added safelist for utility classes and component classes to ensure all
needed styles are generated despite no templates yet.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b7ad2ff`](https://github.com/chen-star/net_alpha/commit/b7ad2ffdc87d6005ce929c446cce2d8c87f3698a))

### Style

* style: ruff format + import sort across web subsystem ([`f171a16`](https://github.com/chen-star/net_alpha/commit/f171a1627e8f92a165dfb03ee797f852980e991c))

### Test

* test(web): add conftest with settings/engine/repo/client fixtures + trade builders ([`a20976f`](https://github.com/chen-star/net_alpha/commit/a20976f597486b940311cb5915a0e26ed10db759))

### Unknown

* Merge feature/local-ui — local web UI (v2.1)

20-task subagent-driven implementation of the local web UI:
FastAPI + Jinja + HTMX + Alpine + Tailwind v3 (vendored, no node/npm).
Drag-drop CSV import, watch list, YTD KPIs, sim, imports management,
detail, wash-sale calendar (annual ribbon + ±30-day focus), ticker
drilldown, error pages, and the `net-alpha ui` CLI command (port picker,
uvicorn boot, browser open, --port/--no-browser/--reload flags).

187 tests passing, ruff clean.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`cd2486c`](https://github.com/chen-star/net_alpha/commit/cd2486c246c2bd4e7543ac486943c0ed96a81e94))

* deps(ui): add optional ui group (fastapi, jinja, uvicorn, multipart) + pytailwindcss/httpx for dev ([`0af0d14`](https://github.com/chen-star/net_alpha/commit/0af0d143505a0152bdbdcd7dfca74a9c408357ef))


## v0.10.0 (2026-04-25)

### Chore

* chore(deps): drop questionary, anthropic, pydantic-settings, textual; bump to 2.0.0

Runtime dep set is now: pydantic, sqlmodel, typer[all], loguru, pyyaml.
Description reflects the v2 simplified product. config.py migrated from
BaseSettings to plain pydantic BaseModel; LLM-related config fields removed.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c19ba5f`](https://github.com/chen-star/net_alpha/commit/c19ba5fe32b194d0794f7bf4ea4691c42b85dd09))

* chore(v2): delete legacy import_/, cli/import_cmd, cli/simulate, unused models

v2 surfaces (default + sim + imports + migrate-from-v1) replace all
prior import/check/simulate paths. Repository stubs and unused
Pydantic models follow them out. MetaRepository remains for the
migration boot in cli/app.py.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ae5ab0b`](https://github.com/chen-star/net_alpha/commit/ae5ab0b3c8b09f204fdb8cc4ab9788ae84913db8))

* chore: move etf_pairs.yaml into package, wire loader through CLI

Bundled file now lives at src/net_alpha/etf_pairs.yaml so pip install
ships it. User override at ~/.net_alpha/etf_pairs.yaml extends bundled
pairs (does not replace). Both CLI recompute call sites now use the
real loader instead of an empty dict stub.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`82c2348`](https://github.com/chen-star/net_alpha/commit/82c2348add81832ddd66aafe412c05904cea12e8))

* chore(v2): remove TUI, agent, wizard, and dropped CLI commands

These surfaces are cut in v2. Engine, db, and import_ packages remain
in place pending replacement in later tasks.

SchemaMapping and anonymize_row were inlined into csv_reader.py and
importer.py respectively (both kept), since schema_detection.py and
anonymizer.py were their sole definitions but still consumed by kept modules.
Integration tests for the deleted commands were also removed.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4fde88e`](https://github.com/chen-star/net_alpha/commit/4fde88e26242a2b4e4412f2e4b5475670a3764c8))

* chore(v2): branch start — implementing v2 simplification spec ([`60d7aba`](https://github.com/chen-star/net_alpha/commit/60d7aba5af3cd7653b812a2c3dbe3091b29fc62e))

### Documentation

* docs: rewrite README, CLAUDE.md, AGENTS.md for v2 surface

Remove all v1-era references (AI import, LLM/Anthropic, questionary,
pydantic-settings, textual TUI, wizard, agent, check/report/rebuys
subcommands). Replace with v2 command surface (default import+check,
sim, imports, imports rm, migrate-from-v1) and bundled-Schwab-parser
description throughout.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`85b7a26`](https://github.com/chen-star/net_alpha/commit/85b7a26a1e334e42da457bc873f3cc72a6d30a98))

* docs(plans): add v2 simplification implementation plan

21 tasks covering worktree setup, legacy module removal, schema
rewrite, repository v2, brokers/ + ingest/ + output/ packages,
detect_in_window, simulate_sell, CLI surface (default/sim/imports),
migrate-from-v1 helper, dep cleanup, docs, and final verification.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`956e5eb`](https://github.com/chen-star/net_alpha/commit/956e5ebea9b637f2a2a642452700649c1925ff8b))

* docs(specs): revise v2 sim — cross-account what-if planner

Sim no longer requires --account; instead enumerates every account
that holds the ticker and shows one option per account with FIFO
lots, P&amp;L, and a cross-account wash-sale verdict per option.
--account becomes an optional filter. Resolves all open questions
on sim, --detail, and account display format.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`eb0c404`](https://github.com/chen-star/net_alpha/commit/eb0c404b6dc9b4c4541ce91ef2cf8156ccc910d3))

* docs(specs): add v2 simplification design

v2 collapses 10 CLI commands + wizard + TUI + agent into 4 commands
to address surface sprawl and setup ceremony in v1. Removes LLM CSV
import, Robinhood, TUI, and agent surfaces. Estimated ~4000 LOC →
~1800 LOC. Stateful/incremental persistence preserved with
windowed wash-sale recompute and idempotent multi-account imports.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9c7f3b3`](https://github.com/chen-star/net_alpha/commit/9c7f3b38fc63cf519bb651dbadc816e8635dd9d2))

### Feature

* feat(cli): migrate-from-v1 helper (v2.0.x only)

Reads ~/.net_alpha/net_alpha.db (v1 schema) and writes a parallel
v2 DB at ~/.net_alpha/net_alpha.db.v2. User then moves it into
place. Refuses to overwrite an existing v2 file.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`be10af3`](https://github.com/chen-star/net_alpha/commit/be10af3731331d57a6fcde99262bd4911b744742))

* feat(cli): v2 surface — default import/check, sim, imports, imports rm

Rewrites app.py with a _FileFirstGroup that routes file-path arguments to
a hidden &#39;run&#39; sub-command, enabling `net-alpha &lt;csv&gt; --account &lt;label&gt;`
as the default entry point alongside explicit `sim` and `imports` sub-commands.
Deletes test_simulate_lots.py (v1 simulate tests superseded by test_app_v2.py).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8d5f09e`](https://github.com/chen-star/net_alpha/commit/8d5f09e2a0241f06900e1a0d6928cd3415869920))

* feat: thread ticker through WashSaleViolation for renderer enrichment

Add ticker field to WashSaleViolation domain model, WashSaleViolationRow
table, detector emission, repository read/write paths, and watch_list
renderer. Removes the hardcoded &#39;TKR&#39; placeholder.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6c19716`](https://github.com/chen-star/net_alpha/commit/6c1971618ae9a19bc930effa87873d28a7e46be8))

* feat(output): renderers — disclaimer, watch_list, ytd_impact, sim_result, imports_table, detail

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c6784b5`](https://github.com/chen-star/net_alpha/commit/c6784b55bc32fc6510cc7cdb9bab25141c70d79b))

* feat(brokers): protocol + registry + Schwab parser

Add BrokerParser Protocol, detect_broker registry, and SchwabParser
implementing buy/sell/reinvest/option action parsing for Schwab CSVs.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`450c6d9`](https://github.com/chen-star/net_alpha/commit/450c6d9d28e5f321944367e035f54998276d05b3))

* feat(ingest): csv_loader, option_parser port, dedup by natural_key

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`26e36dc`](https://github.com/chen-star/net_alpha/commit/26e36dc660deb08bf436c9d2f6638b2b6eaf83e9))

* feat(engine): simulate_sell — cross-account what-if planner

Implements Task 11: simulator.py with FIFO lot consumption, realized P&amp;L,
cross-account wash sale detection, insufficient-shares flagging, and
lookforward_block_until date. 7 new tests; full suite at 215.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`57a4311`](https://github.com/chen-star/net_alpha/commit/57a43119f4437f8843d9a757ac7979a4a29e9fae))

* feat(engine): detect_in_window for incremental recompute

Append new function detect_in_window to detector.py that runs the full
detection algorithm but emits only violations whose loss_sale_date falls
within the supplied window. Caller is responsible for passing trades that
include ±30 days around the window for correct cross-window matching.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9a5d854`](https://github.com/chen-star/net_alpha/commit/9a5d8543697ea57c532241f059ac0117afc92a48))

* feat(engine): violations carry loss_account, buy_account, sale/buy dates

Tightens the scaffolded _violation_to_row helper from Task 8 to use
the new typed fields. Wash sale violations now have full provenance
(which accounts, when) needed by the v2 watch list and YTD renderers.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fa5401f`](https://github.com/chen-star/net_alpha/commit/fa5401f8322fc031bb5cef95c7d74fad8616bde4))

* feat(db): repository remove_import + replace_violations_in_window

Add three methods to v2 Repository: remove_import (cascading delete of
import/trades/lots/violations + recompute window), replace_violations_in_window
(atomic clear-and-rewrite of violations in date range), and _violation_to_row
(scaffolded with getattr defaults for Task-9 fields loss_account_id,
buy_account_id, loss_sale_date, triggering_buy_date).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8716132`](https://github.com/chen-star/net_alpha/commit/8716132626cde08b5f7a33fadc9c56015f9dee78))

* feat(db): repository reads — trades, lots, violations, windowed

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e20ac26`](https://github.com/chen-star/net_alpha/commit/e20ac266803aa3711229f1d9cae30d1d526bd02a))

* feat(db): add_import with dedup via natural_key UNIQUE constraint

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`76054c7`](https://github.com/chen-star/net_alpha/commit/76054c75128d321ece5e4f04c720e5d1f94600ee))

* feat(db): repository v2 skeleton + account/import management methods

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`767c754`](https://github.com/chen-star/net_alpha/commit/767c7545251dd55ebf2dd39b7185567c2bf6af63))

* feat(models): add Trade.compute_natural_key for v2 idempotent imports

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`714a60c`](https://github.com/chen-star/net_alpha/commit/714a60c1fabe23a24239eb83f559792f2bbce2a0))

* feat(db): replace tables with v2 schema (Account, Import, FKs, natural_key)

v1 schema is dropped wholesale. Schema starts at version 1. v1 -&gt; v2
upgrade lives in a separate migrate-from-v1 helper (Task 17).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`934a73f`](https://github.com/chen-star/net_alpha/commit/934a73f5dda0163680d5db1a6b1657fae0af7313))

* feat(models): add v2 domain types — Account, ImportRecord, SimulationOption

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`80cc7ff`](https://github.com/chen-star/net_alpha/commit/80cc7ffe116ada255cafdee6e723b5f2f29a6e9a))

### Fix

* fix(cli,db): persist lots after wash-sale recompute

The default and imports-rm flows were calling detect_in_window then
discarding the result.lots half. As a consequence repo.all_lots() was
always empty and sim reported &#39;no holdings of &lt;ticker&gt;&#39; for any
import. Adds Repository.replace_lots_in_window mirroring the
violations method, and updates both CLI handlers to persist both
halves of the DetectionResult.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`daf22de`](https://github.com/chen-star/net_alpha/commit/daf22de3443f353198f4944fd2ace24a82585828))

* fix(cli,db): tighten violation_to_row session, account annotation, mark TODOs

- repository._violation_to_row now takes the parent session as a
  parameter, matching the row-helper pattern used elsewhere.
- cli/app.py callback&#39;s --account annotation is str | None (was str
  with None default).
- Both etf_pairs={} sites tagged with TODO(Task 16) so the loader
  wire-up isn&#39;t missed.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`8239395`](https://github.com/chen-star/net_alpha/commit/8239395aa452004e2cb37d13f21110453d911efd))

* fix(db): repository violation reads populate full field set

Both all_violations() and violations_for_year() were dropping
loss_sale_date, triggering_buy_date, loss_account, and buy_account
when reconstructing Pydantic WashSaleViolation from the row. This
silently broke watch_list filtering (predicate on triggering_buy_date)
and produced &#39;None ... on None&#39; garbage from --detail.

Also: drop hardcoded &#39;schwab&#39; from sim&#39;s no-such-account message.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1cd2dd5`](https://github.com/chen-star/net_alpha/commit/1cd2dd5bf877ed20c8f1313ee78f6a1574432f16))

* fix(db): consolidate CURRENT_SCHEMA_VERSION; guard removed LLM path

- importer.py: replace SchemaCacheRow LLM branch with explicit
  NotImplementedError so the import path doesn&#39;t crash silently.
- connection.py: import CURRENT_SCHEMA_VERSION from migrations
  (eliminates duplicate constant).
- migrations.py: add scaffolding comment for future schema versions.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3ac3671`](https://github.com/chen-star/net_alpha/commit/3ac3671b778664aa21c9d964f27b5e10bb950c74))

* fix(import_): rename ambiguous &#39;l&#39; var, drop dead _NUMERIC_PATTERN

Both regressions were introduced when inlining anonymizer.py and
schema_detection.py during Task 1. Will be deleted entirely in Task 18,
but fixing now to keep CI green.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`4b82513`](https://github.com/chen-star/net_alpha/commit/4b82513548d8b731077efec6723dfba50e092da8))

### Unknown

* Merge v2 simplification rewrite into master

v2 collapses the surface from 10 CLI commands + wizard + TUI + agent
into 4 commands (sim, imports, imports rm, migrate-from-v1, plus the
default &lt;csv&gt; flow). Removes LLM CSV import, Robinhood, TUI, agent,
wizard, schema cache, and pydantic-settings/anthropic/questionary/
textual deps. New brokers/, ingest/, output/ packages. Repository
v2 with idempotent multi-account imports and windowed wash-sale
recompute. simulate_sell as a cross-account what-if planner.

22 tasks executed via subagent-driven-development with two-stage
review (spec compliance + code quality) per task. Final state:
150 passing tests, lint clean, ruff format clean, package builds
as wash_alpha-2.0.0.

See:
- docs/superpowers/specs/2026-04-25-v2-simplification-design.md
- docs/superpowers/plans/2026-04-25-v2-simplification.md

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`14495ba`](https://github.com/chen-star/net_alpha/commit/14495ba56aaec0120e8c1ce49e45e75149fa91aa))


## v0.9.1 (2026-04-19)

### Fix

* fix: resolve all linting and formatting errors to fix failing CI ([`d8deb63`](https://github.com/chen-star/net_alpha/commit/d8deb631e5ec593fe776b77cdb146a5ff7b4bd21))


## v0.9.0 (2026-04-18)

### Chore

* chore: update GitNexus index statistics in documentation files ([`b0e940b`](https://github.com/chen-star/net_alpha/commit/b0e940b508fcdd7f58286dfe71184f5894dd5f70))

### Documentation

* docs: sync PRD commands with current implementation and update GitNexus stats ([`12d8616`](https://github.com/chen-star/net_alpha/commit/12d8616911551307a17d8427b16f9a44068f3abc))

* docs(plans): add api key fallback implementation plan ([`5c05dbf`](https://github.com/chen-star/net_alpha/commit/5c05dbfe83f509e51ea8990748c654a50276ed79))

* docs(specs): add api key fallback design spec ([`48734bb`](https://github.com/chen-star/net_alpha/commit/48734bb8039da72f3b4bbb967dcb5a8c3e8005a3))

* docs: modernize README and update agent configuration ([`1f5920b`](https://github.com/chen-star/net_alpha/commit/1f5920b5c323433deec649fac4fe700b99251e0d))

### Feature

* feat(cli): remove eager api key prompt from interactive wizard ([`5759c10`](https://github.com/chen-star/net_alpha/commit/5759c10b5b2b5b24b513a39c0f4bbb2991a08d4d))

* feat(cli): make API key optional for import command ([`49edb65`](https://github.com/chen-star/net_alpha/commit/49edb65956ec01916b0720310afb0cfcf324bb4d))

* feat(import): run_import uses hardcoded schema if cache misses and no API key ([`4ca8bea`](https://github.com/chen-star/net_alpha/commit/4ca8beaf5939ebf675857debb0289d2768207e3e))

* feat(import): add hardcoded schemas for schwab and robinhood ([`0d8ab77`](https://github.com/chen-star/net_alpha/commit/0d8ab776d74fd169d20872a66307cc0a81383c48))

### Test

* test: update tests to test LLM branch using unknown_broker instead of known brokers ([`f576a66`](https://github.com/chen-star/net_alpha/commit/f576a66956110ae7d7edc94a28f521baf8d26fec))


## v0.8.0 (2026-04-18)

### Chore

* chore: add textual dependency for TUI ([`2c3261a`](https://github.com/chen-star/net_alpha/commit/2c3261af9b71d1df80968fc6fe894074beb101c9))

* chore: install ui-ux-pro-max-skill for cluade and antigravity ([`e0fcc72`](https://github.com/chen-star/net_alpha/commit/e0fcc721d8e3b40ca8e01bdec610265b71a3df37))

### Documentation

* docs: sync architecture, cli, and readme with tui implementation and update model versions ([`89558c2`](https://github.com/chen-star/net_alpha/commit/89558c27d088b314f45386fa9ecaba19b7aa3024))

* docs: add interactive simulator TUI design spec ([`d8c4e0f`](https://github.com/chen-star/net_alpha/commit/d8c4e0f3125cc2cbd479c97db38db3a53cb335e1))

### Feature

* feat(tui): accurately track and display virtual trade wash sales ([`283a238`](https://github.com/chen-star/net_alpha/commit/283a2381e80332d47666974f54125215bbf5a9e7))

* feat(tui): wire reactive inputs to simulation engine ([`a6408a2`](https://github.com/chen-star/net_alpha/commit/a6408a25f31848fc451fcf9ca9725425c861bd81))

* feat(tui): add simulation engine helper ([`5d146a9`](https://github.com/chen-star/net_alpha/commit/5d146a9059a89e35166017e551d83e4e02f799a2))

* feat(tui): load and display database trades in DataTable ([`b1335b8`](https://github.com/chen-star/net_alpha/commit/b1335b868cc9f974989aa28fd487433257e1053a))

* feat(tui): build split-pane dashboard layout ([`d7e5428`](https://github.com/chen-star/net_alpha/commit/d7e54280ea839401adf0cd571b72614913e134b8))

* feat(tui): scaffold base textual app and cli command ([`a5338fb`](https://github.com/chen-star/net_alpha/commit/a5338fb2cdfba604dcc5281fefae3d03c82d93c0))


## v0.7.0 (2026-04-18)

### Chore

* chore: remove tmp_skills from git ([`88aafed`](https://github.com/chen-star/net_alpha/commit/88aafed0856cfec30f651c21d0034f9970f4c728))

### Documentation

* docs(design): add interactive wizard CLI UX spec ([`6214582`](https://github.com/chen-star/net_alpha/commit/6214582dcc22d86d0ef1bbd1c92a27fd72bfd39e))

* docs: fix verification failures and update codebase references

- Resolve gitnexus tool reference failures in CLAUDE.md and AGENTS.md
- Correct CI/CD workflow paths to .github/workflows/ in release plan
- Update CLI test path to integration test location in CLI plan
- Update project name to wash-alpha and fix SchemaCacheRow symbol ([`e9c31d0`](https://github.com/chen-star/net_alpha/commit/e9c31d0dbaf0b55cfbadce4f5f3487aa1db82ac8))

* docs: update project documentation ([`2f8113f`](https://github.com/chen-star/net_alpha/commit/2f8113fd68d2e1441e048c18fe1ce3d536a2a33e))

### Feature

* feat(cli): add interactive wizard mode ([`dfec553`](https://github.com/chen-star/net_alpha/commit/dfec5538ed0c1d5727953e035519cb108cc6a498))

### Unknown

* merge: synchronize with origin/master and finalize v0.6.0 release ([`af439b3`](https://github.com/chen-star/net_alpha/commit/af439b3f789b0e467e6a22eb44d6dd37fff563c0))


## v0.6.0 (2026-04-16)

### Documentation

* docs: update PyPI badge to Shields.io and refresh GitNexus index ([`e280434`](https://github.com/chen-star/net_alpha/commit/e2804340bf5a96ffb52f483f85e6db151145780f))

* docs: include design spec and implementation plan for README overhaul ([`2f16adc`](https://github.com/chen-star/net_alpha/commit/2f16adc24e390d11700aa279fc17c9697f1a539b))

* docs: add summary for README overhaul plan ([`c70433d`](https://github.com/chen-star/net_alpha/commit/c70433d77266fd1892ba661c2c86fe070b4a5673))

* docs: final polish of README overhaul ([`9a9968f`](https://github.com/chen-star/net_alpha/commit/9a9968fe57f38a14701543e172d1752e1316d5db))

* docs: add technical deep-dive and privacy section to README ([`057964f`](https://github.com/chen-star/net_alpha/commit/057964f984e342c54dac5d7aa9ddd8a8ede7da85))

* docs: add modern workflow walkthrough to README ([`676bd1c`](https://github.com/chen-star/net_alpha/commit/676bd1c2ebb9bd16997d637395be5c5a872a75d1))

* docs: add hero header and value prop to README ([`4c197fa`](https://github.com/chen-star/net_alpha/commit/4c197faab0624aacb9a1a6f0081883332ea7a3db))

### Feature

* feat: add crypto and common ETF pairs for tax loss harvesting ([`4636381`](https://github.com/chen-star/net_alpha/commit/4636381fd1e9bb009bebc3b6121adb705422ad34))


## v0.5.0 (2026-04-16)

### Chore

* chore: update release script, Makefile, and local lockfile ([`7cad10b`](https://github.com/chen-star/net_alpha/commit/7cad10b421152a9555aaef82e6ff52643a49cee9))

### Ci

* ci: fix automated release and add manual release fallback ([`f6bd838`](https://github.com/chen-star/net_alpha/commit/f6bd838efd11d842befe0d4bf5b583ad1be5bc0b))

### Documentation

* docs: update codecov badge with private token ([`1980c62`](https://github.com/chen-star/net_alpha/commit/1980c62eb47dc79708868bc791808350996de24b))

### Feature

* feat: enhance README with AI agent and interactive TUI features ([`d7b75ae`](https://github.com/chen-star/net_alpha/commit/d7b75aef04d444f440d2ed623c752d8aebaa519d))


## v0.4.2 (2026-04-16)

### Ci

* ci: fix codecov badge and improve upload debugging ([`a865c7a`](https://github.com/chen-star/net_alpha/commit/a865c7ab58b01746da3a135b1ce8b2b15a9f7b51))

* ci: remove [skip ci] from release commits to allow workflow triggering ([`bd3fd48`](https://github.com/chen-star/net_alpha/commit/bd3fd484f214c5f84954c848bbb542ec6219055c))

### Fix

* fix: sync internal version and trigger release automation ([`a1e8063`](https://github.com/chen-star/net_alpha/commit/a1e806369cd7e1f9a222074be9aa49e73a0ebb46))

* fix: trigger release automation verification ([`a138042`](https://github.com/chen-star/net_alpha/commit/a138042e96ac7a8b2d995944e116e7f9bb80bd21))


## v0.4.1 (2026-04-16)

### Chore

* chore: add MCP config and tax optimization suite plan ([`8234502`](https://github.com/chen-star/net_alpha/commit/823450251db8461d4b4e9f52f106ba2d97b8d61b))

### Fix

* fix: resolve linting and formatting issues to fix CI ([`5fd12d9`](https://github.com/chen-star/net_alpha/commit/5fd12d984837b3a0f1817dd65de3a58ffa10d72d))


## v0.4.0 (2026-04-16)

### Chore

* chore: update GitNexus metadata and bump version ([`47998bb`](https://github.com/chen-star/net_alpha/commit/47998bb131d3afc1b3fead9e8d717e83bbdd13c2))

### Documentation

* docs: add AI agent wrapper implementation plan

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`47c5220`](https://github.com/chen-star/net_alpha/commit/47c52208e127e5f9adacc25968380ab859535836))

* docs: add AI agent wrapper design spec

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ccf2a03`](https://github.com/chen-star/net_alpha/commit/ccf2a033003e0402a96833f8e975c6c8b0347792))

### Feature

* feat: wire agent command into CLI app and add integration smoke test ([`cba39c8`](https://github.com/chen-star/net_alpha/commit/cba39c8549f6145d21a22565baf6cd36cb3ab10a))

* feat: add agent REPL with local routing and session-start scan ([`61ecab9`](https://github.com/chen-star/net_alpha/commit/61ecab935888443e423cf2ea8853e99ee04dedba))

* feat: add ReAct loop for Claude tool-use agent ([`fcc8e08`](https://github.com/chen-star/net_alpha/commit/fcc8e085f43b1a8b30a4f84eda662a3d219cccb8))

* feat: add agent system prompt assembly ([`a9f7334`](https://github.com/chen-star/net_alpha/commit/a9f733441d8ec6e76fa98711f32546428327b657))

* feat: add agent tool executors and Claude tool schemas ([`d67be5a`](https://github.com/chen-star/net_alpha/commit/d67be5a74de65cc5a1be3456b9996d522ef32967))

* feat: add agent_api_key, agent_model, resolved_agent_api_key to Settings ([`e32e4a9`](https://github.com/chen-star/net_alpha/commit/e32e4a95bd0c37f59f20492bd59f3966b90c75c8))


## v0.3.0 (2026-04-16)

### Documentation

* docs: add CLI UX improvements implementation plan

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9fc1222`](https://github.com/chen-star/net_alpha/commit/9fc12226a4f802bdd0eb979ae235c2eb149d6880))

* docs: add CLI UX improvements design spec

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7c69862`](https://github.com/chen-star/net_alpha/commit/7c698625dbabf080ded29d61a8ccbd63efabf25b))

### Feature

* feat: show example values in schema confirmation and add post-import nudge ([`9d0c8bd`](https://github.com/chen-star/net_alpha/commit/9d0c8bdbb54dc72340c53fcda35f5df971b28f01))

* feat: add broker autocomplete and what-to-do-next panel to wizard ([`648c647`](https://github.com/chen-star/net_alpha/commit/648c647c30b79e9a1f414b5dcf719e4746383f4c))

* feat: add ticker validation with close-match suggestion to simulate sell ([`f1a2097`](https://github.com/chen-star/net_alpha/commit/f1a2097cec3a4b1cd02705efcec64d81773c3baf))

* feat: add --quiet flag to report command ([`9e4fd82`](https://github.com/chen-star/net_alpha/commit/9e4fd82b5c2d07f99075a2a1d2f19b978c142d92))

* feat: add --quiet flag, --type validation, hints, and last_check_at to check command ([`d002753`](https://github.com/chen-star/net_alpha/commit/d0027531daacf198766a90acffddb111059e0e7f))

* feat: add urgency coloring and cross-command hint to rebuys ([`6f75fa1`](https://github.com/chen-star/net_alpha/commit/6f75fa19f79b601ca79b9098824b010c6516f8ce))

* feat: color-code tax-position monetary values and add cross-command hint ([`2d2da80`](https://github.com/chen-star/net_alpha/commit/2d2da80a51789dfffd6ada28d990ff731234d51e))

* feat: add progress spinners to check, report, and import commands ([`854ba64`](https://github.com/chen-star/net_alpha/commit/854ba64f7a19ec2045deb56556ea3745f16038e9))

* feat: add net-alpha status dashboard command ([`e9be993`](https://github.com/chen-star/net_alpha/commit/e9be99349d5989bfb8c12442d898b49c45f5c5f9))

* feat: add MetaRepository for reading and writing meta key-value pairs ([`31a759f`](https://github.com/chen-star/net_alpha/commit/31a759f68a9110a5dbf4ba9f5c9164ad2ccc082f))

* feat: add print_hint and format_currency_colored output helpers

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ba78737`](https://github.com/chen-star/net_alpha/commit/ba78737f7f87d7af28d34b8b49eec581f1e4717d))

### Style

* style: normalize error message formatting across CLI commands ([`477e5a6`](https://github.com/chen-star/net_alpha/commit/477e5a664a96c912e98307d0203df21275902c9b))


## v0.2.0 (2026-04-15)

### Documentation

* docs: add tax optimization suite design spec

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c97cfe1`](https://github.com/chen-star/net_alpha/commit/c97cfe1ac2d45251c4732edf6d564f2f1a16e68f))

### Feature

* feat: enhance simulate sell with lot selection comparison

When --price is given, shows FIFO/HIFO/LIFO comparison table with
ST/LT gain/loss split, wash sale risk flags, and tax-aware
recommendation. Reuses existing wash sale check logic. ([`ab9ced7`](https://github.com/chen-star/net_alpha/commit/ab9ced771773922811d850f07ff4362d06f93e26))

* feat: add tax-position CLI command

Shows YTD realized ST/LT gains and losses, net capital position,
loss-to-zero-st, carryforward, and open lots with holding period
tracker. Sorted by days-to-long-term ascending. ([`1f2e21c`](https://github.com/chen-star/net_alpha/commit/1f2e21c524deebafeabf29b13aa747aaeaf021f2))

* feat: implement tax position engine (Tasks 3-8)

- _allocate_lots: per-(account,ticker) FIFO with realized pairs + open lots
- compute_tax_position: YTD ST/LT aggregation, year-filtered, basis_unknown counted
- identify_open_lots: sorted by days_to_long_term asc, LT lots last
- select_lots: FIFO/HIFO/LIFO across accounts with ST/LT split
- recommend_lot_method: rule-based decision tree with wash risk + fallback
- 42 tests covering all edge cases: boundaries, per-account isolation,
  basis_unknown, option exclusion, holding period, tiebreaks ([`fe59ea2`](https://github.com/chen-star/net_alpha/commit/fe59ea28d5831d561a817af3976cb4a84a9f2908))

* feat: add OpenLotFactory and RealizedPairFactory test fixtures ([`5d55480`](https://github.com/chen-star/net_alpha/commit/5d5548059108a881b7d0e376598ac702ed912509))

* feat: add domain models for tax optimization suite

Add TaxPosition, OpenLot, LotSelection, LotRecommendation,
AllocationResult, and RealizedPair to models/domain.py.
Includes computed properties for net_st, net_lt, net_capital_gain,
loss_needed_to_zero_st, and carryforward ($3,000 cap). ([`ca6cd6f`](https://github.com/chen-star/net_alpha/commit/ca6cd6f5667526bc8c6e2a5f1566981de563870a))

### Style

* style: fix lint and formatting for tax optimization suite ([`6981633`](https://github.com/chen-star/net_alpha/commit/69816330e097105285e7a000af3bfd3f7cd7fe22))

### Test

* test: fix lint and add missing tests for domain models

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c406523`](https://github.com/chen-star/net_alpha/commit/c4065237f3c1c6aa3986a5c81925400c120ffee8))


## v0.1.3 (2026-04-14)

### Fix

* fix: remove unused imports and fix import ordering in test files

Fixes CI lint failures (F401 unused imports, I001 unsorted imports) and
reformats all files to match ruff format standards.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`19ff393`](https://github.com/chen-star/net_alpha/commit/19ff39347d8cbd6569d9a6a0aff1d7fe2faed182))

### Unknown

* Update gitnexus index. ([`b6658f0`](https://github.com/chen-star/net_alpha/commit/b6658f0152eec361b86aeb1dd48a30a70febea10))


## v0.1.2 (2026-04-14)

### Chore

* chore: update GitNexus index stats ([`7345672`](https://github.com/chen-star/net_alpha/commit/734567247c059715716421b3a910d8c291fd2b6e))

### Fix

* fix: set line-length to 120 and fix remaining lint errors ([`90b47e6`](https://github.com/chen-star/net_alpha/commit/90b47e6e48d4567812ba1b68354f00af69bf5a13))

* fix: use --extra dev to install optional dev dependencies in CI ([`8d1f1cb`](https://github.com/chen-star/net_alpha/commit/8d1f1cbf95f4ecbbf6f0cf7b5a8ed9c1b1e71782))


## v0.1.1 (2026-04-14)


## v0.1.0 (2026-04-14)

### Chore

* chore: rename PyPI package to wash-alpha ([`ae94c5e`](https://github.com/chen-star/net_alpha/commit/ae94c5e53218d09d8f335b9f4bbe5cf2695193f8))

* chore: add python-semantic-release config ([`5d89abc`](https://github.com/chen-star/net_alpha/commit/5d89abc88171c4d2790749dbe257d0bb0bd70053))

* chore: add .gitignore with worktrees and Python artifacts ([`0936286`](https://github.com/chen-star/net_alpha/commit/0936286d95c864464d363badcf63db93e68bd2d9))

### Ci

* ci: add explicit tag push step; gate codecov upload to py3.11 ([`73c586a`](https://github.com/chen-star/net_alpha/commit/73c586a0e912c6f473c0969cbe2ed19e3b31c100))

* ci: add release workflow (hatch build, PyPI OIDC publish, GitHub Release) ([`b9590ce`](https://github.com/chen-star/net_alpha/commit/b9590cecc12489b40a874545f454faaf71097e5b))

* ci: pin python-semantic-release to v8 range ([`5fdc4a4`](https://github.com/chen-star/net_alpha/commit/5fdc4a49590dd1c855bfd2f9970ef6f745f7428b))

* ci: add version bump workflow (conventional commits + manual override) ([`919df11`](https://github.com/chen-star/net_alpha/commit/919df111234c1635c215175512a9fa4bf492b92c))

* ci: add CI workflow (lint, test, coverage on push/PR/nightly) ([`50cd408`](https://github.com/chen-star/net_alpha/commit/50cd408048c31d43c3105cb9e3a40cad88c77bbc))

### Documentation

* docs: update spec with wash-alpha package name ([`d6f1a72`](https://github.com/chen-star/net_alpha/commit/d6f1a722a8760d644d68d0d1bdc005b2387c1ee8))

* docs: update plan with wash-alpha package name ([`6ffac86`](https://github.com/chen-star/net_alpha/commit/6ffac86c11c2bc2f04a10bb50640efdbf5ae5ba4))

* docs: add CI, PyPI, and coverage badges to README ([`1aa70c7`](https://github.com/chen-star/net_alpha/commit/1aa70c7551ce9808d7de310768d10f5e33f2c107))

* docs: add CI/CD release implementation plan

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8b3b969`](https://github.com/chen-star/net_alpha/commit/8b3b969a363c4b789f8f23bc8652805897deb5d4))

* docs: add CI/CD, release publishing, and PyPI packaging design spec

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f895ca3`](https://github.com/chen-star/net_alpha/commit/f895ca33e9f293fcc50dddcfcc37a28a94b7f91a))

* docs: add integration test suite implementation plan

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`85a671b`](https://github.com/chen-star/net_alpha/commit/85a671ba0060eca8ddd8a31ee8c6eaad3c021e5b))

* docs: add integration test suite design spec

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`079587b`](https://github.com/chen-star/net_alpha/commit/079587b139853c4a8b2e00677ffb981236a4e591))

### Feature

* feat: add first-run interactive wizard

Implements the interactive wizard that runs on first launch, prompting
for an Anthropic API key, importing broker CSVs, and running an initial
wash sale check.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`152c161`](https://github.com/chen-star/net_alpha/commit/152c161851b4c27d524cca17cc044d1930e50ab7))

* feat: add annual wash sale report command with CSV export

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`52b84fd`](https://github.com/chen-star/net_alpha/commit/52b84fdf1556ea58cc41f6c38d2171a5ce8059a3))

* feat: add safe-to-rebuy tracker command ([`f9cc4a3`](https://github.com/chen-star/net_alpha/commit/f9cc4a38392935b124143cfc88aef02a259ba87f))

* feat: add simulate sell command with look-back detection

Adds `net-alpha simulate sell &lt;ticker&gt; &lt;qty&gt; [--price P]` that checks
the 30-day look-back window for existing buys that would trigger a wash
sale, shows the triggering trade with confidence label and safe-to-sell
date, and estimates the disallowed loss when a price is provided.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f9cc536`](https://github.com/chen-star/net_alpha/commit/f9cc536eea55976be3d3b2f7866a302a717eb45f))

* feat: add check command with summary, detail, and staleness warnings

Implements `net-alpha check` with year/ticker/type filtering, per-account
staleness warnings, wash sale summary table, violation detail table,
rebuy hint, and basis-unknown/option-expiration caveats.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2238af5`](https://github.com/chen-star/net_alpha/commit/2238af5c14ddc657124d8011cf4d3e75b334f9f2))

* feat: add CSV import command with schema confirmation ([`d65e17b`](https://github.com/chen-star/net_alpha/commit/d65e17b24753ededd8d89ddac8ce1a9ccb9bfc9a))

* feat: add Typer app entry point with DB bootstrap ([`3ede198`](https://github.com/chen-star/net_alpha/commit/3ede19850f9cc692513a9be3d6792b751afe3dfd))

* feat: add CLI output helpers and disclaimer ([`b4eb9af`](https://github.com/chen-star/net_alpha/commit/b4eb9af6b2d84f97629165378307588334d68650))

* feat: add main import orchestrator

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2a51c8e`](https://github.com/chen-star/net_alpha/commit/2a51c8e04210c1d85831a147dc5a04c472a2a454))

* feat: add trade deduplication with hash and semantic key signals

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9011a19`](https://github.com/chen-star/net_alpha/commit/9011a19d7b7edb32e8c030b579a89ee69c6e76ac))

* feat: add CSV reader with schema mapping and option parsing

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`539ef2e`](https://github.com/chen-star/net_alpha/commit/539ef2e2c9bfd08b1f0472165e683e55956ab344))

* feat: add LLM schema detection with retry and exponential backoff

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3806ce1`](https://github.com/chen-star/net_alpha/commit/3806ce12ef4c3b9a05b2d273f48ce1176d461e93))

* feat: add option symbol regex parsers (OCC, Schwab, Robinhood)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7aa4ef7`](https://github.com/chen-star/net_alpha/commit/7aa4ef717c8b1caed00fc0da3dadada3391029cf))

* feat: add row anonymizer for LLM schema detection

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`65c88ab`](https://github.com/chen-star/net_alpha/commit/65c88ab982addb2191bc9fc518b84efbbe1a279a))

* feat: add repositories with domain ↔ table mapping

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5fc36db`](https://github.com/chen-star/net_alpha/commit/5fc36dbc9e865aa4cc56e08b4b5a844d629cd912))

* feat: add schema migration framework with v0→v1

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a8d9f42`](https://github.com/chen-star/net_alpha/commit/a8d9f4259f5b9fcf1215648f279c1953ab90862f))

* feat: add DB connection and init with schema versioning

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9aeda37`](https://github.com/chen-star/net_alpha/commit/9aeda372a88326d8965038393dde1bb8a10c2e25))

* feat: add SQLModel table classes for all entities

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4606271`](https://github.com/chen-star/net_alpha/commit/4606271e32932572a1d131fc43131af2180864f2))

* feat: add Settings config via pydantic-settings

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`55b0e98`](https://github.com/chen-star/net_alpha/commit/55b0e980f9bc3096a8fc21bb3e049662d00a389a))

* feat: implement core wash sale detection engine ([`48237e6`](https://github.com/chen-star/net_alpha/commit/48237e65604d172f303f4405577101ea192b003c))

* feat: add ETF pairs loader with user override support ([`d00a3ec`](https://github.com/chen-star/net_alpha/commit/d00a3ece9b136ecb250290cea6c761897d2a90d2))

* feat: implement equity match confidence with ETF pair support

- Add get_match_confidence for all equity/option/ETF scenarios
- Tests cover confirmed, probable, unclear, and no-match cases ([`c32ea31`](https://github.com/chen-star/net_alpha/commit/c32ea318649ab69c073bcafa7fa7bb81cb35b53b))

* feat: implement 30-day wash sale window check ([`fb5c122`](https://github.com/chen-star/net_alpha/commit/fb5c122f4fadfa5f8c6b8168096831c72162a5cb))

* feat: add factory_boy test fixtures for Trade and Lot ([`b447115`](https://github.com/chen-star/net_alpha/commit/b4471156d53460e6a1c9ecd4ac22d52456295459))

* feat: add Lot, WashSaleViolation, and DetectionResult models ([`384e90a`](https://github.com/chen-star/net_alpha/commit/384e90ada3719ad89313ecf27a1bf1808361c082))

* feat: add Trade and OptionDetails domain models ([`8a3039f`](https://github.com/chen-star/net_alpha/commit/8a3039f4b65c59fc6faa2d77a1df35abb8564964))

* feat: initialize project structure with uv and hatch ([`4acbeff`](https://github.com/chen-star/net_alpha/commit/4acbeff7992804852327849ea5d3d2a389833c0b))

### Fix

* fix: resolve ruff linter warnings in Plan 1 source files

Replace Optional[X] with X | None, fix line-length violations,
and clean up unused imports across domain model, matcher, and tests.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2f71493`](https://github.com/chen-star/net_alpha/commit/2f71493b729425045d8d7efdc3f817f612ced1c7))

### Test

* test: complete integration test suite — CLI and engine tiers ([`89a09b5`](https://github.com/chen-star/net_alpha/commit/89a09b51da4a5bb23b2898400f99f95ff87aae6f))

* test: add CLI integration tests for report command ([`d02147b`](https://github.com/chen-star/net_alpha/commit/d02147bfcfcc493e3bc88deb1353fd7458eef5ae))

* test: add CLI integration tests for rebuys command ([`4317a7b`](https://github.com/chen-star/net_alpha/commit/4317a7b2972307b584e19ed00837fe14974bc86c))

* test: add CLI integration tests for simulate sell command ([`f11a7e9`](https://github.com/chen-star/net_alpha/commit/f11a7e96767018aa7f32e095af2b3f997e9fcc98))

* test: add CLI integration tests for check command ([`ef01988`](https://github.com/chen-star/net_alpha/commit/ef01988211f5fe17f9f412738c8edb79186faf62))

* test: add CLI integration tests for import command ([`4f466b1`](https://github.com/chen-star/net_alpha/commit/4f466b131ec8c2ff4bc0d50d05f5ddb45cfbe714))

* test: add engine integration tests for wash sale detector ([`6e35aff`](https://github.com/chen-star/net_alpha/commit/6e35affe4623fa3e8e79c5129227ad64d94acc76))

* test: add engine integration tests for import pipeline ([`a8c05d5`](https://github.com/chen-star/net_alpha/commit/a8c05d50ed4c2fb6e1d4908649832bbaf461354c))

* test: add engine integration tests for import pipeline

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`745d546`](https://github.com/chen-star/net_alpha/commit/745d546b544b1ee5e383f822d6973d8b52f18d1e))

* test: add CLI integration conftest with patched _bootstrap ([`f9b02ae`](https://github.com/chen-star/net_alpha/commit/f9b02ae779796a2b2be8d69967f60dbd7cac59cf))

* test: scaffold integration test directory and shared conftest ([`66975f0`](https://github.com/chen-star/net_alpha/commit/66975f01f52a0a38b2ce3a4b28c1bb0e1860d99b))

* test: add golden file integration tests for Schwab and Robinhood CSV

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a1c3e14`](https://github.com/chen-star/net_alpha/commit/a1c3e148726fc91916505d2c4ab1a2f3a610e96b))

* test: add Lot, Violation, and SchemaCache repository tests

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a086464`](https://github.com/chen-star/net_alpha/commit/a08646430f6229f59b4b4319522f503d290cff9f))

* test: options and ETF wash sale detection scenarios ([`c8a5519`](https://github.com/chen-star/net_alpha/commit/c8a551905348a6fe2cda06c1d2c36987cc2716ee))

* test: cross-account, cross-year, basis_unknown, and edge cases ([`6bc1eb7`](https://github.com/chen-star/net_alpha/commit/6bc1eb7a683b529ada18278a39878fada67b862b))

* test: FIFO allocation, partial wash sales, and basis adjustment ([`43f4282`](https://github.com/chen-star/net_alpha/commit/43f4282cf85bc993f750647469d9614b01c6325a))

### Unknown

* Delete liscense in README.md. ([`e7d88c9`](https://github.com/chen-star/net_alpha/commit/e7d88c9cbf0d2116c215a0bf1427fa321619e9c3))

* Add README.md. ([`3cda8e5`](https://github.com/chen-star/net_alpha/commit/3cda8e5b830adba74f38fc2a759167a3816c8300))

* Enable gitnexus ([`06d1fd5`](https://github.com/chen-star/net_alpha/commit/06d1fd575036a69b3f58fce09d53ef85bc8cac91))

* Add v1 plan ([`c9953f2`](https://github.com/chen-star/net_alpha/commit/c9953f2d4cd0dd5a6b61ca93db2eed44d6d15a01))

* Add spec for v1. ([`2075855`](https://github.com/chen-star/net_alpha/commit/20758558510ca5dbb9061a5fc99600db2e1ee8d8))

* Add product &amp; UX design spec for net_alpha v1

Resolves all open questions from PRD v0.2. Covers feature scope,
command structure, UX flows, confidence label simplification (4→3 tiers),
and new safe-to-rebuy tracker feature.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`dcafcef`](https://github.com/chen-star/net_alpha/commit/dcafcef727b66f8c9e06c6b711457bcc33bf1346))

* init PRD.md ([`9d87db8`](https://github.com/chen-star/net_alpha/commit/9d87db828384b6b034d80650111d1fb9a84e1bb3))
