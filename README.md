# 🚨 incopilot — AI-Powered Incident Triage CLI

![backend](https://img.shields.io/badge/backend-Python-3776AB?logo=python&logoColor=white)
![cli](https://img.shields.io/badge/cli-Click-brightgreen?logo=gnometerminal&logoColor=white)
![sources](https://img.shields.io/badge/sources-journalctl%20%7C%20Docker%20%7C%20File-blueviolet)
![license](https://img.shields.io/badge/license-MIT-blue)
![status](https://img.shields.io/badge/status-live-brightgreen)

> Run one command during an incident. Get instant log collection, pattern extraction,
> Four Golden Signal mapping, and a structured report — from **systemd journal**, **Docker**, or any log file.
>
> **No SaaS. No dashboard. No database connection. Just your terminal.**

---

## What It Does

incopilot automates the first-response pass that every on-call engineer repeats manually:

1. **Collect** — pulls recent logs from `journalctl`, `docker logs`, or a plain log file for a configurable time window
2. **Extract** — identifies high-signal lines: errors, warnings, timeouts, OOMs, restarts, connection failures
3. **Map** — classifies findings against the **Four Golden Signals** (Latency · Traffic · Errors · Saturation)
4. **Report** — writes `out/report.md` (human-readable) and `out/report.json` (automation-ready) with copy/pasteable next steps

---

## Features

- 📥 **3 Log Sources** — `journalctl` (systemd), `docker logs`, plain log file path
- 🗺️ **Four Golden Signals** — auto-maps log patterns to Latency, Traffic, Errors, Saturation
- 📋 **Dual Output** — `report.md` for humans, `report.json` for pipelines and alerting tools
- ⚡ **Single Command** — one CLI invocation covers collection, analysis, and reporting
- 🔀 **Bundle Mode** — analyze journal + Docker container together in one run
- 🔒 **Safe by Design** — suggestions only, no destructive actions ever executed
- 🐍 **Pure Python** — no agents, no cloud APIs, no external services required

---

## Live CLI

```bash
# systemd journal — last 30 minutes of nginx
python -m incopilot journal --unit nginx --since "30 min ago"

# Docker container — last 1 hour
python -m incopilot docker --container my-api --since 1h

# Both sources together (bundle mode)
python -m incopilot bundle \
  --unit nginx \
  --container my-api \
  --since-journal "30 min ago" \
  --since-docker 1h

# Plain log file
python -m incopilot file --path ./sample.log
```

**Outputs written to:**
```
out/report.md    ← structured incident summary (copy/pasteable)
out/report.json  ← machine-readable for pipelines and alerting
```

### Example Report Output

```markdown
## Incident Summary
- Time range:            last 30 min
- Sources analyzed:      nginx (journalctl)
- Total lines collected: 1,842
- High-signal lines:     37

## Four Golden Signals
- 🔴 Errors       — 24 occurrences  (upstream connect error, 502 Bad Gateway)
- 🟡 Latency      — 8 occurrences   (upstream response time > 2s)
- 🟢 Traffic      — nominal
- 🟢 Saturation   — nominal

## Top Recurring Patterns
1. "upstream connect error or disconnect/reset"           — 18x
2. "recv() failed (104: Connection reset by peer)"        — 6x

## Suggested Next Steps
- Check upstream service health: systemctl status my-api
- Tail live logs:                journalctl -u nginx -f
- Review upstream timeout config in nginx.conf
```

---

## Architecture

```
Terminal (CLI)
│
│  python -m incopilot journal | docker | bundle | file
│
└──► cli.py  (Click CLI entrypoint)
          │
          ├──► collectors.py      ← journalctl / docker logs / file reader
          │         │
          │         └── raw log lines (time-windowed)
          │
          ├──► analyzer.py        ← pattern extraction + Four Golden Signal mapping
          │         │
          │         └── findings[]  {signal, pattern, count, severity}
          │
          └──► reporter.py        ← renders report.md + report.json
                    │
                    └── out/report.md
                        out/report.json
```

**Stack:**
- Language: Python 3.10+
- CLI: [Click](https://click.palletsprojects.com/)
- Log sources: `subprocess` → `journalctl`, `docker logs`
- Config: `config.py` / `config_extended.py`
- Output: Markdown + JSON (stdlib only, zero external dependencies for reporting)

---

## Run Locally

**Prerequisites:** Python 3.10+, `journalctl` and/or Docker CLI available on your system

```bash
# Clone
git clone https://github.com/AutoShiftOps/incopilot
cd incopilot

# Install
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run
python -m incopilot journal --unit nginx --since "30 min ago"

# View report
cat out/report.md
```

---

## Project Structure

```
incopilot/
├── incopilot/
│   ├── __main__.py          # Entry point  (python -m incopilot)
│   ├── cli.py               # Click CLI — subcommands: journal, docker, bundle, file
│   ├── collectors.py        # Log collectors — journalctl, docker logs, file reader
│   ├── analyzer.py          # Pattern extraction + Four Golden Signal classifier
│   ├── reporter.py          # report.md + report.json writer
│   ├── config.py            # Base configuration (time window, line limits)
│   └── config_extended.py   # Extended config (custom patterns, signal overrides)
├── out/                     # Generated reports (git-ignored)
├── scripts/                 # Helper scripts
├── systemd/                 # Systemd service/timer unit examples
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Configuration

| Flag | Default | Description |
|---|---|---|
| `--since` | `30 min ago` | Time window for journal / docker sources |
| `--unit` | — | systemd unit name (e.g. `nginx`, `postgresql`) |
| `--container` | — | Docker container name or ID |
| `--path` | — | Path to a plain log file |
| `--since-journal` | `30 min ago` | Journal time window in bundle mode |
| `--since-docker` | `1h` | Docker time window in bundle mode |

Custom pattern overrides and signal classification rules can be set in `incopilot/config_extended.py`.

---

## Roadmap

- [ ] AI layer — LLM-powered root cause hypothesis (HuggingFace / OpenAI)
- [ ] Kubernetes pod logs source (`kubectl logs`)
- [ ] Slack / PagerDuty webhook output
- [ ] GitHub Action: `incopilot-triage` for automated post-deploy checks
- [ ] Interactive TUI mode (Rich)
- [ ] Schema-aware log parsing (structured JSON logs)

---

## Contributing

Issues and PRs welcome. Please open an issue before submitting a large change.

```bash
git checkout -b feature/your-feature
# make changes
git commit -m "feat: describe your change"
git push origin feature/your-feature
# open a pull request
```

---

## License

MIT © 2026 [AutoShiftOps](https://github.com/AutoShiftOps)

Built by [Sudhakar Sajja](https://github.com/AutoShiftOps) — Application Architect, TechMahindra