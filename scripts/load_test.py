from __future__ import annotations

import argparse
import concurrent.futures as futures
import statistics
import time
import urllib.error
import urllib.request


def _one(url: str, timeout: float) -> tuple[bool, float, int]:
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read(64)
            dt = time.perf_counter() - t0
            return True, dt, int(getattr(resp, "status", 0) or 0)
    except urllib.error.HTTPError as e:
        dt = time.perf_counter() - t0
        return False, dt, int(getattr(e, "code", 0) or 0)
    except Exception:
        dt = time.perf_counter() - t0
        return False, dt, 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Simple HTTP load test (no deps).")
    ap.add_argument("--url", default="http://127.0.0.1:8000/", help="Base URL to hit")
    ap.add_argument("--requests", type=int, default=1000, help="Total requests")
    ap.add_argument("--concurrency", type=int, default=50, help="Parallel workers")
    ap.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout seconds")
    args = ap.parse_args()

    url = args.url
    n = int(args.requests)
    c = max(1, int(args.concurrency))
    timeout = float(args.timeout)

    print(f"Target: {url}")
    print(f"Requests: {n}, concurrency: {c}, timeout: {timeout}s")

    t_start = time.perf_counter()
    ok = 0
    codes: dict[int, int] = {}
    dts: list[float] = []

    with futures.ThreadPoolExecutor(max_workers=c) as ex:
        futs = [ex.submit(_one, url, timeout) for _ in range(n)]
        for f in futures.as_completed(futs):
            success, dt, code = f.result()
            dts.append(dt)
            codes[code] = codes.get(code, 0) + 1
            if success and 200 <= code < 400:
                ok += 1

    elapsed = time.perf_counter() - t_start
    rps = n / elapsed if elapsed > 0 else 0.0

    dts_sorted = sorted(dts)
    p50 = dts_sorted[int(0.50 * (len(dts_sorted) - 1))] if dts_sorted else 0
    p90 = dts_sorted[int(0.90 * (len(dts_sorted) - 1))] if dts_sorted else 0
    p99 = dts_sorted[int(0.99 * (len(dts_sorted) - 1))] if dts_sorted else 0

    print("")
    print("=== Summary ===")
    print(f"Total time: {elapsed:.2f}s")
    print(f"RPS: {rps:.2f}")
    print(f"Success (2xx/3xx): {ok}/{n}")
    print("Status codes:", dict(sorted(codes.items(), key=lambda x: x[0])))
    print(f"Latency p50={p50*1000:.1f}ms p90={p90*1000:.1f}ms p99={p99*1000:.1f}ms")
    print(f"Latency avg={statistics.mean(dts)*1000:.1f}ms max={max(dts)*1000:.1f}ms")

    return 0 if ok == n else 2


if __name__ == "__main__":
    raise SystemExit(main())

