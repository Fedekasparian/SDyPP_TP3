"""Evidencia R4 sin imprimir tokens. Solo biblioteca estandar de Python."""
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone


def main():
    base = os.getenv("BASE_URL", "http://localhost:8081/api").rstrip("/")
    tokens = {name: os.environ[name] for name in ("ADMIN_TOKEN", "USER_A_TOKEN", "USER_B_TOKEN")}
    image = Path(os.getenv("IMG", str(Path(__file__).resolve().parents[1] / "loadtest/sample.png")))
    minimum = int(os.getenv("MIN_REPLICAS", "3"))
    passed, failed = 0, 0
    print(f"R4 · {datetime.now(timezone.utc).isoformat()} · base={base}")
    print(f"Replicas distintas requeridas: {minimum}")

    def check(label, ok, detail=""):
        nonlocal passed, failed
        passed += int(ok)
        failed += int(not ok)
        print(f"{'OK  ' if ok else 'FAIL'} {label}" + (f" -> {detail}" if detail else ""))

    def request(path, token=None, data=None, content_type=None):
        headers = {"Connection": "close"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(base + path, data=data, headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=45)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read()
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                body = None
            return response.status, body, response.headers

    for label, path, token, expected in (
        ("Sin token", "/jobs", None, 401),
        ("Token invalido", "/jobs", "invalid", 401),
        ("Usuario sin permiso admin", "/stats", tokens["USER_A_TOKEN"], 403),
        ("Admin consulta estadisticas", "/stats", tokens["ADMIN_TOKEN"], 200),
    ):
        code, _, _ = request(path, token)
        check(label, code == expected, f"HTTP {code}")

    boundary = uuid.uuid4().hex
    payload = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="ops"\r\n\r\nsobel\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="sample.png"\r\n'
        'Content-Type: image/png\r\n\r\n'
    ).encode() + image.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    code, body, _ = request("/jobs", tokens["USER_A_TOKEN"], payload, f"multipart/form-data; boundary={boundary}")
    check("Submit asincronico", code == 202 and isinstance(body, dict) and bool(body.get("job_id")), f"HTTP {code}")
    if code != 202 or not body or not body.get("job_id"):
        return 1
    job_id = body["job_id"]
    print(f"job_id={job_id}")
    for suffix in ("", "/events", "/result/0"):
        code, _, _ = request(f"/jobs/{job_id}{suffix}", tokens["USER_B_TOKEN"])
        check(f"Aislamiento usuario B ({suffix or 'status'})", code == 404, f"HTTP {code}")

    replicas, ok = set(), 0
    for _ in range(30):
        code, body, headers = request(f"/jobs/{job_id}", tokens["USER_A_TOKEN"])
        valid = code == 200 and isinstance(body, dict) and body.get("job_id") == job_id
        ok += int(valid)
        if valid and headers.get("X-Backend-Replica"):
            replicas.add(headers["X-Backend-Replica"])
    check("30 lecturas autorizadas del mismo job", ok == 30, f"{ok}/30")
    check("Backends distintos observados", len(replicas) >= minimum, ", ".join(sorted(replicas)) or "sin header")

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        code, body, _ = request(f"/jobs/{job_id}", tokens["USER_A_TOKEN"])
        if code != 200 or body.get("status") in ("done", "failed", "dlq"):
            break
        time.sleep(.5)
    done = code == 200 and body and body.get("status") == "done"
    check("Pipeline termina", done, body.get("status", "sin estado") if body else f"HTTP {code}")
    if done:
        code, _, headers = request(f"/jobs/{job_id}/result/0", tokens["USER_A_TOKEN"])
        check("Descarga del resultado", code == 200 and headers.get_content_type() == "image/png", f"HTTP {code}")
        code, _, headers = request(f"/jobs/{job_id}/events", tokens["USER_A_TOKEN"])
        check("Progreso SSE autorizado", code == 200 and headers.get_content_type() == "text/event-stream", f"HTTP {code}")
    print(f"---- {passed} OK, {failed} FAIL")
    return int(failed > 0)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, OSError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}; revisar entorno, tokens y conectividad", file=sys.stderr)
        sys.exit(1)
