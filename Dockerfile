# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip "setuptools>=70,<81" wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Bind-mount `.:/app` in docker-compose overwrites /app at runtime; host entrypoint.sh may
# not be +x, which causes "exec: permission denied". Invoke via sh (no execute bit required).
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
