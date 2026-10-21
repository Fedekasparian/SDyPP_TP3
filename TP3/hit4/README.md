# Hit #4: observabilidad (Prometheus y Grafana)

**Responsable: Integrante D**. Todo está en [TP3/observability](../observability/).

| Requisito | Implementación |
|---|---|
| Instalación en el nodepool infra | `kube-prometheus-stack` con [values](../observability/kube-prometheus-stack-values.yaml) (nodeSelector y tolerations `pool=infra`) |
| Métricas custom | [metrics.py](../services/common/tp3common/metrics.py): `tasks_processed_total`, `tasks_queued`, `task_duration_seconds`, `task_errors_total`, `http_request_duration_seconds` |
| Scrape | [servicemonitors.yaml](../observability/servicemonitors.yaml) para las apps, RabbitMQ y Redis. Las VMs workers se descubren con `gce_sd_configs` |
| Dashboard | [dashboards/tp3.json](../observability/dashboards/tp3.json), generado por `gen_dashboard.py`: CPU y memoria por pod y por nodo, mensajes de RabbitMQ, p50/p95/p99 y errores |
| Alertas | [alerts.yaml](../observability/alerts.yaml): cola alta, workers sin procesar, fragmentos en DLQ y tasa de error |

## Local (docker compose)
```bash
docker compose --profile obs up -d     # Prometheus :9090, Grafana :3000 (dashboard "TP3")
```
Los paneles de CPU y memoria por pod y por nodo solo tienen datos en Kubernetes (cAdvisor y node-exporter).

## Pendientes (D)
- [ ] Probar el stack en GKE y capturar el dashboard en vivo durante una corrida de k6.
- [ ] Disparar `ColaDeTareasAlta` (escalar los workers a 0 y mandar carga) y capturarla.
- [ ] Darle `roles/compute.viewer` al SA de nodos para el scrape de las VMs.
