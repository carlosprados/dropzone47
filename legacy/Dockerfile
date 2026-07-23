FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOWNLOAD_DIR=/data \
    HOME=/home/app \
    XDG_CACHE_HOME=/data/.cache

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

# Create non-root user and data/cache dirs
RUN groupadd -r app \
    && useradd -m -d /home/app -r -g app app \
    && mkdir -p /data "$XDG_CACHE_HOME" \
    && chown -R app:app /app /home/app \
    && chown -R 1000:1000 /data || true
USER app:app

# Entrypoint
CMD ["python", "main.py"]
