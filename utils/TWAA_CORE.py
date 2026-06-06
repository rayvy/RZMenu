"""Pure-Python UV cluster grouping and rectangle packing for TexWorks AutoAtlas.

The module intentionally knows nothing about Blender.  It accepts material-local
face dictionaries and returns plain Python dictionaries.  Blender operators,
images, file paths and bpy objects belong in the integration layer.

Public compatibility helpers kept for the surrounding addon:
    build_uv_islands
    group_stacked_islands
    build_groups
    build_texture_bsp_groups
    build_no_texture_dense_groups
    build_single_preview_group
    shelf_pack
    pack_groups
    pack_groups_bounded

New convenience helpers:
    build_texture_groups
    substance_canvas_size
    detect_layout_overlaps
    collect_diagnostics
    build_and_pack_cluster
"""

from __future__ import annotations

import math
from collections import defaultdict

SUBSTANCE_SIZES = (128, 256, 512, 1024, 2048, 4096)
EPSILON = 1.0e-12
UV_ROUND_DIGITS = 6


def next_power_of_two(value):
    value = max(1, int(math.ceil(value)))
    return 1 << (value - 1).bit_length()


def substance_side(value):
    """Return the smallest Substance-compatible side length that can contain value."""
    value = max(1, int(math.ceil(value)))
    for side in SUBSTANCE_SIZES:
        if value <= side:
            return side
    raise RuntimeError(f"Required canvas side {value}px exceeds the 4096px TexWorks limit.")


def substance_canvas_size(raw_w, raw_h):
    return substance_side(raw_w), substance_side(raw_h)


def rounded_uv(uv):
    return round(float(uv[0]), UV_ROUND_DIGITS), round(float(uv[1]), UV_ROUND_DIGITS)


def _canonical_polygon(uvs):
    """Rotation- and winding-independent polygon signature."""
    points = tuple(rounded_uv(uv) for uv in uvs)
    if not points:
        return ()
    variants = []
    for seq in (points, tuple(reversed(points))):
        for offset in range(len(seq)):
            variants.append(seq[offset:] + seq[:offset])
    return min(variants)


def _bbox_from_uvs(uvs):
    if not uvs:
        return 0.0, 0.0, 0.0, 0.0
    u_values = [float(uv[0]) for uv in uvs]
    v_values = [float(uv[1]) for uv in uvs]
    return min(u_values), min(v_values), max(u_values), max(v_values)


def _bbox_area(item):
    return max(0.0, float(item["u_max"]) - float(item["u_min"])) * max(
        0.0, float(item["v_max"]) - float(item["v_min"])
    )


def _union_find(size):
    parent = list(range(size))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a, b):
        root_a = find(a)
        root_b = find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    return parent, find, union


def _validate_faces(faces):
    for face_index, face in enumerate(faces):
        if "uvs" not in face:
            raise ValueError(f"Face {face_index} has no 'uvs' field.")
        if len(face["uvs"]) < 3:
            raise ValueError(f"Face {face_index} has fewer than three UV corners.")
        for uv in face["uvs"]:
            if len(uv) < 2 or not math.isfinite(float(uv[0])) or not math.isfinite(float(uv[1])):
                raise ValueError(f"Face {face_index} contains an invalid UV coordinate: {uv!r}")


def face_uv_bbox(face):
    return _bbox_from_uvs(face["uvs"])


def face_group_bbox(faces, face_indices):
    if not face_indices:
        return 0.0, 0.0, 0.0, 0.0
    boxes = [face_uv_bbox(faces[index]) for index in face_indices]
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _normalized_shape_signature(faces, face_indices, resolution=128):
    """Cheap shape fingerprint used to avoid treating bbox twins as stacked islands."""
    u_min, v_min, u_max, v_max = face_group_bbox(faces, face_indices)
    width = max(EPSILON, u_max - u_min)
    height = max(EPSILON, v_max - v_min)
    points = set()
    edges = set()
    for face_index in face_indices:
        uvs = faces[face_index]["uvs"]
        normalized = []
        for u, v in uvs:
            point = (
                int(round(((float(u) - u_min) / width) * resolution)),
                int(round(((float(v) - v_min) / height) * resolution)),
            )
            normalized.append(point)
            points.add(point)
        for index, point_a in enumerate(normalized):
            point_b = normalized[(index + 1) % len(normalized)]
            edges.add(tuple(sorted((point_a, point_b))))
    return frozenset(points), frozenset(edges)


