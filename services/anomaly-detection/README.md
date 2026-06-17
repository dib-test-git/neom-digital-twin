# services/anomaly-detection

HVAC anomaly detection pipeline. Consumes from
`the-line.bms.hvac.normalized` and emits scored anomalies to
`the-line.bms.hvac.alerts`.

Tracks [KAN-25](https://dib-test1.atlassian.net/browse/KAN-25) — *false
positive reduction*.

## Approach

A two-stage pipeline:

1. **Statistical pre-filter** — per-(module, floor, loop) rolling z-score on
   a 15-minute window. Cheap, runs inline in the consumer.
2. **Isolation Forest** — sklearn model trained on the last 30 days of
   normalized telemetry across all onboarded modules. Outputs an anomaly
   score in `[0, 1]`; threshold is per-module and tuned via the
   `--calibrate` flag.

False-positive reduction comes mainly from the v2 work in
[KAN-25](https://dib-test1.atlassian.net/browse/KAN-25): we now condition
the score on the rolling z-score *and* on the asset's maintenance window
(suppressing alerts during scheduled service).

## Files

| File | Role |
| --- | --- |
| `model.py` | Model definition (Isolation Forest wrapper) + scoring API |
| `train.py` | Offline trainer — pulls from Iceberg, writes model artifact to S3 |
| `serve.py` | Online scorer — consumes Kafka, writes to alerts topic |
| `features.py` | Feature engineering helpers (rolling stats, calendar joins) |

## Train a new model

```bash
python train.py \
  --since 2026-05-01 --until 2026-06-01 \
  --modules 1,2,3,4 \
  --out s3://neom-ml-models/hvac/v2/
```

## Score online

```bash
python serve.py --model s3://neom-ml-models/hvac/v2/model.joblib
```
