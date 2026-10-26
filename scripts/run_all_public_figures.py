from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    ROOT / "scripts" / "plot_outlier_heatmap.py",
    ROOT / "scripts" / "plot_ramp_flag_diagnostics.py",
    ROOT / "scripts" / "plot_representative_power_timeseries.py",
    ROOT / "scripts" / "plot_weather_validation.py",
]


def main() -> None:
    for script in SCRIPTS:
        print(f"Running: {script.name}")
        runpy.run_path(str(script), run_name="__main__")
    print("Finished generating all public figure outputs.")


if __name__ == "__main__":
    main()
