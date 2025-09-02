FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOWNLOAD_DIR=/data

WORKDIR /app

# System deps: ffmpeg is required by yt-dlp for merge/extract
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY dropzone47/ dropzone47/
COPY main.py README.md pyproject.toml ./

# Create non-root user and data dir
RUN groupadd -r app && useradd -r -g app app \
    && mkdir -p /data \
    && chown -R app:app /app /data
USER app:app

# Entrypoint
CMD ["python", "main.py"]
