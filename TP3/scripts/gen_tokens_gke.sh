#!/usr/bin/env bash
# Genera un token de admin y uno de user de la app TP3 corriendo en GKE.
# Solo necesita kubectl y el kubeconfig que le pasamos (profe-kubeconfig.yaml).
#   bash gen_tokens_gke.sh profe-kubeconfig.yaml            -> admin "admin" y user "alice"
#   bash gen_tokens_gke.sh profe-kubeconfig.yaml bob        -> admin "admin" y user "bob"
set -euo pipefail

KCFG="${1:?Uso: bash gen_tokens_gke.sh <kubeconfig> [nombre_user]}"
USER_NAME="${2:-alice}"

# Mismo código que TP3/scripts/gen_token.py, inline para no depender del repo
CODE='import sys
from tp3common.auth import issue_token
print(issue_token(sys.argv[1], sys.argv[2]))'

tok() {
  kubectl --kubeconfig "$KCFG" -n tp3 exec deploy/backend -- python -c "$CODE" "$1" "$2" | tr -d '\r'
}

ADMIN_TOKEN=$(tok admin admin)
USER_TOKEN=$(tok "$USER_NAME" user)

echo "ADMIN_TOKEN=$ADMIN_TOKEN"
echo "USER_TOKEN=$USER_TOKEN"
