# Aviation Intelligence API - Backend Service
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GOOGLE_CLOUD_PROJECT=ai-projects-485420

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create logs directory
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Start application with gunicorn optimized for Cloud Run
# Increased timeout to 120s to allow for slow cold starts with Firestore/API initialization
CMD exec gunicorn --bind :$PORT --workers 1 --timeout 120 --keep-alive 2 --max-requests 1000 app.main:app