# syntax=docker/dockerfile:1

# --- builder: resolve the locked dependencies into /app/.venv ---------------
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app
# Dependencies first so code changes don't invalidate this layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# --- runtime ------------------------------------------------------------------
FROM python:3.13-slim

RUN groupadd --system --gid 10001 cookbook \
    && useradd --system --uid 10001 --gid cookbook --no-create-home --shell /usr/sbin/nologin cookbook

WORKDIR /app
COPY --from=builder --chown=cookbook:cookbook /app/.venv /app/.venv
# `cookbook migrate` finds alembic.ini in the working directory.
COPY --chown=cookbook:cookbook alembic.ini ./
COPY --chown=cookbook:cookbook migrations ./migrations
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    GUNICORN_CMD_ARGS="--bind=0.0.0.0:8080 --workers=2 --no-control-socket"

USER cookbook
EXPOSE 8080

# /healthz doesn't touch the database, so this only says the process is up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "cookbook.app:create_app()"]
