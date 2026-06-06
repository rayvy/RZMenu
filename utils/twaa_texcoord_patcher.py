import json
import math
import os
import struct

import bpy


MANIFEST_TEXT_PREFIX = "RZAutoAtlas."
PREVIEW_UV_NAME = "RZAutoAtlas.UV.preview"
PATCHER_BUILD = "tw-blocks-material-slot-v9-20260606"
_SAMPLE_LIMIT = 192


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


def _format_byte_width(fmt):
    fmt = str(fmt or "").upper()
    if fmt == "R8G8B8A8_UNORM":
        return 4
    if fmt == "R16G16_FLOAT":
        return 4
    if fmt == "R32G32_FLOAT":
        return 8
    if fmt == "R16G16B16A16_FLOAT":
        return 8
    if fmt == "R32G32B32_FLOAT":
        return 12
    if fmt == "R32G32B32A32_FLOAT":
        return 16
    if fmt == "R32G32B32A32_UINT":
        return 16
    return 0


def _format_storage(fmt):
    fmt = str(fmt or "").upper()
    if fmt == "R16G16_FLOAT":
        return "f16"
    if fmt == "R32G32_FLOAT":
        return "f32"
    return None


def _entry_to_dict(entry):
    if isinstance(entry, dict):
        return dict(entry)
    if hasattr(entry, "to_dict"):
        try:
            return dict(entry.to_dict())
        except Exception:
            pass
    result = {}
    for key in ("SemanticName", "SemanticIndex", "Format", "InputSlot", "AlignedByteOffset"):
        if hasattr(entry, key):
            result[key] = getattr(entry, key)
    return result


def _object_vblayout_entries(obj):
    if not obj:
        return []
    raw = obj.get("3DMigoto:VBLayout")
    if raw:
        return [_entry_to_dict(entry) for entry in raw]
    return []


def _parse_dump_txt_layout(path):
    entries = []
    current = None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if line.startswith("element["):
                    if current:
                        entries.append(current)
                    current = {}
                    continue
                if current is None or ":" not in line:
                    continue
                key, value = [part.strip() for part in line.split(":", 1)]
                if key in {"SemanticName", "Format"}:
                    current[key] = value
                elif key in {"SemanticIndex", "InputSlot", "AlignedByteOffset"}:
                    try:
                        current[key] = int(value)
                    except ValueError:
                        pass
            if current:
                entries.append(current)
    except Exception:
        return []
    return entries


