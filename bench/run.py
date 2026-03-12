from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RunConfig:
    framework: str
    host: str
    port: int
    tool: str
    duration: str
    connections: int
    threads: int
    profilis_enabled: bool

    queue_size: int
    flush_interval: float
    sample: float
    stats_file: str | None = None


def _http_json(url: str, *, timeout_s: float = 3.0) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _metrics_retry(host: str, port: int, *, timeout_s: float = 15.0) -> dict[str, Any]:
    url = f"http://{host}:{port}/metrics"
    last: Exception | None = None
    for _ in range(8):
        try:
            return _http_json(url, timeout_s=timeout_s)
        except Exception as e:
            last = e
            time.sleep(0.2)
    raise RuntimeError(f"failed to fetch metrics: {url}") from last


def _parse_bench_collector(stdout: bytes) -> dict[str, Any] | None:
    try:
        text = stdout.decode("utf-8", "replace")
    except Exception:
        return None
    matches = re.findall(r"^BENCH_COLLECTOR\s+(\{.*\})\s*$", text, flags=re.MULTILINE)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except Exception:
        return None


def _wait_ok(host: str, port: int, *, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    url = f"http://{host}:{port}/health"
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            _http_json(url, timeout_s=1.0)
            return
        except Exception as e:
            last = e
            time.sleep(0.1)
    raise RuntimeError(f"healthcheck failed: {url}") from last


class _Suppress:
    def __init__(self, *exc: type[BaseException]) -> None:
        self.exc = exc or (Exception,)

    def __enter__(self) -> None:
        return None

    def __exit__(self, et, ev, tb) -> bool:  # type: ignore[no-untyped-def]
        return ev is not None and isinstance(ev, self.exc)


def _start_server(cfg: RunConfig) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["BENCH_HOST"] = cfg.host
    env["BENCH_PORT"] = str(cfg.port)
    env["PROFILIS_ENABLED"] = "1" if cfg.profilis_enabled else "0"
    env["PROFILIS_QUEUE_SIZE"] = str(cfg.queue_size)
    env["PROFILIS_FLUSH_INTERVAL"] = str(cfg.flush_interval)
    env["PROFILIS_SAMPLE"] = str(cfg.sample)
    if cfg.stats_file:
        env["BENCH_STATS_FILE"] = cfg.stats_file

    # Make Profilis import deterministic regardless of editable install behavior
    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = f"{root}:{root / 'src'}"

    if cfg.framework == "flask":
        cmd = [sys.executable, "-m", "bench.apps.flask_app"]
    elif cfg.framework == "fastapi":
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "bench.apps.fastapi_app:app",
            "--host",
            cfg.host,
            "--port",
            str(cfg.port),
            "--log-level",
            "warning",
            "--workers",
            "1",
        ]
    elif cfg.framework == "sanic":
        cmd = [sys.executable, "-m", "bench.apps.sanic_app"]
    else:
        raise ValueError(f"unknown framework: {cfg.framework}")

    return subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def _stop_server(p: subprocess.Popen[bytes]) -> None:
    if p.poll() is not None:
        return
    with _Suppress():
        p.terminate()  # SIGTERM (lets apps flush BENCH_COLLECTOR)
    try:
        p.wait(timeout=5.0)
        return
    except subprocess.TimeoutExpired:
        pass
    with _Suppress():
        p.send_signal(signal.SIGINT)
    with _Suppress():
        p.wait(timeout=3.0)
    if p.poll() is None:
        with _Suppress():
            p.kill()
        with _Suppress():
            p.wait(timeout=3.0)


def _parse_duration_s(s: str) -> float:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smh])", s.strip())
    if not m:
        raise ValueError(f"invalid duration: {s}")
    v = float(m.group(1))
    u = m.group(2)
    return v if u == "s" else (v * 60.0 if u == "m" else v * 3600.0)


