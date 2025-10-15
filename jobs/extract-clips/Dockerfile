# Extract Clips Cloud Run Job
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY extract_clips_job.py .

# Create directories for processing
RUN mkdir -p /tmp/cache /tmp/clips

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TMPDIR=/tmp

# Run the job
CMD ["python", "main.py"]