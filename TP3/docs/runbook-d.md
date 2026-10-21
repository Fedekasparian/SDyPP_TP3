# Runbook D — Hit #4 (observabilidad) + R5 (carga) + informe

Guía de reproducción de la evidencia de la parte D. Todos los comandos son de
**Git Bash en Windows**, desde la raíz del repo.

## Estado al 21/10/2026 (lo ya hecho)

| | |
|---|---|
| ✅ | `.env` creado con `RABBIT_PASS` y `AUTH_SECRET` generados (está en `.gitignore`, **no se commitea**) |
| ✅ | Las 6 imágenes `tp3/*:dev` construidas, y RabbitMQ, Redis, Prometheus, Grafana y `grafana/k6:0.54.0` descargadas |
| ✅ | Métricas de RabbitMQ **por cola** activadas (`observability/rabbitmq/prometheus.conf`, montado en compose y en `k8s/infra/rabbitmq.yaml`) |
| ✅ | `observability/alerts-compose.yml`: las 4 alertas en formato nativo + `rule_files` en `prometheus-compose.yml`. Validadas con `promtool` (4 rules found) |
| ✅ | `loadtest/run_matrix.sh` reescrito: detecta k6 (binario o Docker), detecta `py`/`python`, modo `SMOKE`, modo `QUICK`, timeout por celda y es retomable |
| ⬜ | Correr la matriz y capturar la evidencia → **pasos 1 a 8** |
| ⬜ | Escribir el informe → **paso 9** |
| ⬜ | Guion y grabación del video (coordina D) |

**No hay rama `feat/d-obs-load` todavía.** Crearla antes de empezar (paso 0).

---

## Paso 0 — Rama

```bash
git checkout main && git pull
git checkout -b feat/d-obs-load
mkdir -p TP3/evidencia/hit4 TP3/evidencia/r5
```

## Paso 1 — Levantar el stack con observabilidad

Docker Desktop tiene que estar abierto (el ícono de la ballena sin "starting").

```bash
docker compose --profile obs up -d --scale worker=2
docker compose ps          # todos "running"; rabbitmq y redis "healthy"
```

## Paso 2 — Verificar que todo responde (antes de medir nada)

```bash
curl -s http://localhost:8000/health          # {"backend":"ok", ...}
```

Y en el navegador:

- `http://localhost:9090/targets` → los jobs **backend**, **consumers** y **rabbitmq** en `UP`. Si `consumers` está en rojo, los workers no exponen `/metrics`: revisar `docker compose logs worker`.
- `http://localhost:9090/alerts` → las 4 alertas listadas en verde (`Inactive`). **Que aparezcan es la prueba de que `rule_files` quedó bien.**
- `http://localhost:3000` → Grafana (login anónimo como Admin), carpeta **TP3**, dashboard *TP3 - Sobel distribuido*, 10 paneles.

> Los paneles **CPU/memoria por pod** y **por nodo** quedan vacíos en
> docker-compose: salen de cAdvisor y node-exporter, que solo existen en
> Kubernetes. **Esto hay que declararlo en el informe**, o conseguir la captura
> en GKE cuando C lo tenga levantado.

## Paso 3 — Imágenes de V1 (una sola vez)

```bash
py -m pip install numpy pillow     # si falta
py TP3/loadtest/gen_images.py      # -> TP3/loadtest/images/{1KB..100MB}.png
```

## Paso 4 — Token admin

```bash
export ADMIN_TOKEN=$(docker compose exec -T backend python /dev/stdin admin admin < TP3/scripts/gen_token.py)
echo "$ADMIN_TOKEN"      # NO tiene que estar vacío
```

Si sale vacío, el backend no arrancó: `docker compose logs backend | tail -30`.

## Paso 5 — Humo (≈3 min). **No saltearlo.**

```bash
SMOKE=1 ./TP3/loadtest/run_matrix.sh
```

8 celdas cortas. Si acá hay 100% de error, no tiene sentido largar la matriz
larga. Al final imprime el resumen; revisar que `tasa_error` sea baja y que
`p95_s` tenga un número (no `nan`).

## Paso 6 — Matriz R5 completa (≈1 h, dejarla corriendo)

```bash
QUICK=1 ./TP3/loadtest/run_matrix.sh 2>&1 | tee TP3/evidencia/r5/corrida_r5.log
```

