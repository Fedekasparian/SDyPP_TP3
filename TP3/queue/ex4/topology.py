"""Ej. 4: retry con backoff exponencial usando una cola de espera por nivel (sin plugin).

    producer --> ex4.main --> consumer_retry
                   ^              | falla, intento < 5: publica en ex4.wait.<2^(intento-1)>s
                   |              v
                   +--(TTL vence, DLX "" rk=ex4.main)-- ex4.wait.1s / 2s / 4s / 8s
                                  | falla el 5to intento (4 reintentos agotados): nack
                                  v
                       [ex3.dlx] --> ex3.dlq   (DLQ del ej. 3)

Una cola por nivel con x-message-ttl fijo evita el problema de head-of-line del TTL por
mensaje: RabbitMQ solo expira el mensaje de la cabeza, y uno de 8 s bloquearia a uno de 1 s.
"""
MAIN = "ex4.main"
DELAYS = (1, 2, 4, 8)
MAX_RETRIES = len(DELAYS)
# Mismos nombres y argumentos que ex3/topology.py, para reutilizar esa DLQ.
EX3_DLX = "ex3.dlx"
EX3_DLQ = "ex3.dlq"


def wait_queue(delay: int) -> str:
    return f"ex4.wait.{delay}s"


def declare(ch) -> None:
    ch.exchange_declare(EX3_DLX, "fanout", durable=True)
    ch.queue_declare(EX3_DLQ, durable=True)
    ch.queue_bind(EX3_DLQ, EX3_DLX)
    ch.queue_declare(MAIN, durable=True, arguments={"x-dead-letter-exchange": EX3_DLX})
    for delay in DELAYS:
        # Sin consumidores: el mensaje espera el TTL y vuelve a ex4.main por el default exchange.
        ch.queue_declare(wait_queue(delay), durable=True, arguments={
            "x-message-ttl": delay * 1000,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": MAIN,
        })
