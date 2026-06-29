bl_info = {
    "name": "RZM Decal Sparse Stencil Baker",
    "author": "OpenAI for Rayvich",
    "version": (0, 3, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > TexWorks > Decal Stencil",
    "description": "Bake selected mesh faces into a packed structured CS decal stencil buffer",
    "category": "TexWorks",
}

import bpy
import json
import math
import os
import re
import struct
import traceback
from collections import defaultdict, deque
from pathlib import Path

from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup


EPSILON = 1.0e-10
INSIDE_EPSILON = 1.0e-7


def _safe_export_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    value = value.strip("._-")
    return value or "rzm_decal_stamp"


def _uv_layer_items(self, context):
    obj = context.active_object if context else None
    if obj and obj.type == "MESH" and obj.data.uv_layers:
        return [(layer.name, layer.name, f"Use UV map '{layer.name}' as target atlas UV") for layer in obj.data.uv_layers]
    return [("__NONE__", "<No UV map>", "Active mesh has no UV map")]


def _target_uv_name(settings, mesh):
    requested = settings.target_uv
    if requested and requested != "__NONE__" and requested in mesh.uv_layers:
        return requested
    if mesh.uv_layers.active:
        return mesh.uv_layers.active.name
    raise RuntimeError("Active mesh has no UV map")




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
        "Target UV map was found, but its per-loop UV data is empty/unreadable. "
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


def _remember_context(context):
    return {
        "active": context.view_layer.objects.active,
        "selected": [obj for obj in context.selected_objects],
        "mode": context.active_object.mode if context.active_object else "OBJECT",
    }


def _set_only_active(context, obj):
    for selected_object in list(context.selected_objects):
        selected_object.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


def _restore_context(context, snapshot):
    try:
        active = context.view_layer.objects.active
        if active and active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    for selected_object in list(context.selected_objects):
        selected_object.select_set(False)
    for selected_object in snapshot["selected"]:
        if selected_object and selected_object.name in bpy.data.objects:
            selected_object.select_set(True)
    if snapshot["active"] and snapshot["active"].name in bpy.data.objects:
        context.view_layer.objects.active = snapshot["active"]
        if snapshot["mode"] != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode=snapshot["mode"])
            except Exception:
                pass


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
    from mathutils import Vector

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


def _build_virtual_decal_uv(context, source_object, selected_faces, mapping_method):
    from mathutils import Vector

    source_mesh = source_object.data
    if source_object.mode == "EDIT":
        source_object.update_from_editmode()

    raw_uv_by_loop = {}
    coords = []
    for face_index in selected_faces:
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


RZM_STAMP_MAGIC = 0x444D5A52
RZM_STAMP_VERSION = 4

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


def _resource_name(export_name):
    return re.sub(r"[^A-Za-z0-9_]+", "_", export_name)


def _make_ini_snippet(export_name, buffer_filename, record_count):
    resource_name = f"Resource_RZM_DecalStamp_{_resource_name(export_name)}"
    dispatch_x = (record_count + 255) // 256
    return f"""[{resource_name}]
type = Buffer
stride = 12
filename = {buffer_filename}

; Add inside the CustomShader block:
cs-t6 = {resource_name}
dispatch = {dispatch_x}, 1, 1
"""


