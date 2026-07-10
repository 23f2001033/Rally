FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 RALLY_DB_PATH=/data/rally.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rally/ ./rally/
COPY seeds/ ./seeds/

# /data is a mounted volume on Fly (see fly.toml) so the roster/shifts persist across deploys.
RUN mkdir -p /data
CMD ["python", "-m", "rally.app"]
