"""Pure TWAA UV grouping and rectangle packing helpers.

This module intentionally has no Blender dependency. Callers pass plain Python
face/group dictionaries in and receive plain Python island/group/layout data out.
All bpy/image/TexWorks IO stays in texworks_mc.py or operator/panel modules.
"""

import math


def next_power_of_two(value):
    value = max(1, int(value))
    return 1 << (value - 1).bit_length()


def rounded_uv(uv):
    return (round(float(uv[0]), 6), round(float(uv[1]), 6))


def build_uv_islands(faces):
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra

    edge_owner = {}
    for face_index, face in enumerate(faces):
        uvs = face["uvs"]
        for i, uv_a in enumerate(uvs):
            uv_b = uvs[(i + 1) % len(uvs)]
            edge = tuple(sorted((rounded_uv(uv_a), rounded_uv(uv_b))))
            other = edge_owner.get(edge)
            if other is not None:
                union(face_index, other)
            else:
                edge_owner[edge] = face_index

    grouped = {}
    for i in range(len(faces)):
        grouped.setdefault(find(i), []).append(i)

    islands = []
    for island_index, face_indices in enumerate(grouped.values()):
        all_uv = [uv for face_index in face_indices for uv in faces[face_index]["uvs"]]
        u_values = [uv[0] for uv in all_uv]
        v_values = [uv[1] for uv in all_uv]
        islands.append({
            "index": island_index,
            "face_indices": face_indices,
            "u_min": min(u_values),
            "v_min": min(v_values),
            "u_max": max(u_values),
            "v_max": max(v_values),
        })
    return islands


def bbox_overlap_ratio(a, b):
    x0 = max(a["u_min"], b["u_min"])
    y0 = max(a["v_min"], b["v_min"])
    x1 = min(a["u_max"], b["u_max"])
    y1 = min(a["v_max"], b["v_max"])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    overlap = (x1 - x0) * (y1 - y0)
    area_a = max(0.0, (a["u_max"] - a["u_min"]) * (a["v_max"] - a["v_min"]))
    area_b = max(0.0, (b["u_max"] - b["u_min"]) * (b["v_max"] - b["v_min"]))
    return overlap / max(1.0e-12, min(area_a, area_b))


def bbox_stack_similarity(a, b, threshold=0.95):
    aw = max(0.0, a["u_max"] - a["u_min"])
    ah = max(0.0, a["v_max"] - a["v_min"])
    bw = max(0.0, b["u_max"] - b["u_min"])
    bh = max(0.0, b["v_max"] - b["v_min"])
    if aw <= 1.0e-8 or ah <= 1.0e-8 or bw <= 1.0e-8 or bh <= 1.0e-8:
        return False

    width_similarity = min(aw, bw) / max(aw, bw)
    height_similarity = min(ah, bh) / max(ah, bh)
    if width_similarity < threshold or height_similarity < threshold:
        return False

    acx = (a["u_min"] + a["u_max"]) * 0.5
    acy = (a["v_min"] + a["v_max"]) * 0.5
    bcx = (b["u_min"] + b["u_max"]) * 0.5
    bcy = (b["v_min"] + b["v_max"]) * 0.5
    max_center_delta_x = max(1.0e-6, min(aw, bw) * (1.0 - threshold))
    max_center_delta_y = max(1.0e-6, min(ah, bh) * (1.0 - threshold))
    if abs(acx - bcx) > max_center_delta_x or abs(acy - bcy) > max_center_delta_y:
        return False

    return bbox_overlap_ratio(a, b) >= threshold


