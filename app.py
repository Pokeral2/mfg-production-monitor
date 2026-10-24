"""Cloud-Based Manufacturing Production Monitoring and Downtime Tracking System.

Flask backend + SQLite storage + HTML dashboard.
Run locally:  python app.py   ->  http://localhost:5000
"""
import os
import sqlite3
import time

from flask import Flask, jsonify, request

DB_PATH = os.environ.get("DB_PATH", os.path.join("data", "production.db"))
VALID_STATUS = {"Running", "Idle", "Down"}

app = Flask(__name__)


def get_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS records (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   machine_id TEXT NOT NULL,
                   status TEXT NOT NULL,
                   units INTEGER NOT NULL,
                   ts REAL NOT NULL)"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS downtime (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   machine_id TEXT NOT NULL,
                   reason TEXT NOT NULL,
                   start_ts REAL NOT NULL,
                   end_ts REAL)"""
        )


init_db()


@app.route("/health")
def health():
    """Health check: confirms the app is up AND the database is reachable."""
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        return jsonify(status="ok", time=time.time()), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify(status="error", detail=str(exc)), 500


@app.route("/api/record", methods=["POST"])
def add_record():
    data = request.get_json(silent=True) or {}
    machine_id = str(data.get("machine_id", "")).strip()
    status = data.get("status")
    try:
        units = int(data.get("units", 0))
    except (TypeError, ValueError):
        return jsonify(error="units must be an integer"), 400
    if not machine_id or status not in VALID_STATUS or units < 0:
        return jsonify(error="need machine_id, status in Running/Idle/Down, units >= 0"), 400

    now = time.time()
    with get_db() as db:
        db.execute(
            "INSERT INTO records (machine_id, status, units, ts) VALUES (?,?,?,?)",
            (machine_id, status, units, now),
        )
        open_dt = db.execute(
            "SELECT id FROM downtime WHERE machine_id=? AND end_ts IS NULL", (machine_id,)
        ).fetchone()
        if status in ("Idle", "Down") and open_dt is None:
            db.execute(
                "INSERT INTO downtime (machine_id, reason, start_ts) VALUES (?,?,?)",
                (machine_id, status, now),
            )
        elif status == "Running" and open_dt is not None:
            db.execute("UPDATE downtime SET end_ts=? WHERE id=?", (now, open_dt["id"]))
    return jsonify(message="recorded"), 201


@app.route("/api/machines")
def machines():
    now = time.time()
    out = []
    with get_db() as db:
        ids = [r["machine_id"] for r in db.execute("SELECT DISTINCT machine_id FROM records ORDER BY machine_id")]
        for mid in ids:
            last = db.execute(
                "SELECT status, ts FROM records WHERE machine_id=? ORDER BY id DESC LIMIT 1", (mid,)
            ).fetchone()
            total = db.execute(
                "SELECT COALESCE(SUM(units),0) AS u FROM records WHERE machine_id=?", (mid,)
            ).fetchone()["u"]
            recent = db.execute(
                "SELECT COALESCE(SUM(units),0) AS u FROM records WHERE machine_id=? AND ts>=?",
                (mid, now - 60),
            ).fetchone()["u"]
            dt = db.execute(
                "SELECT COALESCE(SUM(COALESCE(end_ts, ?) - start_ts),0) AS s FROM downtime WHERE machine_id=?",
                (now, mid),
            ).fetchone()["s"]
            out.append(
                {
                    "machine_id": mid,
                    "status": last["status"],
                    "last_update_age_s": round(now - last["ts"], 1),
                    "total_units": total,
                    "units_last_minute": recent,
                    "downtime_seconds": round(dt, 1),
                }
            )
    return jsonify(machines=out)


@app.route("/api/downtime")
def downtime():
    now = time.time()
    with get_db() as db:
        rows = db.execute("SELECT * FROM downtime ORDER BY id DESC LIMIT 20").fetchall()
    events = [
        {
            "machine_id": r["machine_id"],
            "reason": r["reason"],
            "start": time.strftime("%H:%M:%S", time.localtime(r["start_ts"])),
            "end": time.strftime("%H:%M:%S", time.localtime(r["end_ts"])) if r["end_ts"] else "ongoing",
            "duration_s": round((r["end_ts"] or now) - r["start_ts"], 1),
        }
        for r in rows
    ]
    return jsonify(events=events)


DASHBOARD = """<!doctype html>
<html><head><meta charset="utf-8"><title>Production Monitor</title>
<style>
 body{font-family:Arial,sans-serif;margin:24px;background:#f4f6f8;color:#222}
 h1{margin-bottom:4px} .sub{color:#666;margin-bottom:16px}
 .cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
 .card{background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 3px #0002;min-width:120px}
 .card b{font-size:22px;display:block}
 table{border-collapse:collapse;width:100%;background:#fff;margin-bottom:24px}
 th,td{padding:8px 10px;border-bottom:1px solid #eee;text-align:left}
 th{background:#263238;color:#fff}
 .Running{color:#1b8a3a;font-weight:bold}.Idle{color:#c78a00;font-weight:bold}.Down{color:#c62828;font-weight:bold}
</style></head><body>
<h1>Manufacturing Production Monitor</h1>
<div class="sub">Simulated machine data &middot; auto-refreshes every 3 s</div>
<div class="cards">
 <div class="card">Total units<b id="tu">-</b></div>
 <div class="card">Units / min<b id="rate">-</b></div>
 <div class="card">Total downtime (s)<b id="td">-</b></div>
 <div class="card">Machines down/idle<b id="nd">-</b></div>
</div>
<h3>Machine status</h3>
<table><thead><tr><th>Machine</th><th>Status</th><th>Total units</th><th>Units (last min)</th><th>Downtime (s)</th><th>Last update (s ago)</th></tr></thead>
<tbody id="m"></tbody></table>
<h3>Recent downtime events</h3>
<table><thead><tr><th>Machine</th><th>Reason</th><th>Start</th><th>End</th><th>Duration (s)</th></tr></thead>
<tbody id="d"></tbody></table>
<script>
async function refresh(){
 try{
  const m=(await (await fetch('/api/machines')).json()).machines;
  const d=(await (await fetch('/api/downtime')).json()).events;
  document.getElementById('tu').textContent=m.reduce((a,x)=>a+x.total_units,0);
  document.getElementById('rate').textContent=m.reduce((a,x)=>a+x.units_last_minute,0);
  document.getElementById('td').textContent=m.reduce((a,x)=>a+x.downtime_seconds,0).toFixed(0);
  document.getElementById('nd').textContent=m.filter(x=>x.status!=='Running').length;
  document.getElementById('m').innerHTML=m.map(x=>`<tr><td>${x.machine_id}</td><td class="${x.status}">${x.status}</td><td>${x.total_units}</td><td>${x.units_last_minute}</td><td>${x.downtime_seconds}</td><td>${x.last_update_age_s}</td></tr>`).join('');
  document.getElementById('d').innerHTML=d.map(x=>`<tr><td>${x.machine_id}</td><td>${x.reason}</td><td>${x.start}</td><td>${x.end}</td><td>${x.duration_s}</td></tr>`).join('');
 }catch(e){console.log(e)}
}
refresh(); setInterval(refresh,3000);
</script></body></html>"""


@app.route("/")
def dashboard():
    return DASHBOARD


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
