# CHANGELOG



## v0.41.2 (2026-05-02)

### Chore

* chore: regen lock for 0.41.1 ([`1946708`](https://github.com/chen-star/net_alpha/commit/19467089ec156e0372fa5d7ce1fde0e5e8c6cdde))

### Fix

* fix(portfolio): correct realized P&amp;L pairing, transfer basis, and account chips

Three independent fixes plus pre-existing transfer-basis editor work:

1. realized_pl_from_trades now distributes STO premium across multiple
   BTCs by contract quantity. Previously each BTC subtracted its cost
   from the *full* STO premium for the (account, ticker, strike, expiry,
   cp) key, so a 2-contract STO closed by two 1-contract BTCs credited
   the entire premium twice — inflating lifetime realized P&amp;L. Verified
   against Schwab&#39;s Realized G/L: TSLA lifetime drops from $3,841.11 to
   $2,142.44 to match.

2. compute_open_positions splits accounts into open vs all-trade maps so
   the position-row chip on the Open tab reflects only currently-held
   accounts, not historical churn. NVDA YTD only in `lt` no longer
   surfaces `lt+st`.

3. update_trade_basis preserves basis_source for transfer rows
   (transfer_in / transfer_out) and flips transfer_basis_user_set=True
   instead of clobbering basis_source to &#34;user_set&#34;. The clobber was
   making compute_open_positions count user-set transfer basis as cash
   buys, inflating Cash invested / sh.

4. Schema migration v14 retroactively restores basis_source on existing
   transfer rows where transfer_date is set but basis_source had been
   clobbered to user_set by the old single-lot save path.

5. Imports page and positions-pane set-basis multi-lot editor refinements
   that were already in flight, included for cohesion since they share
   the transfer-basis editing surface.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9001a08`](https://github.com/chen-star/net_alpha/commit/9001a08d372f6ba151be7dee10cc2ac79753dced))


## v0.41.1 (2026-05-02)

### Fix

* fix(web): unbreak imports drop-zone and delete; add bulk delete

The settings drawer&#39;s Imports tab loader uses hx-select=&#34;main &gt; *&#34;
to strip page chrome from the lazy-loaded /imports/_legacy_page.
HTMX inherits hx-* attributes to descendants, so the drop-zone&#39;s
preview POST and the per-row delete DELETE inherited that selector
too. Their responses are bare HTML fragments without a &lt;main&gt;
wrapper, so the inherited selector matched nothing and HTMX
silently swapped empty content into the target — blanking the
import modal (broken file import) and the imports table (delete
appeared to wipe the page). Adding hx-disinherit=&#34;hx-select&#34; on
the loader keeps children using their own targets verbatim.

While in there, added a POST /imports/bulk-delete endpoint plus
per-row checkboxes and a &#34;Delete N selected&#34; submit button so
users can clear multiple imports without N confirms. The bulk
endpoint batches the wash-sale recompute (one re-stitch per
affected account, one global recompute) instead of doing it per
removed import.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`104d70b`](https://github.com/chen-star/net_alpha/commit/104d70b9dd5809270cfcb40797376e52296db3ce))


## v0.41.0 (2026-05-02)

### Feature

* feat(web): add light mode with Light/Dark/System toggle

Adds a full light theme alongside the existing Apple HIG dark theme.
Users pick Light, Dark, or System (follow OS preference) from the new
Appearance section in the settings drawer&#39;s Density tab.

Theme tokens are CSS custom properties under [data-theme=&#34;light&#34;] /
[data-theme=&#34;dark&#34;] selectors; Tailwind utilities resolve via var() so
the entire UI flips at runtime. Light palette uses Apple&#39;s documented
HIG light-mode equivalents (systemRed.light, systemGreen.light, etc.)
that meet WCAG AA on a white surface.

The preference persists per-account via the existing user_preferences
pipeline (new theme column, v12 → v13 migration). A localStorage shadow
plus an inline FOUC-prevention script in &lt;head&gt; resolves and applies
data-theme before stylesheets load, so first paint is always correct.
A matchMedia listener re-applies on OS-pref flips when System is
selected.

ApexCharts re-renders on theme change: charts.js now reads colors live
from CSS vars via getComputedStyle and exposes a render-function
registry that refresh()es on the theme:change window event the toggle
dispatches.

Sweep replaces ~150 hardcoded literal colors across 30+ templates with
the matching tokens (rgba hairlines → --color-hairline; bg-black/X
backdrops → --color-overlay-*; inline semantic hex → var(--color-pos)
etc.; 6 .invert opacity-XX icons → new .icon-mono utility).

11 new tests cover: v13 migration (column add, default, idempotent,
schema bump) and the /preferences route (theme write, default, invalid
rejection). Existing schema-version assertions bumped from 12 to 13.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`894be54`](https://github.com/chen-star/net_alpha/commit/894be542083205e75e243c2675e8e23b6591472b))


## v0.40.1 (2026-05-01)

### Chore

* chore: scrub references to internal docs/ folder

Removes dangling pointers to docs/superpowers/specs/* now that the docs/
folder is local-only and excluded from the repo.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`16be1ab`](https://github.com/chen-star/net_alpha/commit/16be1ab8871174c447e0171ca5dcaa6f83a67ee9))

* chore: scrub AI scaffolding, generated artifacts, and internal docs from repo

Untracks third-party AI skill plugin data (.agent/, .agents/, .junie/,
.claude/skills/), generated coverage report, skills-lock.json, the empty
&#39;nano&#39; file, and the docs/ folder. Adds matching .gitignore entries plus
.DS_Store / editor swap files. Files remain on local disk; only their
tracked status is removed.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3048af6`](https://github.com/chen-star/net_alpha/commit/3048af6f66bc4f4200359790e0089268c5fb6626))

### Documentation

* docs: add monthly PyPI downloads badge to README

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`fe82b14`](https://github.com/chen-star/net_alpha/commit/fe82b14c4819c938cb342f338a315d574e43e3fd))

* docs: refresh AGENTS.md, CLAUDE.md, README.md for v0.40.0

Bring the top-level docs in line with the matured codebase: web UI is now
the primary interactive surface (Portfolio, Positions, Tax, Sim, Imports,
Ticker, Settings), with new subsystems (audit/reconciliation, splits,
position targets, harvest planner, sim suggestions, manual trade CRUD).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`e736073`](https://github.com/chen-star/net_alpha/commit/e736073709a655428e246f100c70ec646682a39c))

### Fix

* fix(packaging): add PyPI metadata, project URLs, and LICENSE

The PyPI page rendered with no README, no GitHub link, and no classifiers,
giving installers no path back to the repo. Adds:

- readme = &#34;README.md&#34; so the full README renders on PyPI
- [project.urls] with Homepage / Repository / Issues / Changelog so the
  PyPI sidebar links to GitHub
- license, classifiers, and keywords for category browsing and search
- LICENSE file to back the MIT claim in the README
- Star call-to-action near the top of the README to convert PyPI readers

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`cfdc046`](https://github.com/chen-star/net_alpha/commit/cfdc046b47ae395f1e3886663fa61bf6beddbfaa))


## v0.40.0 (2026-04-30)

### Feature

* feat(web): resizable settings drawer, chart zoom, positions search, sim form alignment

- Settings drawer: drag the left edge to expand/shrink. Persists to
  localStorage; clamped to [360px, viewport-60px]. Handle uses inline
  styles so it doesn&#39;t depend on Tailwind utility compilation.
- Equity / Cash &amp; Contributions charts: enabled ApexCharts&#39; zoom toolbar
  (drag-select range, zoom in/out, pan, reset) with autoScaleYaxis.
- Positions page: new symbol-search box above the tabs filters every row
  (stocks, options, at-loss, closed, plan) by underlying ticker. Options
  match on the underlying so typing &#39;SPY&#39; shows every contract on it.
  Filter survives HTMX swaps via htmx:afterSwap.
- Sim form: switched to items-start with fixed label/input heights so all
  six controls share the same horizontal baseline regardless of helper-text
  presence.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`ee2006c`](https://github.com/chen-star/net_alpha/commit/ee2006cc111eaf3a060dd0646cff14af8e7a4d04))

* feat(web): wire real content into Profile / ETF pairs / About drawer tabs

Replaces the Phase 1 &#39;Coming soon&#39; placeholders with the per-tab templates,
exposes app_version / data_dir_path / pricing_remote_enabled / etf_pairs_data
to Jinja so the new tabs can render, and updates the regression test to assert
real content rather than placeholder copy. Also bumps GitNexus index counts
in AGENTS.md / CLAUDE.md.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9227416`](https://github.com/chen-star/net_alpha/commit/92274160b1b5a169192dd826da635509f871b84f))

### Refactor

* refactor(planner+web): ORDINARY_LOSS_CAP constant + pass tax_saved as dict

Extract the §1211 $3,000 ordinary-income-offset cap into a named constant
ORDINARY_LOSS_CAP (replacing 4 bare Decimal(&#34;3000&#34;) literals). Replace the
fragile Pydantic __dict__ smuggle in the harvest_plan endpoint with a plain
parallel dict passed explicitly to the template context.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3b99eeb`](https://github.com/chen-star/net_alpha/commit/3b99eebda54cb71058551cd7cb020206ae1fa42d))


## v0.39.0 (2026-04-30)

### Feature

* feat(web): collapsible data-quality groups on Imports page

Groups hygiene warnings into Missing basis / No price quote / Missing dates
buckets rendered as &lt;details&gt; elements; the first non-empty bucket is open
by default, replacing the previous flat list in _data_hygiene.html.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f8acc78`](https://github.com/chen-star/net_alpha/commit/f8acc786b30f2ce59fcc633fbc99be50e8ea665a))

* feat(web): per-row &#39;Simulate sale&#39; action on Holdings

Adds a visible ↗ Sim link to each row in the Holdings table that opens
the Sim page prefilled with ticker, qty, action=sell, and derived price
(market_value ÷ qty when available), making Sim discoverable from the
table without opening the row-actions menu.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b0c2846`](https://github.com/chen-star/net_alpha/commit/b0c2846d669b3fda0f170aa41a07cf1bc9fe5eb1))

* feat(web): /sim/suggestions chip strip on Sim page

Add GET /sim/suggestions HTMX fragment endpoint that surfaces up to 3
one-click prefill chips (largest loss, wash-sale risk, largest gain)
above the sim form; falls back to a demo TSLA chip on empty DB.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4d11259`](https://github.com/chen-star/net_alpha/commit/4d1125947c8a5564023c711f2a2aa82a92071e8c))

* feat(sim): top_suggestions pure-function chip picker

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e69c385`](https://github.com/chen-star/net_alpha/commit/e69c38594d40ca6d0be4eb96274c39f946400fc1))


## v0.38.0 (2026-04-30)

### Feature

* feat(web): /tax/harvest/plan endpoint + lazy-load on at-loss view

Wire up GET /tax/harvest/plan that builds a HarvestPlan and renders the
_harvest_plan.html fragment. Embed it into _positions_view_at_loss.html
via an HTMX loading shell replacing the old inline table. Updated two
compat test files (test_phase1_positions_tabs, test_phase2_at_loss_columns)
to hit the new fragment endpoint directly since headers are now lazy-loaded.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ad4fa93`](https://github.com/chen-star/net_alpha/commit/ad4fa933f2fc9dfb2695335a9b5650e6fe00933f))

* feat(web): _harvest_plan.html fragment skeleton ([`79bc178`](https://github.com/chen-star/net_alpha/commit/79bc178afd9a3bd1123d8a04185be9b1ed6f7021))

* feat(planner): summarize_manual_picks for user-edited selection

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b0fa656`](https://github.com/chen-star/net_alpha/commit/b0fa6569ec25728b264f2c987e151f69c391f6b4))

* feat(planner): build_plan greedy harvest planner with tax-saved ranking

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ccb4e7a`](https://github.com/chen-star/net_alpha/commit/ccb4e7ac6bc0841a53e7a0db4091c4df19429b69))


## v0.37.1 (2026-04-30)

### Feature

* feat(web): aria-label and tooltip on top-nav imports badge ([`d6de0d3`](https://github.com/chen-star/net_alpha/commit/d6de0d34e943264be8682470765e9ed5bdd3fae3))

* feat(web): per-input helper text and missing-quote message on Sim form ([`b17349a`](https://github.com/chen-star/net_alpha/commit/b17349ab17cde3093cace76cdce6141bfc6c4bc2))

* feat(web): inline tax-projection setup form replacing YAML snippet

Replaces the legacy YAML-snippet copy-paste flow with a styled inline
form using the app&#39;s standard classes (panel, label-uc, bg-surface,
btn). Makes state and state_marginal_rate optional (blank = federal-only)
to match TaxConfig defaults. Route handler updated to use Form(&#34;&#34;) /
Form(0.0) defaults accordingly.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`de22f61`](https://github.com/chen-star/net_alpha/commit/de22f61eb940e21254fe3e6cecce7210342c7a0e))

* feat(web): default Harvest queue to &#39;currently harvestable only&#39;

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`19a8cc7`](https://github.com/chen-star/net_alpha/commit/19a8cc7dcf9d0f3f9f0dd5b91e93811dc8779321))

* feat(web): tooltip on wash-sale &#39;to safe&#39; countdown ([`a1e8421`](https://github.com/chen-star/net_alpha/commit/a1e8421dfa7321e0eefd3571ad7d345415af4a37))

* feat(web): explain Watch vs Violations on the Tax wash-sales tab

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`38f14de`](https://github.com/chen-star/net_alpha/commit/38f14de7a09aeb991d5f00b5132438cf038d8cc2))

* feat(web): collapse wash-sales filter behind a Filter summary

Wraps the filter form in a &lt;details&gt; element that is collapsed by default and auto-opens only when at least one filter is explicitly set by the user (ticker, account, confidence, or year). Adds filter_year_explicit context flag to _wash_sales_context so the template can distinguish a user-chosen year from the default current-year preset. Applied to both wash_sales.html and _tax_wash_sales_tab.html (the live route).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8061aa0`](https://github.com/chen-star/net_alpha/commit/8061aa0b4afe4c7f52ed5de4ef185bbaf2d726fe))

* feat(web): sticky thead on remaining Holdings/Portfolio table fragments ([`dd74df0`](https://github.com/chen-star/net_alpha/commit/dd74df056c3e216225f4cd6776c952019f55ec32))

* feat(web): sticky thead on Positions table views

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2c0efa2`](https://github.com/chen-star/net_alpha/commit/2c0efa2f1ebc198ad914bf190d2cee1180b80851))

* feat(web): add tooltips to remaining four portfolio KPI tiles

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`639edd2`](https://github.com/chen-star/net_alpha/commit/639edd29b739e4ec0eb8264c53bb7b8e849d5979))

### Test

* test(web): pin Holdings tab links to Options and Stocks views

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`5ae21e8`](https://github.com/chen-star/net_alpha/commit/5ae21e84ea43279eca6ce24c9537f66f888b6fd6))


## v0.37.0 (2026-04-30)

### Feature

* feat(web): add cash-vs-positions deployment chart on Overview

Splits the allocation row into a 2/3 + 1/3 grid. The new right-hand
panel shows a hero &#34;% deployed&#34; stat, a stacked bar (Positions ·
Cash·free · Cash·pledged), and a per-segment legend so the user can
read deployment ratio at a glance — the data already lived on
AllocationView, so no compute changes.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3e6598e`](https://github.com/chen-star/net_alpha/commit/3e6598e6719c36a70d787dbbdd9308331eebc133))


## v0.36.0 (2026-04-30)

### Feature

* feat(web): show Total planned in Plan tab footer

Adds a Total planned figure (sum of every target&#39;s USD equivalent) to
the Plan tab footer alongside Total to fill / Free cash / Coverage so
the user can see the full target portfolio size at a glance.

Share-unit targets without a quote are excluded from the sum; the
footer indicates partial coverage as &#34;(X/Y priced)&#34; when that happens.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`4339a71`](https://github.com/chen-star/net_alpha/commit/4339a71fd58e9dd07153651ec21397464edb1d07))


## v0.35.1 (2026-04-30)

### Fix

* fix(web): positions UI fixes — overshoot bar, table styling, options dup

- Plan tab + Positions Target column: when % filled &gt; 100, render the bar
  fully filled with a green &#34;target met&#34; segment + red &#34;over&#34; segment
  proportional to the overshoot, instead of capping width at 100%.
- Closed and At-loss tables: replace undefined `data-table` class with the
  existing `panel`+`net-table` styling so rows have proper padding,
  hairlines, and aligned numeric columns.
- Options tab: drop the duplicate `holdings-short-options` panel —
  `/holdings/short-options` is a backwards-compat alias for
  `/holdings/options`, so the same long+short table was rendering twice.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`11006d9`](https://github.com/chen-star/net_alpha/commit/11006d9804cbc6286145be7f96a2a47adfab1c6c))


## v0.35.0 (2026-04-30)

### Feature

* feat(web): add Target column to Positions table when targets exist

Injects a target column into the shared _portfolio_table.html partial
whenever any PositionTarget rows exist; shows current vs target with a
progress bar and color-coded fill percentage.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d3e4d5c`](https://github.com/chen-star/net_alpha/commit/d3e4d5c904a88f4d5e785166ac6c6a48f0efac35))

* feat(web): plan target delete endpoint

Adds DELETE /positions/plan/target/{symbol} that removes a target and returns
the updated plan body fragment; idempotent for unknown symbols (200 in both cases). ([`a645853`](https://github.com/chen-star/net_alpha/commit/a6458532098bfd2b1fa33974b6511429011dba49))

* feat(web): plan target add/edit modal + upsert endpoint

Extracts _build_plan_view_for_request helper from the inline plan branch so
GET ?view=plan, POST /positions/plan/target, and future DELETE can all share
the same view-model assembly. Adds modal template and two new routes.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f3e56fd`](https://github.com/chen-star/net_alpha/commit/f3e56fde2320926b789929806cab2bea4af075cb))

* feat(web): full Plan tab render with progress bars + footer

Replace placeholder div with a complete position-targets table: per-row progress bars (blue/yellow/green/red by fill %), target/current/gap cells, and a footer summarising Total to fill, Free cash, and coverage. Free-cash calculation is now CSP-aware (subtracts cash_secured_total from open short-option positions).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`91ce04c`](https://github.com/chen-star/net_alpha/commit/91ce04ca0a20e028d3df765ff25d6f691441a55d))

* feat(web): add Plan tab navigation + empty state

Wires the Plan tab into the Positions page: adds the tab link to
_positions_tabs.html, branches the positions.html include chain, creates
the _positions_view_plan.html empty-state template, and extends the
positions_page route to validate &#34;plan&#34; as a view, fetch targets for
the tab badge count, and build + inject plan_view for the plan branch
(with a bare cash-balance free_cash that Task 13 will upgrade).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`306e941`](https://github.com/chen-star/net_alpha/commit/306e941850ce37ec75d79b777f233d28165a6789))

* feat(targets): add build_plan_view pure function

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cd22cf7`](https://github.com/chen-star/net_alpha/commit/cd22cf7aa73ff6416e43986082af6aec98745608))

* feat(db): add Repository.{list,get,upsert,delete}_target

Adds four public methods and one static helper to Repository for
reading and writing position_targets rows, using the existing ORM
select() pattern. Uppercases symbols on write and lookup.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ab9b988`](https://github.com/chen-star/net_alpha/commit/ab9b988eb41968532f29605354749b84b4a25697))

* feat(targets): add PositionTarget domain model + SQLModel row

Introduces TargetUnit enum (usd/shares), frozen PositionTarget dataclass,
and PositionTargetRow SQLModel mapped to the existing position_targets table.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`36d8939`](https://github.com/chen-star/net_alpha/commit/36d89393bc3f2b9007bb246694e508d091e2e1b4))

* feat(web): add SPY benchmark line on equity curve

Wire benchmark_symbol from PricingConfig into the equity-curve chart as a
dashed gray ApexCharts series; gracefully degrades to empty list on any
failure or when remote pricing is disabled.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fc097ae`](https://github.com/chen-star/net_alpha/commit/fc097aee0ccc88c5f072d08df5e1e71985812c51))

* feat(portfolio): add benchmark shadow-account series builder

Adds BenchmarkPoint dataclass to models.py and build_benchmark_series()
pure function in portfolio/benchmark.py that simulates a shadow account
buying the benchmark index with the same cash flows as the user&#39;s account.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c13f155`](https://github.com/chen-star/net_alpha/commit/c13f1551507b4d7ddff2d17fafc755f610cd402b))

* feat(pricing): add cached get_historical_close on PricingService

Read-through historical close cache: _MISS sentinel distinguishes
no-row from negative-cache (None), so Yahoo is hit at most once per
(symbol, date) pair even when the close is unavailable.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e07c81c`](https://github.com/chen-star/net_alpha/commit/e07c81c20beb3572eb284b9f7acfe06f2ac9745f))

* feat(db): add v11→v12 migration (position_targets + historical_price_cache)

Introduces two new tables: position_targets (user-managed per-symbol
allocation targets with USD/share unit) and historical_price_cache
(read-through cache for benchmark daily closes). Fixes the migration
chain so v10→v11 assigns current=11 instead of early-returning,
allowing v12 to run. Bumps CURRENT_SCHEMA_VERSION to 12 and updates
all tests that hardcoded version &#34;11&#34;.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7156f10`](https://github.com/chen-star/net_alpha/commit/7156f1020883ae597feef9fdd04bfff6021919dc))

* feat(pricing): add get_historical_close to provider + Yahoo impl

Adds a default no-op get_historical_close(symbol, on) to the PriceProvider
ABC and a full yfinance implementation on YahooPriceProvider that fetches a
single-day window and returns Decimal or None on any failure.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`15a8d0d`](https://github.com/chen-star/net_alpha/commit/15a8d0d09757842ce9fb184723bae3fbc273432a))

* feat(web): add Top Movers panel on Overview

Renders the top-3 unrealized $ winners and losers among open positions
on the portfolio body fragment; panel is caller-gated and omitted when
no priced positions exist.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`17219ac`](https://github.com/chen-star/net_alpha/commit/17219ac2be77d4441581cc9a8e1e2d79835072ff))

* feat(portfolio): add top_movers pure function ([`4b7410f`](https://github.com/chen-star/net_alpha/commit/4b7410f90fe09a59884a7c801c91de00fc0cffc7))

* feat(web): drop TODAY tile, promote Total Return to top row

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`56e8a80`](https://github.com/chen-star/net_alpha/commit/56e8a805cd3f634dc46e2e462c89bb7d65f9c759))

### Fix

* fix(web): address final code review (modal swap header, dt.UTC, target column, dead guards)

- Fix 1: _modal_error now sets HX-Retarget/#plan-modal-backdrop + HX-Reswap/outerHTML
  so validation errors re-render the modal in-place instead of replacing the plan body
- Fix 2: standalone /portfolio/equity-curve passes benchmark_points/benchmark_symbol defaults
- Fix 3: replace datetime.utcnow() with datetime.now(UTC) in repository.upsert_target
- Fix 4: fallback branch in _portfolio_table Target cell appends &#39; sh&#39; for share count clarity
- Fix 5: remove dead _quantize(...) or Decimal(&#34;0&#34;) guards; call .quantize directly
- Fix 6: _render_plan_body forwards selected_account/selected_period context keys
- Tests: strengthen test_post_rejects_empty_symbol/zero_amount with HX-Retarget assertion;
  drop unused dt import from test_positions_pane_context.py (pre-existing ruff F401)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`63b0e14`](https://github.com/chen-star/net_alpha/commit/63b0e14f31ca72a1a7a2d4db9c92e1c6a0492697))

### Style

* style: ruff format + StrEnum upgrade for new feature files

Apply ruff format/check across files added or modified during the
Overview redesign + position targets feature. The functional change is
TargetUnit (enum.Enum) → StrEnum, eliminating the redundant str+Enum
inheritance. Pre-existing ruff issues outside the feature scope are not
touched.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`980f715`](https://github.com/chen-star/net_alpha/commit/980f715a3db1d775bc44d79382968e5773496f94))

* style(web): rename misleading test, remove blank-line artifact

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3d59a28`](https://github.com/chen-star/net_alpha/commit/3d59a289a63782f5971b2d06b60df4fec5e07394))

### Unknown

* Merge branch &#39;feature/overview-redesign-and-position-targets&#39;

Overview page redesign + position targets (17 tasks):
- Drop TODAY tile, promote Total Return to top row
- SPY benchmark line on equity curve (graceful degrade)
- Top Movers panel (3 winners + 3 losers by unrealized $)
- Plan tab on Positions with full CRUD via HTMX modal
- Target column on shared positions table
- New SQLite tables: position_targets, historical_price_cache (v11→v12)
- 31 new tests, full suite 1095 passing ([`6207632`](https://github.com/chen-star/net_alpha/commit/6207632eec564a1326a9845916dc6932993d66e7))


## v0.34.0 (2026-04-29)

### Feature

* feat(web): POST /audit/set-basis/multi for split-into-N-lots

Validates per-row date / qty / basis bounds, qty-sum equality against
the transferred quantity, and acquisition_date &lt;= transfer_date. Calls
Repository.split_imported_transfer which persists N siblings sharing a
transfer_group_id and triggers wash-sale recompute. Adds repo helper
get_trades_in_transfer_group used by tests. Extracts a shared
_post_basis_save_recompute helper to avoid a third copy of the
post-save side effects.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`8c1712e`](https://github.com/chen-star/net_alpha/commit/8c1712e26f7e7641062f8b255ff81c28fe390500))

* feat(web): split-into-multiple-lots link on single-lot form

HTMX-driven swap: clicking the link replaces the single-lot panel
with the multi-lot row table fragment. Removes the Task 4 xfail.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`e1d1c45`](https://github.com/chen-star/net_alpha/commit/e1d1c4570e89159e2f1a02d95814d6be01daf4c5))

* feat(web): multi-lot set-basis fragment and HTMX swap routes

Add GET /audit/set-basis/multi/{trade_id} (multi-lot row-table) and
GET /audit/set-basis/single/{trade_id} (back-to-single swap target).
Multi-lot fragment uses Alpine for live qty-sum validation against
the transferred quantity.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`522258c`](https://github.com/chen-star/net_alpha/commit/522258c4ad961b10c4874b13abfe2ea0637755f6))

* feat(web): single-lot set-basis form takes acquisition date

Add POST /audit/set-basis/single with date + basis fields and
server-side validation (date format, future date, date &gt; transfer
date, negative basis). Legacy POST /audit/set-basis remains for
timeline-cell and imports-drawer callers.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1dfdce3`](https://github.com/chen-star/net_alpha/commit/1dfdce333e978c4d476763ec84297b35825ee7a4))

* feat(web): expose transfer qty + date on positions pane

Wire transfer_qty and transfer_date through positions_pane render
context so the upcoming multi-lot split UI can validate qty-sum and
enforce acquisition_date &lt;= transfer_date.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f520dd1`](https://github.com/chen-star/net_alpha/commit/f520dd1651700c1b04d0d9788ed86ff79f18bf78))

* feat(db): update_trade_basis accepts optional trade_date

The &#34;Set basis &amp; date&#34; inline form on the positions pane needs to set
acquisition date alongside cost_basis on transfer-in trades. Add an
optional trade_date parameter; when None, behavior is unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7d7a9fc`](https://github.com/chen-star/net_alpha/commit/7d7a9fc0a7f673c3e72d35b3a0c04acb879a70c9))

### Fix

* fix(web): correct single-form swap target, cancel propagation, and 4xx swap

Three browser-side bugs found in final review:
- Single-lot form used hx-target=&#34;this&#34;, producing a panel-inside-a-
  panel after save. Now matches the multi flow&#39;s hx-target=&#34;closest
  .panel&#34;.
- Back-to-single cancel handler used stopPropagation, which doesn&#39;t
  block HTMX&#39;s same-element listener. Switch to
  stopImmediatePropagation so cancel actually cancels.
- HTMX 1.9 silently drops 4xx responses by default. Add a global
  htmx:beforeSwap handler so validation error fragments render in
  the form panel as the spec calls for.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`6d585cf`](https://github.com/chen-star/net_alpha/commit/6d585cf2e6f1331671d7287f944d621deb242503))

* fix(db): clear basis_unknown when transfer rows get user-supplied basis

split_imported_transfer and update_imported_transfer were setting
transfer_basis_user_set=True on the parent row but leaving
basis_unknown=True, so the audit/hygiene checker kept flagging rows
the user had already reconciled. Clear the flag in both methods and
add a regression assertion to the integration test.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9a0cea6`](https://github.com/chen-star/net_alpha/commit/9a0cea6ce619140ba0feb7e7e63aa46de040ce11))

* fix(web): don&#39;t echo raw user input in multi-lot date error

Mirror the wording from set_basis_single so a malformed date doesn&#39;t
get reflected back into the error fragment.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`c229387`](https://github.com/chen-star/net_alpha/commit/c2293877b1b38165f18b2113b7cdee8eac8c8bb3))

* fix(web): tighten multi-lot fragment JS — Alpine clone + float tolerance

The &#34;+ Add lot&#34; button cloned a row and tried to wire @click via
setAttribute, which Alpine doesn&#39;t process on cloned nodes. Switch to
addEventListener so the remove button works. Replace == float
comparisons in qty-sum validation with a 1e-4 tolerance consistent
with the server-side check; otherwise fractional shares
(e.g., 33.33+33.33+33.34) leave Save permanently disabled. Tidy the
back-to-single confirm handler.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`81af69c`](https://github.com/chen-star/net_alpha/commit/81af69ce6352f1d25c19a3aa7ae4d9151954e5a1))

* fix(web): test the existing /positions/pane route (no shim)

The test URL was wrong; remove the redundant /portfolio/positions-pane/{sym}
shim that was added to match it, and call the production route directly.
The transfer-context behavior verified by the test is unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1d5e4e1`](https://github.com/chen-star/net_alpha/commit/1d5e4e1ed95b43d99e8178ecd2489d8268b52080))

* fix(portfolio): YTD Net Contributed card now matches its provenance modal

The KPI card on the Overview page read $54,840.64 (lifetime cumulative
transfers) while the provenance modal opened from it read $23,475.53 (YTD
2026 only). compute_cash_kpis returned series[-1].cumulative_contributions,
which is a running total that folds pre-period transfers into the opening
balance and never resets at period_start.

Add a separate `period_net_contributions` field on CashFlowKPIs computed
from in-period events only, and bind the card to it. Lifetime
`net_contributions` is preserved for the growth math (current value − total
money in is correctly lifetime-bounded). The cash-balance series semantics
used by the cash chart are unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`4c83c97`](https://github.com/chen-star/net_alpha/commit/4c83c97ade371a2d0ffa0030145ad4d9808c9a73))

### Refactor

* refactor(web): tighten set-basis/single — top-level import + id guard + tests

Move the datetime import to module top to match other route files.
Guard int(trade_id) so a non-numeric id returns 400 instead of 500.
Add tests for the invalid-date-format and trade-not-found branches
that were uncovered.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0585493`](https://github.com/chen-star/net_alpha/commit/0585493e9b4a5d68bb96ebedb0600a1ecc0816a0))

* refactor(web): remove duplicate imports in positions.py + conftest.py

Single `import datetime as dt` in positions.py replaces the dual
import; same for the inlined Trade import in seed_transfer_in.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`fb79689`](https://github.com/chen-star/net_alpha/commit/fb796895753ec30b61ac1a5782cfc1b5fb06a47a))

### Test

* test(integration): end-to-end multi-lot transfer basis split

Imports a transfer-in row with no basis, walks through the HTMX swap
to the multi-lot fragment, submits a 3-lot split, and verifies the
basis-missing warning clears on re-render.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`79256e8`](https://github.com/chen-star/net_alpha/commit/79256e8e0fb330668eb38a65e34aba27efa3cc89))

### Unknown

* Merge branch &#39;feature/multi-lot-transfer-basis&#39; — Multi-lot transfer basis + YTD net-contributed fix

YTD Overview Net Contributed card now matches its provenance modal
(period-bounded transfers, not lifetime cumulative). Inline Set basis
panel on the positions pane gains a date input plus a tiered Split
Into Multiple Lots flow that calls Repository.split_imported_transfer
under the hood — no schema change. End-to-end integration test covers
the full flow.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`86aefd0`](https://github.com/chen-star/net_alpha/commit/86aefd04f961d058f9035ff27dfd4113a73eefa1))


## v0.33.0 (2026-04-29)

### Documentation

* docs: tax correctness 1.0 — §1256 + explainability + after-tax performance

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`045dc9f`](https://github.com/chen-star/net_alpha/commit/045dc9f9809503fc236a05eb49c0df3790d9aa2d))

### Feature

* feat(web): tax/performance.html — 4 KPIs + ST/LT/§1256 mix + wash cost + caveats

Replaces Task 18 placeholder with full Tier-2 panel: pre-tax/tax-bill/
after-tax/drag KPI cards, stacked mix bar with legend, wash-sale impact
row, effective tax rate, expandable caveats, and disclaimer footer.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`63c49bd`](https://github.com/chen-star/net_alpha/commit/63c49bd504f5b569ff6cbc3bf5d27531e5f58ba1))

* feat(web): /tax?view=performance route uses compute_after_tax

Wire the performance view into the /tax handler: reads tax_brackets_cfg
from app state, builds a Period from the year param (or YTD), calls
compute_after_tax, and renders _tax_performance_panel.html. Adds the
Performance tab to tax.html. Minimal placeholder template satisfies
the pre-tax / after-tax text assertions; Task 19 will flesh it out.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`132c9b9`](https://github.com/chen-star/net_alpha/commit/132c9b96526c3ae6d06df22da95dcf1de38dd0bb))

* feat(portfolio): compute_after_tax + AfterTaxBreakdown (M&#39;s pure compute)

Add Period dataclass, AfterTaxBreakdown Pydantic model, and compute_after_tax
pure function with 60/40 §1256 split, NIIT toggle, state tax layer, and
wash-sale marginal-cost calculation. Add three Repository helpers
(realized_pnl_split, section_1256_pnl, wash_sale_disallowed_total) backed
by RealizedGLLotRow, Section1256ClassificationRow, and WashSaleViolationRow.
12/12 unit tests pass; full suite 1013 passed.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`805d7fb`](https://github.com/chen-star/net_alpha/commit/805d7fb35b37b3cf49efe63765dd99108e73d614))

* feat(tax_planner): add niit_enabled field to TaxBrackets (default True) ([`6875926`](https://github.com/chen-star/net_alpha/commit/687592628e78f18d593c95e922f5da9284bd435f))

* feat(cli): --detail prints per-violation explanations + §1256 exempt matches

Adds cli_renderer.py with render_explanation() that formats an ExplanationModel
as a printable ASCII block; wires _print_detail() into the default command&#39;s
--detail branch to render each WashSaleViolation and §1256 exempt match.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`028453e`](https://github.com/chen-star/net_alpha/commit/028453ef37fcbc1358c629542250233055b86bb4))

* feat(web): wire HTMX inline-expand trigger on wash-sale rows

Each violation row in _detail_table.html now carries hx-get, hx-trigger=&#34;click once&#34;,
hx-target, hx-swap, and an Alpine @click toggle. A sibling explain &lt;tr&gt; with x-show
provides the lazy-load target for the /tax/violation/{id}/explain fragment. Rows are
wrapped per-violation in their own &lt;tbody x-data&gt; so Alpine scope covers both rows.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bf3571d`](https://github.com/chen-star/net_alpha/commit/bf3571de1d4579f04319c7a3efb0f63c88c19f13))

* feat(web): HTMX inline-expand explain fragments for violations + exempt matches

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ade0792`](https://github.com/chen-star/net_alpha/commit/ade0792cf148b4e4534922beb4a817a0892138cb))

* feat(explain): explain_exempt mirrors explain_violation for ExemptMatch

Pure function explain_exempt() builds ExplanationModel with is_exempt=True
and adjusted_basis_target=None for §1256 exempt matches; re-exported from
net_alpha.explain.__init__.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0dfe3e7`](https://github.com/chen-star/net_alpha/commit/0dfe3e745926ae531bddb6dfbd842ee3ee49136e))

* feat(explain): explain_violation + ExplanationModel

Pure function that builds a structured ExplanationModel from a
WashSaleViolationRow, covering exact-ticker, ETF-pair, and option-chain
matches with cross-account detection and partial-wash-sale math strings.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e0747f2`](https://github.com/chen-star/net_alpha/commit/e0747f20e431c08d037836b988904abc066e1be4))

* feat(explain): rule citations, match-reason, disallowed-math, confidence-reason templates

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cb1f5a5`](https://github.com/chen-star/net_alpha/commit/cb1f5a59c499cfd414b666db7cb616f0d7f86c48))

* feat(engine): one-shot migration recompute reclassifies stale §1256 violations

Adds migrate_existing_violations() to engine/recompute.py: backfills
trades.is_section_1256 for legacy rows with DEFAULT 0, converts any
WashSaleViolationRows referencing §1256 contracts into ExemptMatch
records, runs the §1256 60/40 classifier, and returns a
MigrationRecomputeSummary with counts for a user-facing banner.

Wires the one-shot pass into init_db() (connection.py) behind a meta
key guard (section_1256_migration_done) so it runs exactly once per
DB after upgrade from v10. Adds repository helpers delete_violations_by_id
and set_section_1256_flag. Six new integration tests cover reclassification,
no-op on equity violations, flag backfill, idempotency, and classifier output.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1616137`](https://github.com/chen-star/net_alpha/commit/16161372fe2dfa0bfb4018c5717e5260a59af926))

* feat(engine): recompute persists ExemptMatch + §1256 classifications; universe-hash trigger

- Add recompute_all(repo) orchestrator: runs wash-sale detection, persists
  ExemptMatch records, runs §1256 classifier and persists classifications,
  then stamps the universe hash.
- Add should_full_recompute(repo) -&gt; bool: compares stored meta hash against
  current bundled+user universe hash; returns True when stale.
- Add _stamp_universe_hash(repo) private helper.
- Fix add_import and _row_to_trade to round-trip is_section_1256 through
  the DB (was missing, causing trades loaded from DB to always have
  is_section_1256=False, silently breaking exempt-match detection).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`bf0bf85`](https://github.com/chen-star/net_alpha/commit/bf0bf85b110160525dd26de827917a4aa343772f))

* feat(section_1256): 60/40 classifier for closed §1256 trades

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a466988`](https://github.com/chen-star/net_alpha/commit/a466988f2d54091b7bb4b404ea78aabe58aff3b1))

* feat(engine): emit ExemptMatch for §1256 contracts (Approach 2)

When either side of a candidate wash-sale match is a §1256 contract
(trade.is_section_1256 == True), the detector now emits ExemptMatch
instead of WashSaleViolation and does not adjust replacement-lot basis.
Applies to both detect_wash_sales and detect_in_window.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`37321d4`](https://github.com/chen-star/net_alpha/commit/37321d46f76a1a74340ede3d6ee0ea7873468321))

* feat(db): repository methods for ExemptMatch + Section1256Classification

Add save/clear/list methods for ExemptMatch and Section1256Classification
to Repository, with int() FK conversions mirroring _violation_to_row.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d814d58`](https://github.com/chen-star/net_alpha/commit/d814d58a05a122675752c1288609465777e656c1))

* feat(db): migration v10→v11 — exempt_matches + section_1256_classifications + is_section_1256

- Add _migrate_v10_to_v11: creates exempt_matches table (INTEGER FKs),
  section_1256_classifications table, adds trades.is_section_1256 column,
  stamps section_1256_universe_hash and wash_sale_engine_version meta rows.
- Add preflight column-ensure at top of migrate() so SQLModel ORM SELECTs
  (used in intermediate migration steps like v1→v2 backfill) always work
  even when DB hasn&#39;t reached v11 yet — fixes 6 pre-existing test failures.
- Bump CURRENT_SCHEMA_VERSION 10 → 11.
- Add tests/db/test_migration_v11.py (5 new tests, all passing).
- Update version assertions in test_migration_v1_v2.py and test_migrations.py.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4e4c9fa`](https://github.com/chen-star/net_alpha/commit/4e4c9fa0df8e5011bf8893d9a78a41d801598e36))

* feat(db): row tables for ExemptMatch + Section1256Classification + TradeRow.is_section_1256

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d20b2c3`](https://github.com/chen-star/net_alpha/commit/d20b2c3880f6769873cd453b5d227550939a3dc6))

* feat(models): ExemptMatch + Section1256Classification + Trade.is_section_1256

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`02b42b0`](https://github.com/chen-star/net_alpha/commit/02b42b0e7aa7fac3c76e95f18a2e95fcf0a1beaa))

* feat(section_1256): bundled universe + is_section_1256 detection ([`fcee2f4`](https://github.com/chen-star/net_alpha/commit/fcee2f4404f3cc63b7f7d64d4315a04c01c37a1a))

### Fix

* fix(web): surface ExemptMatch on wash-sales tab + valid HTMX target (C4, I1)

C4: _detail_table.html renders a §1256 Exempt Matches section after the
violations table when exempt_matches is non-empty. wash_sales.py passes
exempt_matches into the table-view context (filtered by same ticker/account/year).

I1: Move explain-row id from &lt;tr&gt; to &lt;td colspan=&#34;8&#34;&gt; so HTMX innerHTML
swap inserts into a valid container — a &lt;div&gt; inside a bare &lt;tr&gt; is
hoisted out of the table by browsers. Applied to both violation and exempt
match rows. hx-target updated to point directly to the &lt;td id&gt;.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6982045`](https://github.com/chen-star/net_alpha/commit/6982045dd6baff9d4a9b10010365bc777d6bc93d))

* fix(engine): persist ExemptMatch + classifications in recompute_all_violations (C2, C3)

C2: Fold exempt-match persistence and §1256 classifier invocation into
recompute_all_violations so the production recompute path is complete.
recompute_all() becomes a thin wrapper that auto-loads ETF pairs.

C3: should_full_recompute() now checks both the universe hash AND the
wash_sale_engine_version meta key, triggering a full recompute on binary
upgrades. _stamp_universe_hash() also stamps the engine version.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a86df73`](https://github.com/chen-star/net_alpha/commit/a86df73c21620e7b283448f9d9ffb7feeb9eac78))

* fix(db): set Trade.is_section_1256 in add_import (C1: was always False on import)

Auto-detect §1256 status via is_section_1256() when the broker parser
does not set the flag explicitly. Respects any explicit True already on
the trade object.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`afc0bf8`](https://github.com/chen-star/net_alpha/commit/afc0bf88b66f7a651da64213faec0e83e0b286aa))

* fix(db): exclude §1256 from realized_pnl_split to avoid double-count with section_1256_pnl ([`3559fee`](https://github.com/chen-star/net_alpha/commit/3559feeb81a345842163ef790e5599110423ebbd))

* fix(explain): use Repository.get_trade_by_id (was nonexistent get_trade) ([`b683596`](https://github.com/chen-star/net_alpha/commit/b683596ffc48762f47e14603153a34abdab3e34a))

* fix(db,engine): use bindparams + ORM update; replace typer.echo with print in db layer

- connection.py: convert f-string SQL in _migration_1256_done and _stamp_migration_1256_done to bindparams; remove typer import and replace typer.echo with plain print
- repository.py: rewrite set_section_1256_flag to use ORM table.update().where().values() pattern matching delete_violations_by_id; signature changed to list[int]
- recompute.py: cast Trade.id to int at set_section_1256_flag call site; add idempotency invariant comments for exempt-match save and classifier save steps; ruff-fixed import sort

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`575ffd8`](https://github.com/chen-star/net_alpha/commit/575ffd89a22f533589c6450e8cd38f7568805928))

* fix(engine): stamp universe hash only when recompute ran; add is_section_1256 round-trip test

Move _stamp_universe_hash inside the `if all_dates:` guard so an empty-DB
call to recompute_all does not lock out should_full_recompute when trades
are added later. Add focused add_import → all_trades round-trip test for
the is_section_1256 field to give direct coverage of the repository fix.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1a14355`](https://github.com/chen-star/net_alpha/commit/1a1435589a33e2872d56ecdaa312259ee857e05e))

* fix(section_1256): classifier uses is_sell() predicate (was lowercase string compare)

Real broker-imported trades have action=&#34;Sell&#34; (title case); the hard-coded
`!= &#34;sell&#34;` guard silently skipped every real §1256 sell. Switch to the
existing `Trade.is_sell()` casing-insensitive predicate. Update test fixtures
to use title-case actions matching production broker output; remove unused
`import pytest`.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d4b6c1f`](https://github.com/chen-star/net_alpha/commit/d4b6c1febffa2b33c7adadf8b0b732fb6c060e3a))

* fix(db): repository fixups — account filter consistency, RuntimeError catch, cascade delete on remove_import

- list_exempt_matches: `if account:` → `if account is not None:` to match rest of file
- list_section_1256_classifications: replace dead `acct_id is not None` branch with try/except RuntimeError, returning [] on unknown account (safe for user-controlled filter values in web layer)
- remove_import: cascade-delete ExemptMatchRow (loss_trade_id OR triggering_buy_id) and Section1256ClassificationRow (trade_id) so no orphaned rows persist after import removal
- tests: 2 new filter-path tests (account subset + unknown account → []) bringing file to 6 tests

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8a4b902`](https://github.com/chen-star/net_alpha/commit/8a4b9029969701ffcf6a34a03106ca0e226d4bff))

* fix(db): stamp §1256 meta keys on fresh DB init (was upgrade-only)

Extract _stamp_section_1256_meta() helper and call it from both the
fresh-DB branch of migrate() and _migrate_v10_to_v11, so a new install
gets section_1256_universe_hash + wash_sale_engine_version in meta.
Also changes hardcoded &#39;11&#39; to str(CURRENT_SCHEMA_VERSION) for
extensibility. Adds regression test test_fresh_db_stamps_section_1256_meta_keys.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f91f003`](https://github.com/chen-star/net_alpha/commit/f91f003b45797947252c75c160464e708e551978))

* fix(test): remove unused imports flagged by ruff F401 ([`5e5d23d`](https://github.com/chen-star/net_alpha/commit/5e5d23db2913546ebda7c1a8c9f0c71337d52770))

### Test

* test(integration): real production-path test for §1256 auto-detection + persistence

3 tests covering:
- add_import auto-detects is_section_1256 (no explicit flag set)
- recompute_all_violations persists exempt matches and classifications
- recompute_all_violations stamps universe hash + engine version in meta

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`42fad23`](https://github.com/chen-star/net_alpha/commit/42fad233dfe7032e956ced45f27ab7ff8ddf0642))

* test(integration): end-to-end §1256 recognition + ETF pair preservation

Adds a golden end-to-end integration test that seeds synthetic trades, runs
recompute_all, and asserts the full expected mix: 2 regular wash-sale violations
(TSLA confirmed, SPY/VOO ETF-pair unclear), 1 ExemptMatch for the §1256 SPX
call pair, and 1 Section1256Classification with correct 60/40 LT/ST split on
the closed SPX 5000C profit trade.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4e0dc25`](https://github.com/chen-star/net_alpha/commit/4e0dc25f69b425a2112272d90a4f6fb4ab0bdeec))

* test(explain): cover fallback branches in templates ([`ec27f63`](https://github.com/chen-star/net_alpha/commit/ec27f635ac6e8eabda352d5d0745a28c9cde02cf))

* test(engine): cover §1256 candidate-only flag + detect_in_window exempt path

Replace misnamed test_mixed_spx_loss_spy_buy_emits_exempt_match (which
was a SPX→SPX duplicate) with test_candidate_only_section_1256_still_emits_exempt,
exercising the candidate-arm of the `loss_sale.is_section_1256 or candidate.is_section_1256`
branch with asymmetric flags. Add two detect_in_window tests: one asserting
the §1256 exempt match is included when both trades fall inside the window,
and one asserting it is excluded when both fall outside.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`775f768`](https://github.com/chen-star/net_alpha/commit/775f7686e565cc09ccb2f7b3ae1adf869fe717af))

### Unknown

* Merge branch &#39;feature/tax-correctness-pmo3&#39; — Tax Correctness 1.0 (P+M+O3) ([`9058a3d`](https://github.com/chen-star/net_alpha/commit/9058a3dda109e07717813edfadc1b405ba295454))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`464e4ba`](https://github.com/chen-star/net_alpha/commit/464e4badc6acd4b902793dcd6978908891f5c3e5))


## v0.32.0 (2026-04-29)

### Feature

* feat(snapshots): expand WIDTHS to 4 viewports; recapture 32 baselines (§F1)

Add laptop (1024×768) and desktop-wide (1440×900); refit desktop to
1280×800.  Rewrite tablet/desktop baselines in place; add 16 new
laptop/desktop-wide PNGs.  32 pass in verify mode, 0 diff leaks.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d2351e9`](https://github.com/chen-star/net_alpha/commit/d2351e9edc437832832bc0cb1da9e3aaa9786076))

* feat(web): ticker tabs gain aria-controls + role=tabpanel (I4)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`499ab7e`](https://github.com/chen-star/net_alpha/commit/499ab7ebafe16ee847094c818b76bac7a5fc0418))

* feat(web): side pane + Settings drawer go full-width at narrow widths (§3.9)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5588db0`](https://github.com/chen-star/net_alpha/commit/5588db05d3de1790efbe1742a42ed10d43f78517))

* feat(web): wide tables get overflow-x-auto wrapper at narrow widths (§3.9)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e67193a`](https://github.com/chen-star/net_alpha/commit/e67193a837d77ee1ea67f391460730a214d1ce76))

* feat(web): KPI grids reflow at 768/1024 (§3.9)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3a5a24f`](https://github.com/chen-star/net_alpha/commit/3a5a24f29220403602f786e53131d74df5d8f022))

* feat(web): drop width=1024 viewport, add &lt; 768 banner (§3.9) ([`eb66911`](https://github.com/chen-star/net_alpha/commit/eb669112797637eed9f9efc3452252812ed2a3b7))

### Fix

* fix(web): Phase 5 review fix-pack

- Wrap 4 missed tables in overflow-x-auto (_schwab_lot_detail,
  _reconciliation_diff, _detail_table, _provenance_modal)
- Hide topbar below md (banner-only at &lt; 768 per spec §3.9)
- Update test_baseline_screens.py docstring for 4-width matrix
- Recapture tablet snapshots affected by topbar visibility

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`29a1c25`](https://github.com/chen-star/net_alpha/commit/29a1c2588ccceb7ea663bad322a194b2cb8a6821))

### Test

* test(web): smoke every page returns 200 (Phase 5) ([`37a5237`](https://github.com/chen-star/net_alpha/commit/37a5237e7c0c3aa75d75800e06e4f541dc2fc975))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`6d64635`](https://github.com/chen-star/net_alpha/commit/6d6463556338f3d8616ebf37d26db6453c0ccbde))


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

Section G3 of Phase 4 plan. ([`ea6d98e`](https://github.com/chen-star/net_alpha/commit/ea6d98ec6f1b3f6ed65c4ba990a8eed6a71190f6))

* feat(web): apply --ring-focus to all interactive elements (§5.14)

Adds a single :focus-visible block that applies the --ring-focus token
(0 0 0 2px rgba(94,92,230,0.6)) to every interactive primitive:
.btn, .btn-ghost, .tab, .chip, .nav-link, native button, and form
inputs. Outlines are nullified so the indigo halo is the canonical
keyboard-focus indicator.

Section G2 of Phase 4 plan. ([`7be9de6`](https://github.com/chen-star/net_alpha/commit/7be9de6c3e3f78ff970ac22c4ab3d7c021963d3f))

* feat(web): main container 1280px → 1536px (max-w-screen-2xl) (H8)

Bumps the main and footer containers from max-w-[1280px] to
max-w-screen-2xl (1536px) to give the wider Positions table and
Tax view more horizontal room. Snapshot baselines will be
re-captured in Section H. ([`d6dde36`](https://github.com/chen-star/net_alpha/commit/d6dde36c30eae9a07e2ddda1cdcb5dd27db4028b))

* feat(web): options panel header is a 3-card mini-summary (H7)

/holdings/options now passes options_summary (open_contracts, net_premium,
avg_dte) to _portfolio_open_options.html. Net premium signs short premium
received as a credit and long cost paid as a debit; avg DTE is qty-weighted.
The 3-card grid renders above the row list, mirroring the kpi-numeric
pattern used elsewhere. ([`7635012`](https://github.com/chen-star/net_alpha/commit/76350123f9b3999a1a920202443608fe4d90079e))

* feat(web): LT/ST mixed shows as single &#39;lt+st&#39; chip in Account column (H5)

Adds account_chip (joined sub-account suffixes) and account_displays
(full labels) to PositionRow. Single-account rows render the label in
mono; multi-account rows render a single chip whose tooltip lists
every full label. ([`c1da698`](https://github.com/chen-star/net_alpha/commit/c1da698218bde389ef34cc86ef9ada531c620af2))

* feat(web): all quantity cells use fmt_quantity (H2)

Replaces &#34;%.4f&#34;|format(r.qty) and &#34;%g&#34;|format(r.lt_qty|float) ST splits
with fmt_quantity, so whole shares render as integers and fractional
quantities trim trailing zeros consistently with other tables. ([`64abe94`](https://github.com/chen-star/net_alpha/commit/64abe949351ecf7744d3b385108c3b9dfdeaf744))

* feat(web): missing-basis chip + em-dash empties on Positions table (H1)

Adds PositionRow.basis_known derived from any open lot having non-null,
non-zero cost_basis. The Positions table now renders the new chip
&#39;⚠ basis missing&#39; when basis is provably missing on an open position
instead of showing $0.00, and falls back to fmt_currency (em-dash for
None) elsewhere. ([`da5490f`](https://github.com/chen-star/net_alpha/commit/da5490fbc1a5dd9201a5935d10ef876bcaaca0be))

* feat(web): inline Set-basis chip on Timeline rows missing basis (Tk5)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`c9227ea`](https://github.com/chen-star/net_alpha/commit/c9227ea8c4ea335ac852b3ac7c8107ebc4f3411f))

* feat(web): /ticker accepts ?view=timeline|lots|recon and serves fragments (Tk4) ([`8fbba8e`](https://github.com/chen-star/net_alpha/commit/8fbba8e35087af8d31ab57010af7093cb5b2d1a2))

* feat(web): /ticker uses Timeline / Open lots / Broker reconciliation tabs (Tk4) ([`a9684c2`](https://github.com/chen-star/net_alpha/commit/a9684c2b2f2c35766f15ce3af7c83890a53cb99d))

* feat(web): reconciliation /reconciliation accepts variant=badge for Ticker KPI (Tk3)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`82d11ec`](https://github.com/chen-star/net_alpha/commit/82d11ec6e12d4a773de6a463902a1af9254fd543))

* feat(web): ticker KPIs use sans + fmt_currency; mono only on identifiers (Tk1)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b6edace`](https://github.com/chen-star/net_alpha/commit/b6edaced71f74817f9525a16db03c6729a011594))

* feat(web): ticker page h1 is sans Inter, white (Tk1, Tk2)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`dd49f11`](https://github.com/chen-star/net_alpha/commit/dd49f117ba7717d6c7f71157eda5ccae131aa8e5))

* feat(web): calendar strip shows N events YTD (N3) ([`983d5e2`](https://github.com/chen-star/net_alpha/commit/983d5e235b1de0709a2df8d1981127f41e44be83))

### Fix

* fix(web): keyboard.js state machine + Realized P/L $0 color

keyboard.js: prior matcher used pending.endsWith(seq.replace(&#39; &#39;,&#39;&#39;)),
so typing &#39;good&#39; or &#39;tags&#39; triggered nav. Replace with an explicit
&#39;awaiting g&#39; state machine so only true g-prefixed chords fire.

ticker.html: Realized P/L (YTD and Lifetime) used &gt;= 0 as the green
threshold, painting $0.00 green. Mirror the Disallowed pattern: &gt; 0
positive, &lt; 0 negative, else neutral text-label-2.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`00b3f47`](https://github.com/chen-star/net_alpha/commit/00b3f47d97acfc28c1b5a3d01d68fd617e1e93bf))

* fix(web): inline Set basis chip swaps the basis cell, not affordance cell

The chip lived in the BASIS td but its hx-target pointed at the
affordance cell two columns over, leaving the warning chip stuck after
save. Add id=&#34;trade-basis-{id}&#34; to the basis td, retarget the chip
form, and update the timeline-caller branch of /audit/set-basis to
return matching markup including the saved cost-basis value.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`5abe8be`](https://github.com/chen-star/net_alpha/commit/5abe8bee87b068640a0d690518fe79e065fb8953))

* fix(web): drop HTMX swap on ticker tabs to preserve active state

Tabs server-render the active class from selected_view, but HTMX swap
only replaced inner content, leaving the highlight stuck on the old tab.
Convert to plain &lt;a&gt; nav matching the _positions_tabs.html pattern. The
route already returns full HTML for non-HX requests.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`41bab74`](https://github.com/chen-star/net_alpha/commit/41bab743ff97eaee1c01c15175ab22086a24dbe9))

* fix(web): wash-sale filter chips × is clickable, drops that filter (N2) ([`3b41b59`](https://github.com/chen-star/net_alpha/commit/3b41b59ed8399913ce4d0527671e16a3fe463c8d))

* fix(web): sim Account label flips to (required) when Sell selected (N1) ([`00290c6`](https://github.com/chen-star/net_alpha/commit/00290c6c6887f525293c0f21a20d9edd3a490804))

* fix(web): projection form swap is outerHTML to avoid self-nesting (I1) ([`c236f57`](https://github.com/chen-star/net_alpha/commit/c236f5769c7f1f623791030adecbf2cb0aa590a6))

* fix(web): hero subhead &#39;vs contributed&#39; now equals total − net_contributed (I2)

Adapted to actual codebase field name: cash_kpis.net_contributions (not
net_contributed). Both kpis_fragment and body call sites now compute
total_account_value - cash_kpis.net_contributions instead of
period_realized + period_unrealized. ([`cdf19c1`](https://github.com/chen-star/net_alpha/commit/cdf19c10a6592984bf7c642a0054673a95d79770))

### Refactor

* refactor(web): promote text-label-3 → text-label-2 on load-bearing copy (§5.14)

Per §5.14, label-3 is reserved for decorative dividers and disabled
affordances. Bumps load-bearing copy (KPI sub-lines, panel sub-headers,
source labels, &#34;Loading…&#34; placeholders, event-count spans, harvest
queue origin lines, profile descriptions, etc.) to label-2.

Decorative `·` separators, em-dash placeholders for missing values,
disabled pagination buttons, and chevron affordances stay at label-3.

Section G1 of Phase 4 plan. ([`78426ec`](https://github.com/chen-star/net_alpha/commit/78426ecb54bf54fa2709881f5fd29ca41d7e266c))

* refactor(web): open-options bar shows P/L only; DTE is a separate badge (H6)

The time-elapsed bar already represents only one metric (not P/L,
which would require live option quotes we don&#39;t fetch). Per the
H6 split, DTE becomes a discrete badge-muted with the existing
text-warn / text-label-1 / text-label-2 colorization preserved
based on time-to-expiry, so the row&#39;s right column reads as a
standalone badge instead of a number with inline subscript. ([`78134e9`](https://github.com/chen-star/net_alpha/commit/78134e97d4efcb311e47be36a05bd9ecb9e65bfe))

* refactor(web): rename CASH SUNK/SH → &#39;Cash invested / sh&#39; + tooltip (H3)

Header now uses Title Case, plain English, with a clarifying tooltip on
how the per-share number is derived (and that wash adjustments are
included). ([`220bb81`](https://github.com/chen-star/net_alpha/commit/220bb81c07a468ebc0dacb15cb8e9fe2a8f7531a))

* refactor(web): drop above-table recon strips; badge + tab replace them (Tk3)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7936d4d`](https://github.com/chen-star/net_alpha/commit/7936d4d9bb1306a695cf0d2bc81b67a5dab305e0))

### Test

* test(web): smoke tests for Phase 4 ticker tabs + recon badge variant

Cover the new query-param round-trip on /ticker/&lt;sym&gt;?view=, the
HX-Request fragment-only response, and the variant=badge branch on
/reconciliation/&lt;sym&gt;. Tests are tolerant of unseeded data so they pass
in the default conftest.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`52eba36`](https://github.com/chen-star/net_alpha/commit/52eba36008e4fce1daadc3d957546cdafebefe39))

* test(web): re-capture snapshot baselines after Phase 4 visual sweep ([`3c5aa0f`](https://github.com/chen-star/net_alpha/commit/3c5aa0f9ca089fc33146278dda14f11b5eb5342d))

### Unknown

* Merge branch &#39;phase4-ticker-visual&#39; — Phase 4 Ticker page + visual sweep ([`62187f9`](https://github.com/chen-star/net_alpha/commit/62187f976a7ae2486c2243d4a1d3a45ee046c315))


## v0.30.0 (2026-04-29)

### Chore

* chore(web): delete dead _harvest_tab.html (Phase 1 redirected away; Phase 2 review #I6)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0431899`](https://github.com/chen-star/net_alpha/commit/043189918b93f99b4758947eb157dbef4b60f69b))

### Feature

* feat(web): /sim — recent sims this-session panel (S2)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`4101746`](https://github.com/chen-star/net_alpha/commit/410174648a17ff8747a9fb4f4ea39838a69fd9ff))

* feat(web): /sim — account required for action=Sell with inline error (S3)

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b395c6f`](https://github.com/chen-star/net_alpha/commit/b395c6ff1246b60dbcf973d34284d2fb58142650))

* feat(web): drop-zone preview on drag-over (I4)

Adds drop_zone.js (vanilla JS) that listens to dragenter/dragover on any
element wrapping a [data-drop-zone] file input and shows a sibling
[data-testid=&#34;drop-zone-preview&#34;] element with the incoming file count.
Wires data-drop-zone onto the CSV upload input and adds the preview div
to _drop_zone.html; loads the script via base.html.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`73fcb76`](https://github.com/chen-star/net_alpha/commit/73fcb76a72fbba6e83c82d902f6f07d24f1326df))

* feat(web): drawer Imports — one-explanation card + per-row inline form (I1, I2)

Restructures the data-hygiene section: basis_unknown rows now render a
single shared explanation card (I1) and one compact HTMX inline form each
(I2, caller=drawer).  Adds MissingBasisRow helper to hygiene.py and wires
collect_missing_basis_rows into the imports route context.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0650385`](https://github.com/chen-star/net_alpha/commit/065038541c328ebadcf078f1661231c43430a1d8))

* feat(web): inline tax-projection form replaces YAML snippet (Pr1, Pr2)

Add write_tax_config() to config.py, POST /tax/projection-config route
that persists to config.yaml and hot-reloads app.state, _projection_form.html
with HTMX-wired form, and updated _projection_tab.html / _projection_card.html
to remove the manual YAML-snippet copy.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`006b38b`](https://github.com/chen-star/net_alpha/commit/006b38bcce3ae7429a7632c59f533b278838c617))

* feat(web): tax filter chips with reset (W2); calendar strip always visible (W3)

- _tax_wash_sales_tab.html: add filter chip summary row with
  data-testid=&#34;filter-reset&#34; (W2) and always-visible compact month-header
  strip with data-testid=&#34;calendar-strip&#34; (W3)
- app.src.css: add .chip utility class for filter-bar chips
- app.css: rebuilt

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bb910a5`](https://github.com/chen-star/net_alpha/commit/bb910a51ac729ae602bbfaa17a32eb100e2ccb84))

* feat(web): wash-watch labeled forward; violations labeled backward, affirmative empty (W1, W1b)

- _portfolio_wash_watch.html: heading now reads &#34;Wash-sale watch ·
  forward-looking 30d&#34;
- _tax_wash_sales_tab.html: violations section gets &#34;Violations ·
  backward-looking detected&#34; heading before the detail table
- _detail_table.html: empty state replaced with affirmative &#34;✓ No
  wash-sale violations detected&#34; copy instead of generic &#34;No violations
  match these filters.&#34;
- test_detail_routes.py: updated to match new empty-state copy

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a9202d3`](https://github.com/chen-star/net_alpha/commit/a9202d3413a52132a9bef7fe5e152b4582e1f21e))

* feat(web): tax realized-P/L stacked mini-bar (T5)

Add realized_kpis (OffsetBudget) to _wash_sales_context so the tax
wash-sales tab can render a split loss/gain mini-bar. The bar shows
realized_losses_ytd vs realized_gains_ytd; degrades to an empty-state
message when no P/L has been realized this period.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cb1e530`](https://github.com/chen-star/net_alpha/commit/cb1e5302d757354bb655c11a5afe8705f93f06f1))

* feat(web): loss-harvest budget bar (T4)

Add data-testid=&#34;offset-budget&#34; to the tile wrapper and
data-testid=&#34;offset-budget-bar&#34; to the existing progress bar in
_offset_budget_tile.html so tests can assert the bar is present.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bc5315a`](https://github.com/chen-star/net_alpha/commit/bc5315aeb0d4f3dfe2d890b7d9ab7abb742e56ef))

* feat(web): Overview KPI grid — hero + today + cash (3 large) over 4 small (P2/P4/NEW)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d9a16cc`](https://github.com/chen-star/net_alpha/commit/d9a16cc771161a68f12714bc7abad41dd2066b76))

* feat(portfolio): compute_today_change for the Overview Today tile (P3 prep)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a06cdd0`](https://github.com/chen-star/net_alpha/commit/a06cdd0aaf015c9132d794fdca4248208c006e55))

* feat(pricing): Quote exposes previous_close for the Today tile (Phase 3 prep)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`80362ab`](https://github.com/chen-star/net_alpha/commit/80362ab1613a5d08dce7041bb8e573330cffc3e9))

* feat(web): freshness chip in toolbar — drop in-tile cached-prices copy (P5)

Add compute_price_freshness helper (portfolio/freshness.py) that maps a
PricingSnapshot to a green/amber/red tier and label (&lt; 15m / 15m–24h /
&gt; 24h). Wire it into the / route and render a data-testid=&#34;freshness-chip&#34;
button in the toolbar. Remove the inline &#34;Cached prices…refresh&#34; copy from
the KPI tile footer — the chip is now the single freshness surface.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`035cd2d`](https://github.com/chen-star/net_alpha/commit/035cd2db35a154f5c28d16c0ec3352e53aacb544))

* feat(web): drop Portfolio section header and Tax planning footer (P1, P9)

Remove redundant &#34;Portfolio&#34; section-header div from the body fragment
and drop the Tax planning footer panel (offset budget + year-end
projection) from the Overview page — those panels belong on /tax.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9fc2145`](https://github.com/chen-star/net_alpha/commit/9fc2145fdb00783ea6a215aa4947c301c3462f3f))

* feat(web): at-loss summary strip — total unrealized, harvestable count, replacements count (Phase 2 review #I3)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b4d8d8d`](https://github.com/chen-star/net_alpha/commit/b4d8d8de58e06495f16360ad4ed253f34e1b0baf))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7cb30d9`](https://github.com/chen-star/net_alpha/commit/7cb30d97271e0111b1796cec0b38fc6730a958b3))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`be909a8`](https://github.com/chen-star/net_alpha/commit/be909a8a0691d5d82fc9c7e01e2345c1a400a3a7))

* fix(web): equity x-axis tick density (P6); cash chart line semantics (P7)

Add hideOverlappingLabels: true + tickAmount: 12 to the equity-curve x-axis
so month labels don&#39;t pile up on dense date ranges.

Add data-series-solid=&#34;cash_balance&#34; and data-series-dashed=&#34;net_contributed&#34;
attributes to the cash chart container — stable semantic hooks that confirm
series ordering (cash balance = solid, net contributed = dashed, per §5.12).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`34f4d7c`](https://github.com/chen-star/net_alpha/commit/34f4d7c8f10d77f7106504fdecbc25feb563c210))

* fix(web): CASH KPI rendered exactly once on Overview (P3 bug fix)

Remove the duplicate Cash balance tile from the secondary cash-flow row
in _portfolio_kpis.html. Cash is already shown via the slot_cash macro
in the hero KPI grid; the second block now shows only Net contributed
and Growth (unique data). Resize those two tiles from col-span-4 to
col-span-6 to fill the 12-column grid.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`836911c`](https://github.com/chen-star/net_alpha/commit/836911cabb642a32732e164c74c416648446ad4f))

* fix(web): positions_pane logs lookup failures instead of silent swallow (Phase 2 review #I4)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5db9481`](https://github.com/chen-star/net_alpha/commit/5db9481656f6900ecf38cdf84813e10a4655f87b))

### Refactor

* refactor(web): realized_delta is loss — drop the duplicate compute (Phase 2 review #I5)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`66c383b`](https://github.com/chen-star/net_alpha/commit/66c383b379feaf5c488191696e1369afd923d433))

### Style

* style: fix import block sort order in positions.py (ruff I001)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ffd92b9`](https://github.com/chen-star/net_alpha/commit/ffd92b9c950061bc7709560b51929afd027cb513))

### Test

* test(web): re-capture snapshot baselines after C1/C2 color fixes

The C1 negative-sign fix and C2 .text-loss/.text-gain/.text-success
class definitions land real color on previously-uncolored markup:
- positions-at-loss: per-row loss column + summary unrealized now red
- settings-imports: triangle-alert tone change
- tax-wash: T5 mini-bar totals now red
- overview: Today tile + hero negative-vs-contributed render correctly

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`563ec3e`](https://github.com/chen-star/net_alpha/commit/563ec3edfd623c9270214738c369464d5748f76c))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0c992bd`](https://github.com/chen-star/net_alpha/commit/0c992bd4cf92210a45024eb8a24e8243c3bbb132))

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
keyboard shortcuts). Phase 5 is responsive (drop viewport=1024). ([`40a9848`](https://github.com/chen-star/net_alpha/commit/40a98489ac94229542ff6c70de71298abecfdfb7))


## v0.29.0 (2026-04-28)

### Documentation

* docs(web): document /imports/_legacy_page is drawer-fetched only (review nit #12) ([`430a4ab`](https://github.com/chen-star/net_alpha/commit/430a4ab6d942658157a51f078cff1b9c53a2e7aa))

* docs(web): _density_toggle docstring no longer references /holdings (review nit #11) ([`2f2f02d`](https://github.com/chen-star/net_alpha/commit/2f2f02dfe33d47999371a179af0f7fb5b58092a5))

### Feature

* feat(web): /sim accepts ?account= and ?action= for row-action pre-fill

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`eeaee79`](https://github.com/chen-star/net_alpha/commit/eeaee7928ab04a4ad850e9076b375779d871c51a))

* feat(web): pane set-basis form block (single-lot inline; multi-lot links out) ([`adce4a0`](https://github.com/chen-star/net_alpha/commit/adce4a0cce336d9d2c7b3d8e8b069c6e48e98e34))

* feat(web): pane sim-sell preview block + run-full-sim deep link ([`de6a550`](https://github.com/chen-star/net_alpha/commit/de6a550a5398907a05e548d2542c7992bfb8c3e3))

* feat(web): pane header — qty · account · last · basis · loss ([`e239767`](https://github.com/chen-star/net_alpha/commit/e2397678e5d31058550bda2087fbc1572fdd2901))

* feat(web): row click opens positions side pane (Alpine \$dispatch)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2ac41c1`](https://github.com/chen-star/net_alpha/commit/2ac41c1ad9207c3f5b7e656804a4025a3021f60a))

* feat(web): /positions/pane returns side-pane body fragment

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b14d4b1`](https://github.com/chen-star/net_alpha/commit/b14d4b1a52d59072c1f63fee0f130b3b455cd5e5))

* feat(web): mount positions side pane skeleton (Alpine + HTMX)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9252240`](https://github.com/chen-star/net_alpha/commit/9252240e68a3d876e09052eb9411bbb042595af7))

* feat(web): drop &#39;click row to drill down&#39; hint (audit H9)

The row action menu (§3.4) now provides explicit affordance for row
interaction; the inline hint copy is redundant and adds visual noise.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fcec6f2`](https://github.com/chen-star/net_alpha/commit/fcec6f28553b09205018f4aefb5a7157b2b9a983))

* feat(web): mount row action menu on All / Stocks tab rows

Adds data-row=&#34;position&#34; + group class to each portfolio table row,
appends a matching w-10 header cell, and includes _row_actions.html
in the trailing cell. Uses r.accounts[0] as account label and none
for account_id (PositionRow is account-aggregated, not lot-scoped).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ac762ec`](https://github.com/chen-star/net_alpha/commit/ac762ecaa77388fb64d1ca426e35f2aac229fcae))

* feat(web): row action menu — Open ticker / Sim sell / Set basis / Copy

Adds _row_actions.html partial with four-item Alpine dropdown, hover-
revealed ⋯ button, and aria-keyshortcuts for future Phase 4 bindings.
Mounts on at-loss table rows. Vendors external-link.svg (Lucide 0.469.0).
Adds .row-actions CSS utility. Adds test_phase2_row_actions.py.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`da504eb`](https://github.com/chen-star/net_alpha/commit/da504eb48bcd5075559cbf41915ca97ebca841bf))

* feat(web): at-loss sorts clear rows first; renders &#39;clear&#39; for past dates

Adds _lockout_sort_key so rows with lockout_clear=None or in the past
sort before future-locked rows (ascending date within each group). Passes
`today` into template context so the lockout cell can compare
`row.lockout_clear &gt; today` and display &#39;clear&#39; for past/None dates.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5dc8613`](https://github.com/chen-star/net_alpha/commit/5dc8613bf36985eb0ed29b5c47746f97b9b0a233))

* feat(portfolio): HarvestOpportunity exposes open_basis for at-loss UI

Adds required `open_basis: Decimal` field between `qty` and `loss`.
Wires it at the single construction site in compute_harvest_queue using
the loop variable `basis`. Tightens the MKT/BASIS template guards from
`is defined` to direct access. Updates 4 tests that construct
HarvestOpportunity directly (test_harvest_opportunity_minimal ×1,
test_harvest_queue_render.py ×3).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3190943`](https://github.com/chen-star/net_alpha/commit/319094321ce26f865e8fc934e641223a0f8230f6))

* feat(web): at-loss table — new Lockout-clear + Replacement columns

Replaces the _harvest_queue.html include with a dedicated table that
always renders column headers (SYM/ACCT/QTY/MKT/BASIS/UNREAL/
LOCKOUT-CLEAR/REPLACEMENT). Also fixes budget field names (net_realized,
cap_against_ordinary) and updates the stale Phase 1 test that expected
the old &#34;Harvest queue&#34; heading.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b127a14`](https://github.com/chen-star/net_alpha/commit/b127a14dc15cf05c9f50243feb0f3263c8159a74))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`2d8ccb3`](https://github.com/chen-star/net_alpha/commit/2d8ccb31be41025f07ff343ab4a72f751264adf2))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1547280`](https://github.com/chen-star/net_alpha/commit/15472806f4360451c9af91453210887dceff054a))

* fix(web): /settings/* shows polite hint when drawer closed (review nit #6) ([`1b7ed78`](https://github.com/chen-star/net_alpha/commit/1b7ed78af0fad69e31668de2d2e97aadeeed980e))

* fix(web): drawer placeholders say &#39;Coming soon&#39; not specific phase (review nit #9) ([`6c78e6b`](https://github.com/chen-star/net_alpha/commit/6c78e6bc17cb3157546acd573f35c3078fd02579))

* fix(web): legacy imports page does not highlight Overview nav (review nit #7) ([`ba1857e`](https://github.com/chen-star/net_alpha/commit/ba1857e39464a46c92189f682ff481091b00e086))

* fix(web): empty-state CTA targets /settings/imports directly (review nit #8) ([`78f9927`](https://github.com/chen-star/net_alpha/commit/78f9927feb8c3e4c8fee6df7a903e07a851f307e))

### Style

* style: ruff format fixes for B1/B2 test files

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1a1edb5`](https://github.com/chen-star/net_alpha/commit/1a1edb5d81f4c8039d3cdebc88c4276ae6d120b3))

* style: ruff format test_phase2_review_backlog.py ([`5d0831a`](https://github.com/chen-star/net_alpha/commit/5d0831a8356cdb819981952cd2717ada835f69b8))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`44fed8c`](https://github.com/chen-star/net_alpha/commit/44fed8c8d0dcd36e00d3b628cd5b5842bb6ea12d))

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
side pane and drawer responsive at &lt;1024px. ([`ddece0a`](https://github.com/chen-star/net_alpha/commit/ddece0a09f04792b5a5d7b9c3e45916ee8b2a3cb))


## v0.28.0 (2026-04-28)

### Feature

* feat(web): drop Harvest tab from /tax (moved to /positions?view=at-loss)

Removes the Harvest nav tab from tax.html. The route still processes the
harvest view for profile-default routing, but the tab link is gone. Updates
test_tax_default_tab to assert new behaviour (no nav link, content still
renders).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cf66f12`](https://github.com/chen-star/net_alpha/commit/cf66f1294335b6ced5900f98739419ade20d4d2d))

* feat(web): positions tab views — at-loss serves harvest queue

Wires harvest queue context (rows, only_harvestable, budget) into
positions_page when selected_view == &#39;at-loss&#39;, replicating the context
that /tax?view=harvest used to build before it became a redirect.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`459a8ff`](https://github.com/chen-star/net_alpha/commit/459a8ffef08f67c62808889fafdfd59840e1d0c0))

* feat(web): positions tab strip — All/Stocks/Options/At-a-loss/Closed

Renames holdings.html → positions.html, updates route to render positions.html
and accept ?view= param. Adds _positions_tabs.html with 5-tab strip wired into
positions.html with view-based partial switching.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`458e715`](https://github.com/chen-star/net_alpha/commit/458e715f23d9247fc986799979714d2ab1cf1559))

* feat(web): remove inline density toggle from page chrome (audit H4/T1)

Per-page density toggles removed from holdings.html, tax.html, and
imports.html; the toggle now lives exclusively in the Settings drawer&#39;s
Density tab. Updated test_density_toggle_in_pages.py to assert drawer
presence instead of per-page chrome, updated test_phase3_smoke.py&#39;s
stale page-key assertion, and added test_phase1_density_relocation.py
to guard against per-page regression.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8d6f011`](https://github.com/chen-star/net_alpha/commit/8d6f01162e8d5ccca9e15a2896574190896fa00c))

* feat(web): drawer Density tab — global preference

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b43f89d`](https://github.com/chen-star/net_alpha/commit/b43f89d70963fe2654623ea1654b278a0b2aa4ef))

* feat(web): drawer Imports tab — lazy-load content from legacy page

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2873c07`](https://github.com/chen-star/net_alpha/commit/2873c0717cb2f54d981c5745b9cb7ed0c40b6d82))

* feat(web): settings drawer tab strip + placeholders

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`494c477`](https://github.com/chen-star/net_alpha/commit/494c477acd75988bffb8ef43304f2f0f809776ee))

* feat(web): auto-open settings drawer on /settings/imports load

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ee94a24`](https://github.com/chen-star/net_alpha/commit/ee94a246845269daa907edc3dd6d24054273e4f5))

* feat(web): add gear icon to topbar with drawer-open dispatch

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`af02141`](https://github.com/chen-star/net_alpha/commit/af021419d2fdfbc4578730d1d46a49fea72b8ee6))

* feat(web): drop redundant topbar pills (audit P10)

Remove account-count and period pills from portfolio and holdings topbar_right
blocks — they duplicate info already shown in the page subhead. Update
test_positions_routes and test_phase1_topnav to match new nav labels.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`21314f8`](https://github.com/chen-star/net_alpha/commit/21314f8d9a1983edc26e33b3bcde5d68f2a07937))

* feat(web): update active_page values for new nav (overview/positions)

portfolio→overview, holdings→positions, wash_sales→tax, imports→overview.
Also updates deprecated nav-badge test assertions to match Phase 1 design
(badge removed from nav, will move to gear icon in Section C).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`de09100`](https://github.com/chen-star/net_alpha/commit/de0910059ab2a8f3a1d6c1186f771abee8e2e77a))

* feat(web): rewrite top nav — Overview · Positions · Tax · Sim

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b34ffa8`](https://github.com/chen-star/net_alpha/commit/b34ffa8dcf84bdf6e601dfb286f01e76b5389a2c))

* feat(web): 301 /imports → /settings/imports; add settings drawer entry routes ([`4918311`](https://github.com/chen-star/net_alpha/commit/4918311728ba1d83b008b4223ccda507e2d4487d))

* feat(web): 301 /tax?view=harvest → /positions?view=at-loss ([`e6dd5f0`](https://github.com/chen-star/net_alpha/commit/e6dd5f03033abb7eaa953517b9d1bdf8285a33cb))

* feat(web): 301 /holdings → /positions (preserves query string) ([`a655fdf`](https://github.com/chen-star/net_alpha/commit/a655fdfb6220e7278afdf37d9b6e302a208bde95))

### Fix

* fix(web): CSV upload now redirects to Settings drawer instead of /imports

Critical #3: POST /imports returned 303 to /imports?flash=..., which
then hit the Phase 1 301 to /settings/imports — dropping the flash
param. Flash was already cosmetic (template never displayed it), so
removed the dead plumbing and changed the redirect target to
/settings/imports so the user lands on the drawer&#39;s Imports tab where
the new import is visible in the past-imports table.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`9cb5c63`](https://github.com/chen-star/net_alpha/commit/9cb5c63f4382df881f390a6f89020179ab59d77e))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0438dc8`](https://github.com/chen-star/net_alpha/commit/0438dc846745dd913a873f4fa21c6629e9d7d1d6))

### Refactor

* refactor(web): /holdings → /positions (redirects come in next commit) ([`b7a8aa5`](https://github.com/chen-star/net_alpha/commit/b7a8aa5604f048835584a886df7ae6e382627afe))

* refactor(web): rename holdings router to positions (no path change yet) ([`e3a5e44`](https://github.com/chen-star/net_alpha/commit/e3a5e4419531bc8e2082b02f777eb303f4389c3b))

### Style

* style(web): ruff format Phase 1 touchpoints

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`ad6da8c`](https://github.com/chen-star/net_alpha/commit/ad6da8cadbd53ab4a33c99c880854e9ff5f38f0e))

### Test

* test(web): re-capture snapshot baselines for Phase 1 IA

PAGES list updated to reflect the new IA: overview / positions-all /
positions-at-loss / tax-wash / tax-proj / settings-imports / sim /
ticker-nvda. The old `holdings`, `tax-harvest`, `imports`, and `portfolio`
baseline directories are gone — those URLs now 301 to the new locations.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`8a676bb`](https://github.com/chen-star/net_alpha/commit/8a676bb36042514b08e3ac36231bc2e015bcfbde))

* test(web): nav-link round-trip smoke test

Adds docstring clarifying the B4 round-trip parametrize purpose: each of
the four nav destinations (/, /positions, /tax, /sim) must appear as an
href on the home page and return HTTP 200 with the label in the HTML.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7038442`](https://github.com/chen-star/net_alpha/commit/70384427ae4d81ea4d21f951e098caed13518729))

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
Phase 2 rebuilds the at-loss tab; Phase 3 polishes page interiors. ([`6d00c2f`](https://github.com/chen-star/net_alpha/commit/6d00c2ffdd8535a475547fcd9a5652739e0432c2))


## v0.27.0 (2026-04-28)

### Build

* build: add snapshot-test/-update targets; exclude from default suite

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5946130`](https://github.com/chen-star/net_alpha/commit/59461304581af5b56abb6e491086fd64b35fa5b1))

* build: add pytest-playwright + playwright to [dev] extras

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`47e5de2`](https://github.com/chen-star/net_alpha/commit/47e5de2278421d71e2642b7b97527936773748a3))

* build: add vendor-lucide Makefile target (§5.4) ([`1a1f395`](https://github.com/chen-star/net_alpha/commit/1a1f3952ce4e2f07fa2ce999ed6f443317981eca))

* build(css): rebuild app.css after Phase 0 token additions ([`01ae997`](https://github.com/chen-star/net_alpha/commit/01ae9973af8c1e2f597191018f400b332f8b7ebb))

### Documentation

* docs: UI/UX evaluation &amp; redesign spec (Approach B)

Whole-product audit of the web UI across Portfolio, Holdings, Tax, Imports,
Sim, and Ticker pages, plus a multi-phase redesign that reorganizes the IA
(Overview/Positions/Tax/Sim + Settings drawer), promotes the Sim page,
absorbs the harvest queue into Positions, replaces the YAML tax-projection
setup with an inline form, and lays out a polish pass against ~50 audit
findings. Stack and visual tokens kept; five-phase sequencing with snapshot
tests as part of the work.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`099d54b`](https://github.com/chen-star/net_alpha/commit/099d54b2e121ec95b6941aa726fc552e28b84aaf))

### Feature

* feat(web): mount settings drawer skeleton in base.html ([`4ce1ec4`](https://github.com/chen-star/net_alpha/commit/4ce1ec49c4dba045d85d4e6d4985d4ec7968d558))

* feat(web): add empty settings drawer skeleton (§3.6) ([`d6ca51d`](https://github.com/chen-star/net_alpha/commit/d6ca51d0eb105d20c0c294a28b5ddbf20205b0aa))

* feat(web/static): vendor Lucide icons (§5.4) ([`43e71fa`](https://github.com/chen-star/net_alpha/commit/43e71fa646aa7408ebc9c6613be321c1ce2549c0))

* feat(web/css): add Phase 0 design tokens (§5.1) ([`46e8a95`](https://github.com/chen-star/net_alpha/commit/46e8a95ce4d0a1cc549dafca3e9c67a06f262e88))

* feat(web): register fmt_* helpers as Jinja globals ([`4ba38d7`](https://github.com/chen-star/net_alpha/commit/4ba38d7360b1d7310b67cc255560523753b8804e))

* feat(web/format): add fmt_date (§5.9) ([`1e89922`](https://github.com/chen-star/net_alpha/commit/1e89922ae9ae52de74a026487578cc7411b18ba2))

* feat(web/format): add fmt_percent (§5.9) ([`514e1f7`](https://github.com/chen-star/net_alpha/commit/514e1f7be20861877c17dc00b73594c5371f41bb))

* feat(web/format): add density-aware fmt_currency (§5.9) ([`7cb0546`](https://github.com/chen-star/net_alpha/commit/7cb0546b8a4e9506b3678a3f2df9d65dd9e2d385))

* feat(web/format): add fmt_quantity (§5.9) ([`baaf815`](https://github.com/chen-star/net_alpha/commit/baaf8152350e7bcaff7cd959daf53b0b494f3e45))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`a184483`](https://github.com/chen-star/net_alpha/commit/a184483e629ce1de7123e8930aad33a8a83dbb64))

### Style

* style: apply ruff format to Phase 0 test files

Trailing pass over tests touched by Section B/C/E to satisfy
`ruff format --check` (re-flowed long Path expressions, set literals,
and an f-string that fit on one line).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`be29b80`](https://github.com/chen-star/net_alpha/commit/be29b80223360f0660016497aed6a297420c2613))

### Test

* test(web): capture Phase 0 baseline page snapshots

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9f23727`](https://github.com/chen-star/net_alpha/commit/9f237272aa1d633605c87acce8c7b8dd21a99e3b))

* test(web): baseline-snapshot test scaffolding (no baselines yet)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6e8ba63`](https://github.com/chen-star/net_alpha/commit/6e8ba6356f0591bf911d0ff6a046046f3eb36ad5))

* test(web): add Playwright snapshot test scaffolding

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`495a468`](https://github.com/chen-star/net_alpha/commit/495a4685cefae9f8b2586a2a9814d76fa1a19f18))

* test(web): assert vendored Lucide icons present ([`08b60b9`](https://github.com/chen-star/net_alpha/commit/08b60b902403a80b04dda7eb86b658ddd4e02315))

### Unknown

* Merge branch &#39;phase0-foundations&#39; — Phase 0 Foundations ([`ff3fe65`](https://github.com/chen-star/net_alpha/commit/ff3fe654a6c978de937406a0d1e2309662588de7))

* Merge branch &#39;master&#39; of https://github.com/chen-star/net_alpha ([`cd9675b`](https://github.com/chen-star/net_alpha/commit/cd9675b671980e7c88e4718a6bd8c61634b45ddb))


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
  compact row padding. Two keystrokes to find any holding. ([`a8e7363`](https://github.com/chen-star/net_alpha/commit/a8e7363371a12189c75961c2b2cf477922c496d4))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`493654e`](https://github.com/chen-star/net_alpha/commit/493654eb92e374314ffda7b7784958ff6027f7c7))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`6673ba7`](https://github.com/chen-star/net_alpha/commit/6673ba72bf41acd5f22dd6c1840ceeda109a2ee1))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`af8fb2d`](https://github.com/chen-star/net_alpha/commit/af8fb2d5ccbfef17375ddc54bd59d071b3312226))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1171620`](https://github.com/chen-star/net_alpha/commit/1171620da98d413d8027fee2b9bd3c44c5038427))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`2e0abd2`](https://github.com/chen-star/net_alpha/commit/2e0abd2e0cda196c52084d4d6241a2e71f9b951f))


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
- tax: add .tabs/.tab/.tab--active styles, _harvest_queue uses .net-table ([`077694b`](https://github.com/chen-star/net_alpha/commit/077694b1a7fe8ae26097259eb180a9ca0e3d128c))

### Unknown

* Merge branch &#39;master&#39; of https://github.com/chen-star/net_alpha ([`4c1e0fb`](https://github.com/chen-star/net_alpha/commit/4c1e0fb3c5eab131a64fe0e98e36ce9216083b44))


## v0.24.0 (2026-04-28)

### Chore

* chore: ruff format fixes on Section F test files ([`aebb5cd`](https://github.com/chen-star/net_alpha/commit/aebb5cdf93f31fc03118e89e3ee6597e482e4ee4))

* chore(web): ruff UP017 fix — use datetime.UTC alias in Section D files

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0e66192`](https://github.com/chen-star/net_alpha/commit/0e66192c8226d10db510395bcaf799f3100f0ca8))

### Feature

* feat(web): switcher label reflects current request&#39;s account filter

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f87cb33`](https://github.com/chen-star/net_alpha/commit/f87cb3396edc64bcf860961c37949d2f02ed0674))

* feat(web): /tax default tab from ProfileSettings.default_tax_tab

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8edabc6`](https://github.com/chen-star/net_alpha/commit/8edabc64bbd41045dfd8117b786cd73e25174295))

* feat(web): density toggle on /holdings, /tax, /imports ([`687f085`](https://github.com/chen-star/net_alpha/commit/687f085ea570b5339e001ba575643044ffa070d1))

* feat(web): localStorage density override shim ([`eafcec1`](https://github.com/chen-star/net_alpha/commit/eafcec17daef8af85d687fd4877ed9cc20553e76))

* feat(web): density toggle template (Compact / Comfortable / Tax-view) ([`8ea6b14`](https://github.com/chen-star/net_alpha/commit/8ea6b14763e5dcf74cd6ab077e2fd8b6f62aaf9b))

* feat(web): profile-driven extra columns in holdings table ([`6f139b1`](https://github.com/chen-star/net_alpha/commit/6f139b1f8f12155e1c28f2e6be394c46e5aec2bd))

* feat(portfolio): premium_received per position for options profile ([`7ddf561`](https://github.com/chen-star/net_alpha/commit/7ddf5615d0e6d97941bf7308965e5d58e1d6ad96))

* feat(portfolio): position rows expose days_held + lt/st split ([`38aab14`](https://github.com/chen-star/net_alpha/commit/38aab14b9e02d5cb8d04a0d3887a6fb3f7f50849))

* feat(web): KPI hero ordering driven by ProfileSettings.order

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f7a4265`](https://github.com/chen-star/net_alpha/commit/f7a4265d7433078bdcc478017c79dda303c3c905))

* feat(web): conservative profile collapses wash-watch by default

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ce240a3`](https://github.com/chen-star/net_alpha/commit/ce240a340c6f97751fe36135d4b44734c34660b1))

* feat(web): pass ProfileSettings into /portfolio context

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ffedb56`](https://github.com/chen-star/net_alpha/commit/ffedb567059b1c552b59b32388aca45d37a8883c))

* feat(web): first-visit profile picker modal

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0505c5b`](https://github.com/chen-star/net_alpha/commit/0505c5b030dd2688f107cf22bdad3832a08a964d))

* feat(web): render profile switcher in base topbar

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`84f27f6`](https://github.com/chen-star/net_alpha/commit/84f27f6d492d0f19c8fb78d70bf5bf8923017fe1))

* feat(web): toolbar profile switcher template

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fd7b732`](https://github.com/chen-star/net_alpha/commit/fd7b7326221347576b36853f4dddf40412f63748))

* feat(web): POST /preferences writes per-account or all-account prefs

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b3d79aa`](https://github.com/chen-star/net_alpha/commit/b3d79aa141533fc44f27337e4371425f6dfea7a6))

* feat(web): get_profile_settings FastAPI dependency

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3cb25ce`](https://github.com/chen-star/net_alpha/commit/3cb25ceb9f8378ca6d85b21b10e5835f6b49d9a2))

* feat(prefs): resolve_effective_profile across single/all-account views

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9a7fee9`](https://github.com/chen-star/net_alpha/commit/9a7fee9ef7fbe0ed3ad39d0d858fab3a788a298f))

* feat(prefs): default_columns() and default_tax_tab() ([`e758b53`](https://github.com/chen-star/net_alpha/commit/e758b531939d59f40717396e7cd8f623ed26e3b6))

* feat(prefs): ProfileSettings.order() for KPI hero slots ([`3b397ca`](https://github.com/chen-star/net_alpha/commit/3b397caf1559a4adf6fa1c8102a1574c7ffade4a))

* feat(prefs): ProfileSettings.shows() rule table ([`a586965`](https://github.com/chen-star/net_alpha/commit/a5869652d323ef7b8f39a272e461bdef89a01683))

* feat(db): repository methods for user preferences

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1e8ed24`](https://github.com/chen-star/net_alpha/commit/1e8ed249015f7f90e84a5fcb7445116dada606a3))

* feat(db): v8 -&gt; v9 migration adds user_preferences

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e3a9cbb`](https://github.com/chen-star/net_alpha/commit/e3a9cbb0a309efda6639bb7123285b2a13afd495))

* feat(db): add UserPreferenceRow for v9 schema

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9062bca`](https://github.com/chen-star/net_alpha/commit/9062bcae14827dbb25fc64a47be5d75a6b6b645d))

### Fix

* fix(portfolio): premium_received skips assigned-put chain to avoid double-count

Assigned-put STO/synthetic-close trade pairs (basis_source in
{option_short_open_assigned, option_short_close_assigned}) already fold
their premium into the underlying stock&#39;s adjusted basis. Counting them
again in premium_received would double-credit the user-visible figure.

Move the premium accumulator below the existing _SKIP_AGG_SOURCES guard
so the same skip applies. Adds a regression test exercising the
assigned-put chain.

Caught in Phase 3 final code review. ([`21b4ad5`](https://github.com/chen-star/net_alpha/commit/21b4ad5510008bf48eb515f6e4ab542c6a7fabbf))

* fix: emit data-col markers in holdings.html wrapper for empty-state path

The _portfolio_table.html cols-meta span only renders when rows exist.
In the no-imports (empty-state) path the holdings page skips the table
fragment entirely, so data-col attributes never appeared in the HTML.

Add a hidden cols-meta span directly in holdings.html so column markers
are always present in the page regardless of import state.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`713ed6b`](https://github.com/chen-star/net_alpha/commit/713ed6b9eab2cf1612a2bf7679b927e2ed233078))

### Style

* style: ruff format

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ecc7be1`](https://github.com/chen-star/net_alpha/commit/ecc7be14c1050c985899d7e6d750ef2bec5e4e14))

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

29 commits, +78 tests (672 → 750 pass + 1 skip). ([`198afa1`](https://github.com/chen-star/net_alpha/commit/198afa1ce22a59960577fbd6d890d310dc34c041))


## v0.23.0 (2026-04-28)

### Feature

* feat(web): rename nav &#39;Wash sales&#39; to &#39;Tax&#39;

Update base.html nav link from /wash-sales (active_page=&#39;wash_sales&#39;)
to /tax (active_page=&#39;tax&#39;). The /tax route sets active_page=&#39;tax&#39; in
context so the nav link highlights correctly.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ddd6f1a`](https://github.com/chen-star/net_alpha/commit/ddd6f1ade0ce35bb480834978f608de10e86ea11))

* feat(web): /wash-sales -&gt; /tax 301 redirect (preserves query string)

The wash_sales_legacy handler redirects all /wash-sales requests to /tax.
Old sub-views ?view=table|calendar are normalised to view=wash-sales.
Update test_calendar.py and test_wash_sales_route.py to follow redirects
or target /tax directly. Add test_tax_redirects.py (3 tests).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`074ce26`](https://github.com/chen-star/net_alpha/commit/074ce26d7684b8e7b68dbd15a987558895466c7a))

* feat(web): tax.html 4-tab page (wash-sales | harvest | budget | projection)

Create tax.html wrapper template extending base.html with tab nav.
Extract wash-sales tab inner content into _tax_wash_sales_tab.html
(mirror of wash_sales.html inner body, links updated to /tax).
Add _offset_budget_tab.html and _projection_tab.html for budget and
projection tabs.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6d26543`](https://github.com/chen-star/net_alpha/commit/6d26543623fa537f907b6048c61d4f0a4846f0c2))

* feat(web): add /tax route with tabbed view dispatcher

Extract _wash_sales_context helper from wash_sales.py and wire up new
/tax route supporting wash-sales | harvest | budget | projection tabs.
Register tax_routes.router in app.py. Add test_tax_route.py (4 tests).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`78c597e`](https://github.com/chen-star/net_alpha/commit/78c597ed5e8a672f15e09978921494140ad47fca))

* feat(web): load etf_replacements into app.state at startup

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c4a5c8e`](https://github.com/chen-star/net_alpha/commit/c4a5c8edfe80f136f3eba11492fba9b4c90448f5))

* feat(web): pre-trade traffic-light on /sim result

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2ab3abc`](https://github.com/chen-star/net_alpha/commit/2ab3abc0c15568b15683784bbdda5c2c3749007f))

* feat(tax): assess_trade — bracket-push yellow + lot-method hint

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e77e7de`](https://github.com/chen-star/net_alpha/commit/e77e7de4ac738c824d7d1996f2178fb8864d893d))

* feat(tax): assess_trade — wash-sale red verdict

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b736e20`](https://github.com/chen-star/net_alpha/commit/b736e2000a795270fec50a34e423869adf57f499))

* feat(tax): TaxLightSignal model

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`094cb06`](https://github.com/chen-star/net_alpha/commit/094cb068ceb11c058b4fa064b07e8a3eaf4a5830))

* feat(web): year-end projection card on portfolio (with config-missing placeholder)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4466164`](https://github.com/chen-star/net_alpha/commit/4466164cf053a15d7339ec464a6594ca8f3c2b70))

* feat(tax): year-end tax projection (single marginal rate) + planned trades + bracket-push warnings

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a72dca4`](https://github.com/chen-star/net_alpha/commit/a72dca4326679fa0a2ab40f11d3031fc1f1ea60b))

* feat(tax): TaxBrackets, TaxProjection, MissingTaxConfig

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`25782af`](https://github.com/chen-star/net_alpha/commit/25782af5ad8ffdd4fe0fd06493b189e8db02b9ee))

* feat(web): offset-budget tile on portfolio KPI strip

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1b10e6a`](https://github.com/chen-star/net_alpha/commit/1b10e6a255ede31c47a614745bb843fd01eed0de))

* feat(tax): compute_offset_budget with $3K cap + carryforward + planned delta

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8011099`](https://github.com/chen-star/net_alpha/commit/801109931ded21b2afd6a283a4a3cc2c53aef35d))

* feat(tax): OffsetBudget and PlannedTrade models

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c8405b4`](https://github.com/chen-star/net_alpha/commit/c8405b4e8205606c68f0e4ca4f4d79cea57f913d))

* feat(web): _harvest_queue.html template

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9d126a8`](https://github.com/chen-star/net_alpha/commit/9d126a8d38ab8e5d795bf10b2a2818e4e747bd8b))

* feat(tax): compute_harvest_queue with LT/ST split + account filter

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0d1c0f4`](https://github.com/chen-star/net_alpha/commit/0d1c0f432eefc2b45e202ec76ac8afd288ffe2c7))

* feat(tax): HarvestOpportunity model + portfolio test conftest ([`73cf160`](https://github.com/chen-star/net_alpha/commit/73cf16024b048c5c0209131eb1d2f306e3d6e412))

* feat(engine): cross-asset lockout — open CSP locks out underlying

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3c55520`](https://github.com/chen-star/net_alpha/commit/3c55520625d915e96c8616a3abec5458c74050f9))

* feat(engine): same-symbol lockout-clear date computation

Adds compute_lockout_clear_date in engine/lockout.py: given a symbol, all trades,
and an as-of date, returns the first wash-sale-safe sale date (most recent buy + 31
days) or None when no buy is in the 30-day window. Handles cross-account buys and
substantially-identical ETF pairs. Structured for Task 6 cross-asset extension.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bb0b90b`](https://github.com/chen-star/net_alpha/commit/bb0b90b3a4520251d763e0aead2a9d9e58aebfda))

* feat(tax): premium origin extraction for CSP-assigned lots

Adds CSPAssigned / CCAssigned / PremiumOriginEvent models and
extract_premium_origin() to portfolio/tax_planner.py; recovers the
put premium from the STO→BTC-assigned chain for wheel-strategy lots.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e93a701`](https://github.com/chen-star/net_alpha/commit/e93a7013ea433ccff2dd9fcf387de1b09f176748))

* feat(engine): bundled etf_replacements.yaml + loader with consistency check

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d95febf`](https://github.com/chen-star/net_alpha/commit/d95febf3415a0da265a3eca54ff9345358fd0445))

* feat(audit): hygiene category &#39;tax_config_missing&#39;

Adds a new `tax_config_missing` info-level hygiene issue that surfaces
when no `tax:` section exists in config.yaml. Threads `settings` through
`collect_issues` and `get_imports_badge_count` as an optional kwarg so
all existing callers remain backwards-compatible.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c7e6212`](https://github.com/chen-star/net_alpha/commit/c7e62129d22ec3b4f7f6eb1c309085c183c52261))

* feat(config): add TaxConfig model and loader

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`20c756f`](https://github.com/chen-star/net_alpha/commit/20c756fa277cffe59a506a2bb032ad50f67d60f7))

### Fix

* fix(engine): bundled SCHD replacement DGRO to avoid etf_pairs conflict

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`564dc1c`](https://github.com/chen-star/net_alpha/commit/564dc1cfb5ca8c308fe344fed22c780b85646dc1))

### Refactor

* refactor(test): promote seed_lots to portfolio conftest fixture

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3b32bc3`](https://github.com/chen-star/net_alpha/commit/3b32bc38d96f41c66092c2f65cfffb7ed26b95d7))

### Style

* style: ruff import sort + drop unused TaxProjection test import

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`876cdf9`](https://github.com/chen-star/net_alpha/commit/876cdf9e8fd4ea058a3bc1dfd65a661b8574b179))

### Test

* test(tax): phase-2 smoke — /tax tabs, portfolio embeds, /sim traffic light

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3180be9`](https://github.com/chen-star/net_alpha/commit/3180be9ad0ed25ce2891f9b48ad77ecd6a1d4f50))

* test(tax): CSP origin round-trips through Repository

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ad1a1fd`](https://github.com/chen-star/net_alpha/commit/ad1a1fd1ba5aa34cfb595a893b12882ac9e78cef))

* test(tax): cross-asset wheel-strategy lockout coverage

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2f03414`](https://github.com/chen-star/net_alpha/commit/2f03414eea006f3d3905b000e4bf2b0e18719183))

* test(tax): replacement-suggestion wiring in harvest queue

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`390ce2e`](https://github.com/chen-star/net_alpha/commit/390ce2e639e154bc92a3e4313974afbd44a84fe0))

* test(tax): premium offset and only_harvestable filter coverage

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`5481d49`](https://github.com/chen-star/net_alpha/commit/5481d49a7f77bb0d51caf69059ddb50091cec1f4))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3510997`](https://github.com/chen-star/net_alpha/commit/351099755155d2c8f8ee6099a63027b3b606d89c))


## v0.22.0 (2026-04-28)

### Feature

* feat(audit): nav-bar Imports badge with 30s TTL cache

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`812bc22`](https://github.com/chen-star/net_alpha/commit/812bc2215f0a3336f92125784209100898cde669))

* feat(audit): POST /audit/set-basis updates trade basis with HTMX swap

Also clears basis_unknown=False in update_trade_basis when cost_basis is set.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6417d46`](https://github.com/chen-star/net_alpha/commit/6417d468fffe14cf1b92b40954997346751ecb2c))

* feat(audit): embed data-hygiene section on /imports

Adds _data_hygiene.html partial with severity badges and inline HTMX
fix-forms; wires collect_issues(repo) into the imports_page route so
the section appears when issues exist and is hidden when the DB is clean.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1c29466`](https://github.com/chen-star/net_alpha/commit/1c29466e94fbcbe8bcca3e6aec345177ef2c3d45))

* feat(audit): hygiene check — duplicate natural-key clusters ([`943abc2`](https://github.com/chen-star/net_alpha/commit/943abc2d4eb2a07614951d713fcb7b4ed56e50e6))

* feat(audit): hygiene check — orphan sells ([`bd44ad8`](https://github.com/chen-star/net_alpha/commit/bd44ad8cb7bb454d7c589cc456891d7e48ad7ace))

* feat(audit): hygiene check — basis-unknown buys with inline fix form

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ed37ce2`](https://github.com/chen-star/net_alpha/commit/ed37ce272ea515584651178f8bdf2401a81cf36f))

* feat(audit): hygiene check — unpriced symbols

Add _get_unpriced_symbols helper (monkeypatchable seam) and implement
_check_unpriced to emit a warn-severity HygieneIssue per equity symbol
with no cached price quote, with fix_url pointing to /holdings?symbol=X.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7195d8d`](https://github.com/chen-star/net_alpha/commit/7195d8dcfb5c8c8c3e9a181120e5dee4fb73dcc8))

* feat(audit): hygiene scaffold with HygieneIssue model + collect_issues dispatcher ([`76ba3d6`](https://github.com/chen-star/net_alpha/commit/76ba3d6e9f54d9ad39eaca3d806c19af6893d0aa))

* feat(audit): embed reconciliation strip on ticker page (lazy HTMX load)

Passes account_ids (derived from all accounts with trades for the symbol)
to the ticker template; the template renders one hx-get=&#34;load&#34; div per
account that triggers the /reconciliation/{symbol}?account_id= fragment.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ec7a5cd`](https://github.com/chen-star/net_alpha/commit/ec7a5cdcaa58e1688d352275613ddc1c9e45c9b6))

* feat(audit): /reconciliation/{symbol} route + strip + diff fragments

Appends GET /reconciliation/{symbol}?account_id=&amp;expanded= to audit_routes,
renders _reconciliation_strip.html (match/near_match/diff states with HTMX
investigate button) or _reconciliation_diff.html (per-lot table with collapse).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d13fd71`](https://github.com/chen-star/net_alpha/commit/d13fd71c26145baad6bc37e6311cdbf366caf522))

* feat(audit): per_lot_diffs() with cause hints

Appends LotDiff model, per_lot_diffs(), and _cause_hint() to
reconciliation.py; pairs broker G/L lots against net-alpha sell
trades by close date and returns deltas with heuristic cause labels.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1921056`](https://github.com/chen-star/net_alpha/commit/192105675ccee6375d1a3a832382a592686ac73a))

* feat(audit): reconcile() with tolerance + status enum

Adds ReconciliationResult + reconcile() comparing net_alpha realized P/L
against broker G/L lots, classifying results as MATCH / NEAR_MATCH / DIFF /
UNAVAILABLE based on a configurable tolerance threshold (default $0.50).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1f32e96`](https://github.com/chen-star/net_alpha/commit/1f32e96e15cb3782c09c476b24f576e071ed8312))

* feat(audit): broker provider registry ([`15b2628`](https://github.com/chen-star/net_alpha/commit/15b262803494cd2dc7764777c8f2a65b90031b92))

* feat(audit): SchwabGLProvider over existing get_gl_lots_for_ticker

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`30cb22d`](https://github.com/chen-star/net_alpha/commit/30cb22d89b17c7ce2227bc0c53ab9c6fc7846110))

* feat(audit): BrokerLot + BrokerGLProvider ABC

Define normalized broker lot row and abstract provider interface for
reconciliation. Supports flexibility across broker GL formats.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`51efb7d`](https://github.com/chen-star/net_alpha/commit/51efb7d9291f3e400f30d9d94d672e62c96e92e6))

* feat(audit): wire provenance triggers into Portfolio KPIs and Ticker page

- Add &lt;dialog id=&#34;provenance-dialog&#34;&gt; mount point to base.html (all pages)
- Add _resolve_account_id + _build_metric_refs helpers to portfolio route
- Pass metric_refs to _portfolio_kpis.html via portfolio_kpis and portfolio_body handlers
- Decorate Realized P/L (period + lifetime), Unrealized P/L (period + lifetime), Wash Impact, Cash, and Net Contributed KPIs with provenance_link macro; skip Open Position $ (market snapshot)
- Build RealizedPLRef per symbol in ticker_drilldown, decorate YTD Realized P/L
- Add integration tests (TDD: 3 fail → 3 pass)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`6b91ec9`](https://github.com/chen-star/net_alpha/commit/6b91ec9b6dc567b88001ec46dfb1dfa46333ed16))

* feat(audit): provenance_link Jinja macro with HTMX trigger

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`44c4899`](https://github.com/chen-star/net_alpha/commit/44c489966bf7ee39871b8b112b6b15bc23b3d900))

* feat(audit): full provenance modal template with three sections

Replace placeholder _provenance_modal.html with the complete template
rendering contributing trades, applied wash-sale adjustments (with rule
citation), and contributing cash events in styled tables.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`610b8f6`](https://github.com/chen-star/net_alpha/commit/610b8f6a250ca1193b94ae83eecdd72316e63e9d))

* feat(audit): GET /provenance/{encoded} returns trace fragment with error fallback

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4745359`](https://github.com/chen-star/net_alpha/commit/4745359cf4e75e7a905a974c073dae4ff3ae1a84))

* feat(audit): re-export public API from package root ([`1537fc9`](https://github.com/chen-star/net_alpha/commit/1537fc985cc04edc88f4c100537bb26c48507070))

* feat(audit): provenance_for handles CashRef and NetContributedRef variants

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4004180`](https://github.com/chen-star/net_alpha/commit/4004180d380781ffc9bd4f4bd33e9cfe1d1d1c31))

* feat(audit): provenance_for handles WashImpactRef variant

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`53b0417`](https://github.com/chen-star/net_alpha/commit/53b041713c9b5ea59b5264b280c870e82c7423bd))

* feat(audit): provenance_for handles UnrealizedPLRef variant

Adds _unrealized_pl dispatcher and _account_id_match helper; refactors
_trade_account_match to delegate to the new shared helper (DRY).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`50c0750`](https://github.com/chen-star/net_alpha/commit/50c0750b260dac64f06c639ab8171fbaee568bff))

* feat(audit): provenance_for handles RealizedPLRef variant

Adds the provenance_for dispatcher to provenance.py with the first
variant _realized_pl, which filters repo.all_trades() by period,
symbol, and account_id to build a ProvenanceTrace with signed amounts
and a human-readable metric_label.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c7c7388`](https://github.com/chen-star/net_alpha/commit/c7c738871c5e8400b02235a2cdcbf95b3d0f3258))

* feat(audit): add ProvenanceTrace, ContributingTrade, AppliedAdjustment types

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`76fb429`](https://github.com/chen-star/net_alpha/commit/76fb42946c650498129f5615aa892a1f2ac19834))

* feat(audit): add MetricRef discriminated union + base64 encoding

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9bfcff5`](https://github.com/chen-star/net_alpha/commit/9bfcff531a8eaf7ba1b48919768b77bf631b5adf))

* feat(audit): scaffold audit package with shared test fixture ([`2f3ea76`](https://github.com/chen-star/net_alpha/commit/2f3ea76030950cec3aa9111d8f6460d0f16a1843))

### Fix

* fix(audit): address final review findings

- Hoist repo.list_accounts() out of per-trade and per-violation loops in
  _realized_pl and _wash_impact (matches existing _unrealized_pl pattern).
- POST /audit/set-basis now triggers stitch + recompute_all_violations and
  invalidates the badge cache so engine state matches the DB immediately.
- Export reconcile, collect_issues, and related types from audit/__init__.py
  per the plan&#39;s stable-import-path contract. ([`d4932c9`](https://github.com/chen-star/net_alpha/commit/d4932c953c26162c01bd886e9e97c00a81c7a45c))

### Refactor

* refactor(audit): DRY account-display dict construction via _accounts_by_id

Eliminates the last N+1 in _unrealized_pl (was iterating list_accounts() per
open lot). All three dispatcher branches now share one helper.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`75e6414`](https://github.com/chen-star/net_alpha/commit/75e6414a9ae71e2573ff44df881d1636dcfd74de))

* refactor(audit): hoist all_trades lookup + lift Repository/Trade imports to top

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`08dd71b`](https://github.com/chen-star/net_alpha/commit/08dd71b8c0b0152b75f5d578741fe48dacfa9875))

* refactor(audit): lift seed_import helper into conftest for reuse ([`1dc613f`](https://github.com/chen-star/net_alpha/commit/1dc613f548c8bac2735d46b213c35d27be4f71ac))

### Style

* style(audit): move pytest import to module top in test_metric_ref_encoding ([`6322e1a`](https://github.com/chen-star/net_alpha/commit/6322e1a90e80fdf7c0ccb254ee8985a7f8e82467))

### Test

* test(audit): phase-1 smoke test — provenance + reconciliation + hygiene

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9be039d`](https://github.com/chen-star/net_alpha/commit/9be039dfd73bd5b98e7e5353f8b1c38f82f4e925))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`2b9bd7f`](https://github.com/chen-star/net_alpha/commit/2b9bd7f5a419a87da89df658776c4209308df341))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`67282c0`](https://github.com/chen-star/net_alpha/commit/67282c06be3d6b2f00ef3fb190c32b44886f18cb))


## v0.20.1 (2026-04-27)

### Chore

* chore: update agent instructions and coverage ([`11c82a2`](https://github.com/chen-star/net_alpha/commit/11c82a2ec4802b001d3e9b10aa7b3d02b404a169))

### Ci

* ci: fix tests by installing all extras ([`0915b39`](https://github.com/chen-star/net_alpha/commit/0915b39a3d839cd5cc470930e3ac34769f98f745))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1a7d4c0`](https://github.com/chen-star/net_alpha/commit/1a7d4c022d1dd246d9b04706abe541b26386b6cc))


## v0.20.0 (2026-04-27)

### Chore

* chore: ruff format + lift in-function imports to module top ([`4331f86`](https://github.com/chen-star/net_alpha/commit/4331f867f8aa7c5648e16c24ba62153def5c69b3))

### Feature

* feat(web): show cash_event_count on imports list summary and detail row ([`1a56a47`](https://github.com/chen-star/net_alpha/commit/1a56a47a7c5d9c55bb656954e2bc06ed234a4164))

* feat(web): portfolio body — equity + cash side by side, allocation full width ([`5e3d60c`](https://github.com/chen-star/net_alpha/commit/5e3d60ca4fee504746edb805165e04e6dfc6a5be))

* feat(portfolio): allocation donut shows Cash slice

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1a47e3e`](https://github.com/chen-star/net_alpha/commit/1a47e3e5473f1c9f0cf6917e3f9655290e7f2300))

* feat(web): add Cash / Net contributed / Growth KPI tiles ([`945e162`](https://github.com/chen-star/net_alpha/commit/945e16252845957bc2c452ec0d35bed6669cee44))

* feat(web): add _portfolio_cash_curve.html — ApexCharts balance + contributions ([`348c0ee`](https://github.com/chen-star/net_alpha/commit/348c0eeae1bcb29196e199824d7bb4613fb671b7))

* feat(web): wire cash KPIs/points/slice into /portfolio/body context

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`bc19806`](https://github.com/chen-star/net_alpha/commit/bc1980691fb6349216a6f0150f4e16014a7e5c30))

* feat(portfolio): cash_allocation_slice for donut integration ([`234c422`](https://github.com/chen-star/net_alpha/commit/234c422c5d91da81a8bf30a841226a60bc81835e))

* feat(portfolio): compute_cash_kpis ([`2ea7503`](https://github.com/chen-star/net_alpha/commit/2ea7503ab1c0cc432e2bb85833b586035501093b))

* feat(portfolio): add CashFlowKPIs dataclass alongside CashBalancePoint ([`dff17aa`](https://github.com/chen-star/net_alpha/commit/dff17aa41279cd8390741b3a9308adf47c024828))

* feat(portfolio): build_cash_balance_series with period and account scoping

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`25b768f`](https://github.com/chen-star/net_alpha/commit/25b768f198821efac8dbac993da2b522f4a3d9dd))

* feat(import): wire cash_events through add_import and Schwab callers ([`aa3dee0`](https://github.com/chen-star/net_alpha/commit/aa3dee08c2331a227befe41b15e445c7a431959a))

* feat(schwab): emit CashEvent for transfers, dividends, interest, fees, sweeps ([`134fe4b`](https://github.com/chen-star/net_alpha/commit/134fe4b2204043dec5084b69d2e5fb986a14be5f))

* feat(schwab): populate gross_cash_impact from CSV Amount on every trade ([`a629b19`](https://github.com/chen-star/net_alpha/commit/a629b19eb4981799dd8b55ed412483ca420d8f21))

* feat(models): add ImportResult for parser return value ([`bea7e36`](https://github.com/chen-star/net_alpha/commit/bea7e36ac15b77c11e4f0a4ac668877e97fe7f9b))

* feat(repo): list_cash_events with account/date scoping ([`832f870`](https://github.com/chen-star/net_alpha/commit/832f8708f9c8bc3d41f59c8a6c4cc45788daf699))

* feat(repo): add_cash_events with dedup on (account_id, natural_key) ([`2d682d3`](https://github.com/chen-star/net_alpha/commit/2d682d3c5da5f4a474cf9f19bb8536f5d5bc5946))

* feat(db): v7→v8 migration for cash_events + gross_cash_impact + cash_event_count ([`f63828b`](https://github.com/chen-star/net_alpha/commit/f63828b13d1f7c37427ee6fdeb1530c467e87e9d))

* feat(db): add cash_events table; add gross_cash_impact and cash_event_count columns ([`e401c91`](https://github.com/chen-star/net_alpha/commit/e401c914fb47fe9f8fb8fe309763e37d4dcee647))

* feat(models): add CashEvent domain model with natural_key dedup ([`5b0e645`](https://github.com/chen-star/net_alpha/commit/5b0e645bbebdf5aaf3c49bfc54cf90e778ae4308))

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

Adds regression tests for each. ([`7769970`](https://github.com/chen-star/net_alpha/commit/776997020345d98f38e832af48ae809f7ed755c2))

* fix: skip option-side actions in parse_full; clarify add_import commit ordering ([`72590a1`](https://github.com/chen-star/net_alpha/commit/72590a1e959ce4e17db4e4d088ba58dfe227f739))

* fix(repo): cascade-delete cash_events on remove_import ([`531175d`](https://github.com/chen-star/net_alpha/commit/531175d65f8bab4ee9fd618f9bee559bbc6e0f8a))

### Test

* test(integration): cash events round-trip through both Schwab CSV fixtures

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a8e0667`](https://github.com/chen-star/net_alpha/commit/a8e06674a368efc08df4bbac3b288d37b2770e1d))

* test(fixtures): add anonymized Schwab Short/Long Term Transactions CSVs ([`406d8fc`](https://github.com/chen-star/net_alpha/commit/406d8fc4dfc9926717cbf219e26e29055731dbec))


## v0.19.0 (2026-04-27)

### Feature

* feat(splits): manual per-lot edit UI on /ticker/{sym} (item 5)

Inline edit form on each lot row writes a lot_overrides record with
reason=&#39;manual&#39;. apply_manual_overrides replays the latest edit per
(trade_id, field) at the end of every recompute, so manual edits survive
re-import / unimport / future recomputes.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2257a5e`](https://github.com/chen-star/net_alpha/commit/2257a5ec44c256607ea8894f0176756428035b28))

* feat(splits): auto-sync on first import of a new symbol (item 5)

When a CSV brings in symbols never seen in any prior import, fire
sync_splits for those symbols so existing wash-sale data stays accurate
without manual intervention. Re-imports of known symbols do NOT trigger
fetch -- avoids burning network on every CSV upload.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`69062d2`](https://github.com/chen-star/net_alpha/commit/69062d2842cb490025487cfd6e19b94b1cd7c6b1))

* feat(splits): /splits/sync endpoint + toolbar Sync splits button (item 5)

PricingService.sync_splits orchestrates fetch -&gt; upsert -&gt; apply. Honors
the prices.enable_remote flag (returns error_symbols when disabled, no
network call). Toolbar button POSTs symbols=ALL and reloads the page.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9b48931`](https://github.com/chen-star/net_alpha/commit/9b489312722570ad7b00d893a666e3b38ec635d2))

* feat(engine): apply_splits as final step of recompute (item 5)

apply_splits mutates regenerated lots whose date is before each known
split&#39;s ex-date. Multiplies qty by ratio, preserves total basis (basis is
dollar, not per-share). Idempotent via (trade_id, split_id) check in
lot_overrides. Wired into recompute_all_violations so re-imports and
unimports keep the split-adjustment intact. ([`e772201`](https://github.com/chen-star/net_alpha/commit/e7722013fa7ff953c83ce182aff06707fdc211cc))

* feat(pricing): YahooPriceProvider.fetch_splits (item 5)

Wraps yfinance.Ticker.splits with the same error-swallowing pattern as
get_quotes (per-symbol failures return empty list, never raise). Default
on the ABC is to return [] so providers without split data are unaffected.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`71251bf`](https://github.com/chen-star/net_alpha/commit/71251bf642033729e9ccf1181e5fc7a4db00d7f6))

* feat(db): repository methods for splits + lot_overrides (item 5)

add_split is idempotent on (symbol, split_date). lot_overrides keyed by
trade_id since lots are regenerated on every recompute.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f2b8a37`](https://github.com/chen-star/net_alpha/commit/f2b8a370a8cf7e4dca809e693751d28b1f6d17e0))

* feat(db): schema v7 — splits + lot_overrides tables (item 5)

splits: keyed (symbol, split_date) UNIQUE, holds ratio + source + fetched_at.
lot_overrides: audit trail of qty/basis changes, keyed by trade_id (stable
across recompute since lots are regenerated). split_id FK lets apply_split
check idempotency. Also bumps hardcoded version assertions in older migration
tests from 6 → 7. ([`0fa6c37`](https://github.com/chen-star/net_alpha/commit/0fa6c37f57bde1deea89d0cd3e56deefaf31452b))

* feat(web): merge Detail+Calendar into /wash-sales (item 2)

New route /wash-sales with ?view=table|calendar toggle and a unified
filter bar (ticker, account, year, confidence). Old paths 301-redirect
preserving query string. Top-nav &#39;Detail&#39; becomes &#39;Wash sales&#39;;
&#39;Calendar&#39; link removed.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`be3dc16`](https://github.com/chen-star/net_alpha/commit/be3dc164c7a4d02c0da47d3f86430604bb36c86c))

* feat(web): drop Realized col, add % to Unrealized on Holdings (item 1)

The {period} Realized column was redundant with Portfolio KPIs and the
Timeline. Unrealized now stacks dollar and percent inline, color-coded
together. Percent is unrealized_pl / open_cost.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`62f545d`](https://github.com/chen-star/net_alpha/commit/62f545d66ae0ca020a17b2bc544d56b237f4aea0))

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

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`950f988`](https://github.com/chen-star/net_alpha/commit/950f988c166b5c8714ffef014b7d35c4adfe1501))

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

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`07be6ca`](https://github.com/chen-star/net_alpha/commit/07be6ca1e8e3a188eb0c8f30d3e199b89d5d269f))

* fix(web): extract holdings symbol filter to named Alpine component (item 4)

Inline 27-line x-data block was leaking its expression body as visible text
on the Holdings page when Alpine couldn&#39;t evaluate it. Move to a separate
JS file as a named Alpine.data(&#39;symbolFilter&#39;, ...) component, so the only
inline content is the call site. Also fixes the dropdown&#39;s mis-positioning
(secondary symptom of the same parse failure).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3aad68f`](https://github.com/chen-star/net_alpha/commit/3aad68fbb7dc8833dc599f9bc45b99d435be90d3))

* fix(web): toolbar form stays on the current page (item 6)

Previously the period/account toolbar always submitted to /, bouncing the
user from /holdings back to portfolio when they changed Account. Now each
page passes its own toolbar_action.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`8638369`](https://github.com/chen-star/net_alpha/commit/86383690b6cc1262af05d59799c766a7a7a11579))

### Test

* test(splits): e2e split survival across unimport/reimport (item 5)

Adds integration test verifying split adjustments persist through the
full lifecycle of import -&gt; sync -&gt; unimport -&gt; reimport. Includes fix
to remove_import to clean up lot_overrides for deleted trades, allowing
splits to be re-applied on reimport.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0806438`](https://github.com/chen-star/net_alpha/commit/0806438cdd4dc7644bfee6ce3a2bf3026231fefa))


## v0.18.0 (2026-04-27)

### Chore

* chore: sync uv.lock to pyproject v0.17.0 wash-alpha version

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`cf192c4`](https://github.com/chen-star/net_alpha/commit/cf192c43fa5dca0d18088ef4034053efb1ba679a))

### Feature

* feat(web): Add-trade button + per-row affordances + form modals on ticker page ([`8b096bf`](https://github.com/chen-star/net_alpha/commit/8b096bf5e270e9b92ea11c0896073659d9feb7b6))

* feat(web): POST /trades/{id}/delete ([`055e9f6`](https://github.com/chen-star/net_alpha/commit/055e9f6a76e23fb0cba769fc68420c003b453b8c))

* feat(web): POST /trades/{id}/edit-manual ([`ee29587`](https://github.com/chen-star/net_alpha/commit/ee29587080d4068bbe0e6e9f67da3c1aa55050c8))

* feat(web): POST /trades/{id}/edit-transfer ([`dbc8066`](https://github.com/chen-star/net_alpha/commit/dbc80663cc10247963f1b97a9fecbb9daa7faa99))

* feat(web): POST /trades — create manual trade

Form-driven endpoint mapping Buy/Sell/Transfer In/Transfer Out to
(action, basis_source), validates account/date/quantity, calls
repo.create_manual_trade, and redirects to /ticker/{symbol}.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b5bde27`](https://github.com/chen-star/net_alpha/commit/b5bde27dadcde8b0e55d521ddc0ed319c587a7a0))

* feat(web): Timeline shows Transfer In/Out + provenance badges

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`001b606`](https://github.com/chen-star/net_alpha/commit/001b606583e4fdf18c65d0eaac40b24e912ac577))

* feat(web): display_action helper for transfer-aware Timeline labels ([`76b03cc`](https://github.com/chen-star/net_alpha/commit/76b03ccc93465702aea6d7202dd52b9bf258165d))

* feat(db): Repository.delete_manual_trade ([`d7a26c6`](https://github.com/chen-star/net_alpha/commit/d7a26c6a73adb8d623a1077bcdef0eaeacc249d1))

* feat(db): Repository.update_manual_trade ([`b7bb8fb`](https://github.com/chen-star/net_alpha/commit/b7bb8fb8d6fa2f37c73d805f0ec1151270aa1cdf))

* feat(db): Repository.update_imported_transfer (date + basis|proceeds, immutable natural_key) ([`8111a2c`](https://github.com/chen-star/net_alpha/commit/8111a2c9623e76500bc9d6f5977a738d65654019))

* feat(db): Repository.create_manual_trade + manual: natural_key namespace ([`34451d8`](https://github.com/chen-star/net_alpha/commit/34451d8daed4280afac37edf0ff8e430d1744a1c))

* feat(models): Trade.is_manual + Trade.transfer_basis_user_set

Add is_manual and transfer_basis_user_set fields to the Pydantic Trade
model and TradeRow SQLModel, relax TradeRow.import_id to nullable, and
propagate both flags through _row_to_trade so all_trades() carries them.
Update v5→v6 migration tests to reflect completed Task 2 state.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3ebc0e4`](https://github.com/chen-star/net_alpha/commit/3ebc0e4cb2d5c10768dec3d499fa29ef64983ed7))

* feat(db): v5→v6 — add trades.is_manual + transfer_basis_user_set; nullable import_id

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4acec5f`](https://github.com/chen-star/net_alpha/commit/4acec5f3bfeea9ecc6a863a51da3edcbab1f9a6a))

* feat(web): multi-select symbol filter popover on holdings table

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fc62c7a`](https://github.com/chen-star/net_alpha/commit/fc62c7aaa0a372c42e9bb5901b8ddf88495a0fb7))

* feat(web): replace ?q= with ?symbols= multi-select filter on /portfolio/positions ([`6da8634`](https://github.com/chen-star/net_alpha/commit/6da8634346e27606f31893e7b042e748f84a8d88))

* feat(web): /holdings page + nav link

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`de0467f`](https://github.com/chen-star/net_alpha/commit/de0467fb1adf05794f91d83da70c5cb5f8ee72c1))

* feat(web): single-fragment load on /portfolio (5x→1x request) ([`6d7806e`](https://github.com/chen-star/net_alpha/commit/6d7806e20bd1b18fe37770b229ba268312a8ca72))

* feat(web): /portfolio/body bundled fragment

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`04936bc`](https://github.com/chen-star/net_alpha/commit/04936bcaf79257a7dc0df296dab51a2b775c3a82))

* feat(web): styled Choose Files button + file-count chip in import modal ([`5ea9c5e`](https://github.com/chen-star/net_alpha/commit/5ea9c5ed6e6454faab93f37fae102d9813bd8100))

* feat(web): equalize equity-curve and allocation panel widths ([`4c94c9f`](https://github.com/chen-star/net_alpha/commit/4c94c9f76f649ee9d6d0948d944dc79308998991))

### Fix

* fix(web): account allow-list from list_accounts; add duplicate-count and violation-removal tests

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fc4384f`](https://github.com/chen-star/net_alpha/commit/fc4384f8726dd58a1ba0e694144e1d4fa21e8864))

* fix(test): include is_manual + transfer_basis_user_set in raw trade insert ([`bc154bd`](https://github.com/chen-star/net_alpha/commit/bc154bd71a1d3408a8ab3f1a53bad6205c1ab018))

* fix(web): correct hx-target and smart-quote regressions in holdings table fragment

Replace legacy hx-target=&#34;#portfolio-positions&#34; with &#34;#holdings-positions&#34; across all Show/Pagesize/Pagination buttons; fix Unicode smart quotes (U+201C/201D) on the status-hint span class attribute; add two regression tests covering both issues.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`af8fb92`](https://github.com/chen-star/net_alpha/commit/af8fb92fed5d1b9d549e65b2050a6dd74cd96e4b))

### Test

* test(integration): re-import preserves user edits to transfer rows

End-to-end check that editing a transfer-in row&#39;s date+basis survives
a re-import of the same Schwab CSV (idempotent dedup via natural_key).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`abb426b`](https://github.com/chen-star/net_alpha/commit/abb426befc281b28159cf1dc5aac0fd13b8df822))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`d7c56d8`](https://github.com/chen-star/net_alpha/commit/d7c56d84b286ead08ba75c13343b121cbeb2099b))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`c25aa76`](https://github.com/chen-star/net_alpha/commit/c25aa7675b1239afd4ac77958d9b8dbe246a0d35))

* chore: remove treemap module, template, tests, and TreemapTile model ([`73ec625`](https://github.com/chen-star/net_alpha/commit/73ec625df9227f37311531ff2fa3c9d19615939a))

### Documentation

* docs: update CLAUDE.md — treemap → allocation + add wash_watch in portfolio module list ([`b5777b4`](https://github.com/chen-star/net_alpha/commit/b5777b461c5ad7f245188dbaf6240052c339dcd6))

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

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fa9daee`](https://github.com/chen-star/net_alpha/commit/fa9daeec51e8009270a2f15ff4490301eff90240))

* feat(web): restyle imports + drop zone + modal + toast

Apply Apple-dark design tokens to the full imports stack: panel/net-table
wrappers, dashed drop zone with rgba border, surface-variant modal,
pos/warn colours in detection cards, label-uc labels, and bg-pos toast.
Adds {% set active_page = &#39;imports&#39; %} for topbar highlight.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b115a71`](https://github.com/chen-star/net_alpha/commit/b115a71816f4064546f1a0c5700b02692a3435be))

* feat(web): restyle calendar pages — Apple-system colors for ribbons + dots

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4f9aade`](https://github.com/chen-star/net_alpha/commit/4f9aade9ee60037faf00febac19556ac4395127e))

* feat(web): restyle positions table, toolbar, empty state under new tokens

Replaces all slate/white/emerald Tailwind classes in the three portfolio
fragments with the new design-token components (net-table, panel, seg,
seg-active, label-uc, btn, text-pos/neg, text-label-*, bg-surface-*).
Adds ticker-initial icon block to the Symbol cell and hairline borders
on select and pagination controls via CSS variable.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8e7e1e5`](https://github.com/chen-star/net_alpha/commit/8e7e1e590b3e896a0fd27376ab8758f84a1ea72a))

* feat(web): equity curve via ApexCharts area chart with violet &#39;+ unrealized&#39; marker ([`7efac86`](https://github.com/chen-star/net_alpha/commit/7efac865b5b1587e0f620f1ad7353e10a1bcb904))

* feat(web): shared ApexCharts dark theme + merge helper at /static/charts.js ([`952357f`](https://github.com/chen-star/net_alpha/commit/952357ff4c72c5962bad53241d1ba03495753159))

* feat(web): /portfolio/wash-watch fragment route

Wire recent_loss_closes() into a GET handler that renders the
_portfolio_wash_watch.html partial; supports ?account= and ?window_days=
query params.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9a7dc8c`](https://github.com/chen-star/net_alpha/commit/9a7dc8cf307783094928bf8d0aa7ab8815bdafff))

* feat(web): wash-watch partial — countdown rows w/ red→amber→green safe-bar

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a0b7266`](https://github.com/chen-star/net_alpha/commit/a0b72666792489168dd35d17ef4c3db33d77fc7e))

* feat(portfolio): recent_loss_closes — wash-sale watch aggregation

Add LossCloseRow model and recent_loss_closes() pure function that
aggregates sell trades with negative realized P/L in the last N days,
collapsed per symbol (most recent close, summed loss), sorted by
close_date desc.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e1b5b4a`](https://github.com/chen-star/net_alpha/commit/e1b5b4a6365cdf9af379862b2dc67e21a7b0450a))

* feat(web): portfolio.html — equity+allocation row, wash-watch slot, drop treemap ([`31ac787`](https://github.com/chen-star/net_alpha/commit/31ac7879325f575116a1ae48bb3640c8ee431869))

* feat(web): replace /portfolio/treemap route with /portfolio/allocation ([`0bd2fed`](https://github.com/chen-star/net_alpha/commit/0bd2fedbfd9b7c02bf092d94aaabb2fc81a196e5))

* feat(web): allocation partial — donut + concentration stats + ranked chips ([`27ec5dd`](https://github.com/chen-star/net_alpha/commit/27ec5ddc6dd206c841912ce90e3e788ef2079044))

* feat(portfolio): build_allocation — donut/leaderboard view + concentration stats

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`063c7dc`](https://github.com/chen-star/net_alpha/commit/063c7dc4b9d1fa88f86a1043d580982f068b3ff5))

* feat(web): combined hero KPI cards (Realized/Unrealized) + Open$/Wash mini

Collapse 6-card KPI partial into 4-card grid-cols-12 layout: Realized hero (4 cols, kpi-hero halo) with YTD+Lifetime side-by-side, Unrealized hero (4 cols), Open position $ mini (2 cols), Wash impact mini (2 cols). Route now calls compute_wash_impact and passes wash_impact_total + wash_violations into template context.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`bf49788`](https://github.com/chen-star/net_alpha/commit/bf497883e6cb18c76bd28233ac186a197e30f831))

* feat(web): restyle base.html — vibrancy topbar, Inter+JBM, ApexCharts include

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`536640d`](https://github.com/chen-star/net_alpha/commit/536640dc9eb2242a28df83cf7e51dd6c34e3ed5a))

* feat(web): @font-face Inter+JBM, type scale, full component library

Add 6 @font-face declarations for Inter (400/500/600/700) and JetBrains
Mono (400/500), expand @layer base with dark color-scheme, Inter font
features/antialiasing, h1-h3 type scale, and .num tabular-nums rule.
Replace minimal @layer components with full design-system library:
.panel, .panel-head, .label-uc, .kpi, .kpi-hero, .seg, .pill, .topbar,
.nav-link, .chip-confirm/probable/unclear, .net-table, .brand-mark, plus
back-compat aliases; var(--color-*) used directly where @apply text-*
tokens conflict with Tailwind v4 reserved names.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`564feb2`](https://github.com/chen-star/net_alpha/commit/564feb211a02b8142ce3ac052d7a6eaa504e4ffd))

* feat(web): new Apple-dark color tokens, font stack, radii in tailwind config

Replaces the old small v3-style palette with the full Apple-dark design
system (canvas, hairline, label-tier text, P/L semantics, rank slots, brand
cyber). Updates app.src.css from Tailwind v3 directives to v4 @import/@theme
syntax required by pytailwindcss 0.1.4 (bundles Tailwind v4). Back-compat
aliases (confirmed, probable, unclear, primary, secondary, accent, ink) keep
existing templates rendering until they are restyled.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`804a90c`](https://github.com/chen-star/net_alpha/commit/804a90cc07f11b7a101ea84912747a77872005a6))

* feat(web): vendor ApexCharts 3.51 (no runtime npm)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ad44837`](https://github.com/chen-star/net_alpha/commit/ad448379992368cc5ef2fdc7949a32cbdb20771f))

* feat(web): vendor Inter and JetBrains Mono woff2 fonts

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f60fb20`](https://github.com/chen-star/net_alpha/commit/f60fb200926ce980ab9bbb734eb89a1c7db12b33))


## v0.16.1 (2026-04-26)

### Fix

* fix(web): include current year and trade-activity years in Calendar YEAR dropdown

The dropdown derived its options solely from violation loss_sale_date years,
so a year with trade activity but no detected wash sales (e.g. the current
year on a fresh slate) was missing — the page header still selected it via
today.year, but the user couldn&#39;t pick it from the dropdown. Union trade
years and the current year into the option set, sorted newest-first.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`621fc36`](https://github.com/chen-star/net_alpha/commit/621fc36671c0f168a7ff4d480fe6041fe2e9f31c))


## v0.16.0 (2026-04-26)

### Chore

* chore: ruff format ([`9d7efb5`](https://github.com/chen-star/net_alpha/commit/9d7efb5efbc74385f8731d669f5079aa9034528c))

* chore: refresh gitnexus index stats and sync uv.lock to v0.15.1

- AGENTS.md / CLAUDE.md: gitnexus symbol/relationship/flow counts
  refreshed after the Phase 2 merge (1711 → 2436 symbols).
- uv.lock: wash-alpha version pinned to 0.15.1 to match the
  current pyproject.toml after the semantic-release bump (d5deb1a).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`431e05f`](https://github.com/chen-star/net_alpha/commit/431e05f39ae3f762db02adde98430e1b752050cf))

### Feature

* feat(web): detail page totals bar + group-by-ticker + Lag/Source columns ([`887c676`](https://github.com/chen-star/net_alpha/commit/887c6767ac17d0284177db66f09e28bdaa9677c7))

* feat(web): wire detail summary, ticker grouping, and lag-sort into the route ([`bb2a9b8`](https://github.com/chen-star/net_alpha/commit/bb2a9b8c0f5d39eef19923a628d0dfa06dcd304b))

* feat(portfolio): add detail-page aggregations (summary, grouping, lag, source label) ([`889a422`](https://github.com/chen-star/net_alpha/commit/889a4225158557e010869df0e2fd04e7b3c75723))

* feat(web): POST /sim dispatches BUY/SELL with date and renders new result partials ([`d10180f`](https://github.com/chen-star/net_alpha/commit/d10180f37121c8497ddafe3ce0f049c0c72a7af9))

* feat(web): unified sim form with BUY/SELL toggle and date picker ([`4acd4e0`](https://github.com/chen-star/net_alpha/commit/4acd4e04e3747ba0e8e2e630e253aebe36e0f4a4))

* feat(engine): add simulate_buy() pure function with per-account FIFO loss matching

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`885de0f`](https://github.com/chen-star/net_alpha/commit/885de0f2004353bab348be50132580de06eb49ce))

### Test

* test(web): integration coverage for detail totals, grouping, lag sort, source ([`1c15594`](https://github.com/chen-star/net_alpha/commit/1c15594b5c701665f897bd8d733fc062352c71ad))

* test(web): cover BUY/SELL dispatch on POST /sim with date and account ([`38ebab6`](https://github.com/chen-star/net_alpha/commit/38ebab65dd542a4d56309c16e040a20e7049647c))

* test(engine): add ETF substantially-identical pair tests for simulate_buy ([`bb7d644`](https://github.com/chen-star/net_alpha/commit/bb7d644aeddd037f7f9ebe03f1ead9a517b689b4))

* test(engine): add day-0/30/31 boundary tests for simulate_buy ([`59a883a`](https://github.com/chen-star/net_alpha/commit/59a883a4075d4243b8b03b361f7ddd5c2dbb3c45))

### Unknown

* Merge branch &#39;feat/phase3-sim-and-detail&#39; — Phase 3 sim BUY support + detail enhancements ([`e5ac750`](https://github.com/chen-star/net_alpha/commit/e5ac7503938c6f47450cfa4f51068b7a222a3205))


## v0.15.1 (2026-04-26)

### Feature

* feat(domain): add SimBuyMatch and SimulationBuyOption models ([`d8afe49`](https://github.com/chen-star/net_alpha/commit/d8afe496301ef20a63b7f4f2a4482714a9bbe2f7))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b166af6`](https://github.com/chen-star/net_alpha/commit/b166af6d83a318d434894147c78d585027b1774d))


## v0.15.0 (2026-04-26)

### Chore

* chore: ruff format

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`223b2b8`](https://github.com/chen-star/net_alpha/commit/223b2b8360aaf05d316a21f57ace4de2d5e1ec9c))

### Feature

* feat(web): embed drop zone on imports page

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f6e7a0b`](https://github.com/chen-star/net_alpha/commit/f6e7a0b0e998eb58274e223123c557c99c71a396))

* feat(web): GET /imports/{id}/detail returns expandable detail panel

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7d03ca5`](https://github.com/chen-star/net_alpha/commit/7d03ca5afb701468af474129ddb5dafb8ad8e363))

* feat(web): summary line and expand toggle on imports table

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`492c682`](https://github.com/chen-star/net_alpha/commit/492c68237b282f348a7dcc7b6a4ff0265b0268c2))

* feat(web): compute and persist import aggregates on upload

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`47d7fe8`](https://github.com/chen-star/net_alpha/commit/47d7fe88fc35cdfc2a367d5f9366bc78d034c124))

* feat(db): backfill import aggregates on init_db

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3321bcb`](https://github.com/chen-star/net_alpha/commit/3321bcb68191d1a24da2231c83acdfd5bdd44e2a))

* feat(import): backfill aggregates for legacy import rows

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`068882c`](https://github.com/chen-star/net_alpha/commit/068882c962e48b74e15f1de0dbc8a688f776153a))

* feat(repo): persist and surface import aggregates; add get_import_detail

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1086698`](https://github.com/chen-star/net_alpha/commit/1086698d9f285667c767d9593f79ceba5997200b))

* feat(import): add compute_import_aggregates pure function

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`b8fde73`](https://github.com/chen-star/net_alpha/commit/b8fde7324ab0b55480f0e6d129defd3fd72e79b1))

* feat(models): extend ImportRecord and ImportSummary with v4 aggregate fields

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3fb4e4f`](https://github.com/chen-star/net_alpha/commit/3fb4e4f06aac96c4deb22de91232f9beaf64a71e))

* feat(db): schema v4 — add aggregate columns to imports

Adds 6 nullable columns to the imports table (min/max trade dates,
equity/option/expiry counts, parse warnings JSON) for the calendar
imports Phase 2 backfill. Updates existing migration tests to use
CURRENT_SCHEMA_VERSION instead of hard-coded version literals.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7895223`](https://github.com/chen-star/net_alpha/commit/789522353f5be7f4a7fabcff3211727f2dde6285))

* feat(web): stack monthly P&amp;L ribbon above wash-sale dots

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`877ab57`](https://github.com/chen-star/net_alpha/commit/877ab5786bad699ab769f71f7b6af4ae499cbdb0))

* feat(web): add monthly P&amp;L ribbon partial

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`ddcc096`](https://github.com/chen-star/net_alpha/commit/ddcc0963050b4c6487133561761e9727738e18d1))

* feat(portfolio): add monthly_realized_pl aggregator

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`a12192a`](https://github.com/chen-star/net_alpha/commit/a12192aa05c7599ffb246acf8d41cd56611b9613))

* feat(portfolio): add MonthlyPnl model for calendar ribbon

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`deb2f5f`](https://github.com/chen-star/net_alpha/commit/deb2f5f446493181ac0d8dede10fb56933407bcd))

### Test

* test(db): cover v3 → v4 migration

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`769d491`](https://github.com/chen-star/net_alpha/commit/769d49178b7c135a6bfd977cb05d0c7d5ae7fd90))

* test(portfolio): add Dec-31/Jan-1 boundary case for monthly_realized_pl

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`7718274`](https://github.com/chen-star/net_alpha/commit/77182746d6a1e9d76570d374f80d35143ca5c851))

### Unknown

* Merge branch &#39;feat/calendar-imports-phase2&#39; — Phase 2 calendar dual-ribbon + imports notes

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`6de4f7f`](https://github.com/chen-star/net_alpha/commit/6de4f7fc4bcd16ff15543b0420ce2cba0a2f9e39))


## v0.14.0 (2026-04-26)

### Chore

* chore: sync uv.lock wash-alpha version to 0.13.1 ([`4cd3ef3`](https://github.com/chen-star/net_alpha/commit/4cd3ef3e5a900e459e456610dd687f2dccb1ea38))

* chore: apply ruff format to phase 1 files

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`faa7a6a`](https://github.com/chen-star/net_alpha/commit/faa7a6a915805ebe3fb0b7ef426406a19696ba8f))

* chore(web): remove obsolete dashboard route, templates, and tests ([`01608a4`](https://github.com/chen-star/net_alpha/commit/01608a43ca82b7ee713583e6cb55decfa1a78d9c))

* chore(deps): add yfinance to [ui] extras for portfolio pricing

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`259fe65`](https://github.com/chen-star/net_alpha/commit/259fe651dc4e13c2b6018d1b7337132212ec4b58))

### Documentation

* docs(spec): add UI/UX redesign design (portfolio + calendar + imports + sim + detail)

Three-phase plan: pricing foundation + portfolio rebuild, calendar dual-ribbon
+ imports relocation/notes, sim buy support + detail enhancements. Documents
the no-remote-prices policy relaxation (symbols only, configurable).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`1b66473`](https://github.com/chen-star/net_alpha/commit/1b66473d12a60a5293f133cfe74cf53ba3c091a6))

* docs(claude.md): document price-data privacy + portfolio modules + UI conventions ([`804731a`](https://github.com/chen-star/net_alpha/commit/804731ad1086f1496b0b094aae8a44d8af7e1f28))

* docs(spec): add UI/UX redesign design (portfolio + calendar + imports + sim + detail)

Three-phase plan: pricing foundation + portfolio rebuild, calendar dual-ribbon
+ imports relocation/notes, sim buy support + detail enhancements. Documents
the no-remote-prices policy relaxation (symbols only, configurable).

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`eb5700a`](https://github.com/chen-star/net_alpha/commit/eb5700adca9ee802fc0d1481007ae7ef16e336ec))

### Feature

* feat(web): add &#39;Prices via Yahoo Finance&#39; footer line when remote prices enabled

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d1cfdaa`](https://github.com/chen-star/net_alpha/commit/d1cfdaa6a29e4ba26153ea3a66d5fe0233072516))

* feat(web): treemap, equity curve, wash-impact, lot-aging fragments ([`036ed33`](https://github.com/chen-star/net_alpha/commit/036ed33bbffbeefd535c6619a54ab1dcd2ed6856))

* feat(web): /portfolio/positions fragment + per-symbol table

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4a79442`](https://github.com/chen-star/net_alpha/commit/4a794420a6e904a41bf402ff0f9b17f99eb3756d))

* feat(web): /portfolio/kpis fragment + KPI partial

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`102ab71`](https://github.com/chen-star/net_alpha/commit/102ab7144fb6fcaede347b8cdfdd372d528064fd))

* feat(web): portfolio page shell with HTMX-loaded fragments + empty state

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8851203`](https://github.com/chen-star/net_alpha/commit/8851203e0c0a621abd8bf7e80f4e0806ec917d5f))

* feat(portfolio): compute_wash_impact for portfolio mini-grid

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`56032e5`](https://github.com/chen-star/net_alpha/commit/56032e5f30f43e6808830410333f357fdec3804b))

* feat(portfolio): lot_aging — top-N lots crossing LTCG threshold ([`88d5571`](https://github.com/chen-star/net_alpha/commit/88d557144951c6a073e408a725fb837cc9394116))

* feat(portfolio): equity curve — realized cumulative + present-day point

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`cb383e2`](https://github.com/chen-star/net_alpha/commit/cb383e2ee9831b8a722be53e9344776190f6d161))

* feat(portfolio): slice-and-dice treemap layout

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ea3be67`](https://github.com/chen-star/net_alpha/commit/ea3be6775904dc0c9a6f13d2874d784d82d9c794))

* feat(portfolio): compute_kpis (period + lifetime, account-scoped)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1babe96`](https://github.com/chen-star/net_alpha/commit/1babe966041fe1a8d61ea63b55c1d6325436f932))

* feat(portfolio): compute_open_positions with account/period scoping

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`2ffbfbc`](https://github.com/chen-star/net_alpha/commit/2ffbfbc5c4127fd896b4ed52afe193fa8ddd4088))

* feat(portfolio): view-model dataclasses for positions/KPIs/charts ([`8ab0120`](https://github.com/chen-star/net_alpha/commit/8ab01202af8a9ef534f206dc9698095fbeb130a0))

* feat(web): POST /prices/refresh — invalidate + refetch quotes

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`0b67abf`](https://github.com/chen-star/net_alpha/commit/0b67abfe69baeb92193a2ab375dcd362f9d3a510))

* feat(web): wire PricingService into FastAPI app state and DI

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c5bddeb`](https://github.com/chen-star/net_alpha/commit/c5bddeb0302ab8dca72be1993c8cbee6730337b6))

* feat(pricing): PricingService orchestrating provider + cache

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`c26b74d`](https://github.com/chen-star/net_alpha/commit/c26b74d36dc1ddb0bfee9fbe320cc91b9fbfaa2c))

* feat(pricing): YahooPriceProvider via yfinance + network test marker

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a1d4ff3`](https://github.com/chen-star/net_alpha/commit/a1d4ff34bbb3c7e94a8790337dc3542afac2402e))

* feat(pricing): SQLite-backed PriceCache with TTL + stale detection

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`de48a4d`](https://github.com/chen-star/net_alpha/commit/de48a4d878cd7ea4b8163cb9b537ebdefbb4ad3f))

* feat(pricing): Quote model and PriceProvider ABC

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`27f5010`](https://github.com/chen-star/net_alpha/commit/27f5010436c6a26898ffa34b3cc012551979f905))

* feat(db): schema v3 — add price_cache table for pricing subsystem

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`39f1fa7`](https://github.com/chen-star/net_alpha/commit/39f1fa7e706f55aa53e70cab0d1cd0d96e968c7e))

* feat(config): PricingConfig + YAML loader from ~/.net_alpha/config.yaml

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ab48329`](https://github.com/chen-star/net_alpha/commit/ab4832981164c71c075ed8a34f49960db757adc8))

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

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`540c091`](https://github.com/chen-star/net_alpha/commit/540c09158dfc581602dcc328fa93e61425be7ec0))

### Test

* test(integration): end-to-end portfolio page render with mocked prices

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`763f178`](https://github.com/chen-star/net_alpha/commit/763f17847301a9565ed4303e474e4e3b30a26fb1))

### Unknown

* Merge branch &#39;feat/portfolio-phase1&#39; — Phase 1 portfolio + pricing subsystem ([`f595359`](https://github.com/chen-star/net_alpha/commit/f595359a0ce3da500fecd34fdcfab71509f35621))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`43be6c2`](https://github.com/chen-star/net_alpha/commit/43be6c2f5688e2e225036d4195aaf235f6bb313c))


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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`2cdd8ce`](https://github.com/chen-star/net_alpha/commit/2cdd8ce42d9a913729976f16e9bbd6dba16f902e))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3cc9558`](https://github.com/chen-star/net_alpha/commit/3cc955808608859e1d7be1d7da0489367f9e7bcc))


## v0.12.1 (2026-04-26)

### Chore

* chore: sync uv.lock to v0.12.0 ([`811817c`](https://github.com/chen-star/net_alpha/commit/811817cc7fe5c373fce9362303154e6192f9819a))

* chore: sync uv.lock with v0.11.0 release version bump

After pulling the v0.11.0 release commit, uv sync re-generated the lock
to reflect wash-alpha&#39;s new version.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`2ca03e0`](https://github.com/chen-star/net_alpha/commit/2ca03e01095c7f040289d6e6a5ea1bd2d8d5c059))

### Fix

* fix(web): drop zone — include #csv-input in HTMX request

The drop-zone div is not a &lt;form&gt;, so HTMX did not auto-include the file
input when posting to /imports/preview, causing FastAPI to return 422
Unprocessable Entity (missing &#39;files&#39; field). Adding hx-include=&#34;#csv-input&#34;
explicitly tells HTMX to serialize that input into the request body.

Web tests pass (42/42) — they don&#39;t catch this because they POST directly
without going through HTMX. ([`464408f`](https://github.com/chen-star/net_alpha/commit/464408f722d6baead6358f0adab18349fa6396ed))

### Unknown

* Merge branch &#39;master&#39; of https://github.com/chen-star/net_alpha ([`a6181f4`](https://github.com/chen-star/net_alpha/commit/a6181f4d7e74b50f451023521b0371a9b970dbd8))


## v0.12.0 (2026-04-26)

### Chore

* chore: gitignore private/, drop PRD.md, refresh GitNexus stats, bump uv.lock

- .gitignore: add private/ for local-only Schwab CSVs (not for distribution)
- PRD.md: remove (now superseded by docs/superpowers/specs/)
- AGENTS.md / CLAUDE.md: refresh auto-managed GitNexus stats
- uv.lock: pull in lock churn from feature branch dependencies

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f34f843`](https://github.com/chen-star/net_alpha/commit/f34f8437eaef54deac7f1a4e7f4cf4bbfc6a673e))

* chore(web): rebuild Tailwind CSS for new G/L hydration UI elements

Rebuilt via &#39;npx tailwindcss@3&#39; to capture the new utility classes
introduced by the violation source badges, Schwab lot detail panel,
and imports table G/L lots column. (pytailwindcss 0.1.4 now downloads
a Tailwind v4 binary at runtime, which is incompatible with our v3
config. Using npx pins the v3 tooling explicitly.) ([`27357c2`](https://github.com/chen-star/net_alpha/commit/27357c2e26f83e362377f31789fc7a653a98f93b))

### Feature

* feat(cli): G/L hydration + merge in default import command

CLI accepts mixed Transaction History + Realized G/L files in a single
invocation. Same stitch + merge pipeline as the web UI. Reports
hydration counts and warnings on stdout. Now uses init_db() to ensure
schema migrations run.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`9ce28ad`](https://github.com/chen-star/net_alpha/commit/9ce28ad9c59a681f576640d834f92eb25b09dc63))

* feat(web): show G/L lot count on imports list

ImportSummary gains gl_lot_count. The imports table renders it as a
new column so G/L-only imports are no longer confusing zero-trade rows. ([`4f2b1d7`](https://github.com/chen-star/net_alpha/commit/4f2b1d7d92ec10ffd7102a802dc22840a2ce881d))

* feat(web): Schwab lot detail panel on ticker drilldown

Read-only table showing closed/opened dates, quantity, cost basis,
wash sale flag, and disallowed loss for each G/L lot in this ticker.
Lets users verify our hydrated cost basis against Schwab&#39;s source data.
Hidden when no G/L rows exist for the ticker.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f332cd8`](https://github.com/chen-star/net_alpha/commit/f332cd880f2e60fa4ff63928f7d8a9694fed863b))

* feat(web): violation source badges (Schwab / Cross-account / Engine)

Renders next to the existing confidence pill so the user knows whether
a violation came from Schwab&#39;s 1099-B reporting, engine cross-account
detection, or engine-only substantially-identical inference.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f106827`](https://github.com/chen-star/net_alpha/commit/f106827bebc681f743f283711cb0c4f5af4ea696))

* feat(web): multi-file upload with G/L hydration + merge

Drop zone accepts multiple CSVs (Schwab Transactions, Realized G/L,
or any combination). Per-file detection cards in preview modal.
Upload route runs each file through its parser, then stitch +
detect + merge end-to-end, scoped to the affected ±30-day window.
Flash message reports counts: trades, dups, G/L lots, hydrated sells,
warnings. ([`177d6ba`](https://github.com/chen-star/net_alpha/commit/177d6ba16204cbb092f336a52ce3d525d32042a6))

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

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b56f373`](https://github.com/chen-star/net_alpha/commit/b56f373c9fa450e3455f667b531f6e7481fb32c2))

* feat(engine): stitch — hydrate Sell cost_basis from G/L or FIFO

stitch_account walks every Sell trade in an account and populates
cost_basis from realized_gl_lots (preferred, by symbol+closed_date)
or FIFO buy-lot consumption (fallback). Records basis_source on
each Sell so the UI can surface confidence/source. Returns a
StitchSummary with counts and any quantity-mismatch warnings. ([`3e59740`](https://github.com/chen-star/net_alpha/commit/3e5974090955832ac28c52a91006ac53e532b196))

* feat(brokers): SchwabRealizedGLParser produces RealizedGLLot rows

Recognizes Realized G/L CSV by headers (Symbol, Closed Date, Opened Date,
Quantity, Proceeds, Cost Basis (CB), Wash Sale?). Parses both stock and
option lots, money columns with \$/comma, Yes/No flags, and empty
Disallowed Loss as 0.0. Registered after SchwabParser in the registry.
BrokerParser Protocol relaxed to list[Any] since parsers may emit
different value-object types.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`23e9aa2`](https://github.com/chen-star/net_alpha/commit/23e9aa2940df384aab35173bfec667a8650b6288))

* feat(db): repository methods for G/L lots and stitch helpers

Adds add_gl_lots, get_gl_lots_for_match, get_gl_lots_for_ticker,
get_sells_for_account, get_buys_before_date, update_trade_basis.
Idempotent insert dedups on RealizedGLLot.compute_natural_key().
Trade Pydantic gains basis_source field; round-tripped via repository. ([`c773afa`](https://github.com/chen-star/net_alpha/commit/c773afa199cd388a00460648a5d1871e6c4671fd))

* feat(db): schema v2 — realized_gl_lots table + basis_source/source columns

Adds RealizedGLLotRow table, Trade.basis_source column (default &#39;unknown&#39;),
and WashSaleViolation.source column (default &#39;engine&#39;). Wires
migrate(session) into init_db() so v1 DBs upgrade in place. Migration
is additive and idempotent. ([`bf18031`](https://github.com/chen-star/net_alpha/commit/bf1803186efdf4d2642336a63c8827f3ce662c24))

* feat(models): add RealizedGLLot domain model

Pydantic value object for one tax-lot row from Schwab&#39;s Realized G/L
CSV. Includes Schwab&#39;s per-lot wash sale flag and disallowed loss for
later merge with engine output. compute_natural_key() supports
idempotent dedup on re-imports. ([`578b8c0`](https://github.com/chen-star/net_alpha/commit/578b8c086545dd29c07b1c720202def0bf301daa))

* feat(ingest): smart header detection in load_csv

Skips up to 5 preamble rows (title rows, blank rows) before the real
header row. Required for Schwab Realized G/L CSVs which have a
&#39;Realized Gain/Loss - Lot Details ...&#39; title above the column headers.
Falls back to row 0 when no plausible header row is found, preserving
backwards compat for files that already had headers on row 0. ([`eaf223e`](https://github.com/chen-star/net_alpha/commit/eaf223e238114daa22c31302c3cc2b047ac80669))

### Fix

* fix(db): cascade-delete G/L lots on remove_import + re-stitch

Without this, removing an import that contained G/L data leaves orphan
RealizedGLLotRow rows behind. Subsequent stitch_account calls would
silently hydrate sells using stale cost basis from those orphans,
corrupting wash-sale results.

The web DELETE /imports/{id} route now also runs stitch_account before
re-running detect_in_window, so sells that were hydrated from now-removed
G/L data get demoted to FIFO/unknown as appropriate. ([`e14196e`](https://github.com/chen-star/net_alpha/commit/e14196ef06867d3dc6cbe4a366dbe0adaf09d026))

* fix(db): resolve real trade IDs for Schwab G/L violations

Schwab G/L violations carry synthetic &#39;schwab_gl_&lt;hash&gt;&#39; trade IDs
that can&#39;t be int()-cast for the FK column. _violation_to_row now
detects source=&#39;schwab_g_l&#39; and resolves loss_trade_id by looking
up the matching Sell trade (account+ticker+date). When no matching
Sell trade exists, raises LookupError; replace_violations_in_window
catches and silently skips, supporting G/L-only imports without
Transaction History. ([`9755993`](https://github.com/chen-star/net_alpha/commit/975599397b78de04ee7c306b5d0f164b4cd1b8d8))

* fix(ingest): apply ruff format + clarify load_csv docstring

Address code-review feedback for Task 1:
  - ruff format collapsed implicit string concatenation in tests
    (same lint rule that blocked 79e7763 on master)
  - load_csv docstring references _HEADER_SCAN_LIMIT instead of
    hardcoding the value 5 ([`bb3a557`](https://github.com/chen-star/net_alpha/commit/bb3a5578366ef6cf085452b27131c7c243d24a4f))

### Unknown

* Merge branch &#39;master&#39; of https://github.com/chen-star/net_alpha ([`26ed5ba`](https://github.com/chen-star/net_alpha/commit/26ed5bab42411b79f7eeb009327a47164560386a))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`beaf76c`](https://github.com/chen-star/net_alpha/commit/beaf76cddee4ac90f5388d1004722571f11291eb))


## v0.11.0 (2026-04-26)

### Build

* build(web): tailwind config, source css, and built app.css; add make build-css ([`cb13f90`](https://github.com/chen-star/net_alpha/commit/cb13f90bedecc8a28d9ccda79116734d9ed9feaf))

### Documentation

* docs: document net-alpha ui command + web subsystem in README and CLAUDE.md ([`030acfc`](https://github.com/chen-star/net_alpha/commit/030acfccf28b2f5660dbcce889f454758911da9f))

### Feature

* feat(cli): net-alpha ui command (port picker, uvicorn boot, browser open) ([`08cc044`](https://github.com/chen-star/net_alpha/commit/08cc0446d132b53fb514ad814d547c5d6aba7cbb))

* feat(web): 404/500 handlers render error.html with traceback toggle ([`08d435d`](https://github.com/chen-star/net_alpha/commit/08d435d4d9c181ce84663065dab28dfe42f20414))

* feat(web): GET /ticker/{symbol} drilldown with KPIs, timeline, lots, violations ([`5e57bab`](https://github.com/chen-star/net_alpha/commit/5e57bab84c71d579462d56e97a50f58ef4f34661))

* feat(web): GET /calendar/focus/{id} renders ±30-day strip + violation card ([`48693b8`](https://github.com/chen-star/net_alpha/commit/48693b8bac2e3bb1456b73088df392b2e1ee576a))

* feat(web): GET /calendar with annual ribbon (per-year violation markers) ([`af1ec79`](https://github.com/chen-star/net_alpha/commit/af1ec79e6e7239de092902479d89ed7ac44128a4))

* feat(web): POST /imports/preview + POST /imports for drag-drop upload flow ([`50f3fae`](https://github.com/chen-star/net_alpha/commit/50f3fae5827591c231a29d69fe3325e05cdcd708))

* feat(web): drag-drop zone partial on dashboard with Alpine drag-over highlight ([`03a6363`](https://github.com/chen-star/net_alpha/commit/03a6363a55055dd40dcb08ccd0fcbf17114ffe99))

* feat(web): GET/POST /sim with HTMX-driven per-account result cards ([`66caad0`](https://github.com/chen-star/net_alpha/commit/66caad0b97173328d5d730a4a2123b1d0567c302))

* feat(web): GET /detail page with ticker/account/year/confidence filters ([`8a1e5a4`](https://github.com/chen-star/net_alpha/commit/8a1e5a485a40213175cfe8f576a4d59e2d8b9e53))

* feat(web): DELETE /imports/{id} removes import + recomputes wash sales ([`9037195`](https://github.com/chen-star/net_alpha/commit/9037195e72b61e75eb94718375d8453f322e5a19))

* feat(web): GET /imports management page with HTMX-ready remove button ([`cb1d2f9`](https://github.com/chen-star/net_alpha/commit/cb1d2f9e35324be0e02fa2c362f54c1700e9c3b9))

* feat(web): dashboard route with watch list + YTD KPI cards ([`2a24d82`](https://github.com/chen-star/net_alpha/commit/2a24d8233c782e5e4c6d54e02b773a74d3a248e1))

* feat(db): repository read methods for UI (list_distinct_tickers, get_*_for_ticker) ([`33bd930`](https://github.com/chen-star/net_alpha/commit/33bd930a08ba3445d72725d45d8976dabc4e2acf))

* feat(web): base.html with nav and disclaimer footer; jinja env + etf pairs in app state ([`4c99556`](https://github.com/chen-star/net_alpha/commit/4c99556c8c02a161f667e9ab648f60fa1d76919f))

* feat(web): vendor htmx + alpine static assets, mount /static via StaticFiles ([`ac0f843`](https://github.com/chen-star/net_alpha/commit/ac0f8439e7784bae6ea46ba73b28856d929f41d6))

* feat(web): create web package skeleton with FastAPI app factory ([`3159f4a`](https://github.com/chen-star/net_alpha/commit/3159f4a0cb2a3b4408f316ead0ec687013a7e3dc))

### Fix

* fix(web): correct tailwind palette to match design spec (primary, secondary, accent, bg) ([`ec737d3`](https://github.com/chen-star/net_alpha/commit/ec737d3c02a94b8430c585f01a56a5cc1472313a))

* fix(build): pin pytailwindcss to v3, restore @apply with custom color tokens

Downgrade pytailwindcss to v3.4.1 and restore v3-style CSS with @apply
directives using custom color tokens (primary, secondary, confirmed,
probable, unclear). Manually installed v3 via pytailwindcss.install(),
added safelist for utility classes and component classes to ensure all
needed styles are generated despite no templates yet.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3777561`](https://github.com/chen-star/net_alpha/commit/37775619b3cf973ac16b95becf3103f9746e926e))

### Style

* style: ruff format + import sort across web subsystem ([`30fd46a`](https://github.com/chen-star/net_alpha/commit/30fd46a446f8dc419e8b4d5fcfcf1a8eebf352b4))

### Test

* test(web): add conftest with settings/engine/repo/client fixtures + trade builders ([`881b14c`](https://github.com/chen-star/net_alpha/commit/881b14cdfe68bdfc108f79db2a69cb85a844231a))

### Unknown

* Merge feature/local-ui — local web UI (v2.1)

20-task subagent-driven implementation of the local web UI:
FastAPI + Jinja + HTMX + Alpine + Tailwind v3 (vendored, no node/npm).
Drag-drop CSV import, watch list, YTD KPIs, sim, imports management,
detail, wash-sale calendar (annual ribbon + ±30-day focus), ticker
drilldown, error pages, and the `net-alpha ui` CLI command (port picker,
uvicorn boot, browser open, --port/--no-browser/--reload flags).

187 tests passing, ruff clean.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`07d8d92`](https://github.com/chen-star/net_alpha/commit/07d8d92a220d1a12de4e1a7878c48404798c440d))

* deps(ui): add optional ui group (fastapi, jinja, uvicorn, multipart) + pytailwindcss/httpx for dev ([`9d42901`](https://github.com/chen-star/net_alpha/commit/9d429016cdf19825023ae7ef3e575ee1efaa3d52))


## v0.10.0 (2026-04-25)

### Chore

* chore(deps): drop questionary, anthropic, pydantic-settings, textual; bump to 2.0.0

Runtime dep set is now: pydantic, sqlmodel, typer[all], loguru, pyyaml.
Description reflects the v2 simplified product. config.py migrated from
BaseSettings to plain pydantic BaseModel; LLM-related config fields removed.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7b2752b`](https://github.com/chen-star/net_alpha/commit/7b2752bb2db70a03add7b5b4b4893fa9565ef47b))

* chore(v2): delete legacy import_/, cli/import_cmd, cli/simulate, unused models

v2 surfaces (default + sim + imports + migrate-from-v1) replace all
prior import/check/simulate paths. Repository stubs and unused
Pydantic models follow them out. MetaRepository remains for the
migration boot in cli/app.py.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ceef1c3`](https://github.com/chen-star/net_alpha/commit/ceef1c34da1f833477f15d8c14435401de6cbdf5))

* chore: move etf_pairs.yaml into package, wire loader through CLI

Bundled file now lives at src/net_alpha/etf_pairs.yaml so pip install
ships it. User override at ~/.net_alpha/etf_pairs.yaml extends bundled
pairs (does not replace). Both CLI recompute call sites now use the
real loader instead of an empty dict stub.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`17ad7cb`](https://github.com/chen-star/net_alpha/commit/17ad7cb648fd45bacd32e5333e94bf070994ba3d))

* chore(v2): remove TUI, agent, wizard, and dropped CLI commands

These surfaces are cut in v2. Engine, db, and import_ packages remain
in place pending replacement in later tasks.

SchemaMapping and anonymize_row were inlined into csv_reader.py and
importer.py respectively (both kept), since schema_detection.py and
anonymizer.py were their sole definitions but still consumed by kept modules.
Integration tests for the deleted commands were also removed.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`88d893c`](https://github.com/chen-star/net_alpha/commit/88d893c9cff302cab83e98dade6e53d86a35d7fb))

### Documentation

* docs: rewrite README, CLAUDE.md, AGENTS.md for v2 surface

Remove all v1-era references (AI import, LLM/Anthropic, questionary,
pydantic-settings, textual TUI, wizard, agent, check/report/rebuys
subcommands). Replace with v2 command surface (default import+check,
sim, imports, imports rm, migrate-from-v1) and bundled-Schwab-parser
description throughout.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fa7344c`](https://github.com/chen-star/net_alpha/commit/fa7344cbf0afecc5e9bd90c9bc575527710701bd))

### Feature

* feat(cli): migrate-from-v1 helper (v2.0.x only)

Reads ~/.net_alpha/net_alpha.db (v1 schema) and writes a parallel
v2 DB at ~/.net_alpha/net_alpha.db.v2. User then moves it into
place. Refuses to overwrite an existing v2 file.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ac7ac24`](https://github.com/chen-star/net_alpha/commit/ac7ac24f4489145c7f045804a93c41662ab7beb5))

* feat(cli): v2 surface — default import/check, sim, imports, imports rm

Rewrites app.py with a _FileFirstGroup that routes file-path arguments to
a hidden &#39;run&#39; sub-command, enabling `net-alpha &lt;csv&gt; --account &lt;label&gt;`
as the default entry point alongside explicit `sim` and `imports` sub-commands.
Deletes test_simulate_lots.py (v1 simulate tests superseded by test_app_v2.py).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`973973b`](https://github.com/chen-star/net_alpha/commit/973973bb011007b498a46972e3fdec75efeb323d))

* feat: thread ticker through WashSaleViolation for renderer enrichment

Add ticker field to WashSaleViolation domain model, WashSaleViolationRow
table, detector emission, repository read/write paths, and watch_list
renderer. Removes the hardcoded &#39;TKR&#39; placeholder.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fb90b0e`](https://github.com/chen-star/net_alpha/commit/fb90b0e31e34cde9d8b8f16ae437aba5791295b1))

* feat(output): renderers — disclaimer, watch_list, ytd_impact, sim_result, imports_table, detail

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`09a3697`](https://github.com/chen-star/net_alpha/commit/09a36972a7dab1f602e22ad47249283d10375093))

* feat(brokers): protocol + registry + Schwab parser

Add BrokerParser Protocol, detect_broker registry, and SchwabParser
implementing buy/sell/reinvest/option action parsing for Schwab CSVs.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`121c2ce`](https://github.com/chen-star/net_alpha/commit/121c2ce16c11395e5bdfdad61f16b089c24e3b16))

* feat(ingest): csv_loader, option_parser port, dedup by natural_key

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`57fafea`](https://github.com/chen-star/net_alpha/commit/57fafeab775669521cf36393b9c3366f0df1acbc))

* feat(engine): simulate_sell — cross-account what-if planner

Implements Task 11: simulator.py with FIFO lot consumption, realized P&amp;L,
cross-account wash sale detection, insufficient-shares flagging, and
lookforward_block_until date. 7 new tests; full suite at 215.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`65f8328`](https://github.com/chen-star/net_alpha/commit/65f8328f9d5ebc304e398f6af8bcdc215cbf3d20))

* feat(engine): detect_in_window for incremental recompute

Append new function detect_in_window to detector.py that runs the full
detection algorithm but emits only violations whose loss_sale_date falls
within the supplied window. Caller is responsible for passing trades that
include ±30 days around the window for correct cross-window matching.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`0b12d2c`](https://github.com/chen-star/net_alpha/commit/0b12d2c83e227593777d451a51777d910055947c))

* feat(engine): violations carry loss_account, buy_account, sale/buy dates

Tightens the scaffolded _violation_to_row helper from Task 8 to use
the new typed fields. Wash sale violations now have full provenance
(which accounts, when) needed by the v2 watch list and YTD renderers.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f8b10cc`](https://github.com/chen-star/net_alpha/commit/f8b10cc479ffdf14f1ebb876b050965436e5c9a1))

* feat(db): repository remove_import + replace_violations_in_window

Add three methods to v2 Repository: remove_import (cascading delete of
import/trades/lots/violations + recompute window), replace_violations_in_window
(atomic clear-and-rewrite of violations in date range), and _violation_to_row
(scaffolded with getattr defaults for Task-9 fields loss_account_id,
buy_account_id, loss_sale_date, triggering_buy_date).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`350f8a6`](https://github.com/chen-star/net_alpha/commit/350f8a6c6f933049b5dcabcf66122370918d05c4))

* feat(db): repository reads — trades, lots, violations, windowed

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d5697b5`](https://github.com/chen-star/net_alpha/commit/d5697b5787efff8dde93f146ae70b5219706820f))

* feat(db): add_import with dedup via natural_key UNIQUE constraint

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`4fb5837`](https://github.com/chen-star/net_alpha/commit/4fb583764ed6ccc20d1f265b2980ad78d0f10794))

* feat(db): repository v2 skeleton + account/import management methods

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`96c0cec`](https://github.com/chen-star/net_alpha/commit/96c0cec48acddf1b4d2045ba4af9e2012ebac1a9))

* feat(models): add Trade.compute_natural_key for v2 idempotent imports

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`aa53dd2`](https://github.com/chen-star/net_alpha/commit/aa53dd2237b8c5ee567216df0b5fc5458df6a369))

* feat(db): replace tables with v2 schema (Account, Import, FKs, natural_key)

v1 schema is dropped wholesale. Schema starts at version 1. v1 -&gt; v2
upgrade lives in a separate migrate-from-v1 helper (Task 17).

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`da4992d`](https://github.com/chen-star/net_alpha/commit/da4992dcf53e06b145f3ff0c67d28a40b2508321))

* feat(models): add v2 domain types — Account, ImportRecord, SimulationOption

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e4635a8`](https://github.com/chen-star/net_alpha/commit/e4635a83a7fd8ae12454ff9ba140a857438cd176))

### Fix

* fix(cli,db): persist lots after wash-sale recompute

The default and imports-rm flows were calling detect_in_window then
discarding the result.lots half. As a consequence repo.all_lots() was
always empty and sim reported &#39;no holdings of &lt;ticker&gt;&#39; for any
import. Adds Repository.replace_lots_in_window mirroring the
violations method, and updates both CLI handlers to persist both
halves of the DetectionResult.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`87691bb`](https://github.com/chen-star/net_alpha/commit/87691bbe13657f948801fd07a254f70173bb8440))

* fix(cli,db): tighten violation_to_row session, account annotation, mark TODOs

- repository._violation_to_row now takes the parent session as a
  parameter, matching the row-helper pattern used elsewhere.
- cli/app.py callback&#39;s --account annotation is str | None (was str
  with None default).
- Both etf_pairs={} sites tagged with TODO(Task 16) so the loader
  wire-up isn&#39;t missed.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`3234a50`](https://github.com/chen-star/net_alpha/commit/3234a50fcf5a15e0ebd6904c7971470e26df1c70))

* fix(db): repository violation reads populate full field set

Both all_violations() and violations_for_year() were dropping
loss_sale_date, triggering_buy_date, loss_account, and buy_account
when reconstructing Pydantic WashSaleViolation from the row. This
silently broke watch_list filtering (predicate on triggering_buy_date)
and produced &#39;None ... on None&#39; garbage from --detail.

Also: drop hardcoded &#39;schwab&#39; from sim&#39;s no-such-account message.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7158775`](https://github.com/chen-star/net_alpha/commit/71587752ab4aac2eb4887eafcf1d91de2980cb9c))

* fix(db): consolidate CURRENT_SCHEMA_VERSION; guard removed LLM path

- importer.py: replace SchemaCacheRow LLM branch with explicit
  NotImplementedError so the import path doesn&#39;t crash silently.
- connection.py: import CURRENT_SCHEMA_VERSION from migrations
  (eliminates duplicate constant).
- migrations.py: add scaffolding comment for future schema versions.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f9410c6`](https://github.com/chen-star/net_alpha/commit/f9410c6d244bffecb70708c5c3e456755cc4d4db))

* fix(import_): rename ambiguous &#39;l&#39; var, drop dead _NUMERIC_PATTERN

Both regressions were introduced when inlining anonymizer.py and
schema_detection.py during Task 1. Will be deleted entirely in Task 18,
but fixing now to keep CI green.

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`adb0bc0`](https://github.com/chen-star/net_alpha/commit/adb0bc01d6f36ca9f560be8b5c27819e9f43f2b3))

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

Co-Authored-By: Claude Opus 4.7 (1M context) &lt;noreply@anthropic.com&gt; ([`f17e185`](https://github.com/chen-star/net_alpha/commit/f17e18502721ef2579ff65c02c37f7120421fb3c))


## v0.9.1 (2026-04-19)

### Fix

* fix: resolve all linting and formatting errors to fix failing CI ([`79e7763`](https://github.com/chen-star/net_alpha/commit/79e7763339a88756e56f3d023ef52f10ab10de63))


## v0.9.0 (2026-04-18)

### Chore

* chore: update GitNexus index statistics in documentation files ([`4bce402`](https://github.com/chen-star/net_alpha/commit/4bce4027942a2a6528b10a561623e281045f517a))

### Documentation

* docs: sync PRD commands with current implementation and update GitNexus stats ([`ecdb8ab`](https://github.com/chen-star/net_alpha/commit/ecdb8ab0059f1b3785b3150b0c2d8c72589a0634))

* docs: modernize README and update agent configuration ([`ba80638`](https://github.com/chen-star/net_alpha/commit/ba80638260ddc713c6d625f373a9e906df98c798))

### Feature

* feat(cli): remove eager api key prompt from interactive wizard ([`26f11a5`](https://github.com/chen-star/net_alpha/commit/26f11a5a5d78c30e446d24c7442ee6d5a206af97))

* feat(cli): make API key optional for import command ([`389eb5a`](https://github.com/chen-star/net_alpha/commit/389eb5ac0e58767059d1d41295b5e415b17d2830))

* feat(import): run_import uses hardcoded schema if cache misses and no API key ([`59c7479`](https://github.com/chen-star/net_alpha/commit/59c747925332763fc2c232e97dc94ad7e20cb033))

* feat(import): add hardcoded schemas for schwab and robinhood ([`c0fda74`](https://github.com/chen-star/net_alpha/commit/c0fda74f0aa32d059659b9c22b1fe61ff9069d07))

### Test

* test: update tests to test LLM branch using unknown_broker instead of known brokers ([`9da464c`](https://github.com/chen-star/net_alpha/commit/9da464cce56a1bc08e045fffd82e4c7c7695eda7))


## v0.8.0 (2026-04-18)

### Chore

* chore: add textual dependency for TUI ([`57b6b64`](https://github.com/chen-star/net_alpha/commit/57b6b64fac7faf0232e19c7d01763a220d4b35e3))

* chore: install ui-ux-pro-max-skill for cluade and antigravity ([`f9c8919`](https://github.com/chen-star/net_alpha/commit/f9c8919ac63d12d1129950f318eae6d91686dce4))

### Documentation

* docs: sync architecture, cli, and readme with tui implementation and update model versions ([`188ab91`](https://github.com/chen-star/net_alpha/commit/188ab91971d9fd802ec7be040d5866186a0c8a89))

### Feature

* feat(tui): accurately track and display virtual trade wash sales ([`cd03d50`](https://github.com/chen-star/net_alpha/commit/cd03d5064dfbedec93332e8b52d2faf15fe15d95))

* feat(tui): wire reactive inputs to simulation engine ([`60eef00`](https://github.com/chen-star/net_alpha/commit/60eef0037f30a743cab0bfb69bbc6cf5865fe315))

* feat(tui): add simulation engine helper ([`6322c6c`](https://github.com/chen-star/net_alpha/commit/6322c6c73101dcef351550cd15c1c361d74dc134))

* feat(tui): load and display database trades in DataTable ([`c45cfa0`](https://github.com/chen-star/net_alpha/commit/c45cfa07e86ce5f577a06e7232cdce463e809f44))

* feat(tui): build split-pane dashboard layout ([`e2b4679`](https://github.com/chen-star/net_alpha/commit/e2b46794370f0c7e36d5c25f934424f0f67b59bd))

* feat(tui): scaffold base textual app and cli command ([`ecf5dfe`](https://github.com/chen-star/net_alpha/commit/ecf5dfe606632fc90a130a0fae86a178e7cc7db1))


## v0.7.0 (2026-04-18)

### Chore

* chore: remove tmp_skills from git ([`f8a8545`](https://github.com/chen-star/net_alpha/commit/f8a85450b3902ac712336a5d2cb5b93c76cd12ea))

### Documentation

* docs: fix verification failures and update codebase references

- Resolve gitnexus tool reference failures in CLAUDE.md and AGENTS.md
- Correct CI/CD workflow paths to .github/workflows/ in release plan
- Update CLI test path to integration test location in CLI plan
- Update project name to wash-alpha and fix SchemaCacheRow symbol ([`f8de4e7`](https://github.com/chen-star/net_alpha/commit/f8de4e719ec13ca32c2ccb0b54193ca0b1ddd501))

* docs: update project documentation ([`24dede1`](https://github.com/chen-star/net_alpha/commit/24dede1eff43605c33e8b428104e10a8a02da527))

### Feature

* feat(cli): add interactive wizard mode ([`aa73887`](https://github.com/chen-star/net_alpha/commit/aa7388793404532fdabfa1422e811ac053d5b205))

### Unknown

* merge: synchronize with origin/master and finalize v0.6.0 release ([`e431436`](https://github.com/chen-star/net_alpha/commit/e43143681a8e9f79aed4bac685b8dab0e3d89594))


## v0.6.0 (2026-04-16)

### Documentation

* docs: update PyPI badge to Shields.io and refresh GitNexus index ([`b3ed7af`](https://github.com/chen-star/net_alpha/commit/b3ed7afeeff5150229c9b8868d1cf5f1fc87be1a))

* docs: include design spec and implementation plan for README overhaul ([`52fa57a`](https://github.com/chen-star/net_alpha/commit/52fa57a085da7b1ae825b02fb120a273e540c978))

* docs: add summary for README overhaul plan ([`79ee9e2`](https://github.com/chen-star/net_alpha/commit/79ee9e2a50096f67e1b80fcab0b80f6b8b576575))

* docs: final polish of README overhaul ([`d02bf06`](https://github.com/chen-star/net_alpha/commit/d02bf06fe4187c505d3fa47f21eb9a6b4c789eda))

* docs: add technical deep-dive and privacy section to README ([`bd7cb81`](https://github.com/chen-star/net_alpha/commit/bd7cb81be103889e16eba379bb17032d291b16a1))

* docs: add modern workflow walkthrough to README ([`97a314a`](https://github.com/chen-star/net_alpha/commit/97a314a9dbe9fe1c1971d1b5077939bc1c31eba4))

* docs: add hero header and value prop to README ([`4dd472d`](https://github.com/chen-star/net_alpha/commit/4dd472d38d92c6bae640e6a75265f8ca3196c3bd))

### Feature

* feat: add crypto and common ETF pairs for tax loss harvesting ([`5546b33`](https://github.com/chen-star/net_alpha/commit/5546b3305178448f8c769fb88117671f4c613589))


## v0.5.0 (2026-04-16)

### Chore

* chore: update release script, Makefile, and local lockfile ([`5b31293`](https://github.com/chen-star/net_alpha/commit/5b312937fb9bc0e42dfef80a7f7b871c7ce048d7))

### Ci

* ci: fix automated release and add manual release fallback ([`93a16f6`](https://github.com/chen-star/net_alpha/commit/93a16f6cd6636b2b54441a5dbca18aef854c0192))

### Documentation

* docs: update codecov badge with private token ([`f1b19b2`](https://github.com/chen-star/net_alpha/commit/f1b19b2bc918e30ffcf8343f23b03b8579ad55ee))

### Feature

* feat: enhance README with AI agent and interactive TUI features ([`c0f97cc`](https://github.com/chen-star/net_alpha/commit/c0f97cc2e3fa8c93a62a0af2110077241493a8ac))


## v0.4.2 (2026-04-16)

### Ci

* ci: fix codecov badge and improve upload debugging ([`e2e4f6b`](https://github.com/chen-star/net_alpha/commit/e2e4f6bc949ebc02b70aceaa8b7801a2b83cc2b8))

* ci: remove [skip ci] from release commits to allow workflow triggering ([`2cbe312`](https://github.com/chen-star/net_alpha/commit/2cbe3125964476f9bb207dd14255b07baf74dcfe))

### Fix

* fix: sync internal version and trigger release automation ([`53739f4`](https://github.com/chen-star/net_alpha/commit/53739f445632405cc5e0a944c2f44417dde6cdca))

* fix: trigger release automation verification ([`1c68a14`](https://github.com/chen-star/net_alpha/commit/1c68a149376d6d97ba74a55fd93b87c79704ab28))


## v0.4.1 (2026-04-16)

### Chore

* chore: add MCP config and tax optimization suite plan ([`36b68a3`](https://github.com/chen-star/net_alpha/commit/36b68a34e092608e3f05df758620813b332138a3))

### Fix

* fix: resolve linting and formatting issues to fix CI ([`56e2588`](https://github.com/chen-star/net_alpha/commit/56e2588b69885a2757a348cafc5187e0e5cd3986))


## v0.4.0 (2026-04-16)

### Chore

* chore: update GitNexus metadata and bump version ([`18925c3`](https://github.com/chen-star/net_alpha/commit/18925c3a4036812c1629293e15af9fd4095fcd71))

### Feature

* feat: wire agent command into CLI app and add integration smoke test ([`8688b78`](https://github.com/chen-star/net_alpha/commit/8688b783a0e98b6a70846e944b3fdf9e421afc75))

* feat: add agent REPL with local routing and session-start scan ([`df5bca1`](https://github.com/chen-star/net_alpha/commit/df5bca182ccd5e7584f8772ad96966e1ae6e3c13))

* feat: add ReAct loop for Claude tool-use agent ([`ec3d0a0`](https://github.com/chen-star/net_alpha/commit/ec3d0a00258a09fafc70836530458084b18cca2d))

* feat: add agent system prompt assembly ([`84494a6`](https://github.com/chen-star/net_alpha/commit/84494a63b1a21b40a4318fe8fb6eda0cb78d5a31))

* feat: add agent tool executors and Claude tool schemas ([`9356288`](https://github.com/chen-star/net_alpha/commit/9356288660a881225382d6caf206ca17d5233d3a))

* feat: add agent_api_key, agent_model, resolved_agent_api_key to Settings ([`3293bc4`](https://github.com/chen-star/net_alpha/commit/3293bc45a52029c3a06b5c19bad60dfd44e87129))


## v0.3.0 (2026-04-16)

### Feature

* feat: show example values in schema confirmation and add post-import nudge ([`a74b75c`](https://github.com/chen-star/net_alpha/commit/a74b75c52dd88a4398b2c4f56033e9b8fedb50d8))

* feat: add broker autocomplete and what-to-do-next panel to wizard ([`91a3141`](https://github.com/chen-star/net_alpha/commit/91a3141e831efd1f71b562565b82a5c2f8dc5f23))

* feat: add ticker validation with close-match suggestion to simulate sell ([`146c0b9`](https://github.com/chen-star/net_alpha/commit/146c0b9995308400a8fa458a3fe06e5c12f3061e))

* feat: add --quiet flag to report command ([`9c71723`](https://github.com/chen-star/net_alpha/commit/9c717232ae14c278331c33cb9f04ad373ebfde18))

* feat: add --quiet flag, --type validation, hints, and last_check_at to check command ([`a1e5992`](https://github.com/chen-star/net_alpha/commit/a1e5992b14fabcbed96a688579907d065c97b7c4))

* feat: add urgency coloring and cross-command hint to rebuys ([`ba34bbb`](https://github.com/chen-star/net_alpha/commit/ba34bbbcf40d6f9fd3ca1fe57bc78a51365ae37d))

* feat: color-code tax-position monetary values and add cross-command hint ([`c819312`](https://github.com/chen-star/net_alpha/commit/c819312682caf189559b01e4b092728c2a6a9e61))

* feat: add progress spinners to check, report, and import commands ([`63a00d8`](https://github.com/chen-star/net_alpha/commit/63a00d8877f59079b9b206f0fb3edcf476345fca))

* feat: add net-alpha status dashboard command ([`ebdc415`](https://github.com/chen-star/net_alpha/commit/ebdc4159215eb2e3bc45327af4c0a21ff4433456))

* feat: add MetaRepository for reading and writing meta key-value pairs ([`56864bb`](https://github.com/chen-star/net_alpha/commit/56864bb673f044c45fd9f7be2f2a767cff32d8ef))

* feat: add print_hint and format_currency_colored output helpers

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`a376f45`](https://github.com/chen-star/net_alpha/commit/a376f45b1a9249f38b2e1cfa185d0b693c9920e6))

### Style

* style: normalize error message formatting across CLI commands ([`557b672`](https://github.com/chen-star/net_alpha/commit/557b672fc2859b1b73ee92f32582a8bcee84c1e7))


## v0.2.0 (2026-04-15)

### Feature

* feat: enhance simulate sell with lot selection comparison

When --price is given, shows FIFO/HIFO/LIFO comparison table with
ST/LT gain/loss split, wash sale risk flags, and tax-aware
recommendation. Reuses existing wash sale check logic. ([`590cb5b`](https://github.com/chen-star/net_alpha/commit/590cb5bf167ed0589fdf9203902da0bfb19754f1))

* feat: add tax-position CLI command

Shows YTD realized ST/LT gains and losses, net capital position,
loss-to-zero-st, carryforward, and open lots with holding period
tracker. Sorted by days-to-long-term ascending. ([`2393ce0`](https://github.com/chen-star/net_alpha/commit/2393ce02cb1bb6c55df2085bc1415bd3e59011c9))

* feat: implement tax position engine (Tasks 3-8)

- _allocate_lots: per-(account,ticker) FIFO with realized pairs + open lots
- compute_tax_position: YTD ST/LT aggregation, year-filtered, basis_unknown counted
- identify_open_lots: sorted by days_to_long_term asc, LT lots last
- select_lots: FIFO/HIFO/LIFO across accounts with ST/LT split
- recommend_lot_method: rule-based decision tree with wash risk + fallback
- 42 tests covering all edge cases: boundaries, per-account isolation,
  basis_unknown, option exclusion, holding period, tiebreaks ([`9b5d774`](https://github.com/chen-star/net_alpha/commit/9b5d774ed7edc4e957dc9c82d0c94fd775ce9274))

* feat: add OpenLotFactory and RealizedPairFactory test fixtures ([`b98443a`](https://github.com/chen-star/net_alpha/commit/b98443a192b644476dae1b2f4ae5d0854b5b4599))

* feat: add domain models for tax optimization suite

Add TaxPosition, OpenLot, LotSelection, LotRecommendation,
AllocationResult, and RealizedPair to models/domain.py.
Includes computed properties for net_st, net_lt, net_capital_gain,
loss_needed_to_zero_st, and carryforward ($3,000 cap). ([`10b93c7`](https://github.com/chen-star/net_alpha/commit/10b93c78447618345787bf92449e7f1382585657))

### Style

* style: fix lint and formatting for tax optimization suite ([`4302adc`](https://github.com/chen-star/net_alpha/commit/4302adca872a248b38feb67d9e8db763c461a41f))

### Test

* test: fix lint and add missing tests for domain models

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`7acd573`](https://github.com/chen-star/net_alpha/commit/7acd57373a61e799cc01b2645498ee6843f35a6e))


## v0.1.3 (2026-04-14)

### Fix

* fix: remove unused imports and fix import ordering in test files

Fixes CI lint failures (F401 unused imports, I001 unsorted imports) and
reformats all files to match ruff format standards.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`fde1085`](https://github.com/chen-star/net_alpha/commit/fde108584d18039bb2e2cd38d3d4771b7515172e))

### Unknown

* Update gitnexus index. ([`97cb253`](https://github.com/chen-star/net_alpha/commit/97cb253837342447ab09752d55607eb5d4648d24))


## v0.1.2 (2026-04-14)

### Chore

* chore: update GitNexus index stats ([`bcd9de8`](https://github.com/chen-star/net_alpha/commit/bcd9de82767c8bdce3006db5295f2c546dfcf5e3))

### Fix

* fix: set line-length to 120 and fix remaining lint errors ([`6abcae6`](https://github.com/chen-star/net_alpha/commit/6abcae62cd7ef5be20418ff8ef28d6eed330e24d))

* fix: use --extra dev to install optional dev dependencies in CI ([`deef5b9`](https://github.com/chen-star/net_alpha/commit/deef5b94b11a120cb6c30a18b3c44fddd8aaef53))


## v0.1.1 (2026-04-14)


## v0.1.0 (2026-04-14)

### Chore

* chore: rename PyPI package to wash-alpha ([`7189777`](https://github.com/chen-star/net_alpha/commit/7189777bcac4ee6a8351de7f7afddc795df2b3cb))

* chore: add python-semantic-release config ([`62c3a91`](https://github.com/chen-star/net_alpha/commit/62c3a9198e4d17cade4b6c8e5e8326436020c769))

* chore: add .gitignore with worktrees and Python artifacts ([`c77363c`](https://github.com/chen-star/net_alpha/commit/c77363c3dafad828c893b8c3af2e51dad26d8f32))

### Ci

* ci: add explicit tag push step; gate codecov upload to py3.11 ([`40c582f`](https://github.com/chen-star/net_alpha/commit/40c582fc5c5927d68b3a9fd26b46a8869f6c6d11))

* ci: add release workflow (hatch build, PyPI OIDC publish, GitHub Release) ([`617ec50`](https://github.com/chen-star/net_alpha/commit/617ec50c4a7885be7bf65e1580260ebec924d311))

* ci: pin python-semantic-release to v8 range ([`47eab42`](https://github.com/chen-star/net_alpha/commit/47eab4224f0bdab87e269bbdf376ec3add7009e5))

* ci: add version bump workflow (conventional commits + manual override) ([`ecf4d8c`](https://github.com/chen-star/net_alpha/commit/ecf4d8cb556eb739f64a71648e4219d2a7f0baee))

* ci: add CI workflow (lint, test, coverage on push/PR/nightly) ([`4f54c9b`](https://github.com/chen-star/net_alpha/commit/4f54c9bc8b2c8206b928b25ba04cd1740c6dc1b1))

### Documentation

* docs: add CI, PyPI, and coverage badges to README ([`c19d0fd`](https://github.com/chen-star/net_alpha/commit/c19d0fd8c87340c3abf89a57eb9ef889f74c9daa))

### Feature

* feat: add first-run interactive wizard

Implements the interactive wizard that runs on first launch, prompting
for an Anthropic API key, importing broker CSVs, and running an initial
wash sale check.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`1f3f191`](https://github.com/chen-star/net_alpha/commit/1f3f191b91c9e52e5515c9b02751e766ae5afc74))

* feat: add annual wash sale report command with CSV export

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`8ca38b6`](https://github.com/chen-star/net_alpha/commit/8ca38b686990a726e57c0e50aa456a80793eece0))

* feat: add safe-to-rebuy tracker command ([`25ee889`](https://github.com/chen-star/net_alpha/commit/25ee88958efd09fb8a5271bb8f5acb0a34c8078d))

* feat: add simulate sell command with look-back detection

Adds `net-alpha simulate sell &lt;ticker&gt; &lt;qty&gt; [--price P]` that checks
the 30-day look-back window for existing buys that would trigger a wash
sale, shows the triggering trade with confidence label and safe-to-sell
date, and estimates the disallowed loss when a price is provided.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`3d3a0af`](https://github.com/chen-star/net_alpha/commit/3d3a0afb82a50a3928dda83d43d5e4e8f086a587))

* feat: add check command with summary, detail, and staleness warnings

Implements `net-alpha check` with year/ticker/type filtering, per-account
staleness warnings, wash sale summary table, violation detail table,
rebuy hint, and basis-unknown/option-expiration caveats.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`65466a2`](https://github.com/chen-star/net_alpha/commit/65466a2d0b247d6ec8e860e38b2f84db041a7031))

* feat: add CSV import command with schema confirmation ([`e24fb59`](https://github.com/chen-star/net_alpha/commit/e24fb59408fd3a0b732df3eac73ddbde01c1ef16))

* feat: add Typer app entry point with DB bootstrap ([`12591e9`](https://github.com/chen-star/net_alpha/commit/12591e90ee95f7599d9425e5417e50e166a3149a))

* feat: add CLI output helpers and disclaimer ([`ba743ed`](https://github.com/chen-star/net_alpha/commit/ba743ed1287fd9f8325da0e73b00d88e90061e1d))

* feat: add main import orchestrator

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`88acb60`](https://github.com/chen-star/net_alpha/commit/88acb60a87c5dff65f5e1b6952b32a11967bbc59))

* feat: add trade deduplication with hash and semantic key signals

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`040eca4`](https://github.com/chen-star/net_alpha/commit/040eca4d5cf3b1731039c942e190de4180371457))

* feat: add CSV reader with schema mapping and option parsing

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b144405`](https://github.com/chen-star/net_alpha/commit/b14440574d118ea01d1b1c19bc481f0e689483c3))

* feat: add LLM schema detection with retry and exponential backoff

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d5156b1`](https://github.com/chen-star/net_alpha/commit/d5156b15724af9e1346a99bc1016660117946971))

* feat: add option symbol regex parsers (OCC, Schwab, Robinhood)

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`d48a098`](https://github.com/chen-star/net_alpha/commit/d48a098af9a509e6e7b4ed9f04fae6bff2bccd0e))

* feat: add row anonymizer for LLM schema detection

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`553d46b`](https://github.com/chen-star/net_alpha/commit/553d46b6ec548354d6df182a6a68d46a859109d0))

* feat: add repositories with domain ↔ table mapping

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`18e1bf5`](https://github.com/chen-star/net_alpha/commit/18e1bf5ee41d5f8a3cd0597bcaae235202fda403))

* feat: add schema migration framework with v0→v1

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`b3ef87f`](https://github.com/chen-star/net_alpha/commit/b3ef87fcdb7cc578b3d5f638f8743c10bda5c6f2))

* feat: add DB connection and init with schema versioning

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`e3ed6a1`](https://github.com/chen-star/net_alpha/commit/e3ed6a15f417d729391a470e4afdebf344bb7a34))

* feat: add SQLModel table classes for all entities

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`96af8a7`](https://github.com/chen-star/net_alpha/commit/96af8a7392a637b822a019c3c97d334ee71bebc7))

* feat: add Settings config via pydantic-settings

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`ec96913`](https://github.com/chen-star/net_alpha/commit/ec969132973f985e7b30dc78171e4fcfa2d227c2))

* feat: implement core wash sale detection engine ([`21e590e`](https://github.com/chen-star/net_alpha/commit/21e590eb09101c58126a5b1ca36b9e034f9c7429))

* feat: add ETF pairs loader with user override support ([`aa33a91`](https://github.com/chen-star/net_alpha/commit/aa33a912dc53f87d8698f6cd1d7ad240f6902b57))

* feat: implement equity match confidence with ETF pair support

- Add get_match_confidence for all equity/option/ETF scenarios
- Tests cover confirmed, probable, unclear, and no-match cases ([`d94c022`](https://github.com/chen-star/net_alpha/commit/d94c02258dd2ea1ca35ab290e2e62139c4d034ef))

* feat: implement 30-day wash sale window check ([`0d16b00`](https://github.com/chen-star/net_alpha/commit/0d16b0037127f69993b95a6b4186d19115ea8d9b))

* feat: add factory_boy test fixtures for Trade and Lot ([`2942c0d`](https://github.com/chen-star/net_alpha/commit/2942c0ddcf32d101c650ccb123190fab73ea4073))

* feat: add Lot, WashSaleViolation, and DetectionResult models ([`6c88d0a`](https://github.com/chen-star/net_alpha/commit/6c88d0a4ba7ae9f072775009c55866138166badc))

* feat: add Trade and OptionDetails domain models ([`77cb8cd`](https://github.com/chen-star/net_alpha/commit/77cb8cd87873d554a4eca415e0da2898c8531d9d))

* feat: initialize project structure with uv and hatch ([`c370488`](https://github.com/chen-star/net_alpha/commit/c3704880f9ede0833229a2edc825bbe3b85ebabb))

### Fix

* fix: resolve ruff linter warnings in Plan 1 source files

Replace Optional[X] with X | None, fix line-length violations,
and clean up unused imports across domain model, matcher, and tests.

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`25d778d`](https://github.com/chen-star/net_alpha/commit/25d778de009d04d9fb8935f85571fd3534f2b1dd))

### Test

* test: complete integration test suite — CLI and engine tiers ([`0c8a5dd`](https://github.com/chen-star/net_alpha/commit/0c8a5dd6942a6bc7cd808b5195952ce891ee6000))

* test: add CLI integration tests for report command ([`bd4223e`](https://github.com/chen-star/net_alpha/commit/bd4223e1c4c9b1961afd068dbeff7b9ea156b0dd))

* test: add CLI integration tests for rebuys command ([`ef484fa`](https://github.com/chen-star/net_alpha/commit/ef484fa8883754ba2e747d3c6a97231de564e30e))

* test: add CLI integration tests for simulate sell command ([`9c99f5f`](https://github.com/chen-star/net_alpha/commit/9c99f5fdd20b6a911308ebf1dd930de69b327472))

* test: add CLI integration tests for check command ([`f3a9012`](https://github.com/chen-star/net_alpha/commit/f3a9012f47247a02c573e424f330902f3d05c70f))

* test: add CLI integration tests for import command ([`2416c11`](https://github.com/chen-star/net_alpha/commit/2416c119de4cf61d070f1ea8375d0b8ec299b71b))

* test: add engine integration tests for wash sale detector ([`68e22ac`](https://github.com/chen-star/net_alpha/commit/68e22acf4c859802746ace0a8deda9a9827d9682))

* test: add engine integration tests for import pipeline ([`ffc49aa`](https://github.com/chen-star/net_alpha/commit/ffc49aab1ce17dce6dcd66f8a19783e8ffdbbea0))

* test: add engine integration tests for import pipeline

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`45ed76d`](https://github.com/chen-star/net_alpha/commit/45ed76de64d10281d6b88aac867b9c4ef716f4f3))

* test: add CLI integration conftest with patched _bootstrap ([`5f6e4e3`](https://github.com/chen-star/net_alpha/commit/5f6e4e310912321f5c189cd12d5576e9fe91e774))

* test: scaffold integration test directory and shared conftest ([`7ebd6ac`](https://github.com/chen-star/net_alpha/commit/7ebd6ac53f843e1a30c6570eae38e26c79fde66a))

* test: add golden file integration tests for Schwab and Robinhood CSV

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`f7a36ee`](https://github.com/chen-star/net_alpha/commit/f7a36ee12870164cbdec583c5aab6cc714a6d9da))

* test: add Lot, Violation, and SchemaCache repository tests

Co-Authored-By: Claude Sonnet 4.6 &lt;noreply@anthropic.com&gt; ([`645eb69`](https://github.com/chen-star/net_alpha/commit/645eb6956e4ce192cbbcfc28e1f3612e6f4d308e))

* test: options and ETF wash sale detection scenarios ([`4f9240b`](https://github.com/chen-star/net_alpha/commit/4f9240be4675fbf9a873eb2f75bb66e997aa1ecc))

* test: cross-account, cross-year, basis_unknown, and edge cases ([`d42cb0c`](https://github.com/chen-star/net_alpha/commit/d42cb0c9f1328ad4dc5ac8096d508512182bac7f))

* test: FIFO allocation, partial wash sales, and basis adjustment ([`a902aff`](https://github.com/chen-star/net_alpha/commit/a902aff5317dfb877821cf8b764a858ff6a10c9b))

### Unknown

* Delete liscense in README.md. ([`bbb78b5`](https://github.com/chen-star/net_alpha/commit/bbb78b5ff83232959391d3ac499da8713d9cce31))

* Add README.md. ([`d5152b5`](https://github.com/chen-star/net_alpha/commit/d5152b503a7385b81c5dffd9d5aeb7c94c0e40c7))

* Enable gitnexus ([`f127792`](https://github.com/chen-star/net_alpha/commit/f1277921a8e405b3e5c811c448d541b09f804eb0))

* Add v1 plan ([`2ed4e10`](https://github.com/chen-star/net_alpha/commit/2ed4e10bb1069412bc7a2e7cddb749316c5f15c7))

* Add spec for v1. ([`255a26c`](https://github.com/chen-star/net_alpha/commit/255a26c660fd00aca9799c67ba396ba9a574f59d))

* init PRD.md ([`9d87db8`](https://github.com/chen-star/net_alpha/commit/9d87db828384b6b034d80650111d1fb9a84e1bb3))
