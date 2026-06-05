import bpy
import importlib.util
import json
import math
import os
import re
import traceback
from array import array


GROUP_NAME = "RZM TexWorks Material"
EMPTY_MAT_NAME = "RZM AutoAtlas Material"

SCHEMA = 2
KIND = "RZ_AUTO_ATLAS"
ROLE = "SEMANTIC_TEXTURE_HUB"

TEXTURE_INPUTS = ["Diffuse", "LightMap", "MaterialMap", "NormalMap", "Extra"]
AUTO_ATLAS_UV_NAME = "RZAutoAtlas.UV"
AUTO_ATLAS_RESOURCE_PREFIX = "RZAutoAtlas"
AUTO_ATLAS_OUTPUT_SUBDIR = os.path.join("Textures", "DynAtlas")
AUTO_ATLAS_DEFAULT_PADDING = 8
AUTO_ATLAS_VERTEX_MARGIN_DEFAULT = 4
AUTO_ATLAS_MAX_SIZE = 8192
AUTO_ATLAS_TRANSPARENT = (0.0, 0.0, 0.0, 0.0)

SLOT_DEFAULTS = {
    "Diffuse": (1.0, 1.0, 1.0, 1.0),
    "LightMap": (0.0, 0.0, 0.0, 1.0),
    "MaterialMap": (0.0, 0.5, 0.0, 1.0),
    "NormalMap": (0.5, 0.5, 1.0, 1.0),
    "Extra": (0.0, 0.0, 0.0, 1.0),
}

SOURCE_NAMES = [
    "Diffuse.R", "Diffuse.G", "Diffuse.B", "Diffuse.A",
    "LightMap.R", "LightMap.G", "LightMap.B", "LightMap.A",
    "MaterialMap.R", "MaterialMap.G", "MaterialMap.B", "MaterialMap.A",
    "Extra.R", "Extra.G", "Extra.B", "Extra.A",
    "NormalMap.R", "NormalMap.G", "NormalMap.B",
]

COLORSPACE_NAMES = {
    0: "sRGB",
    1: "Linear",
}

NORMAL_PRESET_NAMES = {
    0: "DX_FULL",
    1: "DX_RG",
    2: "ZZZ",
}

RUNTIME_NAMESPACE_KEY = "rzm_qa_texworks_atlas_runtime"
DEFAULT_BAKE_ACTION_ID = "bake_prototype"
REBUILD_TEXTURES_ACTION_ID = "rebuild_textures"
CALCULATE_ATLAS_ACTION_ID = "calculate_atlas_size"
EXPORT_ATLAS_ACTION_ID = "export_atlas"
DEFAULT_BAKE_SCRIPT = "BakePrototype.py"
DEFAULT_BAKE_FUNCTION = "run"


def runtime_registry():
    return bpy.app.driver_namespace.setdefault(RUNTIME_NAMESPACE_KEY, {})


def register_runtime_action(action_id, callback):
    if not callable(callback):
        raise TypeError(f"Runtime action '{action_id}' is not callable")
    runtime_registry()[action_id] = callback
    return callback


def unregister_runtime_action(action_id):
    runtime_registry().pop(action_id, None)


def get_runtime_action(action_id):
    return runtime_registry().get(action_id)


def qa_dir():
    candidates = []

    try:
        candidates.append(
            bpy.utils.user_resource(
                "SCRIPTS",
                path=os.path.join("addons", "RZMenu", "QA", "TexWorksRework"),
                create=False,
            )
        )
    except Exception:
        pass

    try:
        file_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(file_dir)
    except Exception:
        pass

    try:
        cwd = os.getcwd()
        candidates.extend(
            [
                os.path.join(cwd, "QA", "TexWorksRework"),
                os.path.join(cwd, "RZMenu", "QA", "TexWorksRework"),
            ]
        )
    except Exception:
        pass

    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate

    return candidates[0] if candidates else os.path.join("QA", "TexWorksRework")


def load_callback_from_script(script_path, function_name=DEFAULT_BAKE_FUNCTION):
    if not os.path.exists(script_path):
        raise FileNotFoundError(script_path)

    module_name = f"rzm_qa_runtime_{os.path.splitext(os.path.basename(script_path))[0]}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load module spec for {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    callback = getattr(module, function_name, None)
    if not callable(callback):
        raise AttributeError(f"{script_path} has no callable {function_name}(context, operator=None)")

    return callback


def run_runtime_action(action_id, context, operator=None):
    callback = get_runtime_action(action_id)
    if not callback:
        raise KeyError(f"Runtime action '{action_id}' is not registered")

    try:
        return callback(context, operator=operator)
    except TypeError:
        return callback(context)


def safe_unregister_class(cls):
    old = getattr(bpy.types, cls.__name__, None)
    if old:
        try:
            bpy.utils.unregister_class(old)
        except Exception:
            pass


def clear_group(group):
    group.nodes.clear()
    try:
        group.interface.clear()
    except Exception:
        for item in reversed(list(group.interface.items_tree)):
            try:
                group.interface.remove(item)
            except Exception:
                pass


def add_socket(group, name, in_out, socket_type, default=None):
    sock = group.interface.new_socket(
        name=name,
        in_out=in_out,
        socket_type=socket_type,
    )
    if default is not None:
        try:
            sock.default_value = default
        except Exception:
            pass
    return sock


def make_or_update_group(force=False):
    group = bpy.data.node_groups.get(GROUP_NAME)

    if group is None:
        group = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")
        force = True

    needs_rebuild = (
        force
        or group.get("rzm_texworks_schema") != SCHEMA
        or group.get("rzm_texworks_kind") != KIND
        or group.get("rzm_texworks_role") != ROLE
    )

    if needs_rebuild:
        clear_group(group)

        for name in TEXTURE_INPUTS:
            add_socket(group, name, "INPUT", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0))

        add_socket(group, "Has LightMap", "INPUT", "NodeSocketBool", False)
        add_socket(group, "Has MaterialMap", "INPUT", "NodeSocketBool", False)
        add_socket(group, "Has NormalMap", "INPUT", "NodeSocketBool", False)
        add_socket(group, "Has Extra", "INPUT", "NodeSocketBool", False)

        add_socket(group, "Preview Emit Source", "INPUT", "NodeSocketInt", 3)
        add_socket(group, "Preview Metallic Source", "INPUT", "NodeSocketInt", 8)
        add_socket(group, "Preview Roughness Source", "INPUT", "NodeSocketInt", 9)
        add_socket(group, "Preview AO Source", "INPUT", "NodeSocketInt", 4)
        add_socket(group, "Preview Alpha Source", "INPUT", "NodeSocketInt", 3)

        add_socket(group, "NormalMap Preset", "INPUT", "NodeSocketInt", 0)

        add_socket(group, "Diffuse Color Space", "INPUT", "NodeSocketInt", 0)
        add_socket(group, "LightMap Color Space", "INPUT", "NodeSocketInt", 1)
        add_socket(group, "MaterialMap Color Space", "INPUT", "NodeSocketInt", 1)
        add_socket(group, "NormalMap Color Space", "INPUT", "NodeSocketInt", 1)
        add_socket(group, "Extra Color Space", "INPUT", "NodeSocketInt", 1)

        add_socket(group, "Base Color", "OUTPUT", "NodeSocketColor")
        add_socket(group, "Diffuse", "OUTPUT", "NodeSocketColor")
        add_socket(group, "LightMap", "OUTPUT", "NodeSocketColor")
        add_socket(group, "MaterialMap", "OUTPUT", "NodeSocketColor")
        add_socket(group, "NormalMap", "OUTPUT", "NodeSocketColor")
        add_socket(group, "Extra", "OUTPUT", "NodeSocketColor")

        add_socket(group, "Emission Strength", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Metallic", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Roughness", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Ambient Occlusion", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Alpha", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Preview Normal", "OUTPUT", "NodeSocketColor")
        add_socket(group, "RenderOutput", "OUTPUT", "NodeSocketShader")

        build_nodes(group)

    group["rzm_texworks_schema"] = SCHEMA
    group["rzm_texworks_kind"] = KIND
    group["rzm_texworks_role"] = ROLE

    return group


def build_nodes(group):
    nodes = group.nodes
    links = group.links

    gi = nodes.new("NodeGroupInput")
    gi.location = (-1100, 0)

    go = nodes.new("NodeGroupOutput")
    go.location = (900, 0)

    sep_light = nodes.new("ShaderNodeSeparateColor")
    sep_light.mode = "RGB"
    sep_light.location = (-760, 40)

    sep_mat = nodes.new("ShaderNodeSeparateColor")
    sep_mat.mode = "RGB"
    sep_mat.location = (-760, -220)

    normal_node = nodes.new("ShaderNodeNormalMap")
    normal_node.location = (120, -300)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (400, 100)

    mix_ao = nodes.new("ShaderNodeMix")
    mix_ao.data_type = "RGBA"
    mix_ao.blend_type = "MULTIPLY"
    mix_ao.location = (-160, 220)

    value_emit = nodes.new("ShaderNodeValue")
    value_emit.label = "Default Emit"
    value_emit.outputs[0].default_value = 0.0
    value_emit.location = (-300, -560)

    value_alpha = nodes.new("ShaderNodeValue")
    value_alpha.label = "Default Alpha"
    value_alpha.outputs[0].default_value = 1.0
    value_alpha.location = (-300, -640)

    links.new(gi.outputs["LightMap"], sep_light.inputs["Color"])
    links.new(gi.outputs["MaterialMap"], sep_mat.inputs["Color"])

    links.new(gi.outputs["Diffuse"], go.inputs["Base Color"])
    links.new(gi.outputs["Diffuse"], go.inputs["Diffuse"])
    links.new(gi.outputs["LightMap"], go.inputs["LightMap"])
    links.new(gi.outputs["MaterialMap"], go.inputs["MaterialMap"])
    links.new(gi.outputs["NormalMap"], go.inputs["NormalMap"])
    links.new(gi.outputs["Extra"], go.inputs["Extra"])

    links.new(sep_mat.outputs["Red"], go.inputs["Metallic"])
    links.new(sep_mat.outputs["Green"], go.inputs["Roughness"])
    links.new(sep_light.outputs["Red"], go.inputs["Ambient Occlusion"])

    links.new(value_emit.outputs[0], go.inputs["Emission Strength"])
    links.new(value_alpha.outputs[0], go.inputs["Alpha"])

    links.new(gi.outputs["NormalMap"], normal_node.inputs["Color"])
    links.new(gi.outputs["NormalMap"], go.inputs["Preview Normal"])

    links.new(gi.outputs["Diffuse"], mix_ao.inputs[6])
    links.new(gi.outputs["LightMap"], mix_ao.inputs[7])

    links.new(mix_ao.outputs[2], bsdf.inputs["Base Color"])
    links.new(sep_mat.outputs["Red"], bsdf.inputs["Metallic"])
    links.new(sep_mat.outputs["Green"], bsdf.inputs["Roughness"])
    links.new(value_alpha.outputs[0], bsdf.inputs["Alpha"])
    links.new(normal_node.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], go.inputs["RenderOutput"])


