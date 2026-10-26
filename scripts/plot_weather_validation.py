from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "HENAN-WPF_public_release"
POWER_DATA_PATH = DATA_ROOT / "processed_wind_power" / "wind_power_processed_15min_public.csv"
WEATHER_DIR = DATA_ROOT / "era5_data" / "representative_sites"
OUTPUT_DIR = ROOT / "outputs" / "weather_validation"
FIG_DPI = 450

REPRESENTATIVE_SITES = [
    "Neihuang County",
    "Linying County_1",
    "Yucheng County",
    "Lushi County",
    "Jiyuan City_1",
    "Xin County",
]

HEATMAP_VARS = [
    "wind_speed_10m",
    "wind_direction_100m",
    "wind_speed_100m",
    "wind_gusts_10m",
    "temperature_2m",
    "surface_pressure",
    "precipitation",
    "power",
]

DISPLAY_NAMES = {
    "wind_speed_10m": "WS_10",
    "wind_direction_100m": "WD_100",
    "wind_speed_100m": "WS_100",
    "wind_gusts_10m": "Gust_10",
    "temperature_2m": "Temp_2m",
    "surface_pressure": "Pressure",
    "precipitation": "Precip",
    "power": "Power",
}


def weather_filename(station_label: str) -> str:
    return f"{station_label.replace(' ', '_')}.csv"


def load_power() -> pd.DataFrame:
    power_df = pd.read_csv(POWER_DATA_PATH)
    power_df["datetime"] = pd.to_datetime(power_df["datetime"], errors="coerce")
    power_df = power_df[power_df["datetime"].dt.minute == 0].copy()
    return power_df.sort_values("datetime").reset_index(drop=True)


def load_station_weather(station_label: str) -> pd.DataFrame:
    path = WEATHER_DIR / weather_filename(station_label)
    df = pd.read_csv(path)
    df["datetime_local"] = pd.to_datetime(df["datetime_local"], errors="coerce")
    # The public CSVs retain Open-Meteo's default km/h wind units.
    # Convert a loaded copy to m/s for wind-speed bins and figure labels.
    for column in ("wind_speed_10m", "wind_speed_100m", "wind_gusts_10m"):
        df[column] = pd.to_numeric(df[column], errors="raise") / 3.6
    return df


def merge_weather_power(station_label: str, power_df: pd.DataFrame) -> pd.DataFrame:
    weather_df = load_station_weather(station_label)
    return power_df[["datetime", station_label]].rename(columns={station_label: "power"}).merge(
        weather_df,
        left_on="datetime",
        right_on="datetime_local",
        how="inner",
    )


def plot_correlation_heatmaps(power_df: pd.DataFrame) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="white", font_scale=1.0)
    plt.rcParams["font.family"] = "Times New Roman"
    plt.rcParams["figure.dpi"] = FIG_DPI
    plt.rcParams["savefig.dpi"] = FIG_DPI

    fig, axes = plt.subplots(3, 2, figsize=(16, 19), dpi=FIG_DPI)
    axes = axes.flatten()

    for ax, station_label in zip(axes, REPRESENTATIVE_SITES):
        merged = merge_weather_power(station_label, power_df)
        corr = merged[HEATMAP_VARS].corr(method="pearson")
        corr.index = [DISPLAY_NAMES[col] for col in corr.index]
        corr.columns = [DISPLAY_NAMES[col] for col in corr.columns]

        sns.heatmap(
            corr,
            ax=ax,
            cmap="rocket",
            vmin=-0.4,
            vmax=1.0,
            annot=True,
            fmt=".2f",
            square=True,
            linewidths=0.4,
            cbar=ax is axes[1] or ax is axes[3] or ax is axes[5],
            cbar_kws={"shrink": 0.75},
            annot_kws={"fontsize": 9},
        )
        ax.set_title(station_label, fontsize=14, pad=8)
        ax.tick_params(axis="x", rotation=45, labelsize=10)
        ax.tick_params(axis="y", rotation=0, labelsize=10)

    fig.suptitle("Correlation heatmaps for representative wind farm sites", fontsize=20, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.985))

    out_path = OUTPUT_DIR / "representative_correlation_heatmaps_public.png"
    fig.savefig(out_path, dpi=FIG_DPI, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return out_path


def plot_single_wind_rose(ax, direction: np.ndarray, speed: np.ndarray, title: str) -> None:
    direction = np.asarray(direction) % 360
    speed = np.asarray(speed)

    dir_edges = np.arange(0, 361, 22.5)
    speed_bins = np.array([0, 2, 4, 6, 8, 10, 12, 30])
    colors = ["#0b3c6f", "#2c7fb8", "#6aaed6", "#9ecae1", "#6baed6", "#f4a582", "#f46d43"]

    width = np.deg2rad(np.diff(dir_edges))
    theta = np.deg2rad(dir_edges[:-1])
    base = np.zeros(len(theta))
    total_count = max(len(direction), 1)

    for i in range(len(speed_bins) - 1):
        mask = (speed >= speed_bins[i]) & (speed < speed_bins[i + 1])
        counts, _ = np.histogram(direction[mask], bins=dir_edges)
        freq = counts / total_count * 100
        ax.bar(
            theta,
            freq,
            width=width * 0.88,
            bottom=base,
            align="edge",
            color=colors[i],
            edgecolor="#f8f8f8",
            linewidth=0.7,
            label=f"{speed_bins[i]}-{speed_bins[i + 1]}",
        )
        base += freq

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_thetagrids(
        np.arange(0, 360, 22.5),
        labels=["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"],
        fontsize=10,
    )
    ax.set_rlabel_position(225)
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(color="#bdbdbd", linestyle=(0, (3, 3)), linewidth=0.6, alpha=0.9)
    ax.spines["polar"].set_color("#777777")
    ax.spines["polar"].set_linewidth(0.8)
    ax.set_title(title, fontsize=13.5, pad=24)


def plot_wind_roses() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "Times New Roman"
    plt.rcParams["figure.dpi"] = FIG_DPI
    plt.rcParams["savefig.dpi"] = FIG_DPI

    fig, axes = plt.subplots(3, 2, figsize=(16.5, 18), dpi=FIG_DPI, subplot_kw={"projection": "polar"})
    axes = axes.flatten()

    for ax, station_label in zip(axes, REPRESENTATIVE_SITES):
        weather_df = load_station_weather(station_label)
        plot_single_wind_rose(
            ax=ax,
            direction=weather_df["wind_direction_100m"],
            speed=weather_df["wind_speed_100m"],
            title=station_label,
        )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        title="Wind speed (m/s)",
        loc="center right",
        ncol=1,
        frameon=True,
        fontsize=11,
        title_fontsize=12,
        bbox_to_anchor=(0.935, 0.5),
        borderpad=0.8,
        labelspacing=0.5,
        handlelength=1.6,
        handletextpad=0.6,
    )
    fig.suptitle("Wind rose diagrams for representative wind farm sites", fontsize=20, y=0.99)
    fig.tight_layout(rect=(0, 0.02, 0.94, 0.975))

    out_path = OUTPUT_DIR / "representative_wind_roses_public.png"
    fig.savefig(out_path, dpi=FIG_DPI, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return out_path


def main() -> None:
    power_df = load_power()
    heatmap_out = plot_correlation_heatmaps(power_df)
    rose_out = plot_wind_roses()
    print(f"Saved heatmaps to: {heatmap_out}")
    print(f"Saved wind roses to: {rose_out}")


if __name__ == "__main__":
    main()
