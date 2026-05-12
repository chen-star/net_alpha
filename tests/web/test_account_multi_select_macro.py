from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = "src/net_alpha/web/templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )


def _render(accounts_available: list[str], accounts_selected: list[str]) -> str:
    env = _env()
    tpl = env.from_string(
        '{% import "_account_multi_select.html" as m %}'
        "{{ m.account_multi_select(accounts_available, accounts_selected) }}"
    )
    return tpl.render(
        accounts_available=accounts_available,
        accounts_selected=accounts_selected,
    )


def test_renders_button_with_all_accounts_label_when_none_selected():
    html = _render(["Schwab/Personal", "Fidelity/Roth"], [])
    assert "All accounts" in html
    assert 'name="account"' in html
    # Both account checkboxes present, plus the master toggle = 3 checkboxes
    assert html.count('type="checkbox"') == 3


def test_renders_single_account_label_when_one_selected():
    html = _render(["Schwab/Personal", "Fidelity/Roth"], ["Schwab/Personal"])
    assert "Schwab/Personal" in html
    assert "checked" in html


def test_renders_count_label_when_two_or_more_selected():
    html = _render(
        ["Schwab/Personal", "Fidelity/Roth", "Fidelity/HSA"],
        ["Schwab/Personal", "Fidelity/Roth"],
    )
    assert "2 of 3 accounts" in html


def test_emits_hidden_checkbox_inputs_named_account():
    html = _render(["A", "B"], ["A"])
    assert 'name="account" value="A"' in html
    assert 'name="account" value="B"' in html
