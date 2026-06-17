"""Offline trainer for the HVAC anomaly model.

Pulls normalized HVAC readings from the Iceberg `the_line.hvac_normalized`
table, builds rolling features, fits the model, and uploads the artifact to
S3 alongside a JSON manifest.

KAN-25.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from datetime import datetime

import boto3
import pandas as pd

from features import build_features
from model import HvacAnomalyModel

log = logging.getLogger("the-line.anomaly.train")


def _load_window(since: str, until: str, modules: list[int]) -> pd.DataFrame:
    """Stub loader. In production this is an Iceberg/Trino read.

    For the offline replay tests it falls back to a Parquet on disk.
    """
    src = os.getenv("HVAC_PARQUET", "replay-data/hvac-normalized.parquet")
    log.info("loading %s [%s..%s] modules=%s", src, since, until, modules)
    df = pd.read_parquet(src)
    df = df[(df.ts >= since) & (df.ts < until) & (df.module.isin(modules))]
    return df


def _upload(local_path: str, s3_uri: str) -> None:
    assert s3_uri.startswith("s3://"), s3_uri
    bucket, _, key = s3_uri[5:].partition("/")
    boto3.client("s3").upload_file(local_path, bucket, key)
    log.info("uploaded %s -> %s", local_path, s3_uri)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--modules", required=True, help="comma-separated module ids")
    ap.add_argument("--out", required=True, help="s3://.../  prefix")
    ap.add_argument("--contamination", type=float, default=0.01)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)
    modules = [int(m) for m in args.modules.split(",")]

    raw = _load_window(args.since, args.until, modules)
    feats = build_features(raw)
    log.info("training on %d rows / %d cols", len(feats), feats.shape[1])

    model = HvacAnomalyModel(contamination=args.contamination).fit(feats)

    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, "model.joblib")
        model.save(local)
        manifest = {
            "trained_at": datetime.utcnow().isoformat() + "Z",
            "rows": int(len(feats)),
            "modules": modules,
            "since": args.since,
            "until": args.until,
            "contamination": args.contamination,
            "feature_cols": list(feats.columns),
        }
        manifest_local = os.path.join(tmp, "manifest.json")
        with open(manifest_local, "w") as f:
            json.dump(manifest, f, indent=2)
        _upload(local, args.out.rstrip("/") + "/model.joblib")
        _upload(manifest_local, args.out.rstrip("/") + "/manifest.json")


if __name__ == "__main__":
    main()
