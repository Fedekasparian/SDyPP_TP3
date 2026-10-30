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

## GKE
El job `observability` de [deploy.yml](../../.github/workflows/deploy.yml) instala el stack en
cada deploy. La contraseña de Grafana se genera la primera vez en el Secret `grafana-admin` y no
pasa por el repo:
```bash
kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d; echo
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80   # usuario admin
```
Para que Prometheus descubra las VMs workers, su KSA usa el SA `tp3-gke-nodes` (con
`compute.viewer`) por Workload Identity. Ese binding está en
[bootstrap/main.tf](../infra/terraform/bootstrap/main.tf) (`prometheus_wi`) y se aplicó el 30/10/2026.
Sin él, el job `tp3-vm-workers` queda sin targets y el log de Prometheus muestra
`403 ... iam.serviceAccounts.getAccessToken denied`. Para verificarlo, en Prometheus
*Status → Targets* tienen que figurar `tp3-worker-0` y `tp3-worker-1` en `up`, y
`tasks_processed_total{service="worker"}` tiene que devolver una serie por VM.

## Logs centralizados (extra)
Además de las métricas, Fluent Bit (DaemonSet) manda los logs de los pods a Loki, y se consultan
desde el mismo Grafana en **Explore → Loki**. Detalle en [observability/loki](../observability/loki/).

## Pendientes (D)
Paso a paso en [docs/runbook-d.md](../docs/runbook-d.md).
- [x] Correr la matriz y capturar el dashboard en vivo durante una corrida de k6 ([evidencia/hit4](../evidencia/hit4/)).
- [x] Disparar `ColaDeTareasAlta` (apagar los workers y mandar carga) y capturarla ([alertas_transicion.log](../evidencia/hit4/alertas_transicion.log)).
- [ ] Capturas de CPU y memoria por pod y por nodo en GKE: en docker-compose esos paneles
      quedan vacíos porque salen de cAdvisor y node-exporter, que solo existen en Kubernetes.
- [x] `PROJECT` se reemplaza en el deploy, el SA de nodos tiene `roles/compute.viewer` y el
      binding de Workload Identity del bootstrap está aplicado: Prometheus scrapea las VMs workers (C).
