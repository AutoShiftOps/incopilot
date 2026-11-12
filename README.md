<p align="center">
  <a href="https://firstsignal.autoshiftops.com/"><img src="https://raw.githubusercontent.com/AutoShiftOps/firstsignal/main/docs/brand/firstsignal-banner.png" alt="firstsignal: the loudest error is rarely the first one" width="820"></a>
</p>

# firstsignal

> Formerly **incopilot**. The `incopilot` command, `INCOPILOT_*` variables, `incopilot.toml` and `~/.incopilot` history still work for one release.

Read-only incident triage for logs. One command collects logs from **systemd, Docker, Kubernetes or a file**, maps what it finds to the **Four Golden Signals**, and writes a report with the order things went wrong and safe checks to run next.

[![CI](https://github.com/AutoShiftOps/firstsignal/actions/workflows/ci.yml/badge.svg)](https://github.com/AutoShiftOps/firstsignal/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776AB)
![license](https://img.shields.io/badge/license-MIT-blue)

**Correlate and explain, never auto-act.** firstsignal never changes the systems it reads. It works offline with no account and no agent. An AI hypothesis is available if you bring your own key, and it is off by default.

Website: https://firstsignal.autoshiftops.com/

## Quick start

```bash
pip install firstsignal          # or: pipx install firstsignal

# try it on the bundled example incident
git clone https://github.com/AutoShiftOps/firstsignal && cd firstsignal
firstsignal file --path examples/checkout-incident.log --packs core,nginx
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

### Platforms

Pure Python with one dependency, so it installs on Linux, macOS and Windows (Python 3.10 to 3.13). CI runs the tests on all three. What differs is which log sources each system has:

| Source | Linux | macOS | Windows |
|---|---|---|---|
| `file`, stdin, `bundle --path` | yes | yes | yes |
| `docker` | yes | yes, with Docker Desktop | yes, with Docker Desktop |
| `k8s` | yes | yes, with `kubectl` configured | yes, with `kubectl` configured |
| `journal` (systemd) | yes | no systemd | no systemd |
| `watch`, `--html`, history, `--ai` | yes | yes | yes |

`docker` and `k8s` call the `docker` and `kubectl` commands, so they work from a laptop pointed at a remote host or cluster. On Windows the history file is not restricted to your account, because Windows does not apply POSIX file modes; it holds pattern names, counts, targets and your notes, never log text.

**Windows install tips.** If `pip install` fails with `Failed to write executable` or `WinError 2`, Python is installed system-wide and pip cannot write to its `Scripts` folder. Use one of:

```powershell
pipx install firstsignal                      # recommended: isolated, on PATH
pip install --user firstsignal                # per-user install
py -m venv .venv; .venv\Scripts\activate; pip install firstsignal
```

`py -m firstsignal ...` runs it even when the `Scripts` folder is not on PATH.

## See it as a dashboard

```bash
firstsignal file --path examples/checkout-incident.log --html
# open out/report.html in a browser
```

`--html` writes a self-contained `report.html`: overall severity, the Four Golden Signals, a timeline of when each problem first appeared, findings, and the checks to run next. Nothing is loaded from a server and the report data stays in the file.

The terminal output already shows severity, golden signals, findings and the order of first appearance. Use `--html` when you need to share the result with people who were not at the terminal, for example in an incident channel or a postmortem.

A [live example](https://firstsignal.autoshiftops.com/viewer.html) is on the website.

## It remembers

Every run with findings is remembered as a fingerprint: which patterns fired, in what order, on which target. The next time something similar happens, firstsignal tells you, along with what fixed it last time.

```text
Seen before
  3f9a1c2e  12 days ago on prod/deploy/api  (100% similar, critical)
      Fix noted: raised DB pool size from 10 to 30, added index on orders.customer_id

Remembered as 8b21d0aa. When it is fixed: firstsignal history note 8b21d0aa "what fixed it"
```

```bash
firstsignal history list                         # what is remembered
firstsignal history note 8b21d0aa "what fixed it"
firstsignal history forget 8b21d0aa
```

- **Local and private.** History is one file, `~/.firstsignal/history.jsonl`, readable only by you. Set `FIRSTSIGNAL_HISTORY` or `--history FILE` to move it, for example into a repo your team shares.
- **No log text is stored.** Only pattern names, counts, the target, the time and your note.
- **Matching is deterministic.** The same two incidents always get the same score. No model is involved.
- Re-running during the same incident updates one record instead of creating many. `--no-history` turns it off.

## Sources

```bash
# systemd journal
firstsignal journal --unit nginx --since "30 min ago"

# Docker container (stdout and stderr)
firstsignal docker --container my-api --since 1h

# Kubernetes: a pod, a workload, or a label selector
firstsignal k8s --pod deploy/api -n prod --since 30m
firstsignal k8s -l app=api -n prod --previous        # the container that just crashed

# a file, a .gz file, or stdin
firstsignal file --path /var/log/app.log
kubectl logs deploy/api | firstsignal file --path -

# several sources as one timeline
firstsignal bundle --unit nginx --container my-api --pod deploy/api -n prod
```

## Watch it live

```bash
firstsignal watch k8s --pod deploy/api -n prod
firstsignal watch docker --container my-api --window 10
firstsignal watch file --path /var/log/app.log
```

```text
Watching prod/deploy/api: last 5 min of logs, checked every 15s. Ctrl+C to stop.
09:41:12  NEW          high     Connection limit reached (saturation) x2
09:41:12  SEVERITY     none -> high
09:41:31  NEW          critical Out of memory (saturation) x1
09:41:31  SEVERITY     high -> critical
09:41:31  SEEN BEFORE  3f9a1c2e, 12 days ago on prod/deploy/api (80% similar). Fix noted: raised DB pool size
09:52:40  CLEARED               Connection limit reached
```

`watch` re-analyzes a sliding window and prints only what changed: a new finding, a severity change, a finding that cleared, or a match with a past incident. When you stop it, it writes the usual reports for the worst moment it saw and keeps one history record for the whole session.

| Option | Purpose |
|---|---|
| `--window MINUTES` | How much recent log to analyze each time. Default 5 |
| `--interval SECONDS` | How often to check. Default 15 |
| `--duration SECONDS` | Stop after this long. Default: until Ctrl+C |
| `--json` | One JSON event per line, for piping into other tools |
| `--from-start` | For files: include what is already there. Default: only new lines |

Everything stays on your machine. To run it unattended, use it as a systemd service or a Kubernetes sidecar with `--duration` unset.

## What you get

`out/report.md` for people and `out/report.json` for pipelines (plus `out/report.html` with `--html`), containing:

- **Overall severity** (none, low, medium, high, critical) and a severity per finding
- **Four Golden Signals**: which of latency, traffic, errors and saturation are affected
- **Order of first appearance**: which pattern showed up first
- **Read-only checks to run next**, filled in with your unit, container or pod
- **Seen before**: similar past incidents from your history, with the fix you noted
- **Top repeating lines**, with timestamps, IDs and IPs normalized so repeats group together
- **Redacted examples** for every finding

Plain text, JSON lines, logfmt and `kubectl --prefix --timestamps` output are all understood. Health-check lines are filtered unless they report an error.

## Options

Options go after the source, for example `firstsignal file --path app.log --json`.

| Option | Purpose |
|---|---|
| `--packs core,nginx` | Pattern packs: `core`, `nginx`, `postgres`, `node`, `kubernetes`, `jvm`, `redis`, `mysql`, `haproxy`, `kafka`, `all`. Default `core` |
| `--config FILE` | Settings file. `./firstsignal.toml` is loaded automatically if present |
| `--out-dir DIR` | Where reports are written. Default `out` |
| `--html` | Also write `report.html`, a self-contained dashboard |
| `--json` | Print the JSON report to stdout and nothing else |
| `--no-write`, `-q` | Skip report files; no console output |
| `--fail-on LEVEL` | Exit `3` when overall severity is at or above `low`, `medium`, `high` or `critical` |
| `--max-bytes N` | Analyze only the last N bytes. Default 5,000,000 |
| `--timeout N` | Seconds to wait for `journalctl`, `docker` or `kubectl`. Default 60 |
| `--no-history`, `--history FILE` | Skip incident memory; use a different history file |
| `--no-redact`, `--redact-ips` | Turn secret masking off; also mask IPv4 addresses |
| `--ai`, `--ai-provider`, `--ai-model` | Optional AI hypothesis, see below |

Exit codes: `0` success, `1` could not collect or write, `2` usage error, `3` `--fail-on` threshold met.

## Use it in CI or on a timer

```bash
# fail a post-deploy check if the new pods log anything high or critical
firstsignal k8s -l app=api -n prod --since 10m --fail-on high --quiet
```

`systemd/` has an example service and timer for scheduled runs. A `Dockerfile` is included for piping logs through a container:

```bash
docker build -t firstsignal .
kubectl logs deploy/api | docker run --rm -i firstsignal file --path - --json --no-write
```

## Your own patterns

Copy `examples/firstsignal.toml` to `./firstsignal.toml`:

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
firstsignal k8s --pod deploy/api -n prod --ai

# any OpenAI-compatible endpoint, or a local model with no key at all
firstsignal file --path app.log --ai --ai-provider ollama --ai-model llama3.1
```

- **Off by default.** Without `--ai`, nothing leaves your machine.
- **Only the redacted summary is sent**: counts, order of appearance, up to two redacted example lines per finding, and the top repeating lines. Never the raw log, and never anything with `--no-redact`.
- **The answer is text for you to read.** It is labeled unverified in the report and nothing in it is executed.
- **Log content is treated as untrusted** in the prompt, so text inside a log line cannot give the model instructions.
- If the call fails, the rest of the report is still produced.

Environment: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `FIRSTSIGNAL_AI_KEY`; `FIRSTSIGNAL_AI_PROVIDER`, `FIRSTSIGNAL_AI_MODEL`, `FIRSTSIGNAL_AI_BASE_URL`.

Redaction is pattern-based and cannot promise to catch every secret. See [SECURITY.md](SECURITY.md).

## How it works

```text
cli.py ── collectors.py   journalctl / docker logs / kubectl logs / file  (read-only, no shell)
       ── parsing.py      plain text, JSON lines, logfmt, kubectl prefixes → events
       ── analyzer.py     patterns → findings, severity, golden signals, order of appearance
       ── redact.py       masks secrets before anything is written or sent
       ── ai.py           optional hypothesis from the redacted summary (stdlib HTTP, no SDK)
       ── watch.py        follow a source, re-analyze a sliding window, report changes
       ── memory.py       incident fingerprints, local history, "seen before" matching
       ── reporter.py     report.md + report.json
       ── html.py         report.html: the viewer page with the report embedded
       ── patterns.py     built-in packs      settings.py   firstsignal.toml
```

One runtime dependency (`rich`). Python 3.10 to 3.13 on Linux, macOS and Windows.

## Development

```bash
pip install -e ".[dev]"
pytest --cov
ruff check .
bandit -q -r firstsignal
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and pull requests are welcome.

## Website

Live at https://firstsignal.autoshiftops.com/. `site/` holds the landing page, the report viewer and a 404 page as plain HTML with no build step.

- **GitHub Pages:** the `Website` workflow deploys `site/` on every push to `main` that touches `site/`. Under Settings, Pages, the source must be **GitHub Actions**; "Deploy from a branch" publishes the README instead. The custom domain is set on the same page.
- **Social preview:** `site/og.png` (1280×640, a copy of `docs/brand/firstsignal-banner.png`) is the card shown when the link is shared. Upload the same image under the repository's Settings, Social preview.
- **Brand:** `docs/brand/` holds the mark (`firstsignal-mark.svg`, and `firstsignal-mark-16.svg` drawn for 16px), light and dark lockups, and the banner. The mark is a small first signal that pings, followed by louder ones.
- **Vercel or Netlify:** import the repo, set the root directory to `site`, and leave the build command empty.

`site/viewer.html` and `firstsignal/viewer.html` are the same file; a test keeps them identical.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the phases and [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md) for the reasoning. Work is tracked in [issues](https://github.com/AutoShiftOps/firstsignal/issues) by [milestone](https://github.com/AutoShiftOps/firstsignal/milestones).

## Limits

- Detection is rule-based. It recognizes known failure signatures; it does not understand your application.
- Order of appearance is a lead, not proof of cause.
- It reads logs only. It does not look at metrics, traces or deploy history.

## License

MIT © 2026 [AutoShiftOps](https://github.com/AutoShiftOps)
