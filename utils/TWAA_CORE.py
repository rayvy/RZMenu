"""Pure-Python UV crop/repack core for RZMenu TexWorks AutoAtlas.

The core has deliberately no Blender dependency.  The integration layer passes
plain face dictionaries that MUST already be filtered to one Blender material.
This module turns those faces into material-local UV islands, crop rectangles,
packed layout groups and diagnostics.

There are two different workflows:

* texture mode: crop useful source regions and repack them without resizing.
  Pixel density and pixel integrity are preserved.  Optional rotation is only
  90 degrees.  Mirroring fields are exposed for the integration layer, but are
  not chosen automatically because mirroring does not improve rectangle fit.

* no-texture mode: create a dense editable cluster layout.  UV islands receive
  rectangle area proportional to useful geometry surface contribution.  The
  core scales the generated rectangles to occupy a Substance-compatible canvas.

IMPORTANT INTEGRATION CONTRACT
------------------------------
The Blender/image side must use the returned packed group metadata.  In
particular, when ``rotation == 90`` it must rotate both exported crop pixels and
remapped UVs by exactly one quarter turn.  The core cannot crop PNG files by
itself because image IO intentionally lives outside this module.

The core can diagnose mixed ``material_index`` input, but cannot magically know
which material was intended.  Callers should pass one material only.
"""

from __future__ import annotations

import math
from collections import defaultdict
from copy import deepcopy

SUBSTANCE_SIZES = (128, 256, 512, 1024, 2048, 4096)
EPSILON = 1.0e-12
UV_ROUND_DIGITS = 6
DEFAULT_MAX_SIZE = 4096


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def next_power_of_two(value):
    value = max(1, int(math.ceil(value)))
    return 1 << (value - 1).bit_length()


def substance_side(value, max_size=DEFAULT_MAX_SIZE):
    """Return the smallest allowed Substance side containing ``value`` pixels."""
    value = max(1, int(math.ceil(value)))
    for side in SUBSTANCE_SIZES:
        if side <= int(max_size) and value <= side:
            return side
    raise RuntimeError(
        f"Required canvas side {value}px is above the {int(max_size)}px limit."
    )


def substance_canvas_size(raw_w, raw_h, max_size=DEFAULT_MAX_SIZE):
    """Pad raw used dimensions to independently selected Substance sides."""
    return substance_side(raw_w, max_size), substance_side(raw_h, max_size)


def rounded_uv(uv):
    return round(float(uv[0]), UV_ROUND_DIGITS), round(float(uv[1]), UV_ROUND_DIGITS)


