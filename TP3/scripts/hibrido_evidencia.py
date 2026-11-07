"""Evidencia del Hit #2 hibrido: quien proceso cada job y cuanto tardo.

Corre en el equipo local, con el stack de docker compose arriba
(docker-compose.yml + docker-compose.hibrido.yml). Uso:

    py TP3/scripts/hibrido_evidencia.py <escenario> [jobs] [archivos_por_job]

  escenario  local  -> solo workers locales (sin VM)
             nube   -> workers locales en 0, todo lo procesa la VM de GCP
             mixto  -> workers locales + VM (cloud-bursting)
  El script NO escala nada: deja constancia del estado en que lo encontro
  (consumidores de RabbitMQ con su IP de origen) y mide.

Salida: TP3/evidencia/hit2/<escenario>.txt con
  - consumidores de tasks.tp3-worker y la IP de origen de cada conexion
    (100.x = llega por Tailscale desde la VM; 172.x = contenedor local)
  - por job: tiempo end-to-end, timings por etapa y los worker_id que lo tocaron
  - resumen: p50/max y cuantos fragmentos-job toco cada worker
"""
import json
import statistics
import subprocess
import sys
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://localhost:8000"
ESC = sys.argv[1] if len(sys.argv) > 1 else "mixto"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6
VA = int(sys.argv[3]) if len(sys.argv) > 3 else 5
IMG = ROOT / "TP3/loadtest/images/1MB.png"
if not IMG.exists():
    IMG = ROOT / "TP3/loadtest/sample.png"
OUT = ROOT / "TP3/evidencia/hit2" / f"{ESC}.txt"
lineas = []


def log(s=""):
    print(s)
    lineas.append(s)


def sh(*cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def rabbit(*args):
    return sh("docker", "compose", "exec", "-T", "rabbitmq", "rabbitmqctl", "-q", *args)


def token():
    gen = (ROOT / "TP3/scripts/gen_token.py").read_text(encoding="utf-8")
    r = subprocess.run(["docker", "compose", "exec", "-T", "backend", "python", "-", "hibrido", "user"],
                       cwd=ROOT, input=gen, capture_output=True, text=True)
    return r.stdout.strip()


def submit(tok):
    b = uuid.uuid4().hex
    img = IMG.read_bytes()
    body = b""
    for i in range(VA):
        body += (f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="img{i}.png"\r\n'
                 f"Content-Type: image/png\r\n\r\n").encode() + img + b"\r\n"
    body += f'--{b}\r\nContent-Disposition: form-data; name="ops"\r\n\r\nsobel\r\n--{b}--\r\n'.encode()
    req = urllib.request.Request(f"{BASE}/jobs", data=body, method="POST", headers={
        "Authorization": f"Bearer {tok}", "Content-Type": f"multipart/form-data; boundary={b}"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        job = json.load(r)["job_id"]
    while time.time() - t0 < 600:
        time.sleep(0.5)
        req = urllib.request.Request(f"{BASE}/jobs/{job}", headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            st = json.load(r)
        if st.get("status") in ("done", "failed", "dlq"):
            return job, time.time() - t0, st
    return job, None, {"status": "timeout"}


def main():
    log(f"# Hit #2 hibrido - escenario {ESC} - {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
    log(f"# {N} jobs concurrentes x {VA} archivos ({IMG.name}, {IMG.stat().st_size} bytes) x 4 fragmentos, op sobel")
    log()
    log("## Tailscale (este equipo y la VM)")
    log(sh("tailscale", "status"))
    log()
    log("## Workers locales (docker compose)")
    log(sh("docker", "compose", "ps", "worker", "--format", "{{.Name}}\t{{.Status}}") or "(ninguno)")
    log()
    log("## Consumidores de tasks.tp3-worker en la RabbitMQ LOCAL")
    log(rabbit("list_queues", "name", "consumers", "messages"))
    log()
    log("## Conexiones AMQP (peer_host 100.x = VM de GCP por Tailscale)")
    log(rabbit("list_connections", "name", "peer_host", "state"))
    log()

    tok = token()
    if not tok:
        sys.exit("no pude emitir el token (esta el backend arriba?)")
    t0 = time.time()
    with ThreadPoolExecutor(N) as ex:
        res = list(ex.map(lambda _: submit(tok), range(N)))
    total = time.time() - t0

    log("## Jobs")
    log("job_id\testado\te2e_s\tsplit\tqueue\tprocessing\tjoin\tworkers")
    cuenta, tiempos = {}, []
    for job, dt, st in res:
        tm = st.get("timings_s", {})
        ws = st.get("workers", [])
        for w in ws:
            cuenta[w] = cuenta.get(w, 0) + 1
        if dt is not None and st.get("status") == "done":
            tiempos.append(dt)
        log(f"{job}\t{st.get('status')}\t{dt and round(dt, 2)}\t{tm.get('split')}\t{tm.get('queue')}\t"
            f"{tm.get('processing')}\t{tm.get('join')}\t{','.join(ws)}")
    log()
    log("## Resumen")
    log(f"jobs done: {len(tiempos)}/{N} | lote completo en {total:.2f} s")
    if tiempos:
        log(f"e2e por job: p50 {statistics.median(tiempos):.2f} s | max {max(tiempos):.2f} s")
    log("jobs en los que participo cada worker (los tp3-hibrido-* son VMs de GCP):")
    for w, c in sorted(cuenta.items()):
        log(f"  {w}\t{c}\t{'NUBE (GCP)' if w.startswith('tp3-hibrido') else 'local'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
