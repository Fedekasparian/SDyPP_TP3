"""Metricas Prometheus con nombres fijos (Hit #4) y servidor /health + /metrics
para los servicios que no son HTTP (worker, split, joiner, dlq-monitor)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

TASKS_PROCESSED = Counter("tasks_processed_total", "Tareas/fragmentos procesados", ["service"])
TASKS_QUEUED = Gauge("tasks_queued", "Mensajes pendientes en cola", ["queue"])
TASK_DURATION = Histogram(
    "task_duration_seconds",
    "Tiempo de procesamiento por tarea",
    ["service"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
TASK_ERRORS = Counter("task_errors_total", "Errores al procesar tareas", ["service", "reason"])
HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "Latencia HTTP", ["method", "path", "status"]
)


def start_health_server(service: str, port: int, checks: Callable[[], dict[str, str]]) -> None:
    """Expone GET /health ({servicio: estado, ...}) y GET /metrics en un thread daemon."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.startswith("/metrics"):
                body, ctype, code = generate_latest(), CONTENT_TYPE_LATEST, 200
            elif self.path.startswith("/health"):
                status = {service: "ok", **checks()}
                code = 200 if all(v == "ok" for v in status.values()) else 503
                body, ctype = json.dumps(status).encode(), "application/json"
            else:
                body, ctype, code = b"not found", "text/plain", 404
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # silencia el access log
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
