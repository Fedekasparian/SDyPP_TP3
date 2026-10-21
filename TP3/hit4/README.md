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

Las alertas existen en dos formatos: [alerts.yaml](../observability/alerts.yaml)
(`PrometheusRule`, solo lo lee el operator dentro de k8s) y
[alerts-compose.yml](../observability/alerts-compose.yml) (formato nativo, cargado por
`rule_files` en el Prometheus de docker-compose). Si se cambia una, cambiar la otra.

Las metricas de RabbitMQ **por cola** se activan con
[prometheus.conf](../observability/rabbitmq/prometheus.conf), montado tanto en
`docker-compose.yml` como en `k8s/infra/rabbitmq.yaml`. Sin eso solo hay agregados
globales y la alerta no puede distinguir `tasks.tp3-worker` de `tasks.parked`.

## Pendientes (D)
Paso a paso en [docs/runbook-d.md](../docs/runbook-d.md).
- [ ] Correr la matriz y capturar el dashboard en vivo durante una corrida de k6.
- [ ] Disparar `ColaDeTareasAlta` (apagar los workers y mandar carga) y capturarla.
- [ ] Probar el stack en GKE (depende de C) y conseguir ahi las capturas de CPU y
      memoria por pod y por nodo: en docker-compose esos paneles quedan vacios
      porque salen de cAdvisor y node-exporter, que solo existen en Kubernetes.
- [ ] Reemplazar `PROJECT` en [kube-prometheus-stack-values.yaml](../observability/kube-prometheus-stack-values.yaml)
      y darle `roles/compute.viewer` al SA de nodos para el scrape de las VMs (coordinar con C).
