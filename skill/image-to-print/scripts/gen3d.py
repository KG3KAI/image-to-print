#!/usr/bin/env python3
"""Image -> raw 3D mesh (GLB) via free HF Spaces (Hunyuan3D / TripoSG / TRELLIS.2), Meshy or Tripo APIs."""
import argparse, base64, json, os, shutil, sys, time
from pathlib import Path

FREE_ORDER = ["hunyuan21", "hunyuan2", "triposg", "trellis2"]
SPACES = {"hunyuan21": "tencent/Hunyuan3D-2.1", "hunyuan2": "tencent/Hunyuan3D-2",
          "triposg": "VAST-AI/TripoSG", "trellis2": "microsoft/TRELLIS.2"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def first_file(result):
    items = result if isinstance(result, (list, tuple)) else [result]
    for it in items:
        if isinstance(it, dict):
            it = it.get("value") or it.get("path") or it.get("name")
        if isinstance(it, str) and Path(it).suffix.lower() in (".glb", ".obj", ".ply", ".stl") and Path(it).exists():
            return it
    for it in items:
        if isinstance(it, (list, tuple, dict)):
            f = first_file(list(it.values()) if isinstance(it, dict) else it)
            if f:
                return f
    return None


def run_job(client, timeout, *args, **kw):
    job = client.submit(*args, **kw)
    start, last = time.time(), None
    while not job.done():
        st = job.status()
        msg = f"{st.code.name} queue={getattr(st, 'rank', None)}/{getattr(st, 'queue_size', None)} eta={getattr(st, 'eta', None)}"
        if msg != last:
            log(f"  [{int(time.time() - start)}s] {msg}")
            last = msg
        if time.time() - start > timeout:
            job.cancel()
            raise TimeoutError(f"no result after {timeout}s")
        time.sleep(3)
    return job.result()


def gen_space(backend, image, seed, timeout, space=None):
    from gradio_client import Client, handle_file
    client = Client(space or SPACES[backend], token=os.environ.get("HF_TOKEN"), verbose=False)
    img = handle_file(image)
    if backend in ("hunyuan21", "hunyuan2"):
        kw = dict(image=img, mv_image_front=None, mv_image_back=None, mv_image_left=None, mv_image_right=None,
                  steps=30, guidance_scale=5.0, seed=seed, octree_resolution=256, check_box_rembg=True,
                  num_chunks=8000, api_name="/shape_generation")
        if backend == "hunyuan21":
            kw["randomize_seed"] = False
        else:
            kw["caption"] = None
        return first_file(run_job(client, timeout, **kw))
    if backend == "triposg":
        seg = run_job(client, timeout, img, api_name="/run_segmentation")
        seg_in = handle_file(seg) if isinstance(seg, str) else seg
        return first_file(run_job(client, timeout, seg_in, seed, 50, 7.0, True, 200000, api_name="/image_to_3d"))
    if backend == "trellis2":
        client.predict(api_name="/start_session")
        pre = client.predict(img, api_name="/preprocess_image")
        pre_in = handle_file(pre) if isinstance(pre, str) else pre
        run_job(client, timeout, pre_in, seed, "1024", 7.5, 0.7, 12, 5.0, 7.5, 0.5, 12, 3.0, 1.0, 0.0, 12, 3.0,
                api_name="/image_to_3d")
        return first_file(run_job(client, timeout, 300000, 2048, api_name="/extract_glb"))
    raise ValueError(backend)


def http_json(method, url, key, body=None):
    import requests
    r = requests.request(method, url, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def data_uri(image):
    ext = Path(image).suffix.lower().lstrip(".").replace("jpg", "jpeg")
    return f"data:image/{ext};base64," + base64.b64encode(Path(image).read_bytes()).decode()


def download(url, out):
    import requests
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    return out


def gen_meshy(image, out, timeout):
    key = os.environ["MESHY_API_KEY"]
    task = http_json("POST", "https://api.meshy.ai/openapi/v1/image-to-3d", key,
                     {"image_url": data_uri(image), "should_texture": True, "should_remesh": True,
                      "target_polycount": 200000, "enable_pbr": False})
    tid, start = task["result"], time.time()
    while time.time() - start < timeout:
        t = http_json("GET", f"https://api.meshy.ai/openapi/v1/image-to-3d/{tid}", key)
        log(f"  meshy {t.get('status')} {t.get('progress')}%")
        if t["status"] == "SUCCEEDED":
            return download(t["model_urls"]["glb"], out)
        if t["status"] in ("FAILED", "CANCELED", "EXPIRED"):
            raise RuntimeError(t.get("task_error"))
        time.sleep(10)
    raise TimeoutError("meshy timeout")


def gen_tripo(image, out, timeout):
    import requests
    key = os.environ["TRIPO_API_KEY"]
    with open(image, "rb") as f:
        up = requests.post("https://api.tripo3d.ai/v2/openapi/upload", headers={"Authorization": f"Bearer {key}"},
                           files={"file": f}, timeout=120).json()
    token = up["data"]["image_token"]
    ftype = Path(image).suffix.lower().lstrip(".").replace("jpeg", "jpg")
    task = http_json("POST", "https://api.tripo3d.ai/v2/openapi/task", key,
                     {"type": "image_to_model", "file": {"type": ftype, "file_token": token}})
    tid, start = task["data"]["task_id"], time.time()
    while time.time() - start < timeout:
        t = http_json("GET", f"https://api.tripo3d.ai/v2/openapi/task/{tid}", key)["data"]
        log(f"  tripo {t.get('status')} {t.get('progress')}%")
        if t["status"] == "success":
            o = t["output"]
            return download(o.get("pbr_model") or o.get("model") or o.get("base_model"), out)
        if t["status"] in ("failed", "cancelled", "banned", "expired"):
            raise RuntimeError(t["status"])
        time.sleep(10)
    raise TimeoutError("tripo timeout")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("-o", "--out", required=True, help="output mesh path (.glb recommended)")
    ap.add_argument("--backend", default="auto", choices=["auto", *SPACES, "meshy", "tripo"])
    ap.add_argument("--space", help="override Space id or local Gradio URL (e.g. http://127.0.0.1:7860)")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--timeout", type=int, default=900, help="seconds per backend attempt")
    a = ap.parse_args()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)

    if a.backend == "auto":
        order = (["meshy"] if os.environ.get("MESHY_API_KEY") else []) + \
                (["tripo"] if os.environ.get("TRIPO_API_KEY") else []) + FREE_ORDER
    else:
        order = [a.backend]
    errors = {}
    for b in order:
        log(f"[gen3d] trying {b}")
        try:
            if b == "meshy":
                path = gen_meshy(a.image, a.out, a.timeout)
            elif b == "tripo":
                path = gen_tripo(a.image, a.out, a.timeout)
            else:
                path = gen_space(b, a.image, a.seed, a.timeout, a.space)
                if not path:
                    raise RuntimeError("space returned no mesh file")
                out = Path(a.out).with_suffix(Path(path).suffix)
                shutil.copy(path, out)
                path = str(out)
            print(json.dumps({"out": path, "backend": b}))
            return 0
        except Exception as e:
            errors[b] = f"{type(e).__name__}: {e}"[:300]
            log(f"[gen3d] {b} failed: {errors[b]}")
    print(json.dumps({"out": None, "errors": errors}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
