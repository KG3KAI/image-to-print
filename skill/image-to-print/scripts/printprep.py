#!/usr/bin/env python3
"""Make any mesh (GLB/OBJ/STL/PLY/3MF) printable: merge, repair, solidify, orient, scale, base, check, export."""
import argparse, json, sys
import numpy as np
import trimesh


def load(path):
    obj = trimesh.load(path, force="scene")
    meshes = [g for g in obj.dump() if isinstance(g, trimesh.Trimesh) and len(g.faces)]
    if not meshes:
        sys.exit(f"no triangle mesh in {path}")
    mesh = trimesh.util.concatenate(meshes)
    return trimesh.Trimesh(mesh.vertices, mesh.faces, process=True)


def repair(mesh, voxel_pitch_ratio):
    notes = []
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    parts = mesh.split(only_watertight=False)
    if len(parts) > 1:
        big = max(parts, key=lambda p: p.area)
        keep = [p for p in parts if p.area > big.area * 0.01]
        if len(keep) < len(parts):
            notes.append(f"removed {len(parts) - len(keep)} tiny floating fragments")
        mesh = trimesh.util.concatenate(keep)
    trimesh.repair.fix_normals(mesh)
    trimesh.repair.fill_holes(mesh)
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        try:
            import manifold3d
            m = manifold3d.Manifold(manifold3d.Mesh(np.asarray(mesh.vertices, np.float32), np.asarray(mesh.faces, np.uint32)))
            if m.status() == manifold3d.Error.NoError and m.num_tri() > 0:
                out = m.to_mesh()
                mesh = trimesh.Trimesh(out.vert_properties[:, :3], out.tri_verts)
                notes.append("rebuilt as manifold")
        except Exception:
            pass
    if not mesh.is_watertight:
        pitch = mesh.extents.max() * voxel_pitch_ratio
        vox = mesh.voxelized(pitch).fill()
        mesh = vox.marching_cubes
        mesh.apply_transform(vox.transform)
        trimesh.smoothing.filter_taubin(mesh, iterations=10)
        notes.append(f"voxel-remeshed at {pitch:.3f} model units to close holes")
    parts = mesh.split(only_watertight=False)
    if len(parts) > 1 and all(p.is_watertight for p in parts):
        try:
            for p in parts:
                if p.volume < 0:
                    p.invert()
            merged = trimesh.boolean.union(parts, engine="manifold")
            if merged.is_watertight and len(merged.split(only_watertight=False)) < len(parts):
                notes.append(f"boolean-merged {len(parts)} overlapping shells")
                mesh = merged
        except Exception as e:
            notes.append(f"shell merge skipped: {e}")
    if mesh.volume < 0:
        mesh.invert()
    return mesh, notes


def stable_orient(mesh, mode):
    if mode == "keep":
        return mesh
    if mode == "y-up":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        return mesh
    transforms, probs = trimesh.poses.compute_stable_poses(mesh, n_samples=1, threshold=0.02)
    if len(transforms):
        mesh.apply_transform(transforms[0])
    return mesh


def add_base(mesh, base_mm, margin_mm):
    lo, hi = mesh.bounds
    from shapely.geometry import MultiPoint
    hull = MultiPoint(mesh.vertices[:, :2]).convex_hull
    if hull.geom_type == "Polygon":
        base = trimesh.creation.extrude_polygon(hull.buffer(margin_mm), base_mm)
    else:
        size = hi[:2] - lo[:2] + 2 * margin_mm
        base = trimesh.creation.box([size[0], size[1], base_mm])
        base.apply_translation([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, base_mm / 2])
    mesh.apply_translation([0, 0, base_mm - lo[2] - 0.2])
    base.apply_translation([0, 0, -base.bounds[0][2]])
    try:
        return trimesh.boolean.union([mesh, base], engine="manifold")
    except Exception:
        return trimesh.util.concatenate([mesh, base])


