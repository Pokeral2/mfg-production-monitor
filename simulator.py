"""Simulates 5 factory machines sending production data to the API.

Usage:  python simulator.py                      (talks to http://localhost:5000)
        python simulator.py --url http://<EC2-IP>:5000 --interval 2
"""
import argparse
import json
import random
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:5000")
parser.add_argument("--interval", type=float, default=2.0, help="seconds between rounds")
args = parser.parse_args()

machines = {f"M{i}": "Running" for i in range(1, 6)}


def next_status(current):
    r = random.random()
    if current == "Running":
        return "Down" if r < 0.04 else "Idle" if r < 0.10 else "Running"
    return "Running" if r < 0.30 else current  # downtime lasts a few rounds


def post(payload):
    req = urllib.request.Request(
        args.url + "/api/record",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=5).read()


print(f"Sending simulated data to {args.url} every {args.interval}s (Ctrl+C to stop)")
while True:
    for mid in machines:
        machines[mid] = next_status(machines[mid])
        units = random.randint(1, 5) if machines[mid] == "Running" else 0
        payload = {"machine_id": mid, "status": machines[mid], "units": units}
        try:
            post(payload)
            print(payload)
        except Exception as exc:  # server down = exactly what we want to observe
            print("send failed:", exc)
    time.sleep(args.interval)