def get_context_material():
    space = bpy.context.space_data

    if space and space.type == "NODE_EDITOR":
        tree = space.edit_tree
        if tree:
            for mat in bpy.data.materials:
                if mat.node_tree == tree:
                    return mat

    obj = bpy.context.object
    if obj:
        return obj.active_material

    return None


def add_group_instance(mat, group):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes

    node = nodes.new("ShaderNodeGroup")
    node.node_tree = group
    node.name = GROUP_NAME
    node.label = GROUP_NAME

    if nodes:
        node.location.x = max(n.location.x for n in nodes) + 300
        node.location.y = 100

    return node


def create_empty_material(assign=True):
    group = make_or_update_group()

    mat = bpy.data.materials.new(EMPTY_MAT_NAME)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    hub = add_group_instance(mat, group)
    hub.location = (-320, 80)

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (260, 80)

    links.new(hub.outputs["RenderOutput"], out.inputs["Surface"])

    if assign and bpy.context.object:
        obj = bpy.context.object
        obj.data.materials.append(mat)
        obj.active_material_index = len(obj.data.materials) - 1

    return mat


def find_group_instances(group):
    result = []

    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue

        for node in mat.node_tree.nodes:
            if node.bl_idname == "ShaderNodeGroup" and node.node_tree == group:
                result.append((mat, node))

    return result


def material_objects(mat):
    objects = []

    for obj in bpy.data.objects:
        data = getattr(obj, "data", None)
        mats = getattr(data, "materials", None)
        if not mats:
            continue

        for slot_mat in mats:
            if slot_mat == mat:
                objects.append(obj.name)
                break

    return objects


def socket_value(node, name, fallback=None):
    if not node or name not in node.inputs:
        return fallback

    try:
        return node.inputs[name].default_value
    except Exception:
        return fallback


def source_name(index):
    try:
        index = int(index)
    except Exception:
        return f"Invalid({index})"

    if 0 <= index < len(SOURCE_NAMES):
        return SOURCE_NAMES[index]

    return f"Invalid({index})"


def colorspace_name(value):
    try:
        return COLORSPACE_NAMES.get(int(value), f"Unknown({value})")
    except Exception:
        return f"Invalid({value})"


def normal_preset_name(value):
    try:
        return NORMAL_PRESET_NAMES.get(int(value), f"Unknown({value})")
    except Exception:
        return f"Invalid({value})"


def find_image_from_socket(sock):
    if not sock or not sock.is_linked:
        return None

    link = sock.links[0]
    node = link.from_node

    if node.bl_idname == "ShaderNodeTexImage":
        return node.image

    return None


def image_info(image):
    if not image:
        return "None"

    width = image.size[0] if image.size else 0
    height = image.size[1] if image.size else 0
    colorspace = image.colorspace_settings.name if image.colorspace_settings else "Unknown"
    fmt = image.file_format if image.file_format else "Unknown"

    return f"{image.name} | {width}x{height} | {fmt} | {colorspace}"


def clean_name(value):
    value = str(value or "Item")
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return value or "Item"


def autoatlas_material_key(collection):
    return clean_name(collection.get("active_material") or "Material")


def autoatlas_resource_name(collection, slot_name):
    return f"{AUTO_ATLAS_RESOURCE_PREFIX}.{autoatlas_material_key(collection)}.{slot_name}"


def autoatlas_filename(collection, slot_name):
    return f"{autoatlas_resource_name(collection, slot_name)}.png"


