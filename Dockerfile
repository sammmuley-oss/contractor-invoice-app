FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY backend/pyproject.toml backend/uv.lock* ./

# Install dependencies
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY backend/ .

# Create necessary directories
RUN mkdir -p /data/uploads /data/exports /data/backups

# Set environment variables
ENV DATABASE_URL=sqlite:////data/contractor_invoices.db
ENV UPLOAD_DIR=/data/uploads
ENV EXPORT_DIR=/data/exports
ENV BACKUP_DIR=/data/backups
ENV DEBUG=false

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
