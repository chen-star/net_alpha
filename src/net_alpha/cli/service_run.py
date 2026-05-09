"""`net-alpha service run` — the long-running entry-point launchd invokes."""

from __future__ import annotations

import uvicorn

from net_alpha.service import lock


def run(*, port: int = 8765) -> None:
    """Start the FastAPI app under uvicorn. Holds the pid lock for its lifetime."""
    lock.acquire()
    try:
        uvicorn.run(
            "net_alpha.web.app:create_app",
            host="127.0.0.1",
            port=port,
            log_level="info",
            reload=False,
            factory=True,
        )
    finally:
        lock.release()
