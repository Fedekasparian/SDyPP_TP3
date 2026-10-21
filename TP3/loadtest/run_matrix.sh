#!/usr/bin/env bash
# =============================================================================
# MACHETE: que es esto y por que esta escrito asi
# =============================================================================
# Corre la matriz de pruebas de carga del Hit #3 y de R5, y deja un JSON por
# celda en results/. Despues summarize.py junta todo en summary.csv/md.
#
# 1) QUE PIDE LA CONSIGNA (y por que son 108 celdas)
#    R5 exige cruzar VA x VB x VC con "al menos 2 valores de V1 y 2 de V3":
#      VA = archivos por request        -> 1, 10, 50
#      VB = operaciones encadenadas     -> 1, 2, 3   (sobel | blur,sobel | grayscale,blur,sobel)
#      VC = usuarios concurrentes       -> 1, 10, 50 (mas 1 bot SIN token, que debe dar 401)
#      V1 = tamanio de la imagen        -> 2 valores (10KB y 1MB)
#      V3 = cantidad de workers         -> 2 valores (2 y 6)
#    3*3*3*2*2 = 108 celdas. Las 108 hay que correrlas: el recorte NO va por
#    sacar celdas (romperia la matriz que pide la consigna) sino por acortar
#    cada celda. Ver (3).
#
# 2) MODOS
#    MATRIX=r5    -> la matriz de R5 descrita arriba (default)
#    MATRIX=hit3  -> la del Hit #3: V1 (1KB..100MB) x V2 (concurrencia) x V3,
#                    con VA=1 y VB=sobel, porque ahi la variable es el tamanio.
#    SMOKE=1      -> 8 celdas cortas (~3 min). CORRER ESTO PRIMERO:
#                    valida que el stack, los tokens y k6 andan antes de
#                    largar una corrida de una hora.
#
# 3) DURACION
#    Cada celda = RAMP + DURATION + 5s de bajada. Con los defaults (10s+60s)
#    son 75s x 108 = ~2h15. Con QUICK=1 (5s+20s) son ~30s x 108 = ~1h.
#    Lo que se recorta es la *meseta*, no la matriz: hay que declararlo en el
#    informe ("meseta de 20 s por celda por limite de tiempo de maquina").
#
# 4) ES RETOMABLE
#    Si una celda ya tiene su JSON en results/, la saltea. Si se corta la
#    corrida (o cerras la notebook), volves a lanzar el mismo comando y sigue
#    donde quedo. Para rehacer una celda, borra su JSON.
#
# 5) ESCALADO DE WORKERS (V3), segun MODE
#    MODE=compose  docker compose up -d --scale worker=N      (local, default)
#    MODE=k8s      kubectl -n tp3 scale deploy/worker --replicas=N
#    MODE=manual   pausa y pide escalar a mano (VMs de workers.yml en GCP)
#
# 6) ERRORES TIPICOS
#    - "definir ADMIN_TOKEN": falta el token admin. Ver COMO PROBARLO abajo.
#    - "no pude emitir tokens: 401": el ADMIN_TOKEN no coincide con el
#      AUTH_SECRET del backend (pasa si recreaste el .env y no reiniciaste).
#    - Celdas con error 100%: casi siempre el backend no esta levantado.
#      Probar primero:  curl $BASE_URL/health
#    - "(thresholds no cumplidos)": NO es un fallo del script. Es k6 avisando
#      que esa celda no cumplio el SLO. Es un dato, va a la columna slo_ok.
#
# =============================================================================
# COMO PROBARLO (local, Windows + Git Bash)
# =============================================================================
#   1. Levantar el stack con observabilidad:
#        docker compose --profile obs up -d --scale worker=2
#   2. Generar las imagenes de V1 (una sola vez):
#        py TP3/loadtest/gen_images.py
#   3. Emitir el token admin (lee AUTH_SECRET de adentro del contenedor):
#        export ADMIN_TOKEN=$(docker compose exec -T backend python /dev/stdin admin admin < TP3/scripts/gen_token.py)
#        echo "$ADMIN_TOKEN"      # no tiene que estar vacio
#   4. Humo (3 min), para validar que todo anda:
#        SMOKE=1 ./TP3/loadtest/run_matrix.sh
#   5. La matriz completa (dejarla corriendo y mientras escribir el informe):
#        QUICK=1 ./TP3/loadtest/run_matrix.sh
#   6. Resultados: TP3/loadtest/results/summary.md
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

