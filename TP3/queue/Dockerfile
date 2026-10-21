# Imagen unica para los ejemplos del Hit #0. Build context: TP3/queue
#   docker build -t tp3/queue-examples:dev TP3/queue
#   docker run --rm -e RABBIT_URL=... tp3/queue-examples:dev python ex1/producer.py
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
RUN pip install --no-cache-dir pika==1.3.2
COPY common.py /app/
COPY ex1 /app/ex1
COPY ex2 /app/ex2
COPY ex3 /app/ex3
COPY ex4 /app/ex4
RUN useradd -m app
USER app
