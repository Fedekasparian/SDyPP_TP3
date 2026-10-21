#!/usr/bin/env bash
# Reproduce los resultados de los READMEs con Docker solo (sin Python local ni Kubernetes).
# Levanta un RabbitMQ aislado en la red `hit0`, corre el escenario pedido y lo baja al final.
#   bash TP3/queue/run_demo.sh ex1|ex2|ex3|ex4|all
set -euo pipefail
cd "$(dirname "$0")"

IMG=tp3/queue-examples:dev
R=(docker run --rm --network hit0 -e RABBIT_HOST=hit0-rabbit)
OUT=$(mktemp -d)

setup() {
  docker network create hit0 >/dev/null 2>&1 || true
  docker build -q -t "$IMG" . >/dev/null
  docker run -d --rm --name hit0-rabbit --network hit0 rabbitmq:3.13-management >/dev/null
  echo "esperando a RabbitMQ..."
  # No usar `docker exec rabbitmq-diagnostics` antes de que arranque el nodo: crea la
  # .erlang.cookie como root y el servidor ya no puede leerla.
  until docker logs hit0-rabbit 2>&1 | grep -q "Server startup complete"; do sleep 2; done
}
teardown() { docker rm -f hit0-rabbit >/dev/null 2>&1 || true; docker network rm hit0 >/dev/null 2>&1 || true; }
trap teardown EXIT

ex1() {
  echo "### ex1: 1 consumidor"
  "${R[@]}" --name c1 -e CONSUMER_ID=A -e WORK_SECONDS=0.1 "$IMG" python ex1/consumer.py >"$OUT/a" 2>&1 &
  sleep 4; "${R[@]}" "$IMG" python ex1/producer.py >/dev/null; sleep 3
  docker stop -t1 c1 >/dev/null; cat "$OUT/a"
  for prefetch in 0 1; do
    echo "### ex1: 2 consumidores, A lento (1 s) y B rapido (0.1 s), PREFETCH=$prefetch"
    "${R[@]}" --name c1 -e CONSUMER_ID=A -e PREFETCH=$prefetch -e WORK_SECONDS=1 "$IMG" python ex1/consumer.py >"$OUT/a" 2>&1 &
    "${R[@]}" --name c2 -e CONSUMER_ID=B -e PREFETCH=$prefetch -e WORK_SECONDS=0.1 "$IMG" python ex1/consumer.py >"$OUT/b" 2>&1 &
    sleep 5; "${R[@]}" "$IMG" python ex1/producer.py >/dev/null; sleep 7
    docker stop -t1 c1 c2 >/dev/null; cat "$OUT/a" "$OUT/b"
  done
}

ex2() {
  echo "### ex2: 3 nodos suscriptos desde el principio y uno que llega tarde"
  for n in 1 2 3; do
    "${R[@]}" --name s$n -e NODE_ID=nodo$n -e EXPECTED=5 "$IMG" python ex2/subscriber.py >"$OUT/s$n" 2>&1 &
  done
  sleep 5
  "${R[@]}" "$IMG" python ex2/publisher.py >"$OUT/pub" 2>&1 &
  sleep 2.5
  "${R[@]}" --name s4 -e NODE_ID=tardio "$IMG" python ex2/subscriber.py >"$OUT/s4" 2>&1 &
  sleep 8; docker stop -t1 s4 >/dev/null 2>&1 || true; wait
  cat "$OUT/pub" "$OUT/s1" "$OUT/s2" "$OUT/s3" "$OUT/s4"
}

ex3() {
  echo "### ex3: DLQ"
  "${R[@]}" --name dlq "$IMG" python ex3/dlq_consumer.py >"$OUT/dlq" 2>&1 &
  "${R[@]}" --name c3 "$IMG" python ex3/consumer.py >"$OUT/c3" 2>&1 &
  sleep 5; "${R[@]}" "$IMG" python ex3/producer.py; sleep 3
  docker stop -t1 c3 dlq >/dev/null; cat "$OUT/c3"; echo "--- DLQ"; cat "$OUT/dlq"
}

ex4() {
  echo "### ex4: retry 1/2/4/8 s y DLQ del ej. 3 (SEED=7: reproducible)"
  "${R[@]}" --name dlq "$IMG" python ex3/dlq_consumer.py >"$OUT/dlq" 2>&1 &
  "${R[@]}" --name c4 -e SEED=7 "$IMG" python ex4/consumer_retry.py >"$OUT/c4" 2>&1 &
  sleep 5; "${R[@]}" "$IMG" python ex4/producer.py >/dev/null; sleep 25
  docker stop -t1 c4 dlq >/dev/null; cat "$OUT/c4"; echo "--- DLQ"; cat "$OUT/dlq"
}

setup
case "${1:-all}" in
  ex1) ex1 ;; ex2) ex2 ;; ex3) ex3 ;; ex4) ex4 ;;
  all) ex1; ex2; ex3; ex4 ;;
  *) echo "uso: $0 ex1|ex2|ex3|ex4|all" >&2; exit 2 ;;
esac
