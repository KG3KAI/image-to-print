# Image-to-3D backends

| Backend | Cost | Output | Notes |
|---|---|---|---|
| `hunyuan21` tencent/Hunyuan3D-2.1 | free (ZeroGPU) | untextured GLB | best free geometry for figurines |
| `hunyuan2` tencent/Hunyuan3D-2 | free | untextured GLB | fallback |
| `triposg` VAST-AI/TripoSG | free | GLB | sharp edges, good for objects; segmentation step first |
| `trellis2` microsoft/TRELLIS.2 | free | textured GLB | heavier, often queued |
| `meshy` | paid credits, `MESHY_API_KEY` | textured GLB | most reliable; also has native 3D-print tooling |
| `tripo` | paid credits, `TRIPO_API_KEY` | textured GLB | fast, good characters |

## Free Space failures

- `exceeded your ZeroGPU quota`: anonymous quota is tiny. Set `HF_TOKEN` (free HF account, read token) — PRO accounts get much more. Or wait, or switch backend.
- Hangs in queue: `--timeout` then the next backend; `--backend auto` does this.
- `AppError: RuntimeError` / changed signature: Spaces update their UI. Inspect with
  `PY -c "from gradio_client import Client; Client('SPACE').view_api()"` and adjust the argument list in `gen3d.py`.

## Local GPU

Run the official Gradio app of Hunyuan3D-2.1 / TRELLIS.2 / TripoSG on an NVIDIA machine (≥16 GB VRAM recommended), then
`gen3d.py IMG -o raw.glb --backend hunyuan21 --space http://HOST:PORT`. Apple Silicon can run Hunyuan3D-2 mini/TripoSR slowly; prefer cloud.

## Choosing

- Single-colour FDM figurine: free Hunyuan first, Meshy/Tripo if shape is wrong.
- Multicolour (AMS): need textured output (Meshy/Tripo/TRELLIS.2), then colour-segment in Bambu Studio (Paint/Color) or a dedicated tool; `printprep.py` keeps geometry only.
- Exact-dimension parts: not image-to-3D; use code CAD.
