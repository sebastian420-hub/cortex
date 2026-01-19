# Cortex Terminal Agent Dockerfile
# Multi-stage build for optimal size

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt requirements-test.txt ./
COPY pyproject.toml setup.py ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    pip wheel --no-cache-dir --wheel-dir=/wheels -e .

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /wheels /wheels
COPY --from=builder /app /app

# Install the package
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

# Copy application code
COPY cortex/ ./cortex/
COPY config/ ./config/

# Create non-root user
RUN useradd -m -u 1000 cortex && \
    chown -R cortex:cortex /app
USER cortex

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command
ENTRYPOINT ["python", "-m", "cortex"]
CMD ["--help"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import cortex; print('OK')" || exit 1

# Labels
LABEL org.opencontainers.image.title="Cortex Terminal Agent"
LABEL org.opencontainers.image.description="AI-powered terminal coding assistant"
LABEL org.opencontainers.image.source="https://github.com/yourusername/cortex"
LABEL org.opencontainers.image.licenses="MIT"
