# Multi-stage Dockerfile for Drift Detection Service
# Optimized for small image size and production deployment

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder - Install dependencies and model cache
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Pre-download sentence-transformers model to cache
# This reduces startup time in production
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('all-MiniLM-L6-v2')"

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime - Minimal production image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Disable IPv6 to force IPv4 connections
RUN echo "net.ipv6.conf.all.disable_ipv6 = 1" >> /etc/sysctl.conf || true && \
    echo "net.ipv6.conf.default.disable_ipv6 = 1" >> /etc/sysctl.conf || true && \
    echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy sentence-transformers model cache from builder
COPY --from=builder /root/.cache /home/appuser/.cache

# Copy application code
COPY --chown=appuser:appuser . .

# Make sure scripts are executable
RUN chmod +x run_api.py || true

# Switch to non-root user
USER appuser

# Add local Python packages to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

# Default command - run the API server
# This can be overridden in docker-compose for worker/scheduler containers
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
