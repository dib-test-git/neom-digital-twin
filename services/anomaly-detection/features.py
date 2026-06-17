"""Feature engineering for HVAC anomaly detection."""

from __future__ import annotations

import pandas as pd


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Given normalized HVAC readings, return the feature frame.

    Expected input columns: module, floor, loop, value, ts.
    """
    df = df.sort_values(["module", "floor", "loop", "ts"]).copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True)

    grp = df.groupby(["module", "floor", "loop"], group_keys=False)
    rolling = grp["value"].rolling("15min", on=df["ts"])

    df["rolling_mean_15m"] = rolling.mean().reset_index(level=[0, 1, 2], drop=True)
    df["rolling_std_15m"] = rolling.std().reset_index(level=[0, 1, 2], drop=True).fillna(0.0)
    df["rolling_z_15m"] = (
        (df["value"] - df["rolling_mean_15m"]) / df["rolling_std_15m"].replace(0.0, 1.0)
    )
    df["delta_1m"] = grp["value"].diff().fillna(0.0)
    df["hour_of_day"] = df["ts"].dt.hour
    df["is_weekend"] = (df["ts"].dt.weekday >= 5).astype(int)

    return df.dropna(subset=["value"])
