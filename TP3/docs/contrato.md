# Contrato de la API (R3)

**Responsable: Integrante B**. La especificación OpenAPI completa la genera FastAPI en `GET /openapi.json`, con UI en `/docs`. Para guardarla en el repo: `curl localhost:8000/openapi.json > TP3/docs/openapi.json`.

API **asincrónica**: el envío valida y persiste la entrada, confirma su publicación en RabbitMQ y responde `202` con `job_id`, sin esperar el procesamiento. Ante una dependencia caída, los reintentos pueden demorar la respuesta antes de un `503`.

## Autenticación
Las rutas de jobs y administración requieren `Authorization: Bearer <token>`. El token es un HMAC-SHA256 firmado sobre `{sub, role, exp}` ([auth.py](../services/common/tp3common/auth.py)). Las rutas técnicas `/health`, `/metrics`, `/docs`, `/redoc` y `/openapi.json` son públicas. Los roles son:
- `user`: envía jobs y consulta **solo los suyos**.
- `admin`: además puede usar `/stats`, ver todos los jobs, reprocesar la DLQ y emitir tokens.

## 1. Envío: `POST /jobs`
`multipart/form-data`:

| Campo | Tipo | Oblig. | Descripción |
|---|---|---|---|
| `files` | archivo (repetible) | sí | 1 a `MAX_FILES` (50) imágenes PNG, JPEG o BMP, de hasta `MAX_FILE_MB` cada una |
| `ops` | string | sí | Operaciones encadenadas separadas por coma, en orden: `blur,sobel`. Permitidas: `ALLOWED_OPS` (`sobel`, `grayscale`, `blur`, `threshold`). Máximo `MAX_OPS` |
| `worker_image` | string | no | Pool o imagen de worker que resuelve el job. Debe estar en `ALLOWED_WORKER_IMAGES`. Default: el primero de la lista |
| `params` | string JSON | no | Parámetros por operación: `{"threshold": {"threshold": 90}}` |

Todo se valida **antes de encolar** (R2). Si algo es inválido, la respuesta es 400 o 413 y no se publica nada en RabbitMQ.

**Respuesta `202 Accepted`:**
```json
{ "job_id": "cd4272803e0e455e85d9d6def4cf5e24", "status": "queued", "status_url": "/jobs/cd4272803e0e455e85d9d6def4cf5e24" }
```

## 2. Consulta: `GET /jobs/{job_id}`
```json
{
  "job_id": "cd4272803e0e455e85d9d6def4cf5e24",
  "status": "done",
  "owner": "alice",
  "ops": ["blur", "sobel"],
  "worker_image": "tp3-worker",
  "files": 2,
  "fragments": { "total": 8, "done": 8 },
  "progress_pct": 100.0,
  "timings_s": { "split": 0.0331, "queue": 0.0211, "processing": 0.1276, "join": 0.0429, "total": 0.2306 },
  "workers": ["2591dabe6d14-1c8da6", "5a065dfa4713-969b95", "b37932147ee4-1c9648"],
  "retries": 0,
  "error": null,
  "results": ["/jobs/cd42.../result/0", "/jobs/cd42.../result/1"]
}
```

| Estado | Significado |
|---|---|
| `queued` | Aceptado y esperando el split, o sus fragmentos esperan un worker |
| `processing` | Al menos un worker tomó un fragmento |
| `done` | Todos los archivos están unidos y los resultados disponibles |
| `failed` | Falló la confirmación del envío, el split o el join (ver `error`) |
| `dlq` | Algún fragmento agotó `MAX_RETRIES`. Un admin puede reprocesarlo |

**Tiempos por etapa:** `split` es el particionado, `queue` va del fin del split al primer fragmento tomado, `processing` va del primer fragmento tomado al último resultado, `join` es el armado final y `total` es el tiempo end-to-end desde el submit.

Otros endpoints:
- `GET /jobs/{id}/result/{file_idx}` devuelve `image/png`, o 404 si el job todavía no está `done`.
- `GET /jobs` lista los job_ids propios (los de todos si es admin).
- `GET /stats` (admin) devuelve jobs por estado, profundidad de las colas (incluidas la DLQ y `parked`), workers activos, latencia p50/p95/p99 y tasa de error.
- `POST /admin/dlq/reprocess?max_messages=1000` (admin, límite entre 1 y 1000) reencola los fragmentos estacionados: `{"reprocessed": 3, "jobs": [...]}`.
- `POST /admin/tokens?sub=bob&role=user` (admin) emite tokens.
- `GET /admin/logs?n=100` (admin) devuelve los últimos logs en memoria de la réplica.
- `GET /health` responde `{"backend": "ok", "redis": "ok", "rabbitmq": "ok"}` con 200, o 503 si alguna dependencia está caída.

### Progreso en vivo: `GET /jobs/{job_id}/events`

Requiere el mismo Bearer que la consulta de estado. Un usuario ajeno obtiene **404 antes de abrir el stream**, y un token ausente o inválido, 401. El frontend usa `fetch` con `Authorization`; el token no se envía en la URL ni se guarda en el navegador.

Respuesta `200 text/event-stream`, sin caché ni buffering en nginx:

```text
event: progress
data: {"job_id":"...","status":"processing","progress_pct":50.0,"fragments":{"total":4,"done":2},...}

event: result
data: {"job_id":"...","fragment_id":"0-1","worker_id":"...","attempt":0,...}
```

