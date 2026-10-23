#!/usr/bin/env bash
# R4: permisos, aislamiento y evidencia de al menos tres backends distintos.
# BASE_URL=http://localhost:8081/api ADMIN_TOKEN=... USER_A_TOKEN=... USER_B_TOKEN=... ./r4_evidence.sh
# K8S=1 escala backend a tres replicas en el contexto seleccionado por kubectl.
set -euo pipefail
: "${ADMIN_TOKEN:?definir ADMIN_TOKEN}"
: "${USER_A_TOKEN:?definir USER_A_TOKEN}"
: "${USER_B_TOKEN:?definir USER_B_TOKEN}"
if [[ "${K8S:-0}" == "1" ]]; then
  kubectl -n "${NAMESPACE:-tp3}" scale deploy/backend --replicas=3
  kubectl -n "${NAMESPACE:-tp3}" rollout status deploy/backend --timeout=180s
  kubectl -n "${NAMESPACE:-tp3}" get pods -l app=backend -o wide
fi
exec "${PYTHON:-python3}" "$(dirname "$0")/r4_evidence.py"
