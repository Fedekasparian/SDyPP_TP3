"""Ej. 4: consumidor que falla con probabilidad FAIL_PROB y reintenta con backoff 1, 2, 4, 8 s.

El numero de reintento viaja en el header x-retry. Tras una falla con x-retry < 4 publica el
mensaje en la cola de espera del nivel que corresponde y hace ack del original; si fallan
los 4 reintentos hace nack y ex4.main lo manda a la DLQ del ej. 3.
SEED fija la secuencia aleatoria para que la demo sea reproducible.
"""
import json
import os
import random
import time

import pika

import topology
from common import connect

FAIL_PROB = float(os.getenv("FAIL_PROB", "0.5"))
if os.getenv("SEED"):
    random.seed(int(os.environ["SEED"]))

conn = connect()
ch = conn.channel()
topology.declare(ch)
ch.basic_qos(prefetch_count=1)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def on_message(ch, method, props, body):
    job = json.loads(body)
    retry = int((props.headers or {}).get("x-retry", 0))
    attempt = retry + 1
    if random.random() >= FAIL_PROB:
        log(f"[worker] trabajo {job['id']}: intento {attempt} OK")
        ch.basic_ack(method.delivery_tag)
        return
    if retry < topology.MAX_RETRIES:
        delay = topology.DELAYS[retry]
        log(f"[worker] trabajo {job['id']}: intento {attempt} FALLO, reintento en {delay}s")
        ch.basic_publish("", topology.wait_queue(delay), body, pika.BasicProperties(
            content_type="application/json", delivery_mode=2, headers={"x-retry": retry + 1}))
        ch.basic_ack(method.delivery_tag)
    else:
        log(f"[worker] trabajo {job['id']}: intento {attempt} FALLO, "
            f"{topology.MAX_RETRIES} reintentos agotados -> DLQ")
        ch.basic_nack(method.delivery_tag, requeue=False)


ch.basic_consume(topology.MAIN, on_message)
log(f"[worker] esperando en {topology.MAIN} (FAIL_PROB={FAIL_PROB})")
ch.start_consuming()
