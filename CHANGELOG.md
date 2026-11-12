# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Issue forms (bug report, feature request, new pattern or pack) and a pull request template
- `incopilot watch <source>`: continuous local triage that prints only what changed, keeps one history record per session, and writes a final report when stopped
- Pattern packs for Redis, MySQL, HAProxy and Kafka (`--packs redis,mysql,haproxy,kafka`)
- Incident memory: each run is remembered as a fingerprint, similar past incidents are shown as "Seen before", and `incopilot history list|note|forget` manages them. Stored locally with no log text
- `--html` writes a self-contained `report.html` dashboard
- Terminal output shows the golden-signals summary and an order-of-first-appearance table
- Example report on the website at `site/viewer.html`
- `ROADMAP.md` and `docs/PRODUCT_PLAN.md`

## [0.2.0] - 2026-11-10

### Added
- Kubernetes source (`incopilot k8s`) using `kubectl logs`, by pod, workload reference or label selector
- Structured log support: JSON lines, logfmt levels, and kubectl/docker prefixes and timestamps
- Severity for every finding and an overall severity for the run
- Order of first appearance, to separate likely causes from knock-on effects
- Secret redaction in all reports, on by default (`--no-redact`, `--redact-ips`)
- Optional AI hypothesis (`--ai`) with your own key: Anthropic, OpenAI-compatible endpoints, or local Ollama
- Pattern packs (`--packs`): core, nginx, postgres, node, kubernetes, jvm
- `incopilot.toml` for custom patterns, noise filters and redaction rules
- `--fail-on` exit code for CI and scheduled runs, `--json` output, stdin and `.gz` input
- Dockerfile, CI on Python 3.10 to 3.13, and a project website

### Changed
- JSON report has a new shape with `schema_version: "2"`
- `bundle` accepts any mix of `--unit`, `--container`, `--pod` and `--path`
- Shared options such as `--out-dir` are now given after the subcommand
- Next-step commands are filled in with the targets that were analyzed

### Fixed
- `docker logs` output written to stderr was dropped
- `--max-bytes` truncated by characters and could cut a line in half
- `http_5xx` rarely matched real access logs and could match unrelated numbers
- The test suite imported a Click entry point that did not exist

### Removed
- `config.py` and `config_extended.py`, replaced by pattern packs and `incopilot.toml`
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
