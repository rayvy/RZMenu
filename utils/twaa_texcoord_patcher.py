import json
import math
import os
import struct

import bpy


MANIFEST_TEXT_PREFIX = "RZAutoAtlas."
PREVIEW_UV_NAME = "RZAutoAtlas.UV.preview"


def _finite(value):
    return math.isfinite(float(value))


def _read_f32(data, offset):
    return struct.unpack_from("<f", data, offset)[0]


def _write_f32_pair(data, offset, u, v):
    struct.pack_into("<ff", data, offset, float(u), float(v))


def _as_float_list(value, size):
    try:
        out = [float(value[i]) for i in range(size)]
    except Exception:
        return None
    return out if len(out) == size else None


def _as_int_list(value, size):
    try:
        out = [int(value[i]) for i in range(size)]
    except Exception:
        return None
    return out if len(out) == size else None


def _detect_f32_uv_offset(data, stride, start_vertex, vertex_count):
    if stride < 8 or len(data) < stride:
        return None

    total_vertices = len(data) // stride
    start = max(0, min(int(start_vertex), total_vertices))
    end = max(start, min(start + int(vertex_count), total_vertices))
    if end <= start:
        return None

    sample_count = min(128, end - start)
    if sample_count <= 0:
        return None
    step = max(1, (end - start) // sample_count)
    candidates = []

    for offset in range(0, stride - 7, 4):
        valid = 0
        in_unit = 0
        varied = set()
        u_values = []
        v_values = []
        for vertex in range(start, end, step):
            base = vertex * stride + offset
            try:
                u = _read_f32(data, base)
                v = _read_f32(data, base + 4)
            except Exception:
                continue
            if not (_finite(u) and _finite(v)):
                continue
            if -8.0 <= u <= 8.0 and -8.0 <= v <= 8.0:
                valid += 1
                u_values.append(float(u))
                v_values.append(float(v))
                if -0.25 <= u <= 1.25 and -0.25 <= v <= 1.25:
                    in_unit += 1
                if len(varied) < 16:
                    varied.add((round(u, 4), round(v, 4)))
        if valid:
            u_range = max(u_values) - min(u_values) if u_values else 0.0
            v_range = max(v_values) - min(v_values) if v_values else 0.0
            two_axis_bonus = 32 if u_range > 1.0e-5 and v_range > 1.0e-5 else 0
            constant_axis_penalty = 64 if u_range <= 1.0e-5 or v_range <= 1.0e-5 else 0
            score = (in_unit * 4) + valid + min(len(varied), 16) + two_axis_bonus - constant_axis_penalty
            candidates.append((score, offset, valid, in_unit))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _load_manifest(material_key):
    text = bpy.data.texts.get(f"{MANIFEST_TEXT_PREFIX}{material_key}.manifest")
    if text:
        try:
            return json.loads(text.as_string())
        except Exception:
            pass

    # Fallback for sessions where only exported files are present.
    scene = getattr(bpy.context, "scene", None)
    rzm = getattr(scene, "rzm", None)
    if not rzm:
        return None
    output_subdir = getattr(getattr(rzm, "tw_mc", None), "output_subdir", "Textures/DynAtlas")
    try:
        from ..operators.export_manager import get_target_path

        target_path = get_target_path(bpy.context)
    except Exception:
        target_path = None
    if not target_path:
        return None

    path = os.path.join(bpy.path.abspath(target_path), output_subdir, f"RZAutoAtlas.{material_key}.manifest.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _source_to_cluster_uv(manifest, u_bl, v_bl):
    atlas_w, atlas_h = [max(1, int(v)) for v in manifest.get("atlas_size", [1, 1])]
    y_origin = manifest.get("y_origin", "UV_BOTTOM_LEFT")
    best_group = None
    best_distance = None

    for group in manifest.get("groups", []):
        bounds = group.get("source_uv_bounds") or [0.0, 0.0, 1.0, 1.0]
        u_min, v_min, u_max, v_max = [float(v) for v in bounds]
        du = 0.0 if u_min <= u_bl <= u_max else min(abs(u_bl - u_min), abs(u_bl - u_max))
        dv = 0.0 if v_min <= v_bl <= v_max else min(abs(v_bl - v_min), abs(v_bl - v_max))
        distance = du + dv
        if best_distance is None or distance < best_distance:
            best_group = group
            best_distance = distance

    if not best_group:
        return u_bl, v_bl

    bounds = best_group.get("source_uv_bounds") or [0.0, 0.0, 1.0, 1.0]
    u_min, v_min, u_max, v_max = [float(v) for v in bounds]
    content = best_group.get("content_rect_px") or best_group.get("rect_px") or [0, 0, atlas_w, atlas_h]
    x, y, w, h = [float(v) for v in content]
    if y_origin != "UV_BOTTOM_LEFT":
        y = float(atlas_h) - y - h

    u_span = max(1.0e-8, u_max - u_min)
    v_span = max(1.0e-8, v_max - v_min)
    tu = (u_bl - u_min) / u_span
    tv = (v_bl - v_min) / v_span
    cluster_u_bl = (x + tu * w) / float(atlas_w)
    cluster_v_bl = (y + tv * h) / float(atlas_h)
    return cluster_u_bl, cluster_v_bl


def _buffer_to_blender_uv(u, v, invert_x, invert_y):
    return (1.0 - u if invert_x else u, 1.0 - v if invert_y else v)


def _atlas_blender_to_buffer_uv(cluster_u_bl, cluster_v_bl, pos_size, invert_x, invert_y):
    scale_x, scale_y, offset_x, offset_y_top = pos_size
    atlas_u_top = cluster_u_bl * scale_x + offset_x
    cluster_v_top = 1.0 - cluster_v_bl
    atlas_v_top = cluster_v_top * scale_y + offset_y_top
    out_u_bl = atlas_u_top
    out_v_bl = 1.0 - atlas_v_top
    return (
        1.0 - out_u_bl if invert_x else out_u_bl,
        1.0 - out_v_bl if invert_y else out_v_bl,
    )


def _texcoord_path_for_component(comp_data):
    buf_path = comp_data.get("buf_path") or ""
    if not buf_path:
        return None
    if buf_path.endswith("Texcoord.buf"):
        return buf_path
    if buf_path.endswith("Position.buf"):
        candidate = buf_path[:-len("Position.buf")] + "Texcoord.buf"
        return candidate if os.path.exists(candidate) else None
    if buf_path.endswith(".buf"):
        # Combined buffers need layout semantic offsets. Do not guess them here.
        return None
    return None


def _stride_for_texcoord(path, comp_data):
    n_verts = int(comp_data.get("n_verts", 0) or 0)
    if path and os.path.exists(path) and n_verts > 0:
        size = os.path.getsize(path)
        if size > 0 and size % n_verts == 0:
            stride = size // n_verts
            if 8 <= stride <= 128:
                return stride
    stride = int(comp_data.get("texcoord_stride", 0) or 0)
    return stride if stride >= 8 else None


def patch_exported_twaa_texcoords(context):
    try:
        from ..operators.export_cache import get_cache
    except Exception:
        return {"patched_vertices": 0, "objects": 0, "files": 0, "warnings": ["export cache unavailable"]}

    cache = get_cache()
    if not cache:
        return {"patched_vertices": 0, "objects": 0, "files": 0, "warnings": ["no export cache"]}

    warnings = []
    patched_vertices = 0
    patched_objects = 0
    patched_files = set()
    manifest_cache = {}

    for comp_name, comp_data in cache.get("components", {}).items():
        path = _texcoord_path_for_component(comp_data)
        if not path or not os.path.exists(path):
            continue
        stride = _stride_for_texcoord(path, comp_data)
        if not stride:
            warnings.append(f"{comp_name}: cannot determine Texcoord stride")
            continue

        data = bytearray(open(path, "rb").read())
        file_changed = False

        for obj_data in comp_data.get("objects", []):
            obj = bpy.data.objects.get(obj_data.get("name", ""))
            if not obj or "RZM_TW_MC_COMPONENT" not in obj:
                continue

            material_key = str(obj.get("RZM_TW_MC_COMPONENT", ""))
            pos_size = _as_float_list(obj.get("TEXCOORD_POS_SIZE"), 4)
            if not material_key or not pos_size:
                continue

            manifest = manifest_cache.get(material_key)
            if manifest is None:
                manifest = _load_manifest(material_key)
                manifest_cache[material_key] = manifest
            if not manifest:
                warnings.append(f"{obj.name}: missing TWAA manifest for {material_key}")
                continue

            start = int(obj_data.get("vb_offset", 0) or 0)
            count = int(obj_data.get("vb_count", 0) or 0)
            if count <= 0:
                continue

            uv_offset = _detect_f32_uv_offset(data, stride, start, count)
            if uv_offset is None:
                warnings.append(f"{obj.name}: cannot detect f32 UV offset in {os.path.basename(path)}")
                continue

            invert_x = bool(obj.get("RZM_TW_MC_POST_INVERT_X", False))
            invert_y = bool(obj.get("RZM_TW_MC_POST_INVERT_Y", True))
            total_vertices = len(data) // stride
            end = min(start + count, total_vertices)
            obj_patched = 0

            for vertex in range(start, end):
                base = vertex * stride + uv_offset
                u = _read_f32(data, base)
                v = _read_f32(data, base + 4)
                if not (_finite(u) and _finite(v)):
                    continue
                u_bl, v_bl = _buffer_to_blender_uv(u, v, invert_x, invert_y)
                cluster_u_bl, cluster_v_bl = _source_to_cluster_uv(manifest, u_bl, v_bl)
                out_u, out_v = _atlas_blender_to_buffer_uv(
                    cluster_u_bl,
                    cluster_v_bl,
                    pos_size,
                    invert_x,
                    invert_y,
                )
                _write_f32_pair(data, base, out_u, out_v)
                obj_patched += 1

            if obj_patched:
                patched_vertices += obj_patched
                patched_objects += 1
                file_changed = True
                print(
                    f"[RZM TWAA] Patched {obj_patched} TEXCOORD vertices for {obj.name} "
                    f"in {os.path.basename(path)} @ f32+{uv_offset}"
                )

        if file_changed:
            with open(path, "wb") as handle:
                handle.write(data)
            patched_files.add(path)

    return {
        "patched_vertices": patched_vertices,
        "objects": patched_objects,
        "files": len(patched_files),
        "warnings": warnings,
    }
