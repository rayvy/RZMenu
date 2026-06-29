import math
import os
import re
import struct
import json
from collections import defaultdict, deque
from mathutils import Vector

EPSILON = 1.0e-10
INSIDE_EPSILON = 1.0e-7
RZM_STAMP_MAGIC = 0x444D5A52
RZM_STAMP_VERSION = 4

def _safe_export_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    value = value.strip("._-")
    return value or "rzm_decal_stamp"

def _extract_uv_value(item):
    if item is None:
        return None
    for attr in ("uv", "vector", "value"):
        if hasattr(item, attr):
            value = getattr(item, attr)
            try:
                if len(value) >= 2:
                    return (float(value[0]), float(value[1]))
            except Exception:
                pass
    try:
        if len(item) >= 2:
            return (float(item[0]), float(item[1]))
    except Exception:
        pass
    return None

def _collection_uv_reader(collection, loop_count):
    if collection is None:
        return None
    try:
        collection_len = len(collection)
    except Exception:
        return None
    if collection_len < loop_count:
        return None

    def read(loop_index):
        try:
            value = _extract_uv_value(collection[loop_index])
        except Exception:
            value = None
        if value is None:
            raise RuntimeError(f"UV data exists but loop {loop_index} could not be read")
        return value

    return read

def _make_uv_reader(mesh, uv_name):
    mesh.update()
    loop_count = len(mesh.loops)
    if loop_count <= 0:
        raise RuntimeError("Mesh has zero loops. Apply/repair mesh before baking")

    candidates = []
    uv_layer = mesh.uv_layers.get(uv_name) if hasattr(mesh.uv_layers, "get") else None
    if uv_layer is None:
        try:
            uv_layer = mesh.uv_layers[uv_name]
        except Exception:
            uv_layer = None

    if uv_layer is not None:
        candidates.append((f"uv_layers['{uv_name}'].data", getattr(uv_layer, "data", None)))
        uv_attr = getattr(uv_layer, "uv", None)
        candidates.append((f"uv_layers['{uv_name}'].uv", uv_attr))
        candidates.append((f"uv_layers['{uv_name}'].uv.data", getattr(uv_attr, "data", None)))

    attributes = getattr(mesh, "attributes", None)
    if attributes is not None:
        attr = attributes.get(uv_name) if hasattr(attributes, "get") else None
        if attr is None:
            try:
                attr = attributes[uv_name]
            except Exception:
                attr = None
        if attr is not None:
            candidates.append((f"attributes['{uv_name}'].data", getattr(attr, "data", None)))

    tried = []
    for label, collection in candidates:
        reader = _collection_uv_reader(collection, loop_count)
        try:
            collection_len = len(collection) if collection is not None else 0
        except Exception:
            collection_len = "?"
        tried.append(f"{label}: {collection_len}")
        if reader is not None:
            return reader, {
                "uv_read_source": label,
                "uv_loop_count": loop_count,
                "uv_collection_size": collection_len,
            }

    raise RuntimeError(
        f"Target UV map '{uv_name}' was found, but its per-loop UV data is empty/unreadable. "
        "Try Object Mode, Mesh > Clean Up, or duplicate/apply the mesh before baking. Tried: "
        + "; ".join(tried)
    )

def _flip_target_uv(uv, flip_v):
    return (float(uv[0]), 1.0 - float(uv[1]) if flip_v else float(uv[1]))

def _triangle_pixel_bounds(uv0, uv1, uv2, width, height):
    xs = (uv0[0] * width - 0.5, uv1[0] * width - 0.5, uv2[0] * width - 0.5)
    ys = (uv0[1] * height - 0.5, uv1[1] * height - 0.5, uv2[1] * height - 0.5)
    min_x = max(0, int(math.ceil(min(xs) - INSIDE_EPSILON)))
    max_x = min(width - 1, int(math.floor(max(xs) + INSIDE_EPSILON)))
    min_y = max(0, int(math.ceil(min(ys) - INSIDE_EPSILON)))
    max_y = min(height - 1, int(math.floor(max(ys) + INSIDE_EPSILON)))
    return min_x, max_x, min_y, max_y

