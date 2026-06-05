import json
import math
import os
import struct

import bpy


MANIFEST_TEXT_PREFIX = "RZAutoAtlas."
PREVIEW_UV_NAME = "RZAutoAtlas.UV.preview"
_MAX_SAMPLE_VERTICES = 192
_MAX_PROFILE_SAMPLES = 768


def _finite(value):
    return math.isfinite(float(value))


def _read_pair(data, offset, storage):
    if storage == "f16":
        return struct.unpack_from("<ee", data, offset)
    return struct.unpack_from("<ff", data, offset)


def _write_pair(data, offset, u, v, storage):
    if storage == "f16":
        struct.pack_into("<ee", data, offset, float(u), float(v))
    else:
        struct.pack_into("<ff", data, offset, float(u), float(v))


def _as_float_list(value, size):
    try:
        out = [float(value[i]) for i in range(size)]
    except Exception:
        return None
    return out if len(out) == size else None


def _evenly_spaced_indices(start, end, limit):
    count = max(0, int(end) - int(start))
    if count <= 0:
        return []
    if count <= limit:
        return list(range(start, end))
    step = float(count - 1) / float(limit - 1)
    return sorted({start + int(round(i * step)) for i in range(limit)})


def _quantile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * fraction))
    return float(ordered[max(0, min(index, len(ordered) - 1))])


def _profile_from_pairs(pairs):
    if not pairs:
        return None
    us = [float(pair[0]) for pair in pairs]
    vs = [float(pair[1]) for pair in pairs]
    return {
        "u05": _quantile(us, 0.05),
        "u25": _quantile(us, 0.25),
        "u50": _quantile(us, 0.50),
        "u75": _quantile(us, 0.75),
        "u95": _quantile(us, 0.95),
        "v05": _quantile(vs, 0.05),
        "v25": _quantile(vs, 0.25),
        "v50": _quantile(vs, 0.50),
        "v75": _quantile(vs, 0.75),
        "v95": _quantile(vs, 0.95),
        "u_range": max(us) - min(us),
        "v_range": max(vs) - min(vs),
    }


def _profile_distance(a, b):
    if not a or not b:
        return None
    keys = ("u05", "u25", "u50", "u75", "u95", "v05", "v25", "v50", "v75", "v95")
    distance = sum(abs(float(a[key]) - float(b[key])) for key in keys) / float(len(keys))
    distance += 0.25 * abs(float(a["u_range"]) - float(b["u_range"]))
    distance += 0.25 * abs(float(a["v_range"]) - float(b["v_range"]))
    return distance


def _collect_blender_source_uv_profiles(obj):
    mesh = getattr(obj, "data", None)
    uv_layers = getattr(mesh, "uv_layers", None)
    if not uv_layers:
        return []

    layers = []
    for layer in uv_layers:
        name = str(getattr(layer, "name", ""))
        # The preview layer is already atlas-space. It must never vote for the
        # source TEXCOORD layout that we are trying to locate in the .buf.
        if name == PREVIEW_UV_NAME or name.casefold().endswith(".preview"):
            continue
        priority = 0
        lowered = name.casefold()
        if lowered in {"texcoord.xy", "texcoord", "uvmap", "uv"}:
            priority += 100
        if getattr(uv_layers, "active", None) == layer:
            priority += 20
        if getattr(layer, "active_render", False):
            priority += 10
        layers.append((priority, layer))

    layers.sort(key=lambda item: item[0], reverse=True)
    profiles = []
    for priority, layer in layers[:8]:
        data = getattr(layer, "data", None)
        if not data:
            continue
        indices = _evenly_spaced_indices(0, len(data), _MAX_PROFILE_SAMPLES)
        pairs = []
        for index in indices:
            try:
                uv = data[index].uv
                u, v = float(uv[0]), float(uv[1])
            except Exception:
                continue
            if _finite(u) and _finite(v) and -64.0 <= u <= 64.0 and -64.0 <= v <= 64.0:
                pairs.append((u, v))
        profile = _profile_from_pairs(pairs)
        if profile:
            profiles.append({"name": layer.name, "priority": priority, "profile": profile})
    return profiles


