"""Conexion compartida por los ejemplos del Hit #0.

Toma RABBIT_URL, o la arma con RABBIT_USER/RABBIT_PASS/RABBIT_HOST (asi se inyecta en k8s
desde el Secret `rabbitmq-auth`). Reintenta con backoff 1, 2, 4, 8... s (tope 30 s), igual
que tp3common/retry.py, para tolerar que RabbitMQ todavia este arrancando.
"""
import os
import time

import pika


def rabbit_url() -> str:
    if os.getenv("RABBIT_URL"):
        return os.environ["RABBIT_URL"]
    user = os.getenv("RABBIT_USER", "guest")
    password = os.getenv("RABBIT_PASS", "guest")
    host = os.getenv("RABBIT_HOST", "localhost")
    return f"amqp://{user}:{password}@{host}:5672/"


def connect(max_attempts: int = 6) -> pika.BlockingConnection:
    params = pika.URLParameters(rabbit_url())
    delay = 1
    for attempt in range(1, max_attempts + 1):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError as exc:
            if attempt == max_attempts:
                raise
            print(f"rabbitmq no disponible ({exc!r}), reintento en {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError("unreachable")
