import unittest

from local_scale import marker_scale_mm_per_px, relative_local_displacement


class LocalScaleTests(unittest.TestCase):
    def test_marker_scale_uses_actual_marker_side(self):
        self.assertAlmostEqual(marker_scale_mm_per_px(40.0, 100.0), 0.4)

    def test_local_scales_cancel_common_physical_motion(self):
        result = relative_local_displacement(
            ground_px=(160.0, 50.0), top_px=(212.5, 100.0),
            ground_origin_px=(100.0, 50.0), top_origin_px=(100.0, 100.0),
            ground_scale_mm_px=0.5, top_scale_mm_px=0.4,
        )
        self.assertAlmostEqual(result["ground_x_mm"], 30.0)
        self.assertAlmostEqual(result["top_x_mm"], 45.0)
        self.assertAlmostEqual(result["disp_x_mm"], 15.0)

    def test_ground_only_motion_is_opposite_relative_displacement(self):
        result = relative_local_displacement(
            ground_px=(160.0, 50.0), top_px=(100.0, 100.0),
            ground_origin_px=(100.0, 50.0), top_origin_px=(100.0, 100.0),
            ground_scale_mm_px=0.5, top_scale_mm_px=0.4,
        )
        self.assertAlmostEqual(result["disp_x_mm"], -30.0)

    def test_invalid_scale_is_rejected(self):
        with self.assertRaises(ValueError):
            marker_scale_mm_per_px(40.0, 0.0)


if __name__ == "__main__":
    unittest.main()
