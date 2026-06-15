# Architecture — The Line Digital Twin

> Epic: [KAN-19](https://dib-test1.atlassian.net/browse/KAN-19) — *The Line —
> Vertical City Digital Twin Platform*.

## 1. Goals

1. **Live operational view** of every module of The Line — HVAC, vertical
   transit pods, life-safety systems — at a sub-second cadence.
2. **Anomaly detection** that catches deviations early enough for CityOps
   to dispatch maintenance before a failure becomes guest-visible.
3. **Safety-critical isolation** — fire/life-safety and lift overrides
   never share a failure domain with non-safety telemetry.
4. **Historical fidelity** — all telemetry is retained in a queryable
   long-term store (Iceberg on S3) for forensic analysis.

## 2. High-level data flow

```
+----------------------+    +---------------------+    +-------------------------+
| Per-module BMS / OPC |--->| Edge OPC-UA Gateway |--->| Kafka (multi-AZ)        |
| (HVAC, pods, safety) |    | (redundant per mod) |    |  - general              |
+----------------------+    +---------------------+    |  - safety_critical      |
                                                       +-----------+-------------+
                                                                   |
                                                                   v
                                                       +-----------------------+
                                                       | Flink stream jobs     |
                                                       |  - normalize          |
                                                       |  - feature windows    |
                                                       |  - asset-db enrich    |
                                                       +-----------+-----------+
                                                                   |
                            +-------------------+    +-------------v-----------+
   Operator console  <----- | GraphQL + WS      |<---| Anomaly scorer (sklearn)|
   (React + WebGL,          | (Apollo subgraph) |    | IsolationForest         |
    floor heatmap)          +-------------------+    +-------------------------+
                                                                   |
                                                                   v
                                                       +-----------------------+
                                                       | Firehose -> S3/Iceberg|
                                                       +-----------------------+
```

## 3. Components

### 3.1 Edge gateways

OPC-UA servers running on a redundant pair of edge appliances per module.
They expose the BMS namespace and a normalized pod namespace. The
`services/pod-adapter` and `services/ingestion/producer.py` clients connect
here.

### 3.2 Ingestion (Kafka + Flink)

- Two MSK clusters: `general` and `safety_critical` (see `infra/kafka.tf`).
- Flink jobs are deployed onto EMR-on-EKS, one job per pipeline.
- All topics are partitioned by `module:floor` so per-floor ordering is
  preserved.

### 3.3 Anomaly detection

A two-stage pipeline (`services/anomaly-detection`):

- **Stage 1 — statistical pre-filter:** rolling z-score over 15 min per
  (module, floor, loop). Cheap, inline.
- **Stage 2 — IsolationForest:** sklearn model, trained on the last 30
  days. v2 (KAN-25) adds confidence scoring and maintenance-window
  suppression to drive the false-positive rate down.

### 3.4 Operator console

React + WebGL SPA. The headline view is the floor-by-floor heatmap. Data
arrives via GraphQL subscriptions against the GraphQL gateway.

### 3.5 Long-term archive

Firehose lands all telemetry in S3 (Parquet, Iceberg-compatible). Queried
through Athena / Trino for training and forensic work.

## 4. Safety-critical isolation (KAN-28)

Fire/life-safety and lift-override topics:

- Live on **`safety_critical`** MSK cluster, not `general`.
- Use 5x replication, `min.insync.replicas=3`, unclean leader election
  disabled.
- Backed by dedicated subnets and a dedicated IAM trust boundary.
- Consumers must be explicitly whitelisted; cross-cluster mirroring is
  one-way (safety → archive only, never the reverse).

## 5. Failure modes & runbooks

- HVAC anomaly flood → see `docs/runbooks/anomaly-flood.md` (to be added)
- Pod adapter OPC-UA failover → `docs/runbooks/pod-failover.md` (to be added)
- Safety-critical stream interruption → `docs/runbooks/safety-critical-streams.md`
