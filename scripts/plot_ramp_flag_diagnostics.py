"""Audit the temporal structure of the original five-sigma power-change flags.

This analysis groups screening flags; it does not identify validated physical
ramp events or remove, clip, smooth, or interpolate power observations.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import platform
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
import PIL

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "HENAN-WPF_public_release"
DEFAULT_OUTPUT = ROOT / "outputs" / "ramp_flag_diagnostics"
STEP_MINUTES = 15
SIGMA_MULTIPLIER = 5.0
CONTEXT_STEPS = 8  # Two hours on each side of the complete segment.
CATEGORIES = ["single_step", "two_step_reversal", "same_direction", "longer_mixed"]
LABELS = {
    "single_step": "Single-step change",
    "two_step_reversal": "Two-step reversal",
    "same_direction": "Same-direction sequence",
    "longer_mixed": "Longer mixed sequence",
}
COLORS = {
    "single_step": "#9CA3AF",
    "two_step_reversal": "#D69A55",
    "same_direction": "#4E79A7",
    "longer_mixed": "#8D7E9C",
}
DURATION_BINS = ["15", "30", "45", "60", ">60"]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(values: np.ndarray) -> str:
    if len(values) == 1:
        return "single_step"
    signs = np.sign(values)
    if len(values) == 2 and signs[0] != signs[1]:
        return "two_step_reversal"
    if np.all(signs == signs[0]):
        return "same_direction"
    return "longer_mixed"


def load_data(data_root: Path):
    power_path = data_root / "raw_wind_power" / "wind_power_raw_15min_public.csv"
    meta_path = data_root / "metadata" / "public_station_index.csv"
    power = pd.read_csv(power_path)
    power["datetime"] = pd.to_datetime(power["datetime"], errors="raise")
    times = power["datetime"]
    if times.isna().any() or times.duplicated().any() or not times.is_monotonic_increasing:
        raise ValueError("Power timestamps must be valid, unique, and increasing.")
    if not times.diff().dropna().eq(pd.Timedelta(minutes=STEP_MINUTES)).all():
        raise ValueError("Expected a complete 15-min time grid; no gaps are bridged.")
    metadata = pd.read_csv(meta_path)
    if metadata["Public station label"].duplicated().any():
        raise ValueError("Duplicate public station labels in metadata.")
    meta = metadata.set_index("Public station label")
    for station in power.columns.drop("datetime"):
        power[station] = pd.to_numeric(power[station], errors="raise")
        capacity = float(meta.at[station, "Installed capacity (MW)"])
        if not np.isfinite(capacity) or capacity <= 0:
            raise ValueError(f"Invalid installed capacity for {station}")
        if np.isinf(power[station].to_numpy()).any():
            raise ValueError(f"Infinite power value for {station}")
    return power, metadata, power_path, meta_path


def analyze(power: pd.DataFrame, metadata: pd.DataFrame):
    meta = metadata.set_index("Public station label")
    times = power["datetime"].to_numpy()
    segment_rows, flag_rows, site_rows = [], [], []
    masks = {}
    for station_index, station in enumerate(power.columns.drop("datetime"), start=1):
        s = power[station]
        raw = s.to_numpy(dtype=float)
        diff_series = s.diff()
        differences = diff_series.to_numpy(dtype=float)
        sigma = float(diff_series.std(ddof=1))
        threshold = SIGMA_MULTIPLIER * sigma
        flag = (np.abs(differences) > threshold) if np.isfinite(sigma) and sigma > 0 else np.zeros(len(s), bool)
        masks[station] = flag
        capacity = float(meta.at[station, "Installed capacity (MW)"])
        outside = (raw < 0) | (raw > capacity)
        touches_outside = outside | np.r_[False, outside[:-1]]
        starts = np.flatnonzero(flag & ~np.r_[False, flag[:-1]])
        ends = np.flatnonzero(flag & ~np.r_[flag[1:], False])
        for number, (first, last) in enumerate(zip(starts, ends), start=1):
            values = differences[first:last + 1]
            support = raw[first - 1:last + 1]
            category = classify(values)
            segment_id = f"S{station_index:02d}-{number:05d}"
            duration = (pd.Timestamp(times[last]) - pd.Timestamp(times[first - 1])).total_seconds() / 60
            assert duration == len(values) * STEP_MINUTES
            net = float(support[-1] - support[0])
            direction = "up" if np.all(values > 0) else "down" if np.all(values < 0) else "mixed"
            segment_rows.append({
                "segment_id": segment_id, "station": station, "category": category,
                "direction": direction, "start_time": times[first - 1], "end_time": times[last],
                "first_diff_index": int(first), "last_diff_index": int(last),
                "flag_count": len(values), "duration_min": int(duration),
                "capacity_mw": capacity, "threshold_mw": threshold,
                "start_power_mw": float(support[0]), "end_power_mw": float(support[-1]),
                "net_change_mw": net, "net_change_pct_capacity": net / capacity * 100,
                "power_range_mw": float(np.ptp(support)),
                "power_range_pct_capacity": float(np.ptp(support) / capacity * 100),
                "total_absolute_change_mw": float(np.abs(values).sum()),
                "mean_signed_rate_mw_per_min": net / duration,
                "sign_sequence": "".join("+" if value > 0 else "-" for value in values),
                "flags_touching_out_of_range_power": int(touches_outside[first:last + 1].sum()),
            })
            for position in range(first, last + 1):
                flag_rows.append({
                    "segment_id": segment_id, "station": station, "category": category,
                    "interval_start": times[position - 1], "interval_end": times[position],
                    "power_before_mw": float(raw[position - 1]), "power_after_mw": float(raw[position]),
                    "delta_power_mw": float(differences[position]), "threshold_mw": threshold,
                    "direction": "up" if differences[position] > 0 else "down",
                    "touches_out_of_range_power": bool(touches_outside[position]),
                })
        site_rows.append({
            "station": station, "capacity_mw": capacity,
            "nonmissing_adjacent_differences": int(diff_series.notna().sum()),
            "difference_std_mw": sigma, "threshold_mw": threshold,
            "threshold_pct_capacity": threshold / capacity * 100,
            "flag_count": int(flag.sum()),
            "flag_rate_pct": float(flag.sum() / diff_series.notna().sum() * 100),
            "upward_flags": int((flag & (differences > 0)).sum()),
            "downward_flags": int((flag & (differences < 0)).sum()),
            "segment_count": len(starts),
            "flags_touching_out_of_range_power": int((flag & touches_outside).sum()),
        })
    segments = pd.DataFrame(segment_rows)
    flags = pd.DataFrame(flag_rows)
    sites = pd.DataFrame(site_rows)
    if segments.empty:
        raise ValueError("No flags were detected; the diagnostic figure requires flagged segments.")
    segments["duration_bin_min"] = segments["duration_min"].map(lambda n: str(n) if n <= 60 else ">60")
    summary = segments.groupby("category").agg(segment_count=("segment_id", "size"), flag_count=("flag_count", "sum")).reindex(CATEGORIES, fill_value=0)
    summary["segment_share_pct"] = summary["segment_count"] / len(segments) * 100
    summary["flag_share_pct"] = summary["flag_count"] / len(flags) * 100
    duration = pd.crosstab(segments["duration_bin_min"], segments["category"]).reindex(index=DURATION_BINS, columns=CATEGORIES, fill_value=0)
    duration["total_segments"] = duration.sum(axis=1)
    for category in CATEGORIES:
        per_site = segments.loc[segments.category == category].groupby("station").agg(segment_count=("segment_id", "size"), flag_count=("flag_count", "sum"))
        sites[f"{category}_segments"] = sites.station.map(per_site.segment_count).fillna(0).astype(int)
        sites[f"{category}_flags"] = sites.station.map(per_site.flag_count).fillna(0).astype(int)
    return segments, flags, sites, summary, duration, masks


def validate_legacy(power, metadata, flags, segments, sites, summary, duration):
    """Compare every site with the original public heatmap's actual function."""
    legacy_script = ROOT / "scripts" / "plot_outlier_heatmap.py"
    tree = ast.parse(legacy_script.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build_anomaly_table")
    namespace = {"np": np, "pd": pd}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(legacy_script), "exec"), namespace)
    legacy = namespace["build_anomaly_table"](power, metadata)
    observed = sites.set_index("station")["flag_count"]
    assert np.array_equal(legacy.loc[observed.index, "ramp_outlier"].to_numpy(), observed.to_numpy())
    assert not flags.duplicated(["station", "interval_end"]).any()
    assert not segments.segment_id.duplicated().any()
    assert flags.delta_power_mw.abs().gt(flags.threshold_mw).all()
    assert flags.groupby("segment_id").size().sort_index().equals(segments.set_index("segment_id").flag_count.sort_index())
    assert len(flags) == int(sites.flag_count.sum()) == int(segments.flag_count.sum()) == int(summary.flag_count.sum())
    assert len(segments) == int(sites.segment_count.sum()) == int(duration.total_segments.sum())
    assert np.array_equal(segments.duration_min.to_numpy(), segments.flag_count.to_numpy() * STEP_MINUTES)
    assert summary.loc["two_step_reversal", "flag_count"] == 2 * summary.loc["two_step_reversal", "segment_count"]
    return {"legacy_per_site_counts_identical": True, "each_flag_assigned_once": True,
            "count_reconciliation_passed": True, "duration_support_verified": True,
            "all_flags_strictly_exceed_original_threshold": True}