class RZMDECAL_PG_settings(PropertyGroup):
    destination_dir: StringProperty(
        name="Destination",
        description="Folder where .buf, .json and INI snippet will be written",
        subtype="DIR_PATH",
        default="//TexWorks/DecalStencils/",
    )
    export_name: StringProperty(
        name="Export name",
        description="Base filename for generated stencil files",
        default="rzm_decal_stamp",
    )
    target_uv: EnumProperty(
        name="Target UV",
        description="UV map of the atlas that RWTexture2D writes into",
        items=_uv_layer_items,
    )
    atlas_width: IntProperty(
        name="Atlas width",
        min=1,
        max=16384,
        default=2048,
    )
    atlas_height: IntProperty(
        name="Atlas height",
        min=1,
        max=16384,
        default=2048,
    )
    padding_pixels: IntProperty(
        name="Seam padding",
        description="Dilate only into atlas texels unused by any UV face",
        min=0,
        max=32,
        default=4,
    )
    mapping_method: EnumProperty(
        name="Virtual map",
        items=(
            ("BEST_FIT_PLANE", "Best-fit Plane", "Stable non-operator projection from selected faces"),
            ("LOCAL_XY", "Local XY", "Project selected faces using local X/Y"),
            ("LOCAL_XZ", "Local XZ", "Project selected faces using local X/Z"),
            ("LOCAL_YZ", "Local YZ", "Project selected faces using local Y/Z"),
        ),
        default="BEST_FIT_PLANE",
    )
    flip_target_v: BoolProperty(
        name="Flip target V",
        description="Convert Blender bottom-left UV origin into texture-address Y direction",
        default=True,
    )
    flip_decal_v: BoolProperty(
        name="Flip decal V",
        description="Convert temporary Blender UV into DirectX-style decal texture V",
        default=True,
    )


