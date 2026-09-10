"""Quality controls shared by the ShakeLab acquisition pipeline."""

from typing import Dict, Sequence

import numpy as np


def assess_baseline(
    timestamps_s: Sequence[float],
    rel_x_px: Sequence[float],
    rel_y_px: Sequence[float],
    scale_mm_px: float,
    min_duration_s: float = 2.0,
    min_samples: int = 30,
    max_std_mm: float = 0.35,
    max_peak_to_peak_mm: float = 1.5,
) -> Dict[str, object]:
    """Accept a tare baseline only when it is long enough and physically stable."""
    t = np.asarray(list(timestamps_s), dtype=np.float64)
    x = np.asarray(list(rel_x_px), dtype=np.float64)
    y = np.asarray(list(rel_y_px), dtype=np.float64)
    if t.size != x.size or t.size != y.size or t.size < min_samples:
        return {"valid": False, "reason": "Sampel baseline belum cukup.", "progress": min(1.0, t.size / max(1, min_samples))}
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        return {"valid": False, "reason": "Baseline mengandung data tidak valid.", "progress": 0.0}

    duration = float(t[-1] - t[0])
    if duration < min_duration_s:
        return {"valid": False, "reason": "Menunggu baseline diam selama 2 detik.", "progress": max(0.0, duration / min_duration_s)}

    scale = max(abs(float(scale_mm_px)), 1e-9)
    x_mm, y_mm = x * scale, y * scale
    std_mm = float(max(np.std(x_mm), np.std(y_mm)))
    p2p_mm = float(max(np.ptp(x_mm), np.ptp(y_mm)))
    valid = std_mm <= max_std_mm and p2p_mm <= max_peak_to_peak_mm
    return {
        "valid": valid,
        "reason": "" if valid else "Miniatur atau kamera masih bergerak saat tare.",
        "progress": 1.0,
        "baseline_x_px": float(np.mean(x)),
        "baseline_y_px": float(np.mean(y)),
        "std_mm": std_mm,
        "peak_to_peak_mm": p2p_mm,
        "duration_s": duration,
    }


def lowpass_step(value: float, previous: float | None, dt_s: float, cutoff_hz: float = 12.0) -> float:
    """One-pole low-pass filter that remains stable with variable camera FPS."""
    value = float(value)
    if previous is None or dt_s <= 0.0:
        return value
    rc = 1.0 / (2.0 * np.pi * max(float(cutoff_hz), 1e-6))
    alpha = float(np.clip(dt_s / (rc + dt_s), 0.0, 1.0))
    return float(previous + alpha * (value - previous))


def validate_known_displacement(known_mm: float, measured_mm: float, tolerance_pct: float = 5.0) -> Dict[str, object]:
    """Compare an application reading with a physical displacement reference."""
    known = abs(float(known_mm))
    measured = abs(float(measured_mm))
    if known <= 0.0 or not np.isfinite(known) or not np.isfinite(measured):
        return {"valid": False, "error_mm": float("nan"), "error_pct": float("nan"), "reason": "Jarak referensi harus lebih dari 0 mm."}
    error_mm = abs(measured - known)
    error_pct = error_mm / known * 100.0
    valid = error_pct <= float(tolerance_pct)
    return {
        "valid": valid,
        "error_mm": error_mm,
        "error_pct": error_pct,
        "tolerance_pct": float(tolerance_pct),
        "reason": "" if valid else "Galat kalibrasi melebihi toleransi.",
    }


def quality_summary(total_frames: int, valid_frames: int, interpolated_frames: int, missing_frames: int, baseline: Dict[str, object], fps: float) -> Dict[str, object]:
    """Create serializable per-session quality metadata."""
    total = max(int(total_frames), 0)
    return {
        "tracking_valid_pct": (int(valid_frames) / total * 100.0) if total else 0.0,
        "valid_frames": int(valid_frames),
        "interpolated_frames_excluded": int(interpolated_frames),
        "missing_frames": int(missing_frames),
        "fps_average": float(fps),
        "baseline_valid": bool(baseline.get("valid", False)),
        "baseline_std_mm": baseline.get("std_mm"),
        "baseline_peak_to_peak_mm": baseline.get("peak_to_peak_mm"),
    }