def _barycentric_at_pixel_center(px, py, uv0, uv1, uv2, width, height):
    x = (px + 0.5) / width
    y = (py + 0.5) / height
    x0, y0 = uv0
    x1, y1 = uv1
    x2, y2 = uv2
    denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denominator) <= EPSILON:
        return None
    w0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / denominator
    w1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / denominator
    w2 = 1.0 - w0 - w1
    if w0 < -INSIDE_EPSILON or w1 < -INSIDE_EPSILON or w2 < -INSIDE_EPSILON:
        return None
    return w0, w1, w2

def _rasterize_triangle(uv0, uv1, uv2, width, height):
    min_x, max_x, min_y, max_y = _triangle_pixel_bounds(uv0, uv1, uv2, width, height)
    if min_x > max_x or min_y > max_y:
        return
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            barycentric = _barycentric_at_pixel_center(px, py, uv0, uv1, uv2, width, height)
            if barycentric is not None:
                yield px, py, barycentric

def _selection_diagnostics(mesh, selected_faces):
    edge_to_faces = defaultdict(list)
    for polygon_index in selected_faces:
        if polygon_index < 0 or polygon_index >= len(mesh.polygons):
            continue
        polygon = mesh.polygons[polygon_index]
        for edge_key in polygon.edge_keys:
            edge_to_faces[tuple(sorted(edge_key))].append(polygon_index)

    adjacency = defaultdict(set)
    for face_indices in edge_to_faces.values():
        if len(face_indices) < 2:
            continue
        for face_index in face_indices:
            adjacency[face_index].update(other for other in face_indices if other != face_index)

    remaining = set(selected_faces)
    components = []
    while remaining:
        root = remaining.pop()
        stack = [root]
        component = {root}
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)

    closed_components = 0
    for component in components:
        boundary_edges = 0
        component_set = set(component)
        for face_index in component:
            for edge_key in mesh.polygons[face_index].edge_keys:
                selected_owners = edge_to_faces[tuple(sorted(edge_key))]
                if sum(1 for owner in selected_owners if owner in component_set) == 1:
                    boundary_edges += 1
        if boundary_edges == 0:
            closed_components += 1

    return {
        "connected_components": len(components),
        "closed_components": closed_components,
    }

def _normalize_virtual_uv(raw_uv_by_loop):
    if not raw_uv_by_loop:
        raise RuntimeError("Virtual UV map is empty")

    u_values = [uv[0] for uv in raw_uv_by_loop.values()]
    v_values = [uv[1] for uv in raw_uv_by_loop.values()]
    min_u, max_u = min(u_values), max(u_values)
    min_v, max_v = min(v_values), max(v_values)
    span_u = max_u - min_u
    span_v = max_v - min_v

    if span_u <= EPSILON or span_v <= EPSILON:
        raise RuntimeError("Selected mesh patch collapsed into a line or point in virtual decal mapping")

    return {
        loop_index: ((uv[0] - min_u) / span_u, (uv[1] - min_v) / span_v)
        for loop_index, uv in raw_uv_by_loop.items()
    }, {
        "virtual_uv_bounds_before_normalization": [min_u, min_v, max_u, max_v],
    }

def _safe_normalized(vector, fallback):
    if vector.length <= EPSILON:
        return fallback.copy()
    return vector.normalized()

def _choose_projected_axis(normal, coords):
    if not coords:
        return Vector((1.0, 0.0, 0.0))

    min_x = min(v.x for v in coords)
    max_x = max(v.x for v in coords)
    min_y = min(v.y for v in coords)
    max_y = max(v.y for v in coords)
    min_z = min(v.z for v in coords)
    max_z = max(v.z for v in coords)

    candidates = [
        (max_x - min_x, Vector((1.0, 0.0, 0.0))),
        (max_y - min_y, Vector((0.0, 1.0, 0.0))),
        (max_z - min_z, Vector((0.0, 0.0, 1.0))),
    ]
    candidates.sort(key=lambda item: item[0], reverse=True)

    for _, axis in candidates:
        projected = axis - normal * axis.dot(normal)
        if projected.length > EPSILON:
            return projected.normalized()

    if abs(normal.z) < 0.9:
        fallback = Vector((0.0, 0.0, 1.0))
    else:
        fallback = Vector((0.0, 1.0, 0.0))
    return (fallback - normal * fallback.dot(normal)).normalized()

