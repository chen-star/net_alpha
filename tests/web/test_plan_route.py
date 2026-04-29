from fastapi.testclient import TestClient


def test_plan_tab_link_in_tabs(client: TestClient):
    r = client.get("/positions?view=all")
    assert r.status_code == 200
    assert 'href="/positions?view=plan' in r.text
    assert ">Plan</a>" in r.text or "Plan</a>" in r.text


def test_plan_tab_renders_empty_state_when_no_targets(client: TestClient):
    r = client.get("/positions?view=plan")
    assert r.status_code == 200
    assert "No targets yet" in r.text
