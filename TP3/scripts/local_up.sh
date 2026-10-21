#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

for command in docker minikube kubectl; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command" >&2
    exit 1
  fi
done

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example to .env and set RABBIT_PASS and AUTH_SECRET first." >&2
  exit 1
fi

set -a
# .env is the project runtime configuration and should contain shell-compatible assignments.
source .env
set +a

if [[ -z "${RABBIT_USER:-}" || -z "${RABBIT_PASS:-}" || -z "${RABBIT_URL:-}" || -z "${AUTH_SECRET:-}" ]]; then
  echo "RABBIT_USER, RABBIT_PASS, RABBIT_URL and AUTH_SECRET must be set in .env." >&2
  exit 1
fi

minikube start --driver=docker

docker compose build backend split joiner worker dlq-monitor frontend
for service in backend split joiner worker dlq-monitor frontend; do
  minikube image load "tp3/$service:dev"
done

kubectl create namespace tp3 --dry-run=client -o yaml | kubectl apply -f -
kubectl -n tp3 create secret generic rabbitmq-auth \
  --from-literal="rabbitmq-password=$RABBIT_PASS" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n tp3 create secret generic tp3-secrets \
  --from-literal="RABBIT_URL=$RABBIT_URL" \
  --from-literal="REDIS_URL=${REDIS_URL:-redis://redis:6379/0}" \
  --from-literal="AUTH_SECRET=$AUTH_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k TP3/k8s/overlays/local
for deployment in rabbitmq redis backend split joiner worker dlq-monitor frontend; do
  kubectl -n tp3 rollout status "deployment/$deployment" --timeout=300s
done

echo "Local stack is ready. Run: kubectl -n tp3 port-forward svc/frontend 8081:80"
