"""
Program Deteksi Pergerakan Marker - Uji Gempa Miniatur Gedung
================================================================
Melacak 2 marker ArUco secara realtime:
  - Marker GROUND (statis, di tanah/luar meja gempa) -> titik acuan
  - Marker TOP    (di puncak gedung, ikut bergoncang)

Menghitung displacement relatif TOP terhadap GROUND setiap frame,
menampilkan grafik live, dan menyimpan data ke CSV untuk analisis
lanjutan (FFT, story drift, damping ratio, dll).

Kebutuhan:
    pip install opencv-python numpy matplotlib

Cara pakai:
    1. Tempel marker_0_ground.png di titik acuan tanah
    2. Tempel marker_1_top.png di puncak miniatur gedung
    3. Kalibrasi PIXEL_TO_MM (lihat instruksi di bawah)
    4. Jalankan script ini SEBELUM meja gempa mulai bergerak,
       agar frame-frame awal jadi baseline kondisi diam
    5. Tekan 'q' untuk berhenti & menyimpan data
"""

import os
import cv2
import numpy as np
import csv
import time
from collections import deque

import matplotlib
matplotlib.use("TkAgg")  # ganti ke "Qt5Agg" kalau TkAgg error di sistemmu
import matplotlib.pyplot as plt
from measurement_quality import assess_baseline, lowpass_step

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# ── PILIHAN KAMERA (WEBCAM USB / KAMERA HP VIA IP) ──
# 1. Jika menggunakan Kamera HP lewat IP (misal: IP Webcam, DroidCam, dll):
#    Ubah USE_IP_CAMERA = True dan sesuaikan IP_CAMERA_URL
#    Contoh aplikasi "IP Webcam" di Android : "http://192.168.1.15:8080/video"
#    Contoh aplikasi "DroidCam" di Android/iOS: "http://192.168.1.15:4747/video"
USE_IP_CAMERA = True
IP_CAMERA_URL = "http://192.168.1.193:4747/video"

# 2. Jika menggunakan Webcam bawaan laptop / USB:
CAMERA_INDEX = 1
GROUND_MARKER_ID = 0
TOP_MARKER_ID = 1

# Kalibrasi piksel -> mm.
# Cara isi: taruh penggaris sejajar bidang gerak di frame, ukur berapa
# piksel = berapa mm, lalu isi di sini. Kalau belum sempat kalibrasi,
# biarkan None -> program tetap jalan tapi satuan tetap piksel.
PIXEL_TO_MM = 0.265   # contoh: 100mm / 378px ≈ 0.265 mm/px (layar 96dpi)

BASELINE_FRAMES = 60      # indikator progres tare; kestabilan juga diverifikasi selama >=2 detik
MAX_MISSING_FRAMES = 10   # toleransi berapa frame boleh "hilang" sebelum dianggap gap
PLOT_WINDOW_SEC = 10       # rentang waktu yang ditampilkan di grafik live (detik)

RESULT_DIR = os.path.abspath("result")
os.makedirs(RESULT_DIR, exist_ok=True)

OUTPUT_EXCEL  = os.path.join(RESULT_DIR, "data_gempa.xlsx")     # Spreadsheet Excel dengan kotak-kotak tabel (grid lines)
OUTPUT_CSV    = os.path.join(RESULT_DIR, "data_gempa.csv")      # File CSV
CSV_DELIMITER = "|"                                           # Pemisah CSV: garis vertikal (|)
OUTPUT_TABLE  = os.path.join(RESULT_DIR, "tabel_data_gempa.txt") # File tabel bergaris text
OUTPUT_PLOT   = os.path.join(RESULT_DIR, "grafik_gempa.png")     # Grafik hasil simulasi PNG


# SETUP ARUCO

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)


def export_to_excel(filename, headers, units, rows):
    """Simpan data ke file Excel (.xlsx) dengan tabel dan kotak-kotak sel bergaris."""
    if not HAS_OPENPYXL:
        return
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

        # Header baris 1
        for col_idx, col_name in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border

        # Header baris 2 (satuan)
        for col_idx, unit in enumerate(units, 1):
            cell = ws.cell(row=2, column=col_idx, value=unit)
            cell.font = unit_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border

        # Data baris 3 dst
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
        print(f"File Excel (bergaris) di   : {filename}")
    except PermissionError:
        alt_xlsx = f"data_gempa_{int(time.time())}.xlsx"
        wb.save(alt_xlsx)
        print(f"PERINGATAN: '{filename}' sedang dibuka. Disimpan ke: {alt_xlsx}")
    except Exception as e:
        print(f"Catatan: Gagal menyimpan Excel: {e}")


