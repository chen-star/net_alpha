def render(summaries) -> str:
    if not summaries:
        return "(no imports)"
    lines = [f"{'id':>3} {'account':<20} {'file':<30} {'trades':>7}  imported"]
    lines.append("-" * 70)
    for s in summaries:
        lines.append(
            f"{s.id:>3} {s.account_display:<20} {s.csv_filename:<30} {s.trade_count:>7}  {s.imported_at.date()}"
        )
    return "\n".join(lines)
