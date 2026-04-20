from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import os
import random
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Target:
    name: str
    method: str
    path: str
    weight: int = 1
    headers: dict[str, str] | None = None
    body_json: dict[str, Any] | None = None


def _one(base_url: str, t: Target, timeout: float) -> tuple[str, bool, float, int]:
    url = base_url.rstrip("/") + t.path
    data = None
    headers = dict(t.headers or {})
    if t.body_json is not None:
        raw = json.dumps(t.body_json).encode("utf-8")
        data = raw
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=t.method.upper())
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read(64)
            dt = time.perf_counter() - t0
            return t.name, True, dt, int(getattr(resp, "status", 0) or 0)
    except urllib.error.HTTPError as e:
        dt = time.perf_counter() - t0
        return t.name, False, dt, int(getattr(e, "code", 0) or 0)
    except Exception:
        dt = time.perf_counter() - t0
        # 0 = connect/reset/timeout kabi “network” xato
        return t.name, False, dt, 0


def _pct(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(p * (len(sorted_vals) - 1))
    return sorted_vals[idx]


def main() -> int:
    ap = argparse.ArgumentParser(description="Mixed HTTP load test (no deps).")
    ap.add_argument("--base", default="http://127.0.0.1:8001", help="Base URL (no trailing slash)")
    ap.add_argument("--requests", type=int, default=2000, help="Total requests")
    ap.add_argument("--concurrency", type=int, default=100, help="Parallel workers")
    ap.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout seconds")
    ap.add_argument(
        "--bearer",
        default=os.environ.get("API_BEARER_TOKEN", ""),
        help="Bearer token for /api/bot/* (defaults to API_BEARER_TOKEN env)",
    )
    args = ap.parse_args()

    base = args.base
    n = int(args.requests)
    c = max(1, int(args.concurrency))
    timeout = float(args.timeout)
    bearer = (args.bearer or "").strip()

    common_get = [
        Target("home", "GET", "/", weight=40),
        Target("charities_list", "GET", "/hayriyalar/", weight=25),
        Target("robots", "GET", "/robots.txt", weight=5),
        Target("sitemap", "GET", "/sitemap.xml", weight=5),
        Target("sw", "GET", "/sw.js", weight=5),
    ]

    bot_headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    # register endpoint DBga yozadi; telegram_id random bo'lsa idempotent emas, lekin test uchun OK.
    bot_post = Target(
        "bot_register",
        "POST",
        "/api/bot/register/",
        weight=20,
        headers=bot_headers,
        body_json={
            "telegram_id": "0",
            "phone": "+998900000000",
            "first_name": "Load",
            "last_name": "Test",
        },
    )

    targets = list(common_get)
    if bearer:
        targets.append(bot_post)

    # weighted choice pool
    pool: list[Target] = []
    for t in targets:
        pool.extend([t] * max(1, int(t.weight)))

    print(f"Base: {base}")
    print(f"Requests: {n}, concurrency: {c}, timeout: {timeout}s")
    print("Mix:", ", ".join([f"{t.name}*{t.weight}" for t in targets]))
    if not bearer:
        print("NOTE: bearer yo'q, bot_register mix o'chirildi.")

    stats: dict[str, dict[str, Any]] = {}
    for t in targets:
        stats[t.name] = {"ok": 0, "n": 0, "codes": {}, "dts": []}

    def submit_payload() -> Target:
        t = random.choice(pool)
        if t.name == "bot_register":
            # telegram_id unique-ish qilib yuboramiz
            tid = str(random.randint(10_000_000, 99_999_999))
            body = dict(t.body_json or {})
            body["telegram_id"] = tid
            return Target(
                name=t.name,
                method=t.method,
                path=t.path,
                weight=t.weight,
                headers=t.headers,
                body_json=body,
            )
        return t

    t_start = time.perf_counter()
    with futures.ThreadPoolExecutor(max_workers=c) as ex:
        futs = [ex.submit(_one, base, submit_payload(), timeout) for _ in range(n)]
        for f in futures.as_completed(futs):
            name, success, dt, code = f.result()
            s = stats[name]
            s["n"] += 1
            s["dts"].append(dt)
            s["codes"][code] = s["codes"].get(code, 0) + 1
            if success and 200 <= code < 400:
                s["ok"] += 1

    elapsed = time.perf_counter() - t_start
    print("")
    print("=== Per-endpoint summary ===")
    for name, s in stats.items():
        n1 = int(s["n"])
        if not n1:
            continue
        dts_sorted = sorted(s["dts"])
        ok1 = int(s["ok"])
        rps = n1 / elapsed if elapsed > 0 else 0.0
        codes = dict(sorted(s["codes"].items(), key=lambda x: x[0]))
        p50 = _pct(dts_sorted, 0.50) * 1000
        p90 = _pct(dts_sorted, 0.90) * 1000
        p99 = _pct(dts_sorted, 0.99) * 1000
        avg = statistics.mean(dts_sorted) * 1000
        mx = max(dts_sorted) * 1000
        print(
            f"- {name}: ok={ok1}/{n1} rps={rps:.1f} "
            f"p50={p50:.1f}ms p90={p90:.1f}ms p99={p99:.1f}ms avg={avg:.1f}ms max={mx:.1f}ms codes={codes}"
        )

    print("")
    total_ok = sum(int(s["ok"]) for s in stats.values())
    total_n = sum(int(s["n"]) for s in stats.values())
    print("=== Total ===")
    print(f"Total time: {elapsed:.2f}s")
    print(f"Success (2xx/3xx): {total_ok}/{total_n}")

    return 0 if total_ok == total_n else 2


if __name__ == "__main__":
    raise SystemExit(main())

