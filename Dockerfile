# Build stage: Install python dependencies using uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set working directory
WORKDIR /app

# Enable bytecode compilation and increase HTTP timeout to handle large packages on slower connections
ENV UV_COMPILE_BYTECODE=1
ENV UV_HTTP_TIMEOUT=300

# Copy dependencies configuration
COPY pyproject.toml uv.lock ./

# Install dependencies (without the project code itself) to leverage Docker cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


# Runtime stage: Thin, secure production-grade container
FROM python:3.12-slim-bookworm AS runtime

# Set working directory
WORKDIR /app

# Copy the compiled virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Update path to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Prevent Python from writing .pyc files to disk and ensure stdout/stderr are unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy application source code
COPY . .

# Create a non-root user and set permissions for security
RUN useradd -u 10001 -m appuser && \
    chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Run the application using Uvicorn
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
