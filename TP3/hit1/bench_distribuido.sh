#!/usr/bin/env bash
# Hit #1, etapas 2 y 3, sobre el stack de docker compose (levantarlo antes con
# `docker compose up -d --build`). Escala los workers, asi que no correrlo mientras otro
# usa el stack.
#   bash TP3/hit1/bench_distribuido.sh bench  [IMG]   tiempos por etapa con 1, 2 y 4 workers (WORKERS="1 2 4")
#   bash TP3/hit1/bench_distribuido.sh fallas [IMG]   mata un worker en medio del job y muestra la reasignacion
# IMG por defecto: TP3/loadtest/images/10MB.png (se genera con la imagen del worker si no existe).
# Con mas workers que FRAGMENTS_PER_IMAGE (4 por defecto, en .env) no hay mas paralelismo.
set -euo pipefail
cd "$(dirname "$0")/../.."

BASE="${BASE_URL:-http://localhost:8000}"
MODE="${1:-bench}"
IMG="${2:-TP3/loadtest/images/10MB.png}"
WORKERS="${WORKERS:-1 2 4}"

if [[ ! -f "$IMG" ]]; then
  echo "generando imagenes de prueba en TP3/loadtest/images/ ..."
  MSYS_NO_PATHCONV=1 docker run --rm --user root -v "$(pwd -W 2>/dev/null || pwd)/TP3/loadtest:/lt" \
    -w /lt tp3/worker:dev python gen_images.py
fi

TOKEN=$(docker compose exec -T backend python - bench user < TP3/scripts/gen_token.py | tr -d '\r')
AUTH=(-H "Authorization: Bearer $TOKEN")

submit() {
  curl -sf "${AUTH[@]}" -F "files=@$IMG" -F ops=sobel "$BASE/jobs" \
    | sed -n 's/.*"job_id":"\([^"]*\)".*/\1/p'
}

wait_job() {  # imprime el JSON final del job
  local body status
  for _ in $(seq 1 600); do
    body=$(curl -sf "${AUTH[@]}" "$BASE/jobs/$1")
    status=$(sed -n 's/.*"status":"\([a-z]*\)".*/\1/p' <<<"$body")
    case "$status" in done|failed|dlq) echo "$body"; return 0 ;; esac
    sleep 0.5
  done
  echo "timeout esperando el job $1" >&2; return 1
}

field() { sed -n "s/.*\"$1\":\([^,}]*\).*/\1/p" <<<"$2"; }

scale() {
  docker compose up -d --no-deps --scale worker="$1" worker >/dev/null 2>&1
  sleep 5  # que los workers nuevos se registren como consumidores
}

bench() {
  echo "imagen: $IMG ($(wc -c <"$IMG") bytes)"
  printf "%-8s %-8s %-8s %-11s %-8s %-8s %s\n" workers split queue processing join total workers_usados
  for n in $WORKERS; do
    scale "$n"
    body=$(wait_job "$(submit)")
    used=$(grep -o '"workers":\[[^]]*\]' <<<"$body" | grep -o '"[^"]*"' | tail -n +2 | wc -l)
    printf "%-8s %-8s %-8s %-11s %-8s %-8s %s\n" "$n" "$(field split "$body")" "$(field queue "$body")" \
      "$(field processing "$body")" "$(field join "$body")" "$(field total "$body")" "$used"
  done
}

fallas() {
  # 2 workers y 4 fragmentos: cada worker procesa al menos 2, asi que la victima seguro
  # tiene un fragmento sin ack cuando la matamos.
  scale 2
  local job body victim
  # Cadena larga para que cada fragmento tarde y el kill caiga con un fragmento sin ack.
  job=$(curl -sf "${AUTH[@]}" -F "files=@$IMG" -F ops=blur,blur,blur,blur,sobel "$BASE/jobs" \
    | sed -n 's/.*"job_id":"\([^"]*\)".*/\1/p')
  echo "job $job enviado"
  # WORKER_ID = <hostname>-<sufijo> y el hostname del contenedor es su id corto: con el
  # primer worker que aparece en el job sabemos que contenedor matar.
  for _ in $(seq 1 200); do
    body=$(curl -sf "${AUTH[@]}" "$BASE/jobs/$job")
    victim=$(grep -o '"workers":\["[0-9a-f]\{12\}' <<<"$body" | tail -c 13 || true)
    [[ -n "$victim" ]] && break; sleep 0.05
  done
  docker kill "$victim" >/dev/null
  echo "worker $(docker inspect -f '{{.Name}}' "$victim") ($victim) muerto con SIGKILL"
  body=$(wait_job "$job")
  echo "$body"
  echo "--- logs de los workers para este job"
  docker compose logs --no-color worker 2>/dev/null | grep "job=$job" | sort -k4,5 || true
  scale 2   # restart: unless-stopped no revive un docker kill; lo levantamos de nuevo
}

case "$MODE" in
  bench) bench ;;
  fallas) fallas ;;
  *) echo "uso: $0 bench|fallas [IMG]" >&2; exit 2 ;;
esac
