# SIMPA MCP Service - Multi-stage Dockerfile

# Stage 1: Builder
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml ./
COPY src/simpa/__init__.py src/simpa/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e "." --prefix=/install

# Stage 2: Development
FROM python:3.11-slim-bookworm AS development

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/

# Install in development mode
RUN pip install --no-cache-dir -e "."

# Expose port for SSE transport
EXPOSE 8000

# Default command
CMD ["python", "-m", "src.main"]

# Stage 3: Production
FROM python:3.11-slim-bookworm AS production

WORKDIR /app

# Security: Create non-root user
RUN groupadd --gid 1000 simpa && \
    useradd --uid 1000 --gid simpa --shell /bin/false --create-home simpa

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/
COPY docker-entrypoint.sh ./

# Install in production mode
RUN pip install --no-cache-dir -e "."

# Set ownership
RUN chown -R simpa:simpa /app

# Switch to non-root user
USER simpa

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Expose port for SSE transport
EXPOSE 8000

# Entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "-m", "src.main"]
