FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy action source
WORKDIR /llm-policy-action
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir \
    pyyaml \
    rich \
    pathlib

# Create cache directory for agent verification
RUN mkdir -p /llm-policy-action/.agent-cache

# Set permissions
RUN chmod +x /llm-policy-action/entrypoint.py

# Set environment variables for better Python behavior
ENV PYTHONPATH=/llm-policy-action
ENV PYTHONUNBUFFERED=1

# ► Absolute path so GitHub's work-dir override doesn't matter
ENTRYPOINT ["python", "/llm-policy-action/entrypoint.py"]