"""Boundary and classification checks using known synthetic difference patterns."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


spec = importlib.util.spec_from_file_location(
    "ramp_flag_diagnostics",
    Path(__file__).resolve().parents[1] / "scripts" / "plot_ramp_flag_diagnostics.py",
)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class RampFlagDiagnosticsTests(unittest.TestCase):
    def test_known_patterns_and_first_last_interval_boundaries(self):
        increments = np.zeros(1000)
        specified = {1: 10, 100: 10, 200: 10, 201: -10, 300: 10, 301: 12,
                     400: 10, 401: -12, 402: 11, 500: -10, 501: -11, 999: 10}
        for position, value in specified.items():
            increments[position] = value
        power = pd.DataFrame({"datetime": pd.date_range("2024-01-01", periods=1000, freq="15min"),
                              "Example": 50 + np.cumsum(increments)})
        power.loc[750, "Example"] = np.nan
        meta = pd.DataFrame({"Public station label": ["Example"], "Installed capacity (MW)": [200]})
        segments, flags, sites, summary, duration, masks = analysis.analyze(power, meta)
        self.assertEqual(np.flatnonzero(masks["Example"]).tolist(), list(specified))
        self.assertEqual(segments.flag_count.tolist(), [1, 1, 2, 2, 3, 2, 1])
        self.assertEqual(segments.category.tolist(), ["single_step", "single_step", "two_step_reversal",
                         "same_direction", "longer_mixed", "same_direction", "single_step"])
        self.assertEqual(segments.duration_min.tolist(), [15, 15, 30, 30, 45, 30, 15])
        self.assertEqual(segments.iloc[0].start_time, power.datetime.iloc[0])
        self.assertEqual(segments.iloc[-1].end_time, power.datetime.iloc[-1])
        self.assertEqual(sites.iloc[0].nonmissing_adjacent_differences, 997)
        reversal = segments.loc[segments.category == "two_step_reversal"].iloc[0]
        self.assertEqual(reversal.sign_sequence, "+-")
        self.assertEqual(reversal.net_change_mw, 0)
        self.assertEqual(reversal.power_range_mw, 10)
        self.assertEqual(reversal.duration_min, 30)
        self.assertEqual(summary.flag_count.sum(), len(specified))

    def test_reverse_order_and_multistep_shapes(self):
        self.assertEqual(analysis.classify(np.array([-9, 9])), "two_step_reversal")
        self.assertEqual(analysis.classify(np.array([-9, -8, -7])), "same_direction")
        self.assertEqual(analysis.classify(np.array([9, -8, 7])), "longer_mixed")


if __name__ == "__main__":
    unittest.main()
