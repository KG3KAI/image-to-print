---
name: image-to-print
description: Turn a photo, drawing, logo or AI image into a 3D-printable STL/3MF — full 3D figurines/objects via image-to-3D (Hunyuan3D/TRELLIS/TripoSG free Spaces, Meshy/Tripo paid APIs, or local GPU), reliefs, lithophanes and embossed logos via heightmap — then repair, scale, base and verify printability. Use when the user wants to 3D print something from an image.
---

# Image to Print

Goal: deliver a printable file (STL or 3MF) at the requested real size, plus a printability report.
Never claim "ready to print" without the `printprep.py` report passing.

## Setup (once)

Scripts need Python ≥3.10 with `trimesh numpy pillow scipy manifold3d shapely gradio_client`. Default interpreter: `~/.image-to-print-venv/bin/python` (created by the repo's `install.sh`). If missing:
Prefer an existing env; otherwise:

```bash
uv venv ~/.image-to-print-venv --python 3.11
uv pip install --python ~/.image-to-print-venv/bin/python trimesh numpy pillow scipy manifold3d networkx lxml shapely rtree matplotlib gradio_client requests
```

Below, `PY` = that interpreter, `S` = this skill's `scripts/` dir.

## 1. Pick the route

| User wants | Route |
|---|---|
| Figurine, pet, character, object "in 3D", from one image | **A: image-to-3D** |
| Picture on a plate, wall art, coin, photo relief | **B: relief** (`--mode relief`) |
| Backlit photo panel / lamp shade | **B: lithophane** (`--mode lithophane`) |
| Logo, line art, signature, keychain, stamp | **B: emboss** (`--mode emboss`) |
| Functional part with exact dimensions (bracket, holder) | Not this pipeline: model it as code CAD (OpenSCAD/CadQuery/build123d) using the photo only as reference, then run step 3 |

Ask only for what is missing and matters: target size (default 80 mm tall figurine / 100 mm wide relief), and for route A which backend the user accepts (cost, upload of their photo to a third-party service).

## 2A. Image → 3D mesh

Input image quality decides the result: one object, whole body visible, plain background, even light, 3/4 or front view. If the photo is busy, first cut out the subject or regenerate a clean "figurine on white background" reference with an image tool, and show it to the user before spending generation time.

Run `PY S/gen3d.py IMAGE -o work/raw.glb --backend B`. Backends, in default order:

- `hunyuan21` / `hunyuan2` / `triposg` / `trellis2`: free Hugging Face Spaces, geometry only (good for single-colour prints). Queue time varies from seconds to many minutes; ZeroGPU quota is limited per user, `HF_TOKEN` raises it. `--backend auto` tries them in order.
- `meshy` (`MESHY_API_KEY`) / `tripo` (`TRIPO_API_KEY`): paid, best quality, textured — use for multicolour or when free Spaces fail.
- Local GPU: if the user runs Hunyuan3D/TRELLIS locally with a Gradio UI, pass `--space http://127.0.0.1:PORT --backend hunyuan21` (or matching API).

Read [references/backends.md](references/backends.md) only when a backend errors or you need parameters.

Inspect the raw result (render or open in Blender/Bambu Studio) before prepping: wrong pose, fused limbs, or missing back side mean regenerate with another seed/backend/cleaner image, not repair.

## 2B. Image → relief / lithophane / emboss

```bash
PY S/relief.py IMAGE -o work/relief.stl --mode relief|lithophane|emboss --width 100
```

Useful knobs: `--min-thick/--max-thick` (lithophane 0.8/3.2 mm defaults; print at 100% infill, white PLA, vertical), `--resolution` (mm per pixel, ~half nozzle), `--invert`, `--threshold` (emboss). Boost contrast or remove background of the image first if the subject is weak.

## 3. Make printable and verify (always)

```bash
PY S/printprep.py work/raw.glb -o out/model.3mf --height 80 --base 3 --report out/report.json
```

- Does: merge parts, drop tiny fragments, fix normals, fill holes, manifold rebuild, voxel remesh fallback, orient (`y-up` default for AI GLBs, `stable`, `keep` for reliefs), scale to real mm, optional plinth (`--base`) and hollowing (`--hollow`, mainly resin), decimate, center on bed, check.
- Report: watertight, bodies, size, fits bed (`--bed X,Y,Z`, default 256³), volume, bed contact, center of mass over footprint, overhang ratio, warnings, `pass`.
- Exit code 2 = not passing. Fix by the warning: tipping or tiny contact → `--base`; multiple bodies → check if intentional; not watertight → lower `--voxel-ratio` (e.g. 1/384) or regenerate.
- Overhang warning is advice, not failure: tell the user to enable (tree) supports.
- Thin features: AI meshes often have whiskers, tails, ears thinner than ~1.2 mm (0.4 nozzle). Look at the preview; if fragile, scale up or say so.

Preview before delivering (front/side/back/3-4 PNG, no GPU): `PY S/preview.py out/model.3mf -o out/preview.png` — look at it yourself and show it.

Optional offline slice check with Bambu Studio's default profile (proves the slicer accepts it, gives time estimate; does not print): `S/slice_bambu.sh out/model.3mf out/slice`.

## 4. Deliver

- Give the STL/3MF path(s), real size, report summary and print hints (supports, infill, orientation, material).
- If Bambu Studio is installed, offer to open the file (`open -a BambuStudio out/model.3mf` on macOS). Do not send anything to a printer unless the user explicitly asks.
- Mention that free Spaces uploaded the image to Hugging Face; paid APIs upload to the vendor.
