FROM python:3.13-slim

# FFmpeg install
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Project files
COPY . .

# Required directories
RUN mkdir -p uploads outputs

# Render provides PORT
ENV PORT=10000

EXPOSE 10000

# Start Flask with Gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 7200 app:app
