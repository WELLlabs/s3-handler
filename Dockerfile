# Stage 1: Builder
FROM python:3.13-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    curl

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.13-alpine

# Install only runtime dependencies
RUN apk add --no-cache curl

# Install uv
RUN pip install --no-cache-dir uv

# Create non-root user
RUN adduser -D -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser main.py ./

USER appuser

EXPOSE 8000

CMD ["uv", "run", "main.py"]
