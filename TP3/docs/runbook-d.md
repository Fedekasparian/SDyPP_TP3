# Runbook D — Hit #4 (observabilidad) + R5 (carga) + informe

Guía de reproducción de la evidencia de la parte D. Todos los comandos son de
**Git Bash en Windows**, desde la raíz del repo.

## Estado al 23/10/2026 (día de la entrega)

| | |
|---|---|
| ✅ | `.env`, las 6 imágenes `tp3/*:dev` y las imágenes de V1 (`loadtest/images/`) |
| ✅ | Métricas de RabbitMQ **por cola** y las 4 alertas en formato nativo, validadas |
| ✅ | `run_matrix.sh` arreglado y endurecido (ver "Qué se arregló") |
| ✅ | `summarize.py` reescrito: emite **siempre** las 108 filas esperadas |
| ✅ | **Matriz R5 cerrada: 79 medidas + 29 declaradas = 108, ninguna `SIN MEDIR`** |
| ✅ | 6 capturas de Grafana en `evidencia/hit4/` + `contexto_capturas.txt` |
| ✅ | Paso 8: `ColaDeTareasAlta` y `FragmentosEstacionadosEnDLQ` disparadas y registradas |
| ✅ | Caso de DLQ completo: estacionado → alerta → reproceso → `done` |
| ✅ | Informe: §6 y §8 completas (6.4, 8.4 y 8.6 incluidas), §9, §10 y §11 |
| ✅ | **Tabla del Hit #3: 54 medidas + 66 declaradas = 120, ninguna `SIN MEDIR`** (ver abajo) |
| ✅ | `summarize.py` separa las dos matrices; `gen_images.py` ya no se pasa del tamaño |
| ✅ | **Caso c de R5**: un worker muerto con un fragmento sin ack, reentregado a otro ([evidencia](../evidencia/r5/caso_c_worker_muerto.txt), §8.4 del informe) |
| 🟨 | Observabilidad en GKE: job `observability` propio en `deploy.yml`, secret de Grafana y `PROJECT` resueltos; falta un deploy que lo confirme y las capturas de CPU/memoria |
| 🟨 | Video: guion en [guion-video.md](guion-video.md); falta grabarlo y subirlo |

Pusheado a `feat/d-obs-load`. Los commits los hace D.

### Lo que falta, con el detalle para retomarlo

**1. Caso c de R5 — worker muerto con fragmentos en vuelo.** El paso 8 lo intenta
pero no lo demuestra: `docker compose kill worker` mata *todas* las réplicas y
corrió sin carga en vuelo, así que solo registra el kill. Hay que levantar 3
workers, largar carga liviana (10KB, `VA=10`, `VC=3`, 60 s), matar **un** solo
contenedor con `docker kill <nombre>` a los ~20 s, y después buscar
`reentregado` en los logs de los sobrevivientes (el worker lo imprime cuando
`method.redelivered` es verdadero) y comprobar que los jobs igual terminan.
Está señalado como pendiente en §8.4 del informe.

**2. Observabilidad en GKE.** El paso "Observabilidad (Hit #4)" de
`.github/workflows/deploy.yml` tiene `continue-on-error: true` y timeout de 5 min:
el deploy pasa en verde pero **no instala Prometheus ni Grafana en el cluster**.
Dos causas, las dos en archivos de D:
  - `kube-prometheus-stack-values.yaml` pide `admin.existingSecret: grafana-admin`
    y nadie crea ese secreto; el pod de Grafana queda en `CreateContainerConfigError`
    y el `helm --wait` timeoutea. Hay que crear el secreto en el workflow y agregar
    `tp3-grafana-pass` al `for_each` de `infra/terraform/bootstrap/main.tf`.
  - `additionalScrapeConfigs` tiene `project: PROJECT` literal (el `TODO (D)` del
    scrape de las VMs workers). No rompe el arranque, pero ese job no descubre nada.
Arreglado eso se le saca el `continue-on-error` y se le devuelve el `--timeout 15m`.
Como beneficio, en GKE sí existen cAdvisor y node-exporter, así que se llenarían
los paneles 1 a 4 que en compose quedan vacíos.

**3. Las 66 celdas declaradas del Hit #3 no entran en esta máquina.** La tabla
queda cerrada y sin huecos, pero 66 de las 120 celdas llevan motivo en vez de
números, y el motivo es siempre el mismo: **la memoria del equipo**. Con 13,8 GB
totales y entre 0,4 y 2,7 GB libres, la pasada del 23/10 se murió en la celda 56
de 80 —la mató el entorno por presión de memoria del sistema— y las filas de
10 MB y 100 MB nunca se intentaron. **No es un límite del sistema bajo prueba: es
el banco de pruebas.** Medir el resto exige otra máquina (o el cluster de GKE), no
más intentos en esta.

