# =============================================================================
# Workloom - Production Dockerfile
# Multi-stage build for minimal image size
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpq-dev     && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir .

# -----------------------------------------------------------------------------
# Stage 2: Runtime - Minimal production image
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends     libpq5     curl     ffmpeg     && rm -rf /var/lib/apt/lists/*     && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd --gid 1000 workloom &&     useradd --uid 1000 --gid workloom --shell /bin/bash --create-home workloom

# Copy application code
COPY --chown=workloom:workloom src/ ./src/
COPY --chown=workloom:workloom alembic.ini ./
COPY --chown=workloom:workloom migrations/ ./migrations/

# Create data directory for uploads (owned by non-root user)
RUN mkdir -p /app/data/hr_templates && chown -R workloom:workloom /app/data

# Switch to non-root user
USER workloom

# Environment variables
ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3     CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run application
CMD ["uvicorn", "workloom.main:app", "--host", "0.0.0.0", "--port", "8000"]
