# ----------------------------------------
# Base Image
# ----------------------------------------
FROM python:3.12-slim

# ----------------------------------------
# Working Directory
# ----------------------------------------
WORKDIR /app


# ----------------------------------------
# Install uv (binary copy)
# ----------------------------------------
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# ----------------------------------------
# Copy dependency files first (cache layer)
# ----------------------------------------
COPY pyproject.toml uv.lock ./

# ----------------------------------------
# Install Python dependencies
# ----------------------------------------
RUN uv sync --frozen

# ----------------------------------------
# Copy application code
# ----------------------------------------
COPY . .


RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

USER app

# ----------------------------------------
# Expose Port
# ----------------------------------------
EXPOSE 5678

# ----------------------------------------
# Health Check
# ----------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ----------------------------------------
# Run Application
# ----------------------------------------
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5678"]