Si alguna vez hay equipo, las celdas son retomables y este es el orden de valor.
`run_matrix.sh` saltea las que ya tienen JSON, y la medición tiene precedencia
sobre la declaración, así que no hay que borrar nada de `celdas_declaradas.csv`:

  - **Las 26 que se cortaron** (todo `V3=8` y el final de `V3=4`). Son livianas
    (≤ 1 MB) y son las que faltan para cerrar el eje de workers, que es donde
    está el hallazgo de 8.6. `MATRIX=hit3 QUICK=1 INVALID_RATE=0
    V1_LIST="1KB 10KB 100KB 1MB" ./run_matrix.sh`, ~20 min.
  - **Las 20 de `V1=10MB`**: agregar `K6_MEMORY=2g V1_LIST=10MB`. `VC=25` y `50`
    son ~0,5–1,1 GB de cuerpos multipart en vuelo (una copia por VU).
  - **Las 20 de `V1=100MB`** exigen primero `py TP3/loadtest/gen_images.py 100MB`,
    porque la imagen vieja pesaba 105.482.919 bytes y el backend rechaza con 413
    por encima de 104.857.600. El filtro por argumento existe para **no**
    regenerar `10KB.png` ni `1MB.png`, que son las imágenes con las que se midió
    R5. Después, solo `V2_LIST="1 5"`: con `VC=10` son 11 VUs × ~210 MB.

Al terminar, regenerar con `MATRIX=hit3 py TP3/loadtest/summarize.py` y actualizar
los recuentos de §8.6.

---

## Trampas de ESTA máquina (todas costaron tiempo)

| Síntoma | Causa y solución |
|---|---|
| `no pude emitir tokens: 404` con una página HTML de Laravel | **El puerto 8000 está compartido**: hay un servidor `php` en `127.0.0.1:8000` además de Docker en `::`. `curl localhost:8000` sale por IPv6 y llega al FastAPI, pero un contenedor que entra por `host.docker.internal` cae en el loopback IPv4, o sea en el php. Ya resuelto: k6 corre dentro de la red de compose y usa `http://backend:8000`. **No hay que matar el php.** |
| Docker devuelve 500 en toda la API | Una celda agotó la RAM. Matar los procesos de Docker, `wsl --shutdown`, relanzar Docker Desktop (está en `%LOCALAPPDATA%\Programs\DockerDesktop`, **no** en `Program Files`). Ya mitigado con `K6_MEMORY`. |
| Celdas pesadas que se cortan sin dejar JSON | **Mirar la memoria de Redis**: `docker compose exec -T redis redis-cli INFO memory`. Los fragmentos tienen TTL de 24 h, así que durante una sesión de medición **nada expira** y Redis crece con el throughput acumulado (llegó a 2,91 GB con 602.484 claves). Vaciar entre corridas con `docker compose exec -T redis redis-cli FLUSHDB`. |
| `python` no existe | Usar **`py`**. Los scripts ya detectan cuál hay. |
| `-w C:/Program Files/Git/lt` | Git Bash reescribe rutas de Docker. Resuelto con `MSYS_NO_PATHCONV=1` dentro del script. |
| Paneles de CPU/memoria por pod y nodo vacíos | Normal en compose: salen de cAdvisor y node-exporter, que solo existen en k8s. Declarado en el informe §6.3. |
| `(thresholds no cumplidos)` | **No es un error.** Es k6 avisando que esa celda no cumplió el SLO. Va a la columna `slo_ok`. |

## Qué se arregló de `run_matrix.sh` (22/10)

1. **`cd ../../..`** al escalar workers: un nivel de más desde `TP3/loadtest`, caía fuera del repo y moría en la celda cero. Ahora usa `REPO_ROOT`.
2. **k6 entra por la red de compose** (`K6_NETWORK`) en vez de `host.docker.internal`. Ver la tabla de trampas.
3. **El humo guarda con prefijo `smoke`**: antes usaba los mismos nombres de celda que la matriz real, y 8 de las 108 habrían quedado medidas con la meseta corta del humo, sin aviso.
4. **`JOB_TIMEOUT_S`**: antes `TIMEOUT_S` ni se le pasaba a k6 y quedaba en 120 s, con lo que una celda saturada se moría antes de escribir su JSON. Cota: `RAMP + DURATION + 5s + JOB_TIMEOUT_S < CELL_TIMEOUT`.
5. **`K6_MEMORY`** (1500m): techo de memoria del contenedor de k6, para que una celda que no entra muera sola en vez de llevarse puesto el motor de Docker.
6. **`MODE=none`**: no toca los workers. Lo usa el script de evidencia, que los apaga a propósito.

