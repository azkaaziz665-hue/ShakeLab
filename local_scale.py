"""Local pixel-to-millimeter calibration helpers for ShakeLab."""

from typing import Dict, Sequence

import numpy as np


def marker_scale_mm_per_px(marker_size_mm: float, marker_side_px: float) -> float:
    """Return the local scale for one marker using its known printed side."""
    size = float(marker_size_mm)
    side = float(marker_side_px)
    if not np.isfinite(size) or not np.isfinite(side) or size <= 0.0 or side <= 0.0:
        raise ValueError("Ukuran fisik dan ukuran marker dalam pixel harus lebih dari 0.")
    return size / side


def relative_local_displacement(
    ground_px: Sequence[float],
    top_px: Sequence[float],
    ground_origin_px: Sequence[float],
    top_origin_px: Sequence[float],
    ground_scale_mm_px: float,
    top_scale_mm_px: float,
) -> Dict[str, float]:
    """Convert each marker with its local scale, then return relative X/Y motion."""
    g = np.asarray(ground_px, dtype=np.float64)
    t = np.asarray(top_px, dtype=np.float64)
    g0 = np.asarray(ground_origin_px, dtype=np.float64)
    t0 = np.asarray(top_origin_px, dtype=np.float64)
    if g.shape != (2,) or t.shape != (2,) or g0.shape != (2,) or t0.shape != (2,):
        raise ValueError("Koordinat marker harus terdiri dari pasangan X dan Y.")

    gs = float(ground_scale_mm_px)
    ts = float(top_scale_mm_px)
    if not np.isfinite(gs) or not np.isfinite(ts) or gs <= 0.0 or ts <= 0.0:
        raise ValueError("Skala lokal Ground dan Top harus lebih dari 0.")

    ground_mm = (g - g0) * gs
    top_mm = (t - t0) * ts
    return {
        "ground_x_mm": float(ground_mm[0]),
        "ground_y_mm": float(ground_mm[1]),
        "top_x_mm": float(top_mm[0]),
        "top_y_mm": float(top_mm[1]),
        "disp_x_mm": float(top_mm[0] - ground_mm[0]),
        "disp_y_mm": float(top_mm[1] - ground_mm[1]),
    }