: "${ADMIN_TOKEN:?definir ADMIN_TOKEN (ver COMO PROBARLO en la cabecera de este script)}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
MATRIX="${MATRIX:-r5}"
MODE="${MODE:-compose}"
INVALID_RATE="${INVALID_RATE:-0.05}"
SMOKE="${SMOKE:-0}"
QUICK="${QUICK:-0}"
CELL_TIMEOUT="${CELL_TIMEOUT:-300}"   # corta una celda colgada para no perder la noche

# Guardamos lo que vino por entorno ANTES de aplicar los defaults de la matriz,
# para que el modo SMOKE pueda distinguir "no me pasaron nada" de "me pasaron
# esto". Si no, al llegar al bloque SMOKE las listas ya tienen los valores de
# la matriz R5 y los overrides no tendrian efecto.
ENV_V1_LIST="${V1_LIST:-}"; ENV_V3_LIST="${V3_LIST:-}"
ENV_VA_LIST="${VA_LIST:-}"; ENV_VB_LIST="${VB_LIST:-}"; ENV_VC_LIST="${VC_LIST:-}"

if [[ "$QUICK" == "1" ]]; then
  DURATION="${DURATION:-20s}"; RAMP="${RAMP:-5s}"
else
  DURATION="${DURATION:-60s}"; RAMP="${RAMP:-10s}"
fi
mkdir -p results

# --- Con que corremos k6 -----------------------------------------------------
# Si no esta el binario, usamos la imagen oficial. Ojo: adentro del contenedor
# "localhost" es el contenedor mismo, asi que hay que reescribir BASE_URL a
# host.docker.internal para que k6 vea el backend de la maquina.
# (el `timeout` va adentro de la funcion: `timeout` no puede envolver una
#  funcion de shell, solo un comando real)
if command -v k6 >/dev/null 2>&1; then
  K6_RUNNER="binario local"
  K6_BASE_URL="$BASE_URL"
  k6_run() { timeout "$CELL_TIMEOUT" k6 run "$@"; }
else
  K6_RUNNER="imagen docker grafana/k6:0.54.0"
  K6_BASE_URL="${BASE_URL/localhost/host.docker.internal}"
  K6_BASE_URL="${K6_BASE_URL/127.0.0.1/host.docker.internal}"
  # MSYS_NO_PATHCONV=1 es obligatorio en Git Bash (Windows): si no, reescribe
  # las rutas del contenedor y "-w /lt" le llega a docker como
  # "-w C:/Program Files/Git/lt". En Linux/macOS la variable se ignora.
  k6_run() {
    MSYS_NO_PATHCONV=1 timeout "$CELL_TIMEOUT" docker run --rm -i \
      --add-host=host.docker.internal:host-gateway \
      -v "$(pwd):/lt" -w /lt grafana/k6:0.54.0 run "$@"
  }
fi

# --- Con que corremos python (en Windows suele ser `py`, no `python`) --------
PY=""
for cand in python py python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "pass" >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done

# --- Definicion de la matriz -------------------------------------------------
if [[ "$MATRIX" == "r5" ]]; then
  V1_LIST="${V1_LIST:-10KB 1MB}"; V3_LIST="${V3_LIST:-2 6}"
  VA_LIST="${VA_LIST:-1 10 50}";  VC_LIST="${VC_LIST:-1 10 50}"
  VB_LIST="${VB_LIST:-sobel blur,sobel grayscale,blur,sobel}"
else
  V1_LIST="${V1_LIST:-1KB 10KB 100KB 1MB 10MB 100MB}"; V3_LIST="${V3_LIST:-1 2 4 8}"
  VA_LIST="1"; VB_LIST="sobel"; VC_LIST="${V2_LIST:-1 5 10 25 50}"
