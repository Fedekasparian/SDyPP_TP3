# Pruebas de carga (Hit #3 y R5)

**Responsable: Integrante D**

## Configuración (k6)
- Escenario `users`: `ramping-vus` de 0 a VC durante `RAMP` (10 s), meseta de `DURATION` (60 s) y bajada de 5 s. Cada iteración envía un job con VA archivos y la cadena VB, y hace polling cada 0,5 s hasta `done`, `failed` o `dlq` (timeout de 120 s).
- Escenario `bot_sin_token`: 1 VU que pega sin token y espera 401.
- `INVALID_RATE` (0,05 por defecto en la matriz): fracción de requests con un archivo corrupto, que deben recibir un **400 claro** sin llegar a RabbitMQ.
- **SLO**: ver "Objetivo de negocio y SLO" más abajo. (La corrida local del 23/10 usó un SLO único de p95 < 10 s y error < 5 %; se reproduce con `SLO_MODO=legacy`.)
- La latencia mínima medible es de unos 0,5 s, que es el intervalo de polling.

## Objetivo de negocio y SLO

**Quién usa la plataforma.** La pensamos como el servicio de procesamiento de imágenes de un
*marketplace*: los vendedores suben fotos de producto y la plataforma les devuelve los bordes
(Sobel, más grayscale y blur como preprocesamiento) para el recorte automático y el control de
calidad de la foto antes de publicar. Hay dos formas de uso, con necesidades distintas:

| Clase | Quién | Cómo usa la plataforma | Qué necesita | En la matriz |
|---|---|---|---|---|
| **Interactivo** | Vendedor que publica un producto desde la web | Sube 1 foto y espera el resultado en la pantalla del formulario | Respuesta en segundos: arriba de ~10 s el vendedor abandona o recarga, y se pierde la publicación | `VA=1` |
| **Lote** | Vendedor grande o integración que carga el catálogo | Sube 10 a 50 fotos y sigue con otra cosa (el progreso llega por SSE) | Que el lote termine en menos de un minuto y que **no se pierda ninguna foto** | `VA=10`, `VA=50` |

**SLO (sobre `job_latency`, end-to-end):**

| Clase | Latencia | Errores | Por qué |
|---|---|---|---|
| Interactivo (`VA=1`) | p95 < **10 s** | < **1 %** | Una espera de un formulario web; 1 de cada 100 fotos fallidas ya es un ticket de soporte por día por vendedor activo. |
| Lote (`VA>1`) | p95 < **45 s** | < **1 %** | El usuario no mira la pantalla, pero el lote tiene que cerrar dentro del minuto; el timeout del generador es 60 s, así que todo lo que pase de ahí cuenta como error. |

La concurrencia (`VC`) no cambia el objetivo: el vendedor no sabe ni le importa cuántos otros
están subiendo fotos al mismo tiempo. Justamente la matriz sirve para ver **hasta qué concurrencia
se sostiene el SLO** con 2 y con 6 workers. Error incluye 5xx, `failed`, `dlq` y timeouts; los
400 de los archivos corruptos que manda `INVALID_RATE` **no** cuentan como error (son la respuesta
correcta, R2).

`summarize.py` aplica este SLO por clase (`SLO_P95_S`, `SLO_P95_LOTE_S`, `SLO_ERR`).

## Cuello de botella por celda

En GKE, al terminar cada celda, `prom_celda.py` consulta Prometheus sobre **la ventana exacta de
la celda** y guarda `results-gke/<celda>.prom.json`: máximo de mensajes listos por cola
(`split.requests`, `tasks.tp3-worker`, `results.joiner`), CPU de cada VM worker, CPU de cada app
del cluster como fracción de su `limit`, CPU de los nodos y p95 HTTP. `summarize.py` recorre el
pipeline en orden y marca la **primera etapa saturada**, con el dato que la delata:

1. `backend` con CPU ≥ 80 % del limit → ingreso HTTP.
2. Cola `split.requests` ≥ 50 mensajes → `split`.
3. Cola `tasks.tp3-worker` ≥ 50 → workers; si la CPU de las VMs es ≥ 0,7 núcleos es **CPU de las
   VMs**, si no es **I/O** (cada fragmento va y vuelve a Redis por la red VM ↔ cluster).
4. Cola `results.joiner` ≥ 50 → `joiner`.
5. Algún nodo GKE ≥ 85 % de CPU → ese nodo.
6. Nada de lo anterior → "ninguno": el sistema no satura y la latencia la dominan el recorrido y
   el polling de 0,5 s.

Los umbrales son variables de entorno, y la regla se puede cambiar y volver a correr
`summarize.py` sin repetir la carga.

## R5 en GKE con workers en VM

Workflow [`r5-gke`](../../.github/workflows/r5-gke.yml) (Actions → r5-gke → Run workflow): levanta
el stack, corre un humo de 8 celdas y después las 108. k6 corre en el runner y le pega al Ingress
público. V3 son **VMs workers** creadas con Terraform (2 y 6). El resultado queda en
[`results-gke/summary.md`](results-gke/summary.md). Al terminar deja 2 VMs prendidas.

En GKE el generador ya no muere por OOM: `job.js` arma el multipart a mano en un solo buffer
(antes usaba la `FormData` de la jslib, con un pico de memoria de varias veces el payload). En el
runner k6 corre como binario (`grafana/setup-k6-action`): la imagen `grafana/k6` corre como uid
12345 y no podía escribir el `--summary-export` en el directorio montado.

**Corrida del 07/11/2026: 108/108 medidas**, meseta de 20 s. Análisis en el
[informe, §8.7](../docs/informe.md#87-r5-en-gke-con-workers-en-vm). Hicieron falta tres
corridas porque Redis se cayó dos veces bajo la carga (OOM del pod y después disco lleno por el
AOF). Las celdas medidas antes de cada caída se conservaron y `run_matrix.sh` las salteó en la
corrida siguiente. Las que corrieron con Redis caído se descartaron. Los cambios que lo dejaron
estable están en [`k8s/infra/redis.yaml`](../k8s/infra/redis.yaml): `maxmemory 1200mb` con
`volatile-ttl` y sin persistencia a disco. Las VMs workers no llevan IP pública y salen por
Cloud NAT, porque la cuota regional de 8 IPs no alcanzaba para V3=6.

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
La columna `cuello_de_botella` sale de Prometheus (ver "Cuello de botella por celda").

## Casos de falla durante la carga
- Archivo corrupto: `INVALID_RATE`.
- Operación inexistente: `OPS=sobel,rotate` en una corrida aparte, que debe dar 100% de 400.
- Worker que muere: `docker compose kill worker` o `kubectl delete pod -l app=worker` en medio de la corrida. Reportar `dlq`, `retries` y reprocesados (`POST /admin/dlq/reprocess`).
- `FAIL_RATE=0.3` en los workers, para forzar el camino de la DLQ.
