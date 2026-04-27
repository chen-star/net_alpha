"""Stock-split application — mutate regenerated lots based on the splits
table and record an audit trail in lot_overrides.

Intended call site: as the final step of recompute_all_violations, after
detect_in_window has produced fresh lots and they've been persisted via
replace_lots_in_window. Idempotent — safe to call repeatedly.
"""
