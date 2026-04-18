# Multi-stage build for background worker
# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app/worker

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /install /usr/local

# Make sure scripts in the system prefix are usable
ENV PATH=/usr/local/bin:$PATH
ENV PYTHONPATH=/app

# Copy application code
COPY . /app/worker

# Create directory for PDF processing
RUN mkdir -p /app/pdfs /shared/graph_data

# Create non-root user for running the worker
RUN useradd -m -u 1000 worker && \
    chown -R worker:worker /app /shared/graph_data

USER worker

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CELERY_BROKER_URL=redis://redis:6379/0
ENV CELERY_RESULT_BACKEND=redis://redis:6379/0
ENV GRAPH_ARTIFACTS_PATH=/shared/graph_data

# Health check for Celery worker
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD celery -A worker.celery_app inspect ping || exit 1

# Run Celery worker
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--pool=solo"]
