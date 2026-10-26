# HENAN-WPF Public Release Notes

This note summarizes the structure of the public HENAN-WPF dataset package intended for repository deposition.

## Public package structure

- `raw_wind_power/`
  - Public raw wind power observations at 15 min resolution.
- `processed_wind_power/`
  - Public processed wind power products at 15 min resolution and 1 h sampled resolution.
- `era5_data/`
  - Site-matched ERA5 reanalysis data.
  - `all_sites_wind100/` contains 100 m wind speed and wind direction products for all sites.
  - `representative_sites/` contains expanded ERA5 variables for the representative sites.
  - `download_manifest_public.csv` provides a public ERA5 file index without precise coordinates.
- `metadata/`
  - `public_station_index.csv` provides the public station label, city, county-level geographical location, installed capacity, and terrain type.

## Public naming policy

- The public release uses county-level or district-level geographical names as the primary station labels.
- Suffixes such as `_1` and `_2` are retained only when two wind farms share the same disclosed geographical location.
- Duplicate county names across different cities are disambiguated directly in the public labels, such as `Hebi - Qi County` and `Kaifeng - Qi County`.

## Disclosure policy

- Precise longitude and latitude are not included in the public release package.
- The public metadata disclose only generalized county-level or district-level geographical information.
- All power-data headers, ERA5 filenames, metadata tables, and manuscript figures follow the same public naming convention.

## Representative stations with expanded ERA5 variables

Neihuang County, Linying County_1, Yucheng County, Lushi County, Jiyuan City_1, and Xin County
