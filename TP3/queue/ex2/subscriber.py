"""Ej. 2: suscriptor (nodo) del fanout ex2.blocks.

Cada suscriptor declara su propia cola anonima y exclusiva: RabbitMQ le pone un nombre
(amq.gen-...) y la borra cuando el nodo se desconecta. Por eso un nodo que se conecta tarde
no ve los bloques anteriores (a diferencia de Kafka, que retiene el log).
Con EXPECTED=N termina tras N bloques e imprime un digest de la secuencia recibida:
si los 3 nodos imprimen el mismo digest, recibieron exactamente lo mismo y en el mismo orden.
"""
import hashlib
import json
import os
import socket

from common import connect

EXCHANGE = "ex2.blocks"
ME = os.getenv("NODE_ID", socket.gethostname())
EXPECTED = int(os.getenv("EXPECTED", "0"))

conn = connect()
ch = conn.channel()
ch.exchange_declare(EXCHANGE, "fanout", durable=True)
queue = ch.queue_declare("", exclusive=True).method.queue
ch.queue_bind(queue, EXCHANGE)

received: list[str] = []


def on_block(ch, method, _props, body):
    event = json.loads(body)
    received.append(event["hash"])
    print(f"[nodo {ME}] bloque {event['block']} {event['hash'][:12]}", flush=True)
    ch.basic_ack(method.delivery_tag)
    if EXPECTED and len(received) >= EXPECTED:
        digest = hashlib.sha256("".join(received).encode()).hexdigest()
        print(f"[nodo {ME}] recibidos {len(received)} bloques, digest {digest[:16]}", flush=True)
        ch.stop_consuming()


ch.basic_consume(queue, on_block)
print(f"[nodo {ME}] suscripto a {EXCHANGE} con la cola {queue}", flush=True)
ch.start_consuming()
conn.close()
