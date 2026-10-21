"""Genera dashboards/tp3.json (Hit #4). Editar los paneles aca y regenerar:
    python TP3/observability/dashboards/gen_dashboard.py
"""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}


def q(p: float, metric: str, sel: str = "") -> dict:
    return {
        "expr": f"histogram_quantile({p}, sum by (le) (rate({metric}_bucket{sel}[1m])))",
        "legendFormat": f"p{int(p * 100)}",
    }


PANELS = [
    ("CPU por pod (cores)", "short", [
        {"expr": 'sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="tp3",container!=""}[2m]))',
         "legendFormat": "{{pod}}"}]),
    ("Memoria por pod", "bytes", [
        {"expr": 'sum by (pod) (container_memory_working_set_bytes{namespace="tp3",container!=""})',
         "legendFormat": "{{pod}}"}]),
    ("CPU por nodo", "percentunit", [
        {"expr": '1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[2m]))',
         "legendFormat": "{{instance}}"}]),
    ("Memoria por nodo", "percentunit", [
        {"expr": "1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes",
         "legendFormat": "{{instance}}"}]),
    ("Mensajes en cola (por cola)", "short", [
        {"expr": "tasks_queued", "legendFormat": "{{queue}}"}]),
    ("RabbitMQ: publicados / consumidos (msg/s)", "short", [
        {"expr": "sum(rate(rabbitmq_global_messages_received_total[1m]))", "legendFormat": "publicados"},
        {"expr": "sum(rate(rabbitmq_global_messages_delivered_total[1m]))", "legendFormat": "consumidos"},
        {"expr": "sum(rabbitmq_queue_messages_ready)", "legendFormat": "en cola (total)"}]),
    ("Latencia procesamiento por fragmento (worker)", "s", [
        q(0.5, "task_duration_seconds", '{service="worker"}'),
        q(0.95, "task_duration_seconds", '{service="worker"}'),
        q(0.99, "task_duration_seconds", '{service="worker"}')]),
    ("Latencia HTTP backend", "s", [
        q(0.5, "http_request_duration_seconds"),
        q(0.95, "http_request_duration_seconds"),
        q(0.99, "http_request_duration_seconds")]),
    ("Throughput (tareas/s por servicio)", "short", [
        {"expr": "sum by (service) (rate(tasks_processed_total[1m]))", "legendFormat": "{{service}}"}]),
    ("Tasa de errores", "percentunit", [
        {"expr": "sum(rate(task_errors_total[1m])) / clamp_min(sum(rate(tasks_processed_total[1m])), 0.001)",
         "legendFormat": "tareas"},
        {"expr": 'sum(rate(http_request_duration_seconds_count{status=~"5.."}[1m])) '
                 "/ clamp_min(sum(rate(http_request_duration_seconds_count[1m])), 0.001)",
         "legendFormat": "HTTP 5xx"}]),
]


def build() -> dict:
    panels = []
    for i, (title, unit, targets) in enumerate(PANELS):
        panels.append({
            "id": i + 1,
            "type": "timeseries",
            "title": title,
            "datasource": DS,
            "gridPos": {"h": 8, "w": 12, "x": (i % 2) * 12, "y": (i // 2) * 8},
            "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
            "targets": [{"refId": chr(65 + j), "datasource": DS, **t} for j, t in enumerate(targets)],
        })
    return {
        "uid": "tp3-main",
        "title": "TP3 - Sobel distribuido",
        "schemaVersion": 39,
        "refresh": "5s",
        "time": {"from": "now-30m", "to": "now"},
        "panels": panels,
    }


if __name__ == "__main__":
    out = Path(__file__).with_name("tp3.json")
    out.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"escrito {out}")
