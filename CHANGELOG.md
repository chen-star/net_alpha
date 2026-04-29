# CHANGELOG

## [unreleased] — Tax Correctness 1.0

### Added
- §1256 contract awareness: broad-based index options (SPX/NDX/RUT/VIX/OEX/XSP/MXEF/MXEA) are now exempt from §1091 wash-sale detection per IRC §1256(c). Bundled in `section_1256_underlyings.yaml`; user can extend via `~/.net_alpha/section_1256_underlyings.yaml`.
- §1256 60/40 LT/ST classification on closed contracts (`section_1256_classifications` table).
- Inline-expandable wash-sale and exempt-match explanations (web UI HTMX fragment + CLI `--detail`). Includes rule citation, source trades, match reason, disallowed-amount math, confidence reasoning, adjusted-basis target.
- `/tax?view=performance` tab — after-tax realized P&L, tax-drag, ST/LT/§1256 mix bar, wash-sale cost line, effective tax rate. Reuses existing `tax:` config plus a new `niit_enabled` toggle.

### Changed
- `TaxBrackets` model gains `niit_enabled: bool = True`.
- `DetectionResult` gains `exempt_matches: list[ExemptMatch] = []`.
- `Trade` model gains `is_section_1256: bool = False`.

### Migration (v10 → v11)
- New tables: `exempt_matches`, `section_1256_classifications`.
- New column: `trades.is_section_1256`.
- One-shot recompute on first launch reclassifies prior wash-sale violations on §1256 contracts as exempt matches; populates §1256 classifications. Banner surfaces counts.

### Out of Scope
- Open §1256 position year-end mark-to-market (consult 1099-B / Form 6781).
- Form 6781 export (deferred to unified tax-export spec).
- Capital-loss $3K cap and multi-year carryforward modeling.
- MAGI-based NIIT threshold (assumed exceeded when toggle on).
- Per-year historical tax brackets (Lifetime period uses current rates).

### Rollback
Not offered. Restore from manual SQLite backup if needed.


## v0.32.1 (2026-04-29)

### Fix

* fix(web): Closed positions tab renders historical realized lots

The Positions → Closed tab was a hard-coded &#34;Coming in Phase 2&#34; placeholder.
The data layer (RealizedGLLot model, get_gl_lots_for_account) was already
in place; the view, route branch, and aggregator were never wired up.

- Add Repository.list_all_gl_lots() returning every lot across accounts,
  sorted by close date desc.
- Add ClosedLotRow dataclass + compute_closed_lots() aggregator with
  period (YTD/year/lifetime) + account filtering. Realized P/L =
  proceeds − cost_basis.
- Branch routes/positions.py on selected_view == &#34;closed&#34; mirroring the
  at-loss pattern, including HTMX fragment response.
- Replace _positions_view_closed.html placeholder with a real table:
  Symbol · Acct · Qty · Basis · Proceeds · Realized · Opened · Closed ·
  Holding (LT/ST). Wash-sale lots show a &#34;W&#34; chip with disallowed-loss
  tooltip. Empty state nudges the user toward Settings → Imports.

