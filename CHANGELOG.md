# CHANGELOG



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
