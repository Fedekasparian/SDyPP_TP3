# SDyPP TP3: Kubernetes, RabbitMQ y Cloud

Sistemas Distribuidos y Programación Paralela 2026, UNLu. **Entrega: 23/10/2026.**
Consignas: [Parte 1](https://dpetrocelli.github.io/sd2026/practica-3-parte-1.html) · [Parte 2](https://dpetrocelli.github.io/sd2026/practica-3-parte-2.html)

Plataforma asincrónica de procesamiento distribuido de imágenes (Sobel y otras operaciones) con un patrón master-worker sobre RabbitMQ, estado en Redis, despliegue en GKE con Terraform, workers elásticos en VMs y observabilidad con Prometheus y Grafana.

## Arranque rápido
```bash
cp .env.example .env                      # completar AUTH_SECRET y RABBIT_PASS (y el mismo pass en RABBIT_URL)
docker compose up -d --build --scale worker=3
TOKEN=$(docker compose exec -T backend python /dev/stdin alice user < TP3/scripts/gen_token.py)
curl -H "Authorization: Bearer $TOKEN" -F files=@TP3/loadtest/sample.png -F ops=sobel localhost:8000/jobs
```
UI en http://localhost:8081, Swagger en http://localhost:8000/docs y RabbitMQ en http://localhost:15672. Con `docker compose --profile obs up -d` se suman Grafana (:3000) y Prometheus (:9090).

## Despliegue público (GKE)
| Qué | URL |
|---|---|
| Frontend | http://136.69.20.245 |
| Backend (Swagger) | http://136.69.20.245/api/docs |
| Estado (health-check) | http://136.69.20.245/api/health |
| Grafana | http://136.80.214.178 |

Las dos IPs están reservadas como estáticas (`tp3-ingress`, global, y `tp3-grafana`, regional), así que no cambian aunque se recree el Ingress, el Service de Grafana o el cluster. Los tokens se generan contra el cluster con [gen_tokens_gke.sh](TP3/scripts/gen_tokens_gke.sh) y se comparten por privado.

## Estructura
```
TP3/
  queue/ex1..ex5/        Hit #0: patrones de mensajería                     (A)
  hit1/                  Hit #1: Sobel centralizado, distribuido, tolerante (A)
  hit2/ hit3/ hit4/      README de cada Hit, con punteros al código
  services/              common, backend, split, joiner, worker, dlq_monitor, frontend (A y B)
  k8s/                   base, overlays/local, overlays/gke, infra (RabbitMQ y Redis) (C)
  infra/terraform/       bootstrap, gke, workers                            (C)
  observability/         kube-prometheus-stack, ServiceMonitors, alertas, dashboard (D)
  loadtest/              k6, matriz R5 y Hit #3, resumen                    (D)
  scripts/               gen_token.py, r4_evidence.sh
  docs/                  contrato.md (R3), arquitectura.md, informe.md, r1-evidencia.md
.github/workflows/       ci (gitleaks, tests, build y push), infra, deploy, workers
docker-compose.yml       stack completo local
```

## Reparto
| Integrante | Frente | Entregables |
|---|---|---|
| **A** (Federico Kasparian) | Mensajería y cómputo | Hit #0 (ex1 a ex5), Hit #1 (etapas 1 a 3, demo de fallos), worker, operaciones |
| **B** (Justino Bernal) | Plataforma de aplicación | backend, split, joiner, dlq-monitor, R2, R3 ([contrato](TP3/docs/contrato.md)), R4 (script de evidencia), tests de integración |
| **C** (Mateo Ponti) | Infraestructura y CI/CD | Terraform (bootstrap, gke, workers), Hit #2 (diagrama híbrido), pipelines, R1 ([evidencia](TP3/docs/r1-evidencia.md)), deploy en GKE |
| **D** (Agustina Ortiz) | Observabilidad, carga y docs | Hit #4, matriz R5 y tabla del Hit #3, [informe](TP3/docs/informe.md) |

**Reglas:** una rama por frente (`feat/hit0`, `feat/backend`, `feat/infra`, `feat/obs`) y PRs chicos a `main`. El CI (gitleaks y tests) tiene que pasar. Los cambios en `TP3/services/common` (los contratos) se avisan a los 4.

## Estado actual
**Funcionando:**
- Pipeline end-to-end en docker compose: submit → split → N workers → joiner → `done`.
- Validación R2 antes de encolar, roles y aislamiento R4 (el script pasa los 5 casos), `/stats`, DLQ con reintentos y estacionamiento, y reprocesamiento por el admin.
- Health-checks JSON, logs en memoria, stdout y archivo, y métricas Prometheus.
- Suite de pruebas unitarias e integración real con Redis/RabbitMQ en CI. Progreso SSE, panel admin y evidencia R4 con tres backends locales: [parte B](TP3/docs/parte-b.md).
- Infraestructura aplicada en GCP: el pipeline `deploy` despliega en GKE en cada push a `main` y `workers` crea las VMs. Evidencia R1 en [r1-evidencia.md](TP3/docs/r1-evidencia.md).
- Hit #4 en local (capturas de Grafana y alertas disparadas), matriz R5 (108 celdas) y tabla del Hit #3 (120 celdas): [informe](TP3/docs/informe.md), secciones 6 y 8.
- Evidencia en GKE ([evidencia/gke](TP3/evidencia/gke/), workflow [evidencia-gke](.github/workflows/evidencia-gke.yml)): R4 con tres réplicas detrás del Ingress público, y CPU y memoria por pod y por nodo desde Prometheus.
- Prometheus descubre las VMs workers con `gce_sd_configs`, y los logs de los pods se centralizan en Loki con Fluent Bit ([observability/loki](TP3/observability/loki/)).
- Hit #2 híbrido validado: una VM de GCP consume de la RabbitMQ local por Tailscale, con tiempos de los escenarios local, nube y mixto ([hit2](TP3/hit2/README.md), [evidencia](TP3/evidencia/hit2/)).

## Seguridad
- `.env`, `*.tfstate`, `*.tfvars` y las claves están en `.gitignore`. **gitleaks** corre en cada push y PR, y falla si detecta un secreto.
- GitHub Actions se autentica con GCP por **OIDC (Workload Identity Federation)**, sin claves JSON.
- Las contraseñas viven en **Secret Manager**. El pipeline crea los Kubernetes Secrets y las VMs las leen con su service account.
- Las imágenes van a un **Artifact Registry privado**, que solo pueden leer los SA de los nodos y de los workers.
- Si un secreto se filtra, hay que **revocarlo y rotarlo**, porque queda en el historial de Git.
