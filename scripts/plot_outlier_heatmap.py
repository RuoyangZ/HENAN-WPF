from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "HENAN-WPF_public_release"
RAW_POWER_PATH = DATA_ROOT / "raw_wind_power" / "wind_power_raw_15min_public.csv"
META_PATH = DATA_ROOT / "metadata" / "public_station_index.csv"
OUTPUT_DIR = ROOT / "outputs" / "quality_validation"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    power_df = pd.read_csv(RAW_POWER_PATH)
    power_df["datetime"] = pd.to_datetime(power_df["datetime"], errors="coerce")
    meta_df = pd.read_csv(META_PATH)
    return power_df, meta_df


def build_anomaly_table(power_df: pd.DataFrame, meta_df: pd.DataFrame) -> pd.DataFrame:
    meta_idx = meta_df.set_index("Public station label")
    rows = []

    for station in [c for c in power_df.columns if c != "datetime"]:
        s = pd.to_numeric(power_df[station], errors="coerce")
        cap = meta_idx.at[station, "Installed capacity (MW)"] if station in meta_idx.index else np.nan

        negative = int((s < 0).sum())
        over_capacity = int((s > cap).sum()) if pd.notna(cap) else 0

        median = s.median()
        mad = (s - median).abs().median()
        if pd.isna(mad) or mad == 0:
            robust_outlier = 0
        else:
            robust_z = 0.6745 * (s - median) / mad
            robust_outlier = int(robust_z.abs().gt(5).sum())

        diffs = s.diff()
        ramp_std = diffs.std()
        if pd.isna(ramp_std) or ramp_std == 0:
            ramp_outlier = 0
        else:
            ramp_outlier = int((diffs.abs() > 5 * ramp_std).sum())

        rows.append(
            {
                "Station": station,
                "negative": negative,
                "over_capacity": over_capacity,
                "robust_outlier": robust_outlier,
                "ramp_outlier": ramp_outlier,
            }
        )

    return pd.DataFrame(rows).set_index("Station")


def plot_heatmap(heat_df: pd.DataFrame) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "Times New Roman"

    plot_df = np.log1p(heat_df)
    plt.figure(figsize=(8.5, max(8, len(plot_df) * 0.22)))
    sns.heatmap(plot_df, cmap="YlOrRd", linewidths=0.2, cbar_kws={"label": "log(1 + count)"})
    plt.title("Wind anomaly count heatmap by station and anomaly type")
    plt.xlabel("Anomaly type")
    plt.ylabel("Station")
    plt.tight_layout()

    out_path = OUTPUT_DIR / "wind_anomaly_heatmap_public.png"
    plt.savefig(out_path, dpi=450, bbox_inches="tight")
    plt.close()
    return out_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    power_df, meta_df = load_inputs()
    heat_df = build_anomaly_table(power_df, meta_df)
    csv_path = OUTPUT_DIR / "wind_anomaly_counts_public.csv"
    try:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            heat_df.to_csv(f)
    except PermissionError:
        print(f"Warning: could not write summary CSV to {csv_path}, continuing with figure export.")
    out_path = plot_heatmap(heat_df)
    print(f"Saved outlier heatmap to: {out_path}")


if __name__ == "__main__":
    main()