def check(mesh, bed, contact_band):
    lo, hi = mesh.bounds
    ext = hi - lo
    z = mesh.vertices[:, 2]
    bottom_faces = mesh.triangles_center[:, 2] < lo[2] + contact_band
    down = mesh.face_normals[:, 2] < -0.9
    contact = float(mesh.area_faces[bottom_faces & down].sum())
    over = (mesh.face_normals[:, 2] < -np.cos(np.radians(45))) & ~bottom_faces
    overhang_ratio = float(mesh.area_faces[over].sum() / mesh.area)
    com = mesh.center_mass if mesh.is_watertight else mesh.centroid
    bottom_pts = mesh.vertices[z < lo[2] + contact_band][:, :2]
    stable = None
    if len(bottom_pts) >= 3:
        try:
            from scipy.spatial import Delaunay
            stable = bool(Delaunay(bottom_pts).find_simplex(com[:2]) >= 0)
        except Exception:
            stable = None
    parts = len(mesh.split(only_watertight=False))
    report = {
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "bodies": parts,
        "size_mm": [round(float(v), 2) for v in ext],
        "fits_bed": bool(all(ext[:2] <= np.array(bed[:2])) and ext[2] <= bed[2]),
        "volume_cm3": round(float(abs(mesh.volume)) / 1000, 2) if mesh.is_watertight else None,
        "bed_contact_mm2": round(contact, 1),
        "center_of_mass_over_footprint": stable,
        "overhang_area_ratio_gt45deg": round(overhang_ratio, 3),
        "triangles": int(len(mesh.faces)),
    }
    warnings = []
    if not report["watertight"]:
        warnings.append("NOT watertight: slicer may fail or produce gaps")
    if parts > 1:
        warnings.append(f"{parts} separate bodies: confirm they are intentional")
    if not report["fits_bed"]:
        warnings.append("exceeds build volume")
    if contact < 25:
        warnings.append("small bed contact (<25 mm2): add --base or brim")
    if stable is False:
        warnings.append("center of mass outside footprint: may tip over; add --base")
    if overhang_ratio > 0.15:
        warnings.append("large >45deg overhang area: enable supports (tree supports for organic shapes)")
    report["warnings"] = warnings
    report["pass"] = report["watertight"] and report["fits_bed"] and parts == 1 and stable is not False
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True, help=".stl or .3mf")
    ap.add_argument("--height", type=float, help="target height in mm (Z after orientation)")
    ap.add_argument("--max-dim", type=float, help="alternatively: longest side in mm")
    ap.add_argument("--orient", choices=["y-up", "stable", "keep"], default="y-up",
                    help="y-up for AI GLB output (default); stable picks the most stable resting pose")
    ap.add_argument("--base", type=float, default=0, help="add a plinth of this thickness in mm")
    ap.add_argument("--base-margin", type=float, default=2.0)
    ap.add_argument("--hollow", type=float, default=0, help="wall thickness mm to hollow (resin/large prints)")
    ap.add_argument("--max-faces", type=int, default=300000)
    ap.add_argument("--bed", default="256,256,256", help="build volume X,Y,Z mm (Bambu X1/P1 default)")
    ap.add_argument("--voxel-ratio", type=float, default=1 / 256)
    ap.add_argument("--report", help="write JSON report here")
    a = ap.parse_args()

    mesh = load(a.input)
    mesh, notes = repair(mesh, a.voxel_ratio)
    mesh = stable_orient(mesh, a.orient)
    if a.height or a.max_dim:
        s = a.height / mesh.extents[2] if a.height else a.max_dim / mesh.extents.max()
        mesh.apply_scale(s)
        notes.append(f"scaled x{s:.4f}")
    if len(mesh.faces) > a.max_faces:
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=a.max_faces)
            notes.append(f"decimated to {len(mesh.faces)} faces")
        except Exception as e:
            notes.append(f"decimation skipped: {e}")
        if not mesh.is_watertight:
            mesh, more = repair(mesh, a.voxel_ratio)
            notes += more
    if a.hollow > 0 and mesh.is_watertight:
        import manifold3d
        m = manifold3d.Manifold(manifold3d.Mesh(np.asarray(mesh.vertices, np.float32), np.asarray(mesh.faces, np.uint32)))
        pitch = a.hollow / 2
        inner = mesh.voxelized(pitch).fill()
        from scipy import ndimage
        core = ndimage.binary_erosion(inner.matrix, iterations=max(1, int(round(a.hollow / pitch))))
        if core.any():
            cm = trimesh.voxel.VoxelGrid(core, inner.transform).marching_cubes
            cm.apply_transform(inner.transform)
            mesh = trimesh.boolean.difference([mesh, cm], engine="manifold")
            notes.append(f"hollowed with ~{a.hollow} mm walls (add drain holes for resin)")
    if a.base > 0:
        mesh = add_base(mesh, a.base, a.base_margin)
        notes.append(f"added {a.base} mm base")
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    report = check(mesh, [float(v) for v in a.bed.split(",")], contact_band=0.3)
    report["repair_notes"] = notes
    report["out"] = a.out
    mesh.export(a.out)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if a.report:
        open(a.report, "w").write(text)
    print(text)
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
