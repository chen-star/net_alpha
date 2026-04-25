def render(violations, year: int) -> str:
    if not violations:
        return f"YEAR-TO-DATE IMPACT\n{'─' * 19}\nNo wash sales detected in {year}."

    total = sum(v.disallowed_loss for v in violations)
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.confidence] = counts.get(v.confidence, 0) + 1
    breakdown = ", ".join(f"{n} {c}" for c, n in counts.items())
    return (
        f"YEAR-TO-DATE IMPACT\n{'─' * 19}\n"
        f"${total:,.0f} disallowed across {len(violations)} wash sales ({breakdown}) — {year}"
    )
