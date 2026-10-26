from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "HENAN-WPF_public_release"
POWER_15MIN_PATH = DATA_ROOT / "processed_wind_power" / "wind_power_processed_15min_public.csv"
OUTPUT_DIR = ROOT / "outputs" / "representative_power_timeseries"
FIG_DPI = 450

REPRESENTATIVE_SITES = {
    "plain": ["Neihuang County", "Linying County_1", "Yucheng County"],
    "mountain": ["Lushi County", "Jiyuan City_1", "Xin County"],
}

COLORS = {
    "plain": "#0b3c6f",
    "mountain": "#f07f24",
}

WINDOWS = [
    ("3d", pd.Timestamp("2025-03-01 07:15:00"), pd.Timestamp("2025-03-04 07:15:00")),
    ("7d", pd.Timestamp("2025-03-26 08:30:00"), pd.Timestamp("2025-04-02 08:30:00")),
]


def load_power() -> pd.DataFrame:
    df = pd.read_csv(POWER_15MIN_PATH)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    return df.sort_values("datetime").reset_index(drop=True)


def set_style() -> None:
    plt.rcParams["font.family"] = "Times New Roman"
    plt.rcParams["figure.dpi"] = FIG_DPI
    plt.rcParams["savefig.dpi"] = FIG_DPI


def plot_short_window(df: pd.DataFrame, suffix: str, start: pd.Timestamp, end: pd.Timestamp) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    window_df = df[(df["datetime"] >= start) & (df["datetime"] <= end)].copy()
    ordered_sites = REPRESENTATIVE_SITES["plain"] + REPRESENTATIVE_SITES["mountain"]
    terrain_lookup = {s: "plain" for s in REPRESENTATIVE_SITES["plain"]}
    terrain_lookup.update({s: "mountain" for s in REPRESENTATIVE_SITES["mountain"]})

    fig, axes = plt.subplots(3, 2, figsize=(18, 13), sharex=True)
    axes = axes.ravel()

    for ax, site in zip(axes, ordered_sites):
        terrain = terrain_lookup[site]
        ax.plot(
            window_df["datetime"],
            window_df[site],
            color=COLORS[terrain],
            linewidth=1.2,
            alpha=0.95,
        )
        ax.set_title(f"{site} ({terrain.title()})", fontsize=15, pad=10)
        ax.set_ylabel("Power (MW)", fontsize=11)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.tick_params(axis="both", labelsize=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))

    for ax in axes[-2:]:
        ax.set_xlabel("Date", fontsize=11)

    fig.suptitle(
        f"Representative Wind Power Time Series (15 min, {start:%Y-%m-%d} to {end:%Y-%m-%d})",
        fontsize=19,
        y=0.98,
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))

    out_path = OUTPUT_DIR / f"representative_wind_power_timeseries_{suffix}_15min.png"
    fig.savefig(out_path, dpi=FIG_DPI, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    return out_path


def main() -> None:
    set_style()
    power_df = load_power()
    for suffix, start, end in WINDOWS:
        out_path = plot_short_window(power_df, suffix=suffix, start=start, end=end)
        print(f"Saved figure to: {out_path}")


if __name__ == "__main__":
    main()