def choose_examples(power, segments, masks):
    """Choose median-range examples from explicitly defined eligible pools."""
    selected = []
    for kind in ["up", "down", "reversal"]:
        candidates = segments.loc[segments.category == "two_step_reversal"] if kind == "reversal" else segments.loc[(segments.category == "same_direction") & (segments.direction == kind)]
        eligible = []
        for row in candidates.itertuples():
            lo = row.first_diff_index - 1 - CONTEXT_STEPS
            hi = row.last_diff_index + CONTEXT_STEPS
            if lo < 0 or hi >= len(power):
                continue
            values = power[row.station].iloc[lo:hi + 1].to_numpy()
            if not np.isfinite(values).all() or np.any(values < 0) or np.any(values > row.capacity_mw):
                continue
            if masks[row.station][lo + 1:hi + 1].sum() != row.flag_count:
                continue
            eligible.append(row.Index)
        pool = segments.loc[eligible].copy()
        if pool.empty:
            raise ValueError(f"No eligible example for {kind}; revise and document the selection rule.")
        median = float(pool.power_range_pct_capacity.median())
        pool["selection_distance"] = (pool.power_range_pct_capacity - median).abs().round(10)
        chosen = pool.sort_values(["selection_distance", "station", "start_time", "segment_id"], kind="stable").iloc[0].to_dict()
        chosen.update(example_kind=kind, eligible_pool_size=len(pool), eligible_median_range_pct=median)
        selected.append(chosen)
    examples = pd.DataFrame(selected)
    sources = []
    for row in examples.itertuples():
        lo = row.first_diff_index - 1 - CONTEXT_STEPS
        hi = row.last_diff_index + CONTEXT_STEPS
        positions = np.arange(lo, hi + 1)
        sources.append(pd.DataFrame({
            "example_kind": row.example_kind, "station": row.station, "segment_id": row.segment_id,
            "datetime": power.datetime.iloc[lo:hi + 1].to_numpy(),
            "power_mw": power[row.station].iloc[lo:hi + 1].to_numpy(),
            "power_pct_capacity": power[row.station].iloc[lo:hi + 1].to_numpy() / row.capacity_mw * 100,
            "hours_from_segment_start": (positions - (row.first_diff_index - 1)) * STEP_MINUTES / 60,
            "in_segment_support": (positions >= row.first_diff_index - 1) & (positions <= row.last_diff_index),
            "is_flag_interval_end": masks[row.station][lo:hi + 1],
        }))
    return examples, pd.concat(sources, ignore_index=True)


