# Guion del video (TP3)

La consigna pide que el video quede **subido al repositorio**, que explique los servicios, los
componentes y la configuración, y que muestre **R2** (validación), **R4** (autenticación y roles)
y **una corrida de R5 con Grafana en vivo**. Duración objetivo: 10 a 12 minutos.

Comandos desde Git Bash en la raíz del repo. Todo está probado en docker compose; si GKE está
disponible, el bloque 6 lo suma.

## 0. Preparación (antes de grabar, no sale en el video)
```bash
cp -n .env.example .env                    # si no existe
docker compose -f docker-compose.yml -f docker-compose.r4.yml --profile obs up -d --build --scale worker=3
curl -s localhost:8000/health              # {"backend":"ok","redis":"ok","rabbitmq":"ok"}
export USER_TOKEN=$(docker compose exec -T backend python /dev/stdin alice user < TP3/scripts/gen_token.py)
export ADMIN_TOKEN=$(docker compose exec -T backend python /dev/stdin admin admin < TP3/scripts/gen_token.py)
```
Abrir pestañas: UI http://localhost:8081, Swagger http://localhost:8000/docs,
RabbitMQ http://localhost:15672, Grafana http://localhost:3000 (dashboard "TP3").

## 1. Arquitectura (2 min) — A
- Mostrar el diagrama de [arquitectura.md](arquitectura.md): backend → `split.requests` → split →
  `tasks.tp3-worker` → workers → fanout `results` → joiner / dlq-monitor.
- Por qué los bytes van por Redis y no por RabbitMQ; solapamiento al partir.
- Hit #0 en una frase por patrón y dónde se usa cada uno en la app (tabla del informe, sección 2).

## 2. Un job de punta a punta (1 min) — B
- En la UI: pegar el token de usuario, subir una imagen, ops `blur,sobel`.
- Mostrar el progreso en vivo (SSE) y la imagen final.
- En RabbitMQ: las colas `tasks.tp3-worker` (quorum, DLX) y el exchange `results` (fanout).

## 3. R2: validación antes de encolar (1 min) — B
```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $USER_TOKEN" \
  -F files=@TP3/loadtest/sample.png -F ops=sobel,rotate localhost:8000/jobs        # 400
curl -s -H "Authorization: Bearer $USER_TOKEN" -F files=@README.md -F ops=sobel localhost:8000/jobs   # 400, archivo no es imagen
```
Mostrar en la UI de RabbitMQ que `split.requests` no recibió nada (contador de publicados quieto).

## 4. R4: roles, aislamiento y 3 réplicas (1,5 min) — B
```bash
bash TP3/scripts/r4_evidence.sh
```
Señalar en la salida: 401 sin token, 403 de usuario en `/stats`, 404 al pedir un job ajeno,
200 del admin, y los tres hostnames distintos en `X-Backend-Replica`.
En la UI: el panel admin con el token de usuario (rechazado) y con el de admin (estadísticas).

## 5. R5 con Grafana en vivo (3 min) — D
Con Grafana a la vista, largar una celda de la matriz:
```bash
cd TP3/loadtest
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/lt" -w /lt/k6 grafana/k6:0.54.0 run \
  -e BASE_URL=http://host.docker.internal:8000 -e ADMIN_TOKEN="$ADMIN_TOKEN" \
  -e IMAGE=../images/1MB.png -e VA=10 -e OPS=blur,sobel -e VC=10 -e DURATION=60s k6/job.js
```
- Mientras corre: throughput, mensajes publicados contra consumidos, profundidad de cola y p95.
- A mitad de la corrida, **matar un worker** (`docker kill sdypp_tp3-worker-1`) y mostrar en los
  logs de los otros el fragmento `reentregado` (caso c de la sección 8.4 del informe).
- Al final: el resumen de k6 (p50/p95/p99, errores, SLO) y la tabla de la matriz en el informe
  (sección 8.2) con la conclusión de qué variable domina.
- Alerta: mostrar `ColaDeTareasAlta` en Prometheus → Alerts (o la captura de
  [evidencia/hit4](../evidencia/hit4/)).

## 6. Nube: GKE, Terraform y pipelines (2 min) — C
- GitHub Actions: `ci` (gitleaks, tests, build y push) → `deploy` (1.1 servicios base, 1.2..N apps,
  observabilidad) y `infra` (plan en PR, apply al mergear), `workers` (VMs).
- `kubectl -n tp3 get pods -o wide`: infra y apps en sus nodepools; workers como VMs en la consola de GCP.
- R1: [r1-evidencia.md](r1-evidencia.md), `ImagePullBackOff` sin credenciales y `Running` con la identidad correcta.
- Híbrido (Hit #2): diagrama de [hit2/README.md](../hit2/README.md) y por qué solo los workers van a la nube.

## 7. Cierre (30 s) — D
Conclusiones del informe (sección 11): el cuello de botella es mover bytes, no calcular Sobel; los
reintentos convierten un 30% de fallas por fragmento en ~3% de jobs afectados.

## Después de grabar
Subir el archivo al repo (por ejemplo `TP3/video/tp3.mp4`). Si pesa más de 100 MB, GitHub lo
rechaza: subirlo a YouTube o Drive y dejar el link en el README raíz y en este archivo.
