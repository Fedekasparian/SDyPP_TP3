#!/usr/bin/env bash
# =============================================================================
# Paso 8 del runbook D: dispara la alerta ColaDeTareasAlta y produce los casos
# de falla de R5, guardando toda la evidencia en TP3/evidencia/.
#
# NO correr mientras la matriz R5 esta corriendo: este script apaga y prende
# workers, y le cambia el FAIL_RATE. Arruinaria las celdas en curso.
#
# COMO USARLO
#   export ADMIN_TOKEN=$(docker compose exec -T backend python /dev/stdin admin admin < TP3/scripts/gen_token.py)
#   ./TP3/scripts/evidencia_hit4_r5.sh
#
# Deja:
#   evidencia/hit4/alertas_transicion.log   inactive -> pending -> firing -> inactive, con hora
#   evidencia/r5/stats_dlq.txt              /stats antes y despues del reproceso
#   evidencia/r5/casos_falla.log            salida completa de los 3 casos
# =============================================================================
set -uo pipefail          # sin -e: varios pasos "fallan" a proposito
cd "$(dirname "$0")/../.."
REPO_ROOT="$(pwd)"

: "${ADMIN_TOKEN:?definir ADMIN_TOKEN (ver cabecera)}"
PROM="${PROM:-http://localhost:9090}"
API="${API:-http://localhost:8000}"
EV_HIT4="TP3/evidencia/hit4"
EV_R5="TP3/evidencia/r5"
mkdir -p "$EV_HIT4" "$EV_R5"

PY=""
# Ojo (Windows): existe un `python` que es el stub de la Microsoft Store.
# `command -v` lo encuentra, pero no ejecuta nada y sale sin imprimir una linea,
# asi que todas las muestras de alertas salian vacias y el log quedaba en puros
# "---". Hay que PROBARLO, no solo buscarlo: es lo que ya hace run_matrix.sh.
for cand in python py python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "pass" >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done
[[ -z "$PY" ]] && { echo "no encontre python/py en el PATH"; exit 1; }

