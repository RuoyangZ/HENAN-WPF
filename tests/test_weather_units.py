"""Check wind-unit conversion without modifying the source CSV."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


spec = importlib.util.spec_from_file_location(
    "weather_validation", Path(__file__).resolve().parents[1] / "scripts" / "plot_weather_validation.py"
)
weather = importlib.util.module_from_spec(spec)
spec.loader.exec_module(weather)


class WeatherUnitTests(unittest.TestCase):
    def test_public_kmh_to_mps_and_original_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Example_County.csv"
            pd.DataFrame({
                "datetime_local": ["2024-01-01 00:00", "2024-01-01 01:00"],
                "wind_speed_10m": [0.0, 36.0],
                "wind_speed_100m": [18.0, 72.0],
                "wind_gusts_10m": [10.8, 90.0],
                "wind_direction_100m": [90.0, 270.0],
                "temperature_2m": [-2.0, 8.0],
            }).to_csv(path, index=False)
            original = path.read_bytes()
            with patch.object(weather, "WEATHER_DIR", Path(directory)):
                converted = weather.load_station_weather("Example County")
            np.testing.assert_allclose(converted.wind_speed_10m, [0.0, 10.0])
            np.testing.assert_allclose(converted.wind_speed_100m, [5.0, 20.0])
            np.testing.assert_allclose(converted.wind_gusts_10m, [3.0, 25.0])
            np.testing.assert_array_equal(converted.wind_direction_100m, [90.0, 270.0])
            np.testing.assert_array_equal(converted.temperature_2m, [-2.0, 8.0])
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