108 celdas (VA×VB×VC × 2 de V1 × 2 de V3), meseta de 20 s cada una. Es
retomable: si se corta, el mismo comando sigue donde quedó.

Mientras corre, hacer el paso 7. Al final queda
`TP3/loadtest/results/summary.md`, que es la tabla de R5.

## Paso 7 — Capturas de Grafana *durante* la corrida

Guardar en `TP3/evidencia/hit4/`:

1. `dashboard_completo.png` — los 10 paneles con datos.
2. `latencia_p50_p95_p99.png` — el panel de latencia.
3. `rabbitmq_mensajes.png` — publicados / consumidos / en cola.
4. `throughput_y_errores.png` — los dos paneles de abajo.

Anotar en un `.txt` al lado qué celda estaba corriendo en cada captura: eso es
la columna **`cuello_de_botella`** del `summary.md`, que se completa a mano.

## Paso 8 — Disparar la alerta (entregable del Hit #4)

```bash
docker compose stop worker                       # nadie consume
SMOKE=1 VA_LIST=50 VC_LIST=10 ./TP3/loadtest/run_matrix.sh   # mete >100 fragmentos
```

En `http://localhost:9090/alerts`: `ColaDeTareasAlta` pasa a **PENDING** y a los
2 minutos (`for: 2m`) a **FIRING** en rojo. Capturar los dos estados:
`TP3/evidencia/hit4/alerta_pending.png` y `alerta_firing.png`.

```bash
docker compose start worker      # vuelve a verde: capturar también la recuperación
```

### Casos de falla de R5 (hay que reportar cuántos a error claro, DLQ y reprocesados)

```bash
# a) operación inexistente -> debe dar 100% de 400, sin tocar la cola
SMOKE=1 VB_LIST=sobel,rotate ./TP3/loadtest/run_matrix.sh

# b) workers que fallan el 30% -> fuerza el camino de reintentos y DLQ
FAIL_RATE=0.3 docker compose up -d --no-deps worker
SMOKE=1 ./TP3/loadtest/run_matrix.sh
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/stats
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/admin/dlq/reprocess

# c) worker que muere en medio de un job -> el fragmento se reasigna
docker compose kill worker
```

Guardar las salidas de `/stats` (antes y después del reproceso) en
`TP3/evidencia/r5/stats_dlq.txt`.

```bash
FAIL_RATE=0 docker compose up -d --no-deps worker    # dejar los workers sanos
```

## Paso 9 — Informe

`TP3/docs/informe.md`, secciones de D:

- **§6 Hit #4**: capturas del paso 7 y 8, qué métricas se instrumentaron y por qué, y la limitación de CPU/memoria por pod en compose.
- **§8 Desempeño**: config de k6 (VUs, ramp-up, duración, y **declarar la meseta de 20 s** y por qué), la tabla de `summary.md`, la tabla del Hit #3, los casos de falla y los gráficos.
- **§9 Marco conceptual**: NIST SP 800-145 (las 5 características), cloud native vs híbrido, cloud-bursting y offloading, y CAP en RabbitMQ (quorum queues = Raft = CP) vs Redis (réplica asincrónica = AP).
- **§10 Herramientas de IA** y **§11 Conclusiones**.

## Paso 10 — Cerrar

```bash
docker compose --profile obs down          # -v si además querés borrar los volúmenes
```

---

## Errores típicos

| Síntoma | Causa |
|---|---|
| `definir ADMIN_TOKEN` | Falta el paso 4. El `export` se pierde al cerrar la terminal. |
| `no pude emitir tokens: 401` | El token no coincide con el `AUTH_SECRET` del backend. Rehacer el paso 4 (y si recreaste el `.env`, `docker compose up -d --force-recreate backend`). |
| `-w C:/Program Files/Git/lt` | Git Bash reescribe rutas de Docker. Ya está resuelto con `MSYS_NO_PATHCONV=1` dentro del script. |
| `(thresholds no cumplidos)` | **No es un error.** Es k6 avisando que esa celda no cumplió el SLO. Es un dato: va a la columna `slo_ok`. |
| Paneles de CPU/memoria vacíos | Normal en docker-compose (ver paso 2). |
| Celdas con 100% de error | El backend no está levantado. `curl localhost:8000/health`. |
