# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CI runs the tests on macOS and Windows as well as Linux
- README: platform support table and Windows install tips; install command is now `pip install firstsignal`

## [0.2.0] - 2026-11-12

First release as **firstsignal** (formerly incopilot).

### Changed
- **Renamed to firstsignal** (was incopilot): package, command, config file (`firstsignal.toml`), environment variables (`FIRSTSIGNAL_*`), history folder (`~/.firstsignal`) and website (https://firstsignal.autoshiftops.com/). The old command, variables, config file and history keep working for one release; the old command prints a note on stderr
- New logo and banner in `docs/brand/`
- JSON report has a new shape with `schema_version: "2"`
- `bundle` accepts any mix of `--unit`, `--container`, `--pod` and `--path`
- Shared options such as `--out-dir` are now given after the subcommand
- Next-step commands are filled in with the targets that were analyzed

### Added
- Website at https://firstsignal.autoshiftops.com/: sticky header with the current section highlighted, new sections for incident memory and `watch`, favicon, social preview card, 404 page, sitemap and robots.txt
- Issue forms (bug report, feature request, new pattern or pack) and a pull request template
- `firstsignal watch <source>`: continuous local triage that prints only what changed, keeps one history record per session, and writes a final report when stopped
- Pattern packs for Redis, MySQL, HAProxy and Kafka (`--packs redis,mysql,haproxy,kafka`)
- Incident memory: each run is remembered as a fingerprint, similar past incidents are shown as "Seen before", and `firstsignal history list|note|forget` manages them. Stored locally with no log text
- `--html` writes a self-contained `report.html` dashboard
- Terminal output shows the golden-signals summary and an order-of-first-appearance table
- Example report on the website at `site/viewer.html`
- `ROADMAP.md` and `docs/PRODUCT_PLAN.md`
- Kubernetes source (`firstsignal k8s`) using `kubectl logs`, by pod, workload reference or label selector
- Structured log support: JSON lines, logfmt levels, and kubectl/docker prefixes and timestamps
- Severity for every finding and an overall severity for the run
- Order of first appearance, to separate likely causes from knock-on effects
- Secret redaction in all reports, on by default (`--no-redact`, `--redact-ips`)
- Optional AI hypothesis (`--ai`) with your own key: Anthropic, OpenAI-compatible endpoints, or local Ollama
- Pattern packs (`--packs`): core, nginx, postgres, node, kubernetes, jvm
- `firstsignal.toml` for custom patterns, noise filters and redaction rules
- `--fail-on` exit code for CI and scheduled runs, `--json` output, stdin and `.gz` input
- Dockerfile, CI on Python 3.10 to 3.13, and a project website

### Fixed
- Report viewer: the paste box was always open because a CSS rule overrode `hidden`; it now opens only from "Paste JSON". The header stays visible while scrolling and links to the website
- Website: the timeline's end label overlapped the first row
- `docker logs` output written to stderr was dropped
- `--max-bytes` truncated by characters and could cut a line in half
- `http_5xx` rarely matched real access logs and could match unrelated numbers
- The test suite imported a Click entry point that did not exist

### Removed
- `config.py` and `config_extended.py`, replaced by pattern packs and `firstsignal.toml`
- Sample reports committed under `out/`

## [0.1.0] - 2026-07-08

### Added
- Initial release of incopilot
- AI-powered incident triage CLI agent
- Three log sources: journalctl, Docker logs, plain files
- Four Golden Signals mapping
- Dual output: Markdown and JSON
- Bundle mode for analyzing multiple sources
- Pure Python implementation
