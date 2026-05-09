from net_alpha.service import wrapper


def test_render_starts_with_shebang():
    text = wrapper.render(
        binary="/usr/local/bin/net-alpha",
        sandbox_profile="/u/.net_alpha/run/sandbox.sb",
        disabled_flag="/u/.net_alpha/run/disabled",
    )
    assert text.startswith("#!/bin/bash\n")


def test_render_short_circuits_on_disabled_flag():
    text = wrapper.render(
        binary="/b",
        sandbox_profile="/s",
        disabled_flag="/u/.net_alpha/run/disabled",
    )
    # Wrapper checks for the flag and exits 0
    assert 'if [ -f "/u/.net_alpha/run/disabled" ]' in text
    assert "exit 0" in text


def test_render_invokes_sandbox_exec():
    text = wrapper.render(
        binary="/u/bin/net-alpha",
        sandbox_profile="/u/.net_alpha/run/sandbox.sb",
        disabled_flag="/d",
    )
    assert 'sandbox-exec -f "/u/.net_alpha/run/sandbox.sb"' in text
    assert '"/u/bin/net-alpha" service run' in text


def test_render_uses_strict_mode():
    text = wrapper.render(binary="/b", sandbox_profile="/s", disabled_flag="/d")
    assert "set -euo pipefail" in text
