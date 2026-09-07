"""
Aplikasi Uji Gempa Miniatur Gedung - GUI PyQt6
===============================================
Aplikasi desktop modern untuk melacak displacement miniatur gedung berbasis
OpenCV & ArUco Marker secara realtime dengan grafik live, kalibrasi interaktif,
analisis drift & frekuensi, serta ekspor otomatis ke Excel/CSV/PNG/TXT.

Desain antarmuka dirancang mengikuti konsep Dark Laboratory Command Center:
Earthquake Shaking Table Tracker v2.4.
"""

import sys
import os
import time
import csv
import shutil
from collections import deque


def get_resource_path(relative_name: str) -> str:
    """Kembalikan path absolut ke file resource.
    Bekerja baik saat dijalankan sebagai skrip .py maupun sebagai .exe (PyInstaller).
    """
    if hasattr(sys, "_MEIPASS"):
        # Mode .exe PyInstaller — file ada di folder temp _MEIPASS
        return os.path.join(sys._MEIPASS, relative_name)
    # Mode skrip biasa — ambil dari direktori yang sama dengan gui_app.py
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_name)


import cv2
import numpy as np

# Matplotlib untuk menyimpan grafik PNG akhir (backend non-interaktif murni)
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

# Openpyxl untuk ekspor Excel dengan format tabel bergaris
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QPoint, QSize, QRect, QRectF, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QPainter, QPen, QColor, QBrush, QPalette
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFormLayout, QGroupBox, QPushButton, QLabel,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QRadioButton,
    QButtonGroup, QCheckBox, QDialog, QMessageBox, QFileDialog,
    QProgressBar, QSplitter, QFrame, QScrollArea, QSizePolicy
)

import pyqtgraph as pg


def ensure_arrow_icons():
    """Memastikan file ikon panah up & down tersedia untuk styling QSpinBox."""
    from PyQt6.QtGui import QPolygon
    up_path = get_resource_path("arrow_up.png")
    down_path = get_resource_path("arrow_down.png")
    if not os.path.exists(up_path):
        pm = QPixmap(10, 6)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor('#ffffff'))
        p.setPen(QColor('#ffffff'))
        p.drawPolygon(QPolygon([QPoint(0, 5), QPoint(5, 0), QPoint(10, 5)]))
        p.end()
        try:
            pm.save(up_path)
        except Exception:
            pass

    if not os.path.exists(down_path):
        pm = QPixmap(10, 6)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor('#ffffff'))
        p.setPen(QColor('#ffffff'))
        p.drawPolygon(QPolygon([QPoint(0, 1), QPoint(5, 6), QPoint(10, 1)]))
        p.end()
        try:
            pm.save(down_path)
        except Exception:
            pass

ensure_arrow_icons()


def global_exception_handler(exctype, value, tb):
    """Mencegah aplikasi keluar diam-diam jika terjadi unhandled error pada event loop PyQt."""
    import traceback
    err_text = "".join(traceback.format_exception(exctype, value, tb))
    print(f"[UNHANDLED EXCEPTION]: {err_text}", file=sys.stderr)
    try:
        QMessageBox.critical(
            None, "Peringatan Sistem",
            f"Terjadi kesalahan pada aplikasi:\n{value}\n\nDetail:\n{err_text[:300]}..."
        )
    except Exception:
        pass

sys.excepthook = global_exception_handler



# =====================================================================
# STYLING MODERN LIGHT THEME - LABORATORY COMMAND CENTER (QSS)
# Palet Terang: Putih/Abu Muda dengan Aksen Biru & Hijau
# =====================================================================
MODERN_STYLE = """
/* Base Global Font & Text */
QWidget {
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    color: #1e293b;
}

QMainWindow {
    background-color: #f0f4f8;
    color: #1e293b;
}

/* Dialogs, Message Boxes & Popups */
QDialog, QMessageBox, QFileDialog {
    background-color: #ffffff;
    color: #0f172a;
}
QMessageBox QLabel {
    color: #0f172a;
    font-size: 12px;
    background-color: transparent;
}
QMessageBox QPushButton {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 20px;
    font-weight: 700;
    font-size: 12px;
    min-width: 75px;
    min-height: 26px;
}
QMessageBox QPushButton:hover {
    background-color: #0369a1;
}
QMessageBox QPushButton:pressed {
    background-color: #075985;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    width: 6px;
    background: #e2e8f0;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #94a3b8;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #0ea5e9;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Header & Footer Containers */
QFrame#topHeader {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}
QFrame#footerBar {
    background-color: #ffffff;
    border-top: 1px solid #e2e8f0;
}

/* Cards & Section Boxes */
QFrame#sidebarCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 10px;
}
QFrame#subCard {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px;
}
QFrame#videoContainer {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
QFrame#scopeContainer {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
QFrame#metricCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px;
}

/* Inputs & Form Controls */
QLineEdit, QComboBox {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 8px;
    color: #1e293b;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-weight: 500;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #0ea5e9;
    background-color: #f0f9ff;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    color: #1e293b;
    selection-background-color: #e0f2fe;
    selection-color: #0c4a6e;
}

/* SpinBox & DoubleSpinBox (Tombol Up & Down warna kontras terbedakan) */
QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 8px;
    padding-right: 28px;
    color: #0f172a;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-weight: 600;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #0284c7;
    background-color: #f0f9ff;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 24px;
    background-color: #0284c7;
    border-left: 1px solid #0369a1;
    border-bottom: 1px solid #0369a1;
    border-top-right-radius: 5px;
    margin-top: 1px;
    margin-right: 1px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background-color: #0369a1;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {
    background-color: #075985;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("ARROW_UP_URL");
    width: 10px;
    height: 6px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 24px;
    background-color: #0284c7;
    border-left: 1px solid #0369a1;
    border-bottom-right-radius: 5px;
    margin-bottom: 1px;
    margin-right: 1px;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #0369a1;
}
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #075985;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("ARROW_DOWN_URL");
    width: 10px;
    height: 6px;
}

/* PushButtons */
QPushButton {
    background-color: #f1f5f9;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #e0f2fe;
    border-color: #0ea5e9;
    color: #0c4a6e;
}
QPushButton:pressed {
    background-color: #bae6fd;
}
QPushButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* Primary Action Buttons */
QPushButton#btnStart {
    background-color: #10b981;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 700;
    font-size: 12px;
}
QPushButton#btnStart:hover {
    background-color: #059669;
}
QPushButton#btnStart:disabled {
    background-color: #d1fae5;
    color: #6ee7b7;
}

QPushButton#btnStop {
    background-color: #fff1f2;
    color: #e11d48;
    border: 1px solid #fecdd3;
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 700;
    font-size: 12px;
}
QPushButton#btnStop:hover {
    background-color: #ffe4e6;
    border-color: #fb7185;
}
QPushButton#btnStop:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton#btnStreamLink {
    background-color: #f0fdf4;
    border: 1px solid #86efac;
    color: #16a34a;
    border-radius: 6px;
    font-weight: 600;
    padding: 7px;
}
QPushButton#btnStreamLink:hover {
    background-color: #dcfce7;
    border-color: #4ade80;
}

QPushButton#btnSegmentActive {
    background-color: #e0f2fe;
    color: #0369a1;
    border: 1px solid #7dd3fc;
    border-radius: 5px;
    font-weight: 600;
}
QPushButton#btnSegmentInactive {
    background-color: transparent;
    color: #94a3b8;
    border: none;
    border-radius: 5px;
}
QPushButton#btnSegmentInactive:hover {
    color: #334155;
    background-color: #f1f5f9;
}

/* Progress Bar */
QProgressBar {
    background-color: #e2e8f0;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: right;
}
QProgressBar::chunk {
    background-color: #10b981;
    border-radius: 3px;
}
""".replace("ARROW_UP_URL", get_resource_path("arrow_up.png").replace("\\", "/")) \
   .replace("ARROW_DOWN_URL", get_resource_path("arrow_down.png").replace("\\", "/"))


# =====================================================================
# FUNGSI EKSPOR DATA (EXCEL, TXT, PNG)
# =====================================================================
def export_to_excel(filename, headers, units, rows):
    """Simpan data ke file Excel (.xlsx) dengan tabel bergaris rapi."""
    if not HAS_OPENPYXL:
        return False
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data Gempa"

        thin_border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )
        header_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
        header_font = Font(name='Calibri', size=11, bold=True)
        unit_font = Font(name='Calibri', size=10, italic=True, color='333333')
        data_font = Font(name='Calibri', size=11)

        # Baris 1: Header
        for col_idx, col_name in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border

        # Baris 2: Satuan
        for col_idx, unit in enumerate(units, 1):
            cell = ws.cell(row=2, column=col_idx, value=unit)
            cell.font = unit_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border

        # Baris 3+: Data
        for r_idx, row_data in enumerate(rows, 3):
            for c_idx, val in enumerate(row_data, 1):
                try:
                    num_val = float(val) if '.' in str(val) else int(val)
                except (ValueError, TypeError):
                    num_val = val

                cell = ws.cell(row=r_idx, column=c_idx, value=num_val)
                cell.font = data_font
                cell.border = thin_border
                if isinstance(num_val, (int, float)):
                    cell.alignment = Alignment(horizontal='right', vertical='center')
                else:
                    cell.alignment = Alignment(horizontal='center', vertical='center')

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        ws.views.sheetView[0].showGridLines = True
        wb.save(filename)
        return True
    except Exception as e:
        print(f"Gagal simpan Excel: {e}")
        return False


def save_txt_table(filename, headers, rows, pixel_to_mm, frame_count):
    """Menyimpan tabel format ASCII bergaris ke file teks."""
    try:
        col_widths = [len(h) for h in headers]
        for r in rows:
            for i, val in enumerate(r):
                col_widths[i] = max(col_widths[i], len(str(val)))

        sep_line = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"

        with open(filename, "w", encoding="utf-8") as tf:
            tf.write("HASIL SIMULASI UJI GEMPA - DATA DISPLACEMENT\n")
            tf.write(f"Kalibrasi: {pixel_to_mm} mm/px | Total Frame: {frame_count}\n\n")
            tf.write(sep_line + "\n")
            hdr_str = "|" + "|".join([f" {headers[i]:^{col_widths[i]}} " for i in range(len(headers))]) + "|"
            tf.write(hdr_str + "\n")
            tf.write(sep_line + "\n")
            for r in rows:
                row_str = "|" + "|".join([f" {str(r[i]):>{col_widths[i]}} " if i < len(r)-1 else f" {str(r[i]):^{col_widths[i]}} " for i in range(len(r))]) + "|"
                tf.write(row_str + "\n")
            tf.write(sep_line + "\n")
        return True
    except Exception as e:
        print(f"Gagal simpan TXT: {e}")
        return False


