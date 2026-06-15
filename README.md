# NEOM Digital Twin — The Line

> **The Line — Vertical City Digital Twin Platform**
> Real-time BMS/IoT telemetry ingestion, anomaly detection, and operator
> tooling for The Line's vertical city. Owned by NEOM CityOps + Platform Data.

[![CI](https://github.com/dib-test-git/neom-digital-twin/actions/workflows/ci.yml/badge.svg)](https://github.com/dib-test-git/neom-digital-twin/actions/workflows/ci.yml)

---

## Overview

The Line is a 170 km linear city. Each ~800 m **Module** is effectively a
vertical district with its own HVAC plant rooms, vertical-transit pods,
life-safety systems, and BMS gateways. This repo is the digital-twin
backbone that ingests, processes, and surfaces that telemetry to operators
in real time.

Tracked under Jira Epic [KAN-19](https://dib-test1.atlassian.net/browse/KAN-19).

## Architecture

```
                       +-------------------------+
   Modules 1..N        |   Edge OPC-UA Gateways  |
  (HVAC, Pods,    ===> |  (per-module, redundant)| ===> Kafka (multi-AZ)
   Life-safety)        +-------------------------+              |
                                                                v
                                                    +-----------------------+
                                                    |  Flink stream jobs    |
                                                    |  - normalize          |
                                                    |  - enrich w/ asset DB |
                                                    |  - windowed features  |
                                                    +-----------+-----------+
                                                                |
                       +----------------+      +----------------v---------------+
   Operator console <--+  GraphQL API  +<-----+  Anomaly detection (scikit)    |
   (React + WebGL,     |  + WebSocket   |      |  Isolation Forest + rules     |
    floor heatmap)     +----------------+      +--------------------------------+
                                                                |
                                                                v
                                                       Long-term store (S3 + Iceberg)
```

See [docs/architecture.md](docs/architecture.md) for the full write-up.

## Repo layout

```
services/
  ingestion/           Flink (PyFlink) jobs — Kafka producer + stream jobs
  anomaly-detection/   scikit-learn pipeline, training, scoring service
  pod-adapter/         OPC-UA adapter for high-speed vertical-transit pods
web/
  operator-console/    React + WebGL operator UI (live floor heatmap)
infra/                 Terraform — Kafka (MSK), Kinesis, IAM, multi-AZ wiring
docs/                  Architecture, runbooks, on-call
.github/               CODEOWNERS, workflows, issue/PR templates
```

## Active work

| Jira | Status | What |
| --- | --- | --- |
| [KAN-24](https://dib-test1.atlassian.net/browse/KAN-24) | In Progress | Ingest BMS telemetry from Modules 1–4 HVAC loops |
| [KAN-25](https://dib-test1.atlassian.net/browse/KAN-25) | In Review | HVAC anomaly detection — false-positive reduction |
| [KAN-26](https://dib-test1.atlassian.net/browse/KAN-26) | In Progress | Operator console: live floor-by-floor heatmap |
| [KAN-27](https://dib-test1.atlassian.net/browse/KAN-27) | In Progress | Vertical-transit pod telemetry adapter |
| [KAN-28](https://dib-test1.atlassian.net/browse/KAN-28) | To Do | Safety-critical stream isolation (multi-AZ) |
| [KAN-49](https://dib-test1.atlassian.net/browse/KAN-49) | In Progress | **P1 Bug** — Heatmap freezes on Modules 12–14 |
| [KAN-50](https://dib-test1.atlassian.net/browse/KAN-50) | In Progress | **P2 Bug** — Pod adapter drops messages after failover |

## Getting started

Requires Python 3.11+, Node 20+, Terraform 1.7+, Docker.

```bash
# bootstrap dev deps
make bootstrap

# spin up local Kafka + schema-registry + Flink in docker-compose
make dev-up

# run anomaly detector against a recorded module trace
make replay MODULE=03

# launch the operator console in dev mode
cd web/operator-console && npm install && npm run dev
```

For deeper environment setup (cloud credentials, VPN to NEOM Edge, OPC-UA
client certs), see `docs/runbooks/`.

## On-call

- Primary: **@neom-cityops-leads**
- Platform data: **@neom-platform-data**
- Safety-critical paging policy: [docs/runbooks/safety-critical-streams.md](docs/runbooks/safety-critical-streams.md)

## License

Internal — NEOM. Not for external distribution.