def make_figure(summary, duration, examples, example_data, totals, output):
    plt.rcParams.update({"font.size": 7, "axes.labelsize": 7, "axes.titlesize": 7,
        "xtick.labelsize": 6, "ytick.labelsize": 6.5, "axes.spines.top": False,
        "axes.spines.right": False, "axes.linewidth": 0.6, "xtick.major.width": 0.6,
        "ytick.major.width": 0.6, "legend.frameon": False, "savefig.facecolor": "white"})
    fig = plt.figure(figsize=(183 / 25.4, 155 / 25.4), facecolor="white")
    fig.text(0.035, 0.968, "Temporal structure of large 15-min power-change flags", fontsize=7, fontweight="bold")
    fig.text(0.035, 0.941, f"{totals['station_count']} wind farms  |  {totals['flag_count']:,} flags ({totals['flag_rate_pct']:.2f}% of adjacent differences)  |  {totals['segment_count']:,} segments", fontsize=6.8)

    ax = fig.add_axes([0.235, 0.63, 0.325, 0.25])
    vals = summary.flag_share_pct.to_numpy()
    ax.barh(np.arange(4), vals, color=[COLORS[c] for c in CATEGORIES], height=0.57)
    ax.set_yticks(np.arange(4), ["Single-step\nchange", "Two-step\nreversal", "Same-direction\nsequence", "Longer mixed\nsequence"])
    ax.invert_yaxis()
    ax.set_xlim(0, 85)
    ax.set_xticks([0, 20, 40, 60, 80])
    ax.set_xlabel("Share of all flags (%)")
    ax.tick_params(axis="y", length=0, pad=5)
    for i, (_, row) in enumerate(summary.iterrows()):
        ax.text(row.flag_share_pct + 1.2, i, f"{int(row.flag_count):,} ({row.flag_share_pct:.2f}%)", va="center", fontsize=6)
    fig.text(0.035, 0.903, "a", fontsize=8, fontweight="bold")
    fig.text(0.061, 0.903, "Contribution by segment type", fontsize=7)

    ax = fig.add_axes([0.685, 0.63, 0.28, 0.25])
    base = np.zeros(len(DURATION_BINS))
    for cat in CATEGORIES:
        values = duration[cat].to_numpy()
        ax.bar(np.arange(5), values, bottom=base, color=COLORS[cat], width=0.65)
        base += values
    ax.set_xticks(np.arange(5), DURATION_BINS)
    ax.set_xlabel("Segment duration (min)")
    ax.set_ylabel("Number of segments", labelpad=4)
    ax.set_ylim(0, 13000)
    ax.set_yticks([0, 4000, 8000, 12000])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    for i, total in enumerate(base):
        ax.text(i, total + 250, f"{int(total):,}", ha="center", fontsize=5.9)
    fig.text(0.615, 0.903, "b", fontsize=8, fontweight="bold")
    fig.text(0.641, 0.903, "Duration of flagged segments", fontsize=7)
    short_labels = ["Single-step", "Two-step reversal", "Same-direction", "Longer mixed"]
    fig.legend([Patch(facecolor=COLORS[c]) for c in CATEGORIES], short_labels,
               loc="center", bbox_to_anchor=(0.52, 0.545), ncol=4, fontsize=6.5,
               handlelength=1.2, columnspacing=1.5)

    fig.text(0.035, 0.494, "c", fontsize=8, fontweight="bold")
    fig.text(0.061, 0.494, "Raw-data examples with the flagged segment highlighted", fontsize=7)
    names = {"up": "Upward sequence", "down": "Downward sequence", "reversal": "Two-step reversal"}
    for i, row in enumerate(examples.itertuples()):
        ax = fig.add_axes([0.095 + 0.31 * i, 0.165, 0.25, 0.25])
        values = example_data.loc[example_data.example_kind == row.example_kind]
        highlighted = values.loc[values.in_segment_support]
        col = COLORS[row.category]
        ax.plot(values.hours_from_segment_start, values.power_pct_capacity, "o-", color="#8B9096", linewidth=0.85, markersize=2.2)
        ax.axvspan(0, row.duration_min / 60, color=col, alpha=0.12, linewidth=0)
        ax.axvline(0, color="#717780", linewidth=0.55, linestyle=(0, (3, 3)))
        ax.axvline(row.duration_min / 60, color="#717780", linewidth=0.55, linestyle=(0, (3, 3)))
        ax.plot(highlighted.hours_from_segment_start, highlighted.power_pct_capacity, "o-", color=col, linewidth=1.6, markersize=3.3)
        ax.set_ylim(-3, 112)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_xlim(-2, row.duration_min / 60 + 2)
        ax.set_xticks([-2, -1, 0, 1, 2])
        ax.set_xlabel("Hours from segment start", labelpad=4)
        if i == 0:
            ax.set_ylabel("Power (% of installed capacity)", labelpad=4)
        else:
            ax.tick_params(labelleft=False)
        ax.set_title(f"{names[row.example_kind]}\n{row.station}", pad=10, linespacing=1.5)
        ax.text(0.5, 0.97, f"Range {row.power_range_pct_capacity:.1f}% C; {row.duration_min} min", transform=ax.transAxes, ha="center", va="top", fontsize=5.8)
        start = pd.Timestamp(row.start_time).strftime("%Y-%m-%d %H:%M")
        ax.text(0.5, -0.37, f"Start: {start}", transform=ax.transAxes, ha="center", fontsize=5.8)
    fig.text(0.035, 0.032, "Segment classes describe screening flags; they do not establish data errors or physical causes.", fontsize=6.2)
    stem = output / "ramp_flag_diagnostics"
    fig.savefig(stem.with_suffix(".png"), format="png", dpi=300)
    plt.close(fig)


