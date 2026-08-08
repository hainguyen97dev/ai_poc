# Multi-stage build for Architecture Decision Assistant (ADA) — REST API service (ada-service/main.py)
# NOTE: This is the standalone ADA service, distinct from the Lab 1 CLI agent (agent.py / AIA).
# See ./ada-service/service-agent-contract.md for its contract; agent.py is not built by this image.

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
# domain/ and infra/ are the shared kernel (also used by agent.py, not built here) —
# main.py imports them at runtime, see the sys.path bootstrap at the top of main.py.
COPY domain/ ./domain/
COPY infra/ ./infra/
COPY ada-service/main.py .
COPY ada-service/sa-agent-prompt.md .
COPY ada-service/features/ ./features/

# Set environment
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run service
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
