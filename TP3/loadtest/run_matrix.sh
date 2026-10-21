#!/usr/bin/env bash
# Corre la matriz de pruebas y deja un JSON por celda en results/.
#   MATRIX=r5   VA x VB x VC cruzado con V1_LIST y V3_LIST (R5)
#   MATRIX=hit3 V1 x V2 x V3 (Hit #3): V2 = concurrencia, con VA=1 y VB=sobel
# Escalado de workers (V3) segun MODE:
#   MODE=compose  docker compose up -d --scale worker=N
#   MODE=k8s      kubectl -n tp3 scale deploy/worker --replicas=N
#   MODE=manual   pausa y pide escalar a mano (VMs con workers.yml)
# Ejemplo: BASE_URL=http://localhost:8000 ADMIN_TOKEN=... MATRIX=r5 ./run_matrix.sh
set -euo pipefail
cd "$(dirname "$0")"
: "${ADMIN_TOKEN:?definir ADMIN_TOKEN}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
MATRIX="${MATRIX:-r5}"
MODE="${MODE:-compose}"
DURATION="${DURATION:-60s}"
RAMP="${RAMP:-10s}"
INVALID_RATE="${INVALID_RATE:-0.05}"
mkdir -p results

if [[ "$MATRIX" == "r5" ]]; then
  V1_LIST="${V1_LIST:-10KB 1MB}"; V3_LIST="${V3_LIST:-2 6}"
  VA_LIST="${VA_LIST:-1 10 50}";  VC_LIST="${VC_LIST:-1 10 50}"
  VB_LIST="${VB_LIST:-sobel blur,sobel grayscale,blur,sobel}"
else
  V1_LIST="${V1_LIST:-1KB 10KB 100KB 1MB 10MB 100MB}"; V3_LIST="${V3_LIST:-1 2 4 8}"
  VA_LIST="1"; VB_LIST="sobel"; VC_LIST="${V2_LIST:-1 5 10 25 50}"
fi

scale_workers() {
  case "$MODE" in
    compose) (cd ../../.. && docker compose up -d --no-deps --scale worker="$1" worker) ;;
    k8s) kubectl -n tp3 scale deploy/worker --replicas="$1" && kubectl -n tp3 rollout status deploy/worker ;;
    manual) read -rp "Escalar workers a $1 y presionar Enter..." ;;
  esac
  sleep 10
}

for v3 in $V3_LIST; do
  scale_workers "$v3"
  for v1 in $V1_LIST; do
    for va in $VA_LIST; do
      for vb in $VB_LIST; do
        nb=$(tr -cd ',' <<<"$vb" | wc -c); nb=$((nb + 1))
        for vc in $VC_LIST; do
          cell="${MATRIX}_V1-${v1}_V3-${v3}_VA-${va}_VB-${nb}_VC-${vc}"
          [[ -f "results/$cell.json" ]] && { echo "skip $cell"; continue; }
          echo "==> $cell"
          k6 run --quiet --summary-export "results/$cell.json" \
            -e BASE_URL="$BASE_URL" -e ADMIN_TOKEN="$ADMIN_TOKEN" -e IMAGE="../images/$v1.png" \
            -e VA="$va" -e OPS="$vb" -e VC="$vc" -e DURATION="$DURATION" -e RAMP="$RAMP" \
            -e INVALID_RATE="$INVALID_RATE" k6/job.js || echo "   (thresholds no cumplidos)"
        done
      done
    done
  done
done
python summarize.py