---

## Paso 0 — Carpetas de evidencia (la rama ya existe)

```bash
git branch --show-current          # feat/d-obs-load
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

## Paso 6 — Matriz R5, en pasadas

**No correrla de un saque.** Las celdas no pesan lo mismo: con imágenes de 10 KB
la más pesada mueve 25 MB, pero con las de 1 MB, 50 archivos por request y 50
usuarios son 2,5 GB en vuelo. Partirla en pasadas hace que un fallo en las
pesadas no arrastre lo ya medido, y el script es retomable: saltea toda celda
que ya tenga JSON.

```bash
export ADMIN_TOKEN=$(docker compose exec -T backend python /dev/stdin admin admin < TP3/scripts/gen_token.py)

# Pasada 1: las 54 celdas livianas (~35 min)
QUICK=1 JOB_TIMEOUT_S=30 V1_LIST=10KB ./TP3/loadtest/run_matrix.sh 2>&1 | tee -a TP3/evidencia/r5/corrida_r5.log

# Vaciar Redis entre pasadas (ver la tabla de trampas: si no, se llena y las
# celdas pesadas se cortan)
docker compose exec -T redis redis-cli FLUSHDB

# Pasada 2: 1 MB con VA=1 y VA=10 (36 celdas)
QUICK=1 JOB_TIMEOUT_S=30 V1_LIST=1MB VA_LIST=1  ./TP3/loadtest/run_matrix.sh 2>&1 | tee -a TP3/evidencia/r5/corrida_r5.log
QUICK=1 JOB_TIMEOUT_S=30 V1_LIST=1MB VA_LIST=10 ./TP3/loadtest/run_matrix.sh 2>&1 | tee -a TP3/evidencia/r5/corrida_r5.log

# Pasada 3: 1 MB con VA=50, solo VC 1 y 10 (12 celdas)
QUICK=1 JOB_TIMEOUT_S=30 V1_LIST=1MB VA_LIST=50 VC_LIST="1 10" ./TP3/loadtest/run_matrix.sh 2>&1 | tee -a TP3/evidencia/r5/corrida_r5.log
```

Las 6 celdas restantes (`1MB`, `VA=50`, `VC=50`) no entran en la RAM de esta
máquina y están **declaradas** en `loadtest/celdas_declaradas.csv`.

Al terminar, `py TP3/loadtest/summarize.py` imprime el balance:

```
matriz r5: 108 celdas esperadas | N medidas | 6 declaradas | M SIN MEDIR
```

**Si `M` no es cero, hay que correr esas celdas o declararlas.** El resumen las
lista una por una. Mientras tanto hacer el paso 7.

## Paso 7 — Capturas de Grafana *durante* la corrida

Guardar en `TP3/evidencia/hit4/`:

1. `dashboard_completo.png` — los 10 paneles con datos.
2. `latencia_p50_p95_p99.png` — el panel de latencia.
3. `rabbitmq_mensajes.png` — publicados / consumidos / en cola.
4. `throughput_y_errores.png` — los dos paneles de abajo.

Anotar en un `.txt` al lado qué celda estaba corriendo en cada captura: eso es
la columna **`cuello_de_botella`** del `summary.md`, que se completa a mano.

## Paso 8 — Alerta disparada y casos de falla (entregable del Hit #4 + R5)

Todo automatizado. **No correrlo mientras la matriz esté corriendo**: apaga y
prende workers y les cambia el `FAIL_RATE`.

```bash
export ADMIN_TOKEN=$(docker compose exec -T backend python /dev/stdin admin admin < TP3/scripts/gen_token.py)
./TP3/scripts/evidencia_hit4_r5.sh
```

Tarda ~12 min (la alerta tiene `for: 2m`, así que hay que esperarla de verdad).
Deja:

| Archivo | Qué contiene |
|---|---|
| `evidencia/hit4/alertas_transicion.log` | el estado de las 4 alertas cada 15 s, con hora: `inactive → pending → firing → inactive` |
| `evidencia/r5/stats_dlq.txt` | `/stats` antes y después de `POST /admin/dlq/reprocess` |
| `evidencia/r5/casos_falla.log` | los 3 casos: operación inexistente, `FAIL_RATE=0.3` y worker muerto en caliente |

El log de transiciones es evidencia **que no depende de que el navegador
responda**, y muestra los horarios exactos. Las capturas de pantalla de
`/alerts` en rojo son el complemento, no el sustituto.

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
