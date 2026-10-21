# Build context: TP3/services
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 LOG_DIR=/var/log/tp3
COPY common /app/common
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir /app/common -r /tmp/requirements.txt
COPY backend /app/backend
RUN useradd -m app && mkdir -p /var/log/tp3 && chown app /var/log/tp3
USER app
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
