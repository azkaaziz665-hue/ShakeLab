"""
calibration.py — Modul Kalibrasi Homography & Skala Dinamis (ShakeLab)
========================================================================
Menyediakan transformasi perspektif (homography-based) untuk konversi koordinat
piksel kamera ke koordinat dunia nyata (milimeter), skala dinamis per-marker
sebagai cross-check, dan validasi ground-truth.

Fitur Utama:
  1. Homography-Based Conversion (cv2.findHomography + cv2.perspectiveTransform)
  2. Dynamic Scale Per-Marker (cross-check vs homography)
  3. Ground-Truth Validation (error percentage)
  4. Save / Load matriks homography (JSON & .npy)
  5. Auto-generate titik kalibrasi dari sudut marker ArUco

Integrasi:
  - Impor modul ini dari gui_app.py untuk menggantikan perkalian skalar tunggal.
  - Format output CSV/Excel (disp_x_mm, disp_y_mm, dsb.) tetap identik.
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# =====================================================================
# 1. HOMOGRAPHY COMPUTATION
# =====================================================================

def compute_homography(
    pts_src_px: np.ndarray,
    pts_dst_mm: np.ndarray,
    method: int = cv2.RANSAC,
    reproj_threshold: float = 3.0,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Menghitung matriks homography 3x3 dari pasangan titik piksel → mm.

    Args:
        pts_src_px: Array Nx2 koordinat piksel sumber (citra kamera).
        pts_dst_mm: Array Nx2 koordinat fisik tujuan (dunia nyata dalam mm).
        method: Metode estimasi (cv2.RANSAC, cv2.LMEDS, atau 0 untuk least-squares murni).
        reproj_threshold: Batas toleransi reproyeksi RANSAC (piksel).

    Returns:
        Tuple (H, mask):
          - H: Matriks homography 3x3 (float64), atau None jika gagal.
          - mask: Mask inlier Nx1 (uint8), atau None jika gagal.

    Raises:
        ValueError: Jika jumlah titik < 4 atau dimensi tidak cocok.
    """
    pts_src = np.asarray(pts_src_px, dtype=np.float64)
    pts_dst = np.asarray(pts_dst_mm, dtype=np.float64)

    if pts_src.ndim == 1:
        pts_src = pts_src.reshape(-1, 2)
    if pts_dst.ndim == 1:
        pts_dst = pts_dst.reshape(-1, 2)

    if pts_src.shape[0] < 4:
        raise ValueError(
            f"Dibutuhkan minimal 4 pasang titik korespondensi, diterima {pts_src.shape[0]}."
        )
    if pts_src.shape != pts_dst.shape:
        raise ValueError(
            f"Dimensi titik sumber {pts_src.shape} tidak cocok dengan tujuan {pts_dst.shape}."
        )

    H, mask = cv2.findHomography(pts_src, pts_dst, method, reproj_threshold)
    if H is None:
        logger.error("cv2.findHomography gagal menghitung matriks H.")
        return None, None

    return H, mask


# =====================================================================
# 2. PIXEL TO MM CONVERSION (HOMOGRAPHY)
# =====================================================================

def pixel_to_mm(
    points_px: Union[Tuple[float, float], List, np.ndarray],
    H: np.ndarray,
) -> np.ndarray:
    """Mengubah koordinat piksel ke milimeter menggunakan matriks homography.

    Args:
        points_px: Satu titik (x, y), list of (x, y), atau array Nx2 piksel.
        H: Matriks homography 3x3.

    Returns:
        Array Nx2 koordinat dalam milimeter.

    Raises:
        ValueError: Jika H bukan 3x3 atau input tidak valid.
    """
    H = np.asarray(H, dtype=np.float64)
    if H.shape != (3, 3):
        raise ValueError(f"Matriks homography harus 3x3, diterima {H.shape}.")

    pts = np.asarray(points_px, dtype=np.float64)

    # Normalisasi dimensi: pastikan shape (N, 1, 2) untuk cv2.perspectiveTransform
    if pts.ndim == 1:
        # Single point (x, y)
        pts = pts.reshape(1, 1, 2)
    elif pts.ndim == 2:
        # Array Nx2
        pts = pts.reshape(-1, 1, 2)
    elif pts.ndim == 3:
        # Sudah (N, 1, 2)
        pass
    else:
        raise ValueError(f"Dimensi input tidak valid: {pts.ndim}D, harap (x,y), Nx2, atau Nx1x2.")

    transformed = cv2.perspectiveTransform(pts, H)
    return transformed.reshape(-1, 2)


# =====================================================================
# 3. SAVE / LOAD HOMOGRAPHY
# =====================================================================

