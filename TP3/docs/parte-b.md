# Parte B: aplicación, contrato e integración

Estado al **20/10/2026 (Argentina)**. Implementación y validación local realizadas en `feat/b-backend`. La corrida R4 en GKE requiere el despliegue del frente C.

## Entregables del plan

| Punto | Estado | Ubicación / evidencia |
|---|---|---|
| Contrato R3, estados, progreso, tiempos, workers, retries y errores | Actualizado | [contrato.md](contrato.md) |
| Submit sin bloquear el event loop | Implementado y probado | `backend/main.py`, `test_runtime.py` |
| Backoff de publicación y Redis en ejecución | Implementado y probado | `retry.py`, `store.py`, `test_runtime.py` |
| TTL en claves secundarias e índices sin jobs vencidos | Implementado y probado | `store.py`, worker, joiner, `test_integration.py` |
| Manejo de errores en reproceso de DLQ | Implementado y probado | Confirmación antes de ack; mensaje sin ack ante error |
| Recuperación del hilo de profundidad de colas | Implementado y probado | `dlq_monitor/main.py`, `test_runtime.py` |
| Health de Redis y RabbitMQ | Implementado y probado | `/health`, pruebas unitarias y de integración |
| Consumidor de progreso del fanout | Implementado y probado | Redis Stream acotado, deduplicado y con TTL |
| SSE y frontend con progreso / admin | Implementado y probado | [Captura admin](../evidencia/frontend_admin.png), [prueba de navegador](../evidencia/frontend_check.txt) |
| Tests de integración y servicios reales en CI | Implementado | [test_integration.py](../services/backend/tests/test_integration.py), `.github/workflows/ci.yml` |
| Evidencia R4 local, tres réplicas | **13 OK, 0 FAIL** | [r4_local.txt](../evidencia/r4_local.txt), [contenedores](../evidencia/r4_local_containers.txt) |
| Evidencia R4 en GKE | **Pendiente de C** | Script preparado; falta entorno/contexto y tokens de GKE |
| README de servicios, arquitectura y decisiones | Actualizado | [services/README.md](../services/README.md), [arquitectura.md](arquitectura.md) |

## Validación registrada

- **58 pruebas pytest pasando**, incluidas **13 pruebas de integración** con Redis 7.4 y RabbitMQ 3.13 reales. Ejecución verificada tanto con Python 3.11 local como con Python 3.12 en contenedor: [salida Python 3.12](../evidencia/pytest_python312.txt).
- Integración verifica salida de imagen igual al cálculo centralizado, no solo códigos HTTP. Usa colas con prefijo aleatorio y base Redis exclusiva.
- Stack completo ejecutado en Docker Desktop: tres contenedores backend y tres workers, más split, joiner, dlq-monitor, RabbitMQ, Redis y frontend.
- R4 identifica tres hostnames diferentes en `X-Backend-Replica`, realiza 30 consultas autorizadas, verifica 401/403/404, progreso SSE, job `done` y descarga PNG.
- Navegador Chrome: upload → progreso SSE → imagen final; rechazo del panel admin para usuario común; estadísticas reales con token admin; pantalla móvil sin desborde; sin errores JavaScript.
- Se reprodujo y corrigió el 502 del proxy tras recrear backends: Compose espera sus health checks y reinicia frontend para renovar resolución DNS.

Los timestamps de los archivos de evidencia están en UTC; `2026-10-21 01:43` corresponde al `20/10/2026 22:43` en Argentina. No contienen tokens ni contraseñas.

## Cómo probar y demostrar

Los comandos completos están en [services/README.md](../services/README.md). Para la demo:

1. Levantar `docker-compose.yml` junto a `docker-compose.r4.yml`, con tres backends y tres workers.
2. Abrir `http://localhost:8081`, ingresar token de usuario, subir imagen y encadenar `blur,sobel`.
3. Mostrar progreso y resultado. Intentar estadísticas con usuario común: debe fallar por permisos.
4. Usar token admin y mostrar colas, workers, latencias y tasa de error.
5. Correr `r4_evidence.sh` y mostrar tres réplicas distintas y cero fallos.

## Integración con C y D

- **C:** reconstruir todos los servicios Python porque cambia `tp3common`; desplegar esta rama integrada en GKE; entregar contexto Kubernetes/URL y tokens del entorno para correr R4. En GKE debe usarse `K8S=1` y guardarse la salida real como `TP3/evidencia/r4_gke.txt`.
- **D:** `/stats` sigue disponible para admin; progreso adicional en `/jobs/{id}/events`. La prueba local no sustituye R5 ni demuestra rendimiento en nube. El frontend muestra p95 y tasa de error; la respuesta conserva p50/p95/p99.
- Las colas existentes y sus payloads conservan compatibilidad. Los índices Redis siguen siendo sets. Nuevas claves: `job:{id}:events` y `job:{id}:events:seen`.

## Alcance pendiente

No se ejecutó R4 en GKE ni en minikube: este equipo no tenía contexto Kubernetes configurado. La evidencia incluida corresponde exclusivamente a Docker Compose. No se provisionaron recursos GCP ni se modificó el frente C. El informe final y el video los integra D.
