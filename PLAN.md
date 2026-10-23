# Plan TP3 (Partes 1 y 2), dividido entre 4 integrantes

> **Actualización B (20/10/2026):** este plan conserva el reparto original. Estado real, pruebas y pendientes de B: [TP3/docs/parte-b.md](TP3/docs/parte-b.md). A ya está integrada; varios archivos listados abajo como faltantes ya existían en la base.

## Contexto
Consignas: practica-3-parte-1 y parte-2 (sd2026). **Entrega: viernes 23/10/2026, todos los puntos.** Hoy es martes 20/10, así que quedan unos 3 días. Si falta cualquier entregable de R1–R5, el TP se rehace.

Ya hay mucho hecho, pero **nada está commiteado**: el único commit es "Initial commit" con el README. Esto es lo que ya existe:
- **Servicios Python** (`TP3/services/`): backend FastAPI con validación R2, auth HMAC con roles, `/stats`, reproceso de DLQ, `/health`, logs en memoria y en disco. Además split, worker, joiner y dlq_monitor, y `tp3common` con ops sobel/grayscale/blur/threshold, retry con backoff y store en Redis. Tests unitarios en 3 archivos.
- **Infra**: Terraform `bootstrap` (bucket de estado, Artifact Registry, WIF, Secret Manager), `gke` (pools infra y apps) y `workers` (VMs con startup script). Kustomize base, infra y overlays local/gke.
- **CI/CD**: `ci.yml` (gitleaks, tests, build y push), `deploy.yml`, `infra.yml` (plan en PR, apply en main) y `workers.yml`.
- **Observabilidad** (escrita recién): values de kube-prometheus-stack, ServiceMonitor, 4 alertas, dashboard `tp3.json`.
- **Scripts**: `gen_token.py` y `r4_evidence.sh`.

**Lo que falta** (resultado de la auditoría):
- Hit #0 completo (`TP3/queue/ex1..ex5`)
- Sobel centralizado (Hit1, etapa 1)
- Tests de integración
- k6/Locust y la matriz R5
- `contrato.md`/`openapi.yaml` (R3)
- Evidencia de ImagePullBackOff (R1)
- Consumidor "dashboard" del fanout, hoy un stub en `dlq_monitor/main.py:38-40`
- READMEs por Hit, diagramas, informe y video
- Despliegue real en GCP y en k8s local

## Paso 0: hoy, lo hace Federico antes de repartir
1. Commitear todo lo que hay en `main` y pushear. Revisar antes que `.env` no entre: ya está en `.gitignore`.
2. Dejar el repo **público** y verificar que gitleaks pase en CI.
3. Crear 4 ramas (`feat/a-hit0`, `feat/b-backend`, `feat/c-infra`, `feat/d-obs-load`). Mergear por PR, porque así el plan de Terraform corre en el PR.
4. K8s local: **minikube con Docker Desktop**. Es lo más simple en Windows: tiene el addon de ingress y `minikube image load`. Todos usan el mismo.
5. Averiguar el estado de GCP: `gcloud projects list` y `gsutil ls`. Si no hay nada, C arranca por el bootstrap.

---

## A: Hit #0 (patrones RabbitMQ) + Hit #1 centralizado
Es independiente del resto, así que puede arrancar ya.
- `TP3/queue/ex1/`: productor de 10 tareas y consumidor. Correr con 1 y con 2 consumidores, y documentar el round-robin.
- `TP3/queue/ex2/`: exchange fanout "nuevo bloque minado" con 3 suscriptores. Mencionar EventBridge, Google Pub/Sub y Kafka.
- `TP3/queue/ex3/`: cola con DLX. Hace nack si `"error": true`, y un consumidor lee la DLQ.
- `TP3/queue/ex4/`: 50% de fallas, reintentos a 1, 2, 4 y 8 s con TTL por mensaje y una cola intermedia (o el plugin delayed). A los 4 fallos va a la DLQ de ex3. Loguear el intento y la espera.
- `TP3/queue/ex5/`: solo documentación, con diagrama por patrón, diferencias y cuándo usar cada uno.
- Cada ejercicio lleva código Python con pika, manifests k8s (Deployment/Job más RabbitMQ) y un README corto.
- Para no duplicar: reutilizar `tp3common/retry.py` y el patrón de conexión de `tp3common/rabbit.py`.
- `TP3/sobel_centralizado/sobel.py`: un solo proceso que reutiliza `tp3common/ops.py` (función sobel), con README y tiempos de referencia para el informe.
- `TP3/hit1/README.md`: las 3 etapas (centralizado, distribuido, tolerante a fallas). Para la etapa 3, demo: `kubectl delete pod` de un worker en medio de un job y el fragmento se reasigna por prefetch=1 + ack manual + `x-delivery-limit`.

