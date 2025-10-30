FROM python:3.11-slim

# Install ffmpeg and system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY extract_clips_job.py .
COPY main.py .

# Set Python to run unbuffered (see logs immediately)
ENV PYTHONUNBUFFERED=1

# Run the job
CMD ["python", "main.py"]
