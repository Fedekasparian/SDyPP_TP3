// Escenario de carga (Hit #3 + R5). Parametros por env:
//   BASE_URL     http://localhost:8000 (o http://<ip>/api)
//   ADMIN_TOKEN  token admin: en setup() emite un token por usuario virtual
//   IMAGE        imagen de entrada (V1: tamaño)              default ../sample.png
//   VA           archivos por request (1, 10, 50)            default 1
//   OPS          cadena de acciones VB (sobel | blur,sobel | grayscale,blur,sobel)
//   VC           usuarios concurrentes con token (1, 10, 50) default 1
//   RAMP, DURATION  ramp-up y meseta                          default 10s, 60s
//   INVALID_RATE fraccion de requests invalidos (archivo corrupto) default 0
//   SLO_P95_S    SLO de latencia end-to-end p95 en segundos   default 10
//   TIMEOUT_S    espera maxima por job                        default 120
// Ademas corre siempre 1 bot SIN token (debe recibir 401).
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";
import { FormData } from "https://jslib.k6.io/formdata/0.0.2/index.js";

const BASE = __ENV.BASE_URL || "http://localhost:8000";
const VA = parseInt(__ENV.VA || "1");
const OPS = __ENV.OPS || "sobel";
const VC = parseInt(__ENV.VC || "1");
const RAMP = __ENV.RAMP || "10s";
const DURATION = __ENV.DURATION || "60s";
const INVALID_RATE = parseFloat(__ENV.INVALID_RATE || "0");
const SLO_P95_S = parseFloat(__ENV.SLO_P95_S || "10");
const TIMEOUT_S = parseFloat(__ENV.TIMEOUT_S || "120");
const IMG = open(__ENV.IMAGE || "../sample.png", "b");

const jobLatency = new Trend("job_latency", true);
const jobErrors = new Rate("job_errors");
const jobDlq = new Counter("job_dlq");
const jobTimeouts = new Counter("job_timeouts");
const invalidRejected = new Counter("invalid_rejected");

export const options = {
  scenarios: {
    users: {
      executor: "ramping-vus",
      exec: "user",
      startVUs: 0,
      stages: [
        { duration: RAMP, target: VC },
        { duration: DURATION, target: VC },
        { duration: "5s", target: 0 },
      ],
      gracefulRampDown: `${TIMEOUT_S}s`,
    },
    bot_sin_token: { executor: "constant-vus", exec: "botSinToken", vus: 1, duration: DURATION },
  },
  thresholds: {
    job_latency: [`p(95)<${SLO_P95_S * 1000}`],
    job_errors: ["rate<0.05"],
  },
  summaryTrendStats: ["avg", "min", "med", "p(95)", "p(99)", "max", "count"],
};

export function setup() {
  const headers = { Authorization: `Bearer ${__ENV.ADMIN_TOKEN}` };
  const tokens = [];
  for (let i = 0; i < VC; i++) {
    const r = http.post(`${BASE}/admin/tokens?sub=bot${i}&role=user`, null, { headers });
    if (r.status !== 200) throw new Error(`no pude emitir tokens: ${r.status} ${r.body}`);
    tokens.push(r.json("token"));
  }
  return { tokens };
}

export function user(data) {
  const token = data.tokens[(__VU - 1) % data.tokens.length];
  const auth = { Authorization: `Bearer ${token}` };
  const invalid = Math.random() < INVALID_RATE;

  const fd = new FormData();
  for (let i = 0; i < VA; i++) {
    const body = invalid && i === 0 ? "esto no es una imagen" : IMG;
    fd.append("files", http.file(body, `img${i}.png`, "image/png"));
  }
  fd.append("ops", OPS);

  const t0 = Date.now();
  const res = http.post(`${BASE}/jobs`, fd.body(), {
    headers: { ...auth, "Content-Type": `multipart/form-data; boundary=${fd.boundary}` },
    tags: { name: "POST /jobs" },
  });
  if (invalid) {
    if (check(res, { "invalido -> 400 claro": (r) => r.status === 400 })) invalidRejected.add(1);
    return;
  }
  if (!check(res, { "POST /jobs -> 202": (r) => r.status === 202 })) {
    jobErrors.add(1);
    return;
  }
  const id = res.json("job_id");
  while (Date.now() - t0 < TIMEOUT_S * 1000) {
    sleep(0.5);
    const s = http.get(`${BASE}/jobs/${id}`, { headers: auth, tags: { name: "GET /jobs/:id" } });
    const status = s.json("status");
    if (status === "done") {
      jobLatency.add(Date.now() - t0);
      jobErrors.add(0);
      return;
    }
    if (status === "failed" || status === "dlq") {
      if (status === "dlq") jobDlq.add(1);
      jobErrors.add(1);
      return;
    }
  }
  jobTimeouts.add(1);
  jobErrors.add(1);
}

export function botSinToken() {
  const r = http.get(`${BASE}/jobs`, { tags: { name: "bot sin token" } });
  check(r, { "bot sin token -> 401": (x) => x.status === 401 });
  sleep(1);
}
