"""Ej. 4: publica N trabajos en ex4.main (sin header x-retry: es el primer intento)."""
import json
import os

import pika

import topology
from common import connect

N_MSGS = int(os.getenv("N_MSGS", "5"))

conn = connect()
ch = conn.channel()
topology.declare(ch)

for n in range(1, N_MSGS + 1):
    ch.basic_publish("", topology.MAIN, json.dumps({"id": n}).encode(),
                     pika.BasicProperties(content_type="application/json", delivery_mode=2))
    print(f"[producer] enviado trabajo {n}", flush=True)

conn.close()
