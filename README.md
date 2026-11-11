# incopilot

Read-only incident triage for logs. One command collects logs from **systemd, Docker, Kubernetes or a file**, maps what it finds to the **Four Golden Signals**, and writes a report with the order things went wrong and safe checks to run next.

[![CI](https://github.com/AutoShiftOps/incopilot/actions/workflows/ci.yml/badge.svg)](https://github.com/AutoShiftOps/incopilot/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776AB)
![license](https://img.shields.io/badge/license-MIT-blue)

**Correlate and explain, never auto-act.** incopilot never changes the systems it reads. It works offline with no account and no agent. An AI hypothesis is available if you bring your own key, and it is off by default.

Website: https://autoshiftops.github.io/incopilot/

## Quick start

```bash
pip install git+https://github.com/AutoShiftOps/incopilot

# try it on the bundled example incident
git clone https://github.com/AutoShiftOps/incopilot && cd incopilot
incopilot file --path examples/checkout-incident.log --packs core,nginx
cat out/report.md
```

```text
Overall severity: CRITICAL
15 lines analyzed, 13 matched, 2 filtered as noise

 Finding                    Signal      Severity  Count
 Out of memory              saturation  critical      1
 HTTP 5xx responses         errors      high          5
 Timeouts                   latency     high          4
 Connection limit reached   saturation  high          2
 ...
First to appear: Slow operations
```

The report shows that slow queries came first, then the connection pool filled, then timeouts and 5xx, and the out-of-memory kill came last. That ordering is the point: the loudest error is often not the cause.

## See it as a dashboard

```bash
incopilot file --path examples/checkout-incident.log --html
# open out/report.html in a browser
```

`--html` writes a self-contained `report.html`: overall severity, the Four Golden Signals, a timeline of when each problem first appeared, findings, and the checks to run next. Nothing is loaded from a server and the report data stays in the file.

The terminal output already shows severity, golden signals, findings and the order of first appearance. Use `--html` when you need to share the result with people who were not at the terminal, for example in an incident channel or a postmortem.

A [live example](https://autoshiftops.github.io/incopilot/viewer.html) is on the website.

## Sources

```bash
# systemd journal
incopilot journal --unit nginx --since "30 min ago"

# Docker container (stdout and stderr)
incopilot docker --container my-api --since 1h

# Kubernetes: a pod, a workload, or a label selector
incopilot k8s --pod deploy/api -n prod --since 30m
incopilot k8s -l app=api -n prod --previous        # the container that just crashed

# a file, a .gz file, or stdin
incopilot file --path /var/log/app.log
kubectl logs deploy/api | incopilot file --path -

# several sources as one timeline
incopilot bundle --unit nginx --container my-api --pod deploy/api -n prod
```

## What you get

`out/report.md` for people and `out/report.json` for pipelines (plus `out/report.html` with `--html`), containing:

- **Overall severity** (none, low, medium, high, critical) and a severity per finding
- **Four Golden Signals**: which of latency, traffic, errors and saturation are affected
- **Order of first appearance**: which pattern showed up first
- **Read-only checks to run next**, filled in with your unit, container or pod
- **Top repeating lines**, with timestamps, IDs and IPs normalized so repeats group together
- **Redacted examples** for every finding

Plain text, JSON lines, logfmt and `kubectl --prefix --timestamps` output are all understood. Health-check lines are filtered unless they report an error.

## Options

Options go after the source, for example `incopilot file --path app.log --json`.

| Option | Purpose |
|---|---|
| `--packs core,nginx` | Pattern packs: `core`, `nginx`, `postgres`, `node`, `kubernetes`, `jvm`, `all`. Default `core` |
| `--config FILE` | Settings file. `./incopilot.toml` is loaded automatically if present |
| `--out-dir DIR` | Where reports are written. Default `out` |
| `--html` | Also write `report.html`, a self-contained dashboard |
| `--json` | Print the JSON report to stdout and nothing else |
| `--no-write`, `-q` | Skip report files; no console output |
| `--fail-on LEVEL` | Exit `3` when overall severity is at or above `low`, `medium`, `high` or `critical` |
| `--max-bytes N` | Analyze only the last N bytes. Default 5,000,000 |
| `--timeout N` | Seconds to wait for `journalctl`, `docker` or `kubectl`. Default 60 |
| `--no-redact`, `--redact-ips` | Turn secret masking off; also mask IPv4 addresses |
| `--ai`, `--ai-provider`, `--ai-model` | Optional AI hypothesis, see below |

Exit codes: `0` success, `1` could not collect or write, `2` usage error, `3` `--fail-on` threshold met.

## Use it in CI or on a timer

```bash
# fail a post-deploy check if the new pods log anything high or critical
incopilot k8s -l app=api -n prod --since 10m --fail-on high --quiet
```

`systemd/` has an example service and timer for scheduled runs. A `Dockerfile` is included for piping logs through a container:

```bash
docker build -t incopilot .
kubectl logs deploy/api | docker run --rm -i incopilot file --path - --json --no-write
```

## Your own patterns

Copy `examples/incopilot.toml` to `./incopilot.toml`:

```toml
packs = ["core", "postgres"]

[[patterns]]
key = "ledger_mismatch"
regex = "ledger mismatch"
signal = "errors"        # latency | traffic | errors | saturation
severity = "critical"    # low | medium | high | critical
title = "Ledger mismatch"
advice = "Compare the ledger totals for the affected account before retrying."
```

The same file can replace the noise filter and add redaction rules.

## Optional AI hypothesis

```bash
export ANTHROPIC_API_KEY=...                       # or OPENAI_API_KEY
incopilot k8s --pod deploy/api -n prod --ai

# any OpenAI-compatible endpoint, or a local model with no key at all
incopilot file --path app.log --ai --ai-provider ollama --ai-model llama3.1
```

- **Off by default.** Without `--ai`, nothing leaves your machine.
- **Only the redacted summary is sent**: counts, order of appearance, up to two redacted example lines per finding, and the top repeating lines. Never the raw log, and never anything with `--no-redact`.
- **The answer is text for you to read.** It is labeled unverified in the report and nothing in it is executed.
- **Log content is treated as untrusted** in the prompt, so text inside a log line cannot give the model instructions.
- If the call fails, the rest of the report is still produced.

Environment: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `INCOPILOT_AI_KEY`; `INCOPILOT_AI_PROVIDER`, `INCOPILOT_AI_MODEL`, `INCOPILOT_AI_BASE_URL`.

Redaction is pattern-based and cannot promise to catch every secret. See [SECURITY.md](SECURITY.md).

## How it works

```text
cli.py ── collectors.py   journalctl / docker logs / kubectl logs / file  (read-only, no shell)
       ── parsing.py      plain text, JSON lines, logfmt, kubectl prefixes → events
       ── analyzer.py     patterns → findings, severity, golden signals, order of appearance
       ── redact.py       masks secrets before anything is written or sent
       ── ai.py           optional hypothesis from the redacted summary (stdlib HTTP, no SDK)
       ── reporter.py     report.md + report.json
       ── html.py         report.html: the viewer page with the report embedded
       ── patterns.py     built-in packs      settings.py   incopilot.toml
```

One runtime dependency (`rich`). Python 3.10 to 3.13.

## Development

```bash
pip install -e ".[dev]"
pytest --cov
ruff check .
bandit -q -r incopilot
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and pull requests are welcome.

## Website

`site/` holds the landing page and the report viewer as plain HTML with no build step.

- **GitHub Pages:** the `Website` workflow deploys `site/` on every push to `main`. Turn Pages on once under Settings, Pages, with GitHub Actions as the source.
- **Vercel or Netlify:** import the repo, set the root directory to `site`, and leave the build command empty.

`site/viewer.html` and `incopilot/viewer.html` are the same file; a test keeps them identical.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the phases and [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md) for the reasoning. Work is tracked in [issues](https://github.com/AutoShiftOps/incopilot/issues) by [milestone](https://github.com/AutoShiftOps/incopilot/milestones).

## Limits

- Detection is rule-based. It recognizes known failure signatures; it does not understand your application.
- Order of appearance is a lead, not proof of cause.
- It reads logs only. It does not look at metrics, traces or deploy history.

## License

MIT © 2026 [AutoShiftOps](https://github.com/AutoShiftOps)
