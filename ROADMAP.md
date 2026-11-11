# Roadmap

incopilot is an open-source, read-only incident triage CLI. This roadmap covers the CLI and the possible path to a team product. The reasoning behind it is in [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md).

Work is tracked in [GitHub issues](https://github.com/AutoShiftOps/incopilot/issues), grouped by [milestone](https://github.com/AutoShiftOps/incopilot/milestones). Priorities: **P0** must ship for the milestone, **P1** should ship, **P2** if time allows.

No dates are promised. Phases 4 and 5 only start if Phase 3 says go.

| Phase | Milestone | Goal | Status |
|---|---|---|---|
| 0 | v0.2 Stabilize and ship | Released, installable, verified against real systems | In progress |
| 1 | v0.3 Sharper triage | Better answers from the same logs | Planned |
| 2 | v0.4 Share and integrate | Fits into CI, chat and existing log stores | Planned |
| 3 | Validation gate | Evidence that teams want, and would pay for, more than a CLI | Planned |
| 4 | v0.5 Self-hosted service (alpha) | History and a team dashboard you run yourself | Conditional on Phase 3 |
| 5 | v1.0 Team portal | Alerts, trends, roles | Conditional on Phase 4 |

## Phase 0: v0.2 Stabilize and ship

Shipped: Kubernetes source, structured log parsing, severity and order of first appearance, redaction, optional AI hypothesis, pattern packs, `--fail-on`, the website, a richer terminal summary, and `--html` for a shareable dashboard report.

Remaining: publish to PyPI, tag the release, turn on GitHub Pages, and test the collectors against real journalctl, Docker and a Kubernetes cluster.

**Done when:** `pip install incopilot` works, CI exercises real collectors, and the site is live.

## Phase 1: v0.3 Sharper triage

- Group multi-line stack traces into one event
- Burst detection: when the error rate jumped, not only what appeared
- Per-source timelines in `bundle`, to show which component failed first
- `incopilot diff` to compare a run against a known-good baseline
- Kubernetes events and pod status as a source
- A regression corpus of real log samples to keep false positives down

**Done when:** on the sample corpus, the first-appearing finding matches the labeled root cause in most cases, with the result published.

## Phase 2: v0.4 Share and integrate

- GitHub Action for post-deploy checks, with the report in the job summary
- Opt-in webhook and Slack post of the redacted summary
- Read-only collectors for Loki and CloudWatch Logs
- Container image and one-line installs

**Done when:** a team can run incopilot in a pipeline and get the result in their channel without writing glue code.

## Phase 3: Validation gate

This phase is evidence, not code. It answers the two open questions in the product plan: do small teams want investigation tooling or only fewer alerts, and will they trust a tool with production logs.

- Interviews with engineers on 5 to 50 person teams
- Adoption signals from the open-source tool
- A paid pilot ask with a real price
- A written go or no-go decision

**Go if** the criteria in the product plan are met. **Otherwise** incopilot stays a maintained open-source CLI, which is a fine outcome.

## Phase 4: v0.5 Self-hosted service (alpha)

A small service that stores reports pushed from the CLI and shows history: what fired, when, on which service, and how it trended. Runs from Docker Compose or Helm. The CLI stays the only thing that touches logs.

## Phase 5: v1.0 Team portal

Alert rules and notifications, trends over time, teams and roles, an audit log, and retention controls. Whether to offer a hosted version is decided here, not before.

## Not planned

- Automatic remediation of any kind. incopilot explains; people act.
- Agents installed on hosts.
- Replacing a log store, a metrics system or an on-call scheduler.
