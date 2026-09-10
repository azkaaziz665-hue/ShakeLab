"""Unit tests for ShakeLab frequency and drift calculations."""

import unittest

import numpy as np

from signal_analysis import calculate_drift_ratio, estimate_dominant_frequency


class TestSignalAnalysis(unittest.TestCase):
    def test_estimates_frequency_from_jittered_camera_timestamps(self):
        rng = np.random.default_rng(42)
        intervals = (1.0 / 30.0) + rng.normal(0.0, 0.0015, 900)
        timestamps = np.cumsum(intervals)
        expected_hz = 2.4
        displacement = 8.0 * np.sin(2.0 * np.pi * expected_hz * timestamps)
        displacement += rng.normal(0.0, 0.12, timestamps.size)

        result = estimate_dominant_frequency(timestamps, displacement)

        self.assertTrue(result["valid"], result["reason"])
        self.assertAlmostEqual(result["frequency_hz"], expected_hz, delta=0.08)

    def test_rejects_constant_signal(self):
        timestamps = np.arange(100, dtype=float) / 30.0
        result = estimate_dominant_frequency(timestamps, np.ones(100))

        self.assertFalse(result["valid"])
        self.assertIsNone(result["frequency_hz"])

    def test_drift_uses_actual_structure_height(self):
        result = calculate_drift_ratio(displacement_mm=-8.0, structure_height_mm=320.0)

        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["drift_ratio_pct"], 2.5)

    def test_drift_rejects_invalid_height(self):
        result = calculate_drift_ratio(displacement_mm=8.0, structure_height_mm=0.0)

        self.assertFalse(result["valid"])
        self.assertIsNone(result["drift_ratio_pct"])


if __name__ == "__main__":
    unittest.main()
