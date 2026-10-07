# Stage 1: Build & Dependency Resolution via uv
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency specifications
COPY pyproject.toml uv.lock* ./

# Install dependencies into /app/.venv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_PREFERENCE=only-system
RUN uv sync --frozen --no-dev || uv sync --no-dev

# Stage 2: Minimal Runtime Image
FROM python:3.13-slim AS runtime

WORKDIR /app

# Create non-root system user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Copy source code and proto stubs
COPY proto/ /app/proto/
COPY shared/ /app/shared/
COPY services/ /app/services/

# Compile proto stubs if required at build time
COPY scripts/ /app/scripts/
RUN python scripts/compile_proto.py

# Set proper ownership for non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8000 8001 8002 8003 8004 8005 8006 50051 50052 50053 50054

CMD ["uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

