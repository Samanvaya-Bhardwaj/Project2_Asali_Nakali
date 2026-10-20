# Dockerfile for Asali-Nakali Distributed Polyglot Nodes
FROM python:3.11-slim

WORKDIR /app

# Copy application code and database assets
COPY . /app

# Set pure ASCII environment
ENV PYTHONUNBUFFERED=1
ENV LC_ALL=C
ENV LANG=C

# Default command can be overridden per service in docker-compose.yml
CMD ["python3", "scripts/run_cluster.py", "--mode", "all"]
