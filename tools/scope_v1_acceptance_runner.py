#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import statistics
import tempfile
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "reports" / "scope_v1_evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], env: dict[str, str] | None = None, outfile: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True)
    if outfile:
        outfile.write_text((proc.stdout or "") + ("\nSTDERR:\n" + proc.stderr if proc.stderr else ""))
    return proc


def parse_trace_coverage(summary_text: str) -> tuple[float, list[tuple[str, int, float]]]:
    rows: list[tuple[str, int, float]] = []
    for line in summary_text.splitlines():
        if " app." not in line and "app." not in line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            lines = int(parts[0])
            cov = float(parts[1].replace("%", ""))
            module = parts[2]
        except Exception:
            continue
        if module.startswith("app."):
            rows.append((module, lines, cov))
    total_lines = sum(r[1] for r in rows)
    weighted = sum(r[1] * r[2] for r in rows) / total_lines if total_lines else 0.0
    return weighted, rows


def http_request(method: str, url: str, payload: dict | None = None, headers: dict[str, str] | None = None) -> tuple[int, str]:
    data = None
    req_headers = headers.copy() if headers else {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.getcode(), resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")
    except urllib.error.URLError as exc:
        return 0, str(exc)


def start_server() -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "apps/backend")
    env.setdefault("APP_ENV", "test")
    env.setdefault("APP_AUTH_SECRET", "scope-v1-test-secret")
    env.setdefault("APP_LOGIN_EMAIL", "admin@example.com")
    env.setdefault("APP_LOGIN_PASSWORD", "admin123")
    env.setdefault("APP_PORT", "8010")
    env.setdefault("APP_HOST", "127.0.0.1")
    env.setdefault("APP_CORS_ORIGINS", "http://localhost:3000")
    env.setdefault("GOOGLE_ADS_TOKEN", "railway-google-token")
    env.setdefault("META_ACCESS_TOKEN", "railway-meta-token")
    env.setdefault("OPENAI_API_KEY", "")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8010",
    ]
    return subprocess.Popen(cmd, cwd=ROOT / "apps" / "backend", env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def wait_health(base: str, timeout_s: int = 20) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        code, _ = http_request("GET", f"{base}/health")
        if code == 200:
            return True
        time.sleep(0.5)
    return False


def main() -> int:
    # 1) Functional + regression tests
    pytest_out = EVIDENCE_DIR / "pytest_full.txt"
    p = run(["pytest", "apps/backend/tests", "-q", "-rs"], env={**os.environ, "PYTHONPATH": "apps/backend"}, outfile=pytest_out)

    # 2) Coverage via trace summary (fallback without pytest-cov)
    cov_out = EVIDENCE_DIR / "coverage_trace_summary.txt"
    trace_dir = Path(tempfile.mkdtemp(prefix="scope_v1_trace_"))
    try:
        p_cov = run(
            [sys.executable, "-m", "trace", "--count", "--summary", "--coverdir", str(trace_dir), "--module", "pytest", "apps/backend/tests", "-q"],
            env={**os.environ, "PYTHONPATH": "apps/backend", "APP_AUTH_SECRET": "scope-v1-test-secret"},
            outfile=cov_out,
        )
    finally:
        shutil.rmtree(trace_dir, ignore_errors=True)
    weighted_cov, cov_rows = parse_trace_coverage(cov_out.read_text())

    # 3) API latency + error rate + functional HTTP checks
    base = "http://127.0.0.1:8010"
    server = start_server()
    http_results = {
        "health_ready": False,
        "functional": {},
        "latency": {},
        "error_rate": {},
    }

    try:
        ready = wait_health(base)
        http_results["health_ready"] = ready
        if not ready:
            raise RuntimeError("Server did not become healthy in time")

        code, body = http_request("POST", f"{base}/auth/login", {"email": "admin@example.com", "password": "admin123", "role": "agency_admin"})
        http_results["functional"]["auth_login"] = {"status": code}
        token = ""
        if code == 200:
            token = json.loads(body)["access_token"]

        headers = {"Authorization": f"Bearer {token}"} if token else {}
        for name, method, path, payload in [
            ("google_sync", "POST", "/integrations/google-ads/1/sync", None),
            ("meta_sync", "POST", "/integrations/meta-ads/1/sync", None),
            ("ai_assistant", "GET", "/ai/recommendations/1", None),
            ("dashboard", "GET", "/dashboard/1", None),
        ]:
            code_i, _ = http_request(method, f"{base}{path}", payload, headers)
            http_results["functional"][name] = {"status": code_i}

        def latency_run(name: str, method: str, path: str, payload: dict | None = None, loops: int = 120):
            timings = []
            errors = 0
            for _ in range(loops):
                t0 = time.perf_counter()
                code_l, _ = http_request(method, f"{base}{path}", payload, headers if path != "/auth/login" else None)
                dt = (time.perf_counter() - t0) * 1000.0
                timings.append(dt)
                if code_l >= 500:
                    errors += 1
            p95 = statistics.quantiles(timings, n=100)[94]
            http_results["latency"][name] = {
                "samples": loops,
                "p95_ms": round(p95, 2),
                "avg_ms": round(sum(timings) / len(timings), 2),
            }
            http_results["error_rate"][name] = round((errors / loops) * 100, 3)

        latency_run("health_get", "GET", "/health")
        latency_run("auth_login_post", "POST", "/auth/login", {"email": "admin@example.com", "password": "admin123", "role": "agency_admin"})
        latency_run("dashboard_get", "GET", "/dashboard/1")

    finally:
        server.terminate()
        try:
            out, err = server.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            out, err = server.communicate()
        (EVIDENCE_DIR / "uvicorn_stdout.log").write_text(out or "")
        (EVIDENCE_DIR / "uvicorn_stderr.log").write_text(err or "")

    summary = {
        "pytest_exit_code": p.returncode,
        "trace_exit_code": p_cov.returncode,
        "coverage_weighted_app_percent": round(weighted_cov, 2),
        "coverage_rows": cov_rows,
        "http_results": http_results,
    }
    (EVIDENCE_DIR / "scope_v1_metrics.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    return 0 if p.returncode == 0 and p_cov.returncode == 0 and http_results["health_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
