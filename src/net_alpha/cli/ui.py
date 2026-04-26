from __future__ import annotations

import socket
import webbrowser

import typer
import uvicorn

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def pick_free_port(start: int = 8765, end: int = 8775) -> int:
    """Return the first free port in [start, end] on localhost.

    Raises RuntimeError if all ports are in use.
    """
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"All ports in use ({start}-{end}) — pass --port explicitly.")


def run(
    port: int | None = None,
    no_browser: bool = False,
    reload: bool = False,
) -> int:
    """Boot the local UI server. Blocks until SIGINT."""
    settings = Settings()
    chosen_port = port or pick_free_port()
    url = f"http://127.0.0.1:{chosen_port}"

    typer.echo(f"net-alpha ui — {url}")
    typer.echo("Press Ctrl-C to stop.")

    if not no_browser:
        webbrowser.open(url)

    if reload:
        uvicorn.run(
            "net_alpha.web.app:create_app",
            host="127.0.0.1",
            port=chosen_port,
            reload=True,
            factory=True,
        )
    else:
        app = create_app(settings)
        uvicorn.run(app, host="127.0.0.1", port=chosen_port, log_level="info")
    return 0
