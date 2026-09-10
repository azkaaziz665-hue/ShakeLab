"""Camera-intrinsic calibration and marker pose helpers for ShakeLab."""

import json
import os
import time
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


def save_intrinsics(filepath: str, camera_matrix: np.ndarray, distortion: np.ndarray, image_size: Tuple[int, int], rms: float) -> str:
    payload = {
        "camera_matrix": np.asarray(camera_matrix, dtype=float).tolist(),
        "distortion": np.asarray(distortion, dtype=float).reshape(-1).tolist(),
        "image_size": [int(image_size[0]), int(image_size[1])],
        "rms_reprojection_error": float(rms),
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return os.path.abspath(filepath)


def load_intrinsics(filepath: str) -> Optional[Dict[str, object]]:
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
        matrix = np.asarray(payload["camera_matrix"], dtype=np.float64)
        distortion = np.asarray(payload["distortion"], dtype=np.float64).reshape(-1, 1)
        if matrix.shape != (3, 3) or distortion.size < 4:
            return None
        return {**payload, "camera_matrix": matrix, "distortion": distortion}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def resolution_is_compatible(calibration_size: Tuple[int, int], frame_size: Tuple[int, int], tolerance: float = 0.01) -> bool:
    """Accept scaled images only when their aspect ratios still match."""
    calib_w, calib_h = (float(calibration_size[0]), float(calibration_size[1]))
    frame_w, frame_h = (float(frame_size[0]), float(frame_size[1]))
    if min(calib_w, calib_h, frame_w, frame_h) <= 0.0:
        return False
    return abs((frame_w / frame_h) / (calib_w / calib_h) - 1.0) <= float(tolerance)


def estimate_marker_pose(
    corners_px: np.ndarray,
    marker_size_mm: float,
    camera_matrix: np.ndarray,
    distortion: np.ndarray,
    previous_tvec: Optional[np.ndarray] = None,
    max_reprojection_error_px: float = 1.5,
    max_depth_step_mm: float = 20.0,
) -> Optional[Dict[str, object]]:
    """Estimate a square-marker pose and reject ambiguous or discontinuous depth."""
    marker_size = float(marker_size_mm)
    if marker_size <= 0.0:
        return None
    half = marker_size / 2.0
    object_points = np.array([
        [-half, +half, 0.0], [+half, +half, 0.0],
        [+half, -half, 0.0], [-half, -half, 0.0],
    ], dtype=np.float64)
    image_points = np.asarray(corners_px, dtype=np.float64).reshape(4, 2)
    result = cv2.solvePnPGeneric(
        object_points, image_points, np.asarray(camera_matrix, dtype=np.float64),
        np.asarray(distortion, dtype=np.float64), flags=cv2.SOLVEPNP_IPPE_SQUARE,
    )
    if len(result) < 3 or not result[0]:
        return None
    _, rvecs, tvecs, *_ = result

    candidates = []
    for rvec, tvec in zip(rvecs, tvecs):
        rvec = np.asarray(rvec, dtype=np.float64).reshape(3, 1)
        tvec = np.asarray(tvec, dtype=np.float64).reshape(3, 1)
        if not np.isfinite(rvec).all() or not np.isfinite(tvec).all() or tvec[2, 0] <= 0.0:
            continue
        projected, _ = cv2.projectPoints(
            object_points, rvec, tvec, np.asarray(camera_matrix, dtype=np.float64),
            np.asarray(distortion, dtype=np.float64),
        )
        residual = projected.reshape(4, 2) - image_points
        reprojection_error = float(np.sqrt(np.mean(np.sum(residual ** 2, axis=1))))
        if reprojection_error <= float(max_reprojection_error_px):
            candidates.append({
                "rvec": rvec,
                "tvec": tvec,
                "depth_mm": float(tvec[2, 0]),
                "reprojection_error_px": reprojection_error,
            })

    if not candidates:
        return None

    if previous_tvec is None:
        chosen = min(candidates, key=lambda pose: pose["reprojection_error_px"])
    else:
        previous = np.asarray(previous_tvec, dtype=np.float64).reshape(3, 1)
        if not np.isfinite(previous).all():
            return None
        nearby = [
            pose for pose in candidates
            if abs(pose["depth_mm"] - float(previous[2, 0])) <= float(max_depth_step_mm)
        ]
        if not nearby:
            return None
        # A marker may move laterally, but its depth cannot switch tens of mm
        # within a single camera frame without a physically visible event.
        chosen = min(
            nearby,
            key=lambda pose: (
                abs(pose["depth_mm"] - float(previous[2, 0])),
                pose["reprojection_error_px"],
            ),
        )

    return {**chosen, "candidate_count": len(candidates)}


def estimate_marker_depth(corners_px: np.ndarray, marker_size_mm: float, camera_matrix: np.ndarray, distortion: np.ndarray) -> Optional[float]:
    """Return marker-center depth in mm from a calibrated camera pose."""
    pose = estimate_marker_pose(corners_px, marker_size_mm, camera_matrix, distortion)
    return None if pose is None else float(pose["depth_mm"])


def estimate_marker_size_depth_change(
    baseline_size_px: float,
    current_size_px: float,
    marker_size_mm: float,
    focal_length_px: float,
) -> Optional[float]:
    """Estimate camera-axis change from the apparent size of one planar marker.

    Positive values mean the marker appears smaller (farther from the camera).
    The result is also affected by marker tilt, so it is not vertical height.
    """
    baseline = float(baseline_size_px)
    current = float(current_size_px)
    marker_size = float(marker_size_mm)
    focal = float(focal_length_px)
    if min(baseline, current, marker_size, focal) <= 0.0:
        return None
    reference_depth = focal * marker_size / baseline
    return float(reference_depth * (baseline / current - 1.0))
