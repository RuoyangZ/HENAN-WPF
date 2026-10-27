# HENAN-WPF GitHub Code Release

This repository provides the public figure-reproduction scripts for the HENAN-WPF dataset, together with the public data, metadata, and selected figure assets required for reproducibility.

The repository includes:

- figure-reproduction scripts
- public raw and processed power data and site-matched ERA5 data
- minimal public metadata
- selected released figures
- pinned Python dependencies

## Repository structure

- `scripts/plot_outlier_heatmap.py`
  - Reproduces the anomaly-count heatmap using public station labels and the public raw wind power table.
- `scripts/plot_ramp_flag_diagnostics.py`
  - Audits the temporal structure of the original five-sigma power-change flags, with segment classifications, duration counts, and traceable raw-data examples.
- `scripts/plot_representative_power_timeseries.py`
  - Reproduces short-window 15 min power time-series figures for representative sites.
- `scripts/plot_weather_validation.py`
  - Reproduces the representative-site correlation heatmaps and wind rose diagrams using public ERA5 files and public station labels.
- `scripts/run_all_public_figures.py`
  - Runs all public figure-generation scripts in sequence.
- `metadata/`
  - Public station index used consistently in filenames, table entries, and figure labels.
- `figures/`
  - Selected manuscript figures generated from the project workflow.
- `requirements.txt`
  - Pinned Python dependencies used to generate the public figures.

## Data layout

The public HENAN-WPF CSV data are included under:

`data/HENAN-WPF_public_release/`

The scripts expect at least the following files and folders:

- `data/HENAN-WPF_public_release/raw_wind_power/wind_power_raw_15min_public.csv`
- `data/HENAN-WPF_public_release/processed_wind_power/wind_power_processed_15min_public.csv`
- `data/HENAN-WPF_public_release/metadata/public_station_index.csv`
- `data/HENAN-WPF_public_release/era5_data/representative_sites/`

## Reproducing figures

1. Install dependencies:

`pip install -r requirements.txt`

2. Clone or download the repository, including the `data/` folder described above.

3. Run all figure scripts:

`python scripts/run_all_public_figures.py`

Generated figures are written to the `outputs/` folder.

### ERA5 wind units

The public ERA5 CSV files retain wind speeds and gusts in km/h, the default
unit of the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api).
The original download requests selected the ERA5 model without overriding
`wind_speed_unit`. `plot_weather_validation.py` divides `wind_speed_10m`,
`wind_speed_100m`, and `wind_gusts_10m` by 3.6 after loading, so the wind-rose
bins and labels use m/s. Direction remains in degrees, temperature in degrees
Celsius, surface pressure in hPa, and precipitation in mm. The source CSVs
are not modified. The wind-rose PNG included in this repository reflects
this conversion. Positive unit scaling does not change Pearson correlations.

Run the segmentation and unit-conversion checks with:

`python -m unittest discover -s tests -p "test_*.py"`

### Temporal diagnostics of large power-change flags

Run only the supplementary quality-check analysis with:

`python scripts/plot_ramp_flag_diagnostics.py`

The analysis retains the original site-specific criterion, `abs(P.diff()) > 5 * P.diff().std(ddof=1)`. It groups consecutive flagged differences within each site, including opposite directions in the same segment. A segment containing `m` flagged differences spans `m + 1` observations and lasts `15 * m` minutes. The four mutually exclusive classes are single-step changes, two-step reversals, same-direction sequences, and longer mixed sequences. No minimum-duration filter or additional amplitude threshold is applied. Original power values remain unchanged.

Outputs in `outputs/ramp_flag_diagnostics/` include a PNG figure, per-flag and per-segment CSVs, site-level thresholds and summaries, figure source data, a bilingual HTML report, and English methods, caption, and reviewer-response drafts. Figures are exported only as PNG. The JSON record contains input hashes, software versions, and validation results. The figure uses complete dataset counts, without inferential error bars. Its classes characterize screening flags and do not establish measurement errors or physical ramp events.

Illustrative examples require complete two-hour context on either side, no additional flags in that context, and power bounded by zero and the public capacity. Within each eligible class, the example nearest the median capacity-normalized power range is selected, with ties resolved by public label and start time. This selection affects only the displayed examples.

The original Figure 4 output is preserved. The diagnostic script checks every site's flag count against the original heatmap function before exporting. To check segmentation boundaries and sign-pattern handling on constructed signals, run:

`python -m unittest discover -s tests -p "test_ramp_flag_diagnostics.py"`

## Naming convention

All public station labels follow the county-level or district-level naming system finalized for the manuscript. When two wind farms share the same disclosed geographical location, suffixes such as `_1` and `_2` are retained. For duplicate county names across different cities, disambiguation is handled directly in the public labels, such as `Hebi - Qi County` and `Kaifeng - Qi County`.

## Temporal resolution

The public 1 h wind power product is not generated by hourly averaging. Instead, it is derived by retaining only the top-of-hour records from the cleaned 15 min time series.

## Data access

The public HENAN-WPF CSV data are included under `data/HENAN-WPF_public_release/` and archived at [Zenodo (DOI: 10.5281/zenodo.21215961)](https://doi.org/10.5281/zenodo.21215961). The release includes the raw 15 min wind power table, processed 15 min and 1 h wind power products, site-matched ERA5 files, and the public station index. See [data/README.md](data/README.md) for the file layout and units.
