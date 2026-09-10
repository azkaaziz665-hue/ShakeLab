import os
import tempfile
import unittest

import cv2
import numpy as np

from camera_calibration import (
    estimate_marker_depth, estimate_marker_pose, estimate_marker_size_depth_change, load_intrinsics,
    resolution_is_compatible, save_intrinsics,
)


class TestCameraCalibration(unittest.TestCase):
    def test_save_and_load_intrinsics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "camera.json")
            matrix = np.array([[800.0, 0.0, 640.0], [0.0, 800.0, 360.0], [0.0, 0.0, 1.0]])
            save_intrinsics(path, matrix, np.zeros(5), (1280, 720), 0.2)
            loaded = load_intrinsics(path)
            self.assertIsNotNone(loaded)
            np.testing.assert_allclose(loaded["camera_matrix"], matrix)

    def test_estimates_marker_depth_from_projected_corners(self):
        matrix = np.array([[800.0, 0.0, 640.0], [0.0, 800.0, 360.0], [0.0, 0.0, 1.0]])
        distortion = np.zeros((5, 1))
        marker_size = 40.0
        half = marker_size / 2.0
        object_points = np.array([[-half, half, 0], [half, half, 0], [half, -half, 0], [-half, -half, 0]], dtype=np.float64)
        image_points, _ = cv2.projectPoints(object_points, np.zeros(3), np.array([0.0, 0.0, 500.0]), matrix, distortion)
        depth = estimate_marker_depth(image_points.reshape(4, 2), marker_size, matrix, distortion)
        self.assertAlmostEqual(depth, 500.0, delta=1.0)

    def test_pose_rejects_depth_jump_from_previous_frame(self):
        matrix = np.array([[800.0, 0.0, 640.0], [0.0, 800.0, 360.0], [0.0, 0.0, 1.0]])
        distortion = np.zeros((5, 1))
        half = 20.0
        object_points = np.array(
            [[-half, half, 0], [half, half, 0], [half, -half, 0], [-half, -half, 0]],
            dtype=np.float64,
        )
        image_points, _ = cv2.projectPoints(
            object_points, np.zeros(3), np.array([0.0, 0.0, 500.0]), matrix, distortion
        )
        pose = estimate_marker_pose(
            image_points.reshape(4, 2), 40.0, matrix, distortion,
            previous_tvec=np.array([[0.0], [0.0], [500.0]]),
        )
        self.assertIsNotNone(pose)
        self.assertAlmostEqual(pose["depth_mm"], 500.0, delta=1.0)

        rejected = estimate_marker_pose(
            image_points.reshape(4, 2), 40.0, matrix, distortion,
            previous_tvec=np.array([[0.0], [0.0], [450.0]]), max_depth_step_mm=20.0,
        )
        self.assertIsNone(rejected)

    def test_resolution_requires_matching_aspect_ratio(self):
        self.assertTrue(resolution_is_compatible((640, 480), (1280, 960)))
        self.assertFalse(resolution_is_compatible((640, 480), (1280, 720)))

    def test_marker_size_depth_change_uses_expected_direction(self):
        self.assertAlmostEqual(
            estimate_marker_size_depth_change(100.0, 100.0, 40.0, 800.0), 0.0
        )
        self.assertGreater(
            estimate_marker_size_depth_change(100.0, 80.0, 40.0, 800.0), 0.0
        )
        self.assertLess(
            estimate_marker_size_depth_change(100.0, 120.0, 40.0, 800.0), 0.0
        )


if __name__ == "__main__":
    unittest.main()
