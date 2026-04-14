# CHANGELOG



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
