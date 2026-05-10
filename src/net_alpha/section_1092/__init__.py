"""§1092 straddle awareness — same-underlying offsetting detection,
qualified covered call test, and holding-period suspension warnings.

v1 scope:
- 🟢-tier same-underlying offsetting detection (literal straddles,
  married puts, covered calls, vertical spreads).
- Qualified Covered Call test per §1092(c)(4) (approximation; see qcc.py).
- Holding-period suspension warnings per §1092(f) (no basis math).

Out of scope (v2): loss deferral, modified wash sale (§1092(b)),
identified-straddle elections, correlation-based stock/ETF offsetting.
"""
