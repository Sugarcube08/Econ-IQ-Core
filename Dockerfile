# Build stage: Install python dependencies using uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_HTTP_TIMEOUT=300

# Copy dependencies configuration
COPY pyproject.toml uv.lock ./

# Install dependencies (without the project code itself) to leverage Docker cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


# Runtime stage: Install system services (Postgres, Redis, Supervisor) and copy virtual env
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Prevent Python from writing .pyc files and ensure stdout/stderr are unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql \
    postgresql-contrib \
    redis-server \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source code
COPY . .

# Copy supervisor configuration and entrypoint script
COPY infra/supervisord.conf /etc/supervisor/conf.d/econiq.conf
COPY infra/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose the API port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
