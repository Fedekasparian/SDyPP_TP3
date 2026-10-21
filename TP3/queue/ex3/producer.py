"""Ej. 3: publica N mensajes en ex3.main; uno de cada ERROR_EVERY lleva "error": true."""
import json
import os

import pika

import topology
from common import connect

N_MSGS = int(os.getenv("N_MSGS", "10"))
ERROR_EVERY = int(os.getenv("ERROR_EVERY", "3"))

conn = connect()
ch = conn.channel()
topology.declare(ch)

for n in range(1, N_MSGS + 1):
    msg = {"id": n, "payload": f"pedido {n}", "error": n % ERROR_EVERY == 0}
    ch.basic_publish("", topology.MAIN, json.dumps(msg).encode(),
                     pika.BasicProperties(content_type="application/json", delivery_mode=2))
    print(f"[producer] enviado {msg}", flush=True)

conn.close()