def clamp01(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def next_power_of_two(value):
    value = max(1, int(value))
    return 1 << (value - 1).bit_length()


def report_to_operator(operator, level, message):
    print(message)
    if operator:
        try:
            operator.report({level}, message)
        except Exception:
            pass


def get_vertex_margin_px(context):
    return max(0, int(getattr(context.window_manager, "rzm_qa_autoatlas_vertex_margin_px", AUTO_ATLAS_VERTEX_MARGIN_DEFAULT)))


def get_pack_gap_px(context):
    return max(0, int(getattr(context.window_manager, "rzm_qa_autoatlas_pack_gap_px", AUTO_ATLAS_DEFAULT_PADDING)))


def resolve_mod_output_dir(context):
    try:
        from RZMenu.operators.export_manager import get_target_path
        target = get_target_path(context)
        if target:
            return bpy.path.abspath(target)
    except Exception:
        pass

    return os.path.join(qa_dir(), "out")


def resolve_dynatlas_dir(context):
    return os.path.join(resolve_mod_output_dir(context), AUTO_ATLAS_OUTPUT_SUBDIR)


def get_candidate_objects(context):
    selected = [o for o in context.selected_objects if o.type == "MESH" and o.data]
    if selected:
        return selected

    marked = [
        o for o in context.scene.objects
        if o.type == "MESH" and o.data and bool(o.get("RZM.TexWorksAtlasExport", False))
    ]
    if marked:
        return marked

    active = context.object
    if active and active.type == "MESH" and active.data:
        return [active]

    return []


def objects_using_material(mat):
    result = []
    if not mat:
        return result

    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.data:
            continue

        for slot in obj.material_slots:
            if slot.material == mat:
                result.append(obj)
                break

    return result


def get_rebuild_material(context):
    mat = get_context_material()
    if mat:
        return mat

    obj = context.object
    if obj and obj.active_material:
        return obj.active_material

    return None


def find_rzm_node_in_material(mat):
    group = bpy.data.node_groups.get(GROUP_NAME)
    if not group or not mat or not mat.use_nodes or not mat.node_tree:
        return None

    for node in mat.node_tree.nodes:
        if node.bl_idname == "ShaderNodeGroup" and node.node_tree == group:
            return node
    return None


def direct_image_link_info(node, slot_name):
    sock = node.inputs.get(slot_name) if node else None
    if not sock or not sock.is_linked:
        return None, "EMPTY", None

    link = sock.links[0]
    source_node = link.from_node
    if source_node.bl_idname != "ShaderNodeTexImage":
        return None, "UNSUPPORTED_LINK", source_node.bl_idname

    return source_node.image, "IMAGE", source_node.name


def image_size_or_fallback(image):
    try:
        w, h = int(image.size[0]), int(image.size[1])
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return 3, 3


def material_slot_indices(obj, mat):
    return [
        index for index, slot in enumerate(obj.material_slots)
        if slot.material == mat
    ]


def uv_bounds_for_material_objects(objects, mat):
    u_min = 1.0e30
    v_min = 1.0e30
    u_max = -1.0e30
    v_max = -1.0e30
    loop_count = 0
    poly_count = 0

    for obj in objects:
        mesh = obj.data
        if not mesh or not mesh.uv_layers:
            continue

        indices = set(material_slot_indices(obj, mat))
        if not indices:
            continue

        uv_layer = mesh.uv_layers[0]
        for poly in mesh.polygons:
            if poly.material_index not in indices:
                continue

            poly_count += 1
            for loop_index in poly.loop_indices:
                uv = uv_layer.data[loop_index].uv
                u_min = min(u_min, float(uv.x))
                v_min = min(v_min, float(uv.y))
                u_max = max(u_max, float(uv.x))
                v_max = max(v_max, float(uv.y))
                loop_count += 1

    if loop_count == 0:
        return None

    return {
        "u_min": u_min,
        "v_min": v_min,
        "u_max": u_max,
        "v_max": v_max,
        "loop_count": loop_count,
        "poly_count": poly_count,
    }


def crop_rect_from_uv_bounds(image, uv_bounds, margin=AUTO_ATLAS_DEFAULT_PADDING):
    if not image or not uv_bounds:
        return {"x": 0, "y": 0, "w": 3, "h": 3}

    width, height = image_size_or_fallback(image)
    u0 = max(0.0, min(1.0, uv_bounds["u_min"]))
    v0 = max(0.0, min(1.0, uv_bounds["v_min"]))
    u1 = max(0.0, min(1.0, uv_bounds["u_max"]))
    v1 = max(0.0, min(1.0, uv_bounds["v_max"]))

    if u1 < u0:
        u0, u1 = u1, u0
    if v1 < v0:
        v0, v1 = v1, v0

    x0 = max(0, int(math.floor(u0 * width)) - margin)
    y0 = max(0, int(math.floor(v0 * height)) - margin)
    x1 = min(width, int(math.ceil(u1 * width)) + margin)
    y1 = min(height, int(math.ceil(v1 * height)) + margin)

    return {
        "x": x0,
        "y": y0,
        "w": max(1, x1 - x0),
        "h": max(1, y1 - y0),
    }


def useful_area_percent(image, crop_rect):
    if not image or not crop_rect:
        return 0.0
    width, height = image_size_or_fallback(image)
    total = max(1, width * height)
    useful = max(1, int(crop_rect["w"]) * int(crop_rect["h"]))
    return useful * 100.0 / total


def uv_key(uv, precision=6):
    return (round(float(uv[0]), precision), round(float(uv[1]), precision))


def build_material_faces(objects, mat):
    faces = []

    for obj in objects:
        mesh = obj.data
        if not mesh or not mesh.uv_layers:
            continue

        slot_indices = set(material_slot_indices(obj, mat))
        if not slot_indices:
            continue

        uv_layer = mesh.uv_layers[0]
        for poly in mesh.polygons:
            if poly.material_index not in slot_indices or len(poly.loop_indices) < 3:
                continue

            uvs = []
            for loop_index in poly.loop_indices:
                uv = uv_layer.data[loop_index].uv
                uvs.append((float(uv.x), float(uv.y)))

            faces.append({
                "obj": obj,
                "obj_name": obj.name,
                "poly_index": poly.index,
                "material_index": poly.material_index,
                "loop_indices": list(poly.loop_indices),
                "uvs": uvs,
            })

    return faces


def build_uv_islands(faces):
    if not faces:
        return []

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

    edge_map = {}
    for face_index, face in enumerate(faces):
        uvs = face["uvs"]
        count = len(uvs)
        for i in range(count):
            a = uv_key(uvs[i])
            b = uv_key(uvs[(i + 1) % count])
            key = tuple(sorted((a, b)))
            other = edge_map.get(key)
            if other is None:
                edge_map[key] = face_index
            else:
                union(face_index, other)

    grouped = {}
    for face_index, face in enumerate(faces):
        root = find(face_index)
        grouped.setdefault(root, []).append(face_index)

    islands = []
    for island_index, face_indices in enumerate(grouped.values()):
        u_min = 1.0e30
        v_min = 1.0e30
        u_max = -1.0e30
        v_max = -1.0e30
        for face_index in face_indices:
            for u, v in faces[face_index]["uvs"]:
                u_min = min(u_min, u)
                v_min = min(v_min, v)
                u_max = max(u_max, u)
                v_max = max(v_max, v)
        islands.append({
            "index": island_index,
            "face_indices": face_indices,
            "u_min": u_min,
            "v_min": v_min,
            "u_max": u_max,
            "v_max": v_max,
        })

    return islands


def bbox_overlap_ratio(a, b):
    ax0, ay0, ax1, ay1 = a["u_min"], a["v_min"], a["u_max"], a["v_max"]
    bx0, by0, bx1, by1 = b["u_min"], b["v_min"], b["u_max"], b["v_max"]
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max(1.0e-12, (ax1 - ax0) * (ay1 - ay0))
    area_b = max(1.0e-12, (bx1 - bx0) * (by1 - by0))
    return inter / min(area_a, area_b)


def group_stacked_islands(islands, overlap_threshold=0.90):
    if not islands:
        return []

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
            if bbox_overlap_ratio(islands[i], islands[j]) >= overlap_threshold:
                union(i, j)

    grouped = {}
    for island_index, island in enumerate(islands):
        grouped.setdefault(find(island_index), []).append(island)

    groups = []
    for group_index, group_islands in enumerate(grouped.values()):
        u_min = min(i["u_min"] for i in group_islands)
        v_min = min(i["v_min"] for i in group_islands)
        u_max = max(i["u_max"] for i in group_islands)
        v_max = max(i["v_max"] for i in group_islands)
        face_indices = []
        island_indices = []
        for island in group_islands:
            face_indices.extend(island["face_indices"])
            island_indices.append(island["index"])

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


def build_repack_groups(faces, ref_w, ref_h, vertex_margin=AUTO_ATLAS_VERTEX_MARGIN_DEFAULT):
    islands = build_uv_islands(faces)
    groups = group_stacked_islands(islands)

    face_to_group = {}
    for group in groups:
        raw_w = max(1.0, (group["u_max"] - group["u_min"]) * ref_w)
        raw_h = max(1.0, (group["v_max"] - group["v_min"]) * ref_h)
        group["content_w"] = max(1, int(math.ceil(raw_w)))
        group["content_h"] = max(1, int(math.ceil(raw_h)))
        group["margin"] = int(vertex_margin)
        group["w"] = group["content_w"] + group["margin"] * 2
        group["h"] = group["content_h"] + group["margin"] * 2
        for face_index in group["face_indices"]:
            face_to_group[face_index] = group["index"]

    return islands, groups, face_to_group


def calculate_group_shelf_layout(groups, padding=AUTO_ATLAS_DEFAULT_PADDING, max_size=AUTO_ATLAS_MAX_SIZE):
    if not groups:
        return 0, 0, {}

    sorted_groups = sorted(groups, key=lambda g: (max(g["w"], g["h"]), g["w"] * g["h"]), reverse=True)
    widest = max(int(g["w"]) for g in sorted_groups)
    total_area = sum(int(g["w"]) * int(g["h"]) for g in sorted_groups)
    natural = max(widest, int(math.sqrt(max(1, total_area))))

    candidates = set()
    candidates.add(widest)
    candidates.add(natural)
    for mul in (1.15, 1.35, 1.6, 2.0, 2.75, 3.5, 4.5):
        candidates.add(int(natural * mul))
    for group in sorted_groups:
        candidates.add(int(group["w"]))
        candidates.add(int(group["w"]) + max(0, padding))

    best = None

    for candidate_w in sorted(c for c in candidates if c > 0):
        atlas_w = min(max_size, max(widest, candidate_w))
        x = 0
        y = 0
        row_h = 0
        used_w = 0
        layout = {}
        failed = False

        for group in sorted_groups:
            w = int(group["w"])
            h = int(group["h"])
            if w > atlas_w:
                failed = True
                break

            if x > 0 and x + w > atlas_w:
                x = 0
                y += row_h + padding
                row_h = 0

            layout[group["index"]] = {"x": x, "y": y, "w": w, "h": h}
            used_w = max(used_w, x + w)
            x += w + padding
            row_h = max(row_h, h)

        if failed:
            continue

        used_h = max(1, y + row_h)
        if used_w > max_size or used_h > max_size:
            continue

        area = used_w * used_h
        max_side = max(used_w, used_h)
        fill = total_area / max(1, area)
        score = (area, max_side, -fill)
        if best is None or score < best[0]:
            best = (score, used_w, used_h, layout)

    if not best:
        raise RuntimeError(f"Per-material cluster cannot fit inside {max_size}x{max_size}")

    return max(1, best[1]), max(1, best[2]), best[3]


def collect_autoatlas_entries(context):
    active_mat = get_rebuild_material(context)
    if not active_mat:
        return {
            "objects": [],
            "entries": [],
            "material_to_entry": {},
            "warnings": ["No active material for RZAutoAtlas rebuild"],
            "active_material": None,
            "active_slots": [],
        }

    objects = objects_using_material(active_mat)
    warnings = []
    entries_by_key = {}
    material_to_entry = {}

    if not objects:
        warnings.append(f"No objects use active material '{active_mat.name}'")

    node = find_rzm_node_in_material(active_mat)
    if not node:
        warnings.append(f"Active material '{active_mat.name}' has no '{GROUP_NAME}' node")
        return {
            "objects": objects,
            "entries": [],
            "material_to_entry": material_to_entry,
            "warnings": warnings,
            "active_material": active_mat.name,
            "active_slots": [],
        }

    uv_bounds = uv_bounds_for_material_objects(objects, active_mat)
    if not uv_bounds:
        warnings.append(f"Active material '{active_mat.name}' has no UV-used polygons")
        return {
            "objects": objects,
            "entries": [],
            "material_to_entry": material_to_entry,
            "warnings": warnings,
            "active_material": active_mat.name,
            "active_slots": [],
        }

    base_color = socket_value(node, "Base Color", None)
    if base_color is None:
        base_color = getattr(active_mat, "diffuse_color", SLOT_DEFAULTS["Diffuse"])
    base_color = tuple(clamp01(v) for v in tuple(base_color)[:4])
    if len(base_color) < 4:
        base_color = tuple(list(base_color) + [1.0] * (4 - len(base_color)))

    slot_data = {}
    active_slots = []
    max_w, max_h = 3, 3
    reference_slot = None
    reference_image_size = [3, 3]
    reference_crop_rect = {"x": 0, "y": 0, "w": 3, "h": 3}

    for tex_name in TEXTURE_INPUTS:
        image, status, source = direct_image_link_info(node, tex_name)
        enabled = tex_name == "Diffuse" or bool(socket_value(node, f"Has {tex_name}", False))

        crop_rect = {"x": 0, "y": 0, "w": 3, "h": 3}
        percent = 0.0
        if enabled and image:
            crop_rect = crop_rect_from_uv_bounds(image, uv_bounds)
            percent = useful_area_percent(image, crop_rect)
            max_w = max(max_w, int(crop_rect["w"]))
            max_h = max(max_h, int(crop_rect["h"]))
            active_slots.append(tex_name)
            if reference_slot is None or tex_name == "Diffuse":
                reference_slot = tex_name
                reference_image_size = list(image_size_or_fallback(image))
                reference_crop_rect = dict(crop_rect)
        elif enabled and tex_name == "Diffuse":
            active_slots.append(tex_name)
            max_w = max(max_w, 3)
            max_h = max(max_h, 3)

        if status == "UNSUPPORTED_LINK" and enabled:
            warnings.append(f"{active_mat.name}/{tex_name}: unsupported direct source {source}")

        slot_data[tex_name] = {
            "enabled": enabled,
            "status": status if enabled else "DISABLED",
            "source": source,
            "image": image if enabled else None,
            "image_name": image.name if image and enabled else None,
            "image_path": image.filepath or image.filepath_raw if image and enabled else None,
            "size": list(image_size_or_fallback(image)) if image and enabled else [3, 3],
            "crop_rect": crop_rect,
            "useful_area_percent": percent,
        }

    faces = build_material_faces(objects, active_mat)
    vertex_margin = get_vertex_margin_px(context)
    pack_gap = get_pack_gap_px(context)
    islands, groups, face_to_group = build_repack_groups(
        faces,
        max(1, int(reference_image_size[0])),
        max(1, int(reference_image_size[1])),
        vertex_margin,
    )
    if not faces:
        warnings.append(f"Active material '{active_mat.name}' has no faces to repack")
    if not groups:
        warnings.append(f"Active material '{active_mat.name}' has no UV islands/groups to pack")

    key = f"{active_mat.name}::{node.name}"
    entry = {
        "key": key,
        "name": clean_name(active_mat.name),
        "material": active_mat,
        "material_name": active_mat.name,
        "node_name": node.name,
        "base_color": base_color,
        "width": max_w,
        "height": max_h,
        "uv_bounds": uv_bounds,
        "reference_slot": reference_slot or "Diffuse",
        "reference_image_size": reference_image_size,
        "reference_crop_rect": reference_crop_rect,
        "slots": slot_data,
        "object_names": set(),
        "slot_indices": {},
    }
    entries_by_key[key] = entry

    for obj in objects:
        mesh = obj.data
        if not mesh.uv_layers:
            warnings.append(f"{obj.name}: no UV layers; object skipped")
            continue

        for slot_index, slot in enumerate(obj.material_slots):
            mat = slot.material
            if mat != active_mat:
                continue

            entry["object_names"].add(obj.name)
            entry["slot_indices"].setdefault(obj.name, set()).add(slot_index)
            material_to_entry[(obj.name, slot_index)] = entry

    entries = list(entries_by_key.values())
    for entry in entries:
        entry["object_names"] = sorted(entry["object_names"])
        entry["slot_indices"] = {
            name: sorted(indices) for name, indices in entry["slot_indices"].items()
        }

    return {
        "objects": objects,
        "entries": entries,
        "material_to_entry": material_to_entry,
        "warnings": warnings,
        "active_material": active_mat.name,
        "active_slots": active_slots,
        "faces": faces,
        "islands": islands,
        "groups": groups,
        "face_to_group": face_to_group,
        "reference_size": reference_image_size,
        "vertex_margin_px": vertex_margin,
        "pack_gap_px": pack_gap,
    }


def calculate_shelf_layout(entries, padding=AUTO_ATLAS_DEFAULT_PADDING, max_size=AUTO_ATLAS_MAX_SIZE):
    if not entries:
        return 0, 0, {}

    sorted_entries = sorted(entries, key=lambda e: max(e["width"], e["height"]), reverse=True)
    total_area = sum((e["width"] + padding * 2) * (e["height"] + padding * 2) for e in sorted_entries)
    widest = max(e["width"] + padding * 2 for e in sorted_entries)
    start_width = next_power_of_two(max(widest, int(math.sqrt(total_area))))

    atlas_w = min(max_size, max(64, start_width))

    while True:
        x = padding
        y = padding
        row_h = 0
        layout = {}
        failed = False

        for entry in sorted_entries:
            w = int(entry["width"])
            h = int(entry["height"])
            if w + padding * 2 > atlas_w:
                failed = True
                break

            if x + w + padding > atlas_w:
                x = padding
                y += row_h + padding
                row_h = 0

            layout[entry["key"]] = {
                "x": x,
                "y": y,
                "w": w,
                "h": h,
            }
            x += w + padding
            row_h = max(row_h, h)

        atlas_h = next_power_of_two(y + row_h + padding)

        if not failed and atlas_h <= max_size:
            return atlas_w, atlas_h, layout

        if atlas_w >= max_size:
            raise RuntimeError(f"Atlas cannot fit inside {max_size}x{max_size}")
        atlas_w = min(max_size, atlas_w * 2)


def make_manifest(context, collection, atlas_w, atlas_h, layout):
    entries_json = []
    for entry in collection["entries"]:
        rect = {"x": 0, "y": 0, "w": atlas_w, "h": atlas_h}
        slots_json = {}
        for slot_name, data in entry["slots"].items():
            image = data.get("image")
            slots_json[slot_name] = {
                "enabled": data["enabled"],
                "status": data["status"],
                "image_name": image.name if image else None,
                "image_path": image.filepath or image.filepath_raw if image else None,
                "size": data["size"],
                "crop_rect": data.get("crop_rect"),
                "useful_area_percent": data.get("useful_area_percent", 0.0),
            }

        entries_json.append({
            "key": entry["key"],
            "name": entry["name"],
            "material": entry["material_name"],
            "node": entry["node_name"],
            "objects": entry["object_names"],
            "slot_indices": entry["slot_indices"],
            "base_color": list(entry["base_color"]),
            "source_size": [entry["width"], entry["height"]],
            "uv_bounds": entry.get("uv_bounds"),
            "reference_slot": entry.get("reference_slot"),
            "reference_image_size": entry.get("reference_image_size"),
            "reference_crop_rect": entry.get("reference_crop_rect"),
            "rect": rect,
            "slots": slots_json,
        })

    active_slots = collection.get("active_slots") or ["Diffuse"]
    groups_json = []
    packed_area = 0
    for group in collection.get("groups", []):
        group_rect = layout.get(group["index"], {})
        packed_area += int(group.get("w", 0)) * int(group.get("h", 0))
        groups_json.append({
            "index": group["index"],
            "islands": group["island_indices"],
            "face_count": len(group["face_indices"]),
            "uv_bounds": {
                "u_min": group["u_min"],
                "v_min": group["v_min"],
                "u_max": group["u_max"],
                "v_max": group["v_max"],
            },
            "source_pixel_size": [group["w"], group["h"]],
            "content_pixel_size": [group.get("content_w", group["w"]), group.get("content_h", group["h"])],
            "margin_px": group.get("margin", 0),
            "rect": group_rect,
        })

    manifest = {
        "schema": 1,
        "kind": "RZ_AUTO_ATLAS_QA",
        "active_material": collection.get("active_material"),
        "active_slots": active_slots,
        "uv_layer": AUTO_ATLAS_UV_NAME,
        "output_dir": resolve_dynatlas_dir(context),
        "atlas_size": [atlas_w, atlas_h],
        "vertex_margin_px": collection.get("vertex_margin_px", AUTO_ATLAS_VERTEX_MARGIN_DEFAULT),
        "pack_gap_px": collection.get("pack_gap_px", AUTO_ATLAS_DEFAULT_PADDING),
        "resources": {
            slot: autoatlas_resource_name(collection, slot) for slot in active_slots
        },
        "entries": entries_json,
        "groups": groups_json,
        "stats": {
            "objects": len(collection.get("objects", [])),
            "faces": len(collection.get("faces", [])),
            "islands": len(collection.get("islands", [])),
            "stack_groups": len(collection.get("groups", [])),
            "packed_pixel_area": packed_area,
            "atlas_pixel_area": max(1, atlas_w * atlas_h),
            "atlas_fill_percent": packed_area * 100.0 / max(1, atlas_w * atlas_h),
            "reference_pixel_area": max(1, int((collection.get("reference_size") or [1, 1])[0]) * int((collection.get("reference_size") or [1, 1])[1])),
            "reference_used_percent": packed_area * 100.0 / max(1, int((collection.get("reference_size") or [1, 1])[0]) * int((collection.get("reference_size") or [1, 1])[1])),
        },
        "warnings": collection["warnings"],
    }
    return manifest


def store_manifest(context, manifest):
    text = json.dumps(manifest, indent=2, sort_keys=True)
    context.scene["rzm_autoatlas_manifest_json"] = text
    return text


def write_manifest_files(context, manifest):
    out_dir = resolve_dynatlas_dir(context)
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "RZAutoAtlas.manifest.json")
    report_path = os.path.join(out_dir, "RZAutoAtlas.report.txt")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    lines = [
        "RZAutoAtlas QA Report",
        f"Active material: {manifest.get('active_material')}",
        f"Atlas size: {manifest['atlas_size'][0]}x{manifest['atlas_size'][1]}",
        f"UV layer: {manifest['uv_layer']}",
        f"Vertex margin: {manifest.get('vertex_margin_px')} px",
        f"Pack gap: {manifest.get('pack_gap_px')} px",
        f"Active slots: {', '.join(manifest.get('active_slots') or [])}",
        f"Entries: {len(manifest['entries'])}",
        f"Objects: {manifest['stats']['objects']}",
        f"Faces: {manifest['stats']['faces']}",
        f"UV islands: {manifest['stats']['islands']}",
        f"Stack groups: {manifest['stats']['stack_groups']}",
        f"Packed area: {manifest['stats']['packed_pixel_area']} px",
        f"Atlas fill: {manifest['stats']['atlas_fill_percent']:.2f}%",
        f"Reference used: {manifest['stats']['reference_used_percent']:.2f}%",
        "",
        "Resources:",
    ]
    for slot, res_name in manifest["resources"].items():
        lines.append(f"  {slot}: {res_name}")
    if manifest["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"  - {w}" for w in manifest["warnings"])
    lines.extend(["", "Entries:"])
    for entry in manifest["entries"]:
        r = entry["rect"]
        lines.append(f"  {entry['material']} -> ({r.get('x')},{r.get('y')},{r.get('w')}x{r.get('h')})")
        lines.append(f"    UV bounds: {entry.get('uv_bounds')}")
        for slot_name, slot_data in entry["slots"].items():
            if not slot_data.get("enabled"):
                continue
            crop = slot_data.get("crop_rect")
            useful = slot_data.get("useful_area_percent", 0.0)
            lines.append(f"    {slot_name}: {slot_data.get('status')} crop={crop} useful={useful:.2f}%")
    lines.extend(["", "Packed Groups:"])
    for group in manifest.get("groups", []):
        lines.append(
            f"  group {group['index']}: rect={group['rect']} "
            f"content={group['content_pixel_size']} margin={group['margin_px']} "
            f"outer={group['source_pixel_size']} faces={group['face_count']} islands={group['islands']}"
        )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return manifest_path, report_path


def image_pixels_scaled(image, width, height):
    if not image:
        return None

    temp = None
    source = image
    try:
        if int(image.size[0]) != width or int(image.size[1]) != height:
            temp = image.copy()
            temp.name = f"_RZAutoAtlas_TEMP_{image.name}"
            temp.scale(width, height)
            source = temp

        pixels = array("f", [0.0]) * (width * height * 4)
        source.pixels.foreach_get(pixels)
        return pixels
    finally:
        if temp:
            try:
                bpy.data.images.remove(temp)
            except Exception:
                pass


def crop_image_pixels(image, crop_rect, dst_w, dst_h):
    if not image:
        return None

    src_w, src_h = image_size_or_fallback(image)
    crop_x = int(crop_rect.get("x", 0))
    crop_y = int(crop_rect.get("y", 0))
    crop_w = max(1, int(crop_rect.get("w", src_w)))
    crop_h = max(1, int(crop_rect.get("h", src_h)))

    crop_x = max(0, min(src_w - 1, crop_x))
    crop_y = max(0, min(src_h - 1, crop_y))
    crop_w = max(1, min(src_w - crop_x, crop_w))
    crop_h = max(1, min(src_h - crop_y, crop_h))

    src_pixels = array("f", [0.0]) * (src_w * src_h * 4)
    image.pixels.foreach_get(src_pixels)

    dst = array("f", [0.0]) * (dst_w * dst_h * 4)
    for yy in range(dst_h):
        src_yy = crop_y + min(crop_h - 1, int(yy * crop_h / max(1, dst_h)))
        for xx in range(dst_w):
            src_xx = crop_x + min(crop_w - 1, int(xx * crop_w / max(1, dst_w)))
            src_idx = (src_yy * src_w + src_xx) * 4
            dst_idx = (yy * dst_w + xx) * 4
            dst[dst_idx:dst_idx + 4] = src_pixels[src_idx:src_idx + 4]

    return dst


def fill_rect(pixels, atlas_w, atlas_h, rect, color):
    x0, y0, w, h = int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"])
    rgba = tuple(float(v) for v in color[:4])
    for yy in range(y0, min(y0 + h, atlas_h)):
        row = yy * atlas_w * 4
        for xx in range(x0, min(x0 + w, atlas_w)):
            idx = row + xx * 4
            pixels[idx:idx + 4] = array("f", rgba)


def paste_rect(pixels, atlas_w, atlas_h, rect, source_pixels):
    x0, y0, w, h = int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"])
    if not source_pixels:
        return
    for yy in range(h):
        dst_y = y0 + yy
        if dst_y < 0 or dst_y >= atlas_h:
            continue
        src_row = yy * w * 4
        dst_row = dst_y * atlas_w * 4
        for xx in range(w):
            dst_x = x0 + xx
            if dst_x < 0 or dst_x >= atlas_w:
                continue
            src_idx = src_row + xx * 4
            dst_idx = dst_row + dst_x * 4
            pixels[dst_idx:dst_idx + 4] = source_pixels[src_idx:src_idx + 4]


def get_image_pixel_data(image):
    if not image:
        return None, 0, 0
    width, height = image_size_or_fallback(image)
    pixels = array("f", [0.0]) * (width * height * 4)
    image.pixels.foreach_get(pixels)
    return pixels, width, height


def sample_pixels_bilinear(pixels, width, height, u, v, fallback):
    if not pixels or width <= 0 or height <= 0:
        return fallback

    u = clamp01(u)
    v = clamp01(v)
    x = u * (width - 1)
    y = v * (height - 1)

    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    x1 = min(width - 1, x0 + 1)
    y1 = min(height - 1, y0 + 1)
    tx = x - x0
    ty = y - y0

    def px(ix, iy):
        idx = (iy * width + ix) * 4
        return pixels[idx:idx + 4]

    c00 = px(x0, y0)
    c10 = px(x1, y0)
    c01 = px(x0, y1)
    c11 = px(x1, y1)

    out = []
    for i in range(4):
        a = c00[i] * (1.0 - tx) + c10[i] * tx
        b = c01[i] * (1.0 - tx) + c11[i] * tx
        out.append(a * (1.0 - ty) + b * ty)
    return out


def rasterize_triangle(dst_pixels, dst_w, dst_h, dst_points, src_uvs, src_pixels, src_w, src_h, fallback):
    (x0, y0), (x1, y1), (x2, y2) = dst_points
    min_x = max(0, int(math.floor(min(x0, x1, x2))))
    max_x = min(dst_w - 1, int(math.ceil(max(x0, x1, x2))))
    min_y = max(0, int(math.floor(min(y0, y1, y2))))
    max_y = min(dst_h - 1, int(math.ceil(max(y0, y1, y2))))

    denom = ((y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2))
    if abs(denom) < 1.0e-12:
        return 0

    written = 0
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            sx = px + 0.5
            sy = py + 0.5
            w0 = ((y1 - y2) * (sx - x2) + (x2 - x1) * (sy - y2)) / denom
            w1 = ((y2 - y0) * (sx - x2) + (x0 - x2) * (sy - y2)) / denom
            w2 = 1.0 - w0 - w1

            if w0 < -1.0e-6 or w1 < -1.0e-6 or w2 < -1.0e-6:
                continue

            src_u = src_uvs[0][0] * w0 + src_uvs[1][0] * w1 + src_uvs[2][0] * w2
            src_v = src_uvs[0][1] * w0 + src_uvs[1][1] * w1 + src_uvs[2][1] * w2
            color = sample_pixels_bilinear(src_pixels, src_w, src_h, src_u, src_v, fallback)

            idx = (py * dst_w + px) * 4
            dst_pixels[idx:idx + 4] = array("f", color)
            written += 1

    return written


def dilate_pixels_by_alpha(pixels, width, height, iterations):
    iterations = max(0, int(iterations))
    if iterations <= 0:
        return pixels

    for _ in range(iterations):
        source = array("f", pixels)
        changed = 0
        for y in range(height):
            for x in range(width):
                idx = (y * width + x) * 4
                if source[idx + 3] > 0.0:
                    continue

                accum = [0.0, 0.0, 0.0, 0.0]
                count = 0
                for dy in (-1, 0, 1):
                    ny = y + dy
                    if ny < 0 or ny >= height:
                        continue
                    for dx in (-1, 0, 1):
                        nx = x + dx
                        if nx < 0 or nx >= width or (dx == 0 and dy == 0):
                            continue
                        nidx = (ny * width + nx) * 4
                        if source[nidx + 3] <= 0.0:
                            continue
                        accum[0] += source[nidx]
                        accum[1] += source[nidx + 1]
                        accum[2] += source[nidx + 2]
                        accum[3] += source[nidx + 3]
                        count += 1

                if count:
                    pixels[idx] = accum[0] / count
                    pixels[idx + 1] = accum[1] / count
                    pixels[idx + 2] = accum[2] / count
                    pixels[idx + 3] = accum[3] / count
                    changed += 1

        if changed == 0:
            break

    return pixels


def face_destination_points(face, group, group_rect, ref_w, ref_h):
    points = []
    margin = int(group.get("margin", 0))
    for u, v in face["uvs"]:
        x = group_rect["x"] + margin + (u - group["u_min"]) * ref_w
        y = group_rect["y"] + margin + (v - group["v_min"]) * ref_h
        points.append((x, y))
    return points


def build_atlas_images(context, collection, atlas_w, atlas_h, layout):
    created = {}
    active_slots = collection.get("active_slots") or ["Diffuse"]
    faces = collection.get("faces", [])
    groups = {g["index"]: g for g in collection.get("groups", [])}
    face_to_group = collection.get("face_to_group", {})
    ref_w, ref_h = collection.get("reference_size") or [atlas_w, atlas_h]
    ref_w = max(1, int(ref_w))
    ref_h = max(1, int(ref_h))

    entry = collection["entries"][0] if collection.get("entries") else None
    if not entry:
        return created

    for slot_name in active_slots:
        image_name = autoatlas_resource_name(collection, slot_name)
        old = bpy.data.images.get(image_name)
        if old:
            bpy.data.images.remove(old)

        atlas = bpy.data.images.new(image_name, width=atlas_w, height=atlas_h, alpha=True, float_buffer=False)
        atlas.file_format = "PNG"
        fallback = entry["base_color"] if slot_name == "Diffuse" else SLOT_DEFAULTS[slot_name]
        dst_pixels = array("f", AUTO_ATLAS_TRANSPARENT) * (atlas_w * atlas_h)

        slot = entry["slots"].get(slot_name)
        source_image = slot.get("image") if slot and slot.get("status") == "IMAGE" else None
        src_pixels, src_w, src_h = get_image_pixel_data(source_image)

        if not source_image:
            collection["warnings"].append(f"{entry['material_name']}/{slot_name}: no source image, filled fallback")
        elif [src_w, src_h] != [ref_w, ref_h]:
            collection["warnings"].append(
                f"{entry['material_name']}/{slot_name}: source {src_w}x{src_h}, "
                f"layout reference {ref_w}x{ref_h}; rebake resamples by UV"
            )

        written = 0
        for face_index, face in enumerate(faces):
            group_index = face_to_group.get(face_index)
            group = groups.get(group_index)
            group_rect = layout.get(group_index)
            if not group or not group_rect:
                continue

            dst_points = face_destination_points(face, group, group_rect, ref_w, ref_h)
            src_uvs = face["uvs"]

            for tri_i in range(1, len(src_uvs) - 1):
                tri_dst = [dst_points[0], dst_points[tri_i], dst_points[tri_i + 1]]
                tri_src = [src_uvs[0], src_uvs[tri_i], src_uvs[tri_i + 1]]
                written += rasterize_triangle(
                    dst_pixels,
                    atlas_w,
                    atlas_h,
                    tri_dst,
                    tri_src,
                    src_pixels,
                    src_w,
                    src_h,
                    fallback,
                )

        dst_pixels = dilate_pixels_by_alpha(dst_pixels, atlas_w, atlas_h, int(collection.get("vertex_margin_px", 0)))
        atlas.pixels.foreach_set(dst_pixels)
        atlas.update()
        atlas["rzm_autoatlas_written_pixels"] = written
        created[slot_name] = atlas

    context.scene["rzm_autoatlas_images"] = ",".join(
        autoatlas_resource_name(collection, slot) for slot in active_slots
    )
    return created


def apply_autoatlas_uv(context, collection, atlas_w, atlas_h, layout):
    changed = 0
    groups = {g["index"]: g for g in collection.get("groups", [])}
    face_to_group = collection.get("face_to_group", {})
    ref_w, ref_h = collection.get("reference_size") or [atlas_w, atlas_h]
    ref_w = max(1, int(ref_w))
    ref_h = max(1, int(ref_h))

    target_layers = {}
    for obj in collection.get("objects", []):
        mesh = obj.data
        if not mesh:
            continue

        target_uv = mesh.uv_layers.get(AUTO_ATLAS_UV_NAME)
        if not target_uv:
            target_uv = mesh.uv_layers.new(name=AUTO_ATLAS_UV_NAME)
        target_layers[obj.name] = target_uv

    for face_index, face in enumerate(collection.get("faces", [])):
        group_index = face_to_group.get(face_index)
        group = groups.get(group_index)
        group_rect = layout.get(group_index)
        target_uv = target_layers.get(face["obj_name"])
        if not group or not group_rect or not target_uv:
            continue

        margin = int(group.get("margin", 0))
        for loop_index, (u, v) in zip(face["loop_indices"], face["uvs"]):
            x = group_rect["x"] + margin + (u - group["u_min"]) * ref_w
            y = group_rect["y"] + margin + (v - group["v_min"]) * ref_h
            target_uv.data[loop_index].uv = (
                x / float(atlas_w),
                y / float(atlas_h),
            )
            changed += 1

    for obj in collection.get("objects", []):
        if obj.data:
            obj.data.update()


    return changed


def calculate_autoatlas_pipeline(context, operator=None, write_files=False):
    collection = collect_autoatlas_entries(context)
    entries = collection["entries"]
    if not entries:
        report_to_operator(operator, "WARNING", "[RZM QA] No RZM TexWorks Material entries found.")
        return None, None, None, collection

    atlas_w, atlas_h, layout = calculate_group_shelf_layout(
        collection.get("groups", []),
        padding=int(collection.get("pack_gap_px", AUTO_ATLAS_DEFAULT_PADDING)),
    )
    collection["group_layout"] = layout
    manifest = make_manifest(context, collection, atlas_w, atlas_h, layout)
    store_manifest(context, manifest)

    if write_files:
        paths = write_manifest_files(context, manifest)
        print(f"[RZM QA] Wrote manifest: {paths[0]}")
        print(f"[RZM QA] Wrote report: {paths[1]}")

    return manifest, layout, (atlas_w, atlas_h), collection


def builtin_calculate_atlas_size(context, operator=None):
    manifest, _layout, size, collection = calculate_autoatlas_pipeline(context, operator, write_files=True)
    if not manifest:
        return {"CANCELLED"}

    msg = (
        f"[RZM QA] Atlas calculated: {size[0]}x{size[1]}, "
        f"entries={len(collection['entries'])}, warnings={len(collection['warnings'])}"
    )
    report_to_operator(operator, "INFO", msg)
    return {"FINISHED"}


def builtin_rebuild_textures(context, operator=None):
    manifest, layout, size, collection = calculate_autoatlas_pipeline(context, operator, write_files=True)
    if not manifest:
        return {"CANCELLED"}

    images = build_atlas_images(context, collection, size[0], size[1], layout)
    changed_uvs = apply_autoatlas_uv(context, collection, size[0], size[1], layout)
    manifest = make_manifest(context, collection, size[0], size[1], layout)
    store_manifest(context, manifest)
    write_manifest_files(context, manifest)

    msg = (
        f"[RZM QA] Rebuilt atlas images in Blender: {len(images)} maps, "
        f"UV layer={AUTO_ATLAS_UV_NAME}, loops remapped={changed_uvs}"
    )
    report_to_operator(operator, "INFO", msg)
    return {"FINISHED"}


def builtin_export_atlas(context, operator=None):
    manifest, layout, size, collection = calculate_autoatlas_pipeline(context, operator, write_files=True)
    if not manifest:
        return {"CANCELLED"}

    images = {}
    missing = []
    active_slots = collection.get("active_slots") or ["Diffuse"]
    for slot in active_slots:
        name = autoatlas_resource_name(collection, slot)
        img = bpy.data.images.get(name)
        if img:
            images[slot] = img
        else:
            missing.append(slot)

    if missing:
        images = build_atlas_images(context, collection, size[0], size[1], layout)
        apply_autoatlas_uv(context, collection, size[0], size[1], layout)
        manifest = make_manifest(context, collection, size[0], size[1], layout)
        store_manifest(context, manifest)
        write_manifest_files(context, manifest)

    out_dir = resolve_dynatlas_dir(context)
    os.makedirs(out_dir, exist_ok=True)

    saved = []
    for slot, image in images.items():
        path = os.path.join(out_dir, autoatlas_filename(collection, slot))
        image.file_format = "PNG"
        image.filepath_raw = path
        image.save()
        saved.append(path)

    msg = f"[RZM QA] Exported {len(saved)} PNG atlas map(s) to {out_dir}"
    report_to_operator(operator, "INFO", msg)
    return {"FINISHED"}


def texworks_resource_format(slot_name):
    if slot_name == "Diffuse":
        return "DXGI_FORMAT_R8G8B8A8_UNORM_SRGB"
    if slot_name == "NormalMap":
        return "DXGI_FORMAT_R8G8_TYPELESS"
    return "DXGI_FORMAT_R8G8B8A8_UNORM"


def find_tw_resource(rzm, name):
    for res in rzm.tw_resources:
        if res.name == name:
            return res
    return None


def remove_tw_resource_by_index(collection, index):
    try:
        collection.remove(index)
        return True
    except Exception:
        return False


def sync_autoatlas_texworks_data(context, operator=None):
    manifest, layout, size, collection = calculate_autoatlas_pipeline(context, operator, write_files=True)
    if not manifest:
        return {"CANCELLED"}

    rzm = getattr(context.scene, "rzm", None)
    if not rzm or not hasattr(rzm, "tw_resources"):
        report_to_operator(operator, "ERROR", "[RZM QA] scene.rzm.tw_resources is not available.")
        return {"CANCELLED"}

    material_key = autoatlas_material_key(collection)
    prefix = f"{AUTO_ATLAS_RESOURCE_PREFIX}.{material_key}."
    desired = set(manifest["resources"].values())

    removed = 0
    for index in reversed(range(len(rzm.tw_resources))):
        res = rzm.tw_resources[index]
        if res.name.startswith(prefix) and res.name not in desired:
            if remove_tw_resource_by_index(rzm.tw_resources, index):
                removed += 1

    updated = 0
    created = 0
    out_rel_dir = "DynAtlas"

    for slot_name, resource_name in manifest["resources"].items():
        res = find_tw_resource(rzm, resource_name)
        if not res:
            res = rzm.tw_resources.add()
            created += 1
        else:
            updated += 1

        filename = autoatlas_filename(collection, slot_name)
        res.name = resource_name
        res.type = "ON_DISK"
        res.path = os.path.join(out_rel_dir, filename)
        res.resolution = manifest["atlas_size"]
        res.format = texworks_resource_format(slot_name)
        if hasattr(res, "qt_tag"):
            res.qt_tag = "RZAutoAtlas"

    context.scene["rzm_autoatlas_cluster_manifest_json"] = json.dumps(manifest, indent=2, sort_keys=True)

    text_name = f"{AUTO_ATLAS_RESOURCE_PREFIX}.{material_key}.manifest"
    text = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
    text.clear()
    text.write(json.dumps(manifest, indent=2, sort_keys=True))

    msg = (
        f"[RZM QA] TexWorks sync: material={material_key}, "
        f"created={created}, updated={updated}, removed={removed}, "
        f"clusters={len(manifest.get('groups', []))}"
    )
    report_to_operator(operator, "INFO", msg)
    return {"FINISHED"}


def build_post_export_uv_patch_plan(context):
    raw_manifest = context.scene.get("rzm_autoatlas_cluster_manifest_json")
    manifest = None
    if raw_manifest:
        try:
            manifest = json.loads(raw_manifest)
        except Exception:
            manifest = None

    ranges = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        raw_range = obj.get("RZM_EXPORT_RANGE_JSON")
        if raw_range:
            try:
                data = json.loads(raw_range)
            except Exception:
                data = {}
        else:
            data = {}

        if not raw_range and "RZM_EXPORT_VB_OFFSET" not in obj:
            continue

        ranges.append({
            "object": obj.name,
            "component": data.get("component", obj.get("RZM_EXPORT_COMPONENT", "")),
            "part_fullname": data.get("part_fullname", obj.get("RZM_EXPORT_PART_FULLNAME", "")),
            "vb_offset": int(data.get("vb_offset", obj.get("RZM_EXPORT_VB_OFFSET", 0)) or 0),
            "vb_count": int(data.get("vb_count", obj.get("RZM_EXPORT_VB_COUNT", 0)) or 0),
            "vb_end": int(data.get("vb_end", obj.get("RZM_EXPORT_VB_END", 0)) or 0),
            "is_robust": bool(data.get("is_robust", False)),
            "has_vertex_map": bool(data.get("has_vertex_map", False)),
        })

    return {
        "schema": 1,
        "kind": "RZ_POST_EXPORT_UV_PATCH_PLAN_QA",
        "cluster_material": manifest.get("active_material") if manifest else None,
        "cluster_uv_layer": manifest.get("uv_layer") if manifest else None,
        "cluster_atlas_size": manifest.get("atlas_size") if manifest else None,
        "cluster_groups": manifest.get("groups", []) if manifest else [],
        "ranges": ranges,
        "notes": [
            "Dry-run only. Does not patch buffers.",
            "Future patcher should use export cache/ranges as authority and cluster manifest as UV transform source.",
        ],
    }


def write_post_export_uv_patch_plan(context, operator=None):
    plan = build_post_export_uv_patch_plan(context)
    out_dir = os.path.join(resolve_mod_output_dir(context), "debug")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "rz_autoatlas_post_export_uv_patch_plan.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, sort_keys=True)
    report_to_operator(
        operator,
        "INFO",
        f"[RZM QA] Wrote UV patch plan: ranges={len(plan['ranges'])}, groups={len(plan['cluster_groups'])}",
    )
    return {"FINISHED"}


def print_debug():
    mat = get_context_material()
    group = bpy.data.node_groups.get(GROUP_NAME)

    print("\n========== RZM TEXWORKS MATERIAL HUB DEBUG ==========")
    print(f"Active/Shader Material: {mat.name if mat else None}")
    print(f"Node Group Found: {bool(group)}")

    if not group:
        print("====================================================\n")
        return

    print(f"Group Name: {group.name}")
    print(f"Schema: {group.get('rzm_texworks_schema')}")
    print(f"Kind: {group.get('rzm_texworks_kind')}")
    print(f"Role: {group.get('rzm_texworks_role')}")

    instances = find_group_instances(group)
    print(f"Materials using group: {len(set(m.name for m, _ in instances))}")
    print(f"Node instances: {len(instances)}")

    print("\n--- Interface Inputs ---")
    for item in group.interface.items_tree:
        if getattr(item, "item_type", None) == "SOCKET" and item.in_out == "INPUT":
            print(f"  IN  {item.name} [{item.socket_type}]")

    print("\n--- Interface Outputs ---")
    for item in group.interface.items_tree:
        if getattr(item, "item_type", None) == "SOCKET" and item.in_out == "OUTPUT":
            print(f"  OUT {item.name} [{item.socket_type}]")

    print("\n--- Instances / Bake Preview Passport ---")

    for mat, node in instances:
        print(f"\nMaterial: {mat.name}")
        print(f"Node: {node.name}")
        print(f"Objects: {material_objects(mat)}")

        has_light = bool(socket_value(node, "Has LightMap", False))
        has_mat = bool(socket_value(node, "Has MaterialMap", False))
        has_norm = bool(socket_value(node, "Has NormalMap", False))
        has_extra = bool(socket_value(node, "Has Extra", False))

        print("\nSemantic Textures:")
        for tex_name in TEXTURE_INPUTS:
            img = find_image_from_socket(node.inputs.get(tex_name))

            enabled = True
            if tex_name == "LightMap":
                enabled = has_light
            elif tex_name == "MaterialMap":
                enabled = has_mat
            elif tex_name == "NormalMap":
                enabled = has_norm
            elif tex_name == "Extra":
                enabled = has_extra

            cs = colorspace_name(socket_value(node, f"{tex_name} Color Space", 0))
            print(
                f"  {tex_name}: enabled={enabled} | "
                f"expected_colorspace={cs} | image={image_info(img)}"
            )

        print("\nPreview Channel Mapping:")
        print(f"  Emit      <- {source_name(socket_value(node, 'Preview Emit Source', 3))}")
        print(f"  Metallic  <- {source_name(socket_value(node, 'Preview Metallic Source', 8))}")
        print(f"  Roughness <- {source_name(socket_value(node, 'Preview Roughness Source', 9))}")
        print(f"  AO        <- {source_name(socket_value(node, 'Preview AO Source', 4))}")
        print(f"  Alpha     <- {source_name(socket_value(node, 'Preview Alpha Source', 3))}")
        print(f"  NormalMap Preset: {normal_preset_name(socket_value(node, 'NormalMap Preset', 0))}")

        print("\nBake Interpretation:")
        print("  Diffuse: ALWAYS BAKE RGBA")
        print(f"  LightMap: {'BAKE RGBA' if has_light else 'SKIP'}")
        print(f"  MaterialMap: {'BAKE RGBA' if has_mat else 'SKIP'}")
        print(f"  NormalMap: {'BAKE RGB' if has_norm else 'SKIP'}")
        print(f"  Extra: {'BAKE RGBA' if has_extra else 'SKIP'}")

    print("\n====================================================\n")


class RZM_QA_OT_CreateUpdateMaterialNode(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.create_update_material_node"
    bl_label = "Create / Update RZM Material Node"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        group = make_or_update_group()
        mat = get_context_material()

        if not mat:
            self.report({"ERROR"}, "No active Shader Editor material found.")
            return {"CANCELLED"}

        add_group_instance(mat, group)
        self.report({"INFO"}, "Added RZM TexWorks Material hub node. Nothing was rewired.")
        return {"FINISHED"}


class RZM_QA_OT_UpdateGroupDefinition(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.update_group_definition"
    bl_label = "Update Group Definition"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        make_or_update_group(force=True)
        self.report({"INFO"}, "Rebuilt RZM TexWorks Material group definition.")
        return {"FINISHED"}


class RZM_QA_OT_CreateEmptyMaterial(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.create_empty_material"
    bl_label = "Create Empty RZM Material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        create_empty_material()
        self.report({"INFO"}, "Created empty RZM AutoAtlas Material.")
        return {"FINISHED"}


class RZM_QA_OT_PrintNodeDebug(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.print_node_debug"
    bl_label = "Print Node Debug"

    def execute(self, context):
        print_debug()
        self.report({"INFO"}, "Printed TexWorks material hub debug.")
        return {"FINISHED"}


class RZM_QA_OT_LoadRuntimeAction(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.load_runtime_action"
    bl_label = "Load Runtime Action"
    bl_options = {"REGISTER"}

    action_id: bpy.props.StringProperty(default=DEFAULT_BAKE_ACTION_ID)
    script_name: bpy.props.StringProperty(default=DEFAULT_BAKE_SCRIPT)
    function_name: bpy.props.StringProperty(default=DEFAULT_BAKE_FUNCTION)

    def execute(self, context):
        base_dir = qa_dir()
        script_path = os.path.join(base_dir, self.script_name)

        try:
            callback = load_callback_from_script(script_path, self.function_name)
            register_runtime_action(self.action_id, callback)
        except Exception as exc:
            self.report({"ERROR"}, f"Runtime load failed: {exc}")
            print(f"[RZM QA] Runtime load failed: {exc}")
            print(f"[RZM QA] Runtime base dir: {base_dir}")
            print(f"[RZM QA] Runtime script path: {script_path}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Loaded runtime action '{self.action_id}' from {self.script_name}")
        print(f"[RZM QA] Loaded runtime action '{self.action_id}' from {script_path}")
        return {"FINISHED"}


class RZM_QA_OT_RunRuntimeAction(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.run_runtime_action"
    bl_label = "Run Runtime Action"
    bl_options = {"REGISTER", "UNDO"}

    action_id: bpy.props.StringProperty(default=DEFAULT_BAKE_ACTION_ID)

    def execute(self, context):
        try:
            result = run_runtime_action(self.action_id, context, operator=self)
        except Exception as exc:
            self.report({"ERROR"}, f"Runtime action failed: {exc}")
            print(f"[RZM QA] Runtime action '{self.action_id}' failed: {exc}")
            return {"CANCELLED"}

        if isinstance(result, set):
            return result

        self.report({"INFO"}, f"Runtime action '{self.action_id}' finished.")
        return {"FINISHED"}


class RZM_QA_OT_RebuildTextures(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.rebuild_textures"
    bl_label = "Rebuild Textures"
    bl_description = "Runtime hook: rebake/repackage selected RZM material textures"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            result = builtin_rebuild_textures(context, operator=self)
        except Exception as exc:
            self.report({"ERROR"}, f"Rebuild hook failed: {exc}")
            print(f"[RZM QA] Rebuild textures hook failed: {exc}")
            traceback.print_exc()
            return {"CANCELLED"}

        return result if isinstance(result, set) else {"FINISHED"}


class RZM_QA_OT_CalculateAtlasSize(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.calculate_atlas_size"
    bl_label = "Calculate Atlas Size"
    bl_description = "Runtime hook: calculate target atlas size/layout without export"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            result = builtin_calculate_atlas_size(context, operator=self)
        except Exception as exc:
            self.report({"ERROR"}, f"Calculate hook failed: {exc}")
            print(f"[RZM QA] Calculate atlas hook failed: {exc}")
            traceback.print_exc()
            return {"CANCELLED"}

        return result if isinstance(result, set) else {"FINISHED"}


class RZM_QA_OT_ExportAtlas(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.export_atlas"
    bl_label = "Export Atlas"
    bl_description = "Runtime hook: export rebuilt atlas textures/resources"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            result = builtin_export_atlas(context, operator=self)
        except Exception as exc:
            self.report({"ERROR"}, f"Export hook failed: {exc}")
            print(f"[RZM QA] Export atlas hook failed: {exc}")
            traceback.print_exc()
            return {"CANCELLED"}

        return result if isinstance(result, set) else {"FINISHED"}


class RZM_QA_OT_SyncTexWorksData(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.sync_texworks_data"
    bl_label = "Sync TexWorks Data"
    bl_description = "Add, update, or remove TexWorks resource registration for the active material cluster"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            result = sync_autoatlas_texworks_data(context, operator=self)
        except Exception as exc:
            self.report({"ERROR"}, f"TexWorks sync failed: {exc}")
            print(f"[RZM QA] TexWorks sync failed: {exc}")
            traceback.print_exc()
            return {"CANCELLED"}

        return result if isinstance(result, set) else {"FINISHED"}


class RZM_QA_OT_WritePostExportUVPatchPlan(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.write_post_export_uv_patch_plan"
    bl_label = "Write UV Patch Plan"
    bl_description = "Write dry-run metadata for future post-export TEXCOORD buffer patching"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            return write_post_export_uv_patch_plan(context, operator=self)
        except Exception as exc:
            self.report({"ERROR"}, f"UV patch plan failed: {exc}")
            print(f"[RZM QA] UV patch plan failed: {exc}")
            traceback.print_exc()
            return {"CANCELLED"}


class RZM_QA_PT_TexWorksAtlasMaterial(bpy.types.Panel):
    bl_label = "TexWorks Atlas Material"
    bl_idname = "RZM_QA_PT_texworks_atlas_material"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "RZM QA"

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.tree_type == "ShaderNodeTree"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Material Semantic Hub", icon="NODETREE")

        layout.operator(
            "rzm_qa_texworks_atlas.create_update_material_node",
            icon="NODE",
        )

        layout.operator(
            "rzm_qa_texworks_atlas.update_group_definition",
            icon="FILE_REFRESH",
        )

        layout.separator()

        layout.operator(
            "rzm_qa_texworks_atlas.create_empty_material",
            icon="MATERIAL",
        )

        layout.operator(
            "rzm_qa_texworks_atlas.print_node_debug",
            icon="CONSOLE",
        )

        layout.separator()
        layout.label(text="Runtime Prototype Hook", icon="SCRIPT")

        load_op = layout.operator(
            "rzm_qa_texworks_atlas.load_runtime_action",
            text="Reload BakePrototype.py",
            icon="FILE_REFRESH",
        )
        load_op.action_id = DEFAULT_BAKE_ACTION_ID
        load_op.script_name = DEFAULT_BAKE_SCRIPT
        load_op.function_name = DEFAULT_BAKE_FUNCTION

        run_op = layout.operator(
            "rzm_qa_texworks_atlas.run_runtime_action",
            text="Run Bake Prototype",
            icon="PLAY",
        )
        run_op.action_id = DEFAULT_BAKE_ACTION_ID

        layout.separator()
        layout.label(text="Atlas Pipeline Hooks", icon="TEXTURE")
        layout.prop(context.window_manager, "rzm_qa_autoatlas_vertex_margin_px", text="Island Margin px")
        layout.prop(context.window_manager, "rzm_qa_autoatlas_pack_gap_px", text="Pack Gap px")
        layout.operator(
            "rzm_qa_texworks_atlas.rebuild_textures",
            text="Rebuild Textures",
            icon="RENDER_STILL",
        )
        layout.operator(
            "rzm_qa_texworks_atlas.calculate_atlas_size",
            text="Calculate Atlas Size",
            icon="DRIVER_DISTANCE",
        )
        layout.operator(
            "rzm_qa_texworks_atlas.export_atlas",
            text="Export",
            icon="EXPORT",
        )
        layout.operator(
            "rzm_qa_texworks_atlas.sync_texworks_data",
            text="Sync TexWorks Data",
            icon="LINKED",
        )
        layout.operator(
            "rzm_qa_texworks_atlas.write_post_export_uv_patch_plan",
            text="Write UV Patch Plan",
            icon="TEXT",
        )


CLASSES = (
    RZM_QA_OT_CreateUpdateMaterialNode,
    RZM_QA_OT_UpdateGroupDefinition,
    RZM_QA_OT_CreateEmptyMaterial,
    RZM_QA_OT_PrintNodeDebug,
    RZM_QA_OT_LoadRuntimeAction,
    RZM_QA_OT_RunRuntimeAction,
    RZM_QA_OT_RebuildTextures,
    RZM_QA_OT_CalculateAtlasSize,
    RZM_QA_OT_ExportAtlas,
    RZM_QA_OT_SyncTexWorksData,
    RZM_QA_OT_WritePostExportUVPatchPlan,
    RZM_QA_PT_TexWorksAtlasMaterial,
)


def register():
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)

    for prop_name in (
        "rzm_qa_autoatlas_vertex_margin_px",
        "rzm_qa_autoatlas_pack_gap_px",
    ):
        if hasattr(bpy.types.WindowManager, prop_name):
            try:
                delattr(bpy.types.WindowManager, prop_name)
            except Exception:
                pass

    bpy.types.WindowManager.rzm_qa_autoatlas_vertex_margin_px = bpy.props.IntProperty(
        name="RZAutoAtlas Island Margin",
        description="Extra pixel gutter around packed UV islands, also used for color dilation",
        default=AUTO_ATLAS_VERTEX_MARGIN_DEFAULT,
        min=0,
        max=128,
    )
    bpy.types.WindowManager.rzm_qa_autoatlas_pack_gap_px = bpy.props.IntProperty(
        name="RZAutoAtlas Pack Gap",
        description="Extra spacing between packed island groups",
        default=AUTO_ATLAS_DEFAULT_PADDING,
        min=0,
        max=512,
    )

    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)

    for prop_name in (
        "rzm_qa_autoatlas_vertex_margin_px",
        "rzm_qa_autoatlas_pack_gap_px",
    ):
        if hasattr(bpy.types.WindowManager, prop_name):
            try:
                delattr(bpy.types.WindowManager, prop_name)
            except Exception:
                pass


if __name__ == "__main__":
    register()
    print("RZM QA TexWorks Atlas Material Hub v2.0.1 registered.")