def _build_virtual_decal_uv(source_mesh, selected_faces, mapping_method):
    raw_uv_by_loop = {}
    coords = []
    for face_index in selected_faces:
        if face_index < 0 or face_index >= len(source_mesh.polygons):
            continue
        polygon = source_mesh.polygons[face_index]
        for loop_index in polygon.loop_indices:
            coord = source_mesh.vertices[source_mesh.loops[loop_index].vertex_index].co.copy()
            coords.append(coord)

    if not coords:
        raise RuntimeError("Selected mesh patch has no vertices")

    center = sum(coords, Vector((0.0, 0.0, 0.0))) / len(coords)

    if mapping_method == "LOCAL_XY":
        axis_u = Vector((1.0, 0.0, 0.0))
        axis_v = Vector((0.0, 1.0, 0.0))
        normal = Vector((0.0, 0.0, 1.0))
    elif mapping_method == "LOCAL_XZ":
        axis_u = Vector((1.0, 0.0, 0.0))
        axis_v = Vector((0.0, 0.0, 1.0))
        normal = Vector((0.0, -1.0, 0.0))
    elif mapping_method == "LOCAL_YZ":
        axis_u = Vector((0.0, 1.0, 0.0))
        axis_v = Vector((0.0, 0.0, 1.0))
        normal = Vector((1.0, 0.0, 0.0))
    else:
        normal = Vector((0.0, 0.0, 0.0))
        for face_index in selected_faces:
            polygon = source_mesh.polygons[face_index]
            normal += polygon.normal * max(polygon.area, EPSILON)
        normal = _safe_normalized(normal, Vector((0.0, 0.0, 1.0)))
        axis_u = _choose_projected_axis(normal, coords)
        axis_v = normal.cross(axis_u)
        if axis_v.length <= EPSILON:
            axis_v = Vector((0.0, 1.0, 0.0))
        else:
            axis_v.normalize()

    for face_index in selected_faces:
        polygon = source_mesh.polygons[face_index]
        for loop_index in polygon.loop_indices:
            coord = source_mesh.vertices[source_mesh.loops[loop_index].vertex_index].co
            rel = coord - center
            raw_uv_by_loop[loop_index] = (rel.dot(axis_u), rel.dot(axis_v))

    normalized, metadata = _normalize_virtual_uv(raw_uv_by_loop)
    metadata.update({
        "virtual_mapping": mapping_method,
        "projection_center_local": [center.x, center.y, center.z],
        "projection_axis_u_local": [axis_u.x, axis_u.y, axis_u.z],
        "projection_axis_v_local": [axis_v.x, axis_v.y, axis_v.z],
        "projection_normal_local": [normal.x, normal.y, normal.z],
        "operator_uv_unwrap_used": False,
    })
    return normalized, metadata

def _build_occupancy(mesh, read_target_uv, width, height, flip_target_v):
    occupancy = bytearray(width * height)
    degenerate_triangles = 0
    clipped_triangles = 0

    mesh.calc_loop_triangles()
    for triangle in mesh.loop_triangles:
        target_uvs = [_flip_target_uv(read_target_uv(loop_index), flip_target_v) for loop_index in triangle.loops]
        if any(uv[0] < 0.0 or uv[0] > 1.0 or uv[1] < 0.0 or uv[1] > 1.0 for uv in target_uvs):
            clipped_triangles += 1
        yielded = False
        for px, py, _ in _rasterize_triangle(target_uvs[0], target_uvs[1], target_uvs[2], width, height):
            yielded = True
            occupancy[py * width + px] = 1
        if not yielded:
            area = abs(
                (target_uvs[1][0] - target_uvs[0][0]) * (target_uvs[2][1] - target_uvs[0][1])
                - (target_uvs[2][0] - target_uvs[0][0]) * (target_uvs[1][1] - target_uvs[0][1])
            )
            if area <= EPSILON:
                degenerate_triangles += 1

    return occupancy, degenerate_triangles, clipped_triangles

