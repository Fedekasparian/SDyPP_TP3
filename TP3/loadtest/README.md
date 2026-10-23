# Pruebas de carga (Hit #3 y R5)

**Responsable: Integrante D**

## Configuración (k6)
- Escenario `users`: `ramping-vus` de 0 a VC durante `RAMP` (10 s), meseta de `DURATION` (60 s) y bajada de 5 s. Cada iteración envía un job con VA archivos y la cadena VB, y hace polling cada 0,5 s hasta `done`, `failed` o `dlq` (timeout de 120 s).
- Escenario `bot_sin_token`: 1 VU que pega sin token y espera 401.
- `INVALID_RATE` (0,05 por defecto en la matriz): fracción de requests con un archivo corrupto, que deben recibir un **400 claro** sin llegar a RabbitMQ.
- **SLO**: p95 de la latencia end-to-end por debajo de `SLO_P95_S` (10 s) y tasa de error por debajo del 5%.
- La latencia mínima medible es de unos 0,5 s, que es el intervalo de polling.

## Correr
```bash
python TP3/loadtest/gen_images.py                       # imágenes de V1 (1 KB a 100 MB)
export ADMIN_TOKEN=$(docker compose exec -T backend python /dev/stdin admin admin < TP3/scripts/gen_token.py)
BASE_URL=http://localhost:8000 MATRIX=r5 MODE=compose ./TP3/loadtest/run_matrix.sh
BASE_URL=http://<ip>/api MATRIX=hit3 MODE=manual ./TP3/loadtest/run_matrix.sh   # GKE
```
Sin k6 instalado, se puede usar Docker:
`docker run --rm -v "$PWD/TP3/loadtest:/lt" -w /lt/k6 grafana/k6:0.54.0 run -e BASE_URL=http://host.docker.internal:8000 ... job.js`

La salida queda en `results/*.json` (una celda por archivo, lo que permite cortar y retomar) y en `results/summary.{csv,md}` para R5 o `results/summary_hit3.{csv,md}` para el Hit #3. Las dos matrices escriben archivos distintos a propósito: comparten claves de celda, así que con una sola salida correr una pisaba la tabla de la otra.

## Tamaño de la matriz R5
VA(3) × VB(3) × VC(3) × V1(2) × V3(2) = **108 celdas**, de 75 s cada una: unas **2,5 h**. Conviene correrla de noche.
La columna `cuello_de_botella` se completa mirando Grafana (CPU de los workers, cola creciendo, latencia de Redis, etc.).

## Casos de falla durante la carga
- Archivo corrupto: `INVALID_RATE`.
- Operación inexistente: `OPS=sobel,rotate` en una corrida aparte, que debe dar 100% de 400.
- Worker que muere: `docker compose kill worker` o `kubectl delete pod -l app=worker` en medio de la corrida. Reportar `dlq`, `retries` y reprocesados (`POST /admin/dlq/reprocess`).
- `FAIL_RATE=0.3` en los workers, para forzar el camino de la DLQ.
