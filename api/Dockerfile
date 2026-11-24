FROM python:3.14.7-slim AS base

RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    ca-certificates && \
    apt-get clean

ENV PYTHONUNBUFFERED=True
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project


FROM base AS builder-prod

COPY . /src
WORKDIR /src

RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-editable


FROM base AS builder-dev

WORKDIR /app
COPY . .

RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked


FROM python:3.14.7-slim AS dev
WORKDIR /app
COPY --from=builder-dev /app /app
ENV PATH="/app/.venv/bin:$PATH"
# Apply DB migrations, then start the app (exec: fastapi becomes PID 1 and receives signals)
CMD ["sh", "-c", "vce-migrate && exec fastapi dev --host 0.0.0.0 --port 8000 --reload vce/app.py"]


FROM python:3.14.7-slim AS prod
WORKDIR /app
COPY --from=builder-prod /app /app
ENV PATH="/app/.venv/bin/:$PATH"
# Apply DB migrations, then start the app (exec: fastapi becomes PID 1 and receives signals)
CMD ["sh", "-c", "vce-migrate && exec fastapi run --host 0.0.0.0 --port 8000 .venv/lib/python3.14/site-packages/vce/app.py"]
