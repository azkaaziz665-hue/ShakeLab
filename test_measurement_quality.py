"""Tests for ShakeLab acquisition-quality controls."""

import unittest

import numpy as np

from measurement_quality import assess_baseline, lowpass_step, validate_known_displacement


class TestMeasurementQuality(unittest.TestCase):
    def test_accepts_stable_two_second_baseline(self):
        t = np.arange(61) / 30.0
        result = assess_baseline(t, np.zeros_like(t), np.zeros_like(t), 0.25)
        self.assertTrue(result["valid"])

    def test_rejects_moving_baseline(self):
        t = np.arange(61) / 30.0
        result = assess_baseline(t, np.linspace(0, 20, len(t)), np.zeros_like(t), 0.25)
        self.assertFalse(result["valid"])

    def test_lowpass_reduces_single_frame_spike(self):
        filtered = lowpass_step(20.0, previous=0.0, dt_s=1.0 / 30.0, cutoff_hz=3.0)
        self.assertGreater(filtered, 0.0)
        self.assertLess(filtered, 20.0)

    def test_physical_validation_reports_error(self):
        result = validate_known_displacement(10.0, 9.6)
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["error_pct"], 4.0)


if __name__ == "__main__":
    unittest.main()
