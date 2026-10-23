# Guion del video (TP3)

La consigna pide que el video quede **subido al repositorio**, que explique los servicios, los
componentes y la configuración, y que muestre **R2** (validación), **R4** (autenticación y roles)
y **una corrida de R5 con Grafana en vivo**. Duración objetivo: 10 a 12 minutos.

Comandos desde Git Bash en la raíz del repo. Todo está probado en docker compose; si GKE está
disponible, el bloque 6 lo suma.

## 0. Preparación (antes de grabar, no sale en el video)
Con 3 réplicas del backend (`docker-compose.r4.yml`) **no se publica el puerto 8000**: todo
entra por el proxy del frontend en `localhost:8081/api`.
```bash
cp -n .env.example .env                    # si no existe
docker compose -f docker-compose.yml -f docker-compose.r4.yml --profile obs up -d --build --scale worker=3
curl -s localhost:8081/api/health          # {"backend":"ok","redis":"ok","rabbitmq":"ok"}
tok() { docker compose exec -T backend python /dev/stdin "$1" "$2" < TP3/scripts/gen_token.py | tr -d '\r'; }
export USER_TOKEN=$(tok alice user) ADMIN_TOKEN=$(tok admin admin) USER_A_TOKEN=$(tok alice user) USER_B_TOKEN=$(tok bob user)
```
Abrir pestañas: UI http://localhost:8081, Swagger http://localhost:8081/api/docs,
RabbitMQ http://localhost:15672 (usuario y contraseña del `.env`) y Grafana http://localhost:3000
(`admin`/`admin`, dashboard "TP3 - Sobel distribuido").

**Entre el ensayo y la demo, vaciar Redis.** Los resultados viven 24 h en memoria y Docker tiene
8 GB. El 23/10, Redis murió por OOM después de muchas corridas, y el backend quedó `unhealthy`.
```bash
docker compose exec -T redis redis-cli FLUSHALL
```
Si algo quedó colgado, lo más rápido es reiniciar todo de cero: `docker compose -f docker-compose.yml
-f docker-compose.r4.yml --profile obs down` y repetir el `up`. RabbitMQ y Redis no tienen
volúmenes, así que arrancan vacíos.

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
curl -s -w " %{http_code}\n" -H "Authorization: Bearer $USER_TOKEN" \
  -F files=@TP3/loadtest/sample.png -F ops=sobel,rotate localhost:8081/api/jobs   # 400 unsupported_op
curl -s -w " %{http_code}\n" -H "Authorization: Bearer $USER_TOKEN" \
  -F files=@README.md -F ops=sobel localhost:8081/api/jobs                       # 400 invalid_image
```
Mostrar en la UI de RabbitMQ que `split.requests` no recibió nada (contador de publicados quieto).

## 4. R4: roles, aislamiento y 3 réplicas (1,5 min) — B
```bash
BASE_URL=http://localhost:8081/api bash TP3/scripts/r4_evidence.sh
# Sin Python en la máquina, se corre el mismo script con la imagen del backend:
MSYS_NO_PATHCONV=1 docker run --rm --network sdypp_tp3_default -v "$(pwd)/TP3:/TP3:ro" \
  --entrypoint python -e BASE_URL=http://frontend:8080/api -e ADMIN_TOKEN -e USER_A_TOKEN -e USER_B_TOKEN \
  tp3/backend:dev /TP3/scripts/r4_evidence.py                                    # 13 OK, 0 FAIL
```
Señalar en la salida: 401 sin token, 403 de usuario en `/stats`, 404 al pedir un job ajeno,
200 del admin, y los tres hostnames distintos en `X-Backend-Replica`.
En la UI: el panel admin con el token de usuario (rechazado) y con el de admin (estadísticas).

## 5. R5 con Grafana en vivo (3 min) — D
Con Grafana a la vista, largar una celda de la matriz:
```bash
MSYS_NO_PATHCONV=1 docker run --rm --network sdypp_tp3_default -v "$(pwd)/TP3/loadtest:/lt" -w /lt/k6 \
  grafana/k6:0.54.0 run -e BASE_URL=http://frontend:8080/api -e ADMIN_TOKEN="$ADMIN_TOKEN" \
  -e IMAGE=../images/100KB.png -e VA=10 -e OPS=blur,sobel -e VC=10 -e DURATION=60s job.js
```
Ensayado el 23/10 con 30 s: 133 jobs, 0 errores, p95 4,3 s, SLO cumplido. **No subir a imágenes
de 10 MB ni a VC=50 en vivo**: en esta máquina eso termina en OOM (sección 8.5 del informe).
- Mientras corre: throughput, mensajes publicados contra consumidos, profundidad de cola y p95.
- A mitad de la corrida, **matar un worker** (`docker kill sdypp_tp3-worker-1`). Los jobs siguen
  terminando con los otros dos. Ojo: con fragmentos de ~25 ms, lo más probable es que en ese
  instante no tenga nada sin ack y no aparezca ningún `reentregado`. Para mostrar la reentrega,
  enseñar la evidencia del caso c ([caso_c_worker_muerto.txt](../evidencia/r5/caso_c_worker_muerto.txt)),
  donde se mató justo al worker que tenía un fragmento sin ack. Después:
  `docker start sdypp_tp3-worker-1`.
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
