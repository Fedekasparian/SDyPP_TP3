"""Ej. 2: publicador Pub/Sub. Emite eventos "nuevo bloque minado" en el exchange fanout ex2.blocks.

Cada bloque encadena el hash del anterior (como una blockchain de juguete), asi los
suscriptores pueden verificar que recibieron la misma secuencia.
START_DELAY espera antes de publicar: en k8s da tiempo a que los suscriptores se bindeen,
porque un fanout sin colas bindeadas descarta el mensaje.
"""
import hashlib
import json
import os
import time

import pika

from common import connect

EXCHANGE = "ex2.blocks"
N_BLOCKS = int(os.getenv("N_BLOCKS", "5"))
INTERVAL = float(os.getenv("INTERVAL", "1"))
START_DELAY = float(os.getenv("START_DELAY", "0"))

time.sleep(START_DELAY)
conn = connect()
ch = conn.channel()
ch.exchange_declare(EXCHANGE, "fanout", durable=True)

prev = "0" * 64
for n in range(1, N_BLOCKS + 1):
    block_hash = hashlib.sha256(f"{n}:{prev}".encode()).hexdigest()
    event = {"block": n, "hash": block_hash, "prev": prev, "ts": time.time()}
    # En fanout la routing key se ignora: el exchange copia el mensaje a todas las colas bindeadas.
    ch.basic_publish(EXCHANGE, "", json.dumps(event).encode(),
                     pika.BasicProperties(content_type="application/json", delivery_mode=2))
    print(f"[publisher] bloque {n} minado: {block_hash[:12]}", flush=True)
    prev = block_hash
    time.sleep(INTERVAL)

conn.close()