def _set_similarity(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def build_uv_islands(faces):
    """Build material-local UV islands.

    Exact duplicate UV polygons are collapsed before adjacency traversal.  This
    matters for stacked meshes: two identical triangles occupying the same
    source pixels should not accidentally fuse every stacked layer into one
    giant graph merely because their UV edges are identical.
    """
    _validate_faces(faces)
    if not faces:
        return []

    signature_to_rep = {}
    representatives = []
    duplicate_members = defaultdict(list)
    for face_index, face in enumerate(faces):
        signature = _canonical_polygon(face["uvs"])
        rep = signature_to_rep.get(signature)
        if rep is None:
            rep = len(representatives)
            signature_to_rep[signature] = rep
            representatives.append(face_index)
        duplicate_members[rep].append(face_index)

    _, find, union = _union_find(len(representatives))
    edge_owners = defaultdict(list)
    for rep_index, face_index in enumerate(representatives):
        uvs = faces[face_index]["uvs"]
        for corner_index, uv_a in enumerate(uvs):
            uv_b = uvs[(corner_index + 1) % len(uvs)]
            edge = tuple(sorted((rounded_uv(uv_a), rounded_uv(uv_b))))
            edge_owners[edge].append(rep_index)

    for owners in edge_owners.values():
        if len(owners) >= 2:
            first = owners[0]
            for other in owners[1:]:
                union(first, other)

    grouped_reps = defaultdict(list)
    for rep_index in range(len(representatives)):
        grouped_reps[find(rep_index)].append(rep_index)

    islands = []
    ordered_groups = sorted(grouped_reps.values(), key=lambda reps: min(representatives[r] for r in reps))
    for island_index, rep_indices in enumerate(ordered_groups):
        face_indices = sorted(
            face_index for rep_index in rep_indices for face_index in duplicate_members[rep_index]
        )
        u_min, v_min, u_max, v_max = face_group_bbox(faces, face_indices)
        points, edges = _normalized_shape_signature(faces, face_indices)
        duplicate_counts = [len(duplicate_members[rep_index]) for rep_index in rep_indices]
        collapsed_stack_count = min(duplicate_counts) if duplicate_counts else 1
        islands.append({
            "index": island_index,
            "face_indices": face_indices,
            "u_min": u_min,
            "v_min": v_min,
            "u_max": u_max,
            "v_max": v_max,
            "surface_area": sum(max(0.0, float(faces[i].get("surface_area", 0.0))) for i in face_indices),
            "shape_points": points,
            "shape_edges": edges,
            "stack_count": max(1, collapsed_stack_count),
            "duplicate_polygon_count": sum(max(0, count - 1) for count in duplicate_counts),
        })
    return islands


def bbox_overlap_ratio(a, b):
    x0 = max(float(a["u_min"]), float(b["u_min"]))
    y0 = max(float(a["v_min"]), float(b["v_min"]))
    x1 = min(float(a["u_max"]), float(b["u_max"]))
    y1 = min(float(a["v_max"]), float(b["v_max"]))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    overlap = (x1 - x0) * (y1 - y0)
    return overlap / max(EPSILON, min(_bbox_area(a), _bbox_area(b)))


def bbox_stack_similarity(a, b, threshold=0.95):
    aw = max(0.0, float(a["u_max"]) - float(a["u_min"]))
    ah = max(0.0, float(a["v_max"]) - float(a["v_min"]))
    bw = max(0.0, float(b["u_max"]) - float(b["u_min"]))
    bh = max(0.0, float(b["v_max"]) - float(b["v_min"]))
    if min(aw, ah, bw, bh) <= 1.0e-8:
        return False
    if min(aw, bw) / max(aw, bw) < threshold or min(ah, bh) / max(ah, bh) < threshold:
        return False
    if bbox_overlap_ratio(a, b) < threshold:
        return False

    points_a = a.get("shape_points")
    points_b = b.get("shape_points")
    edges_a = a.get("shape_edges")
    edges_b = b.get("shape_edges")
    if points_a is not None and points_b is not None:
        if _set_similarity(points_a, points_b) < threshold:
            return False
    if edges_a is not None and edges_b is not None:
        if _set_similarity(edges_a, edges_b) < threshold:
            return False
    return True


def _group_from_islands(group_index, group_islands):
    face_indices = sorted(face for island in group_islands for face in island["face_indices"])
    island_indices = sorted(island["index"] for island in group_islands)
    return {
        "index": group_index,
        "island_indices": island_indices,
        "face_indices": face_indices,
        "u_min": min(island["u_min"] for island in group_islands),
        "v_min": min(island["v_min"] for island in group_islands),
        "u_max": max(island["u_max"] for island in group_islands),
        "v_max": max(island["v_max"] for island in group_islands),
        "surface_area": sum(float(island.get("surface_area", 0.0)) for island in group_islands),
        "stack_count": sum(max(1, int(island.get("stack_count", 1))) for island in group_islands),
        "duplicate_polygon_count": sum(int(island.get("duplicate_polygon_count", 0)) for island in group_islands),
    }


def group_stacked_islands(islands, threshold=0.95):
    if not islands:
        return []
    _, find, union = _union_find(len(islands))
    for left in range(len(islands)):
        for right in range(left + 1, len(islands)):
            if bbox_stack_similarity(islands[left], islands[right], threshold=threshold):
                union(left, right)

    grouped = defaultdict(list)
    for island_index, island in enumerate(islands):
        grouped[find(island_index)].append(island)
    ordered = sorted(grouped.values(), key=lambda values: min(item["index"] for item in values))
    return [_group_from_islands(index, values) for index, values in enumerate(ordered)]


def _apply_pixel_dimensions(groups, ref_w, ref_h, margin_px):
    ref_w = max(1, int(ref_w))
    ref_h = max(1, int(ref_h))
    margin_px = max(0, int(margin_px))
    for group in groups:
        content_w = max(1, int(math.ceil((group["u_max"] - group["u_min"]) * ref_w)))
        content_h = max(1, int(math.ceil((group["v_max"] - group["v_min"]) * ref_h)))
        group["content_w"] = content_w
        group["content_h"] = content_h
        group["w"] = content_w + margin_px * 2
        group["h"] = content_h + margin_px * 2
    return groups


def _face_mapping(groups):
    mapping = {}
    for group in groups:
        for face_index in group["face_indices"]:
            mapping[face_index] = group
    return mapping


def build_groups(faces, ref_w, ref_h, margin_px):
    """Compatibility name for standard texture crop/repack grouping."""
    return build_texture_groups(faces, ref_w, ref_h, margin_px)


def build_texture_groups(faces, ref_w, ref_h, margin_px):
    islands = build_uv_islands(faces)
    groups = group_stacked_islands(islands)
    _apply_pixel_dimensions(groups, ref_w, ref_h, margin_px)
    return islands, groups, _face_mapping(groups)


def group_pixel_area_from_bbox(bbox, ref_w, ref_h, margin_px):
    u_min, v_min, u_max, v_max = bbox
    content_w = max(1, int(math.ceil((u_max - u_min) * ref_w)))
    content_h = max(1, int(math.ceil((v_max - v_min) * ref_h)))
    return (content_w + margin_px * 2) * (content_h + margin_px * 2)


def _split_by_largest_gap(faces, face_indices):
    """Return a conservative UV split only when there is an obvious empty corridor."""
    best = None
    for axis in (0, 1):
        items = []
        for face_index in face_indices:
            bbox = face_uv_bbox(faces[face_index])
            center = (bbox[0] + bbox[2]) * 0.5 if axis == 0 else (bbox[1] + bbox[3]) * 0.5
            items.append((center, face_index))
        items.sort()
        span = max(EPSILON, items[-1][0] - items[0][0])
        for split_index in range(8, len(items) - 7):
            gap = items[split_index][0] - items[split_index - 1][0]
            ratio = gap / span
            if best is None or ratio > best[0]:
                best = (ratio, [item[1] for item in items[:split_index]], [item[1] for item in items[split_index:]])
    if best is None or best[0] < 0.20:
        return None
    return best[1], best[2]


def build_texture_bsp_groups(faces, ref_w, ref_h, margin_px):
    """Compatibility entry point with deliberately conservative sparse splitting.

    The previous implementation recursively median-split faces and could shred a
    connected island into horizontal strips.  This version starts from true UV
    islands, preserves stacked groups, and splits only large non-stacked groups
    with an obvious empty UV corridor and a meaningful rectangle-area saving.
    """
    islands, base_groups, _ = build_texture_groups(faces, ref_w, ref_h, margin_px)
    final_groups = []
    pending = list(base_groups)
    while pending:
        group = pending.pop(0)
        if group.get("stack_count", 1) > 1 or len(group["face_indices"]) < 32:
            final_groups.append(group)
            continue
        split = _split_by_largest_gap(faces, group["face_indices"])
        if split is None:
            final_groups.append(group)
            continue
        left, right = split
        parent_area = group_pixel_area_from_bbox(face_group_bbox(faces, group["face_indices"]), ref_w, ref_h, margin_px)
        child_area = group_pixel_area_from_bbox(face_group_bbox(faces, left), ref_w, ref_h, margin_px)
        child_area += group_pixel_area_from_bbox(face_group_bbox(faces, right), ref_w, ref_h, margin_px)
        if child_area > parent_area * 0.65:
            final_groups.append(group)
            continue
        for child_faces in (left, right):
            u_min, v_min, u_max, v_max = face_group_bbox(faces, child_faces)
            child = {
                "index": 0,
                "island_indices": list(group["island_indices"]),
                "face_indices": sorted(child_faces),
                "u_min": u_min,
                "v_min": v_min,
                "u_max": u_max,
                "v_max": v_max,
                "surface_area": sum(max(0.0, float(faces[i].get("surface_area", 0.0))) for i in child_faces),
                "stack_count": 1,
                "sparse_split": True,
            }
            _apply_pixel_dimensions([child], ref_w, ref_h, margin_px)
            final_groups.append(child)

    for index, group in enumerate(final_groups):
        group["index"] = index
    return islands, final_groups, _face_mapping(final_groups)


def _island_aspect(island):
    width = max(EPSILON, float(island["u_max"]) - float(island["u_min"]))
    height = max(EPSILON, float(island["v_max"]) - float(island["v_min"]))
    return max(0.20, min(5.0, width / height))


def build_no_texture_dense_groups(faces, ref_w, ref_h, margin_px):
    """Build editable dense rectangles per UV island, weighted by geometry area."""
    islands = build_uv_islands(faces)
    if not islands:
        return [], [], {}

    ref_w = max(1, int(ref_w))
    ref_h = max(1, int(ref_h))
    margin_px = max(0, int(margin_px))
    total_surface = sum(max(0.0, float(island.get("surface_area", 0.0))) for island in islands)
    fallback_weight = 1.0 / len(islands)
    target_content_pixels = max(1, int(ref_w * ref_h * 0.68))
    min_side = 16

    groups = []
    for island in islands:
        surface = max(0.0, float(island.get("surface_area", 0.0)))
        weight = surface / total_surface if total_surface > EPSILON else fallback_weight
        pixel_budget = max(min_side * min_side, target_content_pixels * weight)
        aspect = _island_aspect(island)
        content_w = max(min_side, int(math.ceil(math.sqrt(pixel_budget * aspect))))
        content_h = max(min_side, int(math.ceil(math.sqrt(pixel_budget / aspect))))
        group = {
            "index": len(groups),
            "island_indices": [island["index"]],
            "face_indices": list(island["face_indices"]),
            "u_min": island["u_min"],
            "v_min": island["v_min"],
            "u_max": island["u_max"],
            "v_max": island["v_max"],
            "content_w": content_w,
            "content_h": content_h,
            "w": content_w + margin_px * 2,
            "h": content_h + margin_px * 2,
            "surface_area": surface,
            "stack_count": 1,
        }
        groups.append(group)
    return islands, groups, _face_mapping(groups)


def build_single_preview_group(faces, ref_w, ref_h, margin_px):
    if not faces:
        return [], [], {}
    _validate_faces(faces)
    u_min, v_min, u_max, v_max = face_group_bbox(faces, range(len(faces)))
    group = {
        "index": 0,
        "island_indices": [0],
        "face_indices": list(range(len(faces))),
        "u_min": u_min,
        "v_min": v_min,
        "u_max": u_max,
        "v_max": v_max,
        "stack_count": 1,
        "x": 0,
        "y": 0,
    }
    _apply_pixel_dimensions([group], ref_w, ref_h, margin_px)
    island = {key: group[key] for key in ("index", "face_indices", "u_min", "v_min", "u_max", "v_max")}
    return [island], [group], _face_mapping([group])


def _rect_intersects(a, b):
    return not (
        a["x"] + a["w"] <= b["x"]
        or b["x"] + b["w"] <= a["x"]
        or a["y"] + a["h"] <= b["y"]
        or b["y"] + b["h"] <= a["y"]
    )


def detect_layout_overlaps(groups):
    warnings = []
    for left in range(len(groups)):
        for right in range(left + 1, len(groups)):
            if _rect_intersects(groups[left], groups[right]):
                warnings.append((groups[left]["index"], groups[right]["index"]))
    return warnings


def shelf_pack(groups, width, gap):
    """Stable shelf fallback retained for compatibility and debugging."""
    ordered = sorted(groups, key=lambda item: (int(item["h"]), int(item["w"]), -int(item["index"])), reverse=True)
    x = y = row_h = max_x = 0
    packed = []
    for group in ordered:
        w, h = int(group["w"]), int(group["h"])
        if x > 0 and x + w > width:
            x = 0
            y += row_h + gap
            row_h = 0
        placed = dict(group)
        placed["x"] = x
        placed["y"] = y
        packed.append(placed)
        x += w + gap
        row_h = max(row_h, h)
        max_x = max(max_x, x - gap)
    return packed, max_x, y + row_h


def _split_free_rectangles(free_rects, placed):
    output = []
    px, py, pw, ph = placed
    for fx, fy, fw, fh in free_rects:
        if px >= fx + fw or px + pw <= fx or py >= fy + fh or py + ph <= fy:
            output.append((fx, fy, fw, fh))
            continue
        if px > fx:
            output.append((fx, fy, px - fx, fh))
        if px + pw < fx + fw:
            output.append((px + pw, fy, fx + fw - (px + pw), fh))
        if py > fy:
            output.append((fx, fy, fw, py - fy))
        if py + ph < fy + fh:
            output.append((fx, py + ph, fw, fy + fh - (py + ph)))

    pruned = []
    for index, rect in enumerate(output):
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            continue
        contained = False
        for other_index, other in enumerate(output):
            if index == other_index:
                continue
            ox, oy, ow, oh = other
            if x >= ox and y >= oy and x + w <= ox + ow and y + h <= oy + oh:
                contained = True
                break
        if not contained and rect not in pruned:
            pruned.append(rect)
    return pruned


def _maxrects_pack(groups, bin_w, bin_h, gap):
    ordered = sorted(
        groups,
        key=lambda item: (max(int(item["w"]), int(item["h"])), int(item["w"]) * int(item["h"]), -int(item["index"])),
        reverse=True,
    )
    free_rects = [(0, 0, int(bin_w), int(bin_h))]
    packed = []
    used_w = used_h = 0
    for group in ordered:
        w = int(group["w"])
        h = int(group["h"])
        best = None
        for rect_index, (x, y, free_w, free_h) in enumerate(free_rects):
            if w <= free_w and h <= free_h:
                leftover_short = min(free_w - w, free_h - h)
                leftover_long = max(free_w - w, free_h - h)
                score = (y, x, leftover_short, leftover_long)
                if best is None or score < best[0]:
                    best = (score, rect_index, x, y)
        if best is None:
            return None
        _, _, x, y = best
        placed = dict(group)
        placed["x"] = x
        placed["y"] = y
        packed.append(placed)
        used_w = max(used_w, x + w)
        used_h = max(used_h, y + h)
        free_rects = _split_free_rectangles(free_rects, (x, y, w + gap, h + gap))
    return packed, used_w, used_h


def _candidate_widths(groups, max_w):
    max_group_w = max(int(group["w"]) for group in groups)
    total_area = sum(int(group["w"]) * int(group["h"]) for group in groups)
    ideal = max(max_group_w, int(math.ceil(math.sqrt(max(1, total_area)))))
    values = {max_group_w, min(max_w, ideal), max_w}
    for scale in (0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0):
        values.add(min(max_w, max(max_group_w, int(math.ceil(ideal * scale)))))
    width = max_group_w
    while width < max_w:
        values.add(width)
        width = max(width + 1, int(math.ceil(width * 1.35)))
    return sorted(value for value in values if max_group_w <= value <= max_w)


def pack_groups_bounded(groups, gap, max_w, max_h, power_of_two=False):
    if not groups:
        return [], 1, 1
    gap = max(0, int(gap))
    max_w = max(1, int(max_w))
    max_h = max(1, int(max_h))
    if max(int(group["w"]) for group in groups) > max_w or max(int(group["h"]) for group in groups) > max_h:
        return None

    total_area = sum(int(group["w"]) * int(group["h"]) for group in groups)
    best = None
    for candidate_w in _candidate_widths(groups, max_w):
        result = _maxrects_pack(groups, candidate_w, max_h, gap)
        if result is None:
            continue
        packed, used_w, used_h = result
        out_w = next_power_of_two(used_w) if power_of_two else max(1, used_w)
        out_h = next_power_of_two(used_h) if power_of_two else max(1, used_h)
        if out_w > max_w or out_h > max_h:
            continue
        score = (out_w * out_h, max(out_w, out_h), abs(out_w - out_h), used_w + used_h)
        if best is None or score < best[0]:
            best = (score, packed, out_w, out_h)

    if best is None:
        return None
    overlaps = detect_layout_overlaps(best[1])
    if overlaps:
        raise RuntimeError(f"Internal packing error: generated overlapping rectangles: {overlaps[:8]}")
    return best[1], best[2], best[3]


def pack_groups(groups, gap, max_size=4096, power_of_two=False):
    if not groups:
        return [], 1, 1
    max_size = min(4096, max(1, int(max_size)))
    largest_w = max(int(group["w"]) for group in groups)
    largest_h = max(int(group["h"]) for group in groups)
    if largest_w > max_size or largest_h > max_size:
        raise RuntimeError(
            f"One UV island group is {largest_w}x{largest_h}px, above the {max_size}px limit. "
            "Check UV range, source resolution or margin size."
        )
    packed = pack_groups_bounded(groups, gap, max_size, max_size, power_of_two=power_of_two)
    if packed is None:
        raise RuntimeError(
            f"Cannot pack {len(groups)} UV groups inside {max_size}x{max_size}px. "
            "Lower reference resolution or margins, or inspect unusually large UV ranges."
        )
    return packed


def collect_diagnostics(faces, islands, groups, packed_groups=None, raw_w=None, raw_h=None):
    packed_groups = packed_groups if packed_groups is not None else groups
    if raw_w is None:
        raw_w = max((int(group.get("x", 0)) + int(group.get("w", 0)) for group in packed_groups), default=1)
    if raw_h is None:
        raw_h = max((int(group.get("y", 0)) + int(group.get("h", 0)) for group in packed_groups), default=1)
    occupied = sum(int(group.get("w", 0)) * int(group.get("h", 0)) for group in groups)
    stack_groups = [group for group in groups if int(group.get("stack_count", 1)) > 1]
    try:
        padded_w, padded_h = substance_canvas_size(raw_w, raw_h)
    except RuntimeError:
        padded_w = padded_h = None
    return {
        "input_face_count": len(faces),
        "island_count": len(islands),
        "group_count": len(groups),
        "raw_used_width": int(raw_w),
        "raw_used_height": int(raw_h),
        "packed_width": padded_w,
        "packed_height": padded_h,
        "fill_percent": round((occupied / max(1, int(raw_w) * int(raw_h))) * 100.0, 2),
        "overlap_warnings": detect_layout_overlaps(packed_groups) if packed_groups else [],
        "stack_detections": [
            {"group_index": group["index"], "island_indices": list(group["island_indices"]), "stack_count": group["stack_count"]}
            for group in stack_groups
        ],
    }


def build_and_pack_cluster(faces, ref_w, ref_h, margin_px, *, has_texture=True, gap=0, max_size=4096):
    """High-level pure-Python helper useful for tests and future integration."""
    if has_texture:
        islands, groups, _ = build_texture_bsp_groups(faces, ref_w, ref_h, margin_px)
    else:
        islands, groups, _ = build_no_texture_dense_groups(faces, ref_w, ref_h, margin_px)
    packed_groups, raw_w, raw_h = pack_groups(groups, gap=gap, max_size=max_size, power_of_two=False)
    packed_by_index = {group["index"]: group for group in packed_groups}
    face_to_group = {}
    for face_index in range(len(faces)):
        for group in groups:
            if face_index in group["face_indices"]:
                face_to_group[face_index] = packed_by_index[group["index"]]
                break
    diagnostics = collect_diagnostics(faces, islands, groups, packed_groups, raw_w, raw_h)
    return islands, packed_groups, face_to_group, diagnostics