## B: Backend, servicios, contrato y evidencia R4
- **R3 `TP3/contrato.md`** (y opcionalmente `openapi.yaml`, que FastAPI genera en `/openapi.json`):
  - submit y respuesta inmediata, estados, % de chunks, timings por etapa, workers, retries
  - tabla de errores 400/401/403/404/413/429/500/503 con el body de cada uno
  - sección "qué falta": costo estimado, nodo/región, chunks reasignados desde la DLQ
  - Fuente: `backend/main.py:108-137` y `validation.py`.
- **Arreglos** detectados en la auditoría:
  - `submit_job` es async pero hace publish bloqueante: pasar a `def` o usar `run_in_threadpool` (`backend/main.py:153,180`).
  - Retry con backoff 1/2/4/8 (máximo 30) también en tiempo de ejecución, para publish y Redis (`main.py:59`).
  - TTL en las claves secundarias de Redis (`store.py`).
  - Manejo de errores en `/admin/dlq/reprocess` (`main.py:236-255`).
  - El hilo de profundidad de colas de `dlq_monitor` debe ir dentro de try/retry (`dlq_monitor/main.py:43-57`).
  - `/health` del backend también tiene que chequear RabbitMQ.
- **Consumidor dashboard del fanout**: `on_result` en `dlq_monitor/main.py:38` publica el progreso en Redis (pub/sub o lista). El backend lo expone con un endpoint SSE `/jobs/{id}/events` o `/admin/live`. El frontend muestra el progreso en vivo y una vista admin de `/stats`.
- **Tests de integración** `TP3/services/backend/tests/test_integration.py`: FastAPI TestClient con Redis y RabbitMQ reales, levantados como `services:` en `ci.yml`. Cubre submit → status, 401/403/404 y validaciones que no deben llegar a la cola.
- **Evidencia R4**: correr `TP3/scripts/r4_evidence.sh` con 3 réplicas en local y en GKE, y guardar la salida en `TP3/evidencia/r4_*.txt`.
- `TP3/services/README.md`: arquitectura, diagrama y decisiones (auth HMAC por request, stateless, topología de colas).

## C: Infra GCP, Terraform, CI/CD, R1 (Hit #2 y #3 en la nube)
- **GCP desde cero**: proyecto con billing → `terraform apply` de `TP3/infra/terraform/bootstrap`. Después migrar su estado al bucket GCS: descomentar `bootstrap/provider.tf:13-15` y `terraform init -migrate-state`. Cargar los valores de Secret Manager y configurar las `vars` de GitHub (`GCP_PROJECT`, WIF provider, SA). Documentar todo en `TP3/infra/README.md`, que `ci.yml:36` ya referencia.
- **GKE**: correr `infra.yml` y pasar `TF_VAR_zone` desde vars. Verificar que RabbitMQ y Redis queden en el pool infra y las apps en el pool apps.
- **Workers**:
  - `workers.yml` debe aplicar al mergear a main, además de la ejecución manual.
  - Leer `rabbit_host`/`redis_host` de los outputs o de la IP del ILB con `kubectl`, en lugar de cargarlos a mano (`workers.yml:28-29`).
  - Deseable: job programado que lea la profundidad de `/stats` y calcule `worker_count`.
- **Pipeline 1**: separar en `deploy.yml` el job 1.1 (servicios base) y los jobs 1.2..N, uno por app con matrix.
- **R1 evidencia** `TP3/evidencia/r1/`:
  1. Deployment con una imagen del registry en un namespace o pool cuyo SA no tenga `artifactregistry.reader` (o sin imagePullSecret en minikube): captura del `ImagePullBackOff`.
  2. El mismo deployment con la identidad correcta funcionando. Agregar un script `TP3/scripts/r1_evidence.sh`.
