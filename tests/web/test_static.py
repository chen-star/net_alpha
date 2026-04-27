def test_static_htmx_served(client):
    resp = client.get("/static/htmx.min.js")
    assert resp.status_code == 200
    assert "htmx" in resp.text.lower()


def test_static_alpine_served(client):
    resp = client.get("/static/alpine.min.js")
    assert resp.status_code == 200
    assert "alpine" in resp.text.lower() or "x-data" in resp.text


def test_static_app_css_served(client):
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert "tailwind" in resp.text.lower() or "--tw-" in resp.text


def test_static_apexcharts_js_served(client):
    resp = client.get("/static/vendor/apexcharts/apexcharts.min.js")
    assert resp.status_code == 200
    assert "apexcharts" in resp.text.lower() or "apexcharts" in resp.text


def test_static_apexcharts_css_served(client):
    resp = client.get("/static/vendor/apexcharts/apexcharts.min.css")
    assert resp.status_code == 200


def test_static_charts_js_served(client):
    resp = client.get("/static/charts.js")
    assert resp.status_code == 200
    assert "netAlphaChartTheme" in resp.text