# Estado de las 4 alertas en una linea, con hora. Es la evidencia que no
# depende de que el navegador responda.
estado_alertas() {
  curl -s --max-time 10 "$PROM/api/v1/rules" | "$PY" -c "
import sys, json, datetime
try:
    d = json.load(sys.stdin)
except Exception:
    print('  (prometheus no respondio)'); sys.exit()
ahora = datetime.datetime.now().strftime('%H:%M:%S')
for g in d['data']['groups']:
    for r in g['rules']:
        if r.get('type') != 'alerting':
            continue
        n = len(r.get('alerts', []))
        print(f\"{ahora}  {r['name']:30} {r.get('state','?'):8} activas={n}\")
"
}

# Mira el estado cada 15s durante N segundos.
vigilar() {
  local etiqueta="$1" segundos="$2" t0
  t0=$(date +%s)
  echo "### $etiqueta" | tee -a "$EV_HIT4/alertas_transicion.log"
  while (( $(date +%s) - t0 < segundos )); do
    estado_alertas | tee -a "$EV_HIT4/alertas_transicion.log"
    echo "---" >> "$EV_HIT4/alertas_transicion.log"
    sleep 15
  done
}

echo "=== Estado inicial (todas deberian estar inactive) ==="
: > "$EV_HIT4/alertas_transicion.log"
vigilar "ESTADO INICIAL" 1

# -----------------------------------------------------------------------------
# 1. Disparar ColaDeTareasAlta: apagar los workers y llenar la cola.
# -----------------------------------------------------------------------------
echo
echo "=== 1. Disparando ColaDeTareasAlta (apago los workers) ==="
docker compose stop worker
# VA=50 archivos x FRAGMENTS_PER_IMAGE=4 = 200 fragmentos, por encima del umbral de 100.
SMOKE=1 VA_LIST=50 VC_LIST=10 V1_LIST=10KB V3_LIST=0 \
  MODE=none JOB_TIMEOUT_S=10 CELL_TIMEOUT=120 \
  ./TP3/loadtest/run_matrix.sh >> "$EV_R5/casos_falla.log" 2>&1 || true

echo "   cola cargada. La alerta tiene for: 2m, asi que vigilo 4 minutos."
vigilar "DESPUES DE LLENAR LA COLA (esperando PENDING y luego FIRING)" 240

# -----------------------------------------------------------------------------
# 2. Recuperacion: volver a prender los workers y ver la alerta apagarse.
# -----------------------------------------------------------------------------
echo
echo "=== 2. Recuperacion (prendo los workers) ==="
docker compose start worker
vigilar "DESPUES DE PRENDER LOS WORKERS (deberia volver a inactive)" 120

# -----------------------------------------------------------------------------
# 3. Casos de falla de R5
# -----------------------------------------------------------------------------
echo
echo "=== 3a. Operacion inexistente -> 400, sin tocar la cola ==="
{
  echo "##### CASO a: operacion inexistente (rotate) -> debe dar 400"
  SMOKE=1 VB_LIST=sobel,rotate V1_LIST=10KB VA_LIST=1 VC_LIST=1 V3_LIST=2 \
    JOB_TIMEOUT_S=15 ./TP3/loadtest/run_matrix.sh 2>&1
} >> "$EV_R5/casos_falla.log"

echo "=== 3b. Workers que fallan el 30% -> reintentos y DLQ ==="
FAIL_RATE=0.3 docker compose up -d --no-deps worker
{
  echo "##### CASO b: FAIL_RATE=0.3 -> fuerza reintentos y DLQ"
  SMOKE=1 V1_LIST=10KB VA_LIST=10 VC_LIST=10 V3_LIST=2 \
    JOB_TIMEOUT_S=20 ./TP3/loadtest/run_matrix.sh 2>&1
} >> "$EV_R5/casos_falla.log"

echo "   esperando a que los reintentos se agoten y caigan en la DLQ..."
sleep 30
vigilar "CON FAIL_RATE=0.3 (deberia aparecer FragmentosEstacionadosEnDLQ)" 90

echo "=== 3c. /stats antes y despues de reprocesar la DLQ ==="
{
  echo "########## /stats ANTES del reproceso  ($(date +%H:%M:%S))"
  curl -s --max-time 15 -H "Authorization: Bearer $ADMIN_TOKEN" "$API/stats"
  echo
  echo "########## POST /admin/dlq/reprocess   ($(date +%H:%M:%S))"
  curl -s --max-time 30 -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API/admin/dlq/reprocess"
  echo
  sleep 20
  echo "########## /stats DESPUES del reproceso ($(date +%H:%M:%S))"
  curl -s --max-time 15 -H "Authorization: Bearer $ADMIN_TOKEN" "$API/stats"
  echo
} | tee "$EV_R5/stats_dlq.txt"

echo
echo "=== 3d. Worker que muere en medio de un job -> el fragmento se reasigna ==="
{
  echo "##### CASO c: matar un worker en caliente"
  echo "workers antes:"; docker compose ps --format '{{.Name}} {{.Status}}' | grep worker
  docker compose kill worker 2>&1
  echo "workers despues del kill:"; docker compose ps --format '{{.Name}} {{.Status}}' | grep worker
} >> "$EV_R5/casos_falla.log" 2>&1

# -----------------------------------------------------------------------------
# 4. Dejar todo sano
# -----------------------------------------------------------------------------
echo
echo "=== 4. Dejando los workers sanos (FAIL_RATE=0) ==="
FAIL_RATE=0 docker compose up -d --no-deps --scale worker=2 worker
sleep 15
vigilar "ESTADO FINAL (todo deberia volver a inactive)" 30

echo
echo "LISTO. Evidencia en:"
echo "  $EV_HIT4/alertas_transicion.log"
echo "  $EV_R5/stats_dlq.txt"
echo "  $EV_R5/casos_falla.log"
