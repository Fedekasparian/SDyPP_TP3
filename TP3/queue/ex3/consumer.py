"""Ej. 3: consumidor de ex3.main. Hace ack a los validos y nack (sin requeue) a los erroneos.

Con requeue=False RabbitMQ no devuelve el mensaje a la cola: lo "dead-letterea" al exchange
configurado en x-dead-letter-exchange, agregando el header x-death con el motivo.
"""
import json

import topology
from common import connect

conn = connect()
ch = conn.channel()
topology.declare(ch)
ch.basic_qos(prefetch_count=1)


def on_message(ch, method, _props, body):
    msg = json.loads(body)
    if msg.get("error"):
        print(f"[consumer] mensaje {msg['id']} con error -> nack, va a la DLQ", flush=True)
        ch.basic_nack(method.delivery_tag, requeue=False)
    else:
        print(f"[consumer] mensaje {msg['id']} procesado OK", flush=True)
        ch.basic_ack(method.delivery_tag)


ch.basic_consume(topology.MAIN, on_message)
print(f"[consumer] esperando en {topology.MAIN}", flush=True)
ch.start_consuming()