Tests: 14 new (11 aggregator unit + 3 route smoke) covering realized P/L
sign, period filter, account filter, sort order, term passthrough, wash-sale
fields, option vs equity display_symbol, empty input.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`d93e226`](https://github.com/chen-star/net_alpha/commit/d93e226792a2b8c2673277ae1804cc2568398526))


## v0.32.0 (2026-04-29)

### Feature

* feat(snapshots): expand WIDTHS to 4 viewports; recapture 32 baselines (§F1)

Add laptop (1024×768) and desktop-wide (1440×900); refit desktop to
1280×800.  Rewrite tablet/desktop baselines in place; add 16 new
laptop/desktop-wide PNGs.  32 pass in verify mode, 0 diff leaks.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bbd1e0a`](https://github.com/chen-star/net_alpha/commit/bbd1e0ab5a96db9fc1eae319fef8eab0ed3f6b16))

* feat(web): ticker tabs gain aria-controls + role=tabpanel (I4)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0bbca74`](https://github.com/chen-star/net_alpha/commit/0bbca7422b5779c9a772b6c770ee560a3852df15))

* feat(web): side pane + Settings drawer go full-width at narrow widths (§3.9)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a367995`](https://github.com/chen-star/net_alpha/commit/a3679950020a8abafdafe01f3239fbdca612e4cc))

* feat(web): wide tables get overflow-x-auto wrapper at narrow widths (§3.9)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c4e83f9`](https://github.com/chen-star/net_alpha/commit/c4e83f96261cc153cc48c16258df1d260f043f92))

* feat(web): KPI grids reflow at 768/1024 (§3.9)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1253863`](https://github.com/chen-star/net_alpha/commit/1253863b12277d9539641b4d362b8b6c7571e8b4))

* feat(web): drop width=1024 viewport, add &lt; 768 banner (§3.9) ([`8b5cfca`](https://github.com/chen-star/net_alpha/commit/8b5cfcacfd9e616c3e7ddb5756c869dd3fbfe7bf))

### Fix

* fix(web): Phase 5 review fix-pack

- Wrap 4 missed tables in overflow-x-auto (_schwab_lot_detail,
  _reconciliation_diff, _detail_table, _provenance_modal)
- Hide topbar below md (banner-only at &lt; 768 per spec §3.9)
- Update test_baseline_screens.py docstring for 4-width matrix
- Recapture tablet snapshots affected by topbar visibility

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9fd2a72`](https://github.com/chen-star/net_alpha/commit/9fd2a72e19280e6e08966c395b9747ec94fd9151))

### Test

* test(web): smoke every page returns 200 (Phase 5) ([`9afcd9c`](https://github.com/chen-star/net_alpha/commit/9afcd9c10a7ed33b4b9eee5e097a80b9e8a12276))

### Unknown

* Merge branch &#39;phase5-responsive&#39; — Phase 5 Responsive (iPad-width usable)

Phase 5 of the UI/UX redesign (spec §3.9, §7).

- Drop width=1024 viewport, add &lt; 768 banner
- KPI grids reflow at 768/1024 (12-col → stacked → 4-col)
- Wide tables get overflow-x-auto wrappers
- Side pane and Settings drawer go full-width below md/lg
- Ticker tabs gain aria-controls + role=tabpanel (I4 carry-over)
- Hide topbar below md (banner-only at &lt; 768)
- Snapshot suite expanded to 768/1024/1280/1440 (32 baselines)
- 768 smoke tests for every page

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`32d8f6c`](https://github.com/chen-star/net_alpha/commit/32d8f6ccb45a98504865a0d50a9790bb286aa4c7))

* plan(web): Phase 5 — Responsive (iPad-width usable)

Sections A-F: viewport drop, KPI grid reflow, table overflow-x,
side pane/drawer full-width, ticker a11y polish, snapshot suite
at 768/1024/1280/1440 + 768 smoke tests.

Refs: docs/superpowers/specs/2026-04-28-ui-ux-evaluation-design.md §3.9, §7.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`a22edc7`](https://github.com/chen-star/net_alpha/commit/a22edc71b4f953ec4c2afc77acab660e86a11802))


## v0.31.0 (2026-04-29)

### Feature

* feat(web): keyboard shortcut layer (g o/p/t/s, ?, ,) + cheatsheet (§3.7)

Adds a small self-contained keydown listener (keyboard.js) that wires:
- g o / g p / g t / g s — navigate to Overview / Positions / Tax / Sim
- ? — open the keyboard cheatsheet modal
- , — open the settings drawer (event already wired in Phase 1)

The handler ignores events from inputs/textareas/selects/contenteditable
so typing inside forms is unaffected. Esc-close for drawers/panes is
already handled by Alpine and is not duplicated here.

Adds nav-link aria-keyshortcuts attributes for assistive tech.
Adds a .kbd token style and the cheatsheet modal (Alpine x-data).

Section G3 of Phase 4 plan. ([`caab763`](https://github.com/chen-star/net_alpha/commit/caab7631dc693ea99fe0c8082fb23e9af4a802c9))

* feat(web): apply --ring-focus to all interactive elements (§5.14)

Adds a single :focus-visible block that applies the --ring-focus token
(0 0 0 2px rgba(94,92,230,0.6)) to every interactive primitive:
.btn, .btn-ghost, .tab, .chip, .nav-link, native button, and form
inputs. Outlines are nullified so the indigo halo is the canonical
keyboard-focus indicator.

Section G2 of Phase 4 plan. ([`791cc91`](https://github.com/chen-star/net_alpha/commit/791cc914577905f86adeb429040d5e0b30be1f3f))

* feat(web): main container 1280px → 1536px (max-w-screen-2xl) (H8)

Bumps the main and footer containers from max-w-[1280px] to
max-w-screen-2xl (1536px) to give the wider Positions table and
Tax view more horizontal room. Snapshot baselines will be
re-captured in Section H. ([`2210e22`](https://github.com/chen-star/net_alpha/commit/2210e22ae1c0f04e0eb4e545deb5a2d47a5110a1))

* feat(web): options panel header is a 3-card mini-summary (H7)

/holdings/options now passes options_summary (open_contracts, net_premium,
avg_dte) to _portfolio_open_options.html. Net premium signs short premium
received as a credit and long cost paid as a debit; avg DTE is qty-weighted.
The 3-card grid renders above the row list, mirroring the kpi-numeric
pattern used elsewhere. ([`3a8b20d`](https://github.com/chen-star/net_alpha/commit/3a8b20dcc445378031012341efb363b255bedb3f))

* feat(web): LT/ST mixed shows as single &#39;lt+st&#39; chip in Account column (H5)

Adds account_chip (joined sub-account suffixes) and account_displays
(full labels) to PositionRow. Single-account rows render the label in
mono; multi-account rows render a single chip whose tooltip lists
every full label. ([`184bdda`](https://github.com/chen-star/net_alpha/commit/184bdda691170e4577ad6edb5360f666f1a79be1))

* feat(web): all quantity cells use fmt_quantity (H2)

Replaces &#34;%.4f&#34;|format(r.qty) and &#34;%g&#34;|format(r.lt_qty|float) ST splits
with fmt_quantity, so whole shares render as integers and fractional
quantities trim trailing zeros consistently with other tables. ([`4847c17`](https://github.com/chen-star/net_alpha/commit/4847c172729be8a5db1eb39f48f40f6e3b6cddc2))

* feat(web): missing-basis chip + em-dash empties on Positions table (H1)

Adds PositionRow.basis_known derived from any open lot having non-null,
non-zero cost_basis. The Positions table now renders the new chip
&#39;⚠ basis missing&#39; when basis is provably missing on an open position
instead of showing $0.00, and falls back to fmt_currency (em-dash for
None) elsewhere. ([`5f4e1d7`](https://github.com/chen-star/net_alpha/commit/5f4e1d767358dac372e8f191c468d5a71327136a))

* feat(web): inline Set-basis chip on Timeline rows missing basis (Tk5)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`c43c384`](https://github.com/chen-star/net_alpha/commit/c43c384f7ee50cbe3f4ee438b7debbfdd14995e6))

* feat(web): /ticker accepts ?view=timeline|lots|recon and serves fragments (Tk4) ([`8b41417`](https://github.com/chen-star/net_alpha/commit/8b41417f012629a9069c787dc403372cb0c39028))

* feat(web): /ticker uses Timeline / Open lots / Broker reconciliation tabs (Tk4) ([`6efa53d`](https://github.com/chen-star/net_alpha/commit/6efa53deacd2b15ff2836d60999ccb00327403ab))

* feat(web): reconciliation /reconciliation accepts variant=badge for Ticker KPI (Tk3)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`50d73bc`](https://github.com/chen-star/net_alpha/commit/50d73bcdd17ad91416c72755063184251e7317d6))

* feat(web): ticker KPIs use sans + fmt_currency; mono only on identifiers (Tk1)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`fd50318`](https://github.com/chen-star/net_alpha/commit/fd503184387b75d386c29f16bde7c23a67076651))

* feat(web): ticker page h1 is sans Inter, white (Tk1, Tk2)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`86da6b8`](https://github.com/chen-star/net_alpha/commit/86da6b81f0769c6b4bcfac9c1fbf45e6c7401ee7))

* feat(web): calendar strip shows N events YTD (N3) ([`d599c58`](https://github.com/chen-star/net_alpha/commit/d599c5874089c9f3df3fb36b82fda04102c74e57))

### Fix

* fix(web): keyboard.js state machine + Realized P/L $0 color

keyboard.js: prior matcher used pending.endsWith(seq.replace(&#39; &#39;,&#39;&#39;)),
so typing &#39;good&#39; or &#39;tags&#39; triggered nav. Replace with an explicit
&#39;awaiting g&#39; state machine so only true g-prefixed chords fire.

ticker.html: Realized P/L (YTD and Lifetime) used &gt;= 0 as the green
threshold, painting $0.00 green. Mirror the Disallowed pattern: &gt; 0
positive, &lt; 0 negative, else neutral text-label-2.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`677fa94`](https://github.com/chen-star/net_alpha/commit/677fa94ee3a171a391fc077b0d0b1653ec50205b))

* fix(web): inline Set basis chip swaps the basis cell, not affordance cell

The chip lived in the BASIS td but its hx-target pointed at the
affordance cell two columns over, leaving the warning chip stuck after
save. Add id=&#34;trade-basis-{id}&#34; to the basis td, retarget the chip
form, and update the timeline-caller branch of /audit/set-basis to
return matching markup including the saved cost-basis value.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`ca807c2`](https://github.com/chen-star/net_alpha/commit/ca807c256e7ee8b5dc532bedd6f94e970062ba4d))

* fix(web): drop HTMX swap on ticker tabs to preserve active state

Tabs server-render the active class from selected_view, but HTMX swap
only replaced inner content, leaving the highlight stuck on the old tab.
Convert to plain &lt;a&gt; nav matching the _positions_tabs.html pattern. The
route already returns full HTML for non-HX requests.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`727d456`](https://github.com/chen-star/net_alpha/commit/727d4563b88f7fd87dd68aa7657069a567d47ef9))

* fix(web): wash-sale filter chips × is clickable, drops that filter (N2) ([`709e26c`](https://github.com/chen-star/net_alpha/commit/709e26c94ecbbba758687c00733770c415008126))

* fix(web): sim Account label flips to (required) when Sell selected (N1) ([`72a9d5c`](https://github.com/chen-star/net_alpha/commit/72a9d5ca3fdd3ea478f332084e8b13afda179528))

* fix(web): projection form swap is outerHTML to avoid self-nesting (I1) ([`0e0a11e`](https://github.com/chen-star/net_alpha/commit/0e0a11e9ef6c6b1c3bb9d7c9e7d3a7b5c8732201))

* fix(web): hero subhead &#39;vs contributed&#39; now equals total − net_contributed (I2)

Adapted to actual codebase field name: cash_kpis.net_contributions (not
net_contributed). Both kpis_fragment and body call sites now compute
total_account_value - cash_kpis.net_contributions instead of
period_realized + period_unrealized. ([`ca3a16a`](https://github.com/chen-star/net_alpha/commit/ca3a16accab720ab07c74d07a116bb9cf83a928d))

### Refactor

* refactor(web): promote text-label-3 → text-label-2 on load-bearing copy (§5.14)

Per §5.14, label-3 is reserved for decorative dividers and disabled
affordances. Bumps load-bearing copy (KPI sub-lines, panel sub-headers,
source labels, &#34;Loading…&#34; placeholders, event-count spans, harvest
queue origin lines, profile descriptions, etc.) to label-2.

Decorative `·` separators, em-dash placeholders for missing values,
disabled pagination buttons, and chevron affordances stay at label-3.

Section G1 of Phase 4 plan. ([`f95b2f1`](https://github.com/chen-star/net_alpha/commit/f95b2f11202cdfb6c28ed58674bb052834971e40))

* refactor(web): open-options bar shows P/L only; DTE is a separate badge (H6)

The time-elapsed bar already represents only one metric (not P/L,
which would require live option quotes we don&#39;t fetch). Per the
H6 split, DTE becomes a discrete badge-muted with the existing
text-warn / text-label-1 / text-label-2 colorization preserved
based on time-to-expiry, so the row&#39;s right column reads as a
standalone badge instead of a number with inline subscript. ([`b29c688`](https://github.com/chen-star/net_alpha/commit/b29c688317a686dcbc276c555cac54a28b73787e))

* refactor(web): rename CASH SUNK/SH → &#39;Cash invested / sh&#39; + tooltip (H3)

Header now uses Title Case, plain English, with a clarifying tooltip on
how the per-share number is derived (and that wash adjustments are
included). ([`c9b21b9`](https://github.com/chen-star/net_alpha/commit/c9b21b91fa18ddbd6cd88fc2f4ffb103307ecc66))

* refactor(web): drop above-table recon strips; badge + tab replace them (Tk3)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`54f8760`](https://github.com/chen-star/net_alpha/commit/54f8760e9da524028050ea362c39434336d167f2))

### Test

* test(web): smoke tests for Phase 4 ticker tabs + recon badge variant

Cover the new query-param round-trip on /ticker/&lt;sym&gt;?view=, the
HX-Request fragment-only response, and the variant=badge branch on
/reconciliation/&lt;sym&gt;. Tests are tolerant of unseeded data so they pass
in the default conftest.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`469ffd7`](https://github.com/chen-star/net_alpha/commit/469ffd78496ec8f626e9c3559b4b4ad9a5b624f5))

* test(web): re-capture snapshot baselines after Phase 4 visual sweep ([`232646d`](https://github.com/chen-star/net_alpha/commit/232646ddb0f95faf4b2a3eedbbafc4751ade1e04))

### Unknown

* Merge branch &#39;phase4-ticker-visual&#39; — Phase 4 Ticker page + visual sweep ([`45fef5c`](https://github.com/chen-star/net_alpha/commit/45fef5cf55301f364e0597412c2bfc5ffaf5d598))

* plan(web): Phase 4 — Ticker page + visual sweep ([`1a8becc`](https://github.com/chen-star/net_alpha/commit/1a8beccf03bf5ee1726073f1eb477105dd55a57a))


## v0.30.0 (2026-04-29)

### Chore

* chore(web): delete dead _harvest_tab.html (Phase 1 redirected away; Phase 2 review #I6)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cbbd3f8`](https://github.com/chen-star/net_alpha/commit/cbbd3f8bce234d65e5d224d3a7309e97c951c59e))

### Documentation

* docs(plans): Phase 3 — Page polish implementation plan

Covers Overview clutter removal + chart fixes + KPI restructure with
Today tile; Tax page polish (mini-bar, budget bar, watch/violations
labels, affirmative empty copy, filter chips, calendar strip); inline
tax-projection form replacing the YAML snippet; Imports drawer
one-explanation card + per-row inline form + drop-zone preview; Sim
account-required validation + recent-sims-this-session panel; plus
the Phase 2 review backlog (at-loss summary enrichment, bare-except
removal, dead _harvest_tab.html, realized_delta dedup).

Approximately 17 tasks across 8 sections (A–H). Section H is the
verification gate; sections A–G ship working features incrementally.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`5fea57a`](https://github.com/chen-star/net_alpha/commit/5fea57ae7b89f029ca061ebfe72c03d2a7ba9d53))

### Feature

* feat(web): /sim — recent sims this-session panel (S2)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`98e75f5`](https://github.com/chen-star/net_alpha/commit/98e75f5964389494a1fa22ad872bedd22be21125))

* feat(web): /sim — account required for action=Sell with inline error (S3)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`84266ec`](https://github.com/chen-star/net_alpha/commit/84266ecf3ecac619175efa5e4d46a28e18ed0a85))

* feat(web): drop-zone preview on drag-over (I4)

Adds drop_zone.js (vanilla JS) that listens to dragenter/dragover on any
element wrapping a [data-drop-zone] file input and shows a sibling
[data-testid=&#34;drop-zone-preview&#34;] element with the incoming file count.
Wires data-drop-zone onto the CSV upload input and adds the preview div
to _drop_zone.html; loads the script via base.html.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0d6862b`](https://github.com/chen-star/net_alpha/commit/0d6862b605b156c1139c1fb4c29581c434c34726))

* feat(web): drawer Imports — one-explanation card + per-row inline form (I1, I2)

Restructures the data-hygiene section: basis_unknown rows now render a
single shared explanation card (I1) and one compact HTMX inline form each
(I2, caller=drawer).  Adds MissingBasisRow helper to hygiene.py and wires
collect_missing_basis_rows into the imports route context.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f3bbf81`](https://github.com/chen-star/net_alpha/commit/f3bbf81e985a490e3fe1ef9a6b6f11ea43db9955))

* feat(web): inline tax-projection form replaces YAML snippet (Pr1, Pr2)

Add write_tax_config() to config.py, POST /tax/projection-config route
that persists to config.yaml and hot-reloads app.state, _projection_form.html
with HTMX-wired form, and updated _projection_tab.html / _projection_card.html
to remove the manual YAML-snippet copy.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3e8e6f0`](https://github.com/chen-star/net_alpha/commit/3e8e6f062f639c36e3ceacc32fa3aba5a6fd4ded))

* feat(web): tax filter chips with reset (W2); calendar strip always visible (W3)

- _tax_wash_sales_tab.html: add filter chip summary row with
  data-testid=&#34;filter-reset&#34; (W2) and always-visible compact month-header
  strip with data-testid=&#34;calendar-strip&#34; (W3)
- app.src.css: add .chip utility class for filter-bar chips
- app.css: rebuilt

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0c6fd84`](https://github.com/chen-star/net_alpha/commit/0c6fd846edeac5246c7f3770983f9b8a72dca0d3))

* feat(web): wash-watch labeled forward; violations labeled backward, affirmative empty (W1, W1b)

- _portfolio_wash_watch.html: heading now reads &#34;Wash-sale watch ·
  forward-looking 30d&#34;
- _tax_wash_sales_tab.html: violations section gets &#34;Violations ·
  backward-looking detected&#34; heading before the detail table
- _detail_table.html: empty state replaced with affirmative &#34;✓ No
  wash-sale violations detected&#34; copy instead of generic &#34;No violations
  match these filters.&#34;
- test_detail_routes.py: updated to match new empty-state copy

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ae288a9`](https://github.com/chen-star/net_alpha/commit/ae288a9e988f9de55cd0a02fb6f79a06461384b6))

* feat(web): tax realized-P/L stacked mini-bar (T5)

Add realized_kpis (OffsetBudget) to _wash_sales_context so the tax
wash-sales tab can render a split loss/gain mini-bar. The bar shows
realized_losses_ytd vs realized_gains_ytd; degrades to an empty-state
message when no P/L has been realized this period.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3ff413d`](https://github.com/chen-star/net_alpha/commit/3ff413d7bd7b03aff761d92cbbd11949943fd407))

* feat(web): loss-harvest budget bar (T4)

Add data-testid=&#34;offset-budget&#34; to the tile wrapper and
data-testid=&#34;offset-budget-bar&#34; to the existing progress bar in
_offset_budget_tile.html so tests can assert the bar is present.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9269df3`](https://github.com/chen-star/net_alpha/commit/9269df30c87f95e8861f8747da860dd93034b141))

* feat(web): Overview KPI grid — hero + today + cash (3 large) over 4 small (P2/P4/NEW)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`395e813`](https://github.com/chen-star/net_alpha/commit/395e8136418a6a19f8c4a6300095e0dd33265bc3))

* feat(portfolio): compute_today_change for the Overview Today tile (P3 prep)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f5e1722`](https://github.com/chen-star/net_alpha/commit/f5e17223ac71ce72222344b938ba8e22df085465))

* feat(pricing): Quote exposes previous_close for the Today tile (Phase 3 prep)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`95a837c`](https://github.com/chen-star/net_alpha/commit/95a837c5620c42f1816fae547b6a39e108085b43))

* feat(web): freshness chip in toolbar — drop in-tile cached-prices copy (P5)

Add compute_price_freshness helper (portfolio/freshness.py) that maps a
PricingSnapshot to a green/amber/red tier and label (&lt; 15m / 15m–24h /
&gt; 24h). Wire it into the / route and render a data-testid=&#34;freshness-chip&#34;
button in the toolbar. Remove the inline &#34;Cached prices…refresh&#34; copy from
the KPI tile footer — the chip is now the single freshness surface.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a7d594a`](https://github.com/chen-star/net_alpha/commit/a7d594a07e038e4a1ac796f451821da0fea293ea))

* feat(web): drop Portfolio section header and Tax planning footer (P1, P9)

Remove redundant &#34;Portfolio&#34; section-header div from the body fragment
and drop the Tax planning footer panel (offset budget + year-end
projection) from the Overview page — those panels belong on /tax.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`08ac60c`](https://github.com/chen-star/net_alpha/commit/08ac60c83a578db93a8738a74f8c85266d412ccb))

* feat(web): at-loss summary strip — total unrealized, harvestable count, replacements count (Phase 2 review #I3)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`19d1706`](https://github.com/chen-star/net_alpha/commit/19d1706e501683b10c803b23cf2e968abef7d224))

### Fix

* fix(web): sim error swap targets sibling div, not #sim-result; refresh stale hygiene copy

C3: G1&#39;s account-required validation re-rendered the entire sim.html
into HTMX&#39;s #sim-result target, producing nested &lt;html&gt;/&lt;body&gt; and
double navbars. Switched to an OOB swap into a new #sim-form-error
sibling of the account select; #sim-result clears via the empty
main-response. Removed the old {% if form_error %} block from inside
the form that is now superseded by the OOB swap.

I3: hygiene.py&#39;s _check_tax_config_missing still pointed users to a
&#34;copy-paste config snippet&#34; — the YAML flow Phase 3 replaced with the
inline form. Updated the copy.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f536a7c`](https://github.com/chen-star/net_alpha/commit/f536a7c4bd20048c2e3caa6860b13b2d7d649ee7))

* fix(web): negative-sign rendering on Today tile + hero, plus text-loss/gain/success aliases

C1: Today tile and the hero tile&#39;s vs-contributed subhead were stripping
the leading minus on negative values via |abs in the template, so
loss days rendered as gains. Removed the |abs and let fmt_currency emit
the sign. The + prefix now fires only on strict positives.

C2: text-loss / text-gain / text-success classes were used across at
least 8 templates (T5 mini-bar, at-loss summary, sim form_error,
harvest-clear status, etc.) but never defined in app.src.css — the
compiled bundle had only .text-neg / .text-pos / .text-warn /
.text-info. Added aliases so the existing markup colors correctly.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`504e1b8`](https://github.com/chen-star/net_alpha/commit/504e1b8419f0a3f2290bc24332199320f3d4b5d0))

* fix(web): equity x-axis tick density (P6); cash chart line semantics (P7)

Add hideOverlappingLabels: true + tickAmount: 12 to the equity-curve x-axis
so month labels don&#39;t pile up on dense date ranges.

Add data-series-solid=&#34;cash_balance&#34; and data-series-dashed=&#34;net_contributed&#34;
attributes to the cash chart container — stable semantic hooks that confirm
series ordering (cash balance = solid, net contributed = dashed, per §5.12).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`532d0e8`](https://github.com/chen-star/net_alpha/commit/532d0e8cd187c77bc4cab0e727a772e9ce995fb2))

* fix(web): CASH KPI rendered exactly once on Overview (P3 bug fix)

Remove the duplicate Cash balance tile from the secondary cash-flow row
in _portfolio_kpis.html. Cash is already shown via the slot_cash macro
in the hero KPI grid; the second block now shows only Net contributed
and Growth (unique data). Resize those two tiles from col-span-4 to
col-span-6 to fill the 12-column grid.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`80d80f3`](https://github.com/chen-star/net_alpha/commit/80d80f3bf56e01f35f149d84feac2d57a678cb0b))

* fix(web): positions_pane logs lookup failures instead of silent swallow (Phase 2 review #I4)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`83ac2c9`](https://github.com/chen-star/net_alpha/commit/83ac2c98a110d0abe596de5eeb765c4bd40feff8))

### Refactor

* refactor(web): realized_delta is loss — drop the duplicate compute (Phase 2 review #I5)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`50aff42`](https://github.com/chen-star/net_alpha/commit/50aff42a7f41d6f87b9301032d80b1022f6adc5f))

### Style

* style: fix import block sort order in positions.py (ruff I001)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ff50849`](https://github.com/chen-star/net_alpha/commit/ff508492a7e163a8e4f9f31d177c345d057284e1))

### Test

* test(web): re-capture snapshot baselines after C1/C2 color fixes

The C1 negative-sign fix and C2 .text-loss/.text-gain/.text-success
class definitions land real color on previously-uncolored markup:
- positions-at-loss: per-row loss column + summary unrealized now red
- settings-imports: triangle-alert tone change
- tax-wash: T5 mini-bar totals now red
- overview: Today tile + hero negative-vs-contributed render correctly

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1b58bac`](https://github.com/chen-star/net_alpha/commit/1b58bac9328b82f74bca5f882a43bfc24251fd59))

* test(web): re-capture snapshot baselines for Phase 3 page polish

Phase 3 changes:
- overview: KPI grid restructured (1 hero + 2 large + 4 small),
  Today tile added, freshness chip in toolbar, Portfolio H2 +
  Tax planning footer dropped, CASH dedup
- tax-wash: realized-P/L stacked mini-bar, watch/violations panel
  labels, affirmative empty copy, filter chips with reset, calendar
  strip
- tax-proj: inline projection form replacing the YAML snippet
- sim: action-required-for-Sell inline error layout, Recent sims
  this-session panel
- settings-imports: one-explanation card + per-row inline form
- positions-* / ticker-nvda: minor pixel diffs from app.css regeneration

Plus ruff-format cleanups in pnl.py + test_provider.py picked up
during the snapshot run.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`5e008c1`](https://github.com/chen-star/net_alpha/commit/5e008c1120feebf2dfd0190ca16e3bb77d77345c))

### Unknown

* Merge branch &#39;phase3-page-polish&#39; — Phase 3 Page Polish

The §4.1, §4.3, §4.4, §4.6 page-interior polish lands. Overview gets
the new KPI grid (1 hero + 2 large + 4 small) with Total Account Value
as the hero, the Today tile (NEW), single-emit CASH (P3 bug fix),
corrected chart semantics (P6, P7), a freshness chip in the toolbar,
and the dropped Portfolio H2 + Tax planning footer. Tax gets a
realized-P/L stacked mini-bar, loss-harvest budget bar, explicit
forward/backward panel labels, affirmative empty-state copy, filter
chips with reset, and an always-visible calendar strip. The YAML-
snippet projection UI is replaced by an inline form that POSTs to
/tax/projection-config and persists to ~/.net_alpha/config.yaml. The
Settings drawer&#39;s Imports tab gets a one-explanation card + per-row
inline forms (caller=drawer) and a drop-zone preview on drag-over.
Sim grows the recent-sims-this-session panel and account-required
validation that returns an OOB-swap fragment instead of a full-page
clobber.

25 commits across sections A (Phase 2 review backlog), B (Overview
clutter + charts), C (KPI restructure + Today tile), D (Tax polish),
E (inline projection form), F (Imports drawer), G (Sim recents +
validation), H (verification), plus review-feedback fixes for
negative-sign rendering, .text-loss/gain/success CSS aliases, sim
error response shape, and stale hygiene copy.

Phase 3 polishes page interiors. Phase 4 is the visual sweep
(Ticker page mono → sans, KPI variants, label-3 → label-2 contrast,
keyboard shortcuts). Phase 5 is responsive (drop viewport=1024). ([`ca87af4`](https://github.com/chen-star/net_alpha/commit/ca87af4f5e7a477ca1f5159bdd6c93a4e74b3ebd))


## v0.29.0 (2026-04-28)

### Documentation

* docs(web): document /imports/_legacy_page is drawer-fetched only (review nit #12) ([`d822355`](https://github.com/chen-star/net_alpha/commit/d822355401aa93cc90d897a8df48289801af5d1e))

* docs(web): _density_toggle docstring no longer references /holdings (review nit #11) ([`e3884e8`](https://github.com/chen-star/net_alpha/commit/e3884e8dec29194adeb4c54704e6fed3ba7495f8))

* docs(plans): Phase 2 — Positions canvas implementation plan

Covers the at-loss column redesign (Lockout-clear, Replacement); the
row-action menu (⋯ on hover with Open ticker / Sim sell / Set basis /
Copy ticker); the non-modal #positions-pane side pane with sim-sell
preview, set-basis form, and open-ticker link; Sim pre-fill from row
action URL params; and the Phase 1 review-backlog cleanup items.

Approximately 24 tasks across 7 sections (A–G). Section A clears the
Phase 1 nits as a warmup; Section G is the verification gate.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`2152afd`](https://github.com/chen-star/net_alpha/commit/2152afd97f159955ed7ca5a4b1bea02d1664a418))

### Feature

* feat(web): /sim accepts ?account= and ?action= for row-action pre-fill

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5df6b49`](https://github.com/chen-star/net_alpha/commit/5df6b495b76dfe30f706696a97c3aa945e75d5ea))

* feat(web): pane set-basis form block (single-lot inline; multi-lot links out) ([`b9996bf`](https://github.com/chen-star/net_alpha/commit/b9996bf666e041248bab09a077bdd68532d5247b))

* feat(web): pane sim-sell preview block + run-full-sim deep link ([`8f69209`](https://github.com/chen-star/net_alpha/commit/8f69209428cff820005f4cb6ddea28559965f615))

* feat(web): pane header — qty · account · last · basis · loss ([`df779b2`](https://github.com/chen-star/net_alpha/commit/df779b29fdc9d42347d6bb0e8baaafa4ab0030dc))

* feat(web): row click opens positions side pane (Alpine \$dispatch)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`935f75a`](https://github.com/chen-star/net_alpha/commit/935f75a48a87c130af8338b7a25e974f3595e0d6))

* feat(web): /positions/pane returns side-pane body fragment

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e25b592`](https://github.com/chen-star/net_alpha/commit/e25b59218507515b63860c4600e0d030901767ab))

* feat(web): mount positions side pane skeleton (Alpine + HTMX)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1043808`](https://github.com/chen-star/net_alpha/commit/1043808555d10c1dd352d13ce5e467de05fbf7cd))

* feat(web): drop &#39;click row to drill down&#39; hint (audit H9)

The row action menu (§3.4) now provides explicit affordance for row
interaction; the inline hint copy is redundant and adds visual noise.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`06e8d86`](https://github.com/chen-star/net_alpha/commit/06e8d866b30ad7ae8726dc1b1a77b607fa015c85))

* feat(web): mount row action menu on All / Stocks tab rows

Adds data-row=&#34;position&#34; + group class to each portfolio table row,
appends a matching w-10 header cell, and includes _row_actions.html
in the trailing cell. Uses r.accounts[0] as account label and none
for account_id (PositionRow is account-aggregated, not lot-scoped).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`dcdd678`](https://github.com/chen-star/net_alpha/commit/dcdd6785ea7f96292820a28e9be8425d9542bdbe))

* feat(web): row action menu — Open ticker / Sim sell / Set basis / Copy

Adds _row_actions.html partial with four-item Alpine dropdown, hover-
revealed ⋯ button, and aria-keyshortcuts for future Phase 4 bindings.
Mounts on at-loss table rows. Vendors external-link.svg (Lucide 0.469.0).
Adds .row-actions CSS utility. Adds test_phase2_row_actions.py.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e2a34c1`](https://github.com/chen-star/net_alpha/commit/e2a34c12f34a4c7fce6d5c2a4273f0028a11551f))

* feat(web): at-loss sorts clear rows first; renders &#39;clear&#39; for past dates

Adds _lockout_sort_key so rows with lockout_clear=None or in the past
sort before future-locked rows (ascending date within each group). Passes
`today` into template context so the lockout cell can compare
`row.lockout_clear &gt; today` and display &#39;clear&#39; for past/None dates.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`42007a9`](https://github.com/chen-star/net_alpha/commit/42007a97e9adea68c5f62652978696f8f0c73eb9))

* feat(portfolio): HarvestOpportunity exposes open_basis for at-loss UI

Adds required `open_basis: Decimal` field between `qty` and `loss`.
Wires it at the single construction site in compute_harvest_queue using
the loop variable `basis`. Tightens the MKT/BASIS template guards from
`is defined` to direct access. Updates 4 tests that construct
HarvestOpportunity directly (test_harvest_opportunity_minimal ×1,
test_harvest_queue_render.py ×3).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a2e8dad`](https://github.com/chen-star/net_alpha/commit/a2e8dad292a80760f0161780712d99084af94ca2))

* feat(web): at-loss table — new Lockout-clear + Replacement columns

Replaces the _harvest_queue.html include with a dedicated table that
always renders column headers (SYM/ACCT/QTY/MKT/BASIS/UNREAL/
LOCKOUT-CLEAR/REPLACEMENT). Also fixes budget field names (net_realized,
cap_against_ordinary) and updates the stale Phase 1 test that expected
the old &#34;Harvest queue&#34; heading.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`876e4a9`](https://github.com/chen-star/net_alpha/commit/876e4a986ce103eafba5a74bd12da311780b8826))

### Fix

* fix(web): set-basis form success state stays inside the pane

The pane&#39;s set-basis form had hx-target=&#34;#positions-pane-body&#34; with
hx-swap=&#34;innerHTML&#34;, which replaced the entire pane body with the
data-hygiene endpoint&#39;s bare &lt;li&gt; response (&#34;Reload the page to recompute
totals&#34;). Free-floating &lt;li&gt; outside a &lt;ul&gt; is invalid HTML and the
copy directs the user out of the pane.

Form now uses hx-target=&#34;this&#34; / hx-swap=&#34;outerHTML&#34; and posts to
/audit/set-basis?caller=pane. The route branches on the caller param
to return _positions_pane_set_basis_saved.html — an inline confirmation
with a &#34;Refresh pane&#34; button that fetches /positions/pane to surface
the updated totals.

Existing data-hygiene callers don&#39;t pass ?caller=pane, so they continue
to receive the legacy _data_hygiene_set_basis.html response unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`5e59074`](https://github.com/chen-star/net_alpha/commit/5e59074a79002b7007f2503b2b67c200fa8327d5))

* fix(web): row action menu — Alpine binding + None handling

C1: aria-expanded was rendered as literal &#34;open ? &#39;true&#39; : &#39;false&#39;&#34;
because the attribute wasn&#39;t prefixed with `:` (or x-bind:). Screen
readers got the source expression; WCAG 4.1.2 violation. Switched to
`:aria-expanded=&#34;open&#34;` so Alpine evaluates and stringifies correctly.

C2: account_id from the All-view&#39;s _portfolio_table.html arrives as
Jinja&#39;s None (the table is symbol-aggregated, no per-row account_id).
Jinja&#39;s |default(&#39;null&#39;) filter only fires when undefined, not None,
so the rendered Alpine handler emitted `account_id: None` — a
ReferenceError that broke the Set-basis menu item silently. Switched
to explicit `account_id is not none` check.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`cf993b4`](https://github.com/chen-star/net_alpha/commit/cf993b498afde8086196325c2819442061adb33e))

* fix(web): /settings/* shows polite hint when drawer closed (review nit #6) ([`21a71a2`](https://github.com/chen-star/net_alpha/commit/21a71a27ad53748e6e0a3c219916bd38c4144bc5))

* fix(web): drawer placeholders say &#39;Coming soon&#39; not specific phase (review nit #9) ([`1856518`](https://github.com/chen-star/net_alpha/commit/1856518eaf9ce06b0d8efb241d0e87bfdf116c97))

* fix(web): legacy imports page does not highlight Overview nav (review nit #7) ([`8eec5bb`](https://github.com/chen-star/net_alpha/commit/8eec5bbfb679092c79d0053458e32791124b5dba))

* fix(web): empty-state CTA targets /settings/imports directly (review nit #8) ([`40c409c`](https://github.com/chen-star/net_alpha/commit/40c409c89c376af8ad7bd9b8b7098c4fba28c858))

### Style

* style: ruff format fixes for B1/B2 test files

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3c1f1db`](https://github.com/chen-star/net_alpha/commit/3c1f1db85938ddb6290884c834e82b0951997a4d))

* style: ruff format test_phase2_review_backlog.py ([`978b012`](https://github.com/chen-star/net_alpha/commit/978b01215c028593e03ad59470db5ce12a5f451a))

### Test

* test(web): re-capture snapshot baselines for Phase 2 canvas

Phase 2 changes:
- positions-all: row-action menu (⋯) column added; row-click semantics
  changed from window.location to side pane $dispatch
- positions-at-loss: complete rewrite — Lockout-clear + Replacement
  columns, sorted with clear lots first
- sim: hidden &lt;select name=&#34;action&#34;&gt; added so the segmented control&#39;s
  value participates in the form contract
- settings-imports: &#39;polite hint&#39; copy added when drawer is closed
- minor pixel diffs across other pages from .row-actions CSS additions

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`d0eb698`](https://github.com/chen-star/net_alpha/commit/d0eb6987b8d5cf77a2c17da4513bb9f1eeae9d1d))

### Unknown

* Merge branch &#39;phase2-positions-canvas&#39; — Phase 2 Positions Canvas

The §3.3/§3.4/§3.5 Positions canvas lands: at-loss tab gets dedicated
Lockout-clear and Replacement columns; every positions row gains a
hover-revealed action menu (⋯) with Open ticker / Sim sell / Set basis /
Copy ticker; a non-modal #positions-pane side pane opens on row click
with sim-sell preview, set-basis form, and open-ticker link; the Sim
page pre-fills from row-action URL params.

24 commits across sections A (Phase 1 review backlog cleanup), B
(at-loss column redesign + HarvestOpportunity.open_basis), C (row
action menu), D (side pane skeleton + /positions/pane route), E
(side pane content), F (sim pre-fill), G (snapshot baselines), plus
review-feedback fixes for the aria-expanded Alpine binding, the
None-handling JS ReferenceError on All-view Set-basis, and the
set-basis form success state.

Phase 2 stays structural — page interiors of Overview, Tax, Imports,
and Ticker are untouched. Phase 3 polishes those; Phase 5 makes the
side pane and drawer responsive at &lt;1024px. ([`60233af`](https://github.com/chen-star/net_alpha/commit/60233af62ef50b8dbaf826b3cdf88be2747e1b31))


## v0.28.0 (2026-04-28)

### Documentation

* docs(plans): Phase 1 — IA migration implementation plan

7 sections / ~25 bite-sized tasks: 301 redirects (/holdings →
/positions, /tax?view=harvest → /positions?view=at-loss, /imports →
/settings/imports), top nav rewrite (Overview · Positions · Tax · Sim
+ gear icon), settings drawer with tab strip and functional Imports +
Density tabs, density toggle relocated from per-page to global, and
positions tabs (All / Stocks / Options / At a loss / Closed) with
at-loss serving the existing harvest queue HTML for now.

Visible IA shift; no page-interior content rebuilds (those are
Phases 2-4). Phase 5 ships the responsive viewport fix.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`af2f264`](https://github.com/chen-star/net_alpha/commit/af2f264f1bbd4d0908be7f973b03da5644c2943b))

### Feature

* feat(web): drop Harvest tab from /tax (moved to /positions?view=at-loss)

Removes the Harvest nav tab from tax.html. The route still processes the
harvest view for profile-default routing, but the tab link is gone. Updates
test_tax_default_tab to assert new behaviour (no nav link, content still
renders).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`778dc70`](https://github.com/chen-star/net_alpha/commit/778dc7067812cb73af6202627809230ba2b60f41))

* feat(web): positions tab views — at-loss serves harvest queue

Wires harvest queue context (rows, only_harvestable, budget) into
positions_page when selected_view == &#39;at-loss&#39;, replicating the context
that /tax?view=harvest used to build before it became a redirect.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6be555a`](https://github.com/chen-star/net_alpha/commit/6be555a9b8975b40bfea4381e1f5581cef419313))

* feat(web): positions tab strip — All/Stocks/Options/At-a-loss/Closed

Renames holdings.html → positions.html, updates route to render positions.html
and accept ?view= param. Adds _positions_tabs.html with 5-tab strip wired into
positions.html with view-based partial switching.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b3472d9`](https://github.com/chen-star/net_alpha/commit/b3472d9a0e6b9cca51cd5e51f2d01482d4f28fda))

* feat(web): remove inline density toggle from page chrome (audit H4/T1)

Per-page density toggles removed from holdings.html, tax.html, and
imports.html; the toggle now lives exclusively in the Settings drawer&#39;s
Density tab. Updated test_density_toggle_in_pages.py to assert drawer
presence instead of per-page chrome, updated test_phase3_smoke.py&#39;s
stale page-key assertion, and added test_phase1_density_relocation.py
to guard against per-page regression.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`67ce51b`](https://github.com/chen-star/net_alpha/commit/67ce51b17375a1e62a214318700cb238e4bbe98a))

* feat(web): drawer Density tab — global preference

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0ef49b5`](https://github.com/chen-star/net_alpha/commit/0ef49b5a9153b1d55eb072c0e403fc2242cb5241))

* feat(web): drawer Imports tab — lazy-load content from legacy page

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d21940a`](https://github.com/chen-star/net_alpha/commit/d21940a9f8d76098537b1e277736d92bbbaf0c1a))

* feat(web): settings drawer tab strip + placeholders

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c60ea57`](https://github.com/chen-star/net_alpha/commit/c60ea572ac213a9d95b0ed1c7cfc8795ae465b13))

* feat(web): auto-open settings drawer on /settings/imports load

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`74c97e9`](https://github.com/chen-star/net_alpha/commit/74c97e9479ea082f5647765374d95459a7567ec5))

* feat(web): add gear icon to topbar with drawer-open dispatch

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f04064d`](https://github.com/chen-star/net_alpha/commit/f04064d6b426950146ee5daaa898fadbfebc070c))

* feat(web): drop redundant topbar pills (audit P10)

Remove account-count and period pills from portfolio and holdings topbar_right
blocks — they duplicate info already shown in the page subhead. Update
test_positions_routes and test_phase1_topnav to match new nav labels.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1142f6e`](https://github.com/chen-star/net_alpha/commit/1142f6e4e303e1d43a8641ca6130713e021db398))

* feat(web): update active_page values for new nav (overview/positions)

portfolio→overview, holdings→positions, wash_sales→tax, imports→overview.
Also updates deprecated nav-badge test assertions to match Phase 1 design
(badge removed from nav, will move to gear icon in Section C).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`92e62a4`](https://github.com/chen-star/net_alpha/commit/92e62a4eb4e7cf12ea30933e18724b2d85839ac4))

* feat(web): rewrite top nav — Overview · Positions · Tax · Sim

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`406871f`](https://github.com/chen-star/net_alpha/commit/406871fc718b227474152992632fc890c3ceb8a2))

* feat(web): 301 /imports → /settings/imports; add settings drawer entry routes ([`4dc8703`](https://github.com/chen-star/net_alpha/commit/4dc87033229ccda8a82d73586fb5782fde855509))

* feat(web): 301 /tax?view=harvest → /positions?view=at-loss ([`5fb023d`](https://github.com/chen-star/net_alpha/commit/5fb023d0124cdf16ca26d5faf2c1de01e6a3a130))

* feat(web): 301 /holdings → /positions (preserves query string) ([`3cee147`](https://github.com/chen-star/net_alpha/commit/3cee1471935a11a28ece48eb85330a3b2bfdec78))

### Fix

* fix(web): CSV upload now redirects to Settings drawer instead of /imports

Critical #3: POST /imports returned 303 to /imports?flash=..., which
then hit the Phase 1 301 to /settings/imports — dropping the flash
param. Flash was already cosmetic (template never displayed it), so
removed the dead plumbing and changed the redirect target to
/settings/imports so the user lands on the drawer&#39;s Imports tab where
the new import is visible in the past-imports table.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f1751b6`](https://github.com/chen-star/net_alpha/commit/f1751b667ae3c8c001ccaf8e3639386433482156))

* fix(web): harvest queue routing — at-loss owns the toggle, /tax fully redirects

Critical #1: the &#39;currently harvestable only&#39; checkbox on
/positions?view=at-loss had hardcoded hx-get=&#39;/tax?view=harvest&#39; and
hx-target=&#39;#tab-content&#39;, neither of which works on the new home.
Parameterized via harvest_form_action / harvest_form_target context vars
and a #positions-tab-content wrapper. HX-Request to /positions?view=at-loss
now returns the panel partial only.

Critical #2: /tax with active/options profile defaults (or ?view=budget)
rendered harvest content with no visible tab. Resolved /budget alias
before the redirect so it 301s to /positions?view=at-loss; updated
profile.default_tax_tab() so &#39;active&#39;/&#39;options&#39; default to &#39;wash-sales&#39;;
deleted the dead harvest-render branch in routes/tax.py and its include
in tax.html.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`002fcbc`](https://github.com/chen-star/net_alpha/commit/002fcbcf8206250c505290be3c2fdd94260a7a47))

### Refactor

* refactor(web): /holdings → /positions (redirects come in next commit) ([`ac0e0ce`](https://github.com/chen-star/net_alpha/commit/ac0e0ce42e68f4d48ad94bd68e7d88d1f4aa7fe5))

* refactor(web): rename holdings router to positions (no path change yet) ([`20c25f2`](https://github.com/chen-star/net_alpha/commit/20c25f2562a53b854f45597897f715080db731c5))

### Style

* style(web): ruff format Phase 1 touchpoints

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1abe3f2`](https://github.com/chen-star/net_alpha/commit/1abe3f2d09b272e4697a033dd5c8b7c0b8cd8c22))

### Test

* test(web): re-capture snapshot baselines for Phase 1 IA

PAGES list updated to reflect the new IA: overview / positions-all /
positions-at-loss / tax-wash / tax-proj / settings-imports / sim /
ticker-nvda. The old `holdings`, `tax-harvest`, `imports`, and `portfolio`
baseline directories are gone — those URLs now 301 to the new locations.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`4ef15a6`](https://github.com/chen-star/net_alpha/commit/4ef15a604d796927592613da2c4eba5ccb3f9b39))

* test(web): nav-link round-trip smoke test

Adds docstring clarifying the B4 round-trip parametrize purpose: each of
the four nav destinations (/, /positions, /tax, /sim) must appear as an
href on the home page and return HTTP 200 with the label in the HTML.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ce92f48`](https://github.com/chen-star/net_alpha/commit/ce92f484d73c1c80e8f25612ae2e9d816da50cc7))

### Unknown

* Merge branch &#39;phase1-ia-migration&#39; — Phase 1 IA Migration

The IA shift from the §3 design spec lands: top nav becomes
Overview · Positions · Tax · Sim plus a settings gear; /holdings becomes
/positions (with 301); /tax?view=harvest 301-redirects to a new
/positions?view=at-loss tab; the Imports page content lifts into a
Settings drawer triggered by the gear; the per-page Density toggle
moves to that drawer as a global preference.

22 commits across sections A (routing &amp; redirects), B (top nav rewrite),
C (gear icon + drawer trigger), D (drawer content — Imports + Density
tabs), E (density toggle removal from page chrome), F (positions tabs
scaffold), G (final verification), plus review-feedback fixes for the
harvest queue toggle wiring and CSV upload redirect target.

Phase 1 is structural only — page-interior content stays untouched.
Phase 2 rebuilds the at-loss tab; Phase 3 polishes page interiors. ([`7379f6d`](https://github.com/chen-star/net_alpha/commit/7379f6d4343701cc04e029fd7e479fb24a344f38))


## v0.27.0 (2026-04-28)

### Build

* build: add snapshot-test/-update targets; exclude from default suite

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`61ab652`](https://github.com/chen-star/net_alpha/commit/61ab65257f60c0d6baf2da4d306af47c69d238bb))

* build: add pytest-playwright + playwright to [dev] extras

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1e7b148`](https://github.com/chen-star/net_alpha/commit/1e7b148c7e7d04684699916a8fe61df8d930d502))

* build: add vendor-lucide Makefile target (§5.4) ([`f8d83d5`](https://github.com/chen-star/net_alpha/commit/f8d83d5ce971000003ba6e5af6ea818af729bf94))

* build(css): rebuild app.css after Phase 0 token additions ([`8092106`](https://github.com/chen-star/net_alpha/commit/8092106b08c7992b5e83510f8a7f3f35abec1e7f))

### Documentation

* docs(plans): Phase 0 — Foundations implementation plan

Bite-sized TDD-first tasks across six sections: centralized format helpers
(fmt_quantity / fmt_currency / fmt_percent / fmt_date) registered as Jinja
globals; new design tokens added to app.src.css; 24 vendored Lucide SVGs
under web/static/icons; empty Settings drawer skeleton mounted in base.html;
pytest-playwright snapshot-test infrastructure with baselines for every
page at desktop + tablet widths.

Phases 1–5 each get their own plan after Phase 0 ships.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`c234417`](https://github.com/chen-star/net_alpha/commit/c23441794374c3209719d456e3ab2577c68d4fde))

* docs: UI/UX evaluation &amp; redesign spec (Approach B)

Whole-product audit of the web UI across Portfolio, Holdings, Tax, Imports,
Sim, and Ticker pages, plus a multi-phase redesign that reorganizes the IA
(Overview/Positions/Tax/Sim + Settings drawer), promotes the Sim page,
absorbs the harvest queue into Positions, replaces the YAML tax-projection
setup with an inline form, and lays out a polish pass against ~50 audit
findings. Stack and visual tokens kept; five-phase sequencing with snapshot
tests as part of the work.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b4e5b62`](https://github.com/chen-star/net_alpha/commit/b4e5b62e36c4f6dc37b0223bbeca603d3547c316))

### Feature

* feat(web): mount settings drawer skeleton in base.html ([`ccb602a`](https://github.com/chen-star/net_alpha/commit/ccb602a5c8665bd4b7c69bfb70f060e8fe514abe))

* feat(web): add empty settings drawer skeleton (§3.6) ([`3337328`](https://github.com/chen-star/net_alpha/commit/3337328cc0ac667d8ad24c33c38119069b45414a))

* feat(web/static): vendor Lucide icons (§5.4) ([`2522584`](https://github.com/chen-star/net_alpha/commit/252258409722792b0d53461ef5ad01d272af33e7))

* feat(web/css): add Phase 0 design tokens (§5.1) ([`c8725a3`](https://github.com/chen-star/net_alpha/commit/c8725a3996384df5617c34f3292a864e8ec4caf3))

* feat(web): register fmt_* helpers as Jinja globals ([`89faed2`](https://github.com/chen-star/net_alpha/commit/89faed2f7533ac1b828b3e9dd549a8ebaaa75f30))

* feat(web/format): add fmt_date (§5.9) ([`a00849a`](https://github.com/chen-star/net_alpha/commit/a00849a88b74f91cb992446ef9b67be8c8268d3e))

* feat(web/format): add fmt_percent (§5.9) ([`7632746`](https://github.com/chen-star/net_alpha/commit/763274621e6fce79d56bc9eec6e15ec79679448d))

* feat(web/format): add density-aware fmt_currency (§5.9) ([`e77be98`](https://github.com/chen-star/net_alpha/commit/e77be9824b38237c15086139666b01f0875dffcf))

* feat(web/format): add fmt_quantity (§5.9) ([`565cb5f`](https://github.com/chen-star/net_alpha/commit/565cb5fdcecc38b870cadc172d9723a80720c51c))

### Fix

* fix(web): code-review feedback for Phase 0

- Restore the vendor-lucide recipe body and the missing tail of
  LUCIDE_ICONS (refresh-cw, database, download) — earlier rebase
  conflict resolution had eaten both. `make vendor-lucide` is now
  functional and reproducibly fetches all 23 icons.
- Drop the dead `Density = Literal[...]` alias from web/format.py.
  A real `Density` literal already exists in models/preferences.py
  with a different value set (&#34;tax&#34; vs &#34;tax-view&#34;); keeping a second
  one was a future-confusion trap and the alias was unused.
- Settings drawer: drop the redundant static `hidden` Tailwind class
  (Alpine `x-show` + `x-cloak` already handle pre-hydration hide),
  add a window-level `open-settings-drawer` listener so Phase 1&#39;s
  gear-icon trigger can $dispatch from outside the drawer&#39;s Alpine
  scope, and an esc-to-close handler.
- Add the load-bearing `[x-cloak] { display: none !important; }`
  rule to app.src.css that four existing templates rely on.

237 tests pass, 16 snapshots pass, lint clean.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`66c8e60`](https://github.com/chen-star/net_alpha/commit/66c8e60162d63d1255a9fc5243997d9df22adba4))

### Style

* style: apply ruff format to Phase 0 test files

Trailing pass over tests touched by Section B/C/E to satisfy
`ruff format --check` (re-flowed long Path expressions, set literals,
and an f-string that fit on one line).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b1c26e6`](https://github.com/chen-star/net_alpha/commit/b1c26e6cbdc306c3d3255308262728d8283d74d2))

### Test

* test(web): capture Phase 0 baseline page snapshots

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c299942`](https://github.com/chen-star/net_alpha/commit/c299942000cf17e491aa0561f83f6fd379d2073c))

* test(web): baseline-snapshot test scaffolding (no baselines yet)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`962e61a`](https://github.com/chen-star/net_alpha/commit/962e61a29842c07db591ea7851706e7b8584938b))

* test(web): add Playwright snapshot test scaffolding

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`56203f9`](https://github.com/chen-star/net_alpha/commit/56203f9a3cd87f64cbf8bde01be048b9b1cf3f97))

* test(web): assert vendored Lucide icons present ([`0150602`](https://github.com/chen-star/net_alpha/commit/01506027ce1a3fec71ea8adc23d85d3ede550dda))

### Unknown

* Merge branch &#39;phase0-foundations&#39; — Phase 0 Foundations ([`cb0b7bb`](https://github.com/chen-star/net_alpha/commit/cb0b7bb5381db7fa422bd38d59d410aa248453e1))

* Merge branch &#39;master&#39; of https://github.com/chen-star/net_alpha ([`73b4be6`](https://github.com/chen-star/net_alpha/commit/73b4be69c37a6c7c9e4d240ac09fede9b42ef97a))


## v0.26.0 (2026-04-28)

### Feature

* feat(web): instant page loads, move wash UI to Tax, filterable allocation modal

- Pricing: stale-while-revalidate read path. PricingService.get_prices
  now serves cached entries (fresh OR stale) immediately and only
  network-fetches symbols with no cache row at all. Stale entries surface
  via snapshot.stale_symbols so the Portfolio KPIs panel shows a soft
  refresh hint. Eliminates the multi-second blocking Yahoo fetch on every
  cold load past the 15-min TTL — Portfolio/Holdings/Tax pages now render
  from cache in under a second after the first ever load.

- Tax-related UI off Portfolio: drop wash_impact slot from default
  active/options profile orderings, remove the Wash-sale watch panel
  from the bundled /portfolio/body fragment, and add the watch panel
  to the Tax page wash-sales tab (which already showed the wash-impact
  summary). Wash-watch is now scoped by the same account filter as the
  rest of that tab.

- Allocation modal: was a wall of low-density rows with no way to find
  a symbol. Adds a typeahead filter (Alpine), sticky table header, and
  compact row padding. Two keystrokes to find any holding. ([`d90d765`](https://github.com/chen-star/net_alpha/commit/d90d765fd456540725010081e7b6390a8d72630b))


## v0.25.0 (2026-04-28)

### Feature

* feat(transfers): multi-segment split for one-to-many transfer rows

A single broker-reported transfer often represents shares acquired across
multiple lots/dates. The &#34;Set basis &amp; date&#34; form now accepts N segments
(acquisition_date, qty, basis) per transfer; quantities must sum to the
parent&#39;s total.

Repository:
- New split_imported_transfer() splits the parent row into N siblings that
  share transfer_group_id and transfer_date. The first segment is written
  in place to preserve the original natural_key (re-import dedup still
  works); siblings get derived &#34;&lt;parent_nk&gt;:seg&lt;i&gt;&#34; keys.
- The legacy update_imported_transfer is kept for any direct callers.

Form:
- Alpine-driven add/remove segment rows; running total of segment qtys
  rendered next to the parent total so the user can validate the split
  before submit.
- The form GET now loads existing siblings (when transfer_group_id is set),
  so re-opening a previously-split row shows every segment populated.

Route:
- /trades/{id}/edit-transfer accepts seg_date[], seg_qty[], seg_basis[]
  parallel arrays and validates them as a unit.

Tests cover single-segment edits (legacy behavior), 3-segment splits, and
sum-mismatch rejection.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`410b3a6`](https://github.com/chen-star/net_alpha/commit/410b3a6ca13ba1e00968bfb2e00d520ce71ab7d9))

* feat(web): portfolio reorg, allocation modal, sortable holdings, all-options panel

- Portfolio page: split into Portfolio (top) and Tax planning (bottom) sections.
- Allocation donut: clickable; opens modal with full ranked breakdown including
  positions normally rolled into &#39;OTHER&#39;. Pledged-cash slice recolored to the
  orange used in the Cash KPI bar so it&#39;s visually distinct from free cash.
- Holdings: sortable column headers (server-side, preserves filters/paging).
- Holdings: &#39;Open short options&#39; panel replaced with &#39;Open options&#39; (long+short),
  sorted by expiry. New compute_open_option_positions function unifies long lots
  with short option chains.
- Ticker page: &#39;accounts&#39; KPI now derives from trades ∪ lots, so symbols with
  only short-option exposure (e.g. UUUU) no longer show &#39;-&#39;.
- Ticker timeline: transfer rows show both &#39;Acq&#39; (acquisition date) and
  &#39;Xferred&#39; (broker-statement date) when they differ.
- Schema v10: trades.transfer_date and trades.transfer_group_id columns added.
  Initial import populates transfer_date from the broker date for transfer rows;
  user edits modify only the acquisition date, preserving the transfer date for
  audit. transfer_group_id reserved for the upcoming multi-segment split.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1010b24`](https://github.com/chen-star/net_alpha/commit/1010b245c671b716d685fc3eaaf13a1ba1ab9d25))


## v0.24.4 (2026-04-28)

### Fix

* fix(ticker): correct realized P&amp;L for short options + Timeline G/L column

Five issues, all on the ticker drilldown page:

#1 (Open lots empty for UUUU): when only short options are open, the long-lots
   table is hidden and replaced with a brief &#34;see Open short options below&#34;
   pointer so the user isn&#39;t staring at an empty table after a CSP open.

#2 (Timeline gain/loss column): added a G/L column showing realized P&amp;L per
   close row. Long-lot Sells show proceeds-basis directly; short-option
   closes (BTC, expiry-synthetic) pair the close cost against the matching
   STO premium so the user sees per-cycle profit on the close row.

#3 (UUUU realized P&amp;L wrong): the legacy realized helper summed
   proceeds-basis for every Sell, which counted STO premiums as realized at
   open and silently dropped BTC closes (which are Buys). Replaced with
   realized_pl_from_trades, which skips STOs and pairs BTCs against their
   matching opens. Wired through ticker.py, compute_open_positions
   (per-symbol realized), and the realized-P&amp;L provenance trace. UUUU YTD
   2026 now reads $826.04 (was $750.02 inflated by un-paired STO premium).

#4 (Schwab Lot Detail title style): heading lifted out of the panel header
   bar and rendered as &lt;h2 class=&#34;text-xl mt-6 mb-2&#34;&gt; to match the Timeline /
   Open lots / Open short options sections.

#5 (sell-put basis/proceeds): same root cause as #3 — the bad realized
   number propagated to FRMI as well. FRMI YTD 2026 now reads -$157.32
   (one closed cycle: STO +129.34 paired with BTC -286.66).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`297fbdd`](https://github.com/chen-star/net_alpha/commit/297fbddbf11feef9ea9a93d29b0c21099165b814))


## v0.24.3 (2026-04-28)

### Fix

* fix(web): batch-2 — 9 issues (rename hygiene, tax merge, allocation, sim, etc.)

#1 hygiene orphan-sell: match option closes by digit-stripped ticker base so
   Schwab corp-action renames (GME → GME1) don&#39;t get falsely flagged.

#2 nav: drop standalone &#34;Sim&#34; entry from top nav. /sim still reachable from
   Holdings/Ticker &#34;Simulate sale&#34; + Tax/Harvest &#34;Simulate harvest&#34; links.

#3 tax route: read only_harvestable from query string and thread it through
   compute_harvest_queue. Previous code hardcoded False so the checkbox was
   visually toggleable but functionally a no-op.

#4 sim form: pre-fill qty + current Yahoo quote when invoked with
   ?harvest=1, and render a &#34;Harvest mode&#34; banner explaining the pre-fill.

#5 projection placeholder: replace cryptic &#34;tax: section in config.yaml&#34;
   copy with a one-liner pointing at the Tax → Projection tab. The tab
   itself now embeds a copy-paste YAML setup snippet with comments.

#6 tax page: collapse &#34;Offset budget&#34; tab into &#34;Harvest&#34; tab (3 tabs total).
   Budget tile + realized-P/L breakdown render above the harvest queue.
   ?view=budget aliased to ?view=harvest for back-compat.

#7 hygiene unpriced: drop misleading &#34;go fix → /holdings&#34; link and downgrade
   severity to info — there&#39;s no in-app price-override UI, so the link was a
   dead end. Rephrase detail to explain the cause is environmental.

#8 allocation donut: split cash slice into free + pledged with subtly
   different shades (CSP collateral shown muted vs free cash). New
   build_allocation cash_pledged param + AllocationSlice.is_pledged_cash.

#9 short options: move panel from Portfolio body to Holdings page (lazy
   /holdings/short-options fragment). Holdings is the inventory page;
   Portfolio stays focused on KPIs / allocation / wash watch / cash.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0f271f3`](https://github.com/chen-star/net_alpha/commit/0f271f30f93d9c3a559f039e5df66f54db102d27))


## v0.24.2 (2026-04-28)

### Fix

* fix(web): address 9 UX issues across portfolio/holdings/tax/imports

- portfolio: replace bleed-out templates with .kpi panels (offset budget tile, projection card)
- portfolio: add CSP free/pledged stacked progress bar, csp_count to body ctx
- portfolio: hoist gl_option_closures to single repo call (perf)
- portfolio: rewrite offset_budget_tab and projection_tab as .kpi panels
- holdings: add column-header tooltips and tax-view footnote in _portfolio_table
- tax: rewrite _harvest_queue with intro paragraph + tooltips on Lockout/Premium/Simulate
- tax: wash sales default year = current year; All years opt-in (value=0)
- imports: hygiene basis_unknown now links to /ticker/&lt;sym&gt;#trade-affordance-&lt;id&gt;
- imports: skip orphan-sell warning when basis_source startswith option_short_open
- imports: dup-cluster key includes price-per-share to allow average-down trades
- repo: add _acct_display_cache to Repository __init__ to eliminate N+1

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0cf15d9`](https://github.com/chen-star/net_alpha/commit/0cf15d9396761054b758e4bb059d84e40369af12))


## v0.24.1 (2026-04-28)

### Fix

* fix(web): open-short visualization, lifetime KPIs, density HTMX, tax CSS

- portfolio: skip None proceeds/cost_basis in tax_planner (fixes 500)
- positions: add compute_open_short_option_positions + OpenShortOptionRow
- ticker: KPIs show YTD + Lifetime; timeline merges put_assignment Buy and
  synthesizes &#34;Closed by Expiry&#34; rows; drops duplicate option_short_close_assigned
- portfolio body: new &#34;Open short options&#34; panel (CSP/CC counts, premium, cash
  secured) shown when shorts exist
- density/profile forms switched to hx-post so HX-Refresh response actually
  refreshes the page
- tax: add .tabs/.tab/.tab--active styles, _harvest_queue uses .net-table ([`66d0c92`](https://github.com/chen-star/net_alpha/commit/66d0c920612eeedc948bf6d88054a42bf34cc786))

### Unknown

* Merge branch &#39;master&#39; of https://github.com/chen-star/net_alpha ([`ba3c1cd`](https://github.com/chen-star/net_alpha/commit/ba3c1cd0f229b4dacfcea9e30c3cdde7f329dc33))


## v0.24.0 (2026-04-28)

### Chore

* chore: ruff format fixes on Section F test files ([`1cad1bf`](https://github.com/chen-star/net_alpha/commit/1cad1bfbf4337d490413386df9186b96a9881783))

* chore(web): ruff UP017 fix — use datetime.UTC alias in Section D files

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`48eb0b1`](https://github.com/chen-star/net_alpha/commit/48eb0b18058add81fdc1c1200307107dee5d9c0c))

### Documentation

* docs: phase 3 implementation plan ([`cd5c2c1`](https://github.com/chen-star/net_alpha/commit/cd5c2c13dadadf2add800ba45295fa746bf28628))

### Feature

* feat(web): switcher label reflects current request&#39;s account filter

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a6aa566`](https://github.com/chen-star/net_alpha/commit/a6aa566aa88ff692f82dd2e078e4ac039afcb02b))

* feat(web): /tax default tab from ProfileSettings.default_tax_tab

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bc6588b`](https://github.com/chen-star/net_alpha/commit/bc6588b8ba9ee425f4ff8b5eb32dd143ec8e9298))

* feat(web): density toggle on /holdings, /tax, /imports ([`0c0d6a3`](https://github.com/chen-star/net_alpha/commit/0c0d6a34634407d054ef57d02e331ab3fabf2257))

* feat(web): localStorage density override shim ([`d61f59b`](https://github.com/chen-star/net_alpha/commit/d61f59be27efc1f709588206b8ad2570f7312ac3))

* feat(web): density toggle template (Compact / Comfortable / Tax-view) ([`08bd159`](https://github.com/chen-star/net_alpha/commit/08bd159c76b68fe9c290cf97f4911cc8e5838f73))

* feat(web): profile-driven extra columns in holdings table ([`092a714`](https://github.com/chen-star/net_alpha/commit/092a714492414633eeb886f7aa19d58091fcebe4))

* feat(portfolio): premium_received per position for options profile ([`6719116`](https://github.com/chen-star/net_alpha/commit/67191163c3135c0e23723cdbec9eeff005afe4c8))

* feat(portfolio): position rows expose days_held + lt/st split ([`434544c`](https://github.com/chen-star/net_alpha/commit/434544cfa3800da796c04a122bc598f6783cad96))

* feat(web): KPI hero ordering driven by ProfileSettings.order

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`732f1c3`](https://github.com/chen-star/net_alpha/commit/732f1c3d1aa949697fcd57942a00d1a5cdc52398))

* feat(web): conservative profile collapses wash-watch by default

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2ef4b29`](https://github.com/chen-star/net_alpha/commit/2ef4b291559f2b49da50dbbe5658c12710de2f9e))

* feat(web): pass ProfileSettings into /portfolio context

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`194fe9d`](https://github.com/chen-star/net_alpha/commit/194fe9d09b1aede7ad42c16d6c5b82ede76724b9))

* feat(web): first-visit profile picker modal

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a1d8378`](https://github.com/chen-star/net_alpha/commit/a1d8378dac9bd2bdb170f6e53ccd6a04ac3a42af))

* feat(web): render profile switcher in base topbar

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`eab81ab`](https://github.com/chen-star/net_alpha/commit/eab81ab73df1ee7b6719ae614763005a8612d814))

* feat(web): toolbar profile switcher template

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`aa4966f`](https://github.com/chen-star/net_alpha/commit/aa4966fdb829b5d38642ae8ac3164a8ceaeeca5b))

* feat(web): POST /preferences writes per-account or all-account prefs

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`642062f`](https://github.com/chen-star/net_alpha/commit/642062f3d293abbfa45cd2156987301bc48dd197))

* feat(web): get_profile_settings FastAPI dependency

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bd79a7c`](https://github.com/chen-star/net_alpha/commit/bd79a7c9a4dc77969a00636f4e79d04f18541a8c))

* feat(prefs): resolve_effective_profile across single/all-account views

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`df3d989`](https://github.com/chen-star/net_alpha/commit/df3d989fa96eaba65a4dbc457eefbeeb9156aeb7))

* feat(prefs): default_columns() and default_tax_tab() ([`213a077`](https://github.com/chen-star/net_alpha/commit/213a077c68d459445fbb04095dfe83289c26bfab))

* feat(prefs): ProfileSettings.order() for KPI hero slots ([`8678f45`](https://github.com/chen-star/net_alpha/commit/8678f454e9cd3560270c5af59ef0d65078a91b32))

* feat(prefs): ProfileSettings.shows() rule table ([`5119abd`](https://github.com/chen-star/net_alpha/commit/5119abd4966371d312548752067616ddc5f890e5))

* feat(db): repository methods for user preferences

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cbf5acf`](https://github.com/chen-star/net_alpha/commit/cbf5acffd8fe764d4ae59db594c281b7f6dcd35a))

* feat(db): v8 -&gt; v9 migration adds user_preferences

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8376221`](https://github.com/chen-star/net_alpha/commit/83762217872f7dd9641784ca8a95ec1a508c7f6e))

* feat(db): add UserPreferenceRow for v9 schema

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f0ed016`](https://github.com/chen-star/net_alpha/commit/f0ed0169a36d10410d551766ba47139b5d7158ae))

### Fix

* fix(portfolio): premium_received skips assigned-put chain to avoid double-count

Assigned-put STO/synthetic-close trade pairs (basis_source in
{option_short_open_assigned, option_short_close_assigned}) already fold
their premium into the underlying stock&#39;s adjusted basis. Counting them
again in premium_received would double-credit the user-visible figure.

Move the premium accumulator below the existing _SKIP_AGG_SOURCES guard
so the same skip applies. Adds a regression test exercising the
assigned-put chain.

Caught in Phase 3 final code review. ([`81881bf`](https://github.com/chen-star/net_alpha/commit/81881bf6b2d0c098ccbbd564169523346bdc53f4))

* fix: emit data-col markers in holdings.html wrapper for empty-state path

The _portfolio_table.html cols-meta span only renders when rows exist.
In the no-imports (empty-state) path the holdings page skips the table
fragment entirely, so data-col attributes never appeared in the HTML.

Add a hidden cols-meta span directly in holdings.html so column markers
are always present in the page regardless of import state.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4ff9ac4`](https://github.com/chen-star/net_alpha/commit/4ff9ac4568df8979698dd3b5ea932665cd327bd5))

### Style

* style: ruff format

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6195963`](https://github.com/chen-star/net_alpha/commit/61959636e7a976f9197b82580bdcdce377e1269a))

### Unknown

* Merge branch &#39;phase3-density&#39; — Phase 3 Style-Aware Density

Adds the per-account profile (Conservative/Active/Options) and per-page
density toggle (Compact/Comfortable/Tax-view) per spec Section 3.

- v8 → v9 schema migration adds user_preferences table.
- prefs/profile.py encapsulates the visibility/ordering/columns rule
  table (Section 3b) so templates ask profile.shows() / order() /
  default_columns() / default_tax_tab() instead of branching on profile
  strings.
- POST /preferences route + toolbar switcher (request-aware) +
  first-visit modal (3a).
- /portfolio: KPI hero ordering by profile, wash-watch
  collapsed-by-default for Conservative.
- /holdings: profile-driven extra columns (days_held, lt_st_split,
  premium_received, origin_event placeholders) + density toggle.
- /tax: default tab from profile.default_tax_tab().
- /imports: density toggle.
- density.js localStorage transient override.

Phase 3d (smart suggestion) is explicitly deferred per spec.

29 commits, +78 tests (672 → 750 pass + 1 skip). ([`5576c2a`](https://github.com/chen-star/net_alpha/commit/5576c2a0642731436feb38620611db9951bcafaf))


## v0.23.0 (2026-04-28)

### Feature

* feat(web): rename nav &#39;Wash sales&#39; to &#39;Tax&#39;

Update base.html nav link from /wash-sales (active_page=&#39;wash_sales&#39;)
to /tax (active_page=&#39;tax&#39;). The /tax route sets active_page=&#39;tax&#39; in
context so the nav link highlights correctly.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cf6792e`](https://github.com/chen-star/net_alpha/commit/cf6792ecdd351562b7fdaa1f7269c92c444a5630))

* feat(web): /wash-sales -&gt; /tax 301 redirect (preserves query string)

The wash_sales_legacy handler redirects all /wash-sales requests to /tax.
Old sub-views ?view=table|calendar are normalised to view=wash-sales.
Update test_calendar.py and test_wash_sales_route.py to follow redirects
or target /tax directly. Add test_tax_redirects.py (3 tests).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cfebaca`](https://github.com/chen-star/net_alpha/commit/cfebacad2ba502f05e25f05aae9fd25b76a183a2))

* feat(web): tax.html 4-tab page (wash-sales | harvest | budget | projection)

Create tax.html wrapper template extending base.html with tab nav.
Extract wash-sales tab inner content into _tax_wash_sales_tab.html
(mirror of wash_sales.html inner body, links updated to /tax).
Add _offset_budget_tab.html and _projection_tab.html for budget and
projection tabs.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`40c3d03`](https://github.com/chen-star/net_alpha/commit/40c3d03c55998f9c42a2c246772d1623ca3cc1b1))

* feat(web): add /tax route with tabbed view dispatcher

Extract _wash_sales_context helper from wash_sales.py and wire up new
/tax route supporting wash-sales | harvest | budget | projection tabs.
Register tax_routes.router in app.py. Add test_tax_route.py (4 tests).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b6cd07b`](https://github.com/chen-star/net_alpha/commit/b6cd07bcade9f5d38deda11d62290fd08c1d595e))

* feat(web): load etf_replacements into app.state at startup

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3f74e29`](https://github.com/chen-star/net_alpha/commit/3f74e293cf19404a31fc667728a81e7939171f3e))

* feat(web): pre-trade traffic-light on /sim result

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b9bc9ac`](https://github.com/chen-star/net_alpha/commit/b9bc9ac61e61b8d549015c82840e57862301ffac))

* feat(tax): assess_trade — bracket-push yellow + lot-method hint

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b4550e9`](https://github.com/chen-star/net_alpha/commit/b4550e90fca37c6a62ca5d510ca952ccad226a21))

* feat(tax): assess_trade — wash-sale red verdict

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c264f74`](https://github.com/chen-star/net_alpha/commit/c264f74d2899179356b7821bf2e36da67c3a87c6))

* feat(tax): TaxLightSignal model

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e07b632`](https://github.com/chen-star/net_alpha/commit/e07b632b1a77586a5c7d7774c3fb297b763f7d3d))

* feat(web): year-end projection card on portfolio (with config-missing placeholder)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`eac368f`](https://github.com/chen-star/net_alpha/commit/eac368fa7d6acdd32c85f14adbd2c5285ba54262))

* feat(tax): year-end tax projection (single marginal rate) + planned trades + bracket-push warnings

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`86e9d43`](https://github.com/chen-star/net_alpha/commit/86e9d4367beb47ce78b9a84a7350439245d32954))

* feat(tax): TaxBrackets, TaxProjection, MissingTaxConfig

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`eda2ca9`](https://github.com/chen-star/net_alpha/commit/eda2ca9fbf83f5e9e9b87557c6fe8c717612d848))

* feat(web): offset-budget tile on portfolio KPI strip

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7fce1c1`](https://github.com/chen-star/net_alpha/commit/7fce1c14829258921bf10fe89a20187e1c59f17a))

* feat(tax): compute_offset_budget with $3K cap + carryforward + planned delta

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9c5b33d`](https://github.com/chen-star/net_alpha/commit/9c5b33d434bfa65a27f3391c27e1dc71af0e7f7b))

* feat(tax): OffsetBudget and PlannedTrade models

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0da2f70`](https://github.com/chen-star/net_alpha/commit/0da2f70cb29490fec9626aa5cd1fc6bf79b801ab))

* feat(web): _harvest_queue.html template

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a32bb05`](https://github.com/chen-star/net_alpha/commit/a32bb05257a141fbe752a694d31be72869027986))

* feat(tax): compute_harvest_queue with LT/ST split + account filter

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5bd4543`](https://github.com/chen-star/net_alpha/commit/5bd4543c8e6abc6debf3b625cbc2ae173e47c0f5))

* feat(tax): HarvestOpportunity model + portfolio test conftest ([`6bb47f6`](https://github.com/chen-star/net_alpha/commit/6bb47f63a98a21d57bb00f55b971abc0935df42f))

* feat(engine): cross-asset lockout — open CSP locks out underlying

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bc98513`](https://github.com/chen-star/net_alpha/commit/bc98513c86d9662477181d62d6e736002be90596))

* feat(engine): same-symbol lockout-clear date computation

Adds compute_lockout_clear_date in engine/lockout.py: given a symbol, all trades,
and an as-of date, returns the first wash-sale-safe sale date (most recent buy + 31
days) or None when no buy is in the 30-day window. Handles cross-account buys and
substantially-identical ETF pairs. Structured for Task 6 cross-asset extension.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`02a11d9`](https://github.com/chen-star/net_alpha/commit/02a11d99ef751766339a23c7cbb0965da1811879))

* feat(tax): premium origin extraction for CSP-assigned lots

Adds CSPAssigned / CCAssigned / PremiumOriginEvent models and
extract_premium_origin() to portfolio/tax_planner.py; recovers the
put premium from the STO→BTC-assigned chain for wheel-strategy lots.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9d7dd8c`](https://github.com/chen-star/net_alpha/commit/9d7dd8cba16bf4788138b696e385c2f8d0ba5bd4))

* feat(engine): bundled etf_replacements.yaml + loader with consistency check

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`51a8df5`](https://github.com/chen-star/net_alpha/commit/51a8df50034f451ddbaf7555a88bd2086b8dcd0e))

* feat(audit): hygiene category &#39;tax_config_missing&#39;

Adds a new `tax_config_missing` info-level hygiene issue that surfaces
when no `tax:` section exists in config.yaml. Threads `settings` through
`collect_issues` and `get_imports_badge_count` as an optional kwarg so
all existing callers remain backwards-compatible.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ca23b10`](https://github.com/chen-star/net_alpha/commit/ca23b10f97395fee5ad512adf936dcabd695c3ff))

* feat(config): add TaxConfig model and loader

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bd7539e`](https://github.com/chen-star/net_alpha/commit/bd7539ee2dd1a642ed02417029ee699d0836055d))

### Fix

* fix(engine): bundled SCHD replacement DGRO to avoid etf_pairs conflict

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`fb045a7`](https://github.com/chen-star/net_alpha/commit/fb045a772aa679cd1304b857127f48860ee19783))

### Refactor

* refactor(test): promote seed_lots to portfolio conftest fixture

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`88a3048`](https://github.com/chen-star/net_alpha/commit/88a30485948a4ef2143b22cedcfe8eccc9b290ce))

### Style

* style: ruff import sort + drop unused TaxProjection test import

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`fe822ec`](https://github.com/chen-star/net_alpha/commit/fe822ec2234097c12b70d42c7106785bc8f01759))

### Test

* test(tax): phase-2 smoke — /tax tabs, portfolio embeds, /sim traffic light

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`27877cf`](https://github.com/chen-star/net_alpha/commit/27877cf0ac1701d233a7b1a951ab09ff54dc81bb))

* test(tax): CSP origin round-trips through Repository

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6fc8e53`](https://github.com/chen-star/net_alpha/commit/6fc8e538bc1a9d9a528dc7c7019bbd54eaa55c94))

* test(tax): cross-asset wheel-strategy lockout coverage

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bb41be9`](https://github.com/chen-star/net_alpha/commit/bb41be9db347615ada732eb5314e29b4ea7500d4))

* test(tax): replacement-suggestion wiring in harvest queue

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8b70a01`](https://github.com/chen-star/net_alpha/commit/8b70a0140d6daf2ed6a81e24095ea3bd54790399))

* test(tax): premium offset and only_harvestable filter coverage

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e23ab52`](https://github.com/chen-star/net_alpha/commit/e23ab525fa02be980f30baef9b720beebe510884))

### Unknown

* Merge branch &#39;phase2-tax-planner&#39; — Phase 2 Forward Tax Planner

Adds a forward-looking tax planner: harvest queue, $3K offset budget gauge,
single-marginal-rate year-end projection, and pre-trade traffic light. Renames
/wash-sales to /tax with a 4-tab page (Wash sales | Harvest queue | Offset
budget | Projection); /wash-sales returns 301 to /tax. Wheel-strategy
awareness: extracts CSP-assigned premium offsets from existing synthetic
trade chains, and treats open short puts as substantially identical to the
underlying for cross-asset wash-sale lockout. Bundled etf_replacements.yaml
suggests harvest replacements with consistency check against etf_pairs.yaml.

Read-only — no DB schema changes, no migrations. New optional `tax:` config
section in ~/.net_alpha/config.yaml; absence renders a placeholder card on
/portfolio. Tax-bracket data never leaves the box.

30 TDD tasks, 31 commits + plan + 2 small fixups. 672 tests pass (up from
603 on master); 1 skipped; ruff clean.

Plan: docs/superpowers/plans/2026-04-27-tax-planner.md
Spec: docs/superpowers/specs/2026-04-27-provenance-tax-planner-density-design.md (Section 2)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`4428486`](https://github.com/chen-star/net_alpha/commit/4428486ea26979f10b41d5b3a26703c970045be1))

* plan: phase 2 — forward tax planner

30 TDD tasks covering harvest queue, offset budget, year-end projection,
pre-trade traffic light, wheel-strategy awareness, etf_replacements, and
the /wash-sales -&gt; /tax route rename.

Follows the spec at docs/superpowers/specs/2026-04-27-provenance-tax-
planner-density-design.md (Section 2). No DB schema changes — wheel
awareness is computed on read from the existing synthetic
option_short_open_assigned trade chain.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`6499768`](https://github.com/chen-star/net_alpha/commit/6499768ec3c84bae12f70515fe3ec213f52bc4d8))


## v0.22.0 (2026-04-28)

### Documentation

* docs(plan): Phase 1 implementation plan — Provenance layer

28 TDD tasks covering Sections 1a (drillable KPI tiles), 1b
(reconciliation strip + BrokerGLProvider abstraction), and 1c (data
hygiene queue + nav badge). Phases 2 and 3 deferred to separate plans.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`27a1293`](https://github.com/chen-star/net_alpha/commit/27a1293115cf351d7d9be565ab3f8c32f3377a91))

* docs(spec): provenance, forward tax planner, and style-aware density

Three new feature areas that reposition net-alpha as portfolio tracker
plus tax tool: drillable provenance for every KPI, forward-looking tax
planning (harvest queue, offset budget, year-end projection, pre-trade
traffic light, wheel-strategy aware), and per-account profile picker
with density toggle. Zero new top-level pages; one route rename
(/wash-sales -&gt; /tax) with 301; one DB migration (v8 -&gt; v9 for
user_preferences); one optional config section (tax). Phased
Provenance -&gt; Tax Planner -&gt; Density.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`db68b8a`](https://github.com/chen-star/net_alpha/commit/db68b8a7dc62e4e02449aa321b1d24d0e80e233d))

### Feature

* feat(audit): nav-bar Imports badge with 30s TTL cache

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`266afbd`](https://github.com/chen-star/net_alpha/commit/266afbdc179448889d69c361a8df82e5952b676b))

* feat(audit): POST /audit/set-basis updates trade basis with HTMX swap

Also clears basis_unknown=False in update_trade_basis when cost_basis is set.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`72d77d3`](https://github.com/chen-star/net_alpha/commit/72d77d339643fa68ff0d1cc4e90ac2d72a5052ac))

* feat(audit): embed data-hygiene section on /imports

Adds _data_hygiene.html partial with severity badges and inline HTMX
fix-forms; wires collect_issues(repo) into the imports_page route so
the section appears when issues exist and is hidden when the DB is clean.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3d22b5c`](https://github.com/chen-star/net_alpha/commit/3d22b5c9f5f8dab0a1a0f8095e655de83f83422f))

* feat(audit): hygiene check — duplicate natural-key clusters ([`e911034`](https://github.com/chen-star/net_alpha/commit/e911034d24095f4298106a52759f90ed9f74e3b5))

* feat(audit): hygiene check — orphan sells ([`6dbe94f`](https://github.com/chen-star/net_alpha/commit/6dbe94f0f84c97fcb1e6bd2bd0d36f6cd9ac40ec))

* feat(audit): hygiene check — basis-unknown buys with inline fix form

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e9b16db`](https://github.com/chen-star/net_alpha/commit/e9b16db0f1ea62b6bb96404991e513b3ec59f4e2))

* feat(audit): hygiene check — unpriced symbols

Add _get_unpriced_symbols helper (monkeypatchable seam) and implement
_check_unpriced to emit a warn-severity HygieneIssue per equity symbol
with no cached price quote, with fix_url pointing to /holdings?symbol=X.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8397ae7`](https://github.com/chen-star/net_alpha/commit/8397ae731fd56ff19b6e20694dd01be2ecd4ff29))

* feat(audit): hygiene scaffold with HygieneIssue model + collect_issues dispatcher ([`b31fe7a`](https://github.com/chen-star/net_alpha/commit/b31fe7ac3c74dfcf7e41fc4ff811b8a2a87906a5))

* feat(audit): embed reconciliation strip on ticker page (lazy HTMX load)

Passes account_ids (derived from all accounts with trades for the symbol)
to the ticker template; the template renders one hx-get=&#34;load&#34; div per
account that triggers the /reconciliation/{symbol}?account_id= fragment.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`96570a9`](https://github.com/chen-star/net_alpha/commit/96570a9b856869a8dbf5b00311965d2404873536))

* feat(audit): /reconciliation/{symbol} route + strip + diff fragments

Appends GET /reconciliation/{symbol}?account_id=&amp;expanded= to audit_routes,
renders _reconciliation_strip.html (match/near_match/diff states with HTMX
investigate button) or _reconciliation_diff.html (per-lot table with collapse).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1eb8f31`](https://github.com/chen-star/net_alpha/commit/1eb8f31c55eaa7eb2eca8e579c1a8a9050b90872))

* feat(audit): per_lot_diffs() with cause hints

Appends LotDiff model, per_lot_diffs(), and _cause_hint() to
reconciliation.py; pairs broker G/L lots against net-alpha sell
trades by close date and returns deltas with heuristic cause labels.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d8d30c1`](https://github.com/chen-star/net_alpha/commit/d8d30c11cc7f733affb2094b5d915757e2b6ad6a))

* feat(audit): reconcile() with tolerance + status enum

Adds ReconciliationResult + reconcile() comparing net_alpha realized P/L
against broker G/L lots, classifying results as MATCH / NEAR_MATCH / DIFF /
UNAVAILABLE based on a configurable tolerance threshold (default $0.50).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4555c55`](https://github.com/chen-star/net_alpha/commit/4555c5557ee96a93bcb0eb8d9c275a8672c763cf))

* feat(audit): broker provider registry ([`9f363ce`](https://github.com/chen-star/net_alpha/commit/9f363ce5a5631e85b75f6e446435a9402f36886b))

* feat(audit): SchwabGLProvider over existing get_gl_lots_for_ticker

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`da643b7`](https://github.com/chen-star/net_alpha/commit/da643b7f021b9f23cc4c08eb52a6ea7130869b4e))

* feat(audit): BrokerLot + BrokerGLProvider ABC

Define normalized broker lot row and abstract provider interface for
reconciliation. Supports flexibility across broker GL formats.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`325bf22`](https://github.com/chen-star/net_alpha/commit/325bf228f5a46f3d0072bb9bfc153a3e44b34fa8))

* feat(audit): wire provenance triggers into Portfolio KPIs and Ticker page

- Add &lt;dialog id=&#34;provenance-dialog&#34;&gt; mount point to base.html (all pages)
- Add _resolve_account_id + _build_metric_refs helpers to portfolio route
- Pass metric_refs to _portfolio_kpis.html via portfolio_kpis and portfolio_body handlers
- Decorate Realized P/L (period + lifetime), Unrealized P/L (period + lifetime), Wash Impact, Cash, and Net Contributed KPIs with provenance_link macro; skip Open Position $ (market snapshot)
- Build RealizedPLRef per symbol in ticker_drilldown, decorate YTD Realized P/L
- Add integration tests (TDD: 3 fail → 3 pass)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`68d54fc`](https://github.com/chen-star/net_alpha/commit/68d54fc66a9867c6fc81e8b46fb1d85253491fe4))

* feat(audit): provenance_link Jinja macro with HTMX trigger

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5cce62d`](https://github.com/chen-star/net_alpha/commit/5cce62d72a4a90553622f9b57f8d9e97396662f9))

* feat(audit): full provenance modal template with three sections

Replace placeholder _provenance_modal.html with the complete template
rendering contributing trades, applied wash-sale adjustments (with rule
citation), and contributing cash events in styled tables.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3eacc91`](https://github.com/chen-star/net_alpha/commit/3eacc91a5da9888ffcfa3d9ce464774fe355ecb9))

* feat(audit): GET /provenance/{encoded} returns trace fragment with error fallback

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`35b8f8d`](https://github.com/chen-star/net_alpha/commit/35b8f8dd010a915d2219a6fddd15596f2d7ae9ca))

* feat(audit): re-export public API from package root ([`5d62e95`](https://github.com/chen-star/net_alpha/commit/5d62e95af5c7c32a1eae9fc60678b8c27d43c792))

* feat(audit): provenance_for handles CashRef and NetContributedRef variants

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5653357`](https://github.com/chen-star/net_alpha/commit/5653357c7b3c60edf083d72e11956d64fbe7f93c))

* feat(audit): provenance_for handles WashImpactRef variant

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`168e534`](https://github.com/chen-star/net_alpha/commit/168e534c8ccf16f1a184bd43d824c43d2831ff47))

* feat(audit): provenance_for handles UnrealizedPLRef variant

Adds _unrealized_pl dispatcher and _account_id_match helper; refactors
_trade_account_match to delegate to the new shared helper (DRY).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b8c841f`](https://github.com/chen-star/net_alpha/commit/b8c841fbc1bd8237f778703c82e23300389c52cd))

* feat(audit): provenance_for handles RealizedPLRef variant

Adds the provenance_for dispatcher to provenance.py with the first
variant _realized_pl, which filters repo.all_trades() by period,
symbol, and account_id to build a ProvenanceTrace with signed amounts
and a human-readable metric_label.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`180d1d7`](https://github.com/chen-star/net_alpha/commit/180d1d778072820b2f43869342ec493707ff2c47))

* feat(audit): add ProvenanceTrace, ContributingTrade, AppliedAdjustment types

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f7add98`](https://github.com/chen-star/net_alpha/commit/f7add98055533a6a5b5ae889533ce028f27653d4))

* feat(audit): add MetricRef discriminated union + base64 encoding

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`538422b`](https://github.com/chen-star/net_alpha/commit/538422bf388c91bb357302309b55df094ef4084b))

* feat(audit): scaffold audit package with shared test fixture ([`0384521`](https://github.com/chen-star/net_alpha/commit/03845211d031646418e25d766f22afb547fb6b27))

### Fix

* fix(audit): address final review findings

- Hoist repo.list_accounts() out of per-trade and per-violation loops in
  _realized_pl and _wash_impact (matches existing _unrealized_pl pattern).
- POST /audit/set-basis now triggers stitch + recompute_all_violations and
  invalidates the badge cache so engine state matches the DB immediately.
- Export reconcile, collect_issues, and related types from audit/__init__.py
  per the plan&#39;s stable-import-path contract. ([`70973bd`](https://github.com/chen-star/net_alpha/commit/70973bdeb0eb1cc5748d2c0e3a1048b8d0a726dc))

### Refactor

* refactor(audit): DRY account-display dict construction via _accounts_by_id

Eliminates the last N+1 in _unrealized_pl (was iterating list_accounts() per
open lot). All three dispatcher branches now share one helper.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`e6b7507`](https://github.com/chen-star/net_alpha/commit/e6b75077aca12f45a62ea0f541b2bceeec57576d))

* refactor(audit): hoist all_trades lookup + lift Repository/Trade imports to top

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`953be61`](https://github.com/chen-star/net_alpha/commit/953be611663f9400a00cb7c7ec4f803386284eee))

* refactor(audit): lift seed_import helper into conftest for reuse ([`e7bd860`](https://github.com/chen-star/net_alpha/commit/e7bd8603a22f4047268e9563d821c610e2362e8b))

### Style

* style(audit): move pytest import to module top in test_metric_ref_encoding ([`49ed3a6`](https://github.com/chen-star/net_alpha/commit/49ed3a63fa00844c8da1fdd5e683ec48665a0048))

### Test

* test(audit): phase-1 smoke test — provenance + reconciliation + hygiene

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e39cb5b`](https://github.com/chen-star/net_alpha/commit/e39cb5b3cc237977785ec96f6054b7832e8a5394))

### Unknown

* Merge branch &#39;phase1-provenance&#39; — Phase 1 Provenance Layer

Three sub-features delivered behind the audit/ subpackage:

Section 1a — Drillable provenance:
  audit/provenance.py with MetricRef discriminated union, ProvenanceTrace,
  provenance_for() dispatcher (5 variants). HTMX route /provenance/{encoded}
  feeds a 3-section modal mounted in base.html. Provenance triggers wired
  into Portfolio KPIs and per-symbol Realized P/L on the Ticker page.

Section 1b — Reconciliation strip:
  audit/brokers/ with BrokerGLProvider ABC + SchwabGLProvider + registry.
  audit/reconciliation.py with reconcile() (MATCH/NEAR_MATCH/DIFF/UNAVAILABLE
  + configurable tolerance) and per_lot_diffs() with cause hints. Lazy HTMX
  strip embedded on the Ticker page.

Section 1c — Data hygiene queue:
  audit/hygiene.py with 4 category checks (unpriced, basis_unknown,
  orphan_sell, dup_key). Embedded section on /imports plus inline fix form
  for basis_unknown. POST /audit/set-basis triggers stitch + recompute
  immediately. Nav-bar Imports badge with 30s TTL cache.

Smoke test exercises all three end-to-end. 603 passing, 1 skipped, zero
regressions.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`17ecf85`](https://github.com/chen-star/net_alpha/commit/17ecf85e314342dc203d75ef1c7762ba3d919fd6))


## v0.21.0 (2026-04-27)

### Feature

* feat: short-option lifecycle, assigned-put handling, lot-view correctness

The largest change is treating Sell-to-Open / Buy-to-Close as first-class
trades rather than dropping them. The v1 parser silently ignored both,
which made premium income invisible and hid open short-option positions
on tickers like UUUU/HIMS where the user only sells puts. Now:

* SchwabParser emits STO as a Sell and BTC as a Buy, tagged with
  basis_source markers (option_short_open / option_short_close) so
  downstream code can recognise them. Assigned-put STOs are tagged
  separately (option_short_open_assigned) and paired with a synthetic
  closing trade on the assignment date — this keeps the open-option
  counter honest without double-counting the premium (which is also
  folded into the assigned underlying&#39;s cost basis).
* engine/detector skips synthetic STO/BTC pairs from wash-sale scans
  and excludes BTC trades from seeding new long lots.
* engine/stitch skips STO sells from FIFO matching (an STO has no prior
  long lot — falling through to FIFO mis-matched STO premiums against
  unrelated equity buys, producing nonsense realised P/L).
* portfolio/positions now consumes long-option lots by their STC trades
  AND by GL-only closures (Schwab does not write a transaction row for
  options that expire worthless, only a GL row), and surfaces a
  per-underlying &#34;open option contracts&#34; count so tickers with
  option-only exposure show up on the holdings page.
* web ticker drilldown uses the new open_lots_view so long-closed BTOs
  no longer linger in the &#34;Open lots&#34; table forever.

Other changes:

* Option-symbol regexes accept tickers with trailing digits (Schwab
  appends &#34;1&#34; after corp actions: &#34;GME&#34; → &#34;GME1&#34;). A new
  _opt_ticker_base() helper strips the suffix when matching events so
  pre/post-action option pairs net out cleanly.
* Trade gains an occurrence_index so byte-identical Schwab fill rows
  (split fills on the same day at the same price) get distinct natural
  keys instead of one being silently dropped on import. The suffix only
  appears when &gt; 0, so existing DB rows continue to dedup against
  re-imports.
* Repository.add_import replaces a per-trade try/rollback dedup loop
  (which on a duplicate would unwind the entire session, silently
  losing every trade flushed earlier in the call) with a pre-filter
  that mirrors how cash events are already handled.
* PricingService skips split-history lookups for option-shaped symbols
  to silence noisy 404s; YahooPriceProvider drops &#34;no price&#34; warnings
  to debug.
* web/app.py adds an asset_v cache-buster (server-start timestamp) on
  every static asset reference so a dev restart actually refreshes
  CSS/JS in the browser.
* holdings_filter.js handles the case where Alpine has already
  initialised before the script runs (alpine:init never fires).

Tests: ~750 LOC of new coverage across brokers, db, detector, stitch,
positions, holdings routes, plus a new tests/ingest/test_option_parser.py
for the corp-action ticker regression.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b0ade79`](https://github.com/chen-star/net_alpha/commit/b0ade79dfe1eec5453e210f36b03d272430686a9))


## v0.20.1 (2026-04-27)

### Chore

* chore: update agent instructions and coverage ([`09436a9`](https://github.com/chen-star/net_alpha/commit/09436a98d268dbd9e1c2adc157226cf5bd39dd7a))

### Ci

* ci: fix tests by installing all extras ([`e75da23`](https://github.com/chen-star/net_alpha/commit/e75da23913fa563783844667b722aa96252ca7d9))

### Fix

* fix(web): single-pick import — reuse drop-zone file input via form attribute

The import flow forced users to select files twice: once into the drop
zone for preview, then again in the modal because a separate file input
required re-attachment (&#34;Browser security requires re-attaching the
files at submit time.&#34;). That second pick wasn&#39;t actually required —
HTML&#39;s `form=&#34;...&#34;` attribute lets a control submit with a form that&#39;s
elsewhere in the DOM.

The drop-zone&#39;s `#csv-input` now declares `form=&#34;import-form&#34;` and the
modal form carries that id. The modal&#39;s redundant file picker, &#34;Choose
files&#34; button, file-chip, and re-attach hint are removed.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0d31044`](https://github.com/chen-star/net_alpha/commit/0d31044fadc473f21097e483272e81a43a886e79))


## v0.20.0 (2026-04-27)

### Chore

* chore: ruff format + lift in-function imports to module top ([`06ceb80`](https://github.com/chen-star/net_alpha/commit/06ceb80ac672ab7f542012f2e8b07e8ed2fbd2dc))

### Documentation

* docs(plan): cash flow &amp; balance tracking implementation plan

23 tasks, TDD-ordered, covering: CashEvent domain model, cash_events
table + v8 migration, gross_cash_impact column on trades, Schwab
parser cash-event extraction (13 action types), repository methods,
pure-function computation layer (build_cash_balance_series,
compute_cash_kpis, cash_allocation_slice), Portfolio web layout
update, fixture-based integration tests using both ST and LT CSVs.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`e16caa1`](https://github.com/chen-star/net_alpha/commit/e16caa14ad8e8e925de100f3ef6b455b9520d123))

### Feature

* feat(web): show cash_event_count on imports list summary and detail row ([`1ecf0ab`](https://github.com/chen-star/net_alpha/commit/1ecf0ab8906f8b970fac652b4e744c1eae32acec))

* feat(web): portfolio body — equity + cash side by side, allocation full width ([`3253a2e`](https://github.com/chen-star/net_alpha/commit/3253a2e345c3ea1b9399a524ea3e90db23025aa1))

* feat(portfolio): allocation donut shows Cash slice

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e588ac9`](https://github.com/chen-star/net_alpha/commit/e588ac9eb73d58027bd06bcff02a9ef0271016d8))

* feat(web): add Cash / Net contributed / Growth KPI tiles ([`596a458`](https://github.com/chen-star/net_alpha/commit/596a458de50f8c85aca4fc740666868e4e0b3acf))

* feat(web): add _portfolio_cash_curve.html — ApexCharts balance + contributions ([`2f806af`](https://github.com/chen-star/net_alpha/commit/2f806affdd73c4f75450b1480a7f807ea14a98b9))

* feat(web): wire cash KPIs/points/slice into /portfolio/body context

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`2dc909e`](https://github.com/chen-star/net_alpha/commit/2dc909eba9ee8dd687f6051cebd460121ae538e1))

* feat(portfolio): cash_allocation_slice for donut integration ([`f7a4dfe`](https://github.com/chen-star/net_alpha/commit/f7a4dfebd3a7d3e781a654d73f654fb6b532e395))

* feat(portfolio): compute_cash_kpis ([`c490b09`](https://github.com/chen-star/net_alpha/commit/c490b09c884ef0d04badb4dfd1cf647b40e28739))

* feat(portfolio): add CashFlowKPIs dataclass alongside CashBalancePoint ([`cba5218`](https://github.com/chen-star/net_alpha/commit/cba5218630abd576ac0b8e000ead09be53979e90))

* feat(portfolio): build_cash_balance_series with period and account scoping

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`55b6058`](https://github.com/chen-star/net_alpha/commit/55b60584688cb0f8571f79f5df49557b287da04f))

* feat(import): wire cash_events through add_import and Schwab callers ([`3fca8fd`](https://github.com/chen-star/net_alpha/commit/3fca8fd98b85d822455b6c2adae1e9d84a426235))

* feat(schwab): emit CashEvent for transfers, dividends, interest, fees, sweeps ([`e5690f4`](https://github.com/chen-star/net_alpha/commit/e5690f436abf35b07a42375c6014c72a7d9d7c1d))

* feat(schwab): populate gross_cash_impact from CSV Amount on every trade ([`6933d1d`](https://github.com/chen-star/net_alpha/commit/6933d1dcbf63068dbda7e7ed22b309480061b09e))

* feat(models): add ImportResult for parser return value ([`348c6e4`](https://github.com/chen-star/net_alpha/commit/348c6e483e5688aa4adca38b2fa9d51a1c86a848))

* feat(repo): list_cash_events with account/date scoping ([`b7e52f0`](https://github.com/chen-star/net_alpha/commit/b7e52f06e9effa6a0b07b6595a4b564b63a5a0cd))

* feat(repo): add_cash_events with dedup on (account_id, natural_key) ([`25494d6`](https://github.com/chen-star/net_alpha/commit/25494d68b97b4392076ef7e4d0f6e722aa89742d))

* feat(db): v7→v8 migration for cash_events + gross_cash_impact + cash_event_count ([`0ebbc94`](https://github.com/chen-star/net_alpha/commit/0ebbc94009854e2545c48ccdcf269bcf06a31ec7))

* feat(db): add cash_events table; add gross_cash_impact and cash_event_count columns ([`35b5159`](https://github.com/chen-star/net_alpha/commit/35b51590d29e726134fc10534dcdaaee6dcab428))

* feat(models): add CashEvent domain model with natural_key dedup ([`25a9c5f`](https://github.com/chen-star/net_alpha/commit/25a9c5f4a0a6dd5ca7cbf76b87a8b4a79b9a941e))

### Fix

* fix: review-found correctness bugs in cash-flow

1. (Critical) add_import pre-filters cash events by natural key in-session
   instead of relying on UNIQUE-constraint rollback, which was unwinding
   trades flushed earlier in the same session and silently dropping data.
2. (Important) _trade_cash_delta returns 0 for Security Transfer /
   Journaled Shares rows (basis_source=transfer_in/out). The legacy
   fallback to ±cost_basis was fabricating phantom cash debits/credits
   for share-only transfers.
3. (Important) Schwab parser maps Reinvest Dividend, Long Term Cap Gain,
   Short Term Cap Gain to dividend cash events (DRIP and capital-gain
   distributions are widely used; the previous mapping silently lost them
   as &#34;Unknown action&#34; warnings).

Adds regression tests for each. ([`7d6ce33`](https://github.com/chen-star/net_alpha/commit/7d6ce334a1b5022735ce0b1c56da59c8b6574bac))

* fix: skip option-side actions in parse_full; clarify add_import commit ordering ([`fccd8c3`](https://github.com/chen-star/net_alpha/commit/fccd8c3cf063dca8c2664874b471952628b8b241))

* fix(repo): cascade-delete cash_events on remove_import ([`73704ad`](https://github.com/chen-star/net_alpha/commit/73704ad6f3a7f33971c198f3ebed99de5f360fa7))

### Test

* test(integration): cash events round-trip through both Schwab CSV fixtures

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9f0b6f7`](https://github.com/chen-star/net_alpha/commit/9f0b6f7fd454c6d8b3345f3a9cbede0648cf92b0))

* test(fixtures): add anonymized Schwab Short/Long Term Transactions CSVs ([`ce173d3`](https://github.com/chen-star/net_alpha/commit/ce173d33363690f89219c1bb561e2ae0be1cb1c9))


## v0.19.0 (2026-04-27)

### Documentation

* docs(spec): cash flow &amp; balance tracking design

Persist non-trade Schwab CSV rows (transfers, dividends, interest,
sweeps, fees) into a new cash_events table. Compute running cash
balance, net contributions vs growth, and cash share of portfolio.
Surface in the existing Portfolio page as a new chart alongside the
realized P&amp;L curve, plus KPI tiles and a cash slice in the allocation
donut.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9fe73d2`](https://github.com/chen-star/net_alpha/commit/9fe73d2f7470c090609e10b23a405ccc60448b7a))

* docs: implementation plan for portfolio bugfixes + wash sales merge + splits

Maps the spec into 13 task-by-task steps in 5 phases. Phase 1 quick UI
fixes (items 1+6), Phase 2 Alpine extraction (item 4), Phase 3 page
merge with redirects (item 2), Phase 4 split handling subsystem (item 5),
Phase 5 e2e + manual smoke.

Notes architectural refinement: lots are regenerated on every
recompute_all_violations call, so split + manual-override application
must happen as the final step inside that function (not just at import).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`d4de4a0`](https://github.com/chen-star/net_alpha/commit/d4de4a088898e5cf4eac595c3bec8b3f05b9a3d4))

* docs: portfolio bugfixes + wash sales merge + split handling spec

Covers items 1, 2, 4, 5, 6 from the user&#39;s bug/improvement report:
- Holdings table column cleanup ($ + % unrealized)
- Multi-symbol filter dropdown extraction to a named Alpine component
- Toolbar form action stays on current page
- Detail+Calendar merge into /wash-sales (table/calendar toggle)
- Stock-split handling via Yahoo + manual lot-edit fallback

Item 3 (Portfolio panel additions) deferred per user request.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`fc7f685`](https://github.com/chen-star/net_alpha/commit/fc7f6852600f7ca1b4476b43bd6f39df91cfcca8))

### Feature

* feat(splits): manual per-lot edit UI on /ticker/{sym} (item 5)

Inline edit form on each lot row writes a lot_overrides record with
reason=&#39;manual&#39;. apply_manual_overrides replays the latest edit per
(trade_id, field) at the end of every recompute, so manual edits survive
re-import / unimport / future recomputes.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`31f57ff`](https://github.com/chen-star/net_alpha/commit/31f57ff4a9d514e50c3cb598a9eb826ab0c3b09e))

* feat(splits): auto-sync on first import of a new symbol (item 5)

When a CSV brings in symbols never seen in any prior import, fire
sync_splits for those symbols so existing wash-sale data stays accurate
without manual intervention. Re-imports of known symbols do NOT trigger
fetch -- avoids burning network on every CSV upload.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`251bf76`](https://github.com/chen-star/net_alpha/commit/251bf76d5089abde4dc8ae8e93d865a26364536e))

* feat(splits): /splits/sync endpoint + toolbar Sync splits button (item 5)

PricingService.sync_splits orchestrates fetch -&gt; upsert -&gt; apply. Honors
the prices.enable_remote flag (returns error_symbols when disabled, no
network call). Toolbar button POSTs symbols=ALL and reloads the page.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2105171`](https://github.com/chen-star/net_alpha/commit/2105171a98d74982758cec2c3e75f8aaa14dd5d2))

* feat(engine): apply_splits as final step of recompute (item 5)

apply_splits mutates regenerated lots whose date is before each known
split&#39;s ex-date. Multiplies qty by ratio, preserves total basis (basis is
dollar, not per-share). Idempotent via (trade_id, split_id) check in
lot_overrides. Wired into recompute_all_violations so re-imports and
unimports keep the split-adjustment intact. ([`861c924`](https://github.com/chen-star/net_alpha/commit/861c9248932c64b6bdbb8325c9a3675e3690b4a4))

* feat(pricing): YahooPriceProvider.fetch_splits (item 5)

Wraps yfinance.Ticker.splits with the same error-swallowing pattern as
get_quotes (per-symbol failures return empty list, never raise). Default
on the ABC is to return [] so providers without split data are unaffected.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`50ec151`](https://github.com/chen-star/net_alpha/commit/50ec1517a4a5979549cd588f01e2b8af541b804a))

* feat(db): repository methods for splits + lot_overrides (item 5)

add_split is idempotent on (symbol, split_date). lot_overrides keyed by
trade_id since lots are regenerated on every recompute.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`51d4885`](https://github.com/chen-star/net_alpha/commit/51d4885d8082aa6a0f5701f1930eb0aafd3b8bee))

* feat(db): schema v7 — splits + lot_overrides tables (item 5)

splits: keyed (symbol, split_date) UNIQUE, holds ratio + source + fetched_at.
lot_overrides: audit trail of qty/basis changes, keyed by trade_id (stable
across recompute since lots are regenerated). split_id FK lets apply_split
check idempotency. Also bumps hardcoded version assertions in older migration
tests from 6 → 7. ([`299179b`](https://github.com/chen-star/net_alpha/commit/299179b64e62201bd5ed27f74c76c58fbab54c8f))

* feat(web): merge Detail+Calendar into /wash-sales (item 2)

New route /wash-sales with ?view=table|calendar toggle and a unified
filter bar (ticker, account, year, confidence). Old paths 301-redirect
preserving query string. Top-nav &#39;Detail&#39; becomes &#39;Wash sales&#39;;
&#39;Calendar&#39; link removed.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a00ffcc`](https://github.com/chen-star/net_alpha/commit/a00ffcc0ee6d82186e7ee4fd9483a38d25ac6d3d))

* feat(web): drop Realized col, add % to Unrealized on Holdings (item 1)

The {period} Realized column was redundant with Portfolio KPIs and the
Timeline. Unrealized now stacks dollar and percent inline, color-coded
together. Percent is unrealized_pl / open_cost.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`663c1e2`](https://github.com/chen-star/net_alpha/commit/663c1e28b641bf0f03f21ca8dd0dff470e505f6c))

### Fix

* fix(splits): apply_splits idempotent via canonical formula

The override-existence skip was wrong — lots are regenerated by
replace_lots_in_window on every recompute, so a prior override row
left freshly-regenerated raw lots un-adjusted on the next recompute.
After Sync splits + any other import, SQQQ silently reverted from 10
shares back to 100 — exactly the user&#39;s original bug.

Replace the skip-list approach with a canonical-inputs formula:
lot.quantity = trade.quantity * cumulative_ratio (product of split
ratios with split_date &gt; trade.date). Idempotent by construction —
calling apply_splits any number of times produces the same result.
The lot_overrides table for splits is now purely an audit log.

Adds regression test test_split_survives_repeated_recompute that
fails without this fix.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`38a77dd`](https://github.com/chen-star/net_alpha/commit/38a77dd0f84d78d70e7486dcecbb8f17d1e83f50))

* fix: route CLI lot replacement through recompute_all_violations

Both cli/default.py:run and cli/imports.py:remove_cmd called
detect_in_window + replace_lots_in_window directly, bypassing apply_splits
and apply_manual_overrides. After CLI unimport or re-import of split-
affected symbols, lots were silently un-split-adjusted. Switch both paths
to recompute_all_violations which already handles the post-replace apply
steps. Also: PricingService.sync_splits now calls apply_manual_overrides
after apply_splits so manual edits retain precedence after a sync.
Polish: SplitRow imports lifted to module top, repository methods now
return list[Split]/list[LotOverride] instead of bare list.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6138f3e`](https://github.com/chen-star/net_alpha/commit/6138f3ee623f028be7631e53d4885fd1556a7f53))

* fix(web): extract holdings symbol filter to named Alpine component (item 4)

Inline 27-line x-data block was leaking its expression body as visible text
on the Holdings page when Alpine couldn&#39;t evaluate it. Move to a separate
JS file as a named Alpine.data(&#39;symbolFilter&#39;, ...) component, so the only
inline content is the call site. Also fixes the dropdown&#39;s mis-positioning
(secondary symptom of the same parse failure).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5bfa80f`](https://github.com/chen-star/net_alpha/commit/5bfa80f9dbbaa9ec0884abc3d902dbdb6a5a6841))

* fix(web): toolbar form stays on the current page (item 6)

Previously the period/account toolbar always submitted to /, bouncing the
user from /holdings back to portfolio when they changed Account. Now each
page passes its own toolbar_action.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`2374ec0`](https://github.com/chen-star/net_alpha/commit/2374ec0de6e995d4e2ce9987c51e7ed70d2bed7d))

### Test

* test(splits): e2e split survival across unimport/reimport (item 5)

Adds integration test verifying split adjustments persist through the
full lifecycle of import -&gt; sync -&gt; unimport -&gt; reimport. Includes fix
to remove_import to clean up lot_overrides for deleted trades, allowing
splits to be re-applied on reimport.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`a161b94`](https://github.com/chen-star/net_alpha/commit/a161b944bec4944679db45f87f42e957c8bd7d71))


## v0.18.0 (2026-04-27)

### Chore

* chore: sync uv.lock to pyproject v0.17.0 wash-alpha version

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`16a73e5`](https://github.com/chen-star/net_alpha/commit/16a73e58c64c250a80de127484cc293e3879039b))

### Documentation

* docs: implementation plans for portfolio polish + perf and manual trade CRUD

Two TDD-structured plans (one per spec). Plan A is 7 tasks; Plan B is
14 tasks. Each task lists exact files, complete code, exact test
commands, and a commit step.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`fa508ad`](https://github.com/chen-star/net_alpha/commit/fa508ad485e6aad2e5787844bfff8b68f6a5939b))

* docs: manual trade CRUD spec (Spec B of 2)

Adds add/edit/delete trades on the per-symbol Timeline. Imported
transfer rows become editable for date + basis only; manual rows
are full CRUD. Re-import idempotency preserved via stable
natural_key on edits.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7dc1cdc`](https://github.com/chen-star/net_alpha/commit/7dc1cdcec52d331b4ade88bcdbb04a3210882783))

* docs: portfolio polish + perf spec (Spec A of 2)

Bundles five UI/perf items: consolidate /portfolio fragment fan-out,
move holdings to /holdings tab, multi-select symbol filter, restyle
import-modal file input, equal-width equity/allocation panels.

Manual trade CRUD on the timeline is intentionally deferred to Spec B.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b9b675e`](https://github.com/chen-star/net_alpha/commit/b9b675ef7f3bae8bc9db96ace47e9733c2eef041))

### Feature

* feat(web): Add-trade button + per-row affordances + form modals on ticker page ([`124a128`](https://github.com/chen-star/net_alpha/commit/124a128fa57030bfc8916ef4416769a7fa937b41))

* feat(web): POST /trades/{id}/delete ([`881e59e`](https://github.com/chen-star/net_alpha/commit/881e59e302a3b7d97cc68d4da791e3b33c174d5e))

* feat(web): POST /trades/{id}/edit-manual ([`def487a`](https://github.com/chen-star/net_alpha/commit/def487ae02e5f05ec3836e24971114f7580035bc))

* feat(web): POST /trades/{id}/edit-transfer ([`12b97c1`](https://github.com/chen-star/net_alpha/commit/12b97c1aee41cfab684ee83db997083de9880a20))

* feat(web): POST /trades — create manual trade

Form-driven endpoint mapping Buy/Sell/Transfer In/Transfer Out to
(action, basis_source), validates account/date/quantity, calls
repo.create_manual_trade, and redirects to /ticker/{symbol}.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`38ca20d`](https://github.com/chen-star/net_alpha/commit/38ca20d9da605723b0da1df57d3f9ba08f437329))

* feat(web): Timeline shows Transfer In/Out + provenance badges

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`939de89`](https://github.com/chen-star/net_alpha/commit/939de898b4bcd3dd5265412ed83b3dfc62270c6c))

* feat(web): display_action helper for transfer-aware Timeline labels ([`45f7706`](https://github.com/chen-star/net_alpha/commit/45f7706805a5453ea2b128b211dd48f1df35b250))

* feat(db): Repository.delete_manual_trade ([`94417cc`](https://github.com/chen-star/net_alpha/commit/94417cc378235a78f3ab53681b92acaca1b374a3))

* feat(db): Repository.update_manual_trade ([`3685ea3`](https://github.com/chen-star/net_alpha/commit/3685ea3af7303026befb5b8200683e5e0b6b4f61))

* feat(db): Repository.update_imported_transfer (date + basis|proceeds, immutable natural_key) ([`14e4be5`](https://github.com/chen-star/net_alpha/commit/14e4be591f4f7a58fb55facba23cfd3533990776))

* feat(db): Repository.create_manual_trade + manual: natural_key namespace ([`0e8a4a4`](https://github.com/chen-star/net_alpha/commit/0e8a4a4202c6eb2acff912f00ca2bd3019c67e27))

* feat(models): Trade.is_manual + Trade.transfer_basis_user_set

Add is_manual and transfer_basis_user_set fields to the Pydantic Trade
model and TradeRow SQLModel, relax TradeRow.import_id to nullable, and
propagate both flags through _row_to_trade so all_trades() carries them.
Update v5→v6 migration tests to reflect completed Task 2 state.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ac08d3c`](https://github.com/chen-star/net_alpha/commit/ac08d3c8e19778dfe2c17f4ecb24042c74e60b0b))

* feat(db): v5→v6 — add trades.is_manual + transfer_basis_user_set; nullable import_id

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1414a3c`](https://github.com/chen-star/net_alpha/commit/1414a3cabacaf2393a46fa4f2a9a49eee44cafee))

* feat(web): multi-select symbol filter popover on holdings table

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a388fcf`](https://github.com/chen-star/net_alpha/commit/a388fcf9c4c314380c1888da1c91c7c9d5602a1c))

* feat(web): replace ?q= with ?symbols= multi-select filter on /portfolio/positions ([`ea460fc`](https://github.com/chen-star/net_alpha/commit/ea460fc765d01bcccb2c0534987b1834514bab81))

* feat(web): /holdings page + nav link

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`be60977`](https://github.com/chen-star/net_alpha/commit/be60977cf2940491b706a6de017bf3592fbc3193))

* feat(web): single-fragment load on /portfolio (5x→1x request) ([`9a496c2`](https://github.com/chen-star/net_alpha/commit/9a496c2d923019b43bb8215c6503fe12e1a832bc))

* feat(web): /portfolio/body bundled fragment

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ef99fc2`](https://github.com/chen-star/net_alpha/commit/ef99fc2fb1d0bf7a5347c53a328e107941be5cea))

* feat(web): styled Choose Files button + file-count chip in import modal ([`5467aa9`](https://github.com/chen-star/net_alpha/commit/5467aa995c5b7c8ff167b85447a46bea3decc8cc))

* feat(web): equalize equity-curve and allocation panel widths ([`f5e03aa`](https://github.com/chen-star/net_alpha/commit/f5e03aa75a4222727288a5a3c538bf873629f28e))

### Fix

* fix(web): account allow-list from list_accounts; add duplicate-count and violation-removal tests

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`678f6f9`](https://github.com/chen-star/net_alpha/commit/678f6f92a181140f67cbebd6738db0e8151bcfa9))

* fix(test): include is_manual + transfer_basis_user_set in raw trade insert ([`d93f05b`](https://github.com/chen-star/net_alpha/commit/d93f05b848fb6937e0db93779d787e4d738caffb))

* fix(web): correct hx-target and smart-quote regressions in holdings table fragment

Replace legacy hx-target=&#34;#portfolio-positions&#34; with &#34;#holdings-positions&#34; across all Show/Pagesize/Pagination buttons; fix Unicode smart quotes (U+201C/201D) on the status-hint span class attribute; add two regression tests covering both issues.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b4f95b4`](https://github.com/chen-star/net_alpha/commit/b4f95b4aeee76b9a106564ac020fe1eb49607d5d))

### Test

* test(integration): re-import preserves user edits to transfer rows

End-to-end check that editing a transfer-in row&#39;s date+basis survives
a re-import of the same Schwab CSV (idempotent dedup via natural_key).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ab83c0c`](https://github.com/chen-star/net_alpha/commit/ab83c0c4ddaf4f5a4c84edccb1b208dea830c8bc))

### Unknown

* wip: pre-Plan-A/B checkpoint

Snapshot of in-progress work prior to executing the
2026-04-26 portfolio-polish-and-perf and manual-trade-crud plans.

Includes:
- schwab.py: transfer-in/out parsing + put-assignment basis offsets
- portfolio/positions.py: FIFO lot consumption with GL closure fallback
- portfolio/equity_curve.py: dual-series (realized + total) curve
- web templates: _portfolio_table + _portfolio_equity_curve restyle iterations
- repository/migrations/tables/domain: small alignment changes
- AGENTS.md / CLAUDE.md: stale GitNexus stat refresh

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`e36e663`](https://github.com/chen-star/net_alpha/commit/e36e66371f820a86db1ad8d1c9a7f5f0b9ee92f4))


## v0.17.0 (2026-04-27)

### Chore

* chore: post-review cleanup — drop dead routes, add static-asset tests, polish

Following the cross-cutting code review, addresses five gaps:

- Delete `_portfolio_wash_impact.html` + `_portfolio_lot_aging.html` and the
  two now-unreachable route handlers `/portfolio/wash-impact` and
  `/portfolio/lot-aging`. Wash impact info is in the KPI strip; lot-aging
  detail lives on the ticker page. Drop the corresponding tests.
- `static/charts.js`: expose `warn` (#FF9F0A) in the theme `colors` table.
- `app.src.css`: add `font-feature-settings: &#34;tnum&#34;, &#34;ss01&#34;` on `.num`.
- `tests/web/test_static.py`: add file-existence smoke tests for the
  ApexCharts vendor JS+CSS and `charts.js`.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`42f7c54`](https://github.com/chen-star/net_alpha/commit/42f7c547b124e6232a3e1ea9bf5aa770f8724367))

* chore: remove treemap module, template, tests, and TreemapTile model ([`df70598`](https://github.com/chen-star/net_alpha/commit/df70598d623516d0800bcea09e9c62bf0d568a61))

### Documentation

* docs: UI visual theme design spec + implementation plan ([`937eda8`](https://github.com/chen-star/net_alpha/commit/937eda842f0af6d23b80d5bbff332424333ce98a))

* docs: update CLAUDE.md — treemap → allocation + add wash_watch in portfolio module list ([`8f0a69c`](https://github.com/chen-star/net_alpha/commit/8f0a69c0a2f0c994d63ca3d7f2346f16cd82f2b2))

### Feature

* feat(web): restyle sim + detail + ticker + error pages

Apply Apple-dark design tokens across all remaining web pages:
- sim.html: seg/seg-active action picker, surface inputs, panel form
- _sim_buy_result / _sim_sell_result: panel cards, num cells, pos/warn labels
- detail.html: panel totals bar with chip-confirm/probable/unclear, surface inputs;
  adds {% set active_page = &#39;detail&#39; %}
- _detail_table.html: panel+net-table, chip-* confidence, info/warn source badges,
  hover:bg-surface-2 rows
- ticker.html: panel KPI grid, net-table timeline; adds panel wrappers
- _lots_table.html: net-table, text-label-2 empty state, bg-warn/5 wash-adj rows
- _schwab_lot_detail.html: panel+net-table, text-neg wash-sale Yes, text-label-3 No
- error.html: panel centered card, text-label-2 detail, bg-surface-2 traceback,
  btn-ghost &#34;← Back&#34; link

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c83ac70`](https://github.com/chen-star/net_alpha/commit/c83ac707e17b93000942235bfa19ee914d9ab8e3))

* feat(web): restyle imports + drop zone + modal + toast

Apply Apple-dark design tokens to the full imports stack: panel/net-table
wrappers, dashed drop zone with rgba border, surface-variant modal,
pos/warn colours in detection cards, label-uc labels, and bg-pos toast.
Adds {% set active_page = &#39;imports&#39; %} for topbar highlight.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`93ac3f5`](https://github.com/chen-star/net_alpha/commit/93ac3f56634d84092824588d2e7a6c1b5a63ad19))

* feat(web): restyle calendar pages — Apple-system colors for ribbons + dots

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5717400`](https://github.com/chen-star/net_alpha/commit/571740003c17ce74151c8edd783e8c3283c2a6de))

* feat(web): restyle positions table, toolbar, empty state under new tokens

Replaces all slate/white/emerald Tailwind classes in the three portfolio
fragments with the new design-token components (net-table, panel, seg,
seg-active, label-uc, btn, text-pos/neg, text-label-*, bg-surface-*).
Adds ticker-initial icon block to the Symbol cell and hairline borders
on select and pagination controls via CSS variable.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7502a6d`](https://github.com/chen-star/net_alpha/commit/7502a6d3dcf601a9eb4afe5b88b1ae6bb310d896))

* feat(web): equity curve via ApexCharts area chart with violet &#39;+ unrealized&#39; marker ([`632df82`](https://github.com/chen-star/net_alpha/commit/632df82ddffce85e92e5bfc8f3aaf39112f8b1a5))

* feat(web): shared ApexCharts dark theme + merge helper at /static/charts.js ([`b69d2ad`](https://github.com/chen-star/net_alpha/commit/b69d2adb62fc626382d573b688bdeca91b7a1679))

* feat(web): /portfolio/wash-watch fragment route

Wire recent_loss_closes() into a GET handler that renders the
_portfolio_wash_watch.html partial; supports ?account= and ?window_days=
query params.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`220926a`](https://github.com/chen-star/net_alpha/commit/220926ada0a45246b45f1376ef025eecba2153df))

* feat(web): wash-watch partial — countdown rows w/ red→amber→green safe-bar

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4218b2c`](https://github.com/chen-star/net_alpha/commit/4218b2ccfe4b66c6ca411d5c195d602d12b1fb93))

* feat(portfolio): recent_loss_closes — wash-sale watch aggregation

Add LossCloseRow model and recent_loss_closes() pure function that
aggregates sell trades with negative realized P/L in the last N days,
collapsed per symbol (most recent close, summed loss), sorted by
close_date desc.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5e7d58c`](https://github.com/chen-star/net_alpha/commit/5e7d58c0157a5d788f00cf3b6e348b4ded905c2b))

* feat(web): portfolio.html — equity+allocation row, wash-watch slot, drop treemap ([`e511171`](https://github.com/chen-star/net_alpha/commit/e5111715583cbe13e136dd044b4858eec0c894d8))

* feat(web): replace /portfolio/treemap route with /portfolio/allocation ([`83d2717`](https://github.com/chen-star/net_alpha/commit/83d2717f3d2e57c0a61919a40a8b4f3c7384f3be))

* feat(web): allocation partial — donut + concentration stats + ranked chips ([`e8ee4ba`](https://github.com/chen-star/net_alpha/commit/e8ee4ba6eb54c89d734e217e9df63a05a541f166))

* feat(portfolio): build_allocation — donut/leaderboard view + concentration stats

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9feac9d`](https://github.com/chen-star/net_alpha/commit/9feac9d0f267692808cb1ad3c07d7211d18e97c7))

* feat(web): combined hero KPI cards (Realized/Unrealized) + Open$/Wash mini

Collapse 6-card KPI partial into 4-card grid-cols-12 layout: Realized hero (4 cols, kpi-hero halo) with YTD+Lifetime side-by-side, Unrealized hero (4 cols), Open position $ mini (2 cols), Wash impact mini (2 cols). Route now calls compute_wash_impact and passes wash_impact_total + wash_violations into template context.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a90b19f`](https://github.com/chen-star/net_alpha/commit/a90b19f4375c70d58644c07959210897bee6996d))

* feat(web): restyle base.html — vibrancy topbar, Inter+JBM, ApexCharts include

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`414984d`](https://github.com/chen-star/net_alpha/commit/414984dd94c1cdd036dc0dd3d6c444dd8ea06ef6))

* feat(web): @font-face Inter+JBM, type scale, full component library

Add 6 @font-face declarations for Inter (400/500/600/700) and JetBrains
Mono (400/500), expand @layer base with dark color-scheme, Inter font
features/antialiasing, h1-h3 type scale, and .num tabular-nums rule.
Replace minimal @layer components with full design-system library:
.panel, .panel-head, .label-uc, .kpi, .kpi-hero, .seg, .pill, .topbar,
.nav-link, .chip-confirm/probable/unclear, .net-table, .brand-mark, plus
back-compat aliases; var(--color-*) used directly where @apply text-*
tokens conflict with Tailwind v4 reserved names.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9c93d2c`](https://github.com/chen-star/net_alpha/commit/9c93d2cfa53c603754fe81cbdf4b4e02e897f0a0))

* feat(web): new Apple-dark color tokens, font stack, radii in tailwind config

Replaces the old small v3-style palette with the full Apple-dark design
system (canvas, hairline, label-tier text, P/L semantics, rank slots, brand
cyber). Updates app.src.css from Tailwind v3 directives to v4 @import/@theme
syntax required by pytailwindcss 0.1.4 (bundles Tailwind v4). Back-compat
aliases (confirmed, probable, unclear, primary, secondary, accent, ink) keep
existing templates rendering until they are restyled.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`51d6aa3`](https://github.com/chen-star/net_alpha/commit/51d6aa3d56ea9aed73149f40f9766bd125e34593))

* feat(web): vendor ApexCharts 3.51 (no runtime npm)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7c73a80`](https://github.com/chen-star/net_alpha/commit/7c73a80acff31729d8f9b6d580eb0c762c007c09))

* feat(web): vendor Inter and JetBrains Mono woff2 fonts

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0b98082`](https://github.com/chen-star/net_alpha/commit/0b980820b753017200db5c5ab352c7193a5d5916))


## v0.16.1 (2026-04-26)

### Fix

* fix(web): include current year and trade-activity years in Calendar YEAR dropdown

The dropdown derived its options solely from violation loss_sale_date years,
so a year with trade activity but no detected wash sales (e.g. the current
year on a fresh slate) was missing — the page header still selected it via
today.year, but the user couldn&#39;t pick it from the dropdown. Union trade
years and the current year into the option set, sorted newest-first.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1facffc`](https://github.com/chen-star/net_alpha/commit/1facffc422a63dd9d11d0fcfef7d8a55bec573d4))


## v0.16.0 (2026-04-26)

### Chore

* chore: ruff format ([`1a75a54`](https://github.com/chen-star/net_alpha/commit/1a75a54c2cfc215b374e860f083c3e64967f8816))

* chore: refresh gitnexus index stats and sync uv.lock to v0.15.1

- AGENTS.md / CLAUDE.md: gitnexus symbol/relationship/flow counts
  refreshed after the Phase 2 merge (1711 → 2436 symbols).
- uv.lock: wash-alpha version pinned to 0.15.1 to match the
  current pyproject.toml after the semantic-release bump (8d09649).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f0a3421`](https://github.com/chen-star/net_alpha/commit/f0a34219d1078dacc5b4c9d83d9ce70046301501))

### Feature

* feat(web): detail page totals bar + group-by-ticker + Lag/Source columns ([`1ced6b8`](https://github.com/chen-star/net_alpha/commit/1ced6b83eee82dca73e67fcdcc5b6a90ca01b812))

* feat(web): wire detail summary, ticker grouping, and lag-sort into the route ([`26279a1`](https://github.com/chen-star/net_alpha/commit/26279a18fb19690a89b2803b14d75ea88bd12525))

* feat(portfolio): add detail-page aggregations (summary, grouping, lag, source label) ([`3f92461`](https://github.com/chen-star/net_alpha/commit/3f92461b7b22aa16b191301a30a690fab88feef4))

* feat(web): POST /sim dispatches BUY/SELL with date and renders new result partials ([`55dd5ca`](https://github.com/chen-star/net_alpha/commit/55dd5ca4b6914ea20c1a77d1741e8eecdb219d1d))

* feat(web): unified sim form with BUY/SELL toggle and date picker ([`c71cfee`](https://github.com/chen-star/net_alpha/commit/c71cfeebc0c068c2bf33cf17678235d87a4e6d19))

* feat(engine): add simulate_buy() pure function with per-account FIFO loss matching

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`5a9f544`](https://github.com/chen-star/net_alpha/commit/5a9f5444fc2f8414145156f52c16a7ae8cb6670f))

### Test

* test(web): integration coverage for detail totals, grouping, lag sort, source ([`749e798`](https://github.com/chen-star/net_alpha/commit/749e798df8af50dc768253c5d629704fa3012364))

* test(web): cover BUY/SELL dispatch on POST /sim with date and account ([`6fd7cc1`](https://github.com/chen-star/net_alpha/commit/6fd7cc179af282b1f82831e197d5545c8d6274a4))

* test(engine): add ETF substantially-identical pair tests for simulate_buy ([`e830d6e`](https://github.com/chen-star/net_alpha/commit/e830d6e1e92d348be560dfdae8e2cd7ce7a6395c))

* test(engine): add day-0/30/31 boundary tests for simulate_buy ([`d05dafb`](https://github.com/chen-star/net_alpha/commit/d05dafb9af7dd8625879fe2d9bd15f76d5f1472a))

### Unknown

* Merge branch &#39;feat/phase3-sim-and-detail&#39; — Phase 3 sim BUY support + detail enhancements ([`cedb4de`](https://github.com/chen-star/net_alpha/commit/cedb4de9ef35f846f2dd945c960f4af6fae7e99a))


## v0.15.1 (2026-04-26)

### Documentation

* docs(plan): add Phase 3 implementation plan — sim BUY support + detail enhancements ([`eedc08c`](https://github.com/chen-star/net_alpha/commit/eedc08cf4bea9a7991a55584ff37ef96d2acb364))

### Feature

* feat(domain): add SimBuyMatch and SimulationBuyOption models ([`5020ec1`](https://github.com/chen-star/net_alpha/commit/5020ec1d88e60d8f798b10b81b5649c5be2e9eea))

### Fix

* fix(web): polish Portfolio page — treemap, equity axes, table paging, KPI

- Allocation treemap uses squarified algorithm for square-ish tiles;
  adds 220px height, 2px gaps, layered labels, hover-detail tooltip,
  and an &#34;OTHER&#34; bucket P/L that surfaces as unknown when every
  rolled-up position is itself unpriced.
- Equity curve gains $-labelled Y gridlines (always includes $0),
  Jan-Dec X axis, sell-event dots, a tethered &#34;+ unrealized&#34; dot,
  and per-point hover tooltips.
- Position table gains 25-row HTMX paging, an Open / All toggle
  (All adds period-closed positions tagged &#34;closed&#34;), and native
  per-column tooltips that explain each calculation.
- KPI grid gains &#34;Net P/L (Lifetime) = Lifetime Realized + Unrealized&#34;
  in slot 6 plus tooltips on every existing card.
- compute_kpis now returns partial sums when only some symbols are
  unpriced (priced_market - priced_basis is correctly subset-scoped),
  along with a missing_symbols list. The KPI fragment surfaces an
  asterisk on each affected card and an amber footer naming the
  unpriced tickers. Falls back to &#34;—&#34; only when every equity lot
  is unpriced (true no-data).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f125d21`](https://github.com/chen-star/net_alpha/commit/f125d2116cae9b52160a048957a4537ffa00e933))


## v0.15.0 (2026-04-26)

### Chore

* chore: ruff format

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`4b2c2f4`](https://github.com/chen-star/net_alpha/commit/4b2c2f4ba403c1c0c8a790d10b0b5a640e1215fc))

### Documentation

* docs(plan): add Phase 2 implementation plan — calendar dual-ribbon + imports notes

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`ae0befc`](https://github.com/chen-star/net_alpha/commit/ae0befcd8a7c151118d4b0174b87b821a3d50bc4))

### Feature

* feat(web): embed drop zone on imports page

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`e90fd9f`](https://github.com/chen-star/net_alpha/commit/e90fd9f04be6076a82358edf0afec39f0ef302c6))

* feat(web): GET /imports/{id}/detail returns expandable detail panel

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`a8e5bc1`](https://github.com/chen-star/net_alpha/commit/a8e5bc136eb4f7554e57324dd8f0cde750956241))

* feat(web): summary line and expand toggle on imports table

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`a266084`](https://github.com/chen-star/net_alpha/commit/a2660845d5161d550900d980fd7f74f3069dd23b))

* feat(web): compute and persist import aggregates on upload

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`6d50d85`](https://github.com/chen-star/net_alpha/commit/6d50d85721b97249abaae3b55c7b1dff02f6400b))

* feat(db): backfill import aggregates on init_db

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`aedb6da`](https://github.com/chen-star/net_alpha/commit/aedb6da80c911c15641c3f1540afb3a1390b0cc0))

* feat(import): backfill aggregates for legacy import rows

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`14cbae7`](https://github.com/chen-star/net_alpha/commit/14cbae782c8668fcc262042f173d213cee1bceb8))

* feat(repo): persist and surface import aggregates; add get_import_detail

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1fef99f`](https://github.com/chen-star/net_alpha/commit/1fef99f88745efe7c3c21c4146d354f4d6139968))

* feat(import): add compute_import_aggregates pure function

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1b86c73`](https://github.com/chen-star/net_alpha/commit/1b86c73a13a9bf4de211ee2768dce09249e7efd8))

* feat(models): extend ImportRecord and ImportSummary with v4 aggregate fields

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1b3a334`](https://github.com/chen-star/net_alpha/commit/1b3a334b4b5f2c7ebba530c033e7a16bd25cec07))

* feat(db): schema v4 — add aggregate columns to imports

Adds 6 nullable columns to the imports table (min/max trade dates,
equity/option/expiry counts, parse warnings JSON) for the calendar
imports Phase 2 backfill. Updates existing migration tests to use
CURRENT_SCHEMA_VERSION instead of hard-coded version literals.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b1790ec`](https://github.com/chen-star/net_alpha/commit/b1790ecb1f00998d0ef970b2999ac9ae0d26abd8))

* feat(web): stack monthly P&amp;L ribbon above wash-sale dots

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7d6406c`](https://github.com/chen-star/net_alpha/commit/7d6406c7b5ab5ba2812691f7d98b47024eb7f90f))

* feat(web): add monthly P&amp;L ribbon partial

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3c71190`](https://github.com/chen-star/net_alpha/commit/3c711901affc25b6c2a7fff94c602a415ed5a772))

* feat(portfolio): add monthly_realized_pl aggregator

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`a51885d`](https://github.com/chen-star/net_alpha/commit/a51885da610263f6867e96c036d808b093f6c747))

* feat(portfolio): add MonthlyPnl model for calendar ribbon

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`30aaea6`](https://github.com/chen-star/net_alpha/commit/30aaea621e174d919c8d95b66d74f32d3bf4a137))

### Test

* test(db): cover v3 → v4 migration

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3b4b652`](https://github.com/chen-star/net_alpha/commit/3b4b6529846969417da46f4ee2251f0e4b1c82c4))

* test(portfolio): add Dec-31/Jan-1 boundary case for monthly_realized_pl

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0d1f170`](https://github.com/chen-star/net_alpha/commit/0d1f170f8a56c8532008de0e1e5d331fc1ea8ed1))

### Unknown

* Merge branch &#39;feat/calendar-imports-phase2&#39; — Phase 2 calendar dual-ribbon + imports notes

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`53fac1f`](https://github.com/chen-star/net_alpha/commit/53fac1f2837801910f3178798eda3dfd69a497e8))


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