def _manifest_source_distance(manifest, u, v):
    best = None
    for group in manifest.get("groups", []):
        bounds = group.get("source_uv_bounds") or [0.0, 0.0, 1.0, 1.0]
        try:
            u_min, v_min, u_max, v_max = [float(value) for value in bounds]
        except Exception:
            continue
        u_span = max(1.0e-6, abs(u_max - u_min))
        v_span = max(1.0e-6, abs(v_max - v_min))
        du = 0.0 if u_min <= u <= u_max else min(abs(u - u_min), abs(u - u_max)) / u_span
        dv = 0.0 if v_min <= v <= v_max else min(abs(v - v_min), abs(v - v_max)) / v_span
        distance = du + dv
        if best is None or distance < best:
            best = distance
    if best is None:
        # No useful groups in the manifest: fall back to a loose UV tile.
        du = 0.0 if -0.25 <= u <= 1.25 else min(abs(u + 0.25), abs(u - 1.25))
        dv = 0.0 if -0.25 <= v <= 1.25 else min(abs(v + 0.25), abs(v - 1.25))
        best = du + dv
    return best


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


def _candidate_storage_layouts(stride):
    # DXGI float TEXCOORD streams are naturally aligned. Scan both f32 and f16:
    # the exporter may choose either one depending on the source component.
    for offset in range(0, stride - 7, 4):
        yield "f32", offset, 8
    for offset in range(0, stride - 3, 2):
        yield "f16", offset, 4