def _component_name_from_texcoord_path(path):
    name = os.path.basename(str(path or ""))
    for suffix in ("Texcoord.buf", "Position.buf", "Blend.buf", ".buf"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return name


def _candidate_dump_layout_files(context, obj_data, texcoord_path=None):
    scene = getattr(context, "scene", None)
    xxmi = getattr(scene, "xxmi", None)
    dump_path = getattr(xxmi, "dump_path", "") if xxmi else ""
    if not dump_path:
        return []
    root = bpy.path.abspath(dump_path)
    if not os.path.isdir(root):
        return []

    names = []
    component_name = _component_name_from_texcoord_path(texcoord_path)
    if component_name:
        names.append(component_name)
    for key in ("part_fullname", "part_suffix"):
        value = str(obj_data.get(key, "") or "").strip()
        if value:
            names.append(value)
    obj_name = str(obj_data.get("name", "") or "").strip()
    if obj_name:
        names.append(obj_name)

    paths = []
    lowered = [name.lower() for name in names]
    try:
        for file_name in os.listdir(root):
            low = file_name.lower()
            if not (low.endswith(".txt") and "-vb" in low):
                continue
            if lowered and not any(name and name in low for name in lowered):
                continue
            paths.append(os.path.join(root, file_name))
    except Exception:
        return []
    paths.sort(key=lambda item: 0 if component_name and component_name.lower() in os.path.basename(item).lower() else 1)
    return paths


def _layout_entries_for_object(context, obj, obj_data, texcoord_path=None):
    entries = _object_vblayout_entries(obj)
    if entries:
        return entries, "object:3DMigoto:VBLayout"

    for path in _candidate_dump_layout_files(context, obj_data, texcoord_path):
        entries = _parse_dump_txt_layout(path)
        if entries:
            return entries, f"dump:{os.path.basename(path)}"

    return [], ""


def _packed_texcoord_primary_layout(entries):
    layouts = _packed_texcoord_layouts(entries)
    return layouts[0] if layouts else None


def _packed_texcoord_layouts(entries):
    layouts = []
    offset = 0
    color_seen = False
    for entry in entries:
        semantic = str(entry.get("SemanticName", "")).upper()
        semantic_index = int(entry.get("SemanticIndex", 0) or 0)
        fmt = str(entry.get("Format", ""))
        size = _format_byte_width(fmt)
        if semantic not in {"COLOR", "TEXCOORD"} or size <= 0:
            continue
        if semantic == "COLOR":
            color_seen = True
        if semantic == "TEXCOORD":
            storage = _format_storage(fmt)
            if storage:
                layouts.append({
                    "score": 999.0,
                    "storage": storage,
                    "offset": offset,
                    "source": "layout",
                    "semantic": "TEXCOORD",
                    "semantic_index": semantic_index,
                    "format": fmt,
                    "color_in_texcoord_buffer": color_seen,
                })
        offset += size
    layouts.sort(key=lambda item: int(item.get("semantic_index", 0)))
    return layouts


def _as_float_list(value, size):
    try:
        out = [float(value[i]) for i in range(size)]
    except Exception:
        return None
    return out if len(out) == size else None


def _sample_vertices(start, end, limit=_SAMPLE_LIMIT):
    start = int(start)
    end = int(end)
    count = max(0, end - start)
    if count <= 0:
        return []
    if count <= limit:
        return list(range(start, end))
    step = float(count - 1) / float(limit - 1)
    return sorted({start + int(round(index * step)) for index in range(limit)})


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
    return 0.0 if best is None else best


def _fract(value):
    return float(value) - math.floor(float(value))


def _addon_preferences(context):
    try:
        addon_name = __package__.split(".")[0]
        addon = context.preferences.addons.get(addon_name)
        return addon.preferences if addon else None
    except Exception:
        return None


def _post_patch_enabled(context):
    prefs = _addon_preferences(context)
    return bool(getattr(prefs, "tw_mc_post_patch_enabled", True)) if prefs else True


def _score_primary_candidate(data, stride, start, end, storage, offset, manifest):
    """Score one possible storage format for the *primary* TEXCOORD.xy pair.

    Important: in split XXMI Texcoord.buf streams the semantic location is
    deliberately restricted elsewhere to offset +4 (or +0 fallback).  This
    scorer only decides whether those bytes are encoded as f16x2 or f32x2.
    A f32 decoder pointed at packed f16 data often produces finite-looking
    garbage, so "finite" alone is not evidence.  Real UVs normally vary on
    both axes and spend a meaningful amount of time in a UV-sized range.
    """
    width = 4 if storage == "f16" else 8
    if offset < 0 or offset + width > stride:
        return None

    vertices = _sample_vertices(start, end)
    if not vertices:
        return None

    finite = 0
    sane = 0
    uv_sized = 0
    source_hits = 0
    meaningful = 0
    pairs = set()
    us = []
    vs = []

    for vertex in vertices:
        base = vertex * stride + offset
        try:
            u, v = _read_pair(data, base, storage)
        except Exception:
            continue
        u = float(u)
        v = float(v)
        if not (_finite(u) and _finite(v)):
            continue
        finite += 1
        if not (-64.0 <= u <= 64.0 and -64.0 <= v <= 64.0):
            continue
        sane += 1
        us.append(u)
        vs.append(v)
        if -2.0 <= u <= 2.0 and -2.0 <= v <= 2.0:
            uv_sized += 1
        if abs(u) > 1.0e-7 or abs(v) > 1.0e-7:
            meaningful += 1
        if _manifest_source_distance(manifest, u, v) <= 1.0e-4:
            source_hits += 1
        if len(pairs) < 64:
            pairs.add((round(u, 5), round(v, 5)))

    sample_count = len(vertices)
    finite_ratio = finite / float(sample_count)
    sane_ratio = sane / float(sample_count)
    uv_sized_ratio = uv_sized / float(max(1, sane))
    hit_ratio = source_hits / float(max(1, sane))
    meaningful_ratio = meaningful / float(max(1, sane))
    unique_ratio = min(1.0, len(pairs) / float(max(1, min(sane, 32))))
    u_range = max(us) - min(us) if us else 0.0
    v_range = max(vs) - min(vs) if vs else 0.0
    min_range = min(u_range, v_range)
    max_range = max(u_range, v_range)
    spread_axes = int(u_range > 1.0e-5) + int(v_range > 1.0e-5)
    balance = min_range / max(max_range, 1.0e-12)

    score = 0.0
    score += finite_ratio * 20.0
    score += sane_ratio * 70.0
    score += uv_sized_ratio * 55.0
    score += hit_ratio * 35.0
    score += meaningful_ratio * 10.0
    score += unique_ratio * 15.0
    score += spread_axes * 12.0
    score += min(1.0, balance * 4.0) * 35.0

    # A real UV pair should not look like one animated needle and one dead
    # axis.  This is the exact signature produced when f32 reads two packed
    # f16 pairs as if they were two float32 values.
    if max_range > 1.0e-3 and min_range < 1.0e-5:
        score -= 120.0
    elif max_range > 1.0e-2 and balance < 0.01:
        score -= 65.0

    # Prefer the semantic primary location, not later secondary payloads.
    # Storage itself receives no blind bonus: the bytes must prove whether
    # they are f16x2 or f32x2.
    score -= float(offset) * 1.5
    if offset == 4:
        score += 12.0

    return {
        "score": score,
        "storage": storage,
        "offset": offset,
        "finite_ratio": finite_ratio,
        "sane_ratio": sane_ratio,
        "uv_sized_ratio": uv_sized_ratio,
        "hit_ratio": hit_ratio,
        "meaningful_ratio": meaningful_ratio,
        "unique_ratio": unique_ratio,
        "u_range": u_range,
        "v_range": v_range,
        "spread_axes": spread_axes,
        "balance": balance,
    }

def _format_candidate(candidate):
    if candidate.get("source") == "layout":
        color_note = "+COLOR" if candidate.get("color_in_texcoord_buffer") else ""
        semantic_index = int(candidate.get("semantic_index", 0) or 0)
        semantic_name = "TEXCOORD" if semantic_index == 0 else f"TEXCOORD{semantic_index}"
        return (
            f"{semantic_name}.xy {candidate['storage']}+{candidate['offset']} "
            f"layout{color_note} format={candidate.get('format', '')}"
        )
    return (
        f"{candidate['storage']}+{candidate['offset']} score={candidate['score']:.1f} "
        f"hits={candidate['hit_ratio']:.0%} sane={candidate['sane_ratio']:.0%} "
        f"uv={candidate['uv_sized_ratio']:.0%} balance={candidate['balance']:.3f} "
        f"spread=({candidate['u_range']:.4g},{candidate['v_range']:.4g})"
    )

def _detect_primary_texcoord_layout(data, stride, start, count, manifest):
    total_vertices = len(data) // stride if stride > 0 else 0
    start = max(0, min(int(start), total_vertices))
    end = max(start, min(start + int(count), total_vertices))
    if end <= start:
        return None, []

    # Only the primary semantic is eligible.  For split Texcoord.buf streams:
    #   +4 = primary TEXCOORD.xy after packed COLOR
    #   +0 = fallback for layouts without COLOR
    # Secondary TEXCOORD1.xy offsets are intentionally not scanned.
    preferred = [
        ("f16", 4),
        ("f32", 4),
        ("f16", 0),
        ("f32", 0),
    ]

    ranked = []
    for storage, offset in preferred:
        candidate = _score_primary_candidate(data, stride, start, end, storage, offset, manifest)
        if candidate:
            ranked.append(candidate)
    ranked.sort(key=lambda item: item["score"], reverse=True)

    if not ranked:
        return None, []

    best = ranked[0]
    if best["sane_ratio"] < 0.80:
        return None, ranked
    if best["uv_sized_ratio"] < 0.70:
        return None, ranked
    if best["meaningful_ratio"] < 0.10:
        return None, ranked
    if best["spread_axes"] < 2:
        return None, ranked

    # Do not silently write into ambiguous bytes.  A close race means the
    # stream needs an explicit override or a proper fmt parser, not roulette.
    if len(ranked) > 1 and best["score"] - ranked[1]["score"] < 8.0:
        return None, ranked
    return best, ranked

def _load_manifest(material_key):
    text = bpy.data.texts.get(f"{MANIFEST_TEXT_PREFIX}{material_key}.manifest")
    if text:
        try:
            return json.loads(text.as_string())
        except Exception:
            pass

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
    best_uv = (float(u_bl), float(v_bl))
    uv_candidates = [
        (float(u_bl), float(v_bl)),
        (_fract(u_bl), _fract(v_bl)),
    ]

    for group in manifest.get("groups", []):
        bounds = group.get("source_uv_bounds") or [0.0, 0.0, 1.0, 1.0]
        u_min, v_min, u_max, v_max = [float(v) for v in bounds]
        u_span = max(1.0e-8, abs(u_max - u_min))
        v_span = max(1.0e-8, abs(v_max - v_min))
        for cand_u, cand_v in uv_candidates:
            du = 0.0 if u_min <= cand_u <= u_max else min(abs(cand_u - u_min), abs(cand_u - u_max)) / u_span
            dv = 0.0 if v_min <= cand_v <= v_max else min(abs(cand_v - v_min), abs(cand_v - v_max)) / v_span
            distance = du + dv
            if best_distance is None or distance < best_distance:
                best_group = group
                best_distance = distance
                best_uv = (cand_u, cand_v)

    if not best_group:
        return _fract(u_bl), _fract(v_bl)

    bounds = best_group.get("source_uv_bounds") or [0.0, 0.0, 1.0, 1.0]
    u_min, v_min, u_max, v_max = [float(v) for v in bounds]
    content = best_group.get("content_rect_px") or best_group.get("rect_px") or [0, 0, atlas_w, atlas_h]
    x, y, w, h = [float(v) for v in content]
    if y_origin != "UV_BOTTOM_LEFT":
        y = float(atlas_h) - y - h

    u_span = max(1.0e-8, u_max - u_min)
    v_span = max(1.0e-8, v_max - v_min)
    tu = (best_uv[0] - u_min) / u_span
    tv = (best_uv[1] - v_min) / v_span
    cluster_u_bl = (x + tu * w) / float(atlas_w)
    cluster_v_bl = (y + tv * h) / float(atlas_h)
    return cluster_u_bl, cluster_v_bl


def _buffer_to_blender_uv(u, v, invert_x, invert_y):
    return (1.0 - u if invert_x else u, 1.0 - v if invert_y else v)


def _atlas_blender_to_buffer_uv(cluster_u_bl, cluster_v_bl, pos_size, invert_x, invert_y):
    scale_x, scale_y, offset_x, offset_y_top = pos_size
    atlas_u = cluster_u_bl * scale_x + offset_x
    atlas_v_top_space = cluster_v_bl * scale_y + offset_y_top
    return (
        1.0 - atlas_u if invert_x else atlas_u,
        atlas_v_top_space if invert_y else 1.0 - atlas_v_top_space,
    )


def _block_name_is_twaa(name):
    return str(name or "").casefold().startswith("rzautoatlas")


def _block_name_is_current_twaa(name):
    lowered = str(name or "").casefold()
    return lowered in {
        "rzautoatlasdiffuse",
        "rzautoatlaslightmap",
        "rzautoatlasmaterialmap",
        "rzautoatlasnormalmap",
        "rzautoatlasextramap",
    }


def _twaa_blocks(context):
    scene = getattr(context, "scene", None)
    rzm = getattr(scene, "rzm", None)
    if not rzm:
        return []
    current_blocks = []
    legacy_blocks = []
    for block in getattr(rzm, "tw_blocks", []):
        block_name = str(getattr(block, "name", "") or "")
        resource_name = str(getattr(block, "resource_name", "") or "")
        if _block_name_is_current_twaa(block_name) or _block_name_is_current_twaa(resource_name):
            current_blocks.append(block)
        elif _block_name_is_twaa(block_name) or _block_name_is_twaa(resource_name):
            legacy_blocks.append(block)
    return current_blocks or legacy_blocks


def _twaa_component_keys(context):
    keys = set()
    for block in _twaa_blocks(context):
        for component in getattr(block, "components", []):
            name = str(getattr(component, "name", "") or "")
            if name:
                keys.add(name)
    return keys


def _material_name_to_key(name):
    raw = str(name or "")
    try:
        from .texworks_mc import material_key

        return material_key(raw)
    except Exception:
        return raw


def _slot_material_key(slot, valid_keys):
    mat = getattr(slot, "material", None)
    if not mat:
        return None
    names = [str(getattr(mat, "name", "") or ""), _material_name_to_key(getattr(mat, "name", ""))]
    for name in names:
        if name in valid_keys:
            return name
    return None


def _resolve_export_material_key(context, obj, obj_data):
    valid_keys = _twaa_component_keys(context)
    if not valid_keys:
        prop_key = str(obj.get("RZM_TW_MC_COMPONENT", "") or "")
        return prop_key, "object-prop/no-tw-blocks"

    mat_idx = obj_data.get("mat_idx", None)
    try:
        mat_idx = int(mat_idx)
    except Exception:
        mat_idx = -1
    if 0 <= mat_idx < len(obj.material_slots):
        key = _slot_material_key(obj.material_slots[mat_idx], valid_keys)
        if key:
            return key, f"material-slot[{mat_idx}]"

    slot_matches = []
    for index, slot in enumerate(obj.material_slots):
        key = _slot_material_key(slot, valid_keys)
        if key and key not in slot_matches:
            slot_matches.append(key)
    if len(slot_matches) == 1:
        return slot_matches[0], "single-material-slot"

    prop_key = str(obj.get("RZM_TW_MC_COMPONENT", "") or "")
    if prop_key in valid_keys:
        return prop_key, "object-prop/fallback"

    if slot_matches:
        return slot_matches[0], "ambiguous-material-slot"
    return prop_key, "object-prop/unmatched"


def _component_matches_material(component, material_key):
    key = str(material_key or "")
    return str(getattr(component, "name", "") or "") == key


def _find_twaa_component_layout(context, material_key):
    """Read virtual atlas placement from TexWorks blocks.

    This is the single source of truth for runtime atlas placement. Object
    custom properties are debug/cache only and must not drive export-time UV
    patching.
    """
    candidates = []
    for block in _twaa_blocks(context):
        block_name = str(getattr(block, "name", "") or "")
        resource_name = str(getattr(block, "resource_name", "") or "")
        if not (_block_name_is_twaa(block_name) or _block_name_is_twaa(resource_name)):
            continue
        try:
            atlas_w, atlas_h = [int(value) for value in block.block_resource_size[:2]]
        except Exception:
            continue
        if atlas_w <= 0 or atlas_h <= 0:
            continue
        for component in getattr(block, "components", []):
            if not _component_matches_material(component, material_key):
                continue
            try:
                x, y, w, h = [int(value) for value in component.rect[:4]]
            except Exception:
                continue
            if w <= 0 or h <= 0:
                continue
            candidates.append({
                "block": block_name or resource_name,
                "resource": resource_name or block_name,
                "component": str(component.name),
                "atlas_size": [atlas_w, atlas_h],
                "rect": [x, y, w, h],
                "pos_size": [
                    float(w) / float(atlas_w),
                    float(h) / float(atlas_h),
                    float(x) / float(atlas_w),
                    float(y) / float(atlas_h),
                ],
            })

    if not candidates:
        return None

    first = candidates[0]
    mismatches = [
        item for item in candidates[1:]
        if item["atlas_size"] != first["atlas_size"] or item["rect"] != first["rect"]
    ]
    first["mismatches"] = mismatches
    first["all_blocks"] = [item["block"] for item in candidates]
    return first


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
        # Combined buffers require an explicit layout parser. Do not guess.
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
    print(f"[RZM TWAA] build={PATCHER_BUILD}")
    if not _post_patch_enabled(context):
        print("[RZM TWAA] Post buffer patch disabled by addon preference.")
        return {"patched_vertices": 0, "objects": 0, "files": 0, "warnings": ["disabled by addon preference"]}

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
            if not obj:
                continue

            material_key, material_source = _resolve_export_material_key(context, obj, obj_data)
            if not material_key:
                continue
            tw_layout = _find_twaa_component_layout(context, material_key)
            if not tw_layout:
                warning = f"{obj.name}: no TWAA component in rzm.tw_blocks for material {material_key}"
                warnings.append(warning)
                print(f"[RZM TWAA] SKIP: {warning}")
                continue
            pos_size = tw_layout["pos_size"]
            if tw_layout.get("mismatches"):
                warning = (
                    f"{material_key}: TWAA component rect mismatch across blocks; "
                    f"using {tw_layout['block']} rect={tw_layout['rect']} atlas={tw_layout['atlas_size']}"
                )
                warnings.append(warning)
                print(f"[RZM TWAA] WARN: {warning}")

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

            print(
                f"[RZM TWAA] TW Blocks source: material={material_key} "
                f"material_source={material_source} "
                f"block={tw_layout['block']} atlas={tw_layout['atlas_size']} "
                f"rect={tw_layout['rect']} pos={tuple(round(v, 6) for v in pos_size)}"
            )

            entries, layout_source = _layout_entries_for_object(context, obj, obj_data, path)
            exact_layouts = [
                item for item in _packed_texcoord_layouts(entries)
                if item["offset"] + (4 if item["storage"] == "f16" else 8) <= stride
            ]
            if exact_layouts:
                layouts = exact_layouts
                ranked = layouts
            else:
                layout, ranked = _detect_primary_texcoord_layout(data, stride, start, count, manifest)
                layouts = [layout] if layout else []
            if not layouts:
                candidates = " | ".join(_format_candidate(item) for item in ranked[:4]) or "no candidates"
                warning = f"{obj.name}: cannot detect TEXCOORD.xy payloads in {os.path.basename(path)}; {candidates}"
                warnings.append(warning)
                print(f"[RZM TWAA] SKIP: {warning}")
                continue

            print(
                f"[RZM TWAA] TEXCOORD payloads selected "
                f"{', '.join(_format_candidate(item) for item in layouts)} "
                f"range=vertices[{start}:{start + count}]"
                + (f" via {layout_source}" if any(item.get("source") == "layout" for item in layouts) else "")
            )
            if not exact_layouts:
                alternatives = " | ".join(_format_candidate(item) for item in ranked if item not in layouts)
                if alternatives:
                    print(f"[RZM TWAA] TEXCOORD alternatives: {alternatives}")

            invert_x = bool(obj.get("RZM_TW_MC_POST_INVERT_X", False))
            invert_y = bool(obj.get("RZM_TW_MC_POST_INVERT_Y", True))
            total_vertices = len(data) // stride
            end = min(start + count, total_vertices)
            obj_patched_values = 0
            obj_patched_vertices = 0
            patched_layouts = []

            for layout in layouts:
                layout_patched = 0
                for vertex in range(start, end):
                    base = vertex * stride + layout["offset"]
                    try:
                        u, v = _read_pair(data, base, layout["storage"])
                    except Exception:
                        continue
                    if not (_finite(u) and _finite(v)):
                        continue
                    # Source UVs are Blender/export authoring coordinates.
                    # Post-export invert flags are applied only when writing
                    # the final runtime buffer coordinates.
                    u_bl, v_bl = float(u), float(v)
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
                    layout_patched += 1
                if layout_patched:
                    obj_patched_values += layout_patched
                    obj_patched_vertices = max(obj_patched_vertices, layout_patched)
                    patched_layouts.append(_format_candidate(layout))

            if obj_patched_values:
                patched_vertices += obj_patched_vertices
                patched_objects += 1
                file_changed = True
                print(
                    f"[RZM TWAA] Patched {obj_patched_values} TEXCOORD values "
                    f"({obj_patched_vertices} vertices) for {obj.name} "
                    f"in {os.path.basename(path)} @ {', '.join(patched_layouts)}"
                )

        if file_changed:
            tmp_path = f"{path}.rzm_tmp"
            with open(tmp_path, "wb") as handle:
                handle.write(data)
            os.replace(tmp_path, path)
            patched_files.add(path)

    return {
        "patched_vertices": patched_vertices,
        "objects": patched_objects,
        "files": len(patched_files),
        "warnings": warnings,
    }
