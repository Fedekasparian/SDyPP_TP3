# Contrato de la API (R3)

**Responsable: Integrante B**. La especificación OpenAPI completa la genera FastAPI en `GET /openapi.json`, con UI en `/docs`. Para guardarla en el repo: `curl localhost:8000/openapi.json > TP3/docs/openapi.json`.

API **asincrónica**: el envío responde enseguida con un `job_id`, y el resultado se consulta después.

## Autenticación
Todas las rutas, salvo `/health`, requieren `Authorization: Bearer <token>`. El token es un HMAC-SHA256 firmado sobre `{sub, role, exp}` ([auth.py](../services/common/tp3common/auth.py)). Los roles son:
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
| `failed` | Error no recuperable en el split o el join (ver `error`) |
| `dlq` | Algún fragmento agotó `MAX_RETRIES`. Un admin puede reprocesarlo |

**Tiempos por etapa:** `split` es el particionado, `queue` va del fin del split al primer fragmento tomado, `processing` va del primer fragmento tomado al último resultado, `join` es el armado final y `total` es el tiempo end-to-end desde el submit.

Otros endpoints:
- `GET /jobs/{id}/result/{file_idx}` devuelve `image/png`, o 404 si el job todavía no está `done`.
- `GET /jobs` lista los job_ids propios (los de todos si es admin).
- `GET /stats` (admin) devuelve jobs por estado, profundidad de las colas (incluidas la DLQ y `parked`), workers activos, latencia p50/p95/p99 y tasa de error.
- `POST /admin/dlq/reprocess` (admin) reencola los fragmentos estacionados: `{"reprocessed": 3, "jobs": [...]}`.
- `POST /admin/tokens?sub=bob&role=user` (admin) emite tokens.
- `GET /admin/logs?n=100` (admin) devuelve los últimos logs en memoria de la réplica.
- `GET /health` responde `{"backend": "ok", "redis": "ok"}` con 200, o 503 si alguna dependencia está caída.

## 3. Errores
Formato común: `{"error": "<codigo>", "detail": "<mensaje legible>"}`

| HTTP | Cuándo | Ejemplo de `error` |
|---|---|---|
| 400 | Operación no soportada, imagen de worker no permitida, archivo corrupto o con formato no permitido, `params` inválido, demasiados archivos u operaciones | `unsupported_op`, `worker_image_not_allowed`, `invalid_image`, `unsupported_format`, `invalid_params`, `too_many_files` |
| 401 | Falta el token, o es inválido o está vencido | `unauthorized` |
| 403 | Un `user` intenta usar una ruta admin (`/stats`, `/admin/*`) | `forbidden` |
| 404 | El job no existe **o pertenece a otro usuario** (no revelamos que existe), o el resultado todavía no está listo | `not_found`, `not_ready` |
| 413 | Un archivo supera `MAX_FILE_MB` | `file_too_large` |
| 429 | Se superó `RATE_LIMIT_PER_MIN` requests por usuario y por minuto (contador en Redis, compartido por todas las réplicas) | `rate_limited` |
| 500 | Error inesperado del servidor | `internal_error` |
| 503 | RabbitMQ o Redis no disponible al encolar | `broker_unavailable` |

## 4. Lo que falta (datos que no devolvemos, pero podríamos)
| Dato | Por qué queda afuera |
|---|---|
| Costo estimado del job (USD) | Requiere tarifar CPU-segundo por tipo de VM y prorratear los nodos compartidos. Es complejo y poco preciso con instancias spot |
| Nodo o región donde corrió cada fragmento | El `worker_id` (hostname) ya lo identifica. Mapearlo a una zona requiere consultar la API de Compute en cada request |
| Fragmentos reasignados desde la DLQ, uno por uno | Devolvemos solo el total (`retries`). El detalle está en los logs del dlq-monitor; exponerlo agranda la respuesta sin un uso claro |
| Tiempo de procesamiento por fragmento | Está en Prometheus (`task_duration_seconds`). Duplicarlo por job en Redis multiplica las escrituras |
| Notificación push (webhook o websocket) al terminar | El fanout `results` lo permitiría. Queda fuera por alcance: el cliente hace polling |
| Expiración de resultados | Los datos viven 24 h en Redis (TTL). No se informa la fecha exacta de expiración |
