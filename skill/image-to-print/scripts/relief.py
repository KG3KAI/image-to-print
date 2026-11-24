#!/usr/bin/env python3
"""Image -> watertight relief / lithophane / emboss STL (no AI, deterministic)."""
import argparse, json, sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps
import trimesh


def heightfield_mesh(height, width_mm, pixel_mm, base_mm):
    rows, cols = height.shape
    xs = np.arange(cols) * pixel_mm
    ys = (rows - 1 - np.arange(rows)) * pixel_mm
    gx, gy = np.meshgrid(xs, ys)
    top = np.stack([gx, gy, height + base_mm], -1).reshape(-1, 3)
    bot = np.stack([gx, gy, np.zeros_like(height)], -1).reshape(-1, 3)
    verts = np.vstack([top, bot])
    n = rows * cols
    idx = np.arange(n).reshape(rows, cols)
    a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, :-1], idx[1:, 1:]
    top_f = np.concatenate([np.stack([a, c, b], -1).reshape(-1, 3), np.stack([b, c, d], -1).reshape(-1, 3)])
    bot_f = top_f[:, ::-1] + n
    edges = []
    border = list(idx[0, :]) + list(idx[1:, -1]) + list(idx[-1, -2::-1]) + list(idx[-2:0:-1, 0])
    for i in range(len(border)):
        p, q = border[i], border[(i + 1) % len(border)]
        edges += [[p, q + n, q], [p, p + n, q + n]]
    faces = np.vstack([top_f, bot_f, np.array(edges)])
    mesh = trimesh.Trimesh(verts, faces, process=True)
    if mesh.volume < 0:
        mesh.invert()
    return mesh


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--mode", choices=["relief", "lithophane", "emboss"], default="relief",
                    help="relief: bright=high; lithophane: dark=thick, view with backlight; emboss: threshold logo/line art")
    ap.add_argument("--width", type=float, default=100, help="output width in mm")
    ap.add_argument("--min-thick", type=float, default=None, help="thinnest point mm (default relief 1.5, litho 0.8)")
    ap.add_argument("--max-thick", type=float, default=None, help="thickest point mm (default relief 5, litho 3.2)")
    ap.add_argument("--resolution", type=float, default=0.2, help="mm per pixel; ~nozzle/2")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--threshold", type=int, default=128, help="emboss mode cutoff 0-255")
    ap.add_argument("--blur", type=float, default=0.6)
    a = ap.parse_args()

    img = Image.open(a.image)
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, rgba)
    gray = ImageOps.exif_transpose(img).convert("L")
    cols = max(2, int(round(a.width / a.resolution)))
    rows = max(2, int(round(cols * gray.height / gray.width)))
    gray = gray.resize((cols, rows), Image.LANCZOS)
    if a.blur > 0:
        gray = gray.filter(ImageFilter.GaussianBlur(a.blur))
    g = np.asarray(gray, dtype=np.float64) / 255.0

    if a.mode == "lithophane":
        lo, hi = a.min_thick or 0.8, a.max_thick or 3.2
        t = 1.0 - g
    elif a.mode == "emboss":
        lo, hi = a.min_thick or 1.5, a.max_thick or 3.0
        t = (g * 255 < a.threshold).astype(float)
    else:
        lo, hi = a.min_thick or 1.5, a.max_thick or 5.0
        t = g
    if a.invert:
        t = 1.0 - t
    height = t * (hi - lo)
    mesh = heightfield_mesh(height, a.width, a.width / cols, lo)
    mesh.export(a.out)
    ext = mesh.extents
    print(json.dumps({"out": a.out, "mode": a.mode, "size_mm": [round(float(x), 2) for x in ext],
                      "watertight": bool(mesh.is_watertight), "triangles": int(len(mesh.faces)),
                      "thickness_mm": [lo, hi]}, ensure_ascii=False))
    return 0 if mesh.is_watertight else 2


if __name__ == "__main__":
    sys.exit(main())
