FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Database lives in /data so it can be mounted as a persistent volume
ENV DB_PATH=/data/production.db
RUN mkdir -p /data
VOLUME /data

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=2)" || exit 1

CMD ["gunicorn", "-b", "0.0.0.0:5000", "--workers", "2", "app:app"]
