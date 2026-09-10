"""Numerical helpers for ShakeLab vibration metrics."""

from typing import Dict, Sequence

import numpy as np


def _invalid_frequency(reason: str) -> Dict[str, object]:
    return {
        "valid": False,
        "frequency_hz": None,
        "sample_rate_hz": 0.0,
        "duration_s": 0.0,
        "snr_db": float("-inf"),
        "reason": reason,
    }


def estimate_dominant_frequency(
    timestamps_s: Sequence[float],
    displacement_mm: Sequence[float],
    min_frequency_hz: float = 0.2,
    max_frequency_hz: float | None = None,
    min_samples: int = 64,
    min_duration_s: float = 2.0,
    min_snr_db: float = 6.0,
) -> Dict[str, object]:
    """Estimate the dominant lateral frequency using a detrended FFT.

    Camera frames are not always evenly spaced. The samples are resampled on a
    uniform grid before applying a Hann window and an FFT, which avoids treating
    frame-rate jitter as structural vibration.
    """
    try:
        t = np.asarray(list(timestamps_s), dtype=np.float64)
        x = np.asarray(list(displacement_mm), dtype=np.float64)
    except (TypeError, ValueError):
        return _invalid_frequency("Timestamp atau displacement tidak numerik.")

    if t.ndim != 1 or x.ndim != 1 or t.size != x.size:
        return _invalid_frequency("Timestamp dan displacement harus satu dimensi dengan panjang sama.")

    finite = np.isfinite(t) & np.isfinite(x)
    t = t[finite]
    x = x[finite]
    if t.size < min_samples:
        return _invalid_frequency(f"Sampel valid belum cukup ({t.size}/{min_samples}).")
    if np.any(np.diff(t) <= 0):
        return _invalid_frequency("Timestamp harus meningkat pada setiap sampel.")

    dt = np.diff(t)
    median_dt = float(np.median(dt))
    if median_dt <= 0.0:
        return _invalid_frequency("Interval frame tidak valid.")

    sample_rate = 1.0 / median_dt
    uniform_t = np.arange(t[0], t[-1] + median_dt * 0.5, median_dt)
    uniform_x = np.interp(uniform_t, t, x)
    duration = float(uniform_t[-1] - uniform_t[0])
    if uniform_x.size < min_samples or duration < min_duration_s:
        return _invalid_frequency("Durasi rekaman valid belum cukup untuk estimasi frekuensi.")

    # Remove the baseline and slow camera/structure drift before spectral analysis.
    trend = np.polyval(np.polyfit(uniform_t - uniform_t[0], uniform_x, 1), uniform_t - uniform_t[0])
    signal = uniform_x - trend
    if float(np.std(signal)) <= 1e-9:
        return _invalid_frequency("Sinyal getaran terlalu kecil atau konstan.")

    windowed = signal * np.hanning(signal.size)
    magnitudes = np.abs(np.fft.rfft(windowed))
    frequencies = np.fft.rfftfreq(windowed.size, d=median_dt)

    lower = max(float(min_frequency_hz), 1.0 / duration)
    upper = min(float(max_frequency_hz) if max_frequency_hz is not None else sample_rate * 0.40, sample_rate * 0.45)
    candidates = np.flatnonzero((frequencies >= lower) & (frequencies <= upper))
    if candidates.size == 0:
        return _invalid_frequency("Rentang frekuensi tidak tersedia pada laju sampel saat ini.")

    peak_index = int(candidates[np.argmax(magnitudes[candidates])])
    peak_frequency = float(frequencies[peak_index])

    # Quadratic interpolation gives a less quantized estimate than an FFT bin.
    if 0 < peak_index < len(magnitudes) - 1:
        left, center, right = magnitudes[peak_index - 1:peak_index + 2]
        denominator = left - 2.0 * center + right
        if abs(denominator) > 1e-12:
            offset = float(np.clip(0.5 * (left - right) / denominator, -0.5, 0.5))
            peak_frequency += offset * (sample_rate / windowed.size)

    noise = magnitudes[candidates]
    exclusion = np.abs(candidates - peak_index) > 1
    noise_floor = float(np.median(noise[exclusion])) if np.any(exclusion) else float(np.median(noise))
    peak_magnitude = float(magnitudes[peak_index])
    snr_db = 20.0 * np.log10(peak_magnitude / max(noise_floor, 1e-12))
    valid = bool(snr_db >= min_snr_db)

    return {
        "valid": valid,
        "frequency_hz": peak_frequency if valid else None,
        "sample_rate_hz": sample_rate,
        "duration_s": duration,
        "snr_db": float(snr_db),
        "reason": "" if valid else f"Puncak spektrum belum cukup jelas (SNR {snr_db:.1f} dB).",
    }


def calculate_drift_ratio(displacement_mm: float, structure_height_mm: float) -> Dict[str, object]:
    """Return story-drift ratio from measured lateral displacement and height."""
    try:
        displacement = float(displacement_mm)
        height = float(structure_height_mm)
    except (TypeError, ValueError):
        return {"valid": False, "drift_ratio_pct": None, "reason": "Input drift tidak numerik."}

    if not np.isfinite(displacement) or not np.isfinite(height) or height <= 0.0:
        return {"valid": False, "drift_ratio_pct": None, "reason": "Tinggi miniatur harus lebih dari 0 mm."}

    return {
        "valid": True,
        "drift_ratio_pct": abs(displacement) / height * 100.0,
        "reason": "",
    }
