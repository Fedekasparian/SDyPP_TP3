"""Genera un token firmado (requiere AUTH_SECRET en el entorno).

    docker compose exec backend python /dev/stdin alice user < TP3/scripts/gen_token.py
    kubectl -n tp3 exec deploy/backend -- python -c "$(cat TP3/scripts/gen_token.py)" admin admin
"""
import sys

from tp3common.auth import issue_token

if __name__ == "__main__":
    sub = sys.argv[1] if len(sys.argv) > 1 else "alice"
    role = sys.argv[2] if len(sys.argv) > 2 else "user"
    print(issue_token(sub, role))