Los ejemplos están abreviados; `progress` lleva la misma representación completa que `GET /jobs/{id}`. `result` lleva el aviso del worker, guardado por el consumidor `results.monitor` en un Redis Stream de hasta 256 eventos. Se deduplica por fragmento e intento y expira junto al job.

- Siempre se envía un snapshot inicial. El estado se vuelve a consultar como máximo cada segundo mientras Redis responde, incluso si el joiner termina después que el monitor.
- El stream se cierra en `done`, `failed` o `dlq`; para jobs activos emite `reconnect` y cierra a los 55 segundos. El frontend reconecta y vuelve a autorizarse.
- Una reconexión puede repetir los eventos de fragmentos retenidos: es una vista de progreso, no un registro de auditoría con entrega exactamente una vez.
- Si vence el token o falla Redis después de abrir el stream, llega `event: error` con `{error, detail}` y se cierra. El HTTP ya enviado sigue siendo 200.
- El frontend muestra el resultado y el progreso; la vista admin consulta `/stats` cada 5 segundos y se detiene ante un error de permisos.

Cada respuesta incluye `X-Backend-Replica` con el hostname del backend. El script R4 usa este header para comprobar tres contenedores/pods distintos, no solamente tres procesos o veinte requests al mismo backend.

## 3. Errores
Formato común: `{"error": "<codigo>", "detail": "<mensaje legible>"}`

| HTTP | Situación | Ejemplo de body |
|---|---|---|
| 400 | Operación inválida, campos ausentes, formato o parámetros inválidos | `{"error":"unsupported_op","detail":"Operacion(es) no soportada(s): ['rotate']. Permitidas: ['sobel', 'grayscale', 'blur', 'threshold']"}` |
| 401 | Token ausente, inválido o vencido | `{"error":"unauthorized","detail":"Token expirado"}` (el texto puede variar según la causa) |
| 403 | Un usuario accede a una ruta admin | `{"error":"forbidden","detail":"Requiere rol admin"}` |
| 404 | Job inexistente, vencido o ajeno | `{"error":"not_found","detail":"Job inexistente"}` |
| 413 | Archivo por encima del máximo configurado | `{"error":"file_too_large","detail":"'foto.png' supera 100.0 MB"}` |
| 429 | Límite por usuario/minuto compartido entre réplicas | `{"error":"rate_limited","detail":"Maximo 600 requests/minuto"}` |
| 500 | Error inesperado | `{"error":"internal_error","detail":"Error interno"}` |
| 503 | RabbitMQ no confirma la publicación | `{"error":"broker_unavailable","detail":"RabbitMQ no disponible; no se confirmo el envio"}` |
| 503 | Redis no disponible | `{"error":"store_unavailable","detail":"Redis no disponible"}` |
| 503 | El bucket de imágenes no responde tras los reintentos | `{"error":"blob_unavailable","detail":"Almacenamiento de imagenes no disponible"}` |

Los textos incluyen los valores efectivos de configuración. Otros códigos 400: `missing_ops`, `too_many_ops`, `worker_image_not_allowed`, `invalid_image`, `unsupported_format`, `invalid_params`, `too_many_files`, `missing_files`, `invalid_request`, `invalid_role`. Un resultado todavía no listo devuelve `404 not_ready`. Un mensaje estacionado malformado devuelve `500 invalid_dlq_message` y permanece sin ack para revisión.

**Reintentos:** publicación y lecturas Redis usan cinco intentos, con esperas 1/2/4/8 s; el helper general limita el backoff a 30 s. Se reintentan también escrituras idempotentes (guardar un job con el mismo ID, actualizar estado, registrar eventos). Contadores como `INCR` no se repiten automáticamente porque podrían incrementarse dos veces. Los errores de programación Redis no se reintentan.

**Entrega:** publisher confirms y ack manual evitan confirmar un reproceso antes de publicar. Una desconexión después de aceptar un mensaje puede causar reentrega: la garantía es al menos una vez, no exactamente una vez. Las operaciones repartidas entre Redis y RabbitMQ no forman una transacción única. El joiner deduplica fragmentos y el monitor deduplica eventos.

**Expiración:** el job dura 24 h. Sets auxiliares de workers, fragmentos completados, metadatos y eventos tienen vencimiento asociado al job. Índices globales/por usuario/por estado tienen TTL y las consultas eliminan referencias a jobs expirados. Los bytes de entrada/salida viven en el bucket de imágenes (Redis guarda solo el puntero `gs://...`, con TTL de 24 h desde cada escritura) y una regla de lifecycle los borra al día.

## 4. Lo que falta (datos que no devolvemos, pero podríamos)
| Dato | Por qué queda afuera |
|---|---|
| Costo estimado del job (USD) | Requiere tarifar CPU-segundo por tipo de VM y prorratear los nodos compartidos. Es complejo y poco preciso con instancias spot |
| Nodo o región donde corrió cada fragmento | El `worker_id` (hostname) ya lo identifica. Mapearlo a una zona requiere consultar la API de Compute en cada request |
| Fragmentos reasignados desde la DLQ, uno por uno | Devolvemos solo el total (`retries`). El detalle está en los logs del dlq-monitor; exponerlo agranda la respuesta sin un uso claro |
| Tiempo de procesamiento por fragmento | Está en Prometheus (`task_duration_seconds`). Duplicarlo por job en Redis multiplica las escrituras |
| Webhook o WebSocket | El progreso push disponible usa SSE; no se implementan otros transportes |
| Expiración de resultados | Los datos viven 24 h en Redis (TTL). No se informa la fecha exacta de expiración |
