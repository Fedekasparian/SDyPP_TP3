"""Tokens firmados con HMAC-SHA256 (R4). La identidad viaja en cada request:
no hay sesion en memoria, cualquier replica puede validar el token.

Formato: base64url(json{sub, role, exp}) + "." + base64url(hmac(payload))
"""
import base64
import hashlib
import hmac
import json
import time

from . import config

ROLES = ("user", "admin")


class AuthError(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def issue_token(sub: str, role: str, ttl_s: int = 7 * 24 * 3600, secret: str | None = None) -> str:
    secret = secret or config.AUTH_SECRET
    if not secret:
        raise AuthError("AUTH_SECRET no configurado")
    if role not in ROLES:
        raise AuthError(f"rol invalido: {role}")
    payload = _b64(json.dumps({"sub": sub, "role": role, "exp": int(time.time()) + ttl_s}).encode())
    return f"{payload}.{_sign(payload, secret)}"


def verify_token(token: str, secret: str | None = None) -> dict:
    secret = secret or config.AUTH_SECRET
    if not secret:
        raise AuthError("AUTH_SECRET no configurado")
    try:
        payload, sig = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("token mal formado") from exc
    if not hmac.compare_digest(sig, _sign(payload, secret)):
        raise AuthError("firma invalida")
    claims = json.loads(_unb64(payload))
    if claims.get("exp", 0) < time.time():
        raise AuthError("token expirado")
    if claims.get("role") not in ROLES:
        raise AuthError("rol invalido")
    return claims