def save_png_plot(filename, t_all, x_all, y_all, z_all, unit_label):
    """Menyimpan grafik plot pergeseran gedung ke gambar PNG resolusi tinggi secara thread-safe (3 Sumbu: X, Y, Z)."""
    if len(t_all) < 2:
        return False
    try:
        fig = Figure(figsize=(11, 8))
        canvas = FigureCanvasAgg(fig)
        fig.patch.set_facecolor('#ffffff')
        fig.suptitle("ShakeLab — Dynamic 3D Structural Response (Lateral, Axial & Out-of-Plane)",
                     fontsize=13, fontweight="bold", color="#0f172a")

        # Jika data z_all kosong atau panjangnya tidak sama, buat array nol
        if not z_all or len(z_all) != len(t_all):
            z_all = [0.0] * len(t_all)

        ax = fig.subplots(3, 1, sharex=True)
        for a in ax:
            a.set_facecolor('#f8fafc')
            a.grid(True, color='#e2e8f0', linestyle='--', alpha=0.8)
            a.tick_params(colors='#475569')
            for spine in a.spines.values():
                spine.set_color('#cbd5e1')

        # Sumbu X
        ax[0].plot(t_all, x_all, color="#0284c7", linewidth=1.5, label="ΔX (Lateral Sway)")
        ax[0].set_ylabel(f"ΔX ({unit_label})", color='#0284c7', fontweight='bold')
        ax[0].axhline(0, color="#0284c7", linewidth=0.8, linestyle="--", alpha=0.5)

        # Sumbu Y
        ax[1].plot(t_all, y_all, color="#9333ea", linewidth=1.5, label="ΔY (Axial Drop)")
        ax[1].set_ylabel(f"ΔY ({unit_label})", color='#9333ea', fontweight='bold')
        ax[1].axhline(0, color="#9333ea", linewidth=0.8, linestyle="--", alpha=0.5)

        # Sumbu Z
        ax[2].plot(t_all, z_all, color="#ea580c", linewidth=1.5, label="ΔZ (Out-of-Plane)")
        ax[2].set_ylabel(f"ΔZ ({unit_label})", color='#ea580c', fontweight='bold')
        ax[2].set_xlabel("Waktu (detik)", color='#0f172a')
        ax[2].axhline(0, color="#ea580c", linewidth=0.8, linestyle="--", alpha=0.5)

        series_data = [
            (ax[0], x_all, '#0284c7', 'ΔX Lateral'),
            (ax[1], y_all, '#9333ea', 'ΔY Axial'),
            (ax[2], z_all, '#ea580c', 'ΔZ Out-of-Plane')
        ]

        for ax_s, vals, c, name in series_data:
            arr = np.array(vals)
            txt = f"{name} | Max: {arr.max():+.2f} | Min: {arr.min():+.2f} | RMS: {np.sqrt(np.mean(arr**2)):.2f} {unit_label}"
            ax_s.annotate(txt, xy=(0.02, 0.90), xycoords="axes fraction",
                          fontsize=8.5, va="top", color=c,
                          bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec="#cbd5e1", alpha=0.95))

        fig.tight_layout()
        canvas.print_figure(filename, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        return True
    except Exception as e:
        print(f"Gagal simpan PNG: {e}")
        return False


# =====================================================================
# DIALOG KALIBRASI INTERAKTIF (BEBAS GLITCH RESIZE)
# =====================================================================
class CalibrationCanvas(QWidget):
    """Widget kanvas untuk mengklik 2 titik pada penggaris."""
    pointsChanged = pyqtSignal(list, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.original_pixmap = None
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #070e1d; border: 1px solid #2a364d; border-radius: 8px;")

    def set_frame(self, cv_img):
        h, w, ch = cv_img.shape
        bytes_per_line = ch * w
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.original_pixmap = QPixmap.fromImage(q_img)
        self.points = []
        self.update()

    def reset_points(self):
        self.points = []
        self.update()
        self.pointsChanged.emit([], 0.0)

    def _get_draw_params(self):
        if self.original_pixmap is None or self.original_pixmap.width() == 0 or self.original_pixmap.height() == 0:
            return 1.0, 0, 0, 0, 0
        lbl_w, lbl_h = self.width(), self.height()
        pm_w, pm_h = self.original_pixmap.width(), self.original_pixmap.height()
        scale = min(lbl_w / pm_w, lbl_h / pm_h)
        disp_w = pm_w * scale
        disp_h = pm_h * scale
        offset_x = (lbl_w - disp_w) / 2.0
        offset_y = (lbl_h - disp_h) / 2.0
        return scale, offset_x, offset_y, disp_w, disp_h

    def mousePressEvent(self, event):
        if self.original_pixmap is None:
            return
        if len(self.points) >= 2:
            self.points = []

        scale, offset_x, offset_y, disp_w, disp_h = self._get_draw_params()
        pos = event.position()
        mx, my = pos.x(), pos.y()

        if offset_x <= mx <= offset_x + disp_w and offset_y <= my <= offset_y + disp_h:
            orig_x = (mx - offset_x) / scale
            orig_y = (my - offset_y) / scale
            self.points.append((orig_x, orig_y))
            
            dist_px = 0.0
            if len(self.points) == 2:
                p1, p2 = np.array(self.points[0]), np.array(self.points[1])
                dist_px = float(np.linalg.norm(p2 - p1))

            self.update()
            self.pointsChanged.emit(self.points, dist_px)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.fillRect(self.rect(), QColor("#070e1d"))

        if self.original_pixmap is None:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Tidak ada frame gambar kamera.")
            return

        scale, offset_x, offset_y, disp_w, disp_h = self._get_draw_params()

        target_rect = QRectF(offset_x, offset_y, disp_w, disp_h)
        painter.drawPixmap(target_rect.toRect(), self.original_pixmap)

        for i, (orig_x, orig_y) in enumerate(self.points):
            sx = int(offset_x + orig_x * scale)
            sy = int(offset_y + orig_y * scale)

            painter.setBrush(QColor(52, 211, 153))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(QPoint(sx, sy), 7, 7)
            painter.setFont(QFont("JetBrains Mono", 10, QFont.Weight.Bold))
            painter.setPen(QColor(52, 211, 153))
            painter.drawText(sx + 10, sy - 10, f"P{i+1}")

        if len(self.points) == 2:
            s1_x = int(offset_x + self.points[0][0] * scale)
            s1_y = int(offset_y + self.points[0][1] * scale)
            s2_x = int(offset_x + self.points[1][0] * scale)
            s2_y = int(offset_y + self.points[1][1] * scale)

            painter.setPen(QPen(QColor(56, 189, 248), 3, Qt.PenStyle.DashLine))
            painter.drawLine(QPoint(s1_x, s1_y), QPoint(s2_x, s2_y))

            dist_px = float(np.linalg.norm(np.array(self.points[1]) - np.array(self.points[0])))
            mid_x = (s1_x + s2_x) // 2
            mid_y = (s1_y + s2_y) // 2 - 12
            painter.setFont(QFont("JetBrains Mono", 11, QFont.Weight.Bold))
            painter.setPen(QColor(56, 189, 248))
            painter.drawText(mid_x, mid_y, f"{dist_px:.1f} px")


class CalibrationDialog(QDialog):
    """Dialog kalibrasi rasio pixel ke millimeter (mm/px)."""
    def __init__(self, current_frame, current_val=0.265, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scale Calibration — Ruler Tool")
        self.resize(850, 600)
        self.setStyleSheet(MODERN_STYLE)

        self.calculated_scale = current_val
        self.dist_px = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info_card = QFrame()
        info_card.setObjectName("sidebarCard")
        info_lay = QVBoxLayout(info_card)
        info_label = QLabel(
            "<b>Instruksi Kalibrasi Skala:</b><br>"
            "1. Klik <b>Titik 1 (P1)</b> pada penanda awal penggaris fisik di gambar.<br>"
            "2. Klik <b>Titik 2 (P2)</b> pada penanda akhir penggaris fisik.<br>"
            "3. Masukkan jarak fisik asli (dalam mm) di bawah, lalu klik 'Terapkan'."
        )
        info_label.setStyleSheet("color: #64748b; font-size: 12px;")
        info_lay.addWidget(info_label)
        layout.addWidget(info_card)

        self.canvas = CalibrationCanvas(self)
        self.canvas.set_frame(current_frame)
        self.canvas.pointsChanged.connect(self.on_points_changed)
        layout.addWidget(self.canvas, stretch=1)

        calc_card = QFrame()
        calc_card.setObjectName("sidebarCard")
        calc_layout = QGridLayout(calc_card)

        calc_layout.addWidget(QLabel("Jarak Terukur di Layar:"), 0, 0)
        self.lbl_px = QLabel("0.0 piksel")
        self.lbl_px.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: bold; color: #0284c7;")
        calc_layout.addWidget(self.lbl_px, 0, 1)

        calc_layout.addWidget(QLabel("Jarak Fisik Penggaris:"), 0, 2)
        self.spin_mm = QDoubleSpinBox()
        self.spin_mm.setRange(1.0, 10000.0)
        self.spin_mm.setValue(100.0)
        self.spin_mm.setSuffix(" mm")
        self.spin_mm.setMinimumHeight(32)
        self.spin_mm.valueChanged.connect(self.compute_scale)
        calc_layout.addWidget(self.spin_mm, 0, 3)

        calc_layout.addWidget(QLabel("Hasil Skala (PIXEL_TO_MM):"), 1, 0)
        self.lbl_result = QLabel(f"{current_val:.6f} mm/px")
        self.lbl_result.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 14px; font-weight: bold; color: #059669;")
        calc_layout.addWidget(self.lbl_result, 1, 1, 1, 3)

        layout.addWidget(calc_card)

        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("Reset Titik")
        btn_reset.clicked.connect(self.canvas.reset_points)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_cancel = QPushButton("Batal")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self.btn_apply = QPushButton("Terapkan Skala Ini")
        self.btn_apply.setObjectName("btnStart")
        self.btn_apply.clicked.connect(self.accept)
        self.btn_apply.setEnabled(False)
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

    def on_points_changed(self, points, dist_px):
        self.dist_px = dist_px
        self.lbl_px.setText(f"{dist_px:.2f} px")
        if len(points) == 2 and dist_px > 0:
            self.compute_scale()
            self.btn_apply.setEnabled(True)
        else:
            self.btn_apply.setEnabled(False)

    def compute_scale(self):
        if self.dist_px > 0:
            mm = self.spin_mm.value()
            self.calculated_scale = mm / self.dist_px
            self.lbl_result.setText(f"{self.calculated_scale:.6f} mm/px ({mm:.1f} mm / {self.dist_px:.1f} px)")


# =====================================================================
# DETEKSI KAMERA YANG TERHUBUNG
# =====================================================================
def enumerate_cameras():
    """
    Mendeteksi daftar kamera yang terhubung ke sistem.
    Mengembalikan list of (index, name) tuple.
    Menggunakan WMI (Windows) untuk mendapatkan nama kamera asli.
    Fallback ke scan OpenCV jika WMI tidak tersedia.
    """
    cameras = []

    # Coba ambil nama kamera via WMI (Windows)
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        wmi_names = [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
    except Exception:
        wmi_names = []

    # Scan OpenCV untuk cek index mana yang benar-benar aktif
    active_indices = []
    for i in range(6):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            active_indices.append(i)
            cap.release()

    # Gabungkan: pasangkan nama WMI dengan index aktif
    for i, idx in enumerate(active_indices):
        if i < len(wmi_names):
            name = wmi_names[i]
        else:
            name = f"Camera {idx}"
        cameras.append((idx, name))

    # Jika tidak ada kamera aktif sama sekali
    if not cameras:
        cameras.append((0, "Camera 0 (tidak terdeteksi)"))

    return cameras


# =====================================================================
# THREAD PEMROSES VIDEO & ARUCO (WORKER THREAD)
# =====================================================================
class VideoWorker(QThread):
    """Thread pemrosesan video kamera & deteksi ArUco secara realtime (X, Y, Z)."""
    frameReady = pyqtSignal(QImage, np.ndarray, int, float)  # q_img, raw_frame, frame_idx, fps
    newDataPoint = pyqtSignal(float, int, float, float, float, str, bool, bool)  # t, idx, dx, dy, dz, status, g_ok, t_ok
    baselineStatus = pyqtSignal(int, int)  # current, total
    connectionChanged = pyqtSignal(bool, str)
    testFinished = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = False
        self.recording = False
        self._stopped_manually = False
        
        self.camera_source = 0
        self.use_dshow = True
        self.resolution_str = ""

        self.ground_id = 0
        self.top_id = 1
        self.pixel_to_mm = 0.265
        self.baseline_frames_target = 30
        self.max_missing_frames = 10

        self.baseline_samples = []
        self.baseline_rel = None
        self.baseline_sizes = None
        self.all_rows = []
        self.t_all = []
        self.x_all = []
        self.y_all = []
        self.z_all = []
        self.frame_idx = 0
        self.t0 = 0.0

    def set_camera(self, source, is_usb=True):
        self.camera_source = source
        self.use_dshow = is_usb

    def set_parameters(self, ground_id, top_id, scale, baseline_frames):
        self.ground_id = ground_id
        self.top_id = top_id
        self.pixel_to_mm = scale
        self.baseline_frames_target = baseline_frames

    def start_recording(self):
        self.recording = True
        self.baseline_samples = []
        self.baseline_rel = None
        self.baseline_sizes = None
        self.all_rows = []
        self.t_all = []
        self.x_all = []
        self.y_all = []
        self.z_all = []
        self.frame_idx = 0
        self.t0 = time.time()

    def stop_recording(self):
        self.recording = False
        try:
            summary = {
                "total_frames": self.frame_idx,
                "t_all": list(self.t_all),
                "x_all": list(self.x_all),
                "y_all": list(self.y_all),
                "z_all": list(self.z_all),
                "all_rows": [list(r) for r in self.all_rows],
                "pixel_to_mm": self.pixel_to_mm
            }
        except Exception as e:
            print(f"[VideoWorker] Warning snapshot buffer: {e}")
            summary = {
                "total_frames": self.frame_idx,
                "t_all": [],
                "x_all": [],
                "y_all": [],
                "z_all": [],
                "all_rows": [],
                "pixel_to_mm": self.pixel_to_mm
            }
        return summary

    def stop_worker(self):
        self._stopped_manually = True
        self.running = False
        self.recording = False

    def run(self):
        self.running = True

        if isinstance(self.camera_source, str):
            # Optimasi FFmpeg low-latency untuk stream IP Camera via jaringan
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "nobuffer;max_delay=500000"
            cap = cv2.VideoCapture(self.camera_source)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            if self.use_dshow:
                cap = cv2.VideoCapture(self.camera_source, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(self.camera_source)

            # Prioritaskan Full HD (1920x1080) untuk webcam / virtual cam (Iriun, DroidCam, USB HD)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            if isinstance(self.camera_source, str):
                msg = (
                    f"Tidak dapat terhubung ke IP Camera:\n{self.camera_source}\n\n"
                    "Kemungkinan penyebab:\n"
                    "1. Ponsel dan Laptop belum terhubung ke jaringan Wi-Fi yang sama.\n"
                    "2. Alamat IP atau port tidak sesuai (cek angka di layar aplikasi IP Webcam HP).\n"
                    "3. Server kamera HP belum aktif ('Start server').\n\n"
                    "Silakan periksa kembali alamat IP lalu klik 'Hubungkan Kamera' untuk mencoba lagi."
                )
            else:
                msg = (
                    f"Tidak dapat membuka webcam USB (Index: {self.camera_source}).\n\n"
                    "Kemungkinan penyebab:\n"
                    "1. Kamera sedang digunakan oleh aplikasi lain (Zoom, Teams, Camera app).\n"
                    "2. Nomor index kamera tidak sesuai (coba ganti Index ke 1 atau 2).\n"
                    "3. Kabel kamera longgar atau driver belum siap.\n\n"
                    "Silakan periksa perangkat lalu klik 'Hubungkan Kamera' untuk mencoba lagi."
                )
            self.connectionChanged.emit(False, msg)
            self.running = False
            return

        # Uji baca frame pertama untuk memastikan aliran stream benar-benar aktif
        ret, test_frame = cap.read()
        if not ret or test_frame is None:
            try:
                cap.release()
            except Exception:
                pass
            if isinstance(self.camera_source, str):
                msg = (
                    f"Alamat IP berhasil dihubungi, namun tidak ada video stream:\n{self.camera_source}\n\n"
                    "Pastikan URL stream lengkap (biasanya berakhiran '/video')\n"
                    "Contoh: http://192.168.1.193:4747/video"
                )
            else:
                msg = f"Webcam terdeteksi namun tidak dapat membaca frame gambar (Index: {self.camera_source})."
            self.connectionChanged.emit(False, msg)
            self.running = False
            return

        h_act, w_act = test_frame.shape[:2]
        self.resolution_str = f"{w_act}x{h_act}"
        self.connectionChanged.emit(True, f"Kamera berhasil terhubung ({self.resolution_str})")

        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        aruco_params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

        last_ground = None
        last_top = None
        last_ground_size = None
        last_top_size = None
        missing_count = 0

        fps_timer = time.time()
        fps_frame_counter = 0
        current_fps = 30.0

        while self.running:
            try:
                ret, frame = cap.read()
            except Exception:
                break
            if not ret or not self.running:
                time.sleep(0.01)
                continue

            fps_frame_counter += 1
            if time.time() - fps_timer >= 1.0:
                current_fps = float(fps_frame_counter) / (time.time() - fps_timer)
                fps_frame_counter = 0
                fps_timer = time.time()

            raw_frame_copy = frame.copy()
            corners, ids, _ = detector.detectMarkers(frame)
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            centers = {}
            sizes = {}
            if ids is not None:
                for i, marker_id in enumerate(ids.flatten()):
                    c = corners[i][0]
                    cx, cy = float(c[:, 0].mean()), float(c[:, 1].mean())
                    centers[int(marker_id)] = (cx, cy)
                    d01 = float(np.linalg.norm(c[0] - c[1]))
                    d12 = float(np.linalg.norm(c[1] - c[2]))
                    d23 = float(np.linalg.norm(c[2] - c[3]))
                    d30 = float(np.linalg.norm(c[3] - c[0]))
                    sizes[int(marker_id)] = (d01 + d12 + d23 + d30) / 4.0

            ground_pos = centers.get(self.ground_id)
            top_pos = centers.get(self.top_id)
            ground_size = sizes.get(self.ground_id)
            top_size = sizes.get(self.top_id)

            g_detected = ground_pos is not None
            t_detected = top_pos is not None

            status = "ok"
            if ground_pos is None or top_pos is None:
                missing_count += 1
                status = "interpolated" if missing_count <= self.max_missing_frames else "missing"
                ground_pos = ground_pos or last_ground
                top_pos = top_pos or last_top
                ground_size = ground_size or last_ground_size
                top_size = top_size or last_top_size
            else:
                missing_count = 0

            if ground_pos is not None:
                last_ground = ground_pos
                last_ground_size = ground_size
            if top_pos is not None:
                last_top = top_pos
                last_top_size = top_size

            # Anotasi visual modern command center pada frame kamera
            if ground_pos and top_pos and status != "missing":
                gx, gy = int(ground_pos[0]), int(ground_pos[1])
                tx, ty = int(top_pos[0]), int(top_pos[1])

                # Garis defleksi struktur gedung (Cyan)
                cv2.line(frame, (gx, gy), (tx, ty), (248, 189, 56), 2)

                # Titik penanda Ground (#0) & Top (#1)
                cv2.circle(frame, (gx, gy), 6, (248, 189, 56), -1)
                cv2.circle(frame, (tx, ty), 6, (252, 132, 192), -1)

                # Tag callout Ground Base Datum
                cv2.rectangle(frame, (gx + 12, gy - 12), (gx + 140, gy + 12), (29, 14, 7), -1)
                cv2.rectangle(frame, (gx + 12, gy - 12), (gx + 140, gy + 12), (248, 189, 56), 1)
                cv2.putText(frame, f"REF #{self.ground_id} GROUND", (gx + 16, gy + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (248, 189, 56), 1)

            # Logika saat pengujian aktif (Recording)
            if self.recording:
                now = time.time() - self.t0
                if ground_pos and top_pos and status != "missing":
                    rel_x = top_pos[0] - ground_pos[0]
                    rel_y = top_pos[1] - ground_pos[1]

                    if len(self.baseline_samples) < self.baseline_frames_target:
                        self.baseline_samples.append((rel_x, rel_y, ground_size or 50.0, top_size or 50.0))
                        self.baselineStatus.emit(len(self.baseline_samples), self.baseline_frames_target)
                        if len(self.baseline_samples) == self.baseline_frames_target:
                            arr = np.array(self.baseline_samples)
                            self.baseline_rel = (arr[:, 0].mean(), arr[:, 1].mean())
                            self.baseline_sizes = (arr[:, 2].mean(), arr[:, 3].mean())

                        cv2.putText(frame, f"TARE BASELINE: {len(self.baseline_samples)}/{self.baseline_frames_target} - Diamkan gedung",
                                    (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 165, 255), 2)

                    elif self.baseline_rel is not None:
                        disp_x = rel_x - self.baseline_rel[0]
                        disp_y = rel_y - self.baseline_rel[1]

                        if self.pixel_to_mm:
                            disp_x *= self.pixel_to_mm
                            disp_y *= self.pixel_to_mm

                        scale = self.pixel_to_mm if self.pixel_to_mm else 1.0
                        g_x = ground_pos[0] * scale
                        g_y = ground_pos[1] * scale
                        t_x = top_pos[0] * scale
                        t_y = top_pos[1] * scale

                        # Estimasi kedalaman Out-of-Plane (Sumbu Z)
                        # Model optik perspektif: Z ~ f * W / size
                        focal_px = 0.85 * w_act if w_act else 1000.0
                        z_ref = focal_px * scale
                        bg_s, bt_s = getattr(self, 'baseline_sizes', (50.0, 50.0))
                        g_z = z_ref * ((bg_s / max(ground_size or bg_s, 1e-3)) - 1.0)
                        t_z = z_ref * ((bt_s / max(top_size or bt_s, 1e-3)) - 1.0)
                        disp_z = t_z - g_z

                        row_data = [f"{now:.4f}", self.frame_idx,
                                    f"{g_x:.3f}", f"{g_y:.3f}", f"{g_z:.3f}",
                                    f"{t_x:.3f}", f"{t_y:.3f}", f"{t_z:.3f}",
                                    f"{disp_x:.3f}", f"{disp_y:.3f}", f"{disp_z:.3f}", status]
                        self.all_rows.append(row_data)
                        self.t_all.append(now)
                        self.x_all.append(disp_x)
                        self.y_all.append(disp_y)
                        self.z_all.append(disp_z)

                        self.newDataPoint.emit(now, self.frame_idx, disp_x, disp_y, disp_z, status, g_detected, t_detected)

                        # Tag callout Top Marker dengan nilai live delta X & Z
                        tx, ty = int(top_pos[0]), int(top_pos[1])
                        cv2.rectangle(frame, (tx + 12, ty - 14), (tx + 195, ty + 12), (29, 14, 7), -1)
                        cv2.rectangle(frame, (tx + 12, ty - 14), (tx + 195, ty + 12), (252, 132, 192), 1)
                        cv2.putText(frame, f"TOP #{self.top_id}: dX {disp_x:+.2f} | dZ {disp_z:+.2f}", (tx + 16, ty + 4),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (252, 132, 192), 1)

                        cv2.putText(frame, f"ACTIVE RUN: dX {disp_x:+.2f} mm | dY {disp_y:+.2f} mm | dZ {disp_z:+.2f} mm",
                                    (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (52, 211, 153), 2)
                else:
                    cv2.putText(frame, "PERINGATAN: Target Marker Hilang!",
                                (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                self.frame_idx += 1
            else:
                cv2.putText(frame, "STANDBY - Kamera Terhubung",
                            (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (148, 163, 184), 2)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            self.frameReady.emit(q_img, raw_frame_copy, self.frame_idx, current_fps)

            # Jeda minimal non-blocking untuk yield thread tanpa menumpuk buffer video
            time.sleep(0.001)

        try:
            cap.release()
        except Exception:
            pass

        if not self._stopped_manually:
            self.connectionChanged.emit(False, "Kamera terputus")


# =====================================================================
# JENDELA UTAMA APLIKASI (MAIN WINDOW)
# =====================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ShakeLab — Miniature Building Vibration Analysis")
        self.resize(1360, 850)
        self.setMinimumSize(1150, 720)
        self.setStyleSheet(MODERN_STYLE)

        # Ikon jendela (title bar & taskbar) — ganti "logo.png" dengan nama file logo kamu
        _icon_path = get_resource_path("logo.png")
        if os.path.exists(_icon_path):
            self.setWindowIcon(QIcon(_icon_path))

        self.worker = None
        self.latest_raw_frame = None

        # Data buffer untuk grafik realtime
        self.plot_window_sec = 10.0
        self.time_buffer = deque()
        self.x_buffer = deque()
        self.y_buffer = deque()
        self.z_buffer = deque()

        # Statistik sementara
        self.max_x = 0.0
        self.min_x = 0.0
        self.max_y = 0.0
        self.min_y = 0.0
        self.max_z = 0.0
        self.min_z = 0.0
        self.sum_sq_x = 0.0
        self.sum_sq_y = 0.0
        self.sum_sq_z = 0.0
        self.count_samples = 0
        self.total_frames_seen = 0
        self.locked_frames_count = 0
        self.run_counter = 1

        self.last_saved_excel = ""
        self.last_saved_csv = ""
        self.last_saved_png = ""

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 1. TOP HEADER (CLEAN & CALM COMMAND CENTER) ──────────────
        header_frame = QFrame()
        header_frame.setObjectName("topHeader")
        header_frame.setFixedHeight(62)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 8, 20, 8)
        header_layout.setSpacing(12)

        # Logo Icon Box
        # Logo sudah memiliki background gelap & rounded corner bawaan,
        # jadi icon_box tidak perlu background tambahan agar tidak double-layer.
        LOGO_PATH = get_resource_path("logo.png")
        icon_box = QLabel()
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setFixedSize(46, 46)
        icon_box.setStyleSheet(
            "background: transparent; "
            "border: none;"
        )
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH).scaled(
                46, 46,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            icon_box.setPixmap(pixmap)
        else:
            icon_box.setText("🏛")  # fallback jika file tidak ditemukan
            icon_box.setStyleSheet("font-size: 22px;")

        header_layout.addWidget(icon_box)

        # Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        row_title = QHBoxLayout()
        row_title.setSpacing(8)

        lbl_app_title = QLabel("ShakeLab")
        lbl_app_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0f172a; letter-spacing: 0.3px;")
        row_title.addWidget(lbl_app_title)

        row_title.addStretch()
        title_box.addLayout(row_title)

        lbl_subtitle = QLabel("Miniature Building Vibration & Displacement Analysis")
        lbl_subtitle.setStyleSheet("font-size: 11px; color: #64748b;")
        title_box.addWidget(lbl_subtitle)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Status Pill: Camera
        self.pill_cam = QLabel("● Camera Disconnected")
        self.pill_cam.setStyleSheet(
            "background-color: #f1f5f9; color: #64748b; "
            "border: 1px solid #cbd5e1; border-radius: 14px; "
            "padding: 5px 12px; font-weight: 600; font-size: 11px;"
        )
        header_layout.addWidget(self.pill_cam)

        # Status Pill: Active Run
        self.pill_run = QLabel("STANDBY")
        self.pill_run.setStyleSheet(
            "background-color: #f1f5f9; color: #64748b; "
            "border: 1px solid #cbd5e1; border-radius: 14px; "
            "padding: 5px 12px; font-weight: 700; font-size: 11px;"
        )
        header_layout.addWidget(self.pill_run)

        root_layout.addWidget(header_frame)


        # ── 2. MAIN BODY (SIDEBAR + WORKSPACE) ───────────────────────
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(14, 14, 14, 14)
        body_layout.setSpacing(14)

        # ── LEFT SIDEBAR (Controls & Settings) ──
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setFixedWidth(340)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        sidebar_inner = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_inner)
        sidebar_layout.setContentsMargins(0, 0, 4, 0)
        sidebar_layout.setSpacing(10)

        # CARD 01: CAMERA SOURCE
        card_cam = QFrame()
        card_cam.setObjectName("sidebarCard")
        lay_card_cam = QVBoxLayout(card_cam)
        lay_card_cam.setSpacing(8)

        head_cam = QHBoxLayout()
        badge_01 = QLabel("01")
        badge_01.setStyleSheet("background-color: #e0f2fe; color: #0284c7; font-weight: bold; border-radius: 4px; padding: 2px 6px; font-family: 'JetBrains Mono';")
        head_cam.addWidget(badge_01)
        lbl_cam_title = QLabel("CAMERA SOURCE")
        lbl_cam_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #0f172a; letter-spacing: 0.5px;")
        head_cam.addWidget(lbl_cam_title)
        head_cam.addStretch()
        self.lbl_cam_status = QLabel("● Ready")
        self.lbl_cam_status.setStyleSheet("color: #059669; font-size: 11px; font-weight: 600;")
        head_cam.addWidget(self.lbl_cam_status)
        lay_card_cam.addLayout(head_cam)

        # Segmented Button (USB / IP)
        row_segment = QHBoxLayout()
        row_segment.setSpacing(2)
        row_segment.setContentsMargins(2, 2, 2, 2)
        seg_container = QFrame()
        seg_container.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")
        seg_box = QHBoxLayout(seg_container)
        seg_box.setContentsMargins(2, 2, 2, 2)
        seg_box.setSpacing(4)

        self.btn_seg_usb = QPushButton("USB Webcam")
        self.btn_seg_usb.setObjectName("btnSegmentActive")
        self.btn_seg_ip = QPushButton("IP / Wi-Fi")
        self.btn_seg_ip.setObjectName("btnSegmentInactive")

        self.btn_seg_usb.clicked.connect(lambda: self.switch_cam_mode(True))
        self.btn_seg_ip.clicked.connect(lambda: self.switch_cam_mode(False))
        seg_box.addWidget(self.btn_seg_usb)
        seg_box.addWidget(self.btn_seg_ip)
        lay_card_cam.addWidget(seg_container)

        # Input Parameter Kamera
        self.container_usb = QWidget()
        lay_u = QVBoxLayout(self.container_usb)
        lay_u.setContentsMargins(0, 2, 0, 2)
        lay_u.setSpacing(4)

        lbl_dev = QLabel("Pilih Kamera:")
        lbl_dev.setStyleSheet("color: #64748b; font-size: 11px;")
        lay_u.addWidget(lbl_dev)

        row_cam = QHBoxLayout()
        row_cam.setContentsMargins(0, 0, 0, 0)
        row_cam.setSpacing(6)

        self.combo_cam = QComboBox()
        self.combo_cam.setToolTip("Pilih kamera yang ingin digunakan")
        self._camera_list = []  # list of (index, name)
        self._populate_camera_combo()
        row_cam.addWidget(self.combo_cam, 1)

        self.btn_refresh_cam = QPushButton("↺")
        self.btn_refresh_cam.setFixedSize(36, 32)
        self.btn_refresh_cam.setToolTip("Pindai ulang kamera yang terhubung")
        self.btn_refresh_cam.setStyleSheet(
            "QPushButton { background: #f8fafc; color: #0284c7; border: 1px solid #cbd5e1; "
            "border-radius: 6px; font-size: 16px; font-weight: bold; padding: 0px; } "
            "QPushButton:hover { background: #e0f2fe; color: #0369a1; border-color: #7dd3fc; } "
            "QPushButton:disabled { color: #94a3b8; border-color: #e2e8f0; }"
        )
        self.btn_refresh_cam.clicked.connect(self._refresh_cameras)
        row_cam.addWidget(self.btn_refresh_cam)

        lay_u.addLayout(row_cam)
        lay_card_cam.addWidget(self.container_usb)

        self.container_ip = QWidget()
        self.container_ip.setVisible(False)
        lay_ip = QVBoxLayout(self.container_ip)
        lay_ip.setContentsMargins(0, 2, 0, 2)
        lay_ip.addWidget(QLabel("URL Stream IP Camera:"))
        self.txt_ip_url = QLineEdit()
        self.txt_ip_url.setPlaceholderText("http://192.168.x.x:port/video")
        lay_ip.addWidget(self.txt_ip_url)
        lay_card_cam.addWidget(self.container_ip)

        # Tombol Connect / Stream Linked
        self.btn_connect = QPushButton("Hubungkan Kamera")
        self.btn_connect.setObjectName("btnStreamLink")
        self.btn_connect.clicked.connect(self.toggle_camera)
        lay_card_cam.addWidget(self.btn_connect)

        sidebar_layout.addWidget(card_cam)

        # CARD 02: TARGET MARKERS
        card_marker = QFrame()
        card_marker.setObjectName("sidebarCard")
        lay_card_marker = QVBoxLayout(card_marker)
        lay_card_marker.setSpacing(8)

        head_marker = QHBoxLayout()
        badge_02 = QLabel("02")
        badge_02.setStyleSheet("background-color: #e0f2fe; color: #0284c7; font-weight: bold; border-radius: 4px; padding: 2px 6px; font-family: 'JetBrains Mono';")
        head_marker.addWidget(badge_02)
        lbl_marker_title = QLabel("TARGET MARKERS")
        lbl_marker_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #0f172a; letter-spacing: 0.5px;")
        head_marker.addWidget(lbl_marker_title)
        head_marker.addStretch()
        lbl_dict = QLabel("ArUco 4x4")
        lbl_dict.setStyleSheet("color: #64748b; font-size: 10px; font-family: 'JetBrains Mono';")
        head_marker.addWidget(lbl_dict)
        lay_card_marker.addLayout(head_marker)

        # Ground Marker Card (#0)
        card_m0 = QFrame()
        card_m0.setObjectName("subCard")
        lay_m0 = QHBoxLayout(card_m0)
        lay_m0.setContentsMargins(8, 6, 8, 6)
        lbl_id0 = QLabel("#0")
        lbl_id0.setFixedSize(28, 28)
        lbl_id0.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_id0.setStyleSheet("background-color: #e0f2fe; color: #0284c7; font-weight: bold; font-family: 'JetBrains Mono'; border-radius: 6px;")
        lay_m0.addWidget(lbl_id0)
        txt_m0 = QVBoxLayout()
        txt_m0.setSpacing(1)
        lbl_m0_name = QLabel("Ground Base Datum")
        lbl_m0_name.setStyleSheet("font-weight: 600; font-size: 11px; color: #0f172a;")
        txt_m0.addWidget(lbl_m0_name)
        lbl_m0_sub = QLabel("Shaking table platform")
        lbl_m0_sub.setStyleSheet("font-size: 10px; color: #64748b;")
        txt_m0.addWidget(lbl_m0_sub)
        lay_m0.addLayout(txt_m0)
        lay_m0.addStretch()
        self.badge_m0_status = QLabel("Standby")
        self.badge_m0_status.setStyleSheet("background-color: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; border-radius: 10px; padding: 2px 7px; font-size: 9px; font-weight: 600; font-family: 'JetBrains Mono';")
        lay_m0.addWidget(self.badge_m0_status)
        lay_card_marker.addWidget(card_m0)

        # Roof Marker Card (#1)
        card_m1 = QFrame()
        card_m1.setObjectName("subCard")
        lay_m1 = QHBoxLayout(card_m1)
        lay_m1.setContentsMargins(8, 6, 8, 6)
        lbl_id1 = QLabel("#1")
        lbl_id1.setFixedSize(28, 28)
        lbl_id1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_id1.setStyleSheet("background-color: #faf5ff; color: #9333ea; font-weight: bold; font-family: 'JetBrains Mono'; border-radius: 6px;")
        lay_m1.addWidget(lbl_id1)
        txt_m1 = QVBoxLayout()
        txt_m1.setSpacing(1)
        lbl_m1_name = QLabel("Roof Target")
        lbl_m1_name.setStyleSheet("font-weight: 600; font-size: 11px; color: #0f172a;")
        txt_m1.addWidget(lbl_m1_name)
        lbl_m1_sub = QLabel("Top story apex node")
        lbl_m1_sub.setStyleSheet("font-size: 10px; color: #64748b;")
        txt_m1.addWidget(lbl_m1_sub)
        lay_m1.addLayout(txt_m1)
        lay_m1.addStretch()
        self.badge_m1_status = QLabel("Standby")
        self.badge_m1_status.setStyleSheet("background-color: #faf5ff; color: #9333ea; border: 1px solid #e9d5ff; border-radius: 10px; padding: 2px 7px; font-size: 9px; font-weight: 600; font-family: 'JetBrains Mono';")
        lay_m1.addWidget(self.badge_m1_status)
        lay_card_marker.addWidget(card_m1)

        sidebar_layout.addWidget(card_marker)

        # CARD 03: SCALE CALIBRATION
        card_calib = QFrame()
        card_calib.setObjectName("sidebarCard")
        lay_card_calib = QVBoxLayout(card_calib)
        lay_card_calib.setSpacing(8)

        head_calib = QHBoxLayout()
        badge_03 = QLabel("03")
        badge_03.setStyleSheet("background-color: #e0f2fe; color: #0284c7; font-weight: bold; border-radius: 4px; padding: 2px 6px; font-family: 'JetBrains Mono';")
        head_calib.addWidget(badge_03)
        lbl_calib_title = QLabel("SCALE CALIBRATION")
        lbl_calib_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #0f172a; letter-spacing: 0.5px;")
        head_calib.addWidget(lbl_calib_title)
        head_calib.addStretch()
        self.lbl_calib_verified = QLabel("● Verified")
        self.lbl_calib_verified.setStyleSheet("color: #059669; font-size: 11px; font-weight: 600;")
        head_calib.addWidget(self.lbl_calib_verified)
        lay_card_calib.addLayout(head_calib)

        row_scale_input = QHBoxLayout()
        row_scale_input.setSpacing(6)
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setDecimals(6)
        self.spin_scale.setRange(0.0001, 10.0)
        self.spin_scale.setValue(0.265000)
        self.spin_scale.setSingleStep(0.005)
        self.spin_scale.setSuffix(" mm/px")
        self.spin_scale.setMinimumHeight(32)
        row_scale_input.addWidget(self.spin_scale, stretch=3)

        self.btn_calib = QPushButton("Kalibrasi")
        self.btn_calib.setMinimumHeight(32)
        self.btn_calib.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_calib.clicked.connect(self.open_calibration_dialog)
        row_scale_input.addWidget(self.btn_calib, stretch=2)
        lay_card_calib.addLayout(row_scale_input)

        sidebar_layout.addWidget(card_calib)

        # CARD 04: EXPERIMENT CONTROL
        card_exp = QFrame()
        card_exp.setObjectName("sidebarCard")
        lay_card_exp = QVBoxLayout(card_exp)
        lay_card_exp.setSpacing(9)

        head_exp = QHBoxLayout()
        badge_04 = QLabel("04")
        badge_04.setStyleSheet("background-color: #e0f2fe; color: #0284c7; font-weight: bold; border-radius: 4px; padding: 2px 6px; font-family: 'JetBrains Mono';")
        head_exp.addWidget(badge_04)
        lbl_exp_title = QLabel("EXPERIMENT CONTROL")
        lbl_exp_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #0f172a; letter-spacing: 0.5px;")
        head_exp.addWidget(lbl_exp_title)
        head_exp.addStretch()
        self.lbl_run_tag = QLabel("RUN #001")
        self.lbl_run_tag.setStyleSheet("color: #059669; font-weight: bold; font-family: 'JetBrains Mono'; font-size: 11px;")
        head_exp.addWidget(self.lbl_run_tag)
        lay_card_exp.addLayout(head_exp)

        # Tombol Start & Stop
        grid_btns = QHBoxLayout()
        grid_btns.setSpacing(8)

        self.btn_start = QPushButton("Start / Resume")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setEnabled(False)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_test)
        grid_btns.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop and Save")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_test)
        grid_btns.addWidget(self.btn_stop)
        lay_card_exp.addLayout(grid_btns)

        # Baseline Tare Filter Progress
        row_tare = QHBoxLayout()
        lbl_tare = QLabel("Baseline Tare Filter")
        lbl_tare.setStyleSheet("font-size: 11px; color: #64748b;")
        row_tare.addWidget(lbl_tare)
        row_tare.addStretch()
        self.lbl_tare_percent = QLabel("100% Ready")
        self.lbl_tare_percent.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; color: #059669; font-weight: bold;")
        row_tare.addWidget(self.lbl_tare_percent)
        lay_card_exp.addLayout(row_tare)

        self.prog_baseline = QProgressBar()
        self.prog_baseline.setRange(0, 30)
        self.prog_baseline.setValue(30)
        self.prog_baseline.setTextVisible(False)
        lay_card_exp.addWidget(self.prog_baseline)

        # Grid Elapsed Time & Lock Confidence
        grid_time_conf = QHBoxLayout()
        grid_time_conf.setSpacing(8)

        box_time = QFrame()
        box_time.setObjectName("subCard")
        lay_bt = QVBoxLayout(box_time)
        lay_bt.setContentsMargins(6, 6, 6, 6)
        lay_bt.setSpacing(2)
        lbl_et_title = QLabel("ELAPSED TIME")
        lbl_et_title.setStyleSheet("font-size: 9px; font-weight: bold; color: #64748b;")
        lay_bt.addWidget(lbl_et_title)
        self.lbl_elapsed_time = QLabel("00:00:00.0")
        self.lbl_elapsed_time.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 13px; font-weight: bold; color: #0f172a;")
        lay_bt.addWidget(self.lbl_elapsed_time)
        grid_time_conf.addWidget(box_time)

        box_conf = QFrame()
        box_conf.setObjectName("subCard")
        lay_bc = QVBoxLayout(box_conf)
        lay_bc.setContentsMargins(6, 6, 6, 6)
        lay_bc.setSpacing(2)
        lbl_lc_title = QLabel("LOCK CONFIDENCE")
        lbl_lc_title.setStyleSheet("font-size: 9px; font-weight: bold; color: #64748b;")
        lay_bc.addWidget(lbl_lc_title)
        self.lbl_lock_conf = QLabel("100.0%")
        self.lbl_lock_conf.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 13px; font-weight: bold; color: #059669;")
        lay_bc.addWidget(self.lbl_lock_conf)
        grid_time_conf.addWidget(box_conf)

        lay_card_exp.addLayout(grid_time_conf)
        sidebar_layout.addWidget(card_exp)

        sidebar_layout.addStretch()
        sidebar_scroll.setWidget(sidebar_inner)
        body_layout.addWidget(sidebar_scroll)

        # ── RIGHT WORKSPACE (Live Video + Realtime Scope + Hero Metrics) ──
        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(12)

        # ── TOP HALF: LIVE CAMERA FEED ──
        video_frame = QFrame()
        video_frame.setObjectName("videoContainer")
        video_layout = QVBoxLayout(video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)

        # Feed Header
        feed_header = QFrame()
        feed_header.setStyleSheet("background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; border-top-left-radius: 9px; border-top-right-radius: 9px;")
        feed_header.setFixedHeight(36)
        fh_layout = QHBoxLayout(feed_header)
        fh_layout.setContentsMargins(14, 4, 14, 4)
        fh_layout.setSpacing(8)

        lbl_vh_title = QLabel("LIVE CAMERA FEED | Optical Tracking & Displacement View")
        lbl_vh_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #0f172a; letter-spacing: 0.3px;")
        fh_layout.addWidget(lbl_vh_title)
        fh_layout.addStretch()

        self.lbl_feed_frame = QLabel("Frame: 0")
        self.lbl_feed_frame.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; color: #64748b;")
        fh_layout.addWidget(self.lbl_feed_frame)

        self.lbl_feed_res = QLabel("Resolution: 720p")
        self.lbl_feed_res.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; color: #64748b;")
        fh_layout.addWidget(self.lbl_feed_res)

        self.badge_tracking_status = QLabel("● Tracking Stable")
        self.badge_tracking_status.setStyleSheet(
            "background-color: #ecfdf5; color: #059669; "
            "border: 1px solid #a7f3d0; border-radius: 10px; "
            "padding: 2px 8px; font-size: 10px; font-weight: 600;"
        )
        fh_layout.addWidget(self.badge_tracking_status)
        video_layout.addWidget(feed_header)

        # Video Canvas
        self.lbl_video = QLabel("Kamera belum terhubung.\nSilakan klik 'Hubungkan Kamera' pada panel sebelah kiri.")
        self.lbl_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_video.setStyleSheet("font-size: 14px; color: #94a3b8; background-color: #0f172a;")
        self.lbl_video.setMinimumSize(400, 240)
        self.lbl_video.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        video_layout.addWidget(self.lbl_video, stretch=1)

        workspace_layout.addWidget(video_frame, stretch=4)

        # ── BOTTOM HALF: 2-COLUMN SPLIT (SCOPE GRAPH + HERO METRICS) ──
        bottom_split = QHBoxLayout()
        bottom_split.setSpacing(12)

        # LEFT (COL SPAN 7): DISPLACEMENT GRAPH SCOPE
        scope_frame = QFrame()
        scope_frame.setObjectName("scopeContainer")
        scope_layout = QVBoxLayout(scope_frame)
        scope_layout.setContentsMargins(12, 10, 12, 10)
        scope_layout.setSpacing(6)

        # Scope Header
        scope_head = QHBoxLayout()
        sh_left = QVBoxLayout()
        sh_left.setSpacing(1)
        lbl_sh_title = QLabel("REAL-TIME DISPLACEMENT (MM)")
        lbl_sh_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #0f172a; letter-spacing: 0.4px;")
        sh_left.addWidget(lbl_sh_title)
        lbl_sh_sub = QLabel("Differential Roof Motion relative to Ground Base Datum")
        lbl_sh_sub.setStyleSheet("font-size: 10px; color: #64748b;")
        sh_left.addWidget(lbl_sh_sub)
        scope_head.addLayout(sh_left)

        scope_head.addStretch()

        # Legend Pills
        leg_x = QLabel("— ΔX (Lateral)")
        leg_x.setStyleSheet("background-color: #f0f9ff; color: #0284c7; border: 1px solid #bae6fd; border-radius: 6px; padding: 3px 8px; font-weight: 600; font-family: 'JetBrains Mono'; font-size: 10px;")
        scope_head.addWidget(leg_x)

        leg_y = QLabel("— ΔY (Axial)")
        leg_y.setStyleSheet("background-color: #faf5ff; color: #9333ea; border: 1px solid #e9d5ff; border-radius: 6px; padding: 3px 8px; font-weight: 600; font-family: 'JetBrains Mono'; font-size: 10px;")
        scope_head.addWidget(leg_y)

        leg_z = QLabel("— ΔZ (Out-of-Plane)")
        leg_z.setStyleSheet("background-color: #fff7ed; color: #ea580c; border: 1px solid #ffedd5; border-radius: 6px; padding: 3px 8px; font-weight: 600; font-family: 'JetBrains Mono'; font-size: 10px;")
        scope_head.addWidget(leg_z)

        scope_layout.addLayout(scope_head)

        # PyQtGraph Widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#ffffff')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.plot_widget.getAxis('left').setTextPen('#475569')
        self.plot_widget.getAxis('bottom').setTextPen('#475569')
        self.plot_widget.getAxis('left').setPen('#cbd5e1')
        self.plot_widget.getAxis('bottom').setPen('#cbd5e1')

        # Zero reference line
        zero_line = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(color='#94a3b8', width=1, style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(zero_line)

        # Kurva X (Deep Sky Blue), Kurva Y (Purple), Kurva Z (Amber-Orange)
        self.curve_x = self.plot_widget.plot(pen=pg.mkPen(color='#0284c7', width=2.5), name="ΔX (Lateral)")
        self.curve_y = self.plot_widget.plot(pen=pg.mkPen(color='#9333ea', width=2.0), name="ΔY (Axial)")
        self.curve_z = self.plot_widget.plot(pen=pg.mkPen(color='#ea580c', width=2.0), name="ΔZ (Out-of-Plane)")

        scope_layout.addWidget(self.plot_widget, stretch=1)

        # Scope Footer (Time Axis)
        scope_foot = QHBoxLayout()
        for t_label in ["T-10.0s", "T-7.5s", "T-5.0s", "T-2.5s"]:
            lbl_t = QLabel(t_label)
            lbl_t.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 10px;")
            scope_foot.addWidget(lbl_t)
            scope_foot.addStretch()
        lbl_now = QLabel("NOW (0.0s)")
        lbl_now.setStyleSheet("color: #0284c7; font-weight: bold; font-family: 'JetBrains Mono'; font-size: 10px;")
        scope_foot.addWidget(lbl_now)
        scope_layout.addLayout(scope_foot)

        bottom_split.addWidget(scope_frame, stretch=7)

        # RIGHT (COL SPAN 5): HERO MEASUREMENTS, STATS & ACTIONS
        stats_col = QVBoxLayout()
        stats_col.setSpacing(8)

        # Metric 1: Lateral Sway (ΔX)
        card_sway = QFrame()
        card_sway.setObjectName("metricCard")
        lay_sway = QVBoxLayout(card_sway)
        lay_sway.setContentsMargins(12, 7, 12, 7)
        lay_sway.setSpacing(3)

        head_sway = QHBoxLayout()
        lbl_sway_t = QLabel("LATERAL SWAY (ΔX)")
        lbl_sway_t.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; letter-spacing: 0.5px;")
        head_sway.addWidget(lbl_sway_t)
        head_sway.addStretch()
        self.badge_sway_dir = QLabel("Right Sway")
        self.badge_sway_dir.setStyleSheet("color: #059669; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")
        head_sway.addWidget(self.badge_sway_dir)
        lay_sway.addLayout(head_sway)

        row_sway_val = QHBoxLayout()
        self.lbl_sway_val = QLabel("+0.00")
        self.lbl_sway_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 24px; font-weight: bold; color: #0284c7;")
        row_sway_val.addWidget(self.lbl_sway_val)
        lbl_mm1 = QLabel("mm")
        lbl_mm1.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 12px; color: #64748b; padding-top: 6px;")
        row_sway_val.addWidget(lbl_mm1)
        row_sway_val.addStretch()
        lay_sway.addLayout(row_sway_val)

        self.lbl_sway_limits = QLabel("Max: +0.00 mm  |  Min: -0.00 mm")
        self.lbl_sway_limits.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 11px; border-top: 1px solid #e2e8f0; padding-top: 3px;")
        lay_sway.addWidget(self.lbl_sway_limits)
        stats_col.addWidget(card_sway)

        # Metric 2: Vertical Drop (ΔY)
        card_drop = QFrame()
        card_drop.setObjectName("metricCard")
        lay_drop = QVBoxLayout(card_drop)
        lay_drop.setContentsMargins(12, 7, 12, 7)
        lay_drop.setSpacing(3)

        head_drop = QHBoxLayout()
        lbl_drop_t = QLabel("VERTICAL DROP (ΔY)")
        lbl_drop_t.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; letter-spacing: 0.5px;")
        head_drop.addWidget(lbl_drop_t)
        head_drop.addStretch()
        lbl_drop_sub = QLabel("Axial")
        lbl_drop_sub.setStyleSheet("color: #9333ea; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")
        head_drop.addWidget(lbl_drop_sub)
        lay_drop.addLayout(head_drop)

        row_drop_val = QHBoxLayout()
        self.lbl_drop_val = QLabel("-0.00")
        self.lbl_drop_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 24px; font-weight: bold; color: #9333ea;")
        row_drop_val.addWidget(self.lbl_drop_val)
        lbl_mm2 = QLabel("mm")
        lbl_mm2.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 12px; color: #64748b; padding-top: 6px;")
        row_drop_val.addWidget(lbl_mm2)
        row_drop_val.addStretch()
        lay_drop.addLayout(row_drop_val)

        self.lbl_drop_limits = QLabel("Max: +0.00 mm  |  Min: -0.00 mm")
        self.lbl_drop_limits.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 11px; border-top: 1px solid #e2e8f0; padding-top: 3px;")
        lay_drop.addWidget(self.lbl_drop_limits)
        stats_col.addWidget(card_drop)

        # Metric 3: Out-of-Plane Motion (ΔZ)
        card_depth = QFrame()
        card_depth.setObjectName("metricCard")
        lay_depth = QVBoxLayout(card_depth)
        lay_depth.setContentsMargins(12, 7, 12, 7)
        lay_depth.setSpacing(3)

        head_depth = QHBoxLayout()
        lbl_depth_t = QLabel("OUT-OF-PLANE (ΔZ)")
        lbl_depth_t.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; letter-spacing: 0.5px;")
        head_depth.addWidget(lbl_depth_t)
        head_depth.addStretch()
        self.badge_depth_dir = QLabel("Stable")
        self.badge_depth_dir.setStyleSheet("color: #ea580c; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")
        head_depth.addWidget(self.badge_depth_dir)
        lay_depth.addLayout(head_depth)

        row_depth_val = QHBoxLayout()
        self.lbl_depth_val = QLabel("+0.00")
        self.lbl_depth_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 24px; font-weight: bold; color: #ea580c;")
        row_depth_val.addWidget(self.lbl_depth_val)
        lbl_mm3 = QLabel("mm")
        lbl_mm3.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 12px; color: #64748b; padding-top: 6px;")
        row_depth_val.addWidget(lbl_mm3)
        row_depth_val.addStretch()
        lay_depth.addLayout(row_depth_val)

        self.lbl_depth_limits = QLabel("Max: +0.00 mm  |  Min: -0.00 mm")
        self.lbl_depth_limits.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 11px; border-top: 1px solid #e2e8f0; padding-top: 3px;")
        lay_depth.addWidget(self.lbl_depth_limits)
        stats_col.addWidget(card_depth)

        # Dual Summary Badges: Drift Ratio & Natural Frequency
        row_dual_badges = QHBoxLayout()
        row_dual_badges.setSpacing(8)

        card_drift = QFrame()
        card_drift.setObjectName("metricCard")
        lay_cd = QVBoxLayout(card_drift)
        lay_cd.setContentsMargins(10, 8, 10, 8)
        lay_cd.setSpacing(2)
        lbl_dr_t = QLabel("DRIFT RATIO")
        lbl_dr_t.setStyleSheet("font-size: 9px; font-weight: bold; color: #64748b;")
        lay_cd.addWidget(lbl_dr_t)
        self.lbl_drift_val = QLabel("0.00%")
        self.lbl_drift_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 17px; font-weight: bold; color: #059669;")
        lay_cd.addWidget(self.lbl_drift_val)
        lbl_dr_desc = QLabel("Relative to Height")
        lbl_dr_desc.setStyleSheet("font-size: 9px; color: #94a3b8;")
        lay_cd.addWidget(lbl_dr_desc)
        row_dual_badges.addWidget(card_drift)

        card_freq = QFrame()
        card_freq.setObjectName("metricCard")
        lay_cf = QVBoxLayout(card_freq)
        lay_cf.setContentsMargins(10, 8, 10, 8)
        lay_cf.setSpacing(2)
        lbl_fq_t = QLabel("FREQUENCY (f₁)")
        lbl_fq_t.setStyleSheet("font-size: 9px; font-weight: bold; color: #64748b;")
        lay_cf.addWidget(lbl_fq_t)
        self.lbl_freq_val = QLabel("— Hz")
        self.lbl_freq_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 17px; font-weight: bold; color: #0284c7;")
        lay_cf.addWidget(self.lbl_freq_val)
        lbl_fq_desc = QLabel("1st Dominant Mode")
        lbl_fq_desc.setStyleSheet("font-size: 9px; color: #94a3b8;")
        lay_cf.addWidget(lbl_fq_desc)
        row_dual_badges.addWidget(card_freq)

        stats_col.addLayout(row_dual_badges)

        # Quick Action Export Buttons
        row_exports = QHBoxLayout()
        row_exports.setSpacing(6)

        self.btn_open_folder = QPushButton("📂 Folder")
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        row_exports.addWidget(self.btn_open_folder)

        self.btn_open_excel = QPushButton("📊 Excel")
        self.btn_open_excel.setEnabled(False)
        self.btn_open_excel.clicked.connect(lambda: self.open_file(self.last_saved_excel))
        row_exports.addWidget(self.btn_open_excel)

        self.btn_open_png = QPushButton("📈 Grafik PNG")
        self.btn_open_png.setEnabled(False)
        self.btn_open_png.clicked.connect(lambda: self.open_file(self.last_saved_png))
        row_exports.addWidget(self.btn_open_png)

        stats_col.addLayout(row_exports)

        bottom_split.addLayout(stats_col, stretch=5)
        workspace_layout.addLayout(bottom_split, stretch=3)

        body_layout.addWidget(workspace)
        root_layout.addWidget(body_widget)

        # ── 3. BOTTOM FOOTER STATUS BAR ──────────────────────────────
        footer = QFrame()
        footer.setObjectName("footerBar")
        footer.setFixedHeight(36)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 4, 20, 4)
        footer_layout.setSpacing(12)

        def make_sep():
            s = QLabel("|")
            s.setStyleSheet("color: #cbd5e1;")
            return s

        self.lbl_ft_cam = QLabel("● Camera: Disconnected")
        self.lbl_ft_cam.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 11px;")
        footer_layout.addWidget(self.lbl_ft_cam)

        footer_layout.addWidget(make_sep())

        self.lbl_ft_tracking = QLabel("Tracking: 0.0%")
        self.lbl_ft_tracking.setStyleSheet("color: #0284c7; font-family: 'JetBrains Mono'; font-size: 11px; font-weight: 600;")
        footer_layout.addWidget(self.lbl_ft_tracking)

        footer_layout.addWidget(make_sep())

        self.lbl_ft_markers = QLabel("Markers: 0/2 Locked")
        self.lbl_ft_markers.setStyleSheet("color: #0f172a; font-family: 'JetBrains Mono'; font-size: 11px;")
        footer_layout.addWidget(self.lbl_ft_markers)

        footer_layout.addWidget(make_sep())

        # Storage Free space
        try:
            free_gb = shutil.disk_usage(".")[2] / (1024 ** 3)
            str_storage = f"Storage: OK ({free_gb:.1f} GB free)"
        except Exception:
            str_storage = "Storage: Ready"
        lbl_ft_storage = QLabel(str_storage)
        lbl_ft_storage.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 11px;")
        footer_layout.addWidget(lbl_ft_storage)

        footer_layout.addStretch()

        self.lbl_ft_sync = QLabel("● Sync OK")
        self.lbl_ft_sync.setStyleSheet("color: #059669; font-family: 'JetBrains Mono'; font-size: 11px;")
        footer_layout.addWidget(self.lbl_ft_sync)

        self.lbl_ft_lat = QLabel("Latency: 3.2ms")
        self.lbl_ft_lat.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 11px;")
        footer_layout.addWidget(self.lbl_ft_lat)

        root_layout.addWidget(footer)

    def switch_cam_mode(self, is_usb):
        if is_usb:
            self.btn_seg_usb.setObjectName("btnSegmentActive")
            self.btn_seg_ip.setObjectName("btnSegmentInactive")
            self.container_usb.setVisible(True)
            self.container_ip.setVisible(False)
        else:
            self.btn_seg_usb.setObjectName("btnSegmentInactive")
            self.btn_seg_ip.setObjectName("btnSegmentActive")
            self.container_usb.setVisible(False)
            self.container_ip.setVisible(True)
        self.btn_seg_usb.setStyle(self.btn_seg_usb.style())
        self.btn_seg_ip.setStyle(self.btn_seg_ip.style())

    # ── DETEKSI & PEMILIHAN KAMERA ────────────────────────────────
    def _populate_camera_combo(self):
        """Isi ComboBox kamera dengan nama perangkat yang terdeteksi."""
        self._camera_list = enumerate_cameras()
        self.combo_cam.blockSignals(True)
        self.combo_cam.clear()
        for idx, name in self._camera_list:
            self.combo_cam.addItem(f"[{idx}] {name}", userData=idx)
        self.combo_cam.blockSignals(False)

    def _refresh_cameras(self):
        """Pindai ulang kamera yang terhubung dan perbarui ComboBox."""
        self.btn_refresh_cam.setEnabled(False)
        self.btn_refresh_cam.setText("...")
        prev_data = self.combo_cam.currentData()
        self._populate_camera_combo()
        # Coba pertahankan pilihan sebelumnya
        for i in range(self.combo_cam.count()):
            if self.combo_cam.itemData(i) == prev_data:
                self.combo_cam.setCurrentIndex(i)
                break
        self.btn_refresh_cam.setEnabled(True)
        self.btn_refresh_cam.setText("↺")

    # ── KONTROL KAMERA ───────────────────────────────────────────
    def toggle_camera(self):
        if self.worker is not None and self.worker.isRunning():
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Memutuskan...")

            # Lepaskan koneksi sinyal frame agar UI tidak terus memproses frame saat thread mati
            try:
                self.worker.frameReady.disconnect()
            except Exception:
                pass

            w = self.worker
            self.worker = None

            w.stop_worker()
            w.finished.connect(w.deleteLater)
            w.wait(400)

            self.btn_connect.setText("Hubungkan Kamera")
            self.btn_connect.setStyleSheet("")
            self.btn_connect.setEnabled(True)
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.lbl_video.setText("Kamera terputus.")
            self.pill_cam.setText("● Camera Disconnected")
            self.pill_cam.setStyleSheet("background-color: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1; border-radius: 14px; padding: 5px 12px; font-weight: 600; font-size: 11px;")
            self.lbl_cam_status.setText("● Off")
            self.lbl_cam_status.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
            self.lbl_ft_cam.setText("● Camera: Disconnected")
            self.lbl_ft_cam.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 11px;")
        else:
            is_usb = (self.btn_seg_usb.objectName() == "btnSegmentActive")
            if is_usb:
                cam_idx = self.combo_cam.currentIndex()
                source = self._camera_list[cam_idx][0] if cam_idx < len(self._camera_list) else 0
            else:
                source = self.txt_ip_url.text().strip()

            # Validasi input URL jika mode IP Cam dipilih
            if not is_usb:
                if not source:
                    QMessageBox.warning(
                        self, "Input IP Kosong",
                        "Alamat URL IP Camera tidak boleh kosong.\n\n"
                        "Contoh format yang benar:\nhttp://192.168.1.193:4747/video"
                    )
                    return
                if not (source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://")):
                    QMessageBox.warning(
                        self, "Format URL Tidak Sesuai",
                        f"URL yang dimasukkan:\n'{source}'\n\n"
                        "Alamat IP Camera harus diawali dengan http:// atau rtsp://\n\n"
                        "Contoh format yang benar:\nhttp://192.168.1.193:4747/video"
                    )
                    return

                # Otomatis tambahkan /video jika pengguna hanya memasukkan host:port (misal http://192.168.18.15:8080)
                if source.startswith("http://") or source.startswith("https://"):
                    from urllib.parse import urlparse
                    parsed = urlparse(source)
                    if not parsed.path or parsed.path == "/":
                        source = source.rstrip("/") + "/video"
                        self.txt_ip_url.setText(source)

            self.lbl_video.setText("Menghubungkan ke sumber kamera, mohon tunggu...")
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Menghubungkan...")

            self.worker = VideoWorker()
            self.worker.set_camera(source, is_usb)
            self.worker.set_parameters(
                ground_id=0,
                top_id=1,
                scale=self.spin_scale.value(),
                baseline_frames=30
            )
            self.worker.frameReady.connect(self.on_frame_ready)
            self.worker.newDataPoint.connect(self.on_new_data_point)
            self.worker.baselineStatus.connect(self.on_baseline_progress)
            self.worker.connectionChanged.connect(self.on_connection_changed)
            self.worker.start()

    def on_connection_changed(self, connected, message):
        self.btn_connect.setEnabled(True)
        if connected:
            self.btn_connect.setText("Putuskan Kamera")
            self.btn_connect.setStyleSheet("background-color: #ecfdf5; border: 1px solid #10b981; color: #059669;")
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            res_info = f" ({self.worker.resolution_str})" if (self.worker and getattr(self.worker, 'resolution_str', '')) else ""
            self.pill_cam.setText(f"● Camera Connected{res_info}")
            self.pill_cam.setStyleSheet("background-color: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; border-radius: 14px; padding: 5px 12px; font-weight: 600; font-size: 11px;")
            self.lbl_cam_status.setText(f"● Linked{res_info}")
            self.lbl_cam_status.setStyleSheet("color: #059669; font-size: 11px; font-weight: 600;")
            self.lbl_ft_cam.setText(f"● Camera: Connected{res_info}")
            self.lbl_ft_cam.setStyleSheet("color: #059669; font-family: 'JetBrains Mono'; font-size: 11px;")
        else:
            self.btn_connect.setText("Hubungkan Kamera")
            self.btn_connect.setStyleSheet("")
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.lbl_video.setText("Kamera tidak terhubung.\nSilakan periksa pengaturan/IP lalu klik 'Hubungkan Kamera' lagi.")
            self.pill_cam.setText("● Camera Disconnected")
            self.pill_cam.setStyleSheet("background-color: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1; border-radius: 14px; padding: 5px 12px; font-weight: 600; font-size: 11px;")
            self.lbl_cam_status.setText("● No Signal")
            self.lbl_cam_status.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 600;")
            self.lbl_ft_cam.setText("● Camera: Disconnected")
            self.lbl_ft_cam.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 11px;")

            # Reset referensi worker agar siap untuk mencoba hubungkan ulang
            if self.worker and not self.worker.isRunning():
                self.worker = None

            if message and message != "Kamera terputus":
                QMessageBox.warning(self, "Gagal Menghubungkan Kamera", message)

    def on_frame_ready(self, q_img, raw_frame, frame_idx, current_fps):
        if q_img.isNull():
            return
        self.latest_raw_frame = raw_frame
        self.lbl_feed_frame.setText(f"Frame: {frame_idx:,}")
        if hasattr(self, 'pill_fps'):
            self.pill_fps.setText(f"{int(round(current_fps))} FPS")

        w = self.lbl_video.width()
        h = self.lbl_video.height()
        if w > 10 and h > 10:
            pixmap = QPixmap.fromImage(q_img)
            scaled_pixmap = pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_video.setPixmap(scaled_pixmap)

    # ── KALIBRASI ────────────────────────────────────────────────
    def open_calibration_dialog(self):
        if self.latest_raw_frame is None:
            QMessageBox.information(
                self, "Kalibrasi Skala",
                "Hubungkan kamera terlebih dahulu agar ada frame gambar yang dapat dikalibrasi."
            )
            return

        dlg = CalibrationDialog(self.latest_raw_frame, self.spin_scale.value(), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_scale = dlg.calculated_scale
            self.spin_scale.setValue(new_scale)
            if self.worker:
                self.worker.pixel_to_mm = new_scale
            self.lbl_calib_verified.setText("● Verified")
            self.lbl_calib_verified.setStyleSheet("color: #059669; font-size: 11px; font-weight: 600;")
            QMessageBox.information(
                self, "Kalibrasi Berhasil",
                f"Skala fisik berhasil diperbarui:\nPIXEL_TO_MM = {new_scale:.6f} mm/px"
            )

    # ── PENGUJIAN (START / STOP) ──────────────────────────────────
    def start_test(self):
        if not self.worker:
            return

        self.worker.set_parameters(
            ground_id=0,
            top_id=1,
            scale=self.spin_scale.value(),
            baseline_frames=30
        )

        self.time_buffer.clear()
        self.x_buffer.clear()
        self.y_buffer.clear()
        self.z_buffer.clear()
        self.curve_x.setData([], [])
        self.curve_y.setData([], [])
        self.curve_z.setData([], [])

        self.max_x = -float('inf')
        self.min_x = float('inf')
        self.max_y = -float('inf')
        self.min_y = float('inf')
        self.max_z = -float('inf')
        self.min_z = float('inf')
        self.sum_sq_x = 0.0
        self.sum_sq_y = 0.0
        self.sum_sq_z = 0.0
        self.count_samples = 0
        self.total_frames_seen = 0
        self.locked_frames_count = 0

        self.prog_baseline.setValue(0)
        self.lbl_tare_percent.setText("0% Calculating...")

        self.worker.start_recording()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_calib.setEnabled(False)

        self.pill_run.setText("ACTIVE RUN")
        self.pill_run.setStyleSheet(
            "background-color: #ecfdf5; color: #059669; "
            "border: 1px solid #a7f3d0; border-radius: 14px; "
            "padding: 5px 12px; font-weight: 800; font-size: 11px;"
        )
        self.lbl_run_tag.setText(f"RUN #{self.run_counter:03d}")

    def stop_test(self):
        if not self.worker:
            return

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_calib.setEnabled(True)

        self.pill_run.setText("STANDBY")
        self.pill_run.setStyleSheet(
            "background-color: #f1f5f9; color: #64748b; "
            "border: 1px solid #cbd5e1; border-radius: 14px; "
            "padding: 5px 12px; font-weight: 700; font-size: 11px;"
        )
        self.run_counter += 1

        summary = self.worker.stop_recording()
        # Jalankan ekspor file di antrian event loop berikutnya agar penanganan klik tombol selesai dulu
        QTimer.singleShot(60, lambda: self.on_test_finished(summary))

    def on_baseline_progress(self, current, total):
        self.prog_baseline.setValue(current)
        percent = int(current / total * 100)
        if current >= total:
            self.lbl_tare_percent.setText("100% Ready")
            self.lbl_tare_percent.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; color: #059669; font-weight: bold;")
        else:
            self.lbl_tare_percent.setText(f"{percent}% Tare...")
            self.lbl_tare_percent.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; color: #0284c7; font-weight: bold;")

    def on_new_data_point(self, now, frame_idx, disp_x, disp_y, disp_z, status, g_ok, t_ok):
        # 1. Update status marker di sidebar & footer
        self.total_frames_seen += 1
        locked_both = g_ok and t_ok
        if locked_both:
            self.locked_frames_count += 1

        self.badge_m0_status.setText("Locked" if g_ok else "Lost")
        self.badge_m0_status.setStyleSheet("background-color: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; border-radius: 10px; padding: 2px 7px; font-size: 9px; font-weight: 600; font-family: 'JetBrains Mono';" if g_ok else "background-color: #fef2f2; color: #ef4444; border: 1px solid #fecaca; border-radius: 10px; padding: 2px 7px; font-size: 9px; font-weight: 600; font-family: 'JetBrains Mono';")

        self.badge_m1_status.setText("Tracking" if t_ok else "Lost")
        self.badge_m1_status.setStyleSheet("background-color: #faf5ff; color: #9333ea; border: 1px solid #e9d5ff; border-radius: 10px; padding: 2px 7px; font-size: 9px; font-weight: 600; font-family: 'JetBrains Mono';" if t_ok else "background-color: #fef2f2; color: #ef4444; border: 1px solid #fecaca; border-radius: 10px; padding: 2px 7px; font-size: 9px; font-weight: 600; font-family: 'JetBrains Mono';")

        # Footer stats
        lock_rate = (self.locked_frames_count / max(1, self.total_frames_seen)) * 100.0
        self.lbl_lock_conf.setText(f"{lock_rate:.1f}%")
        self.lbl_ft_tracking.setText(f"Tracking: {lock_rate:.1f}%")
        m_count = (1 if g_ok else 0) + (1 if t_ok else 0)
        self.lbl_ft_markers.setText(f"Markers: {m_count}/2 Locked")

        # Timer format
        mins = int(now // 60)
        secs = int(now % 60)
        millis = int((now * 10) % 10)
        self.lbl_elapsed_time.setText(f"{mins:02d}:{secs:02d}.{millis:01d}")

        # 2. Buffer untuk grafik realtime scope
        self.time_buffer.append(now)
        self.x_buffer.append(disp_x)
        self.y_buffer.append(disp_y)
        self.z_buffer.append(disp_z)

        while self.time_buffer and now - self.time_buffer[0] > self.plot_window_sec:
            self.time_buffer.popleft()
            self.x_buffer.popleft()
            self.y_buffer.popleft()
            self.z_buffer.popleft()

        self.curve_x.setData(list(self.time_buffer), list(self.x_buffer))
        self.curve_y.setData(list(self.time_buffer), list(self.y_buffer))
        self.curve_z.setData(list(self.time_buffer), list(self.z_buffer))

        # 3. Update Hero Metrics
        self.count_samples += 1
        self.max_x = max(self.max_x, disp_x)
        self.min_x = min(self.min_x, disp_x)
        self.max_y = max(self.max_y, disp_y)
        self.min_y = min(self.min_y, disp_y)
        self.max_z = max(self.max_z, disp_z)
        self.min_z = min(self.min_z, disp_z)

        unit = "mm" if self.spin_scale.value() else "px"
        self.lbl_sway_val.setText(f"{disp_x:+.2f}")
        self.lbl_drop_val.setText(f"{disp_y:+.2f}")
        self.lbl_depth_val.setText(f"{disp_z:+.2f}")

        # Direction indicator
        if disp_x > 0.5:
            self.badge_sway_dir.setText("Right Sway")
            self.badge_sway_dir.setStyleSheet("color: #059669; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")
        elif disp_x < -0.5:
            self.badge_sway_dir.setText("Left Sway")
            self.badge_sway_dir.setStyleSheet("color: #0284c7; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")
        else:
            self.badge_sway_dir.setText("Centered")
            self.badge_sway_dir.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")

        # Z Direction indicator (Forward/Backward)
        if disp_z > 0.5:
            self.badge_depth_dir.setText("Forward (+Z)")
            self.badge_depth_dir.setStyleSheet("color: #ea580c; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")
        elif disp_z < -0.5:
            self.badge_depth_dir.setText("Backward (-Z)")
            self.badge_depth_dir.setStyleSheet("color: #d97706; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")
        else:
            self.badge_depth_dir.setText("Stable")
            self.badge_depth_dir.setStyleSheet("color: #64748b; font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600;")

        self.lbl_sway_limits.setText(f"Max: {self.max_x:+.2f} {unit}  |  Min: {self.min_x:+.2f} {unit}")
        self.lbl_drop_limits.setText(f"Max: {self.max_y:+.2f} {unit}  |  Min: {self.min_y:+.2f} {unit}")
        self.lbl_depth_limits.setText(f"Max: {self.max_z:+.2f} {unit}  |  Min: {self.min_z:+.2f} {unit}")

        # 4. Drift Ratio & Frekuensi Alami Dominan
        # Asumsi tinggi gedung referensi ~400mm jika belum spesifik, atau gunakan rasio displacement
        ref_h = 400.0
        drift_pct = (abs(disp_x) / ref_h) * 100.0
        self.lbl_drift_val.setText(f"{drift_pct:.2f}%")

        # Estimasi Frekuensi Alami Dominan f1 dari zero crossings
        if len(self.x_buffer) >= 30:
            arr_x = np.array(self.x_buffer)
            zero_crossings = np.where(np.diff(np.signbit(arr_x)))[0]
            duration = self.time_buffer[-1] - self.time_buffer[0]
            if duration > 1.0 and len(zero_crossings) > 2:
                freq = (len(zero_crossings) / 2.0) / duration
                self.lbl_freq_val.setText(f"{freq:.2f} Hz")

    # ── PENYIMPANAN & EKSPOR DATA ─────────────────────────────────
    def on_test_finished(self, summary):
        try:
            all_rows = summary.get("all_rows", [])
            if not all_rows:
                QMessageBox.warning(
                    self, "Hasil Pengujian",
                    "Tidak ada data displacement yang terekam.\n\n"
                    "Catatan:\n"
                    "• Pastikan kedua marker ArUco (#0 dan #1) terlihat kamera.\n"
                    "• Tunggu hingga proses tare baseline selesai (100%) sebelum menekan Stop."
                )
                return

            unit_label = "mm" if self.spin_scale.value() else "px"
            pos_unit = "mm" if self.spin_scale.value() else "piksel"
            disp_unit = "mm" if self.spin_scale.value() else "piksel"

            result_dir = os.path.abspath("result")
            os.makedirs(result_dir, exist_ok=True)

            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            excel_path = os.path.join(result_dir, f"data_gempa_{timestamp_str}.xlsx")
            csv_path = os.path.join(result_dir, f"data_gempa_{timestamp_str}.csv")
            txt_path = os.path.join(result_dir, f"tabel_data_gempa_{timestamp_str}.txt")
            png_path = os.path.join(result_dir, f"grafik_gempa_{timestamp_str}.png")

            headers = [
                "timestamp_s", "frame",
                f"ground_x_{unit_label}", f"ground_y_{unit_label}", f"ground_z_{unit_label}",
                f"top_x_{unit_label}", f"top_y_{unit_label}", f"top_z_{unit_label}",
                f"disp_x_{unit_label}", f"disp_y_{unit_label}", f"disp_z_{unit_label}",
                "status"
            ]
            units = [
                "[s]", "[frame#]",
                f"[{pos_unit}]", f"[{pos_unit}]", f"[{pos_unit}]",
                f"[{pos_unit}]", f"[{pos_unit}]", f"[{pos_unit}]",
                f"[{disp_unit}]", f"[{disp_unit}]", f"[{disp_unit}]",
                "[-]"
            ]

            saved_items = []
            errors = []

            # 1. Simpan CSV
            try:
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f, delimiter="|")
                    writer.writerow([
                        "# METADATA",
                        f"kalibrasi_PIXEL_TO_MM={self.spin_scale.value()}",
                        f"satuan_posisi={pos_unit}",
                        f"satuan_displacement={disp_unit}",
                        f"satuan_waktu=detik"
                    ])
                    writer.writerow(headers)
                    writer.writerow(units)
                    for r in all_rows:
                        writer.writerow(r)
                self.last_saved_csv = os.path.abspath(csv_path)
                saved_items.append(f"CSV: result/{os.path.basename(csv_path)}")
            except Exception as e:
                errors.append(f"CSV: {e}")

            # 2. Simpan Excel
            try:
                if export_to_excel(excel_path, headers, units, all_rows):
                    self.last_saved_excel = os.path.abspath(excel_path)
                    self.btn_open_excel.setEnabled(True)
                    saved_items.append(f"Excel: result/{os.path.basename(excel_path)}")
            except Exception as e:
                errors.append(f"Excel: {e}")

            # 3. Simpan TXT
            try:
                if save_txt_table(txt_path, headers, all_rows, self.spin_scale.value(), summary.get("total_frames", 0)):
                    saved_items.append(f"Tabel: result/{os.path.basename(txt_path)}")
            except Exception as e:
                errors.append(f"TXT: {e}")

            # 4. Simpan PNG (3 Sumbu: X, Y, Z)
            try:
                if save_png_plot(png_path, summary.get("t_all", []), summary.get("x_all", []), summary.get("y_all", []), summary.get("z_all", []), unit_label):
                    self.last_saved_png = os.path.abspath(png_path)
                    self.btn_open_png.setEnabled(True)
                    saved_items.append(f"Grafik: result/{os.path.basename(png_path)}")
            except Exception as e:
                errors.append(f"PNG: {e}")

            elapsed_str = self.lbl_elapsed_time.text() if hasattr(self, 'lbl_elapsed_time') else "-"
            summary_files = "\n• " + "\n• ".join(saved_items) if saved_items else "Gagal menyimpan berkas."
            err_msg = f"\n\n⚠ Catatan peringatan: {', '.join(errors)}" if errors else ""

            # Dialog Sukses
            QMessageBox.information(
                self, "Pengujian Selesai",
                f"Data simulasi getaran gedung berhasil direkam & diekspor ke folder 'result'!\n"
                f"{summary_files}\n\n"
                f"Total Frame Terekam: {summary.get('total_frames', 0):,}\n"
                f"Durasi Uji: {elapsed_str} detik"
                f"{err_msg}"
            )
        except Exception as ex:
            QMessageBox.critical(
                self, "Peringatan Penyimpanan",
                f"Terjadi kesalahan saat memproses hasil pengujian:\n{ex}\n\nAplikasi tetap berjalan normal."
            )

    def open_output_folder(self):
        result_dir = os.path.abspath("result")
        os.makedirs(result_dir, exist_ok=True)
        os.startfile(result_dir)

    def open_file(self, file_path):
        if file_path and os.path.exists(file_path):
            os.startfile(file_path)
        else:
            QMessageBox.warning(self, "Buka File", "File belum tersedia atau belum disimpan.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop_worker()
            self.worker.wait(400)
        event.accept()


# =====================================================================
# ENTRY POINT UTAMA
# =====================================================================
def main():
    # ── Paksa Windows tampilkan ikon aplikasi kustom di taskbar ──────
    # Tanpa ini, Windows menampilkan ikon python.exe, bukan ikon app kita.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ShakeLab.v2_4"
        )
    except Exception:
        pass  # Tidak berpengaruh di non-Windows

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set light palette secara eksplisit agar dialog OS / QMessageBox tidak gelap di Windows Dark Mode
    from PyQt6.QtGui import QPalette
    light_palette = QPalette()
    light_palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    light_palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
    light_palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fafc"))
    light_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    light_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f172a"))
    light_palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
    light_palette.setColor(QPalette.ColorRole.Button, QColor("#f1f5f9"))
    light_palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0f172a"))
    light_palette.setColor(QPalette.ColorRole.BrightText, QColor("#ef4444"))
    light_palette.setColor(QPalette.ColorRole.Link, QColor("#0284c7"))
    light_palette.setColor(QPalette.ColorRole.Highlight, QColor("#0284c7"))
    light_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(light_palette)

    app.setStyleSheet(MODERN_STYLE)

    # Ikon aplikasi global (muncul di taskbar Windows & Alt+Tab)
    # Gunakan .ico untuk taskbar agar resolusi optimal di semua ukuran
    _ico_path = get_resource_path("logo.ico")
    _png_path = get_resource_path("logo.png")
    if os.path.exists(_ico_path):
        app.setWindowIcon(QIcon(_ico_path))
    elif os.path.exists(_png_path):
        app.setWindowIcon(QIcon(_png_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
