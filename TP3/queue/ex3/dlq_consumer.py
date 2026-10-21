"""Ej. 3: lee ex3.dlq e imprime cada mensaje fallido con los datos del header x-death.

Tambien recibe los mensajes que el ej. 4 manda a la DLQ tras agotar reintentos.
"""
import json

import topology
from common import connect

conn = connect()
ch = conn.channel()
topology.declare(ch)


def on_dead(ch, method, props, body):
    death = ((props.headers or {}).get("x-death") or [{}])[0]
    reason = death.get("reason", "?")
    origin = death.get("queue", "?")
    retries = (props.headers or {}).get("x-retry")
    extra = f", reintentos={retries}" if retries is not None else ""
    print(f"[dlq] {json.loads(body)} | motivo={reason}, cola origen={origin}{extra}", flush=True)
    ch.basic_ack(method.delivery_tag)


ch.basic_consume(topology.DLQ, on_dead)
print(f"[dlq] esperando en {topology.DLQ}", flush=True)
ch.start_consuming()