def _safe_surface_area(face):
    try:
        area = float(face.get("surface_area", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return area if math.isfinite(area) and area > 0.0 else 0.0


def _bbox_from_uvs(uvs):
    if not uvs:
        return 0.0, 0.0, 0.0, 0.0
    us = [float(uv[0]) for uv in uvs]
    vs = [float(uv[1]) for uv in uvs]
    return min(us), min(vs), max(us), max(vs)


def _bbox_area(item):
    return max(0.0, float(item["u_max"]) - float(item["u_min"])) * max(
        0.0, float(item["v_max"]) - float(item["v_min"])
    )


def _canonical_polygon(uvs):
    """Rotation- and winding-independent UV polygon signature."""
    points = tuple(rounded_uv(uv) for uv in uvs)
    if not points:
        return ()
    variants = []
    for sequence in (points, tuple(reversed(points))):
        for offset in range(len(sequence)):
            variants.append(sequence[offset:] + sequence[:offset])
    return min(variants)


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
            if len(uv) < 2:
                raise ValueError(f"Face {face_index} contains malformed UV coordinate {uv!r}.")
            if not math.isfinite(float(uv[0])) or not math.isfinite(float(uv[1])):
                raise ValueError(f"Face {face_index} contains invalid UV coordinate {uv!r}.")


def inspect_material_locality(faces):
    """Return material/object/mesh input summary without filtering anything."""
    material_indices = sorted({face.get("material_index") for face in faces})
    objects = sorted({str(face.get("object", "")) for face in faces})
    meshes = sorted({str(face.get("mesh", "")) for face in faces})
    warnings = []
    if len(material_indices) > 1:
        warnings.append(
            "Core received faces with multiple material_index values: "
            f"{material_indices!r}. The Blender integration must pre-filter one material."
        )
    return {
        "material_indices": material_indices,
        "object_names": objects,
        "mesh_names": meshes,
        "mixed_material_input": len(material_indices) > 1,
        "input_warnings": warnings,
    }


def assert_material_local_faces(faces):
    locality = inspect_material_locality(faces)
    if locality["mixed_material_input"]:
        raise ValueError(locality["input_warnings"][0])
    return locality


# ---------------------------------------------------------------------------
# UV islands and stacked UV detection
# ---------------------------------------------------------------------------


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


def _normalized_shape_signature(faces, face_indices, resolution=256):
    """Cheap normalized shape fingerprint used by stacked-island detection."""
    u_min, v_min, u_max, v_max = face_group_bbox(faces, face_indices)
    width = max(EPSILON, u_max - u_min)
    height = max(EPSILON, v_max - v_min)
    points = set()
    edges = set()
    for face_index in face_indices:
        normalized = []
        for u, v in faces[face_index]["uvs"]:
            point = (
                int(round(((float(u) - u_min) / width) * resolution)),
                int(round(((float(v) - v_min) / height) * resolution)),
            )
            normalized.append(point)
            points.add(point)
        for corner, point_a in enumerate(normalized):
            point_b = normalized[(corner + 1) % len(normalized)]
            edges.add(tuple(sorted((point_a, point_b))))
    return frozenset(points), frozenset(edges)


def _set_similarity(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def build_uv_islands(faces):
    """Build material-local UV islands from shared UV edges.

    Duplicate UV polygons are collapsed while adjacency is traversed and then
    expanded back into the output.  This prevents perfectly stacked layers from
    exploding the graph while retaining all original face indices.
    """
    _validate_faces(faces)
    if not faces:
        return []

    signature_to_rep = {}
    representative_faces = []
    duplicate_members = defaultdict(list)

    for face_index, face in enumerate(faces):
        signature = _canonical_polygon(face["uvs"])
        rep_index = signature_to_rep.get(signature)
        if rep_index is None:
            rep_index = len(representative_faces)
            signature_to_rep[signature] = rep_index
            representative_faces.append(face_index)
        duplicate_members[rep_index].append(face_index)

    _, find, union = _union_find(len(representative_faces))
    edge_owners = defaultdict(list)
    for rep_index, face_index in enumerate(representative_faces):
        uvs = faces[face_index]["uvs"]
        for corner, uv_a in enumerate(uvs):
            uv_b = uvs[(corner + 1) % len(uvs)]
            edge_owners[tuple(sorted((rounded_uv(uv_a), rounded_uv(uv_b))))].append(rep_index)

    for owners in edge_owners.values():
        if len(owners) > 1:
            first = owners[0]
            for owner in owners[1:]:
                union(first, owner)

    grouped_reps = defaultdict(list)
    for rep_index in range(len(representative_faces)):
        grouped_reps[find(rep_index)].append(rep_index)

    islands = []
    ordered = sorted(grouped_reps.values(), key=lambda reps: min(representative_faces[r] for r in reps))
    for island_index, rep_indices in enumerate(ordered):
        face_indices = sorted(
            face_index
            for rep_index in rep_indices
            for face_index in duplicate_members[rep_index]
        )
        u_min, v_min, u_max, v_max = face_group_bbox(faces, face_indices)
        points, edges = _normalized_shape_signature(faces, face_indices)
        duplicate_counts = [len(duplicate_members[rep]) for rep in rep_indices]
        stack_count = max(1, min(duplicate_counts) if duplicate_counts else 1)
        surface_total = sum(_safe_surface_area(faces[index]) for index in face_indices)
        islands.append({
            "index": island_index,
            "face_indices": face_indices,
            "u_min": u_min,
            "v_min": v_min,
            "u_max": u_max,
            "v_max": v_max,
            "shape_points": points,
            "shape_edges": edges,
            "stack_count": stack_count,
            "duplicate_polygon_count": sum(max(0, count - 1) for count in duplicate_counts),
            "surface_area_total": surface_total,
            "surface_area": surface_total / max(1, stack_count),
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
    if min(aw, bw) / max(aw, bw) < threshold:
        return False
    if min(ah, bh) / max(ah, bh) < threshold:
        return False
    if bbox_overlap_ratio(a, b) < threshold:
        return False
    if "shape_points" in a and "shape_points" in b:
        if _set_similarity(a["shape_points"], b["shape_points"]) < threshold:
            return False
    if "shape_edges" in a and "shape_edges" in b:
        if _set_similarity(a["shape_edges"], b["shape_edges"]) < threshold:
            return False
    return True


def group_stacked_islands(islands, threshold=0.95):
    """Merge islands that sample effectively the same source texture region."""
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

    groups = []
    ordered = sorted(grouped.values(), key=lambda chunk: min(i["index"] for i in chunk))
    for group_index, chunk in enumerate(ordered):
        face_indices = sorted(index for island in chunk for index in island["face_indices"])
        stack_count = sum(max(1, int(island.get("stack_count", 1))) for island in chunk)
        surface_total = sum(float(island.get("surface_area_total", island.get("surface_area", 0.0))) for island in chunk)
        groups.append({
            "index": group_index,
            "island_indices": sorted(island["index"] for island in chunk),
            "face_indices": face_indices,
            "u_min": min(island["u_min"] for island in chunk),
            "v_min": min(island["v_min"] for island in chunk),
            "u_max": max(island["u_max"] for island in chunk),
            "v_max": max(island["v_max"] for island in chunk),
            "stack_count": max(1, stack_count),
            "duplicate_polygon_count": sum(int(island.get("duplicate_polygon_count", 0)) for island in chunk),
            "surface_area_total": surface_total,
            "surface_area": surface_total / max(1, stack_count),
        })
    return groups


# ---------------------------------------------------------------------------
# Crop groups
# ---------------------------------------------------------------------------


def _decorate_crop_group(group, ref_w, ref_h, margin_px):
    result = dict(group)
    source_w = max(1, int(math.ceil((float(group["u_max"]) - float(group["u_min"])) * int(ref_w))))
    source_h = max(1, int(math.ceil((float(group["v_max"]) - float(group["v_min"])) * int(ref_h))))
    result.update({
        "mode": "texture",
        "content_w": source_w,
        "content_h": source_h,
        "source_content_w": source_w,
        "source_content_h": source_h,
        "packed_content_w": source_w,
        "packed_content_h": source_h,
        "margin_px": int(margin_px),
        "w": source_w + int(margin_px) * 2,
        "h": source_h + int(margin_px) * 2,
        "rotation": 0,
        "flip_x": False,
        "flip_y": False,
    })
    return result


def _face_bbox_gap_split(faces, face_indices, ref_w, ref_h, margin_px, min_gap_px=16):
    """Find a real empty UV corridor and split only across that corridor.

    This never uses median cuts, so it cannot manufacture hundreds of strips by
    slicing continuously occupied regions.  It is intentionally conservative.
    """
    if len(face_indices) < 8:
        return None
    boxes = [(index, face_uv_bbox(faces[index])) for index in face_indices]
    best = None
    for axis, ref_size in ((0, ref_w), (1, ref_h)):
        intervals = []
        for face_index, box in boxes:
            low = box[axis]
            high = box[axis + 2]
            intervals.append((low, high, face_index))
        intervals.sort(key=lambda item: (item[0], item[1], item[2]))
        running_high = intervals[0][1]
        for position in range(1, len(intervals)):
            gap_uv = intervals[position][0] - running_high
            gap_px = gap_uv * float(ref_size)
            if gap_px >= max(float(min_gap_px), float(margin_px) * 4.0):
                left = [entry[2] for entry in intervals[:position]]
                right = [entry[2] for entry in intervals[position:]]
                if left and right:
                    score = gap_px
                    if best is None or score > best[0]:
                        best = (score, left, right)
            running_high = max(running_high, intervals[position][1])
    if best is None:
        return None
    return best[1], best[2]


def _pixel_bbox_area(faces, face_indices, ref_w, ref_h, margin_px):
    u_min, v_min, u_max, v_max = face_group_bbox(faces, face_indices)
    width = max(1, int(math.ceil((u_max - u_min) * int(ref_w)))) + int(margin_px) * 2
    height = max(1, int(math.ceil((v_max - v_min) * int(ref_h)))) + int(margin_px) * 2
    return width * height


def _split_sparse_crop_groups(
    faces,
    base_groups,
    ref_w,
    ref_h,
    margin_px,
    min_saving=0.55,
    max_groups=256,
):
    """Split only very sparse groups with a genuine empty corridor."""
    queue = [dict(group) for group in base_groups]
    output = []
    while queue:
        group = queue.pop(0)
        if len(output) + len(queue) >= max_groups:
            output.append(group)
            continue
        split = _face_bbox_gap_split(faces, group["face_indices"], ref_w, ref_h, margin_px)
        if split is None:
            output.append(group)
            continue
        left, right = split
        parent_area = _pixel_bbox_area(faces, group["face_indices"], ref_w, ref_h, margin_px)
        child_area = _pixel_bbox_area(faces, left, ref_w, ref_h, margin_px) + _pixel_bbox_area(
            faces, right, ref_w, ref_h, margin_px
        )
        saving = 1.0 - child_area / max(1, parent_area)
        if saving < float(min_saving):
            output.append(group)
            continue
        children = []
        for face_indices in (left, right):
            u_min, v_min, u_max, v_max = face_group_bbox(faces, face_indices)
            child = dict(group)
            child.update({
                "face_indices": sorted(face_indices),
                "u_min": u_min,
                "v_min": v_min,
                "u_max": u_max,
                "v_max": v_max,
                "split_from_sparse_parent": True,
            })
            children.append(child)
        queue.extend(children)
    for index, group in enumerate(output):
        group["index"] = index
    return output


def _mapping_from_groups(groups):
    mapping = {}
    for group in groups:
        for face_index in group["face_indices"]:
            mapping[face_index] = group
    return mapping


def build_texture_groups(
    faces,
    ref_w,
    ref_h,
    margin_px,
    *,
    split_sparse=True,
    strict_material=False,
):
    """Build fixed-pixel crop rectangles from useful material-local UV regions."""
    _validate_faces(faces)
    if strict_material:
        assert_material_local_faces(faces)
    islands = build_uv_islands(faces)
    groups = group_stacked_islands(islands)
    if split_sparse:
        groups = _split_sparse_crop_groups(faces, groups, ref_w, ref_h, margin_px)
    groups = [_decorate_crop_group(group, ref_w, ref_h, margin_px) for group in groups]
    return islands, groups, _mapping_from_groups(groups)


def build_groups(faces, ref_w, ref_h, margin_px):
    """Compatibility alias for crop group construction."""
    return build_texture_groups(faces, ref_w, ref_h, margin_px, split_sparse=False)


def build_texture_bsp_groups(faces, ref_w, ref_h, margin_px):
    """Compatibility name.  Uses safe empty-corridor splitting, never median BSP."""
    return build_texture_groups(faces, ref_w, ref_h, margin_px, split_sparse=True)


# ---------------------------------------------------------------------------
# No-texture dense groups
# ---------------------------------------------------------------------------


def _island_aspect(island):
    width = max(EPSILON, float(island["u_max"]) - float(island["u_min"]))
    height = max(EPSILON, float(island["v_max"]) - float(island["v_min"]))
    return max(0.125, min(8.0, width / height))


def _decorate_dense_group(group, content_w, content_h, margin_px):
    result = dict(group)
    content_w = max(1, int(content_w))
    content_h = max(1, int(content_h))
    result.update({
        "mode": "no_texture",
        "content_w": content_w,
        "content_h": content_h,
        "source_content_w": content_w,
        "source_content_h": content_h,
        "packed_content_w": content_w,
        "packed_content_h": content_h,
        "margin_px": int(margin_px),
        "w": content_w + int(margin_px) * 2,
        "h": content_h + int(margin_px) * 2,
        "rotation": 0,
        "flip_x": False,
        "flip_y": False,
    })
    return result


def build_no_texture_dense_groups(
    faces,
    ref_w,
    ref_h,
    margin_px,
    *,
    min_editable_side=12,
    strict_material=False,
):
    """Build island-based editable groups weighted by useful surface area.

    ``ref_w * ref_h`` is treated as the desired working pixel budget.  Final
    fitting and near-full canvas utilization are performed by
    ``pack_no_texture_dense_groups`` or ``build_and_pack_cluster``.
    """
    _validate_faces(faces)
    if strict_material:
        assert_material_local_faces(faces)
    islands = build_uv_islands(faces)
    if not islands:
        return [], [], {}

    base_groups = group_stacked_islands(islands)
    total_area = sum(max(EPSILON, float(group.get("surface_area", 0.0))) for group in base_groups)
    desired_pixels = max(1, int(ref_w) * int(ref_h))
    groups = []
    for index, group in enumerate(base_groups):
        area = max(EPSILON, float(group.get("surface_area", 0.0)))
        aspect = _island_aspect(group)
        budget = max(float(min_editable_side) ** 2, desired_pixels * area / total_area)
        content_w = max(int(min_editable_side), int(round(math.sqrt(budget * aspect))))
        content_h = max(int(min_editable_side), int(round(math.sqrt(budget / aspect))))
        dense = dict(group)
        dense["index"] = index
        dense["allocation_weight"] = area / total_area
        groups.append(_decorate_dense_group(dense, content_w, content_h, margin_px))
    return islands, groups, _mapping_from_groups(groups)


# ---------------------------------------------------------------------------
# Rectangle packing
# ---------------------------------------------------------------------------


def _rect_intersects(a, b):
    return not (
        a[0] + a[2] <= b[0]
        or b[0] + b[2] <= a[0]
        or a[1] + a[3] <= b[1]
        or b[1] + b[3] <= a[1]
    )


def _rect_contains(a, b):
    return (
        a[0] <= b[0]
        and a[1] <= b[1]
        and a[0] + a[2] >= b[0] + b[2]
        and a[1] + a[3] >= b[1] + b[3]
    )


def _prune_free_rectangles(rectangles):
    cleaned = []
    for rect in rectangles:
        if rect[2] <= 0 or rect[3] <= 0:
            continue
        if any(_rect_contains(other, rect) for other in rectangles if other is not rect):
            continue
        if rect not in cleaned:
            cleaned.append(rect)
    return cleaned


def _split_free_rectangles(free_rectangles, used):
    output = []
    ux, uy, uw, uh = used
    for free in free_rectangles:
        if not _rect_intersects(free, used):
            output.append(free)
            continue
        fx, fy, fw, fh = free
        if ux > fx:
            output.append((fx, fy, ux - fx, fh))
        if ux + uw < fx + fw:
            output.append((ux + uw, fy, fx + fw - (ux + uw), fh))
        if uy > fy:
            output.append((fx, fy, fw, uy - fy))
        if uy + uh < fy + fh:
            output.append((fx, uy + uh, fw, fy + fh - (uy + uh)))
    return _prune_free_rectangles(output)


def _group_orientations(group, allow_rotate):
    width = int(group["w"])
    height = int(group["h"])
    yield 0, width, height
    if allow_rotate and width != height:
        yield 90, height, width


def _apply_orientation(group, rotation, x, y, width, height):
    packed = dict(group)
    packed["x"] = int(x)
    packed["y"] = int(y)
    packed["rotation"] = int(rotation)
    packed["w"] = int(width)
    packed["h"] = int(height)
    if rotation == 90:
        packed["packed_content_w"] = int(group["source_content_h"])
        packed["packed_content_h"] = int(group["source_content_w"])
    else:
        packed["packed_content_w"] = int(group["source_content_w"])
        packed["packed_content_h"] = int(group["source_content_h"])
    return packed


def maxrects_pack(groups, canvas_w, canvas_h, *, gap=0, allow_rotate=False):
    """Pack rectangles into an exact canvas using a Best Short Side Fit variant."""
    canvas_w = max(1, int(canvas_w))
    canvas_h = max(1, int(canvas_h))
    gap = max(0, int(gap))
    free_rectangles = [(0, 0, canvas_w, canvas_h)]
    packed = []

    ordered = sorted(
        groups,
        key=lambda group: (
            max(int(group["w"]), int(group["h"])),
            int(group["w"]) * int(group["h"]),
            min(int(group["w"]), int(group["h"])),
            -int(group.get("index", 0)),
        ),
        reverse=True,
    )

    for group in ordered:
        best = None
        for rotation, width, height in _group_orientations(group, allow_rotate):
            fit_w = width + gap
            fit_h = height + gap
            for free in free_rectangles:
                fx, fy, fw, fh = free
                if fit_w > fw or fit_h > fh:
                    continue
                short_side = min(fw - fit_w, fh - fit_h)
                long_side = max(fw - fit_w, fh - fit_h)
                score = (short_side, long_side, fy, fx, rotation)
                if best is None or score < best[0]:
                    best = (score, rotation, fx, fy, width, height, fit_w, fit_h)
        if best is None:
            return None
        _, rotation, x, y, width, height, fit_w, fit_h = best
        packed.append(_apply_orientation(group, rotation, x, y, width, height))
        free_rectangles = _split_free_rectangles(free_rectangles, (x, y, fit_w, fit_h))

    packed.sort(key=lambda group: int(group.get("index", 0)))
    used_w = max((int(group["x"]) + int(group["w"]) for group in packed), default=1)
    used_h = max((int(group["y"]) + int(group["h"]) for group in packed), default=1)
    return packed, used_w, used_h


def shelf_pack(groups, width, gap):
    """Compatibility helper retained for external callers.

    New code should use maxrects packing.  This wrapper packs into a tall canvas
    and returns raw used bounds.
    """
    total_height = sum(int(group["h"]) + max(0, int(gap)) for group in groups) or 1
    result = maxrects_pack(groups, int(width), total_height, gap=gap, allow_rotate=False)
    if result is None:
        return [], 0, 0
    return result


def _candidate_raw_sides(groups, max_size):
    largest_w = max(int(group["w"]) for group in groups)
    total_area = sum(int(group["w"]) * int(group["h"]) for group in groups)
    ideal = int(math.ceil(math.sqrt(max(1, total_area))))
    values = {largest_w, ideal, int(max_size)}
    current = largest_w
    while current < int(max_size):
        values.add(current)
        current = max(current + 1, int(math.ceil(current * 1.25)))
    return sorted(value for value in values if largest_w <= value <= int(max_size))


def pack_groups(groups, gap=0, max_size=DEFAULT_MAX_SIZE, power_of_two=False, allow_rotate=False):
    """Pack into raw dimensions no larger than max_size.

    Compatibility API: returns ``packed_groups, raw_used_w, raw_used_h``.  The
    Blender side may pad raw bounds afterwards.  For Substance-aware shrinking,
    prefer ``pack_texture_groups_substance``.
    """
    if not groups:
        return [], 1, 1
    max_size = int(max_size)
    largest_w = max(int(group["w"]) for group in groups)
    largest_h = max(int(group["h"]) for group in groups)
    if min(largest_w, largest_h) > max_size or (largest_w > max_size and largest_h > max_size):
        raise RuntimeError(
            f"One UV group is larger than the {max_size}px limit: {largest_w}x{largest_h}."
        )

    best = None
    for width in _candidate_raw_sides(groups, max_size):
        result = maxrects_pack(groups, width, max_size, gap=gap, allow_rotate=allow_rotate)
        if result is None:
            continue
        packed, used_w, used_h = result
        if used_w > max_size or used_h > max_size:
            continue
        out_w = next_power_of_two(used_w) if power_of_two else used_w
        out_h = next_power_of_two(used_h) if power_of_two else used_h
        if out_w > max_size or out_h > max_size:
            continue
        score = (out_w * out_h, max(out_w, out_h), out_h, out_w)
        if best is None or score < best[0]:
            best = (score, packed, out_w, out_h)
    if best is None:
        raise RuntimeError(
            f"Cannot pack UV groups into {max_size}x{max_size}. "
            "Reduce margins, inspect UV ranges, or split the component."
        )
    return best[1], best[2], best[3]


def pack_groups_bounded(groups, gap, max_w, max_h, power_of_two=False, allow_rotate=False):
    """Compatibility bounded pack.  Returns None when rectangles do not fit."""
    if not groups:
        return [], 1, 1
    result = maxrects_pack(groups, int(max_w), int(max_h), gap=gap, allow_rotate=allow_rotate)
    if result is None:
        return None
    packed, used_w, used_h = result
    out_w = next_power_of_two(used_w) if power_of_two else used_w
    out_h = next_power_of_two(used_h) if power_of_two else used_h
    if out_w > int(max_w) or out_h > int(max_h):
        return None
    return packed, out_w, out_h


def _substance_candidates(max_size=DEFAULT_MAX_SIZE):
    sides = [side for side in SUBSTANCE_SIZES if side <= int(max_size)]
    return sorted(((w, h) for w in sides for h in sides), key=lambda pair: (pair[0] * pair[1], max(pair), pair[1], pair[0]))


def _annotate_canvas(groups, canvas_w, canvas_h):
    output = []
    for group in groups:
        copy = dict(group)
        copy["canvas_w"] = int(canvas_w)
        copy["canvas_h"] = int(canvas_h)
        output.append(copy)
    return output


def pack_texture_groups_substance(groups, *, gap=0, max_size=DEFAULT_MAX_SIZE, allow_rotate=False):
    """Pack fixed-size texture crops into the smallest valid Substance canvas."""
    if not groups:
        return [], 128, 128, 1, 1
    best = None
    total_area = sum(int(group["w"]) * int(group["h"]) for group in groups)
    for canvas_w, canvas_h in _substance_candidates(max_size):
        result = maxrects_pack(groups, canvas_w, canvas_h, gap=gap, allow_rotate=allow_rotate)
        if result is None:
            continue
        packed, used_w, used_h = result
        fill = total_area / max(1, canvas_w * canvas_h)
        score = (canvas_w * canvas_h, -fill, max(canvas_w, canvas_h), canvas_h, canvas_w)
        if best is None or score < best[0]:
            best = (score, packed, canvas_w, canvas_h, used_w, used_h)
    if best is None:
        raise RuntimeError(
            f"Cannot fit texture crop rectangles inside the Substance limit {int(max_size)}x{int(max_size)}. "
            "The used source pixels exceed one cluster; inspect UV ranges or split the material component."
        )
    _, packed, canvas_w, canvas_h, used_w, used_h = best
    return _annotate_canvas(packed, canvas_w, canvas_h), canvas_w, canvas_h, used_w, used_h


def _rescale_dense_groups(groups, scale, min_editable_side):
    output = []
    for group in groups:
        aspect = max(0.125, min(8.0, float(group["content_w"]) / max(1.0, float(group["content_h"]))))
        base_area = max(1.0, float(group["content_w"]) * float(group["content_h"]))
        target_area = max(float(min_editable_side) ** 2, base_area * scale * scale)
        width = max(int(min_editable_side), int(round(math.sqrt(target_area * aspect))))
        height = max(int(min_editable_side), int(round(math.sqrt(target_area / aspect))))
        output.append(_decorate_dense_group(group, width, height, int(group.get("margin_px", 0))))
    return output


def _fit_dense_groups_to_canvas(
    groups,
    canvas_w,
    canvas_h,
    *,
    gap,
    allow_rotate,
    min_editable_side,
):
    """Return the largest shared scale that fits an exact canvas, or None."""
    low = 0.0
    high = 4.0
    best = None
    for _ in range(28):
        scale = (low + high) * 0.5
        scaled = _rescale_dense_groups(groups, scale, min_editable_side)
        result = maxrects_pack(scaled, canvas_w, canvas_h, gap=gap, allow_rotate=allow_rotate)
        if result is None:
            high = scale
        else:
            packed, used_w, used_h = result
            best = (packed, used_w, used_h, scale)
            low = scale
    return best


def pack_no_texture_dense_groups(
    groups,
    *,
    target_w,
    target_h,
    gap=0,
    allow_rotate=True,
    min_editable_side=12,
    max_size=DEFAULT_MAX_SIZE,
):
    """Scale generated island rectangles into an efficient Substance canvas.

    ``target_w * target_h`` is a quality budget, not a mandatory empty slab.
    Every compatible rectangular canvas up to that area is considered.  The
    winner maximizes useful editable pixels first, then prefers less blank
    padding.  This allows results such as 128x4096 when that shape is genuinely
    useful, while avoiding a 1024x512 canvas that contains only a 512x512 square.
    """
    target_canvas_w, target_canvas_h = substance_canvas_size(target_w, target_h, max_size)
    budget_area = target_canvas_w * target_canvas_h
    candidates = [
        (canvas_w, canvas_h)
        for canvas_w, canvas_h in _substance_candidates(max_size)
        if canvas_w * canvas_h <= budget_area
    ]
    if not groups:
        return [], 128, 128, 1, 1

    best = None
    for canvas_w, canvas_h in candidates:
        fitted = _fit_dense_groups_to_canvas(
            groups,
            canvas_w,
            canvas_h,
            gap=gap,
            allow_rotate=allow_rotate,
            min_editable_side=min_editable_side,
        )
        if fitted is None:
            continue
        packed, used_w, used_h, scale = fitted
        content_area = sum(int(group["packed_content_w"]) * int(group["packed_content_h"]) for group in packed)
        rectangle_area = sum(int(group["w"]) * int(group["h"]) for group in packed)
        canvas_area = canvas_w * canvas_h
        fill = rectangle_area / max(1, canvas_area)
        useful_density_score = content_area * fill
        score = (
            -useful_density_score,  # reward usable resolution only when the canvas is actually occupied
            -fill,                  # aggressively avoid giant mostly-empty canvases
            -content_area,          # then preserve as many editable pixels as possible
            canvas_area,
            max(canvas_w, canvas_h),
            canvas_h,
            canvas_w,
        )
        if best is None or score < best[0]:
            best = (score, packed, canvas_w, canvas_h, used_w, used_h, scale)

    if best is None:
        raise RuntimeError(
            f"Cannot fit minimum editable no-texture islands inside the {budget_area}px budget. "
            "Use a larger fallback canvas, smaller margins, or provide coherent geometry islands."
        )
    _, packed, canvas_w, canvas_h, used_w, used_h, _ = best
    return _annotate_canvas(packed, canvas_w, canvas_h), canvas_w, canvas_h, used_w, used_h


# ---------------------------------------------------------------------------
# Diagnostics and high-level workflow
# ---------------------------------------------------------------------------


def detect_layout_overlaps(groups):
    warnings = []
    for left in range(len(groups)):
        a = groups[left]
        rect_a = (int(a.get("x", 0)), int(a.get("y", 0)), int(a["w"]), int(a["h"]))
        for right in range(left + 1, len(groups)):
            b = groups[right]
            rect_b = (int(b.get("x", 0)), int(b.get("y", 0)), int(b["w"]), int(b["h"]))
            if _rect_intersects(rect_a, rect_b):
                warnings.append({"group_a": int(a.get("index", left)), "group_b": int(b.get("index", right))})
    return warnings


def _stack_detections(groups):
    detections = []
    for group in groups:
        if int(group.get("stack_count", 1)) > 1 or int(group.get("duplicate_polygon_count", 0)) > 0:
            detections.append({
                "group_index": int(group.get("index", 0)),
                "island_indices": list(group.get("island_indices", [])),
                "stack_count": int(group.get("stack_count", 1)),
                "duplicate_polygon_count": int(group.get("duplicate_polygon_count", 0)),
                "median_surface_area": float(group.get("surface_area", 0.0)),
            })
    return detections


def collect_diagnostics(
    faces,
    islands,
    groups,
    *,
    raw_used_w,
    raw_used_h,
    canvas_w,
    canvas_h,
    mode,
):
    locality = inspect_material_locality(faces)
    rectangle_area = sum(int(group["w"]) * int(group["h"]) for group in groups)
    canvas_area = max(1, int(canvas_w) * int(canvas_h))
    return {
        "mode": mode,
        "input_face_count": len(faces),
        "island_count": len(islands),
        "group_count": len(groups),
        "raw_used_w": int(raw_used_w),
        "raw_used_h": int(raw_used_h),
        "canvas_w": int(canvas_w),
        "canvas_h": int(canvas_h),
        "substance_canvas": (int(canvas_w), int(canvas_h)),
        "rectangle_fill_percent": rectangle_area * 100.0 / canvas_area,
        "raw_bounds_fill_percent": int(raw_used_w) * int(raw_used_h) * 100.0 / canvas_area,
        "overlap_warnings": detect_layout_overlaps(groups),
        "stack_detections": _stack_detections(groups),
        **locality,
    }


def build_and_pack_cluster(
    faces,
    ref_w,
    ref_h,
    margin_px,
    *,
    has_texture,
    gap=0,
    max_size=DEFAULT_MAX_SIZE,
    allow_rotate=False,
    strict_material=False,
    split_sparse=True,
    min_editable_side=12,
):
    """Main API: build groups, pack them and return diagnostics.

    Returns ``islands, packed_groups, face_to_group, diagnostics``.
    """
    _validate_faces(faces)
    if strict_material:
        assert_material_local_faces(faces)

    if has_texture:
        islands, groups, _ = build_texture_groups(
            faces,
            ref_w,
            ref_h,
            margin_px,
            split_sparse=split_sparse,
            strict_material=False,
        )
        packed, canvas_w, canvas_h, raw_w, raw_h = pack_texture_groups_substance(
            groups,
            gap=gap,
            max_size=max_size,
            allow_rotate=allow_rotate,
        )
        mode = "texture"
    else:
        islands, groups, _ = build_no_texture_dense_groups(
            faces,
            ref_w,
            ref_h,
            margin_px,
            min_editable_side=min_editable_side,
            strict_material=False,
        )
        packed, canvas_w, canvas_h, raw_w, raw_h = pack_no_texture_dense_groups(
            groups,
            target_w=ref_w,
            target_h=ref_h,
            gap=gap,
            allow_rotate=allow_rotate,
            min_editable_side=min_editable_side,
            max_size=max_size,
        )
        mode = "no_texture"

    mapping = _mapping_from_groups(packed)
    diagnostics = collect_diagnostics(
        faces,
        islands,
        packed,
        raw_used_w=raw_w,
        raw_used_h=raw_h,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        mode=mode,
    )
    return islands, packed, mapping, diagnostics


# ---------------------------------------------------------------------------
# Legacy preview helper
# ---------------------------------------------------------------------------


def build_single_preview_group(faces, ref_w, ref_h, margin_px):
    """Legacy compatibility helper for preview paths that intentionally use one bbox."""
    _validate_faces(faces)
    if not faces:
        return [], [], {}
    u_min, v_min, u_max, v_max = face_group_bbox(faces, list(range(len(faces))))
    island = {
        "index": 0,
        "face_indices": list(range(len(faces))),
        "u_min": u_min,
        "v_min": v_min,
        "u_max": u_max,
        "v_max": v_max,
    }
    group = _decorate_crop_group({
        **island,
        "island_indices": [0],
        "stack_count": 1,
        "duplicate_polygon_count": 0,
        "surface_area": sum(_safe_surface_area(face) for face in faces),
    }, ref_w, ref_h, margin_px)
    group["x"] = 0
    group["y"] = 0
    return [island], [group], _mapping_from_groups([group])
