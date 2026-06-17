"""HVAC anomaly detection model (v1).

This is the production model currently running against Modules 1-4. The v2
model with confidence scoring and maintenance-window suppression is being
developed on the `feat/anomaly-v2` branch (see KAN-25).
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass
class ScoringResult:
    score: float          # raw anomaly score in [-1, 1] (sklearn convention)
    is_anomaly: bool      # thresholded
    threshold: float      # threshold used for this (module, loop)


class HvacAnomalyModel:
    """Wraps an IsolationForest with per-(module, loop) thresholds."""

    def __init__(self, contamination: float = 0.01, random_state: int = 42) -> None:
        self.pipeline: Pipeline = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "iforest",
                    IsolationForest(
                        n_estimators=200,
                        contamination=contamination,
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
        self.thresholds: dict[tuple[int, str], float] = {}

    # ------------------------------------------------------------------ train
    def fit(self, df: pd.DataFrame) -> "HvacAnomalyModel":
        X = df[FEATURE_COLS].to_numpy()
        self.pipeline.fit(X)
        # Default threshold per (module, loop) at the 99th percentile of
        # training scores. v2 (KAN-25) replaces this with a per-asset
        # calibration step.
        scores = self.pipeline.score_samples(X)
        df = df.assign(score=scores)
        for (mod, loop), group in df.groupby(["module", "loop"]):
            self.thresholds[(mod, loop)] = float(np.percentile(group["score"], 1.0))
        return self

    # ------------------------------------------------------------------ score
    def score_one(self, row: dict) -> ScoringResult:
        X = np.array([[row[c] for c in FEATURE_COLS]])
        score = float(self.pipeline.score_samples(X)[0])
        thr = self.thresholds.get((row["module"], row["loop"]), -0.1)
        return ScoringResult(score=score, is_anomaly=score < thr, threshold=thr)

    # ----------------------------------------------------------- persistence
    def save(self, path: str) -> None:
        joblib.dump({"pipeline": self.pipeline, "thresholds": self.thresholds}, path)

    @classmethod
    def load(cls, path: str) -> "HvacAnomalyModel":
        blob = joblib.load(path)
        m = cls()
        m.pipeline = blob["pipeline"]
        m.thresholds = blob["thresholds"]
        return m