def write_report(output, totals, summary, duration, examples, checks):
    nf, ns, nd = totals["flag_count"], totals["segment_count"], totals["nonmissing_adjacent_differences"]
    reverse = summary.loc["two_step_reversal"]
    methods = (
        "For each wind farm, signed differences were calculated between adjacent 15-min power observations. "
        "Differences were flagged when their absolute magnitude exceeded five times the site-specific sample standard deviation of all non-missing signed differences (ddof = 1). "
        "Consecutive flagged differences were grouped into maximal contiguous segments within each farm, without bridging an unflagged or missing difference. "
        "The start of each segment was the observation preceding its first flagged difference; its end was the observation completing its last flagged difference. "
        "A segment containing m flagged differences therefore spanned m + 1 observations and lasted 15m minutes. "
        "Segments were classified as single-step changes, two-step reversals, same-direction sequences, or longer mixed sequences. "
        "Two-step reversals contained exactly two differences of opposite sign. "
        "Same-direction sequences contained at least two differences with identical signs. "
        "Longer mixed sequences contained at least three differences and a change of sign. "
        "All durations were retained, with no additional amplitude or minimum-duration filter. "
        "Original power values were retained without clipping, smoothing, deletion, or interpolation. "
        "Flags involving negative or above-capacity endpoints were retained and separately identified in the source tables."
    )
    caption = (
        f"Temporal structure of large 15-min power-change flags across {totals['station_count']} wind farms. "
        f"The original five-sigma screening rule flagged {nf:,} of {nd:,} non-missing adjacent differences ({totals['flag_rate_pct']:.2f}%). "
        f"Grouping consecutive flags within farms yielded {ns:,} segments. "
        "(a) Number and percentage of flagged differences contributed by each segment class. "
        "(b) Segment counts by duration, stacked by the same classes; duration includes the observation preceding the first flagged difference. "
        "(c) Illustrative upward, downward, and two-step reversal segments from the raw power series. "
        "Power is expressed as a percentage of the public installed capacity. "
        "Grey lines show two hours of context on either side; coloured lines and shading identify the selected segment. "
        "Eligible examples had complete, physically bounded context and no additional flagged differences within that context. "
        "Each example was selected nearest to the median capacity-normalized power range in its eligible class, with ties resolved by station label and start time. "
        "The examples illustrate temporal shapes and are not representative estimates of their physical causes. "
        "Bars are complete counts for the released dataset; no inferential tests or error bars are applied. "
        "Segment labels do not establish measurement errors, operational causes, or independently validated ramp events."
    )
    response = (
        "Thank you for highlighting the need to examine and categorize the large-ramp flags more carefully. "
        "The original heatmap counts threshold-exceeding adjacent power differences, rather than independently identified ramp events. "
        f"Across 36 wind farms, {nf:,} of {nd:,} non-missing adjacent differences were flagged, corresponding to {totals['flag_rate_pct']:.2f}%.\n\n"
        "We examined their temporal structure by grouping consecutive flagged differences within each farm, without separating them by direction beforehand. "
        f"This yielded {ns:,} segments, categorized into single-step changes, two-step reversals, same-direction sequences, and longer mixed sequences. "
        f"The {int(reverse.segment_count):,} two-step reversal segments contributed {int(reverse.flag_count):,} flags, representing {reverse.flag_share_pct:.1f}% of all flagged differences. "
        "Thus, short reversal patterns account for a substantial proportion of the original flag count.\n\n"
        "An additional diagnostic figure presents the class contributions, segment-duration distribution, and illustrative upward, downward, and reversal cases. "
        "All segment durations were retained, including changes spanning a single 15-min interval. "
        "This analysis characterizes screening flags and does not establish their physical causes or confirm measurement errors. "
        "These flags indicate observations requiring further inspection, rather than observations that should automatically be removed."
    )
    (output / "figure_caption.txt").write_text(caption + "\n", encoding="utf-8")
    (output / "methods_and_reviewer_response.txt").write_text("Methods\n\n" + methods + "\n\nReviewer response draft\n\n" + response + "\n\nInsert the final figure number and manuscript locations after the revision is incorporated.\n", encoding="utf-8")
    display = summary.reset_index().copy()
    display["category"] = display.category.map({"single_step": "单步大幅变化", "two_step_reversal": "两步反向变化", "same_direction": "连续同向变化", "longer_mixed": "较长混合方向变化"})
    display.columns = ["类别", "片段数", "标记次数", "片段占比 (%)", "标记占比 (%)"]
    table = display.to_html(index=False, float_format=lambda x: f"{x:.2f}", border=0)
    example_table = examples[["example_kind", "station", "start_time", "duration_min", "power_range_pct_capacity", "eligible_pool_size"]].to_html(index=False, float_format=lambda x: f"{x:.2f}", border=0)
    paragraph = lambda text: "".join("<p>" + html.escape(p) + "</p>" for p in text.split("\n\n"))
    content = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>大幅功率变化标记的时间结构检查</title>
