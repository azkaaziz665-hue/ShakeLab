"""Generate a printable checkerboard for ShakeLab camera calibration.

The default board matches the in-app camera calibration dialog:
9 x 6 inner corners and 20 mm squares.
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


MM_PER_INCH = 25.4


def build_checkerboard(inner_cols: int, inner_rows: int, square_mm: float, dpi: int, border_squares: int):
    """Return a checkerboard image and its physical dimensions in millimetres."""
    if inner_cols < 3 or inner_rows < 3:
        raise ValueError("Jumlah sudut dalam minimal 3 x 3.")
    if square_mm <= 0 or dpi <= 0 or border_squares < 0:
        raise ValueError("Ukuran kotak, DPI, dan border harus valid.")

    squares_x = inner_cols + 1
    squares_y = inner_rows + 1
    square_px = round(square_mm / MM_PER_INCH * dpi)
    total_x = squares_x + 2 * border_squares
    total_y = squares_y + 2 * border_squares

    image = np.full((total_y * square_px, total_x * square_px), 255, dtype=np.uint8)
    for row in range(squares_y):
        for col in range(squares_x):
            if (row + col) % 2 == 0:
                y0 = (row + border_squares) * square_px
                x0 = (col + border_squares) * square_px
                image[y0:y0 + square_px, x0:x0 + square_px] = 0

    width_mm = total_x * square_mm
    height_mm = total_y * square_mm
    return image, width_mm, height_mm


def save_checkerboard(output_stem: Path, image: np.ndarray, width_mm: float, height_mm: float, dpi: int):
    """Save a PNG and a PDF at the requested physical print size."""
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    png_path = output_stem.with_suffix(".png")
    pdf_path = output_stem.with_suffix(".pdf")

    figure = plt.figure(figsize=(width_mm / MM_PER_INCH, height_mm / MM_PER_INCH), dpi=dpi)
    axes = figure.add_axes([0, 0, 1, 1])
    axes.imshow(image, cmap="gray", vmin=0, vmax=255, interpolation="nearest")
    axes.axis("off")
    figure.savefig(png_path, dpi=dpi, pad_inches=0, facecolor="white")
    figure.savefig(pdf_path, dpi=dpi, pad_inches=0, facecolor="white")
    plt.close(figure)
    return png_path, pdf_path


def main():
    parser = argparse.ArgumentParser(description="Buat papan checkerboard untuk kalibrasi kamera ShakeLab.")
    parser.add_argument("--inner-cols", type=int, default=9, help="Jumlah sudut dalam arah horizontal.")
    parser.add_argument("--inner-rows", type=int, default=6, help="Jumlah sudut dalam arah vertikal.")
    parser.add_argument("--square-mm", type=float, default=20.0, help="Panjang sisi satu kotak saat dicetak.")
    parser.add_argument("--dpi", type=int, default=300, help="Resolusi berkas cetak.")
    parser.add_argument("--border-squares", type=int, default=1, help="Lebar margin putih dalam satuan kotak.")
    parser.add_argument("--output", default="checkerboard_9x6_20mm", help="Nama berkas tanpa ekstensi.")
    args = parser.parse_args()

    image, width_mm, height_mm = build_checkerboard(
        args.inner_cols, args.inner_rows, args.square_mm, args.dpi, args.border_squares
    )
    png_path, pdf_path = save_checkerboard(Path(args.output), image, width_mm, height_mm, args.dpi)
    print(f"PNG: {png_path.resolve()}")
    print(f"PDF: {pdf_path.resolve()}")
    print(f"Ukuran cetak: {width_mm:.1f} x {height_mm:.1f} mm")
    print("Cetak PDF pada skala 100% / Actual Size. Jangan gunakan Fit to Page.")


if __name__ == "__main__":
    main()
