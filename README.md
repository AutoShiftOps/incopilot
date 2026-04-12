# AI Incident Copilot (CLI)

A practical incident-triage CLI that collects recent logs from **systemd journal** (journalctl) and/or **Docker** (docker logs), extracts high-signal patterns, maps them to the **Four Golden Signals**, and generates a `report.md` and `report.json`.

## Why this exists
During an incident, responders often repeat the same steps: pull recent logs, search for recurring errors, and decide what to check next. This tool automates the first pass and produces a copy/pasteable incident artifact.

## Features
- Sources: `journalctl`, `docker logs`, plain log file
- Outputs: `out/report.md`, `out/report.json`
- Safe by design: **suggestions only** (no destructive actions)

## Quickstart

### 1) Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Run
```bash
# systemd journal
python -m incopilot journal --unit nginx --since "30 min ago"

# docker
python -m incopilot docker --container my-api --since 1h

# both
python -m incopilot bundle --unit nginx --container my-api --since-journal "30 min ago" --since-docker 1h

# file
python -m incopilot file --path ./sample.log
```

## License
MIT
