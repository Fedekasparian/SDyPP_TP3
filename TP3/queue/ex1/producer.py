"""Ej. 1: productor punto a punto. Publica N tareas numeradas (persistentes) en ex1.tasks."""
import os

import pika

from common import connect

QUEUE = "ex1.tasks"
N_TASKS = int(os.getenv("N_TASKS", "10"))

conn = connect()
ch = conn.channel()
ch.queue_declare(QUEUE, durable=True)

for n in range(1, N_TASKS + 1):
    # Default exchange: routing_key = nombre de la cola -> entrega punto a punto.
    ch.basic_publish(
        exchange="",
        routing_key=QUEUE,
        body=f"tarea {n}".encode(),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    print(f"[producer] enviada tarea {n}", flush=True)

conn.close()