def _build_core_records(mesh, read_target_uv, virtual_uv_by_loop, selected_faces, width, height, flip_target_v, flip_decal_v):
    selected_set = set(selected_faces)
    core_records = {}
    duplicate_same_mapping = 0
    conflicting_target_texels = 0
    selected_degenerate_triangles = 0

    mesh.calc_loop_triangles()
    for triangle in mesh.loop_triangles:
        if triangle.polygon_index not in selected_set:
            continue
        if any(loop_index not in virtual_uv_by_loop for loop_index in triangle.loops):
            raise RuntimeError(f"Missing virtual UV for polygon {triangle.polygon_index}")

        target_uvs = [_flip_target_uv(read_target_uv(loop_index), flip_target_v) for loop_index in triangle.loops]
        decal_uvs = [virtual_uv_by_loop[loop_index] for loop_index in triangle.loops]

        yielded = False
        for px, py, weights in _rasterize_triangle(target_uvs[0], target_uvs[1], target_uvs[2], width, height):
            yielded = True
            w0, w1, w2 = weights
            decal_u = decal_uvs[0][0] * w0 + decal_uvs[1][0] * w1 + decal_uvs[2][0] * w2
            decal_v = decal_uvs[0][1] * w0 + decal_uvs[1][1] * w1 + decal_uvs[2][1] * w2
            decal_u = min(1.0, max(0.0, decal_u))
            decal_v = min(1.0, max(0.0, decal_v))
            if flip_decal_v:
                decal_v = 1.0 - decal_v

            index = py * width + px
            previous = core_records.get(index)
            if previous is None:
                core_records[index] = (decal_u, decal_v)
            else:
                if abs(previous[0] - decal_u) <= 1.0e-5 and abs(previous[1] - decal_v) <= 1.0e-5:
                    duplicate_same_mapping += 1
                else:
                    conflicting_target_texels += 1

        if not yielded:
            area = abs(
                (target_uvs[1][0] - target_uvs[0][0]) * (target_uvs[2][1] - target_uvs[0][1])
                - (target_uvs[2][0] - target_uvs[0][0]) * (target_uvs[1][1] - target_uvs[0][1])
            )
            if area <= EPSILON:
                selected_degenerate_triangles += 1

    return core_records, {
        "duplicate_same_mapping_texels": duplicate_same_mapping,
        "conflicting_target_texels": conflicting_target_texels,
        "selected_degenerate_triangles": selected_degenerate_triangles,
    }

def _add_padding_records(core_records, occupancy, width, height, padding_pixels):
    if padding_pixels <= 0 or not core_records:
        return {}

    padding_records = {}
    queue = deque((index, uv[0], uv[1], 0) for index, uv in core_records.items())
    visited = set(core_records.keys())
    directions = (
        (-1, -1), (0, -1), (1, -1),
        (-1, 0),           (1, 0),
        (-1, 1),  (0, 1),  (1, 1),
    )

    while queue:
        index, decal_u, decal_v, distance = queue.popleft()
        if distance >= padding_pixels:
            continue
        x = index % width
        y = index // width
        next_distance = distance + 1

        for dx, dy in directions:
            nx = x + dx
            ny = y + dy
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            neighbor_index = ny * width + nx
            if neighbor_index in visited:
                continue
            visited.add(neighbor_index)
            if occupancy[neighbor_index]:
                continue
            padding_records[neighbor_index] = (decal_u, decal_v)
            queue.append((neighbor_index, decal_u, decal_v, next_distance))

    return padding_records

def _clamp01(value):
    return max(0.0, min(1.0, float(value)))

def _pack_u16_pair(a, b):
    return (int(a) & 0xFFFF) | ((int(b) & 0xFFFF) << 16)

def _pack_unorm16_pair(a, b):
    au = int(round(_clamp01(a) * 65535.0))
    bu = int(round(_clamp01(b) * 65535.0))
    return _pack_u16_pair(au, bu)

def _write_buffer(buffer_path, records, width, height, flags=0):
    with open(buffer_path, "wb") as handle:
        handle.write(struct.pack("<3I", RZM_STAMP_MAGIC, (RZM_STAMP_VERSION & 0xFFFF) | ((int(flags) & 0xFFFF) << 16), _pack_u16_pair(width, height)))
        for index in sorted(records):
            x = index % width
            y = index // width
            decal_u, decal_v = records[index]
            target_xy = _pack_u16_pair(x, y)
            decal_uv = _pack_unorm16_pair(decal_u, decal_v)
            weight_flags = _pack_u16_pair(65535, 0)
            handle.write(struct.pack("<3I", target_xy, decal_uv, weight_flags))
