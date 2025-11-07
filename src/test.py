#!/usr/bin/env python3
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import csv
import json
import time
import os

RADIUS_SERVER = "x.x.x.x"
RADIUS_PORT = 1812
SECRET = "testing123"
PASSWORD = "password"
NAS_IP = "x.x.x.x"

TOTAL_REQUESTS = 1000
CONCURRENCY = 50
TIMEOUT_SEC = 10
USER_START = 1
USER_END = 10000
USER_TEMPLATE = "TST{:07d}"

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

def send_request(idx):
    user_number = USER_START + (idx % (USER_END - USER_START + 1))
    username = USER_TEMPLATE.format(user_number)

    cmd = (
        f'echo "User-Name = {username}, User-Password = {PASSWORD}, '
        f'NAS-IP-Address = {NAS_IP}" | radclient -x {RADIUS_SERVER}:{RADIUS_PORT} auth {SECRET}'
    )

    start = time.time()
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT_SEC
        )
        elapsed = time.time() - start
        output = result.stdout

        if "Access-Accept" in output:
            status = "SUCCESS"
        elif "Access-Reject" in output:
            status = "REJECT"
        else:
            status = "ERROR"
    except Exception as e:
        elapsed = time.time() - start
        status = "ERROR"
        output = str(e)

    return {
        "id": idx,
        "username": username,
        "status": status,
        "time_sec": elapsed,
        "output": output,
    }


def print_text_summary(results, summary):
    print("\n=== RADIUS Load Test Summary ===")
    print(f"Server           : {summary['server']}")
    print(f"Total Requests   : {summary['requests_total']}")
    print(f"Concurrency      : {summary['concurrency']}")
    print(f"Success          : {summary['success']}")
    print(f"Reject           : {summary['reject']}")
    print(f"Error            : {summary['error']}")
    print(f"Total Time (sec) : {summary['total_time_sec']:.2f}")
    print(f"Throughput (req/s): {summary['throughput_req_per_sec']:.2f}")

    times = [r["time_sec"] for r in results if r["status"] == "SUCCESS"]
    if times:
        times.sort()
        avg = sum(times) / len(times)
        p95 = times[int(len(times) * 0.95) - 1]
        mx = max(times)
        print(f"Avg Response Time (s)  : {avg:.3f}")
        print(f"P95 Response Time (s)  : {p95:.3f}")
        print(f"Max Response Time (s)  : {mx:.3f}")
    else:
        print("No successful requests to calculate response times.")


def main():
    results = []
    start_time = time.time()

    print(f"Start RADIUS load test: {TOTAL_REQUESTS} requests, concurrency={CONCURRENCY}")

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(send_request, i) for i in range(TOTAL_REQUESTS)]
        for future in as_completed(futures):
            results.append(future.result())

    total_time = time.time() - start_time

    success = sum(1 for r in results if r["status"] == "SUCCESS")
    reject = sum(1 for r in results if r["status"] == "REJECT")
    error = sum(1 for r in results if r["status"] == "ERROR")
    throughput = TOTAL_REQUESTS / total_time if total_time > 0 else 0

    summary = {
        "timestamp": datetime.now().isoformat(),
        "server": RADIUS_SERVER,
        "requests_total": TOTAL_REQUESTS,
        "concurrency": CONCURRENCY,
        "success": success,
        "reject": reject,
        "error": error,
        "total_time_sec": total_time,
        "throughput_req_per_sec": throughput,
    }

    csv_file = f"{RESULTS_DIR}/radius_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "username", "status", "time_sec", "output"])
        writer.writeheader()
        writer.writerows(results)

    json_file = f"{RESULTS_DIR}/radius_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_file, "w") as f:
        json.dump(summary, f, indent=2)

    print_text_summary(results, summary)


if __name__ == "__main__":
    main()
