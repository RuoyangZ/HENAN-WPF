# HENAN-WPF public data

The 41 CSV files in `HENAN-WPF_public_release/` mirror the public data archived at [Zenodo (DOI: 10.5281/zenodo.21215961)](https://doi.org/10.5281/zenodo.21215961). Their contents are unchanged; the directory layout matches the inputs expected by the scripts in this repository.

| Location within `HENAN-WPF_public_release/` | Contents | CSV files |
| --- | --- | ---: |
| `raw_wind_power/` | Raw 15 min wind power table | 1 |
| `processed_wind_power/` | Processed 15 min and 1 h wind power tables | 2 |
| `era5_data/representative_sites/` | Meteorological data for six representative sites | 6 |
| `era5_data/all_sites_wind100/` | 100 m wind data for the remaining 30 sites | 30 |
| `era5_data/download_manifest_public.csv` | Public meteorological download manifest | 1 |
| `metadata/public_station_index.csv` | Public station labels and metadata | 1 |

Power values are in MW. The 1 h power product retains top-of-hour records from the processed 15 min series; it is not an hourly average.

The meteorological CSVs retain wind speed and gusts in **km/h**. The weather plotting script converts these values to m/s in memory for the wind rose plots; it does not modify the CSVs. Temperature is in degrees Celsius, surface pressure in hPa, precipitation in mm, and wind direction in degrees. The meteorological tables include UTC and local timestamps as labelled in their columns.

The published ramp-screening records and segment table are in [`../quality_flags/`](../quality_flags/). These files describe the ramp screening criterion, not a complete per-record flag table for all anomaly types.

After cloning the repository, the data are already in the directory expected by the figure scripts. See the root README for installation and execution instructions.