fi

# SMOKE: 8 celdas que tocan los dos extremos de V1, VA y VC (chica/sola y
# grande/concurrente), para validar el pipeline completo en pocos minutos.
# Ojo: usa ${VAR:-default} para que SMOKE igual respete lo que le pases por
# entorno. Asi sirve tambien para los casos de falla de R5, por ejemplo
#   SMOKE=1 VB_LIST=sobel,rotate ./run_matrix.sh     (operacion inexistente)
#   SMOKE=1 VA_LIST=50 VC_LIST=10 ./run_matrix.sh    (llenar la cola)
if [[ "$SMOKE" == "1" ]]; then
  V1_LIST="${ENV_V1_LIST:-10KB 1MB}"; V3_LIST="${ENV_V3_LIST:-2}"
  VA_LIST="${ENV_VA_LIST:-1 10}";     VC_LIST="${ENV_VC_LIST:-1 10}"
  VB_LIST="${ENV_VB_LIST:-sobel}";    DURATION="10s"; RAMP="3s"
  echo "### SMOKE: celdas cortas, solo para validar que el stack responde."
fi

ncells=0
for v3 in $V3_LIST; do for v1 in $V1_LIST; do for va in $VA_LIST; do
  for vb in $VB_LIST; do for vc in $VC_LIST; do ncells=$((ncells + 1)); done; done
done; done; done

k6_note=""
[[ "$K6_BASE_URL" != "$BASE_URL" ]] && k6_note="(k6 lo ve como $K6_BASE_URL)"
smoke_note=""
[[ "$SMOKE" == "1" ]] && smoke_note="(SMOKE)"

cat <<EOF
--------------------------------------------------------------------
Matriz      : $MATRIX $smoke_note
Celdas      : $ncells   (las que ya tengan JSON en results/ se saltean)
Por celda   : ramp $RAMP + meseta $DURATION + 5s   (timeout ${CELL_TIMEOUT}s)
k6          : $K6_RUNNER
Backend     : $BASE_URL $k6_note
Escalado V3 : MODE=$MODE
--------------------------------------------------------------------
EOF

scale_workers() {
  echo "--> escalando workers a $1"
  case "$MODE" in
    compose) (cd ../../.. && docker compose up -d --no-deps --scale worker="$1" worker) ;;
    k8s) kubectl -n tp3 scale deploy/worker --replicas="$1" && kubectl -n tp3 rollout status deploy/worker ;;
    manual) read -rp "Escalar workers a $1 y presionar Enter..." ;;
  esac
  sleep 10
}

i=0
for v3 in $V3_LIST; do
  scale_workers "$v3"
  for v1 in $V1_LIST; do
    for va in $VA_LIST; do
      for vb in $VB_LIST; do
        nb=$(tr -cd ',' <<<"$vb" | wc -c); nb=$((nb + 1))
        for vc in $VC_LIST; do
          i=$((i + 1))
          cell="${MATRIX}_V1-${v1}_V3-${v3}_VA-${va}_VB-${nb}_VC-${vc}"
          if [[ -f "results/$cell.json" ]]; then
            echo "[$i/$ncells] skip $cell (ya corrida)"
            continue
          fi
          echo "[$i/$ncells] ==> $cell"
          # IMAGE es relativa al .js (k6/), no a loadtest/: de ahi el ../
          k6_run --quiet --summary-export "results/$cell.json" \
            -e BASE_URL="$K6_BASE_URL" -e ADMIN_TOKEN="$ADMIN_TOKEN" -e IMAGE="../images/$v1.png" \
            -e VA="$va" -e OPS="$vb" -e VC="$vc" -e DURATION="$DURATION" -e RAMP="$RAMP" \
            -e INVALID_RATE="$INVALID_RATE" k6/job.js \
            || echo "   (thresholds no cumplidos o celda cortada por timeout: es un dato, sigue)"
        done
      done
    done
  done
done

if [[ -n "$PY" ]]; then
  "$PY" summarize.py
else
  echo "!! No encontre python/py en el PATH. Corre a mano:  py TP3/loadtest/summarize.py"
fi
