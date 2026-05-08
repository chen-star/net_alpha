from net_alpha.service import sandbox


def test_render_starts_with_version():
    text = sandbox.render(net_alpha_home="/u/.net_alpha", port=8765)
    assert text.startswith("(version 1)")


def test_render_denies_default():
    text = sandbox.render(net_alpha_home="/u/.net_alpha", port=8765)
    assert "(deny default)" in text


def test_render_allows_writes_only_to_net_alpha_home():
    text = sandbox.render(net_alpha_home="/u/.net_alpha", port=8765)
    assert "(allow file-write*" in text
    assert '(subpath "/u/.net_alpha")' in text


def test_render_allows_loopback_bind_on_pinned_port():
    text = sandbox.render(net_alpha_home="/u/.net_alpha", port=8765)
    assert "(allow network-bind" in text
    assert '"127.0.0.1:8765"' in text


def test_render_permissive_outbound_443():
    text = sandbox.render(net_alpha_home="/u/.net_alpha", port=8765)
    assert "(allow network-outbound" in text
    assert "*:443" in text


def test_render_documents_reasoning_inline():
    text = sandbox.render(net_alpha_home="/u/.net_alpha", port=8765)
    # Comment explains the permissive *:443 (yfinance CDN rotation)
    assert "yfinance" in text.lower() or "yahoo" in text.lower()