class RZMDECAL_OT_bake_sparse_stencil(Operator):
    bl_idname = "rzm_decal.bake_sparse_stencil"
    bl_label = "Bake Sparse Decal Stencil"
    bl_description = "Bake selected mesh faces into a packed structured CS buffer"
    bl_options = {"REGISTER"}

    def execute(self, context):
        settings = context.scene.rzm_decal_stencil_settings
        source_object = context.active_object
        if source_object is None or source_object.type != "MESH":
            self.report({"ERROR"}, "Select an active mesh object")
            return {"CANCELLED"}

        source_mesh = source_object.data
        if source_object.mode == "EDIT":
            source_object.update_from_editmode()

        selected_faces = [polygon.index for polygon in source_mesh.polygons if polygon.select]
        if not selected_faces:
            self.report({"ERROR"}, "Select at least one mesh face")
            return {"CANCELLED"}

        try:
            uv_name = _target_uv_name(settings, source_mesh)
            read_target_uv, uv_reader_metadata = _make_uv_reader(source_mesh, uv_name)
            export_name = _safe_export_name(settings.export_name)
            destination = Path(bpy.path.abspath(settings.destination_dir)).expanduser().resolve()
            destination.mkdir(parents=True, exist_ok=True)

            diagnostics = _selection_diagnostics(source_mesh, selected_faces)
            virtual_uv_by_loop, unwrap_metadata = _build_virtual_decal_uv(
                context,
                source_object,
                selected_faces,
                settings.mapping_method,
            )

            occupancy, all_degenerate_triangles, clipped_triangles = _build_occupancy(
                source_mesh,
                read_target_uv,
                settings.atlas_width,
                settings.atlas_height,
                settings.flip_target_v,
            )
            core_records, core_metadata = _build_core_records(
                source_mesh,
                read_target_uv,
                virtual_uv_by_loop,
                selected_faces,
                settings.atlas_width,
                settings.atlas_height,
                settings.flip_target_v,
                settings.flip_decal_v,
            )
            if not core_records:
                raise RuntimeError("Selected faces produced zero atlas texels. Check atlas resolution and target UV map")

            padding_records = _add_padding_records(
                core_records,
                occupancy,
                settings.atlas_width,
                settings.atlas_height,
                settings.padding_pixels,
            )
            all_records = dict(core_records)
            all_records.update(padding_records)

            buffer_filename = f"{export_name}.buf"
            json_filename = f"{export_name}.json"
            ini_filename = f"{export_name}_resource.ini"
            buffer_path = destination / buffer_filename
            json_path = destination / json_filename
            ini_path = destination / ini_filename

            _write_buffer(buffer_path, all_records, settings.atlas_width, settings.atlas_height)
            ini_snippet = _make_ini_snippet(export_name, buffer_filename, len(all_records))
            ini_path.write_text(ini_snippet, encoding="utf-8")

            warnings = []
            if diagnostics["connected_components"] > 1:
                warnings.append("Selection has multiple disconnected components. Blender unwrap packs them as separate virtual islands")
            if diagnostics["closed_components"] > 0:
                warnings.append("Selection contains a closed component without a boundary. A rectangular decal cannot flatten it without an implicit cut")
            if clipped_triangles > 0:
                warnings.append("Some target UV triangles leave the 0..1 atlas range and were clipped")
            if core_metadata["conflicting_target_texels"] > 0:
                warnings.append("Target UV overlap detected inside the stencil. First mapping wins for deterministic CS writes")
            if all_degenerate_triangles > 0 or core_metadata["selected_degenerate_triangles"] > 0:
                warnings.append("Degenerate UV triangles detected. They cannot contribute texels")

            metadata = {
                "format_version": 1,
                "algorithm": "selected_faces_virtual_unwrap_to_sparse_atlas_texels",
                "record_layout": ["target_x_float", "target_y_float", "decal_u", "decal_v"],
                "record_stride_bytes": 16,
                "shader_resource_format": "R32G32B32A32_FLOAT",
                "object": source_object.name,
                "target_uv": uv_name,
                "atlas_size": [settings.atlas_width, settings.atlas_height],
                "flip_target_v": settings.flip_target_v,
                "flip_decal_v": settings.flip_decal_v,
                "unwrap_method": settings.mapping_method,
                "selected_face_count": len(selected_faces),
                "core_record_count": len(core_records),
                "padding_record_count": len(padding_records),
                "record_count": len(all_records),
                    "stored_struct_count": len(all_records) + 1,
                "dispatch": [(len(all_records) + 255) // 256, 1, 1],
                "selection_diagnostics": diagnostics,
                "raster_diagnostics": {
                    "all_mesh_degenerate_uv_triangles": all_degenerate_triangles,
                    "target_uv_triangles_clipped_to_atlas": clipped_triangles,
                    **core_metadata,
                },
                "unwrap_metadata": unwrap_metadata,
                "warnings": warnings,
                "files": {
                    "buffer": buffer_filename,
                    "metadata": json_filename,
                    "ini_snippet": ini_filename,
                },
                "ini_snippet": ini_snippet,
            }
            json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

            warning_suffix = f"; warnings: {len(warnings)}" if warnings else ""
            self.report(
                {"INFO"},
                f"Baked {len(all_records)} records ({len(core_records)} core + {len(padding_records)} padding){warning_suffix}",
            )
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class RZMDECAL_PT_sparse_stencil_panel(Panel):
    bl_label = "Decal Sparse Stencil"
    bl_idname = "RZMDECAL_PT_sparse_stencil_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "TexWorks"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rzm_decal_stencil_settings
        obj = context.active_object

        layout.label(text="Selected faces → packed CS stencil buffer")
        if obj and obj.type == "MESH":
            if obj.mode == "EDIT":
                obj.update_from_editmode()
            selected_face_count = sum(1 for polygon in obj.data.polygons if polygon.select)
            layout.label(text=f"Active: {obj.name}")
            layout.label(text=f"Selected faces: {selected_face_count}")
        else:
            layout.label(text="Select a mesh object", icon="ERROR")

        layout.prop(settings, "destination_dir")
        layout.prop(settings, "export_name")
        layout.prop(settings, "target_uv")

        row = layout.row(align=True)
        row.prop(settings, "atlas_width")
        row.prop(settings, "atlas_height")

        layout.prop(settings, "padding_pixels")
        layout.prop(settings, "mapping_method")

        box = layout.box()
        box.label(text="Coordinate conversion")
        box.prop(settings, "flip_target_v")
        box.prop(settings, "flip_decal_v")

        layout.operator("rzm_decal.bake_sparse_stencil", icon="UV")


CLASSES = (
    RZMDECAL_PG_settings,
    RZMDECAL_OT_bake_sparse_stencil,
    RZMDECAL_PT_sparse_stencil_panel,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rzm_decal_stencil_settings = PointerProperty(type=RZMDECAL_PG_settings)


def unregister():
    if hasattr(bpy.types.Scene, "rzm_decal_stencil_settings"):
        del bpy.types.Scene.rzm_decal_stencil_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    try:
        unregister()
    except Exception:
        pass
    register()
