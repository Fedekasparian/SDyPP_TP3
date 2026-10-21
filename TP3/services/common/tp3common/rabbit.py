"""Topologia RabbitMQ compartida (contrato del Paso 0).

    backend --(split.requests)--> split --[tasks: direct, rk=<worker_image>]--> tasks.<pool> --> worker
                                                       | nack / crash definitivo
                                                       v
                                          [tasks.dlx: fanout] --> tasks.dlq --> dlq-monitor
                                                                                 | reintentos agotados
                                                                                 v
                                                                             tasks.parked (admin reprocesa)
    worker --[results: fanout]--> results.joiner --> joiner
                               \-> results.monitor --> dlq-monitor (dashboard/progreso)

Mensaje de tarea (JSON):
    {job_id, file_idx, frag_idx, fragment_id, total_fragments, ops, params,
     worker_image, pad_top, core_h, attempt, enqueued_at}
Mensaje de resultado (JSON):
    {job_id, file_idx, frag_idx, fragment_id, pad_top, core_h, worker_id,
     started_at, finished_at, attempt}
"""
import json
from typing import Any

import pika

from . import config
from .retry import retry_with_backoff

EX_TASKS = "tasks"
EX_TASKS_DLX = "tasks.dlx"
EX_RESULTS = "results"
Q_SPLIT = "split.requests"
Q_DLQ = "tasks.dlq"
Q_PARKED = "tasks.parked"
Q_RESULTS_JOINER = "results.joiner"
Q_RESULTS_MONITOR = "results.monitor"


def task_queue(pool: str) -> str:
    return f"tasks.{pool}"


def connect(url: str | None = None, max_attempts: int = 10) -> pika.BlockingConnection:
    params = pika.URLParameters(url or config.RABBIT_URL)
    params.heartbeat = 60
    params.blocked_connection_timeout = 30
    return retry_with_backoff(lambda: pika.BlockingConnection(params), "rabbitmq", max_attempts)


def declare_topology(ch, pools: list[str] | None = None) -> None:
    """Idempotente: cualquier servicio puede llamarla al arrancar."""
    ch.exchange_declare(EX_TASKS, "direct", durable=True)
    ch.exchange_declare(EX_TASKS_DLX, "fanout", durable=True)
    ch.exchange_declare(EX_RESULTS, "fanout", durable=True)

    ch.queue_declare(Q_SPLIT, durable=True)
    ch.queue_declare(Q_DLQ, durable=True)
    ch.queue_bind(Q_DLQ, EX_TASKS_DLX)
    ch.queue_declare(Q_PARKED, durable=True)

    for pool in pools or config.ALLOWED_WORKER_IMAGES:
        q = task_queue(pool)
        # Quorum + delivery-limit: si un worker muere (crash/OOM) con el mensaje sin ack,
        # RabbitMQ lo reentrega; superado el limite, va a la DLQ en vez de ciclar para siempre.
        ch.queue_declare(q, durable=True, arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": 2,
            "x-dead-letter-exchange": EX_TASKS_DLX,
        })
        ch.queue_bind(q, EX_TASKS, routing_key=pool)

    for q in (Q_RESULTS_JOINER, Q_RESULTS_MONITOR):
        ch.queue_declare(q, durable=True)
        ch.queue_bind(q, EX_RESULTS)


def publish_json(ch, exchange: str, routing_key: str, body: dict[str, Any]) -> None:
    ch.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=json.dumps(body).encode(),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
    )


def queue_depth(ch, queue: str) -> int:
    return ch.queue_declare(queue, passive=True).method.message_count
