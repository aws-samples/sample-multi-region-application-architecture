# Multi-stage Dockerfile for React + Flask application
# Stage 1: Build React frontend
FROM public.ecr.aws/docker/library/node:20-alpine AS frontend-build

WORKDIR /frontend

# Copy package files
COPY frontend/package*.json ./

# Install ALL dependencies (not just production)
RUN npm install

# Copy frontend source
COPY frontend/ ./

# Build React app
RUN npm run build

# Stage 2: Flask backend + React static files
FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements
COPY app/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser

# Copy Flask application
COPY app/app.py ./
COPY app/auth.py ./

# Copy global-bundle.pem for DocumentDB TLS
COPY data/global-bundle.pem ./

# Copy React build from frontend-build stage
COPY --from=frontend-build /frontend/dist ./static

# Expose port
EXPOSE 5000

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

# Run with gunicorn (multi-worker, production-ready)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]