def _candidate_vertex_ranges(raw_start, raw_count, stride, total_vertices, obj):
    raw_start = max(0, int(raw_start))
    raw_count = max(0, int(raw_count))
    options = []

    def add(mode, start, count, preference):
        start = int(start)
        count = int(count)
        if count <= 0 or start < 0 or start >= total_vertices:
            return
        end = min(total_vertices, start + count)
        if end <= start:
            return
        key = (start, end)
        if any(item["key"] == key for item in options):
            return
        options.append({"key": key, "mode": mode, "start": start, "end": end, "preference": preference})

    add("vertices", raw_start, raw_count, 8.0)
    if stride > 0 and raw_start % stride == 0:
        add("start_bytes", raw_start // stride, raw_count, 2.0)
    if stride > 0 and raw_count % stride == 0:
        add("count_bytes", raw_start, raw_count // stride, 1.0)
    if stride > 0 and raw_start % stride == 0 and raw_count % stride == 0:
        add("bytes", raw_start // stride, raw_count // stride, 0.0)

    # Use mesh size only as a soft hint. Split vertices can legitimately make
    # exported counts larger than obj.data.vertices but not wildly unrelated.
    mesh_vertex_count = len(getattr(getattr(obj, "data", None), "vertices", []) or [])
    mesh_loop_count = len(getattr(getattr(obj, "data", None), "loops", []) or [])
    for option in options:
        count = option["end"] - option["start"]
        if mesh_vertex_count > 0:
            ratio = float(count) / float(mesh_vertex_count)
            if 0.65 <= ratio <= 1.65:
                option["preference"] += 8.0
            elif 0.25 <= ratio <= 4.0:
                option["preference"] += 2.0
            else:
                option["preference"] -= 8.0
        if mesh_loop_count > 0 and count > mesh_loop_count * 1.25:
            option["preference"] -= 12.0
    return options


def _score_uv_candidate(data, stride, range_info, storage, offset, manifest, pos_size, invert_x, invert_y, uv_profiles):
    width = 4 if storage == "f16" else 8
    if offset < 0 or offset + width > stride:
        return None

    sample_vertices = _evenly_spaced_indices(range_info["start"], range_info["end"], _MAX_SAMPLE_VERTICES)
    if not sample_vertices:
        return None

    source_pairs = []
    sane = 0
    source_hits = 0
    output_sane = 0
    source_distance_sum = 0.0
    unique = set()

    for vertex in sample_vertices:
        base = vertex * stride + offset
        try:
            u, v = _read_pair(data, base, storage)
        except Exception:
            continue
        if not (_finite(u) and _finite(v)):
            continue
        u = float(u)
        v = float(v)
        if not (-64.0 <= u <= 64.0 and -64.0 <= v <= 64.0):
            continue
        sane += 1
        u_bl, v_bl = _buffer_to_blender_uv(u, v, invert_x, invert_y)
        source_pairs.append((u_bl, v_bl))
        if len(unique) < 96:
            unique.add((round(u_bl, 5), round(v_bl, 5)))

        source_distance = _manifest_source_distance(manifest, u_bl, v_bl)
        source_distance_sum += min(source_distance, 16.0)
        if source_distance <= 1.0e-5:
            source_hits += 1

        try:
            cluster_u, cluster_v = _source_to_cluster_uv(manifest, u_bl, v_bl)
            out_u, out_v = _atlas_blender_to_buffer_uv(cluster_u, cluster_v, pos_size, invert_x, invert_y)
            if _finite(out_u) and _finite(out_v) and -16.0 <= out_u <= 16.0 and -16.0 <= out_v <= 16.0:
                output_sane += 1
        except Exception:
            pass

    sample_count = len(sample_vertices)
    if sane <= max(2, sample_count // 8):
        return None

    candidate_profile = _profile_from_pairs(source_pairs)
    best_profile_distance = None
    best_profile_name = None
    for entry in uv_profiles:
        distance = _profile_distance(candidate_profile, entry["profile"])
        if distance is None:
            continue
        # Slightly prefer conventional source UV layer names when distances tie.
        adjusted = distance - min(0.03, float(entry["priority"]) * 0.0002)
        if best_profile_distance is None or adjusted < best_profile_distance:
            best_profile_distance = adjusted
            best_profile_name = entry["name"]

    valid_ratio = sane / float(sample_count)
    hit_ratio = source_hits / float(sane)
    output_ratio = output_sane / float(sane)
    avg_source_distance = source_distance_sum / float(sane)
    uniqueness_ratio = len(unique) / float(min(sane, 96))
    u_range = candidate_profile["u_range"] if candidate_profile else 0.0
    v_range = candidate_profile["v_range"] if candidate_profile else 0.0

    score = 0.0
    score += valid_ratio * 95.0
    score += hit_ratio * 230.0
    score += output_ratio * 55.0
    score += min(1.0, uniqueness_ratio * 2.0) * 45.0
    score -= min(12.0, avg_source_distance) * 24.0
    score += float(range_info["preference"])

    if u_range > 1.0e-5 and v_range > 1.0e-5:
        score += 28.0
    else:
        score -= 75.0

    if best_profile_distance is not None:
        # A distribution match against Blender's real source UV layer is the
        # strongest available signal. Wrong float pairs can look UV-ish, but
        # their quantiles almost never match the mesh UVs.
        profile_score = max(-140.0, 150.0 - best_profile_distance * 180.0)
        score += profile_score
    else:
        profile_score = None

    # Prefer f32 only very slightly when everything else is equal. This avoids
    # f16 aliases inside genuine f32 data winning by numerical accident.
    if storage == "f32":
        score += 4.0

    return {
        "score": score,
        "storage": storage,
        "offset": offset,
        "start": range_info["start"],
        "end": range_info["end"],
        "range_mode": range_info["mode"],
        "samples": sample_count,
        "valid_ratio": valid_ratio,
        "hit_ratio": hit_ratio,
        "output_ratio": output_ratio,
        "avg_source_distance": avg_source_distance,
        "uniqueness_ratio": uniqueness_ratio,
        "profile_distance": best_profile_distance,
        "profile_name": best_profile_name,
        "profile_score": profile_score,
    }


def _format_candidate(candidate):
    profile = "none" if candidate["profile_distance"] is None else f"{candidate['profile_distance']:.4f}:{candidate['profile_name']}"
    return (
        f"{candidate['storage']}+{candidate['offset']} score={candidate['score']:.1f} "
        f"hits={candidate['hit_ratio']:.0%} valid={candidate['valid_ratio']:.0%} "
        f"profile={profile} range={candidate['range_mode']}[{candidate['start']}:{candidate['end']}]"
    )


def _detect_uv_layout(data, stride, raw_start, raw_count, obj, manifest, pos_size, invert_x, invert_y):
    total_vertices = len(data) // stride if stride > 0 else 0
    ranges = _candidate_vertex_ranges(raw_start, raw_count, stride, total_vertices, obj)
    if not ranges:
        return None, []

    profiles = _collect_blender_source_uv_profiles(obj)
    candidates = []
    for range_info in ranges:
        for storage, offset, _width in _candidate_storage_layouts(stride):
            candidate = _score_uv_candidate(
                data,
                stride,
                range_info,
                storage,
                offset,
                manifest,
                pos_size,
                invert_x,
                invert_y,
                profiles,
            )
            if candidate:
                candidates.append(candidate)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    if not candidates:
        return None, []

    best = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None
    gap = best["score"] - runner_up["score"] if runner_up else 999.0

    # Refuse to cut when the detector is genuinely blind. The old patcher
    # always guessed and could silently corrupt a finished .buf.
    if best["valid_ratio"] < 0.70 or best["output_ratio"] < 0.70:
        return None, candidates[:5]
    if best["hit_ratio"] < 0.35 and best["profile_distance"] is None:
        return None, candidates[:5]
    if gap < 2.0 and best["profile_distance"] is None:
        return None, candidates[:5]

    return best, candidates[:5]


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
        # Combined buffers need semantic offsets from a .fmt layout. Separate
        # Texcoord.buf streams are safe to infer automatically.
        return None
    return None


def _stride_for_texcoord(path, comp_data):
    n_verts = int(comp_data.get("n_verts", 0) or 0)
    if path and os.path.exists(path) and n_verts > 0:
        size = os.path.getsize(path)
        if size > 0 and size % n_verts == 0:
            stride = size // n_verts
            if 4 <= stride <= 128:
                return stride
    stride = int(comp_data.get("texcoord_stride", 0) or 0)
    return stride if stride >= 4 else None


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

        with open(path, "rb") as handle:
            data = bytearray(handle.read())
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

            raw_start = int(obj_data.get("vb_offset", 0) or 0)
            raw_count = int(obj_data.get("vb_count", 0) or 0)
            if raw_count <= 0:
                continue

            invert_x = bool(obj.get("RZM_TW_MC_POST_INVERT_X", False))
            invert_y = bool(obj.get("RZM_TW_MC_POST_INVERT_Y", True))
            layout, ranked = _detect_uv_layout(
                data,
                stride,
                raw_start,
                raw_count,
                obj,
                manifest,
                pos_size,
                invert_x,
                invert_y,
            )
            if layout is None:
                candidates = " | ".join(_format_candidate(item) for item in ranked[:3]) or "no candidates"
                warning = f"{obj.name}: cannot confidently detect TEXCOORD layout in {os.path.basename(path)}; {candidates}"
                warnings.append(warning)
                print(f"[RZM TWAA] SKIP: {warning}")
                continue

            alternatives = " | ".join(_format_candidate(item) for item in ranked[1:3])
            print(f"[RZM TWAA] MindReader selected {_format_candidate(layout)}")
            if alternatives:
                print(f"[RZM TWAA] MindReader alternatives: {alternatives}")

            obj_patched = 0
            for vertex in range(layout["start"], layout["end"]):
                base = vertex * stride + layout["offset"]
                try:
                    u, v = _read_pair(data, base, layout["storage"])
                except Exception:
                    continue
                if not (_finite(u) and _finite(v)):
                    continue
                u_bl, v_bl = _buffer_to_blender_uv(float(u), float(v), invert_x, invert_y)
                cluster_u_bl, cluster_v_bl = _source_to_cluster_uv(manifest, u_bl, v_bl)
                out_u, out_v = _atlas_blender_to_buffer_uv(
                    cluster_u_bl,
                    cluster_v_bl,
                    pos_size,
                    invert_x,
                    invert_y,
                )
                if not (_finite(out_u) and _finite(out_v)):
                    continue
                _write_pair(data, base, out_u, out_v, layout["storage"])
                obj_patched += 1

            if obj_patched:
                patched_vertices += obj_patched
                patched_objects += 1
                file_changed = True
                print(
                    f"[RZM TWAA] Patched {obj_patched} TEXCOORD vertices for {obj.name} "
                    f"in {os.path.basename(path)} @ {layout['storage']}+{layout['offset']} "
                    f"range={layout['range_mode']}[{layout['start']}:{layout['end']}]"
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
