# Servicios

| Servicio | Responsable | Qué hace | Puerto (health y metrics) |
|---|---|---|---|
| [common/](common/) | todos (cambios por PR) | Contratos: colas, claves Redis, auth, operaciones, logging, métricas, retry | n/a |
| [backend/](backend/) | B | API HTTP, validación R2, auth y roles R4, `/stats` | 8000 (`/health`, `/metrics`) |
| [split/](split/) | B | Parte las imágenes en franjas y publica las tareas | 8080 |
| [joiner/](joiner/) | B | Une los fragmentos y marca el job como `done` | 8080 |
| [dlq_monitor/](dlq_monitor/) | B | Reasigna desde la DLQ, estaciona y publica la métrica `tasks_queued` | 8080 |
| [worker/](worker/) | A | Aplica la cadena de operaciones a un fragmento | 8080 |
| [frontend/](frontend/) | B | Página mínima de upload y proxy `/api` hacia el backend | 8080 (`/health`) |

## Desarrollo
```bash
cp .env.example .env              # completar AUTH_SECRET y RABBIT_PASS (y el mismo pass en RABBIT_URL)
docker compose up -d --build --scale worker=3
TOKEN=$(docker compose exec -T backend python /dev/stdin alice user < TP3/scripts/gen_token.py)
curl -H "Authorization: Bearer $TOKEN" -F files=@TP3/loadtest/sample.png -F ops=blur,sobel localhost:8000/jobs
curl -H "Authorization: Bearer $TOKEN" localhost:8000/jobs/<job_id>
# UI: http://localhost:8081   Swagger: http://localhost:8000/docs   RabbitMQ: http://localhost:15672
```

## Tests
```bash
cd TP3/services
pip install ./common pytest -r backend/requirements.txt
python -m pytest -q common/tests backend/tests
```
- **Unitarios**: operaciones, split, join, auth, retry y validación.
- **Integración**: [scripts/r4_evidence.sh](../scripts/r4_evidence.sh) contra el stack levantado.
- TODO (B): tests de integración con pytest contra el compose, que corran en CI.

## Agregar una operación nueva (R2)
1. Implementarla en [ops.py](common/tp3common/ops.py) y registrarla en `OPS` y en `NEIGHBORHOOD`.
2. Sumarla a `ALLOWED_OPS`, en `.env` y en [configmap.yaml](../k8s/base/configmap.yaml).
3. Agregar un test en [test_ops_imaging.py](common/tests/test_ops_imaging.py), incluido el de partir y unir.