- **Local**: dejar andando `TP3/k8s/overlays/local` en minikube, con un script `TP3/scripts/local_up.sh` que haga build, `minikube image load`, cree los secrets y haga `kubectl apply -k`.
- **Diagrama de arquitectura híbrida** (Hit2): para cada servicio, si va local o en la nube y por qué. Agregar una nota sobre el CAP de RabbitMQ (quorum queues → CP) frente a Redis (AP/async replication).

## D: Observabilidad (Hit #4) + load tests R5 + informe
- Terminar Hit4: completar el `TODO (D)` en `kube-prometheus-stack-values.yaml:19`. Hay que reemplazar `PROJECT`, darle `roles/compute.viewer` al SA de nodos (coordinar con C en `bootstrap/main.tf`) y abrir el puerto 8080 de las VMs en el firewall.
- Activar en RabbitMQ las métricas por objeto (`rabbitmq_prometheus.return_per_object_metrics = true` en `k8s/infra/rabbitmq.yaml`) para tener publicados y consumidos por cola.
- Verificar que `dashboards/tp3.json` tenga CPU y memoria por pod y por nodo, mensajes de RabbitMQ, p50/p95/p99 y tasa de error. Probar una alerta disparándola: cola > 100 con los workers apagados.
- **k6** en `TP3/loadtest/`:
  - `scenario.js` parametrizado por env: VA (1/10/50 archivos), VB (1/2/3 ops encadenadas), VC (1/10/50 VUs, con al menos un bot sin token), V1 (tamaño de imagen: generar 10 KB, 1 MB, 10 MB…).
  - Casos inválidos: op inexistente, archivo corrupto, worker que muere con `FAIL_RATE`.
  - `run_matrix.sh` recorre VA×VB×VC × 2 valores de V1 × 2 de V3 (cantidad de workers) y guarda JSON.
  - `summarize.py` arma la tabla p50/p95/p99, throughput, error rate y si se cumple el SLO (definir uno, por ejemplo p95 < 10 s y errores < 1%).
  - Documentar VUs, ramp-up y duración en `TP3/loadtest/README.md`.
- **Informe** `TP3/informe.md` (o PDF): herramientas de IA usadas y cómo ayudaron, respuestas teóricas (NIST, cloud-native vs híbrido, cloud-bursting, CAP), tablas R5 y del Hit3, gráficos de Grafana, diagramas y conclusiones. Cada integrante aporta su sección; D integra.
- **Video**: guion y grabación (D coordina). Tiene que mostrar R2, R4 y una corrida de R5 con Grafana en vivo.

---

## Cronograma
| Día | A | B | C | D |
|---|---|---|---|---|
| Mar 20 (noche) | ex1–ex3 | contrato.md + arreglos | bootstrap GCP + vars de GitHub | k6 `scenario.js` local |
| Mié 21 | ex4–ex5, sobel centralizado, README Hit1 | integración, SSE/dashboard, frontend | GKE + deploy + workers, local_up.sh | observabilidad en GKE, alertas |
| Jue 22 | ayudar con R5/video, diagramas | evidencia R4 (local + GKE) | evidencia R1, diagrama híbrido | matriz R5 en GKE, informe |
| Vie 23 | revisión final, video, README raíz con índice por Hit, entrega | | | |

**Dependencias**: B y D pueden trabajar con docker-compose o minikube mientras C levanta GKE. La matriz R5 y la evidencia R4 en la nube necesitan GKE (jueves). Si GCP se traba, la Parte 1 local igual tiene que quedar completa.

**Cuidado con la cuota**: la cuenta free trial tiene límite de vCPU. Usar máquinas chicas (e2-small/medium) y, si hace falta, VMs de workers en otra región. Hacer `terraform destroy` de los workers después de cada corrida.

## Verificación final (checklist de entrega)
- `pytest TP3/services` en verde, CI en verde con gitleaks y el build pusheando a Artifact Registry.
- `scripts/local_up.sh`: job end-to-end en minikube y `/health` de cada servicio.
- `kubectl get pods -o wide` en GKE: infra y apps en sus pools, workers como VMs que procesan.
- `r1_evidence.sh` y `r4_evidence.sh` con salidas guardadas en `TP3/evidencia/`.
- Matrix k6 con la tabla en el informe, Grafana con datos y una alerta disparada (captura).
- Cada carpeta de Hit tiene README (cómo correr, diagrama, decisiones), además de `contrato.md`, el informe y el video en el repo.
