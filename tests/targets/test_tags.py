from net_alpha.targets.tags import normalize_tag, normalize_tags


def test_normalize_lowercases_and_trims():
    assert normalize_tag("  Core  ") == "core"


def test_normalize_collapses_internal_whitespace():
    assert normalize_tag("long hold") == "long-hold"
    assert normalize_tag("a   b\tc") == "a-b-c"


def test_normalize_allows_alnum_underscore_hyphen():
    assert normalize_tag("a-b_c1") == "a-b_c1"


def test_normalize_rejects_empty():
    assert normalize_tag("") is None
    assert normalize_tag("   ") is None


def test_normalize_rejects_reserved():
    assert normalize_tag("untagged") is None
    assert normalize_tag(" UNTAGGED ") is None  # case-insensitive


def test_normalize_rejects_leading_underscore_or_hyphen():
    assert normalize_tag("_core") is None
    assert normalize_tag("-core") is None


def test_normalize_allows_leading_digit():
    assert normalize_tag("2026") == "2026"


def test_normalize_rejects_too_long():
    assert normalize_tag("a" * 24) == "a" * 24  # boundary OK
    assert normalize_tag("a" * 25) is None      # over


def test_normalize_rejects_unicode():
    assert normalize_tag("café") is None
    assert normalize_tag("核心") is None


def test_normalize_rejects_special_chars():
    assert normalize_tag("a!b") is None
    assert normalize_tag("a/b") is None
    assert normalize_tag("a.b") is None


def test_normalize_tags_dedups_and_sorts():
    assert normalize_tags(["B", "a", "B", "core"]) == ("a", "b", "core")


def test_normalize_tags_drops_invalid_silently():
    # Caller pre-validates individually; the bulk helper just filters Nones.
    assert normalize_tags(["core", "", "untagged", "income"]) == ("core", "income")


def test_normalize_tags_empty_input():
    assert normalize_tags([]) == ()
