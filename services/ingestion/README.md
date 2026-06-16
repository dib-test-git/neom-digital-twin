# services/ingestion

Stream-ingestion layer for The Line BMS / IoT telemetry.

Tracks [KAN-24](https://dib-test1.atlassian.net/browse/KAN-24) — *Ingest BMS
telemetry from Modules 1-4 HVAC loops*.

## Components

| File | Role |
| --- | --- |
| `producer.py` | Pulls from per-module OPC-UA gateway, publishes to Kafka |
| `flink_hvac_job.py` | PyFlink streaming job: normalize + window + sink |
| `schemas/hvac.avsc` | Avro schema registered with Confluent Schema Registry |
| `config/topics.yaml` | Topic + partitioning + retention config (per env) |

## Topics

| Topic | Partitions | Retention | Notes |
| --- | --- | --- | --- |
| `the-line.bms.hvac.raw` | 64 | 7d | Per-module HVAC tags (OPC-UA values) |
| `the-line.bms.hvac.normalized` | 64 | 30d | Common schema, unit-normalized |
| `the-line.bms.hvac.alerts` | 12 | 30d | Anomaly detector output |
| `the-line.safety.fire-life` | 24 | 90d | **Safety-critical** — see [KAN-28](https://dib-test1.atlassian.net/browse/KAN-28) |

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# stand up local Kafka + schema-registry (uses repo-root docker-compose)
make -C ../.. dev-up

# replay a recorded trace
python producer.py --module 03 --replay ../../replay-data/module-03.parquet
```

## Production deploy

Submitted to the shared Flink cluster via `infra/flink/submit.sh`. Multi-AZ
isolation for safety-critical topics is tracked under
[KAN-28](https://dib-test1.atlassian.net/browse/KAN-28).
