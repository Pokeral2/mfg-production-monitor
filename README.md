# Cloud-Based Manufacturing Production Monitoring and Downtime Tracking System

A small cloud-computing mini project. A Flask application receives **simulated** machine data, stores it in SQLite, shows a live dashboard (machine status, units produced, production rate, downtime), and logs downtime events automatically. It is packaged with Docker and designed for deployment on AWS EC2 with CloudWatch monitoring.

## Project status

| Item | Status |
|---|---|
| Flask API, SQLite storage, dashboard, `/health` endpoint | Done (tested locally) |
| Machine simulator | Done (tested locally) |
| Dockerfile | Written |
| Docker build and run test | Planned |
| AWS EC2 deployment, CloudWatch monitoring | Planned |
| Latency, availability and TTR measurements | Planned (no results yet) |

## Files

- `app.py`: backend API and dashboard page
- `simulator.py`: simulates 5 machines sending data
- `requirements.txt`: Python dependencies
- `Dockerfile`: container image definition

## Run locally

```
pip install flask
python app.py
```

In a second terminal:

```
python simulator.py
```

Open http://localhost:5000 in a browser. Health check: http://localhost:5000/health

## API

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Dashboard |
| `/health` | GET | Health check (app + database) |
| `/api/record` | POST | Submit a record: `{"machine_id": "M1", "status": "Running", "units": 3}` |
| `/api/machines` | GET | Per-machine status and totals |
| `/api/downtime` | GET | Recent downtime events |

Valid statuses: `Running`, `Idle`, `Down`.

## Run with Docker (planned test)

```
docker build -t mfg-monitor .
docker run -d --name mfg -p 5000:5000 -v mfgdata:/data mfg-monitor
```

The `-v mfgdata:/data` volume keeps the database when the container is removed.

## Design targets (not measured results)

- Availability: 99.5% during the test window
- Response time: under 2 s for 95% of requests
- TTR (time to recovery): under 5 minutes, from detection to verified restoration

## Limitations

Simulated data only, single server, SQLite (not built for many concurrent writers), no authentication.
