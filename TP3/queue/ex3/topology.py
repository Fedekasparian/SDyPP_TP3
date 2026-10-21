"""Ej. 3: topologia con Dead Letter Exchange. Idempotente; la llaman los tres scripts.

    producer --> ex3.main --(nack requeue=False)--> [ex3.dlx: fanout] --> ex3.dlq --> dlq_consumer

El ej. 4 reutiliza ex3.dlx/ex3.dlq como destino final de los mensajes que agotan reintentos.
"""
MAIN = "ex3.main"
DLX = "ex3.dlx"
DLQ = "ex3.dlq"


def declare(ch) -> None:
    ch.exchange_declare(DLX, "fanout", durable=True)
    ch.queue_declare(DLQ, durable=True)
    ch.queue_bind(DLQ, DLX)
    ch.queue_declare(MAIN, durable=True, arguments={"x-dead-letter-exchange": DLX})