def save_homography(
    H: np.ndarray,
    filepath: str = "homography_matrix.json",
    metadata: Optional[Dict] = None,
) -> str:
    """Simpan matriks homography ke file JSON atau .npy.

    Args:
        H: Matriks homography 3x3.
        filepath: Path file tujuan (.json atau .npy).
        metadata: Dict opsional metadata tambahan (titik kalibrasi, dsb.).

    Returns:
        Path absolut file yang tersimpan.
    """
    filepath = os.path.abspath(filepath)

    if filepath.endswith(".npy"):
        np.save(filepath, H)
        logger.info(f"Matriks homography disimpan (npy): {filepath}")
    else:
        payload = {
            "homography_matrix": H.tolist(),
            "shape": list(H.shape),
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if metadata:
            payload["metadata"] = metadata
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info(f"Matriks homography disimpan (json): {filepath}")

    return filepath


def load_homography(
    filepath: str = "homography_matrix.json",
    return_metadata: bool = False,
) -> Union[Optional[np.ndarray], Tuple[Optional[np.ndarray], Dict]]:
    """Muat matriks homography dari file JSON atau .npy.

    Args:
        filepath: Path file sumber.
        return_metadata: Jika True, mengembalikan tuple (H, metadata).

    Returns:
        Matriks homography 3x3 (float64) atau tuple (H, metadata).
    """
    filepath = os.path.abspath(filepath)
    if not os.path.isfile(filepath):
        logger.warning(f"File homography tidak ditemukan: {filepath}")
        return (None, {}) if return_metadata else None

    metadata = {}
    try:
        if filepath.endswith(".npy"):
            H = np.load(filepath)
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                payload = json.load(f)
            H = np.array(payload["homography_matrix"], dtype=np.float64)
            metadata = payload.get("metadata", {})

        if H.shape != (3, 3):
            logger.error(f"Shape matriks tidak valid: {H.shape}, diharapkan (3, 3).")
            return (None, {}) if return_metadata else None

        logger.info(f"Matriks homography dimuat dari: {filepath}")
        return (H, metadata) if return_metadata else H
    except Exception as e:
        logger.error(f"Gagal memuat file homography '{filepath}': {e}")
        return (None, {}) if return_metadata else None


# =====================================================================
# 4. DYNAMIC SCALE PER-MARKER (CROSS-CHECK)
# =====================================================================

def compute_marker_dynamic_scale(
    marker_input: Union[float, int, np.ndarray, List],
    L_marker_mm: float = 40.0,
    **kwargs,
) -> float:
    """Hitung skala dinamis lokal dari ukuran marker yang terdeteksi di frame.

    Args:
        marker_input: Panjang sisi marker dalam piksel (float), ATAU array 4 sudut marker (Nx2).
        L_marker_mm: Panjang sisi fisik marker cetak (mm).

    Returns:
        Skala dinamis (mm/px).
    """
    # Dukung alias keyword argument jika ada
    if "marker_size_mm" in kwargs:
        L_marker_mm = float(kwargs["marker_size_mm"])

    if isinstance(marker_input, (int, float)):
        s_px = float(marker_input)
    else:
        # Jika berupa koordinat 4 sudut
        pts = np.asarray(marker_input, dtype=np.float64).reshape(-1, 2)
        if len(pts) >= 4:
            # Rata-rata 4 sisi
            s0 = np.linalg.norm(pts[1] - pts[0])
            s1 = np.linalg.norm(pts[2] - pts[1])
            s2 = np.linalg.norm(pts[3] - pts[2])
            s3 = np.linalg.norm(pts[0] - pts[3])
            s_px = float((s0 + s1 + s2 + s3) / 4.0)
        else:
            s_px = 0.0

    if s_px <= 0:
        return 0.0
    return float(L_marker_mm / s_px)


def cross_check_homography_vs_dynamic(
    H: Optional[np.ndarray] = None,
    marker_center_px: Optional[Tuple[float, float]] = None,
    s_marker_px: Optional[float] = None,
    L_marker_mm: float = 40.0,
    threshold_pct: float = 5.0,
    **kwargs,
) -> Dict:
    """Bandingkan estimasi homography dengan skala dinamis marker.

    Mendukung dua mode pemanggilan:
      1. Berdasarkan matriks H, titik pusat marker, dan ukuran marker piksel.
      2. Berdasarkan perbandingan perpindahan langsung (disp_homography_mm, disp_px, dynamic_scale_mm_px).

    Returns:
        Dict dengan status valid/passed dan nilai deviasi.
    """
    # Mode 2: Perbandingan langsung dari displacement
    if "disp_homography_mm" in kwargs and ("dynamic_scale_mm_px" in kwargs or "disp_dynamic_mm" in kwargs):
        disp_h = float(kwargs["disp_homography_mm"])
        tol = float(kwargs.get("tolerance_percent", kwargs.get("tolerance_pct", threshold_pct)))
        
        if "disp_dynamic_mm" in kwargs:
            disp_d = float(kwargs["disp_dynamic_mm"])
        else:
            disp_px = float(kwargs.get("disp_px", 0.0))
            scale_d = float(kwargs.get("dynamic_scale_mm_px", 0.0))
            disp_d = disp_px * scale_d

        if disp_d > 0:
            dev_pct = abs(disp_h - disp_d) / disp_d * 100.0
        elif disp_h == 0 and disp_d == 0:
            dev_pct = 0.0
        else:
            dev_pct = float("inf")

        valid = dev_pct <= tol
        return {
            "scale_homography": disp_h,
            "scale_dynamic": disp_d,
            "deviation_pct": dev_pct,
            "discrepancy_percent": dev_pct,
            "passed": valid,
            "valid": valid,
            "warning_msg": "" if valid else f"Discrepancy {dev_pct:.2f}% exceeds tolerance {tol:.1f}%",
        }

    # Mode 1: Berdasarkan matriks H dan probe point
    if H is None or marker_center_px is None or s_marker_px is None:
        return {
            "scale_homography": 0.0,
            "scale_dynamic": 0.0,
            "deviation_pct": float("inf"),
            "discrepancy_percent": float("inf"),
            "passed": False,
            "valid": False,
            "warning_msg": "Parameter tidak lengkap untuk cross check.",
        }

    cx, cy = float(marker_center_px[0]), float(marker_center_px[1])
    probe_pts = np.array([
        [cx - 0.5, cy],
        [cx + 0.5, cy],
    ], dtype=np.float64)
    transformed = pixel_to_mm(probe_pts, H)
    dx_mm = float(np.linalg.norm(transformed[1] - transformed[0]))
    scale_h = dx_mm

    scale_d = compute_marker_dynamic_scale(s_marker_px, L_marker_mm)

    if scale_d > 0:
        deviation_pct = abs(scale_h - scale_d) / scale_d * 100.0
    else:
        deviation_pct = float("inf")

    passed = deviation_pct <= threshold_pct
    warning_msg = ""
    if not passed:
        warning_msg = (
            f"Deviasi skala {deviation_pct:.2f}% melebihi batas {threshold_pct:.1f}%: "
            f"Homography={scale_h:.6f} mm/px vs Marker Dinamis={scale_d:.6f} mm/px"
        )
        logger.debug(warning_msg)

    return {
        "scale_homography": scale_h,
        "scale_dynamic": scale_d,
        "deviation_pct": deviation_pct,
        "discrepancy_percent": deviation_pct,
        "passed": passed,
        "valid": passed,
        "warning_msg": warning_msg,
    }


# =====================================================================
# 5. GROUND-TRUTH VALIDATION
# =====================================================================

def test_calibration(
    jarak_diketahui_mm_or_H: Union[float, np.ndarray],
    hasil_ukur_mm_or_pt_a: Union[float, Tuple[float, float]],
    tolerance_pct: float = 5.0,
    **kwargs,
) -> Dict:
    """Validasi akurasi kalibrasi terhadap pengukuran ground-truth.

    Mendukung dua pemanggilan:
      1. test_calibration(jarak_diketahui_mm, hasil_ukur_mm, tolerance_pct)
      2. test_calibration(H, pt_a_px, pt_b_px, ground_truth_mm, tolerance_pct=5.0)

    Returns:
        Dict berisi 'error_mm', 'error_pct', 'passed', dsb.
    """
    # Jika parameter pertama adalah matriks H
    if isinstance(jarak_diketahui_mm_or_H, np.ndarray) and jarak_diketahui_mm_or_H.shape == (3, 3):
        H = jarak_diketahui_mm_or_H
        pt_a_px = hasil_ukur_mm_or_pt_a
        pt_b_px = kwargs.get("pt_b") if "pt_b" in kwargs else tolerance_pct
        ground_truth = float(kwargs.get("ground_truth_mm", kwargs.get("ground_truth", 0.0)))
        tol = float(kwargs.get("tolerance_percent", kwargs.get("tolerance_pct", 5.0)))

        pts_transformed = pixel_to_mm([pt_a_px, pt_b_px], H)
        measured_dist = float(np.linalg.norm(pts_transformed[1] - pts_transformed[0]))
        
        if ground_truth > 0:
            err_mm = abs(measured_dist - ground_truth)
            err_pct = (err_mm / ground_truth) * 100.0
        else:
            err_mm = 0.0
            err_pct = 0.0

        passed = err_pct <= tol
        return {
            "error_mm": err_mm,
            "error_pct": err_pct,
            "error_percent": err_pct,
            "measured_distance_mm": measured_dist,
            "ground_truth_mm": ground_truth,
            "passed": passed,
            "message": f"Measured: {measured_dist:.2f} mm, Truth: {ground_truth:.2f} mm, Err: {err_pct:.2f}%",
        }

    jarak_diketahui_mm = float(jarak_diketahui_mm_or_H)
    hasil_ukur_mm = float(hasil_ukur_mm_or_pt_a)
    tol = float(kwargs.get("tolerance_percent", tolerance_pct))

    if jarak_diketahui_mm <= 0:
        return {
            "error_mm": float("nan"),
            "error_pct": float("nan"),
            "error_percent": float("nan"),
            "measured_distance_mm": hasil_ukur_mm,
            "ground_truth_mm": jarak_diketahui_mm,
            "passed": False,
            "message": "Jarak ground-truth harus > 0.",
        }

    error_mm = abs(hasil_ukur_mm - jarak_diketahui_mm)
    error_pct = (error_mm / jarak_diketahui_mm) * 100.0
    passed = error_pct <= tol

    msg = (
        f"Validasi Ground-Truth: "
        f"Diketahui={jarak_diketahui_mm:.2f} mm, "
        f"Terukur={hasil_ukur_mm:.2f} mm, "
        f"Error={error_mm:.2f} mm ({error_pct:.2f}%), "
        f"Batas={tol:.1f}% -> {'LULUS' if passed else 'GAGAL'}"
    )

    return {
        "error_mm": error_mm,
        "error_pct": error_pct,
        "error_percent": error_pct,
        "measured_distance_mm": hasil_ukur_mm,
        "ground_truth_mm": jarak_diketahui_mm,
        "passed": passed,
        "message": msg,
    }


# =====================================================================
# 6. AUTO-GENERATE CALIBRATION POINTS FROM ARUCO CORNERS
# =====================================================================

def generate_aruco_calibration_points(
    corners_ground_px: np.ndarray,
    corners_top_px: np.ndarray,
    L_marker_mm: float = 40.0,
    H_fisik_mm: float = 350.0,
    top_offset_x_mm: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Membentuk pasangan titik korespondensi piksel ↔ mm dari ArUco corners.

    Menggunakan 4 sudut marker Ground + 4 sudut marker Top = 8 pasang titik.
    Titik dunia (mm) diatur dengan origin di pusat marker Ground:
      - Ground marker: kotak L×L di y=0
      - Top marker: kotak L×L di y = -H_fisik (negatif karena ke atas di dunia nyata)

    Args:
        corners_ground_px: Array 4x2 sudut marker Ground dalam piksel.
        corners_top_px: Array 4x2 sudut marker Top dalam piksel.
        L_marker_mm: Panjang sisi marker fisik (mm).
        H_fisik_mm: Jarak vertikal fisik dari pusat Ground ke pusat Top (mm).

    Returns:
        Tuple (pts_src_px, pts_dst_mm):
          - pts_src_px: Array 8x2 koordinat piksel.
          - pts_dst_mm: Array 8x2 koordinat dunia (mm).
    """
    corners_g = np.asarray(corners_ground_px, dtype=np.float64).reshape(4, 2)
    corners_t = np.asarray(corners_top_px, dtype=np.float64).reshape(4, 2)

    half_L = L_marker_mm / 2.0

    # Pusat Ground di dunia = (0, 0), marker bujur sangkar
    # Urutan sudut ArUco: top-left, top-right, bottom-right, bottom-left
    ground_world = np.array([
        [-half_L, -half_L],  # sudut kiri atas
        [+half_L, -half_L],  # sudut kanan atas
        [+half_L, +half_L],  # sudut kanan bawah
        [-half_L, +half_L],  # sudut kiri bawah
    ], dtype=np.float64)

    # Pusat Top di dunia = (offset_x, -H_fisik)
    # offset_x dihitung relatif dari pusat Ground
    # Do not derive a physical X offset from image pixels: camera perspective
    # would otherwise couple the physical X and Y axes.
    offset_x_mm = float(top_offset_x_mm)
    # Top berada di atas Ground → y negatif
    top_center_y_mm = -H_fisik_mm

    top_world = np.array([
        [offset_x_mm - half_L, top_center_y_mm - half_L],
        [offset_x_mm + half_L, top_center_y_mm - half_L],
        [offset_x_mm + half_L, top_center_y_mm + half_L],
        [offset_x_mm - half_L, top_center_y_mm + half_L],
    ], dtype=np.float64)

    pts_src_px = np.vstack([corners_g, corners_t])
    pts_dst_mm = np.vstack([ground_world, top_world])

    return pts_src_px, pts_dst_mm
