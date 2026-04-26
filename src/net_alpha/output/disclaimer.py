def render() -> str:
    return "⚠ This is informational only. Consult a tax professional before filing."


def price_source_line(source: str | None = "Yahoo Finance") -> str:
    if not source:
        return ""
    return f"Prices via {source}, ~15 min delayed."
