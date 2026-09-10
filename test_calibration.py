"""
test_calibration.py — Unit Tests untuk Modul Kalibrasi Homography (ShakeLab)
===========================================================================
Menguji seluruh fungsi dalam calibration.py:
  1. compute_homography
  2. pixel_to_mm
  3. save_homography & load_homography (JSON & NPY)
  4. compute_marker_dynamic_scale
  5. cross_check_homography_vs_dynamic
  6. test_calibration (validasi ground-truth)
  7. generate_aruco_calibration_points
"""

import os
import shutil
import tempfile
import unittest
import numpy as np
import cv2

from calibration import (
    compute_homography,
    pixel_to_mm,
    save_homography,
    load_homography,
    compute_marker_dynamic_scale,
    cross_check_homography_vs_dynamic,
    test_calibration,
    generate_aruco_calibration_points,
)


class TestCalibrationModule(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_homography_valid(self):
        # 4 sudut persegi sederhana: (0,0)->(0,0), (100,0)->(50,0), (100,100)->(50,50), (0,100)->(0,50)
        src = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float64)
        dst = np.array([[0, 0], [50, 0], [50, 50], [0, 50]], dtype=np.float64)

        H, mask = compute_homography(src, dst, method=0)
        self.assertIsNotNone(H)
        self.assertEqual(H.shape, (3, 3))

        # Test transformasi titik (50, 50) harus menjadi (25, 25)
        pt_transformed = pixel_to_mm((50, 50), H)
        np.testing.assert_allclose(pt_transformed[0], [25.0, 25.0], atol=1e-3)

    def test_compute_homography_invalid_points(self):
        # Kurang dari 4 titik
        src = np.array([[0, 0], [10, 10], [20, 20]], dtype=np.float64)
        dst = np.array([[0, 0], [5, 5], [10, 10]], dtype=np.float64)
        with self.assertRaises(ValueError):
            compute_homography(src, dst)

        # Dimensi tidak cocok
        src_4 = np.zeros((4, 2))
        dst_5 = np.zeros((5, 2))
        with self.assertRaises(ValueError):
            compute_homography(src_4, dst_5)

    def test_pixel_to_mm_shapes(self):
        H = np.eye(3, dtype=np.float64)
        # Single tuple
        res1 = pixel_to_mm((10.0, 20.0), H)
        self.assertEqual(res1.shape, (1, 2))
        self.assertAlmostEqual(res1[0, 0], 10.0)
        self.assertAlmostEqual(res1[0, 1], 20.0)

        # List of points
        res2 = pixel_to_mm([(10, 20), (30, 40)], H)
        self.assertEqual(res2.shape, (2, 2))

        # Array Nx2
        pts = np.random.rand(10, 2) * 100
        res3 = pixel_to_mm(pts, H)
        self.assertEqual(res3.shape, (10, 2))
        np.testing.assert_allclose(res3, pts, atol=1e-5)

    def test_save_load_homography_json(self):
        H_orig = np.array([
            [1.2, 0.05, 10.5],
            [-0.02, 1.15, 20.1],
            [1e-5, -2e-5, 1.0]
        ], dtype=np.float64)

        json_path = os.path.join(self.temp_dir, "test_H.json")
        meta = {"unit": "mm", "source": "test"}
        saved_path = save_homography(H_orig, json_path, metadata=meta)
        self.assertTrue(os.path.exists(saved_path))

        # Test single return
        H_loaded = load_homography(saved_path)
        np.testing.assert_allclose(H_orig, H_loaded, atol=1e-6)

        # Test return with metadata
        H_loaded2, meta_loaded = load_homography(saved_path, return_metadata=True)
        np.testing.assert_allclose(H_orig, H_loaded2, atol=1e-6)
        self.assertEqual(meta_loaded.get("unit"), "mm")

    def test_save_load_homography_npy(self):
        H_orig = np.random.rand(3, 3).astype(np.float64)
        npy_path = os.path.join(self.temp_dir, "test_H.npy")
        save_homography(H_orig, npy_path)
        self.assertTrue(os.path.exists(npy_path))

        H_loaded = load_homography(npy_path)
        np.testing.assert_allclose(H_orig, H_loaded, atol=1e-6)

    def test_compute_marker_dynamic_scale(self):
        # Persegi panjang 100 x 100 px, marker fisik 50 x 50 mm
        # scale harus = 50 / 100 = 0.5 mm/px
        corners = np.array([
            [10.0, 10.0],
            [110.0, 10.0],
            [110.0, 110.0],
            [10.0, 110.0]
        ], dtype=np.float64)

        scale = compute_marker_dynamic_scale(corners, marker_size_mm=50.0)
        self.assertAlmostEqual(scale, 0.5, places=3)

        # Test float input
        scale_float = compute_marker_dynamic_scale(100.0, L_marker_mm=50.0)
        self.assertAlmostEqual(scale_float, 0.5, places=3)

    def test_cross_check_homography_vs_dynamic(self):
        # Case 1: Homography & dynamic scale cocok (deviasi < 5%)
        res = cross_check_homography_vs_dynamic(
            disp_homography_mm=5.1,
            disp_px=10.0,
            dynamic_scale_mm_px=0.5,
            tolerance_percent=5.0
        )
        self.assertTrue(res["valid"])
        self.assertLess(res["discrepancy_percent"], 5.0)

        # Case 2: Discrepancy besar (> 5%)
        res_fail = cross_check_homography_vs_dynamic(
            disp_homography_mm=7.0,
            disp_px=10.0,
            dynamic_scale_mm_px=0.5,
            tolerance_percent=5.0
        )
        self.assertFalse(res_fail["valid"])
        self.assertGreater(res_fail["discrepancy_percent"], 5.0)

    def test_test_calibration(self):
        # Test signature user: test_calibration(jarak_diketahui_mm, hasil_ukur_mm, tolerance_pct)
        res_pass = test_calibration(100.0, 101.0, tolerance_pct=2.0)
        self.assertTrue(res_pass["passed"])
        self.assertAlmostEqual(res_pass["error_mm"], 1.0, places=3)
        self.assertAlmostEqual(res_pass["error_pct"], 1.0, places=3)

        res_fail = test_calibration(100.0, 105.0, tolerance_pct=2.0)
        self.assertFalse(res_fail["passed"])
        self.assertGreater(res_fail["error_pct"], 2.0)

        # Test invalid ground truth
        res_invalid = test_calibration(0.0, 10.0)
        self.assertFalse(res_invalid["passed"])

    def test_generate_aruco_calibration_points(self):
        corners_g = np.array([[100, 100], [150, 100], [150, 150], [100, 150]], dtype=np.float64)
        corners_t = np.array([[100, 50], [150, 50], [150, 100], [100, 100]], dtype=np.float64)

        pts_src, pts_dst = generate_aruco_calibration_points(
            corners_ground_px=corners_g,
            corners_top_px=corners_t,
            L_marker_mm=50.0,
            H_fisik_mm=100.0
        )
        self.assertEqual(pts_src.shape, (8, 2))
        self.assertEqual(pts_dst.shape, (8, 2))

    def test_calibration_points_use_declared_physical_lateral_offset(self):
        # A large horizontal image offset can be caused by perspective and must
        # not become a physical X offset unless the user explicitly supplies it.
        corners_g = np.array([[100, 200], [150, 200], [150, 250], [100, 250]], dtype=np.float64)
        corners_t = np.array([[240, 50], [290, 50], [290, 100], [240, 100]], dtype=np.float64)

        _, pts_dst_zero = generate_aruco_calibration_points(
            corners_g, corners_t, L_marker_mm=50.0, H_fisik_mm=100.0
        )
        _, pts_dst_offset = generate_aruco_calibration_points(
            corners_g, corners_t, L_marker_mm=50.0, H_fisik_mm=100.0, top_offset_x_mm=25.0
        )

        self.assertAlmostEqual(float(pts_dst_zero[4:, 0].mean()), 0.0)
        self.assertAlmostEqual(float(pts_dst_zero[4:, 1].mean()), -100.0)
        self.assertAlmostEqual(float(pts_dst_offset[4:, 0].mean()), 25.0)


if __name__ == "__main__":
    unittest.main()
