#!/usr/bin/env python3
"""Render a quick 4-view PNG preview of a mesh (front/side/back/top) with matplotlib, no GPU needed."""
import argparse
import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mesh")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--max-faces", type=int, default=40000)
    a = ap.parse_args()
    m = trimesh.load(a.mesh, force="mesh")
    if len(m.faces) > a.max_faces:
        try:
            m = m.simplify_quadric_decimation(face_count=a.max_faces)
        except Exception:
            m = m.submesh([np.random.default_rng(0).choice(len(m.faces), a.max_faces, replace=False)], append=True)
    tri = m.vertices[m.faces]
    light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(m.face_normals @ light, 0, 1)
    colors = np.c_[shade[:, None] * [0.85, 0.82, 0.75], np.ones(len(shade))]
    views = [("front", 0, -90), ("side", 0, 0), ("back", 0, 90), ("3/4", 25, -60)]
    fig = plt.figure(figsize=(12, 3.4))
    lo, hi = m.bounds; c = (lo + hi) / 2; r = (hi - lo).max() / 2
    for i, (name, elev, azim) in enumerate(views):
        ax = fig.add_subplot(1, 4, i + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(tri, facecolors=colors, linewidths=0))
        for set_lim, k in ((ax.set_xlim, 0), (ax.set_ylim, 1), (ax.set_zlim, 2)):
            set_lim(c[k] - r, c[k] + r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off(); ax.set_title(name)
    ext = m.extents
    fig.suptitle(f"{ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm")
    fig.tight_layout(); fig.savefig(a.out, dpi=110)
    print(a.out)


if __name__ == "__main__":
    main()
