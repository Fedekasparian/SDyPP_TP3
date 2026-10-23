# Hit #3: Sobel contenerizado, asincrónico y escalable

**Responsables: B (aplicación) y C (infraestructura). Análisis de desempeño: D**

| Pieza | Dónde |
|---|---|
| Servicios (backend, split, joiner, worker, dlq-monitor, frontend) | [TP3/services](../services/) |
| Cluster GKE con nodepools `infra` y `apps` | [TP3/infra/terraform/gke](../infra/terraform/gke/) |
| Workers fuera del cluster (VMs) | [TP3/infra/terraform/workers](../infra/terraform/workers/) |
| Manifiestos | [TP3/k8s](../k8s/) (`infra/`, `base/`, `overlays/local`, `overlays/gke`) |
| Pipeline 1 (infra): cluster | [.github/workflows/infra.yml](../../.github/workflows/infra.yml) |
| Pipeline 1.1 (servicios base) y 1.2..N (apps) | [.github/workflows/deploy.yml](../../.github/workflows/deploy.yml) |
| Pipeline 2 (workers dinámicos) | [.github/workflows/workers.yml](../../.github/workflows/workers.yml) |
| Análisis de carga | [TP3/loadtest](../loadtest/) |

## Requisitos de mensajería
- **DLQ**: las colas `tasks.*` tienen DLX `tasks.dlx`. Un worker caído, con timeout o con OOM deja el mensaje sin ack. Las colas *quorum* lo reentregan y, superado `x-delivery-limit`, va a `tasks.dlq`. El `dlq-monitor` lo reasigna.
- **Retry de conexión**: backoff de 1, 2, 4, 8 y 16 s con tope de 30 s ([retry.py](../services/common/tp3common/retry.py)). No se reintenta nunca sin espera.
- **Pub/Sub de resultados**: exchange `fanout` `results` hacia `results.joiner` y `results.monitor`.

## Pendientes
- [ ] (C) `terraform apply` del cluster y carga de las GitHub Variables (ver [infra/README.md](../infra/README.md)).
- [ ] (C) Deseable: autoescalado de workers según la profundidad de `tasks.tp3-worker`.
- [x] (D) Tabla V1 × V2 × V3 con `MATRIX=hit3 ./run_matrix.sh`: 54 celdas medidas y 66 declaradas con motivo, en [loadtest/results/summary_hit3.md](../loadtest/results/summary_hit3.md). Análisis en la sección 8.6 del [informe](../docs/informe.md). Las 66 declaradas son retomables: relanzar el mismo comando completa lo que falta.
