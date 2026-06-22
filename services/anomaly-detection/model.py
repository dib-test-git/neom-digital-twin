"""HVAC anomaly detection model — v2.

Changes vs v1:

- Adds a *confidence* score in [0, 1] alongside the raw IsolationForest
  score, derived from how far the sample falls below the per-asset
  calibrated threshold.
- Threshold calibration is now per-(module, floor, loop) rather than
  per-(module, loop) — Modules 1-4 had enough heterogeneity between
  floors that the coarser-grained threshold was dominating the
  false-positive rate (KAN-25).
- New `suppress_during_maintenance` flag: alerts are downgraded to
  `is_anomaly=False` if the asset's maintenance calendar marks the
  window as planned service.
- `score_one` now returns a structured `ScoringResult` with both
  fields so the alert pipeline can route low-confidence anomalies to
  the "watchlist" topic instead of paging.

KAN-25.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLS: list[str] = [
    "value",
    "rolling_mean_15m",
    "rolling_std_15m",
    "rolling_z_15m",
    "delta_1m",
    "hour_of_day",
    "is_weekend",
]


# Type for the "is this asset currently under maintenance?" callback.
# In production this is backed by the CityOps maintenance calendar.
MaintenanceFn = Callable[[int, int, str, float], bool]


@dataclass
class ScoringResult:
    score: float          # raw IsolationForest score (lower = more anomalous)
    confidence: float     # 0..1, distance below threshold normalized
    is_anomaly: bool      # final decision (post-suppression)
    threshold: float
    suppressed: bool = False


@dataclass
class CalibrationStats:
    """Per-asset calibration captured at training time."""
    threshold: float
    score_p01: float
    score_p99: float
    n_samples: int


class HvacAnomalyModel:
    """IsolationForest with per-(module, floor, loop) calibration."""

    VERSION = "2.0.0"

    def __init__(self, contamination: float = 0.005, random_state: int = 42) -> None:
        self.pipeline: Pipeline = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "iforest",
                    IsolationForest(
                        n_estimators=300,
                        contamination=contamination,
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
        self.calibration: dict[tuple[int, int, str], CalibrationStats] = {}

    # ------------------------------------------------------------------ train
    def fit(self, df: pd.DataFrame) -> "HvacAnomalyModel":
        X = df[FEATURE_COLS].to_numpy()
        self.pipeline.fit(X)
        scores = self.pipeline.score_samples(X)
        df = df.assign(score=scores)
        for (mod, floor, loop), group in df.groupby(["module", "floor", "loop"]):
            self.calibration[(mod, floor, loop)] = CalibrationStats(
                threshold=float(np.percentile(group["score"], 0.5)),
                score_p01=float(np.percentile(group["score"], 1.0)),
                score_p99=float(np.percentile(group["score"], 99.0)),
                n_samples=int(len(group)),
            )
        return self

    # ------------------------------------------------------------------ score
    def score_one(
        self,
        row: dict,
        maintenance_fn: MaintenanceFn | None = None,
    ) -> ScoringResult:
        X = np.array([[row[c] for c in FEATURE_COLS]])
        score = float(self.pipeline.score_samples(X)[0])
        cal = self.calibration.get(
            (row["module"], row["floor"], row["loop"]),
            CalibrationStats(threshold=-0.1, score_p01=-0.3, score_p99=0.3, n_samples=0),
        )

        # Confidence: how far we are below the threshold, normalized by the
        # spread of the calibration window. Clamped to [0, 1].
        if score < cal.threshold:
            spread = max(cal.threshold - cal.score_p01, 1e-6)
            confidence = float(min(1.0, (cal.threshold - score) / spread))
            is_anomaly = True
        else:
            confidence = 0.0
            is_anomaly = False

        # Maintenance-window suppression (KAN-25 false-positive reduction).
        suppressed = False
        if is_anomaly and maintenance_fn is not None:
            if maintenance_fn(row["module"], row["floor"], row["loop"], row["ts_ms"]):
                is_anomaly = False
                suppressed = True

        return ScoringResult(
            score=score,
            confidence=confidence,
            is_anomaly=is_anomaly,
            threshold=cal.threshold,
            suppressed=suppressed,
        )

    # ----------------------------------------------------------- persistence
    def save(self, path: str) -> None:
        joblib.dump(
            {
                "version": self.VERSION,
                "pipeline": self.pipeline,
                "calibration": self.calibration,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "HvacAnomalyModel":
        blob = joblib.load(path)
        m = cls()
        m.pipeline = blob["pipeline"]
        m.calibration = blob.get("calibration") or blob.get("thresholds", {})
        return m