def get_marker_centers(corners, ids):
    """Kembalikan dict {id: (cx, cy)} dan dict {id: size} dari hasil deteksi."""
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
    return centers, sizes



# MAIN LOOP

def main():
    if USE_IP_CAMERA:
        print(f"Menghubungkan ke IP Camera HP: {IP_CAMERA_URL} ...")
        cap = cv2.VideoCapture(IP_CAMERA_URL)
    else:
        print(f"Membuka kamera USB/Laptop (Index: {CAMERA_INDEX}) ...")
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)  # CAP_DSHOW lebih stabil di Windows

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        if USE_IP_CAMERA:
            print(f"\nERROR: Kamera HP di '{IP_CAMERA_URL}' tidak bisa dibuka!")
            print("Tips:")
            print("  1. Pastikan HP dan laptop/PC terhubung ke jaringan Wi-Fi / hotspot yang sama.")
            print("  2. Pastikan aplikasi kamera HP (seperti IP Webcam) sudah di-Start Server.")
            print("  3. Pastikan URL IP dan port-nya sudah benar (contoh: http://192.168.1.15:8080/video).")
        else:
            print(f"\nERROR: Kamera index {CAMERA_INDEX} tidak bisa dibuka. Cek CAMERA_INDEX atau ubah USE_IP_CAMERA = True jika menggunakan HP.")
        return

    csv_path = OUTPUT_CSV
    try:
        csv_file = open(csv_path, "w", newline="")
    except PermissionError:
        csv_path = os.path.join(RESULT_DIR, f"data_gempa_{int(time.time())}.csv")
        print(f"PERINGATAN: '{OUTPUT_CSV}' sedang dibuka di Excel/program lain.")
        print(f"Data CSV dialihkan ke: {csv_path}")
        csv_file = open(csv_path, "w", newline="")

    writer = csv.writer(csv_file, delimiter=CSV_DELIMITER)
    unit_label = "mm" if PIXEL_TO_MM else "px"
    pos_unit  = "mm"  if PIXEL_TO_MM else "piksel"
    disp_unit = "mm"  if PIXEL_TO_MM else "piksel"

    header_cols = [
        "timestamp_s", "frame",
        f"ground_x_{unit_label}", f"ground_y_{unit_label}", f"ground_z_{unit_label}",
        f"top_x_{unit_label}", f"top_y_{unit_label}", f"top_z_{unit_label}",
        f"disp_x_{unit_label}", f"disp_y_{unit_label}", f"disp_z_{unit_label}",
        "status"
    ]
    unit_cols = [
        "[s]", "[frame#]",
        f"[{pos_unit}]", f"[{pos_unit}]", f"[{pos_unit}]",
        f"[{pos_unit}]", f"[{pos_unit}]", f"[{pos_unit}]",
        f"[{disp_unit}]", f"[{disp_unit}]", f"[{disp_unit}]",
        "[-]"
    ]

    # ── Baris 1: metadata ringkas ────────────────────────────────────────
    writer.writerow([
        "# METADATA",
        f"kalibrasi_PIXEL_TO_MM={PIXEL_TO_MM}",
        f"satuan_posisi={pos_unit}",
        f"satuan_displacement={disp_unit}",
        f"satuan_waktu=detik",
        f"baseline_frames={BASELINE_FRAMES}",
    ])

    # ── Baris 2: nama kolom ──────────────────────────────────────────────
    writer.writerow(header_cols)

    # ── Baris 3: keterangan satuan setiap kolom ──────────────────────────
    writer.writerow(unit_cols)

    # Baseline (posisi relatif saat gedung diam)
    baseline_samples = []
    baseline_rel = None
    filtered_x, filtered_y = None, None
    filter_time = None

    # Origin posisi absolut — agar ground_x/y dan top_x/y dimulai dari 0
    origin_ground = None   # (gx0, gy0) posisi awal ground dalam satuan fisik
    origin_top    = None   # (tx0, ty0) posisi awal top dalam satuan fisik

    # Buffer untuk plot live (hanya window terakhir)
    t_buffer = deque()
    x_buffer = deque()
    y_buffer = deque()
    z_buffer = deque()

    # Buffer penuh — menyimpan SELURUH riwayat untuk grafik akhir & tabel
    t_all = []
    x_all = []
    y_all = []
    z_all = []
    all_rows = []

    # State terakhir yang valid (untuk menutup gap deteksi singkat)
    last_ground, last_top = None, None
    last_ground_size, last_top_size = None, None
    missing_count = 0

    # Setup plot live
    plt.ion()
    fig, ax = plt.subplots(figsize=(9, 5))
    line_x, = ax.plot([], [], label=f"Displacement X ({unit_label})", color="crimson")
    line_y, = ax.plot([], [], label=f"Displacement Y ({unit_label})", color="royalblue")
    line_z, = ax.plot([], [], label=f"Displacement Z ({unit_label})", color="darkorange")
    ax.set_xlabel("Waktu (s)")
    ax.set_ylabel(f"Displacement ({unit_label})")
    ax.set_title("Respons Gedung Realtime (X, Y, Z) - Uji Gempa")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    frame_idx = 0
    t0 = time.time()

    print("Merekam... frame awal dipakai sebagai baseline kondisi diam.")
    print("Tekan 'q' pada jendela video untuk berhenti.\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Gagal membaca frame dari kamera.")
                break

            now = time.time() - t0
            corners, ids, _ = detector.detectMarkers(frame)
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            centers, sizes = get_marker_centers(corners, ids)

            ground_pos = centers.get(GROUND_MARKER_ID)
            top_pos = centers.get(TOP_MARKER_ID)
            ground_size = sizes.get(GROUND_MARKER_ID)
            top_size = sizes.get(TOP_MARKER_ID)

            status = "ok"
            if ground_pos is None or top_pos is None:
                # Marker hilang sementara -> pakai posisi terakhir yang valid
                missing_count += 1
                status = "interpolated" if missing_count <= MAX_MISSING_FRAMES else "missing"
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

            # Posisi interpolasi dipakai hanya agar tampilan tidak putus; tidak
            # ikut menjadi baseline, statistik, maupun data ekspor.
            if ground_pos and top_pos and status == "ok":
                rel_x = top_pos[0] - ground_pos[0]
                rel_y = top_pos[1] - ground_pos[1]

                # Kumpulkan baseline dari frame-frame paling awal (kondisi diam)
                if baseline_rel is None:
                    baseline_samples.append((now, rel_x, rel_y, ground_size or 50.0, top_size or 50.0))
                    if len(baseline_samples) > 120:
                        baseline_samples.pop(0)
                    baseline_result = assess_baseline(
                        [s[0] for s in baseline_samples],
                        [s[1] for s in baseline_samples],
                        [s[2] for s in baseline_samples],
                        PIXEL_TO_MM or 1.0,
                    )
                    if baseline_result["valid"]:
                        arr = np.array(baseline_samples)
                        baseline_rel = (baseline_result["baseline_x_px"], baseline_result["baseline_y_px"])
                        baseline_sizes = (arr[:, 3].mean(), arr[:, 4].mean())

                        # Simpan posisi absolut awal sebagai origin (titik nol)
                        scale0 = PIXEL_TO_MM if PIXEL_TO_MM else 1.0
                        origin_ground = (ground_pos[0] * scale0, ground_pos[1] * scale0)
                        origin_top    = (top_pos[0]    * scale0, top_pos[1]    * scale0)
                        print(f"Baseline terkalibrasi: XY={baseline_rel}, Sizes={baseline_sizes}")
                        print(f"Origin ground: {origin_ground}, Origin top: {origin_top}")

                if baseline_rel is not None:
                    disp_x = rel_x - baseline_rel[0]
                    disp_y = rel_y - baseline_rel[1]

                    if PIXEL_TO_MM:
                        disp_x *= PIXEL_TO_MM
                        disp_y *= PIXEL_TO_MM

                    dt_s = now - filter_time if filter_time is not None else 0.0
                    filtered_x = lowpass_step(disp_x, filtered_x, dt_s)
                    filtered_y = lowpass_step(disp_y, filtered_y, dt_s)
                    filter_time = now
                    disp_x, disp_y = filtered_x, filtered_y

                    # Konversi posisi absolut ke satuan fisik, lalu normalisasi ke 0
                    scale = PIXEL_TO_MM if PIXEL_TO_MM else 1.0
                    g_x_abs = ground_pos[0] * scale
                    g_y_abs = ground_pos[1] * scale
                    t_x_abs = top_pos[0]    * scale
                    t_y_abs = top_pos[1]    * scale

                    # Kurangi dengan origin agar posisi dimulai dari 0
                    if origin_ground is not None and origin_top is not None:
                        g_x = g_x_abs - origin_ground[0]
                        g_y = g_y_abs - origin_ground[1]
                        t_x = t_x_abs - origin_top[0]
                        t_y = t_y_abs - origin_top[1]
                    else:
                        g_x, g_y = g_x_abs, g_y_abs
                        t_x, t_y = t_x_abs, t_y_abs

                    # Sumbu Z (Out-of-Plane)
                    w_frame = frame.shape[1]
                    focal_px = 0.85 * w_frame
                    z_ref = focal_px * scale
                    bg_s, bt_s = baseline_sizes if 'baseline_sizes' in locals() else (50.0, 50.0)
                    g_z = z_ref * ((bg_s / max(ground_size or bg_s, 1e-3)) - 1.0)
                    t_z = z_ref * ((bt_s / max(top_size or bt_s, 1e-3)) - 1.0)
                    disp_z = t_z - g_z

                    row_data = [f"{now:.4f}", frame_idx,
                                f"{g_x:.3f}", f"{g_y:.3f}", f"{g_z:.3f}",
                                f"{t_x:.3f}", f"{t_y:.3f}", f"{t_z:.3f}",
                                f"{disp_x:.3f}", f"{disp_y:.3f}", f"{disp_z:.3f}", status]
                    writer.writerow(row_data)
                    all_rows.append(row_data)

                    # Update buffer plot live (hanya simpan window terakhir)
                    t_buffer.append(now)
                    x_buffer.append(disp_x)
                    y_buffer.append(disp_y)
                    z_buffer.append(disp_z)
                    while t_buffer and now - t_buffer[0] > PLOT_WINDOW_SEC:
                        t_buffer.popleft()
                        x_buffer.popleft()
                        y_buffer.popleft()
                        z_buffer.popleft()

                    # Simpan ke buffer penuh
                    t_all.append(now)
                    x_all.append(disp_x)
                    y_all.append(disp_y)
                    z_all.append(disp_z)

                    # Overlay info di video
                    cv2.line(frame, (int(ground_pos[0]), int(ground_pos[1])),
                              (int(top_pos[0]), int(top_pos[1])), (0, 255, 255), 2)
                    cv2.putText(frame, f"dX:{disp_x:+.2f} dY:{disp_y:+.2f} dZ:{disp_z:+.2f}{unit_label}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                else:
                    cv2.putText(frame, "Mengkalibrasi baseline... jangan digoyang dulu",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            else:
                cv2.putText(frame, "Marker tidak terdeteksi!", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # Refresh plot tiap beberapa frame saja (biar tidak nge-lag)
            if frame_idx % 3 == 0 and len(t_buffer) > 1:
                line_x.set_data(t_buffer, x_buffer)
                line_y.set_data(t_buffer, y_buffer)
                line_z.set_data(t_buffer, z_buffer)
                ax.set_xlim(max(0, now - PLOT_WINDOW_SEC), max(now, PLOT_WINDOW_SEC))
                ax.relim()
                ax.autoscale_view(scalex=False)
                fig.canvas.draw_idle()
                fig.canvas.flush_events()

            cv2.imshow("Uji Gempa - Tracking Realtime (tekan q untuk stop)", frame)
            frame_idx += 1

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        csv_file.close()
        plt.ioff()

        # ── Simpan tabel bergaris ke file TXT ─────────────────────────────
        if all_rows:
            headers = [
                "Waktu (s)", "Frame#",
                f"Ground X ({unit_label})", f"Ground Y ({unit_label})", f"Ground Z ({unit_label})",
                f"Top X ({unit_label})", f"Top Y ({unit_label})", f"Top Z ({unit_label})",
                f"Disp X ({unit_label})", f"Disp Y ({unit_label})", f"Disp Z ({unit_label})",
                "Status"
            ]
            col_widths = [len(h) for h in headers]
            for r in all_rows:
                for i, val in enumerate(r):
                    col_widths[i] = max(col_widths[i], len(str(val)))

            sep_line = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"

            with open(OUTPUT_TABLE, "w", encoding="utf-8") as tf:
                tf.write("HASIL SIMULASI UJI GEMPA - DATA DISPLACEMENT\n")
                tf.write(f"Kalibrasi: {PIXEL_TO_MM} mm/px | Total Frame: {frame_idx}\n\n")
                tf.write(sep_line + "\n")
                # Header
                hdr_str = "|" + "|".join([f" {headers[i]:^{col_widths[i]}} " for i in range(len(headers))]) + "|"
                tf.write(hdr_str + "\n")
                tf.write(sep_line + "\n")
                # Rows dengan garis pemisah
                for r in all_rows:
                    row_str = "|" + "|".join([f" {str(r[i]):>{col_widths[i]}} " if i < len(r)-1 else f" {str(r[i]):^{col_widths[i]}} " for i in range(len(r))]) + "|"
                    tf.write(row_str + "\n")
                tf.write(sep_line + "\n")
            print(f"Tabel bergaris tersimpan di: {OUTPUT_TABLE}")

        # ── Simpan grafik hasil simulasi ke file PNG ──────────────────────
        if len(t_all) > 1:
            fig_save, ax_save = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
            fig_save.suptitle("Hasil Simulasi Uji Gempa — Displacement Marker (X, Y, Z)",
                              fontsize=14, fontweight="bold")

            ax_save[0].plot(t_all, x_all, color="crimson", linewidth=0.8)
            ax_save[0].set_ylabel(f"Displacement X ({unit_label})")
            ax_save[0].grid(True, alpha=0.3)
            ax_save[0].axhline(0, color="gray", linewidth=0.6, linestyle="--")

            ax_save[1].plot(t_all, y_all, color="royalblue", linewidth=0.8)
            ax_save[1].set_ylabel(f"Displacement Y ({unit_label})")
            ax_save[1].grid(True, alpha=0.3)
            ax_save[1].axhline(0, color="gray", linewidth=0.6, linestyle="--")

            ax_save[2].plot(t_all, z_all, color="darkorange", linewidth=0.8)
            ax_save[2].set_ylabel(f"Displacement Z ({unit_label})")
            ax_save[2].set_xlabel("Waktu (s)")
            ax_save[2].grid(True, alpha=0.3)
            ax_save[2].axhline(0, color="gray", linewidth=0.6, linestyle="--")

            # Anotasi statistik ringkas di tiap subplot
            for ax_s, vals, lbl in zip(ax_save, [x_all, y_all, z_all], ["X", "Y", "Z"]):
                arr = np.array(vals)
                txt = (f"max={arr.max():.2f}  min={arr.min():.2f}  "
                       f"RMS={np.sqrt(np.mean(arr**2)):.2f} {unit_label}")
                ax_s.annotate(txt, xy=(0.01, 0.95), xycoords="axes fraction",
                              fontsize=8, va="top",
                              bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

            fig_save.tight_layout()
            fig_save.savefig(OUTPUT_PLOT, dpi=150)
            plt.close(fig_save)
            print(f"Grafik tersimpan di        : {OUTPUT_PLOT}")
        else:
            print("Tidak ada data yang cukup untuk menyimpan grafik.")

        # ── Simpan file Excel (.xlsx) dengan garis-garis sel (grid borders) 
        if all_rows:
            export_to_excel(OUTPUT_EXCEL, header_cols, unit_cols, all_rows)

        plt.close(fig)
        print(f"Data CSV tersimpan di      : {csv_path}")
        print(f"Total frame terekam        : {frame_idx}")


if __name__ == "__main__":
    main()