<style>body{{font:16px/1.7 Arial,"Microsoft YaHei",sans-serif;color:#24303a;max-width:1120px;margin:38px auto;padding:0 28px}}h1{{font-size:26px}}h2{{font-size:21px;margin-top:34px}}.lead{{background:#f3f6f8;padding:18px 22px;border-left:4px solid #4e79a7}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border-bottom:1px solid #dce2e7;padding:9px;text-align:left}}th{{background:#f3f6f8}}.note{{color:#58636d}}a{{color:#315f89}}.english{{font-size:15px}}code{{background:#f0f3f6;padding:2px 5px}}</style>
<h1>大幅功率变化标记的时间结构检查</h1>
<p class="lead">原始 5σ 判据识别出 <b>{nf:,}</b> 次大幅功率变化，占 <b>{nd:,}</b> 个非缺失相邻差分的 <b>{totals['flag_rate_pct']:.4f}%</b>。连续标记组成 <b>{ns:,}</b> 个片段；其中两步反向片段贡献 <b>{reverse.flag_share_pct:.2f}%</b> 的全部标记。</p>
<p>本分析解释原筛查标记的时间结构。片段不是已经验证的独立物理爬坡事件；分类不能确定记录真伪或变化成因。所有原始数值和 15 分钟片段均予以保留。</p>
<p><a href="ramp_flag_diagnostics.png">PNG</a></p>
<img src="ramp_flag_diagnostics.png" alt="真实数据生成的标记分类、持续时间及案例三联图">
<h2>分类结果</h2>{table}
<p class="note">(a) 的分母为标记次数；(b) 的分母为片段数量。两步反向片段贡献两次标记，覆盖三个功率观测点，持续 30 分钟。</p>
<h2>持续时间与检查边界</h2>
{duration.to_html(border=0)}
<p>其中 {totals['flags_touching_out_of_range_power']} 次标记涉及负值或超容量的相邻功率端点；这些标记已在结果表中单独标注，未从统计中移除。{int(summary.loc['same_direction','segment_count'])} 个连续同向片段仅代表每一步均超过阈值的连续片段，并非完整数据中所有持续爬坡的数量。</p>
<h2>真实案例与选择规则</h2>{example_table}
<p>分别从连续上升、连续下降和两步反向三类候选片段中选择案例。候选片段须具有前后各两小时完整数据，背景窗口内没有额外标记，且背景功率均在 0 至公开装机容量之间。在各自合格候选集内，选取功率极差（除以装机容量）最接近中位数的片段；并列时按公开场站标签、起始时间排序。此筛选仅用于图中案例，整体统计未应用这些筛选条件。案例属于形态说明，不承担成因验证。</p>
<h2>方法与图注（英文草稿）</h2><div class="english">{paragraph(methods)}{paragraph(caption)}</div>
<h2>审稿回复（英文草稿）</h2><div class="english">{paragraph(response)}</div>
<p class="note">新增分析及图件已生成；将其插入论文后，再补充图号与修改位置。原 Figure 4 未被本脚本覆盖。</p>
<h2>复核与下载</h2><p>已逐场站比对原热图脚本：标记数量完全一致。每次标记仅分配到一个片段，各表合计一致，持续时间按实际时间戳核验。原始输入文件 SHA-256 保持不变。</p>
<p><a href="ramp_flag_records.csv">逐次标记</a> · <a href="ramp_flag_segments.csv">逐片段明细</a> · <a href="site_summary.csv">逐场站统计与阈值</a> · <a href="category_summary.csv">分类统计</a> · <a href="duration_by_category.csv">持续时间统计</a> · <a href="example_timeseries.csv">案例原始数据</a> · <a href="examples.csv">案例选择记录</a> · <a href="analysis_summary.json">参数、版本与校验记录</a></p>
</html>'''
    (output / "report.html").write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    power, metadata, power_path, meta_path = load_data(args.data_root)
    input_hashes = {"raw_power_sha256": digest(power_path), "metadata_sha256": digest(meta_path)}
    segments, flags, sites, summary, duration, masks = analyze(power, metadata)
    checks = validate_legacy(power, metadata, flags, segments, sites, summary, duration)
    examples, example_data = choose_examples(power, segments, masks)
    totals = {"station_count": len(sites), "observations_per_station": len(power),
        "nonmissing_adjacent_differences": int(sites.nonmissing_adjacent_differences.sum()),
        "flag_count": len(flags), "segment_count": len(segments),
        "flag_rate_pct": len(flags) / int(sites.nonmissing_adjacent_differences.sum()) * 100,
        "flags_touching_out_of_range_power": int(sites.flags_touching_out_of_range_power.sum()),
        "upward_flags": int(sites.upward_flags.sum()), "downward_flags": int(sites.downward_flags.sum()),
        "station_flag_rate_pct_min": float(sites.flag_rate_pct.min()),
        "station_flag_rate_pct_max": float(sites.flag_rate_pct.max())}
    for name, frame, index in [
        ("ramp_flag_records", flags, False), ("ramp_flag_segments", segments, False),
        ("site_summary", sites, False), ("category_summary", summary, True),
        ("duration_by_category", duration, True), ("examples", examples, False),
        ("example_timeseries", example_data, False),
    ]:
        frame.to_csv(output / f"{name}.csv", index=index, encoding="utf-8-sig", float_format="%.10g", date_format="%Y-%m-%d %H:%M:%S")
    make_figure(summary, duration, examples, example_data, totals, output)
    assert digest(power_path) == input_hashes["raw_power_sha256"]
    assert digest(meta_path) == input_hashes["metadata_sha256"]
    checks["input_files_unchanged"] = True
    provenance = {"totals": totals, "validation": checks, "inputs": input_hashes,
        "parameters": {"step_minutes": STEP_MINUTES, "sigma_multiplier": SIGMA_MULTIPLIER,
            "std_ddof": 1, "comparison": "abs(signed_difference) > 5 * sample_std(signed_differences)",
            "additional_minimum_duration_filter": None, "additional_amplitude_filter": None,
            "context_hours_each_side": 2},
        "software": {"python": platform.python_version(), "numpy": np.__version__,
            "pandas": pd.__version__, "matplotlib": matplotlib.__version__, "Pillow": PIL.__version__},
        "figure_contract": {"claim": "Two-step reversals contribute more than half of the original large-change flags.",
            "backend": "Python/matplotlib", "size_mm": [183, 155],
            "panels": {"a": "Flag contributions by temporal shape", "b": "Unfiltered segment durations", "c": "Traceable raw examples"},
            "limits": "Morphology is not evidence of physical cause, measurement error, or an independent ramp event."}}
    (output / "analysis_summary.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(output, totals, summary, duration, examples, checks)
    print(json.dumps(totals, indent=2))
    print("All per-site legacy-count and data-integrity checks passed.")
    print(f"Saved diagnostic figure, source tables, and report to: {output}")


if __name__ == "__main__":
    main()
