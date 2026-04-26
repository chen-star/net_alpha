import socket

import pytest


def test_pick_free_port_returns_open_port():
    from net_alpha.cli.ui import pick_free_port

    port = pick_free_port(8765, 8775)
    assert 8765 <= port <= 8775
    s = socket.socket()
    s.bind(("127.0.0.1", port))
    s.close()


def test_pick_free_port_skips_busy_ports():
    from net_alpha.cli.ui import pick_free_port

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 8765))
    s.listen(1)
    try:
        port = pick_free_port(8765, 8775)
        assert port != 8765
    finally:
        s.close()


def test_pick_free_port_raises_when_range_exhausted():
    from net_alpha.cli.ui import pick_free_port

    sockets = []
    try:
        for p in range(9000, 9003):
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", p))
            s.listen(1)
            sockets.append(s)
        with pytest.raises(RuntimeError, match="ports in use"):
            pick_free_port(9000, 9002)
    finally:
        for s in sockets:
            s.close()
