"""Ej. 1: consumidor punto a punto con ack manual.

PREFETCH=0 deja el default de RabbitMQ (sin limite: round-robin estricto al despachar).
PREFETCH=1 hace que RabbitMQ no le mande otra tarea hasta que haga ack (fair dispatch).
WORK_SECONDS simula el costo de procesar, para comparar un consumidor lento con uno rapido.
"""
import os
import socket
import time

from common import connect

QUEUE = "ex1.tasks"
ME = os.getenv("CONSUMER_ID", socket.gethostname())
PREFETCH = int(os.getenv("PREFETCH", "1"))
WORK_SECONDS = float(os.getenv("WORK_SECONDS", "0.5"))

conn = connect()
ch = conn.channel()
ch.queue_declare(QUEUE, durable=True)
if PREFETCH:
    ch.basic_qos(prefetch_count=PREFETCH)


def on_message(ch, method, _props, body):
    time.sleep(WORK_SECONDS)
    print(f"[consumer {ME}] {body.decode()}", flush=True)
    ch.basic_ack(method.delivery_tag)


ch.basic_consume(QUEUE, on_message)
print(f"[consumer {ME}] esperando en {QUEUE} (prefetch={PREFETCH or 'sin limite'})", flush=True)
ch.start_consuming()
