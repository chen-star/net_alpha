# Runtime image for the net_alpha web UI on a remote box.
# Binds 0.0.0.0:18765 INSIDE the container; compose never publishes the port,
# so it is reachable only on the internal docker network (by cloudflared).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --extra ui --frozen --no-dev

# Data dir: HOME is set to /data at runtime (compose), so ~/.net_alpha -> /data/.net_alpha.
VOLUME ["/data"]
EXPOSE 18765

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:18765/healthz || exit 1

# NOT `net-alpha ui` (calls launchctl) and NOT `service run` (hardcodes 127.0.0.1).
# Direct uvicorn on 0.0.0.0; the FastAPI lifespan starts the APScheduler jobs.
CMD ["uv", "run", "uvicorn", "net_alpha.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "18765"]
