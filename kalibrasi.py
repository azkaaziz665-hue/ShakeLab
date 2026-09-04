"""
Script Kalibrasi PIXEL_TO_MM
==============================
Cara pakai:
  1. Letakkan penggaris FISIK di depan kamera, sejajar arah gerak gedung
  2. Jalankan script ini: py kalibrasi.py
  3. Tekan SPACE untuk membekukan frame (atau live klik langsung)
  4. Klik Titik 1 (awal) -> Klik Titik 2 (akhir) pada penggaris
  5. Kotak dialog popup akan muncul untuk memasukkan jarak fisik (mm)
  6. Hasil perhitungan mm/px akan langsung muncul di layar dan terminal
  7. Tekan 'r' untuk reset titik, 'q' atau ESC untuk keluar
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import simpledialog

# ── PILIHAN KAMERA (WEBCAM USB / KAMERA HP VIA IP) ──
# 1. Jika menggunakan Kamera HP lewat IP (misal: IP Webcam, DroidCam, dll):
#    Ubah USE_IP_CAMERA = True dan sesuaikan IP_CAMERA_URL
#    Contoh aplikasi "IP Webcam" di Android : "http://192.168.1.15:8080/video"
#    Contoh aplikasi "DroidCam" di Android/iOS: "http://192.168.1.15:4747/video"
USE_IP_CAMERA = True
IP_CAMERA_URL = "http://192.168.18.15:4747/video"
# 2. Jika menggunakan Webcam bawaan laptop / USB:
CAMERA_INDEX = 0   # Ganti jika kamera bukan index 0

# ──────────────────────────────────────────────
# State global
# ──────────────────────────────────────────────
clicks = []
frozen_frame = None
last_result = None  # Menyimpan hasil kalibrasi terakhir untuk ditampilkan di layar


def on_mouse(event, x, y, flags, param):
    global clicks
    if event == cv2.EVENT_LBUTTONDOWN and len(clicks) < 2:
        clicks.append((x, y))
        print(f"  Titik {len(clicks)} dipilih: ({x}, {y}) px")


def draw_ui(frame, frozen):
    disp = frame.copy()

    # Gambar titik yang sudah diklik
    for i, (px, py) in enumerate(clicks):
        cv2.circle(disp, (px, py), 6, (0, 255, 0), -1)
        cv2.putText(disp, f"P{i+1}", (px + 8, py - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # Gambar garis jika sudah 2 titik
    if len(clicks) == 2:
        cv2.line(disp, clicks[0], clicks[1], (0, 220, 255), 2)
        dist_px = float(np.linalg.norm(np.array(clicks[1]) - np.array(clicks[0])))
        mid_x = (clicks[0][0] + clicks[1][0]) // 2
        mid_y = (clicks[0][1] + clicks[1][1]) // 2 - 10
        cv2.putText(disp, f"{dist_px:.1f} px", (mid_x, mid_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 2)

    # Status frame & instruksi
    status_text = "[FRAME BEKU]" if frozen else "[LIVE VIDEO]"
    status_color = (0, 215, 255) if frozen else (0, 255, 0)
    cv2.putText(disp, status_text, (disp.shape[1] - 170, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

    instructions = [
        "1. Tekan SPACE untuk bekukan/lepas frame",
        "2. Klik 2 titik pada penggaris (P1 -> P2)",
        "3. Tekan 'r' untuk RESET titik | 'q' / ESC untuk KELUAR",
    ]
    for i, text in enumerate(instructions):
        cv2.putText(disp, text, (10, 25 + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 100), 1)

    # Tampilkan hasil kalibrasi jika sudah ada
    if last_result:
        res_box_y = disp.shape[0] - 50
        cv2.rectangle(disp, (10, res_box_y - 25), (disp.shape[1] - 10, disp.shape[0] - 10), (0, 0, 0), -1)
        cv2.rectangle(disp, (10, res_box_y - 25), (disp.shape[1] - 10, disp.shape[0] - 10), (0, 255, 0), 2)
        res_str = f"HASIL: PIXEL_TO_MM = {last_result['pixel_to_mm']:.6f} mm/px ({last_result['dist_mm']:.1f} mm / {last_result['dist_px']:.1f} px)"
        cv2.putText(disp, res_str, (20, res_box_y + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

    return disp


def ask_distance_dialog(dist_px):
    """Buka popup dialog input angka mm yang tidak membuat window not responding."""
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        dist_mm = simpledialog.askfloat(
            title="Input Jarak Penggaris",
            prompt=f"Jarak terukur di layar: {dist_px:.2f} piksel\n\nMasukkan jarak fisik asli antara 2 titik (dalam mm):",
            parent=root,
            minvalue=0.1,
            maxvalue=10000.0
        )
        root.destroy()
        return dist_mm
    except Exception as e:
        print(f"Dialog error: {e}")
        return None


def main():
    global frozen_frame, clicks, last_result

    if USE_IP_CAMERA:
        print(f"Menghubungkan ke IP Camera HP: {IP_CAMERA_URL} ...")
        cap = cv2.VideoCapture(IP_CAMERA_URL)
    else:
        print(f"Membuka kamera USB/Laptop (Index: {CAMERA_INDEX}) ...")
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)  # CAP_DSHOW stabil di Windows

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

    window_name = "Kalibrasi PIXEL_TO_MM"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)

    print("\n" + "="*50)
    print("           PROGRAM KALIBRASI PIXEL_TO_MM")
    print("="*50)
    print("1. Letakkan penggaris fisik di depan kamera.")
    print("2. Tekan SPACE untuk membekukan frame gambar.")
    print("3. Klik Titik 1 dan Titik 2 pada penggaris.")
    print("4. Masukkan jarak milimeter pada kotak dialog yang muncul.")
    print("5. Tekan 'r' untuk reset titik, 'q' atau ESC untuk selesai.\n")

    frozen = False
    calculating = False

    while True:
        if not frozen:
            ret, frame = cap.read()
            if not ret:
                print("Gagal membaca frame dari kamera.")
                break
            frozen_frame = frame.copy()

        display = draw_ui(frozen_frame, frozen)
        cv2.imshow(window_name, display)

        # Cek jika window ditutup dengan tombol silang (X)
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            print("Jendela kalibrasi ditutup.")
            break

        key = cv2.waitKey(15) & 0xFF

        # Tombol ESC atau 'q' untuk keluar
        if key in [27, ord('q'), ord('Q')]:
            print("Kalibrasi selesai/ditutup.")
            break

        # Tombol SPACE untuk bekukan / aktifkan kembali live camera
        elif key == ord(' '):
            frozen = not frozen
            clicks = []
            if frozen:
                print(">> Frame dibekukan. Silakan klik 2 titik pada penggaris.")
            else:
                print(">> Live video aktif kembali.")

        # Tombol 'r' untuk reset klik
        elif key in [ord('r'), ord('R')]:
            clicks = []
            last_result = None
            print(">> Titik di-reset. Silakan klik ulang 2 titik.")

        # Jika sudah 2 titik dan belum memproses dialog
        if len(clicks) == 2 and not calculating:
            calculating = True
            dist_px = float(np.linalg.norm(np.array(clicks[1]) - np.array(clicks[0])))
            
            # Refresh tampilan agar garis dan titik terlihat sebelum dialog muncul
            display = draw_ui(frozen_frame, frozen)
            cv2.imshow(window_name, display)
            cv2.waitKey(50)

            print(f"\nJarak piksel: {dist_px:.2f} px")
            print("Silakan isi jarak fisik (mm) pada kotak dialog popup...")

            dist_mm = ask_distance_dialog(dist_px)

            if dist_mm is not None and dist_mm > 0:
                pixel_to_mm = dist_mm / dist_px
                last_result = {
                    "pixel_to_mm": pixel_to_mm,
                    "dist_mm": dist_mm,
                    "dist_px": dist_px
                }
                print("\n" + "="*50)
                print("             HASIL KALIBRASI")
                print("="*50)
                print(f"  Jarak fisik   : {dist_mm:.1f} mm")
                print(f"  Jarak piksel  : {dist_px:.2f} px")
                print(f"  PIXEL_TO_MM   : {pixel_to_mm:.6f} mm/px")
                print("="*50)
                print("\nSalin nilai ini ke marker.py (baris PIXEL_TO_MM):")
                print(f"PIXEL_TO_MM = {pixel_to_mm:.6f}   # {dist_mm:.0f}mm / {dist_px:.1f}px\n")
            else:
                print("Input dibatalkan. Tekan 'r' untuk reset atau klik ulang.")
                clicks = []

            calculating = False

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