def _percentile_ms(sorted_lat_s: list[float], q: float) -> float | None:
    if not sorted_lat_s:
        return None
    q = min(1.0, max(0.0, q))
    idx = round((len(sorted_lat_s) - 1) * q)
    return sorted_lat_s[idx] * 1000.0


def _run_py_client(cfg: RunConfig, url: str) -> dict[str, Any]:
    duration_s = _parse_duration_s(cfg.duration)
    stop_at = time.monotonic() + duration_s

    ok = 0
    err = 0
    lat_s: list[float] = []
    lock = threading.Lock()

    def worker() -> None:
        nonlocal ok, err
        while time.monotonic() < stop_at:
            t0 = time.perf_counter()
            try:
                _http_json(url, timeout_s=1.0)
                dt = time.perf_counter() - t0
                with lock:
                    ok += 1
                    lat_s.append(dt)
            except Exception:
                dt = time.perf_counter() - t0
                with lock:
                    err += 1
                    lat_s.append(dt)

    threads: list[threading.Thread] = []
    started = time.monotonic()
    for _ in range(max(1, cfg.connections)):
        t = threading.Thread(target=worker, daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    wall_s = max(0.000001, time.monotonic() - started)

    lat_sorted = sorted(lat_s)
    return {
        "tool": "py",
        "wall_s": wall_s,
        "ok": ok,
        "err": err,
        "rps": float(ok) / wall_s,
        "p50_ms": _percentile_ms(lat_sorted, 0.50),
        "p95_ms": _percentile_ms(lat_sorted, 0.95),
    }


def _run_tool(cfg: RunConfig) -> dict[str, Any]:
    url = f"http://{cfg.host}:{cfg.port}/work?n=2000"
    if cfg.tool == "py":
        return _run_py_client(cfg, url)

    if cfg.tool == "hey":
        cmd = ["hey", "-z", cfg.duration, "-c", str(cfg.connections), url]
    elif cfg.tool == "wrk":
        cmd = [
            "wrk",
            "-d",
            cfg.duration,
            "-c",
            str(cfg.connections),
            "-t",
            str(cfg.threads),
            "--latency",
            url,
        ]
    else:
        raise ValueError(f"unknown tool: {cfg.tool}")

    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    wall_s = max(0.000001, time.monotonic() - t0)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    parsed = _parse_tool_output(cfg.tool, out)
    parsed.update({"tool": cfg.tool, "exit_code": proc.returncode, "wall_s": wall_s, "raw": out})
    return parsed


def _parse_tool_output(tool: str, out: str) -> dict[str, Any]:
    def first_float(pat: str) -> float:
        m = re.search(pat, out)
        if not m:
            raise RuntimeError(f"failed to parse {tool} output: {pat}")
        return float(m.group(1))

    def first_dur_ms(pat: str) -> float:
        m = re.search(pat, out)
        if not m:
            raise RuntimeError(f"failed to parse {tool} output: {pat}")
        s = m.group(1).strip()
        m2 = re.fullmatch(r"([0-9.]+)(us|µs|ms|s)", s)
        if not m2:
            raise RuntimeError(f"unexpected duration: {s}")
        v = float(m2.group(1))
        u = m2.group(2)
        return v / 1000.0 if u in ("us", "µs") else (v if u == "ms" else v * 1000.0)

    rps = first_float(r"Requests/sec:\s+([0-9.]+)")
    if tool == "hey":
        return {
            "rps": rps,
            "p50_ms": first_dur_ms(r"50%\s+in\s+([0-9.]+[a-zµ]+)"),
            "p95_ms": first_dur_ms(r"95%\s+in\s+([0-9.]+[a-zµ]+)"),
        }
    if tool == "wrk":
        # wrk doesn't provide p95 directly (it prints 50/75/90/99). Keep p95 null.
        return {"rps": rps, "p50_ms": first_dur_ms(r"50%\s+([0-9.]+[a-zµ]+)"), "p95_ms": None}
    raise ValueError(tool)


def _results_dir() -> Path:
    d = Path(__file__).resolve().parent / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_results(framework: str, payload: dict[str, Any]) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = _results_dir() / f"{framework}-{ts}.json"
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def quick(args: argparse.Namespace) -> int:
    base = RunConfig(
        framework=args.framework,
        host=args.host,
        port=args.port,
        tool=args.tool,
        duration=args.duration,
        connections=args.connections,
        threads=args.threads,
        profilis_enabled=False,
        queue_size=args.queue_size,
        flush_interval=args.flush_interval,
        sample=args.sample,
    )

    results: dict[str, Any] = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "framework": args.framework,
        "mode": "quick",
        "config": {
            "tool": args.tool,
            "duration": args.duration,
            "connections": args.connections,
            "threads": args.threads,
            "profilis": {
                "queue_size": args.queue_size,
                "flush_interval": args.flush_interval,
                "sample": args.sample,
            },
        },
        "runs": [],
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for enabled in (False, True):
        stats_file = str(
            _results_dir() / f"stats-{args.framework}-{'on' if enabled else 'off'}-{ts}.json"
        )
        cfg = RunConfig(**{**asdict(base), "profilis_enabled": enabled, "stats_file": stats_file})
        p = _start_server(cfg)
        try:
            try:
                _wait_ok(cfg.host, cfg.port, timeout_s=20.0)
            except Exception as e:
                if p.poll() is not None:
                    out = b""
                    with _Suppress(Exception):
                        out = p.stdout.read() if p.stdout is not None else b""  # type: ignore[union-attr]
                    raise RuntimeError(
                        f"server exited during startup (code={p.returncode}). Output:\n{out.decode('utf-8', 'replace')}"
                    ) from e
                raise

            tool = _run_tool(cfg)
            wall_s = float(tool.get("wall_s", _parse_duration_s(cfg.duration)))

            results["runs"].append(
                {
                    "profilis_enabled": enabled,
                    "latency": {"p50_ms": tool.get("p50_ms"), "p95_ms": tool.get("p95_ms")},
                    "rps": tool.get("rps"),
                    "events_per_min": None,
                    "tool": tool,
                }
            )
        finally:
            _stop_server(p)
            out = b""
            with _Suppress(Exception):
                out = p.stdout.read() if p.stdout is not None else b""  # type: ignore[union-attr]
            collector = _parse_bench_collector(out)
            if results["runs"]:
                results["runs"][-1]["server_stdout"] = out.decode("utf-8", "replace")[-4000:]
                results["runs"][-1]["collector"] = collector
                results["runs"][-1]["stats_file"] = cfg.stats_file
                stats = None
                if cfg.stats_file:
                    with _Suppress(Exception):
                        stats = json.loads(Path(cfg.stats_file).read_text(encoding="utf-8"))
                if enabled:
                    processed = int((stats or collector or {}).get("processed", 0))
                    results["runs"][-1]["events_per_min"] = (
                        processed / max(0.000001, wall_s)
                    ) * 60.0
                if not enabled:
                    results["runs"][-1]["events_per_min"] = 0.0

    off = next(r for r in results["runs"] if not r["profilis_enabled"])
    on = next(r for r in results["runs"] if r["profilis_enabled"])
    results["deltas"] = {
        "p50_ms": _delta(on["latency"]["p50_ms"], off["latency"]["p50_ms"]),
        "p95_ms": _delta(on["latency"]["p95_ms"], off["latency"]["p95_ms"]),
        "rps": _delta(on["rps"], off["rps"]),
        "events_per_min": _delta(on["events_per_min"], off["events_per_min"]),
    }

    out = _write_results(args.framework, results)
    print(str(out))
    return 0


def _delta(a: Any, b: Any) -> float | None:
    try:
        if a is None or b is None:
            return None
        return float(a) - float(b)
    except Exception:
        return None


def soak(args: argparse.Namespace) -> int:
    # Headless locust run, writes CSV into bench/results/locust-*.csv
    base = RunConfig(
        framework=args.framework,
        host=args.host,
        port=args.port,
        tool="py",
        duration="1s",
        connections=1,
        threads=1,
        profilis_enabled=False,
        queue_size=args.queue_size,
        flush_interval=args.flush_interval,
        sample=args.sample,
    )

    results: dict[str, Any] = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "framework": args.framework,
        "mode": "soak",
        "config": {
            "users": args.users,
            "spawn_rate": args.spawn_rate,
            "time": args.time,
            "profilis": {
                "queue_size": args.queue_size,
                "flush_interval": args.flush_interval,
                "sample": args.sample,
            },
        },
        "runs": [],
    }

    locustfile = Path(__file__).resolve().parent / "soak_locustfile.py"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_prefix = _results_dir() / f"locust-{args.framework}-{ts}"

    for enabled in (False, True):
        stats_file = str(
            _results_dir() / f"stats-{args.framework}-soak-{'on' if enabled else 'off'}-{ts}.json"
        )
        cfg = RunConfig(**{**asdict(base), "profilis_enabled": enabled, "stats_file": stats_file})
        p = _start_server(cfg)
        try:
            _wait_ok(cfg.host, cfg.port, timeout_s=25.0)
            before = _http_json(f"http://{cfg.host}:{cfg.port}/metrics", timeout_s=5.0)

            host_url = f"http://{cfg.host}:{cfg.port}"
            cmd = [
                "locust",
                "-f",
                str(locustfile),
                "--headless",
                "-u",
                str(args.users),
                "-r",
                str(args.spawn_rate),
                "-t",
                args.time,
                "--host",
                host_url,
                "--csv",
                str(out_prefix) + ("-on" if enabled else "-off"),
                "--only-summary",
            ]

            t0 = time.monotonic()
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            wall_s = max(0.000001, time.monotonic() - t0)

            after = _http_json(f"http://{cfg.host}:{cfg.port}/metrics", timeout_s=5.0)
            events = int(after.get("processed", 0)) - int(before.get("processed", 0))
            events_per_min = (events / wall_s) * 60.0

            results["runs"].append(
                {
                    "profilis_enabled": enabled,
                    "locust": {
                        "exit_code": proc.returncode,
                        "wall_s": wall_s,
                        "stdout": proc.stdout,
                        "stderr": proc.stderr,
                        "csv_prefix": str(out_prefix) + ("-on" if enabled else "-off"),
                    },
                    "events_per_min": events_per_min,
                    "collector_before": before,
                    "collector_after": after,
                }
            )
        finally:
            _stop_server(p)

    out = _write_results(f"{args.framework}-soak", results)
    print(str(out))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bench")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quick")
    q.add_argument("--framework", choices=["flask", "fastapi", "sanic"], required=True)
    q.add_argument("--host", default="127.0.0.1")
    q.add_argument("--port", type=int, default=9011)
    q.add_argument("--tool", choices=["py", "hey", "wrk"], default="py")
    q.add_argument("--duration", default="20s")
    q.add_argument("--connections", type=int, default=50)
    q.add_argument("--threads", type=int, default=4)
    q.add_argument("--queue-size", type=int, default=2048)
    q.add_argument("--flush-interval", type=float, default=0.1)
    q.add_argument("--sample", type=float, default=1.0)
    q.set_defaults(func=quick)

    s = sub.add_parser("soak")
    s.add_argument("--framework", choices=["flask", "fastapi", "sanic"], required=True)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=9011)
    s.add_argument("--users", type=int, default=50)
    s.add_argument("--spawn-rate", type=int, default=5)
    s.add_argument("--time", default="30m")
    s.add_argument("--queue-size", type=int, default=2048)
    s.add_argument("--flush-interval", type=float, default=0.1)
    s.add_argument("--sample", type=float, default=1.0)
    s.set_defaults(func=soak)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