def group_stacked_islands(islands):
    parent = list(range(len(islands)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(islands)):
        for j in range(i + 1, len(islands)):
            if bbox_stack_similarity(islands[i], islands[j], threshold=0.95):
                union(i, j)

    grouped = {}
    for i, island in enumerate(islands):
        grouped.setdefault(find(i), []).append(island)

    groups = []
    for group_index, group_islands in enumerate(grouped.values()):
        face_indices = []
        island_indices = []
        for island in group_islands:
            face_indices.extend(island["face_indices"])
            island_indices.append(island["index"])
        u_min = min(i["u_min"] for i in group_islands)
        v_min = min(i["v_min"] for i in group_islands)
        u_max = max(i["u_max"] for i in group_islands)
        v_max = max(i["v_max"] for i in group_islands)
        groups.append({
            "index": group_index,
            "island_indices": sorted(island_indices),
            "face_indices": sorted(face_indices),
            "u_min": u_min,
            "v_min": v_min,
            "u_max": u_max,
            "v_max": v_max,
        })
    return groups


def build_groups(faces, ref_w, ref_h, margin_px):
    islands = build_uv_islands(faces)
    groups = group_stacked_islands(islands)
    face_to_group = {}
    for group in groups:
        content_w = max(1, int(math.ceil((group["u_max"] - group["u_min"]) * ref_w)))
        content_h = max(1, int(math.ceil((group["v_max"] - group["v_min"]) * ref_h)))
        group["content_w"] = content_w
        group["content_h"] = content_h
        group["w"] = content_w + margin_px * 2
        group["h"] = content_h + margin_px * 2
        for face_index in group["face_indices"]:
            face_to_group[face_index] = group
    return islands, groups, face_to_group


def face_uv_bbox(face):
    uvs = face["uvs"]
    u_values = [uv[0] for uv in uvs]
    v_values = [uv[1] for uv in uvs]
    return min(u_values), min(v_values), max(u_values), max(v_values)


def face_group_bbox(faces, face_indices):
    boxes = [face_uv_bbox(faces[index]) for index in face_indices]
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def group_pixel_area_from_bbox(bbox, ref_w, ref_h, margin_px):
    u_min, v_min, u_max, v_max = bbox
    content_w = max(1, int(math.ceil((u_max - u_min) * ref_w)))
    content_h = max(1, int(math.ceil((v_max - v_min) * ref_h)))
    return (content_w + margin_px * 2) * (content_h + margin_px * 2)


def split_face_indices_by_median(faces, face_indices, axis):
    centers = []
    for face_index in face_indices:
        u_min, v_min, u_max, v_max = face_uv_bbox(faces[face_index])
        center = ((u_min + u_max) * 0.5) if axis == 0 else ((v_min + v_max) * 0.5)
        centers.append((center, face_index))
    centers.sort(key=lambda item: item[0])
    mid = len(centers) // 2
    left = [item[1] for item in centers[:mid]]
    right = [item[1] for item in centers[mid:]]
    return left, right


def build_texture_bsp_groups(faces, ref_w, ref_h, margin_px):
    islands = build_uv_islands(faces)
    stack_groups = group_stacked_islands(islands)
    max_groups = 160
    min_faces_to_split = 12
    min_area_saving = 0.18

    pending = [list(group["face_indices"]) for group in stack_groups]
    final = []

    while pending:
        face_indices = pending.pop()
        if len(final) + len(pending) >= max_groups or len(face_indices) < min_faces_to_split:
            final.append(face_indices)
            continue

        bbox = face_group_bbox(faces, face_indices)
        u_min, v_min, u_max, v_max = bbox
        axis = 0 if (u_max - u_min) >= (v_max - v_min) else 1
        left, right = split_face_indices_by_median(faces, face_indices, axis)
        if not left or not right:
            final.append(face_indices)
            continue

        parent_area = group_pixel_area_from_bbox(bbox, ref_w, ref_h, margin_px)
        child_area = (
            group_pixel_area_from_bbox(face_group_bbox(faces, left), ref_w, ref_h, margin_px)
            + group_pixel_area_from_bbox(face_group_bbox(faces, right), ref_w, ref_h, margin_px)
        )
        saving = 1.0 - (child_area / max(1, parent_area))
        if saving >= min_area_saving:
            pending.append(left)
            pending.append(right)
        else:
            final.append(face_indices)

    groups = []
    face_to_group = {}
    for group_index, face_indices in enumerate(final):
        u_min, v_min, u_max, v_max = face_group_bbox(faces, face_indices)
        content_w = max(1, int(math.ceil((u_max - u_min) * ref_w)))
        content_h = max(1, int(math.ceil((v_max - v_min) * ref_h)))
        group = {
            "index": group_index,
            "island_indices": [group_index],
            "face_indices": sorted(face_indices),
            "u_min": u_min,
            "v_min": v_min,
            "u_max": u_max,
            "v_max": v_max,
            "content_w": content_w,
            "content_h": content_h,
            "w": content_w + margin_px * 2,
            "h": content_h + margin_px * 2,
        }
        groups.append(group)
        for face_index in group["face_indices"]:
            face_to_group[face_index] = group

    out_islands = [
        {
            "index": group["index"],
            "face_indices": group["face_indices"],
            "u_min": group["u_min"],
            "v_min": group["v_min"],
            "u_max": group["u_max"],
            "v_max": group["v_max"],
        }
        for group in groups
    ]
    return out_islands, groups, face_to_group


def build_no_texture_dense_groups(faces, ref_w, ref_h, margin_px):
    total_area = sum(max(0.0, float(face.get("surface_area", 0.0))) for face in faces)
    if total_area <= 1.0e-12:
        total_area = float(max(1, len(faces)))

    total_pixels = max(1, int(ref_w) * int(ref_h))
    min_side = 8
    groups = []
    face_to_group = {}
    for face_index, face in enumerate(faces):
        u_min, v_min, u_max, v_max = face_uv_bbox(face)
        uv_w = max(1.0e-6, u_max - u_min)
        uv_h = max(1.0e-6, v_max - v_min)
        aspect = max(0.1, min(10.0, uv_w / uv_h))
        area = max(0.0, float(face.get("surface_area", 0.0)))
        if area <= 1.0e-12:
            area = total_area / max(1, len(faces))
        pixel_budget = max(min_side * min_side, total_pixels * (area / total_area))
        content_w = max(min_side, int(math.ceil(math.sqrt(pixel_budget * aspect))))
        content_h = max(min_side, int(math.ceil(math.sqrt(pixel_budget / aspect))))
        group = {
            "index": len(groups),
            "island_indices": [face_index],
            "face_indices": [face_index],
            "u_min": u_min,
            "v_min": v_min,
            "u_max": u_max,
            "v_max": v_max,
            "content_w": content_w,
            "content_h": content_h,
            "w": content_w + margin_px * 2,
            "h": content_h + margin_px * 2,
            "surface_area": area,
        }
        groups.append(group)
        face_to_group[face_index] = group

    islands = [
        {
            "index": group["index"],
            "face_indices": group["face_indices"],
            "u_min": group["u_min"],
            "v_min": group["v_min"],
            "u_max": group["u_max"],
            "v_max": group["v_max"],
        }
        for group in groups
    ]
    return islands, groups, face_to_group


def build_single_preview_group(faces, ref_w, ref_h, margin_px):
    all_uv = [uv for face in faces for uv in face["uvs"]]
    if not all_uv:
        return [], [], {}
    u_values = [uv[0] for uv in all_uv]
    v_values = [uv[1] for uv in all_uv]
    u_min = min(u_values)
    v_min = min(v_values)
    u_max = max(u_values)
    v_max = max(v_values)
    content_w = max(1, int(math.ceil((u_max - u_min) * ref_w)))
    content_h = max(1, int(math.ceil((v_max - v_min) * ref_h)))
    island = {
        "index": 0,
        "face_indices": list(range(len(faces))),
        "u_min": u_min,
        "v_min": v_min,
        "u_max": u_max,
        "v_max": v_max,
    }
    group = {
        "index": 0,
        "island_indices": [0],
        "face_indices": list(range(len(faces))),
        "u_min": u_min,
        "v_min": v_min,
        "u_max": u_max,
        "v_max": v_max,
        "content_w": content_w,
        "content_h": content_h,
        "w": content_w + margin_px * 2,
        "h": content_h + margin_px * 2,
        "x": 0,
        "y": 0,
    }
    return [island], [group], {face_index: group for face_index in range(len(faces))}


def shelf_pack(groups, width, gap):
    ordered = sorted(groups, key=lambda item: (item["h"], item["w"]), reverse=True)
    x = 0
    y = 0
    row_h = 0
    max_x = 0
    packed = []
    for group in ordered:
        w = int(group["w"])
        h = int(group["h"])
        if x > 0 and x + w > width:
            x = 0
            y += row_h + gap
            row_h = 0
        new_group = dict(group)
        new_group["x"] = x
        new_group["y"] = y
        packed.append(new_group)
        x += w + gap
        row_h = max(row_h, h)
        max_x = max(max_x, x - gap)
    return packed, max_x, y + row_h


def pack_groups(groups, gap, max_size, power_of_two=False):
    if not groups:
        return [], 1, 1
    max_group_w = max(int(g["w"]) for g in groups)
    max_group_h = max(int(g["h"]) for g in groups)
    if max_group_w > max_size or max_group_h > max_size:
        raise RuntimeError(
            f"One UV island group is larger than Max Size: {max_group_w}x{max_group_h}, limit {max_size}. "
            "Check UV range, lower fallback resolution, or increase TexWorks MC Max Size."
        )
    total_area = sum(int(g["w"]) * int(g["h"]) for g in groups)
    ideal = int(math.ceil(math.sqrt(max(1, total_area))))
    candidates = {max_group_w, ideal}
    width = max_group_w
    while width < max_size:
        candidates.add(width)
        width *= 2
    candidates.add(max_size)

    best = None
    for candidate in sorted(c for c in candidates if c <= max_size):
        packed, used_w, used_h = shelf_pack(groups, max(candidate, max_group_w), gap)
        if used_w > max_size or used_h > max_size:
            continue
        out_w = next_power_of_two(used_w) if power_of_two else max(1, used_w)
        out_h = next_power_of_two(used_h) if power_of_two else max(1, used_h)
        score = out_w * out_h
        if best is None or score < best[0]:
            best = (score, packed, out_w, out_h)

    if best is None:
        raise RuntimeError(
            f"Cannot pack UV groups into Max Size {max_size}. "
            "Try lower fallback/reference resolution, lower margins, or check UV range."
        )
    return best[1], best[2], best[3]


def pack_groups_bounded(groups, gap, max_w, max_h, power_of_two=False):
    if not groups:
        return [], 1, 1
    max_w = max(1, int(max_w))
    max_h = max(1, int(max_h))
    max_group_w = max(int(g["w"]) for g in groups)
    max_group_h = max(int(g["h"]) for g in groups)
    if max_group_w > max_w or max_group_h > max_h:
        return None

    total_area = sum(int(g["w"]) * int(g["h"]) for g in groups)
    ideal = int(math.ceil(math.sqrt(max(1, total_area))))
    candidates = {max_group_w, min(max_w, ideal), max_w}
    width = max_group_w
    while width < max_w:
        candidates.add(width)
        width = max(width + 1, int(width * 1.35))

    best = None
    for candidate in sorted(c for c in candidates if max_group_w <= c <= max_w):
        packed, used_w, used_h = shelf_pack(groups, candidate, gap)
        if used_w > max_w or used_h > max_h:
            continue
        out_w = next_power_of_two(used_w) if power_of_two else max(1, used_w)
        out_h = next_power_of_two(used_h) if power_of_two else max(1, used_h)
        if out_w > max_w or out_h > max_h:
            continue
        empty_area = max(0, out_w * out_h - total_area)
        score = out_w * out_h + empty_area * 0.15
        if best is None or score < best[0]:
            best = (score, packed, out_w, out_h)

    if best is None:
        return None
    return best[1], best[2], best[3]
