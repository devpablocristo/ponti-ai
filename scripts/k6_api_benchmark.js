import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.K6_BASE_URL || "http://localhost:8090";
const SERVICE_KEY = __ENV.K6_SERVICE_KEY || "servicekey123";
const USER_ID = __ENV.K6_USER_ID || "k6-user";
const PROJECT_ID = __ENV.K6_PROJECT_ID || "1";

const HEADERS = {
  "Content-Type": "application/json",
  "X-SERVICE-KEY": SERVICE_KEY,
  "X-USER-ID": USER_ID,
  "X-PROJECT-ID": PROJECT_ID,
};

const failureRate = new Rate("failure_rate");
const endpointFailures = new Counter("endpoint_failures");
const copilotLatency = new Trend("copilot_latency_ms");
const jobsLatency = new Trend("jobs_latency_ms");

const benchmarkDuration = __ENV.BENCH_DURATION || "45s";
const benchmarkVus = Number(__ENV.BENCH_VUS || 6);

export const options = {
  scenarios: {
    core_reads: {
      executor: "constant-vus",
      vus: benchmarkVus,
      duration: benchmarkDuration,
      exec: "coreReads",
    },
    jobs_writes: {
      executor: "constant-vus",
      vus: 2,
      duration: benchmarkDuration,
      exec: "jobsWrites",
      startTime: "2s",
    },
    copilot_reads: {
      executor: "constant-vus",
      vus: 2,
      duration: benchmarkDuration,
      exec: "copilotReads",
      startTime: "4s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<4000", "p(99)<8000"],
    failure_rate: ["rate<0.05"],
    copilot_latency_ms: ["p(95)<30000"],
    jobs_latency_ms: ["p(95)<10000"],
  },
};

function assertOk(res, name) {
  const ok = check(res, {
    [`${name} status`]: (r) => r.status >= 200 && r.status < 300,
  });
  failureRate.add(!ok);
  if (!ok) {
    endpointFailures.add(1);
  }
  return ok;
}

function request(method, path, body = null) {
  const url = `${BASE_URL}${path}`;
  if (body === null) {
    return http.request(method, url, null, { headers: HEADERS });
  }
  return http.request(method, url, JSON.stringify(body), { headers: HEADERS });
}

export function setup() {
  const h = http.get(`${BASE_URL}/healthz`);
  check(h, { "healthz up": (r) => r.status === 200 });

  const b = request("POST", "/v1/jobs/recompute-baselines", {});
  assertOk(b, "recompute-baselines");
  const c = request("POST", "/v1/insights/compute");
  assertOk(c, "compute-insights");
  const s = request("GET", "/v1/insights/summary");
  assertOk(s, "summary");

  let insightId = null;
  try {
    const payload = s.json();
    if (payload && payload.top_insights && payload.top_insights.length > 0) {
      insightId = payload.top_insights[0].id;
    }
  } catch (_err) {
    insightId = null;
  }

  return { insightId };
}

export function coreReads() {
  const routes = [
    "/v1/insights/summary",
    "/v1/insights/project/1",
    "/v1/ml/status",
    "/metrics",
  ];
  const route = routes[Math.floor(Math.random() * routes.length)];
  const res = request("GET", route);
  assertOk(res, `core ${route}`);
  sleep(0.2);
}

export function jobsWrites() {
  const start = Date.now();
  const r1 = request("POST", "/v1/jobs/recompute-queue/enqueue", {
    source: "k6",
    reason: "benchmark",
    debounce_seconds: 0,
  });
  assertOk(r1, "enqueue");

  const r2 = request("POST", "/v1/jobs/recompute-queue/process", {
    limit: 10,
    workers: 2,
  });
  assertOk(r2, "process-queue");
  jobsLatency.add(Date.now() - start);
  sleep(0.3);
}

export function copilotReads(data) {
  if (!data || !data.insightId) {
    sleep(0.5);
    return;
  }

  const paths = [
    `/v1/copilot/insights/${data.insightId}/explain`,
    `/v1/copilot/insights/${data.insightId}/why`,
    `/v1/copilot/insights/${data.insightId}/next-steps`,
  ];
  const path = paths[Math.floor(Math.random() * paths.length)];

  const start = Date.now();
  const res = request("GET", path);
  assertOk(res, `copilot ${path}`);
  copilotLatency.add(Date.now() - start);
  sleep(0.4);
}

export function handleSummary(data) {
  const out = {
    k6_status: "completed",
    http_reqs: data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 0,
    http_failed_rate: data.metrics.http_req_failed ? data.metrics.http_req_failed.values.rate : null,
    p95_ms: data.metrics.http_req_duration ? data.metrics.http_req_duration.values["p(95)"] : null,
    p99_ms: data.metrics.http_req_duration ? data.metrics.http_req_duration.values["p(99)"] : null,
    failure_rate: data.metrics.failure_rate ? data.metrics.failure_rate.values.rate : null,
  };
  return {
    stdout: `${JSON.stringify(out, null, 2)}\n`,
  };
}
