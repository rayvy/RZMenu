import json
import math
import os
import re
import struct
import time
import zlib
from array import array

import bpy

from . import TWAA_CORE as twaa_core

try:
    import numpy as np
except Exception:
    np = None


GROUP_NAME = "RZM TexWorks Material"
RESOURCE_PREFIX = "RZAutoAtlas"
OUTPUT_SUBDIR = "Textures/DynAtlas"
UV_NAME = "RZAutoAtlas.UV"
PREVIEW_UV_NAME = "RZAutoAtlas.UV.preview"
PREVIEW_UV_PREFIX = "TWAA."
TEXCOORD_UV_NAME = "TEXCOORD.xy"
SCHEMA = 3
KIND = "RZ_TEXWORKS_MC_MATERIAL"
ROLE = "SEMANTIC_TEXTURE_HUB"
DEFAULT_MAX_RASTER_PIXELS = 16 * 1024 * 1024

SLOTS = ("Diffuse", "LightMap", "MaterialMap", "NormalMap", "Extra")
SLOT_FILE_SUFFIX = {
    "Diffuse": "Diffuse",
    "LightMap": "LightMap",
    "MaterialMap": "MaterialMap",
    "NormalMap": "NormalMap",
    "Extra": "ExtraMap",
}
SLOT_DEFAULTS = {
    "Diffuse": (1.0, 1.0, 1.0, 1.0),
    "LightMap": (0.0, 0.0, 0.0, 1.0),
    "MaterialMap": (0.0, 0.5, 0.0, 1.0),
    "NormalMap": (0.5, 0.5, 1.0, 1.0),
    "Extra": (0.0, 0.0, 0.0, 1.0),
}
SLOT_COLORSPACES = {
    "Diffuse": "sRGB",
    "LightMap": "Non-Color",
    "MaterialMap": "Non-Color",
    "NormalMap": "Non-Color",
    "Extra": "Non-Color",
}


def material_key(name):
    key = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip())
    key = key.strip("_")
    return key or "Material"


def preview_uv_name_for_material(mat_or_name):
    name = getattr(mat_or_name, "name", mat_or_name)
    return f"{PREVIEW_UV_PREFIX}{material_key(str(name or 'Material'))}"


def slot_file_suffix(slot):
    return SLOT_FILE_SUFFIX.get(slot, slot)


def autoatlas_block_name(slot):
    return f"{RESOURCE_PREFIX}{slot_file_suffix(slot)}"


def cluster_file_stem(mat_name, slot):
    return f"{material_key(mat_name)}{slot_file_suffix(slot)}"


def round_up_to_multiple(value, multiple=16):
    value = max(1, int(math.ceil(value)))
    multiple = max(1, int(multiple))
    return ((value + multiple - 1) // multiple) * multiple


def clamp01(value):
    return max(0.0, min(1.0, float(value)))


def get_settings(context):
    rzm = context.scene.rzm
    settings = getattr(rzm, "tw_mc", None)
    if not settings:
        raise RuntimeError("TexWorks MC settings are not registered")
    return settings


def get_active_material(context):
    obj = context.object
    if not obj or obj.type != "MESH":
        raise RuntimeError("Select a mesh object with an active material")
    mat = obj.active_material
    if not mat:
        raise RuntimeError("Active mesh has no active material")
    return mat


def find_material_group_node(mat):
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None
    for node in mat.node_tree.nodes:
        if node.bl_idname == "ShaderNodeGroup" and node.node_tree and node.node_tree.name == GROUP_NAME:
            return node
    return None


def iter_material_group_nodes(group=None):
    for mat in bpy.data.materials:
        if not mat or not mat.use_nodes or not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname != "ShaderNodeGroup":
                continue
            if group is not None and node.node_tree != group:
                continue
            if group is None and (not node.node_tree or node.node_tree.name != GROUP_NAME):
                continue
            yield mat, node


def _socket_value_copy(socket):
    value = getattr(socket, "default_value", None)
    if value is None:
        return None
    try:
        return tuple(value)
    except TypeError:
        try:
            return value.copy()
        except Exception:
            return value


def _set_socket_value(socket, value):
    if value is None or socket is None:
        return
    try:
        socket.default_value = value
    except Exception:
        try:
            for index, item in enumerate(value):
                socket.default_value[index] = item
        except Exception:
            pass


def snapshot_material_group_bindings(group):
    snapshots = []
    for mat, node in iter_material_group_nodes(group):
        tree = mat.node_tree
        inputs = {}
        outputs = {}
        for socket in node.inputs:
            data = {"default": _socket_value_copy(socket), "links": []}
            for link in socket.links:
                data["links"].append({
                    "from_node": link.from_node.name,
                    "from_socket": link.from_socket.name,
                    "to_socket": socket.name,
                })
            inputs[socket.name] = data
        for socket in node.outputs:
            data = {"links": []}
            for link in socket.links:
                data["links"].append({
                    "from_socket": socket.name,
                    "to_node": link.to_node.name,
                    "to_socket": link.to_socket.name,
                })
            outputs[socket.name] = data
        snapshots.append({
            "material": mat.name,
            "node": node.name,
            "inputs": inputs,
            "outputs": outputs,
        })
    return snapshots


def restore_material_group_bindings(snapshots):
    restored_links = 0
    for snapshot in snapshots or []:
        mat = bpy.data.materials.get(snapshot.get("material", ""))
        if not mat or not mat.use_nodes or not mat.node_tree:
            continue
        tree = mat.node_tree
        node = tree.nodes.get(snapshot.get("node", ""))
        if not node or node.bl_idname != "ShaderNodeGroup":
            continue

        for socket_name, data in snapshot.get("inputs", {}).items():
            socket = node.inputs.get(socket_name)
            if not socket:
                continue
            _set_socket_value(socket, data.get("default"))
            for link_data in data.get("links", []):
                from_node = tree.nodes.get(link_data.get("from_node", ""))
                from_socket = from_node.outputs.get(link_data.get("from_socket", "")) if from_node else None
                if not from_socket or socket.is_linked:
                    continue
                try:
                    tree.links.new(from_socket, socket)
                    restored_links += 1
                except Exception:
                    pass

        for socket_name, data in snapshot.get("outputs", {}).items():
            socket = node.outputs.get(socket_name)
            if not socket:
                continue
            for link_data in data.get("links", []):
                to_node = tree.nodes.get(link_data.get("to_node", ""))
                to_socket = to_node.inputs.get(link_data.get("to_socket", "")) if to_node else None
                if not to_socket:
                    continue
                if any(link.from_socket == socket and link.to_socket == to_socket for link in tree.links):
                    continue
                try:
                    tree.links.new(socket, to_socket)
                    restored_links += 1
                except Exception:
                    pass
    return restored_links


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


def build_material_group_nodes(group):
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


def make_or_update_material_group(force=False):
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
        snapshots = snapshot_material_group_bindings(group)
        clear_group(group)
        for name in SLOTS:
            add_socket(group, name, "INPUT", "NodeSocketColor", SLOT_DEFAULTS.get(name, (0.0, 0.0, 0.0, 1.0)))

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
        add_socket(group, "Default Resolution X", "INPUT", "NodeSocketInt", 512)
        add_socket(group, "Default Resolution Y", "INPUT", "NodeSocketInt", 512)

        add_socket(group, "Diffuse Color Space", "INPUT", "NodeSocketInt", 0)
        add_socket(group, "LightMap Color Space", "INPUT", "NodeSocketInt", 1)
        add_socket(group, "MaterialMap Color Space", "INPUT", "NodeSocketInt", 1)
        add_socket(group, "NormalMap Color Space", "INPUT", "NodeSocketInt", 1)
        add_socket(group, "Extra Color Space", "INPUT", "NodeSocketInt", 1)

        add_socket(group, "Base Color", "OUTPUT", "NodeSocketColor")
        for name in SLOTS:
            add_socket(group, name, "OUTPUT", "NodeSocketColor")
        add_socket(group, "Emission Strength", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Metallic", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Roughness", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Ambient Occlusion", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Alpha", "OUTPUT", "NodeSocketFloat")
        add_socket(group, "Preview Normal", "OUTPUT", "NodeSocketColor")
        add_socket(group, "RenderOutput", "OUTPUT", "NodeSocketShader")
        build_material_group_nodes(group)
        restored = restore_material_group_bindings(snapshots)
        if restored:
            print(f"[RZM TexWorks MC] Restored {restored} material node link(s) after schema rebuild.")

    group["rzm_texworks_schema"] = SCHEMA
    group["rzm_texworks_kind"] = KIND
    group["rzm_texworks_role"] = ROLE
    return group


def set_material_node_default_resolution(group_node, resolution, force=False):
    if not group_node:
        return
    try:
        width = max(1, int(resolution[0]))
        height = max(1, int(resolution[1]))
    except Exception:
        width, height = 512, 512
    for socket_name, value in (("Default Resolution X", width), ("Default Resolution Y", height)):
        socket = group_node.inputs.get(socket_name)
        if not socket:
            continue
        try:
            if force or int(socket.default_value) <= 0:
                socket.default_value = value
        except Exception:
            try:
                socket.default_value = value
            except Exception:
                pass


def material_node_default_resolution(mat, settings=None):
    group_node = find_material_group_node(mat)
    if group_node:
        try:
            width = int(group_node.inputs["Default Resolution X"].default_value)
            height = int(group_node.inputs["Default Resolution Y"].default_value)
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass
    if settings:
        try:
            return max(1, int(settings.default_resolution[0])), max(1, int(settings.default_resolution[1]))
        except Exception:
            pass
    return 512, 512


def add_group_instance(mat, group):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    node = nodes.new("ShaderNodeGroup")
    node.node_tree = group
    node.name = GROUP_NAME
    node.label = GROUP_NAME
    if nodes:
        node.location.x = max(n.location.x for n in nodes) + 300
        node.location.y = max((n.location.y for n in nodes), default=0) + 40
    return node


def classify_texture_node(node):
    image = getattr(node, "image", None)
    text = " ".join(
        str(part or "").lower()
        for part in (
            getattr(node, "name", ""),
            getattr(node, "label", ""),
            getattr(image, "name", "") if image else "",
            getattr(image, "filepath", "") if image else "",
        )
    )
    aliases = {
        "LightMap": ("lightmap", "light_map", "light map", "_lm", "-lm"),
        "MaterialMap": ("materialmap", "material_map", "material map", "_mm", "-mm", "matmap"),
        "NormalMap": ("normalmap", "normal_map", "normal map", "_n", "-n", "norm"),
        "Extra": ("extra", "extramap", "extra_map", "extra map"),
        "Diffuse": ("diffuse", "basecolor", "base_color", "base color", "albedo", "_d", "-d", "color"),
    }
    for slot, keys in aliases.items():
        if any(key in text for key in keys):
            return slot
    return None


def texture_nodes_by_slot(mat):
    result = {slot: [] for slot in SLOTS}
    if not mat or not mat.use_nodes or not mat.node_tree:
        return result
    unclassified = []
    for node in mat.node_tree.nodes:
        if node.bl_idname != "ShaderNodeTexImage" or not node.image:
            continue
        slot = classify_texture_node(node)
        if slot:
            result[slot].append(node)
        else:
            unclassified.append(node)
    if not result["Diffuse"] and len(unclassified) == 1:
        result["Diffuse"].append(unclassified[0])
    return result


def link_auto_texture_nodes(mat, group_node):
    by_slot = texture_nodes_by_slot(mat)
    linked = []
    for slot, nodes in by_slot.items():
        if not nodes or slot not in group_node.inputs:
            continue
        input_socket = group_node.inputs[slot]
        if input_socket.is_linked:
            continue
        for link in list(input_socket.links):
            mat.node_tree.links.remove(link)
        mat.node_tree.links.new(nodes[0].outputs["Color"], input_socket)
        nodes[0].location = (group_node.location.x - 430, group_node.location.y + SLOTS.index(slot) * -260)
        linked.append(slot)

        flag_name = f"Has {slot}"
        if flag_name in group_node.inputs:
            try:
                group_node.inputs[flag_name].default_value = True
            except Exception:
                pass
    return linked


def sync_diffuse_default_from_material(mat, group_node):
    if not group_node or "Diffuse" not in group_node.inputs:
        return
    socket = group_node.inputs["Diffuse"]
    if socket.is_linked:
        return
    color = material_principled_base_color(mat)
    mat_color = tuple(float(c) for c in getattr(mat, "diffuse_color", (1.0, 1.0, 1.0, 1.0)))
    if color is None or is_black_color(color):
        color = mat_color
    try:
        socket.default_value = color
    except Exception:
        pass


def ensure_material_node(mat, rebuild_group=False, connect_surface=False):
    if not mat:
        raise RuntimeError("No active material")
    existing_node = find_material_group_node(mat)
    had_resolution_inputs = bool(
        existing_node
        and "Default Resolution X" in existing_node.inputs
        and "Default Resolution Y" in existing_node.inputs
    )
    group = make_or_update_material_group(force=rebuild_group)
    mat.use_nodes = True
    node = find_material_group_node(mat)
    created_node = False
    if not node:
        node = add_group_instance(mat, group)
        created_node = True
    set_material_node_default_resolution(
        node,
        get_settings(bpy.context).default_resolution,
        force=created_node or not had_resolution_inputs,
    )
    link_auto_texture_nodes(mat, node)
    sync_diffuse_default_from_material(mat, node)
    if connect_surface and "RenderOutput" in node.outputs:
        outputs = [n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
        out = outputs[0] if outputs else mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        out.location = (node.location.x + 520, node.location.y)
        mat.node_tree.links.new(node.outputs["RenderOutput"], out.inputs["Surface"])
    return node


def create_empty_material(context, assign=True):
    settings = get_settings(context)
    group = make_or_update_material_group()
    mat = bpy.data.materials.new("RZM AutoAtlas Material")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    hub = add_group_instance(mat, group)
    set_material_node_default_resolution(hub, settings.default_resolution, force=True)
    hub.location = (-320, 80)
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (260, 80)
    mat.node_tree.links.new(hub.outputs["RenderOutput"], out.inputs["Surface"])
    if assign and context.object and hasattr(context.object.data, "materials"):
        obj = context.object
        materials = obj.data.materials
        active_index = int(getattr(obj, "active_material_index", 0) or 0)
        if len(materials) == 0:
            materials.append(mat)
            obj.active_material_index = 0
        elif 0 <= active_index < len(materials) and materials[active_index] is None:
            materials[active_index] = mat
        else:
            materials.append(mat)
            obj.active_material_index = len(materials) - 1
    return mat


def socket_default_color(socket, fallback):
    if not socket:
        return fallback
    value = getattr(socket, "default_value", None)
    if value is None:
        return fallback
    try:
        if len(value) >= 4:
            return tuple(float(value[i]) for i in range(4))
        if len(value) == 3:
            return (float(value[0]), float(value[1]), float(value[2]), 1.0)
    except Exception:
        pass
    return fallback


def socket_default_bool(socket, fallback=False):
    if not socket:
        return fallback
    try:
        return bool(socket.default_value)
    except Exception:
        return fallback


def material_principled_base_color(mat):
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None
    for node in mat.node_tree.nodes:
        if node.bl_idname != "ShaderNodeBsdfPrincipled":
            continue
        socket = node.inputs.get("Base Color")
        image = find_upstream_image(socket)
        if image:
            continue
        color = socket_default_color(socket, None)
        if color is not None:
            return color
    return None


def is_black_color(color):
    try:
        return float(color[0]) <= 0.0001 and float(color[1]) <= 0.0001 and float(color[2]) <= 0.0001
    except Exception:
        return False


def find_upstream_image(socket, visited=None):
    if visited is None:
        visited = set()
    if not socket or not socket.is_linked:
        return None

    for link in socket.links:
        node = link.from_node
        if not node or node.as_pointer() in visited:
            continue
        visited.add(node.as_pointer())
        if node.bl_idname == "ShaderNodeTexImage" and node.image:
            return node.image
        for input_socket in getattr(node, "inputs", []):
            image = find_upstream_image(input_socket, visited)
            if image:
                return image
    return None


def material_slot_source(mat, slot):
    group = find_material_group_node(mat)
    input_socket = group.inputs.get(slot) if group else None
    flag_socket = group.inputs.get(f"Has {slot}") if group else None

    image = find_upstream_image(input_socket)
    procedural = bool(input_socket and input_socket.is_linked and not image)
    color = socket_default_color(input_socket, SLOT_DEFAULTS.get(slot, (0.0, 0.0, 0.0, 1.0)))
    if slot == "Diffuse" and not image:
        principled_color = material_principled_base_color(mat)
        mat_color = tuple(float(c) for c in getattr(mat, "diffuse_color", color))
        if is_black_color(color) and principled_color is not None and not is_black_color(principled_color):
            color = principled_color
        if is_black_color(color) and not is_black_color(mat_color):
            color = mat_color

    enabled = True if slot == "Diffuse" else bool(image) or procedural or socket_default_bool(flag_socket, False)
    return {
        "slot": slot,
        "enabled": enabled,
        "image": image,
        "procedural": procedural,
        "solid_color": color,
        "has_flag": socket_default_bool(flag_socket, False),
    }


def collect_slot_sources(mat):
    return {slot: material_slot_source(mat, slot) for slot in SLOTS}


def choose_reference_size(settings, slot_sources, mat=None):
    order = []
    if settings.reference_slot != "AUTO":
        order.append(settings.reference_slot)
    else:
        order.extend(("Diffuse", "LightMap", "MaterialMap", "NormalMap", "Extra"))

    for slot in order:
        source = slot_sources.get(slot)
        image = source.get("image") if source else None
        if image and image.size[0] > 0 and image.size[1] > 0:
            return int(image.size[0]), int(image.size[1]), slot

    width, height = material_node_default_resolution(mat, settings)
    return int(width), int(height), "fallback"


def material_slot_indices(obj, mat):
    indices = []
    for idx, slot in enumerate(obj.material_slots):
        if slot.material == mat:
            indices.append(idx)
    return set(indices)


def source_uv_layer_for_mesh(mesh):
    uv = mesh.uv_layers.get(TEXCOORD_UV_NAME)
    if uv and not is_twaa_preview_uv_name(uv.name):
        return uv
    for layer in mesh.uv_layers:
        if not is_twaa_preview_uv_name(layer.name):
            layer.name = TEXCOORD_UV_NAME
            return layer
    try:
        return mesh.uv_layers.new(name=TEXCOORD_UV_NAME)
    except Exception:
        return None


def is_twaa_preview_uv_name(name):
    return bool(name == PREVIEW_UV_NAME or str(name).startswith(PREVIEW_UV_PREFIX))


def preview_uv_layer_for_mesh(mesh, mat=None):
    source = source_uv_layer_for_mesh(mesh)
    preview_name = preview_uv_name_for_material(mat) if mat else PREVIEW_UV_NAME
    preview = mesh.uv_layers.get(preview_name)
    if preview is None:
        preview = mesh.uv_layers.new(name=preview_name)
    if source is None:
        return preview

    src_data = source.data
    dst_data = preview.data
    count = min(len(src_data), len(dst_data))
    for i in range(count):
        dst_data[i].uv = src_data[i].uv
    try:
        preview.active = True
    except Exception:
        pass
    try:
        preview.active_render = True
    except Exception:
        pass
    return preview


def mesh_has_preview_uv(mesh):
    return bool(mesh and any(is_twaa_preview_uv_name(layer.name) for layer in mesh.uv_layers))


def mesh_has_material_preview_uv(mesh, mat):
    return bool(mesh and mesh.uv_layers.get(preview_uv_name_for_material(mat)))


def active_material_has_preview_uv(context):
    try:
        mat = get_active_material(context)
    except Exception:
        return False
    for obj in context.scene.objects:
        if obj.type != "MESH":
            continue
        if material_slot_indices(obj, mat) and mesh_has_material_preview_uv(obj.data, mat):
            return True
    return False


def collect_cluster_faces(context, mat):
    objects = []
    faces = []
    warnings = []

    for obj in context.scene.objects:
        if obj.type != "MESH":
            continue
        mat_indices = material_slot_indices(obj, mat)
        if not mat_indices:
            continue
        mesh = obj.data
        uv_layer = source_uv_layer_for_mesh(mesh)
        if not uv_layer:
            warnings.append(f"{obj.name}: no UV layer, skipped")
            continue
        obj_face_count = 0
        for poly in mesh.polygons:
            if poly.material_index not in mat_indices:
                continue
            uvs = []
            for loop_index in poly.loop_indices:
                uv = uv_layer.data[loop_index].uv
                uvs.append((float(uv.x), float(uv.y)))
            if len(uvs) < 3:
                continue
            faces.append({
                "object": obj.name,
                "mesh": mesh.name,
                "poly_index": int(poly.index),
                "material_index": int(poly.material_index),
                "loop_indices": [int(i) for i in poly.loop_indices],
                "uvs": uvs,
                "source_uvs": list(uvs),
                "uv_layer_name": uv_layer.name,
                "surface_area": float(poly.area) * abs(float(obj.scale.x * obj.scale.y * obj.scale.z)) ** (2.0 / 3.0),
            })
            obj_face_count += 1
        if obj_face_count:
            objects.append(obj.name)

    return faces, sorted(set(objects)), warnings


def collect_preview_cluster_faces(context, mat):
    objects = []
    faces = []
    warnings = []

    for obj in context.scene.objects:
        if obj.type != "MESH":
            continue
        mat_indices = material_slot_indices(obj, mat)
        if not mat_indices:
            continue
        mesh = obj.data
        source_layer = source_uv_layer_for_mesh(mesh)
        preview_name = preview_uv_name_for_material(mat)
        preview_layer = mesh.uv_layers.get(preview_name)
        if not source_layer:
            warnings.append(f"{obj.name}: no source UV layer, skipped")
            continue
        if not preview_layer:
            warnings.append(f"{obj.name}: no preview UV layer {preview_name}, skipped")
            continue
        obj_face_count = 0
        for poly in mesh.polygons:
            if poly.material_index not in mat_indices:
                continue
            source_uvs = []
            preview_uvs = []
            for loop_index in poly.loop_indices:
                suv = source_layer.data[loop_index].uv
                duv = preview_layer.data[loop_index].uv
                source_uvs.append((float(suv.x), float(suv.y)))
                preview_uvs.append((float(duv.x), float(duv.y)))
            if len(preview_uvs) < 3:
                continue
            faces.append({
                "object": obj.name,
                "mesh": mesh.name,
                "poly_index": int(poly.index),
                "material_index": int(poly.material_index),
                "loop_indices": [int(i) for i in poly.loop_indices],
                "uvs": preview_uvs,
                "source_uvs": source_uvs,
                "uv_layer_name": source_layer.name,
                "preview_uv_layer_name": preview_layer.name,
                "surface_area": float(poly.area) * abs(float(obj.scale.x * obj.scale.y * obj.scale.z)) ** (2.0 / 3.0),
            })
            obj_face_count += 1
        if obj_face_count:
            objects.append(obj.name)

    return faces, sorted(set(objects)), warnings


# UV island grouping and rectangle packing live in TWAA_CORE.py. This module keeps Blender IO only.

def image_pixels(image):
    if not image:
        return None, 1, 1
    try:
        width = int(image.size[0])
        height = int(image.size[1])
        if getattr(image, "filepath", "") and not image.packed_file:
            try:
                image.reload()
            except Exception:
                pass
        pixels = array("f", [0.0]) * (width * height * 4)
        image.pixels.foreach_get(pixels)
        if width <= 0 or height <= 0 or not pixels:
            return None, 1, 1
        return pixels, width, height
    except Exception:
        return None, 1, 1


def sample_bilinear(pixels, width, height, u, v, fallback):
    if not pixels:
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
    return tuple(out)


def sample_bilinear_np(src, width, height, u, v):
    u = np.clip(u, 0.0, 1.0)
    v = np.clip(v, 0.0, 1.0)
    x = u * (width - 1)
    y = v * (height - 1)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(width - 1, x0 + 1)
    y1 = np.minimum(height - 1, y0 + 1)
    tx = (x - x0).astype(np.float32)[:, None]
    ty = (y - y0).astype(np.float32)[:, None]

    c00 = src[y0, x0]
    c10 = src[y0, x1]
    c01 = src[y1, x0]
    c11 = src[y1, x1]
    a = c00 * (1.0 - tx) + c10 * tx
    b = c01 * (1.0 - tx) + c11 * tx
    return a * (1.0 - ty) + b * ty


def barycentric(px, py, a, b, c):
    denom = ((b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]))
    if abs(denom) < 1.0e-8:
        return None
    w0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / denom
    w1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / denom
    w2 = 1.0 - w0 - w1
    if w0 < -1.0e-5 or w1 < -1.0e-5 or w2 < -1.0e-5:
        return None
    return w0, w1, w2


def face_triangles(uvs):
    for i in range(1, len(uvs) - 1):
        yield uvs[0], uvs[i], uvs[i + 1]


def dest_uv_to_pixel(uv, group, ref_w, ref_h, margin):
    x = group["x"] + margin + (uv[0] - group["u_min"]) * ref_w
    y = group["y"] + margin + (group["v_max"] - uv[1]) * ref_h
    return x, y


def write_pixel(buffer, width, height, x, y, color):
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    idx = (int(y) * width + int(x)) * 4
    buffer[idx] = color[0]
    buffer[idx + 1] = color[1]
    buffer[idx + 2] = color[2]
    buffer[idx + 3] = color[3]


def solid_pixel_buffer(width, height, color):
    px_count = int(width) * int(height)
    r, g, b, a = (float(color[0]), float(color[1]), float(color[2]), float(color[3]))
    data = array("f", [0.0]) * (px_count * 4)
    data[0::4] = array("f", [r]) * px_count
    data[1::4] = array("f", [g]) * px_count
    data[2::4] = array("f", [b]) * px_count
    data[3::4] = array("f", [a]) * px_count
    return data


def dilate_alpha(buffer, width, height, radius):
    if radius <= 0:
        return buffer
    radius = min(int(radius), 16)
    if np is not None:
        try:
            arr = np.frombuffer(buffer, dtype=np.float32).reshape(int(height), int(width), 4)
            for _ in range(radius):
                src = arr.copy()
                empty = src[:, :, 3] <= 0.0
                if not empty.any():
                    break

                fill = np.zeros(empty.shape, dtype=bool)
                fill[:, 1:] = empty[:, 1:] & (src[:, :-1, 3] > 0.0)
                arr[:, 1:][fill[:, 1:]] = src[:, :-1][fill[:, 1:]]

                empty = arr[:, :, 3] <= 0.0
                fill[:, :] = False
                fill[:, :-1] = empty[:, :-1] & (src[:, 1:, 3] > 0.0)
                arr[:, :-1][fill[:, :-1]] = src[:, 1:][fill[:, :-1]]

                empty = arr[:, :, 3] <= 0.0
                fill[:, :] = False
                fill[1:, :] = empty[1:, :] & (src[:-1, :, 3] > 0.0)
                arr[1:, :][fill[1:, :]] = src[:-1, :][fill[1:, :]]

                empty = arr[:, :, 3] <= 0.0
                fill[:, :] = False
                fill[:-1, :] = empty[:-1, :] & (src[1:, :, 3] > 0.0)
                arr[:-1, :][fill[:-1, :]] = src[1:, :][fill[:-1, :]]
            return buffer
        except Exception as exc:
            print(f"[RZM TexWorks MC] NumPy dilation fallback: {exc}")

    for _ in range(radius):
        src = list(buffer)
        changed = False
        for y in range(height):
            row = y * width
            for x in range(width):
                idx = (row + x) * 4
                if src[idx + 3] > 0.0:
                    continue
                neighbor = None
                if x > 0:
                    nidx = idx - 4
                    if src[nidx + 3] > 0.0:
                        neighbor = src[nidx:nidx + 4]
                if neighbor is None and x + 1 < width:
                    nidx = idx + 4
                    if src[nidx + 3] > 0.0:
                        neighbor = src[nidx:nidx + 4]
                if neighbor is None and y > 0:
                    nidx = idx - width * 4
                    if src[nidx + 3] > 0.0:
                        neighbor = src[nidx:nidx + 4]
                if neighbor is None and y + 1 < height:
                    nidx = idx + width * 4
                    if src[nidx + 3] > 0.0:
                        neighbor = src[nidx:nidx + 4]
                if neighbor:
                    buffer[idx] = neighbor[0]
                    buffer[idx + 1] = neighbor[1]
                    buffer[idx + 2] = neighbor[2]
                    buffer[idx + 3] = neighbor[3]
                    changed = True
        if not changed:
            break
    return buffer


def bake_slot_image(slot, source, faces, face_to_group, layout_groups, atlas_w, atlas_h, ref_w, ref_h, margin, max_raster_pixels=DEFAULT_MAX_RASTER_PIXELS):
    group_by_index = {group["index"]: group for group in layout_groups}
    src_pixels, src_w, src_h = image_pixels(source.get("image"))
    fallback = source.get("solid_color") or SLOT_DEFAULTS.get(slot, (0.0, 0.0, 0.0, 1.0))
    pixel_count = int(atlas_w) * int(atlas_h)
    if pixel_count > max_raster_pixels:
        raise RuntimeError(
            f"Generated cluster atlas is too large for CPU bake: {atlas_w}x{atlas_h} "
            f"({pixel_count:,} pixels, limit {max_raster_pixels:,}). "
            "Check UV range, lower TexWorks MC Max Size, or increase Max Raster Pixels."
        )
    if not src_pixels:
        return solid_pixel_buffer(atlas_w, atlas_h, fallback)

    src_avg = pixel_average_rgba(src_pixels, sample_step=256)
    if slot == "Diffuse" and max(src_avg) <= 0.001 and not is_black_color(fallback):
        return solid_pixel_buffer(atlas_w, atlas_h, fallback)

    if np is not None:
        try:
            return bake_slot_image_numpy(
                slot,
                source,
                faces,
                face_to_group,
                layout_groups,
                atlas_w,
                atlas_h,
                ref_w,
                ref_h,
                margin,
                src_pixels,
                src_w,
                src_h,
                fallback,
            )
        except Exception as exc:
            print(f"[RZM TexWorks MC] NumPy raster fallback: {exc}")

    buffer = array("f", [0.0]) * (pixel_count * 4)

    for face_index, face in enumerate(faces):
        base_group = face_to_group.get(face_index)
        if not base_group:
            continue
        group = group_by_index.get(base_group["index"])
        if not group:
            continue
        src_triangles = list(face_triangles(face.get("source_uvs") or face["uvs"]))
        for tri_index, (uv_a, uv_b, uv_c) in enumerate(face_triangles(face["uvs"])):
            src_a, src_b, src_c = src_triangles[tri_index] if tri_index < len(src_triangles) else (uv_a, uv_b, uv_c)
            pa = dest_uv_to_pixel(uv_a, group, ref_w, ref_h, margin)
            pb = dest_uv_to_pixel(uv_b, group, ref_w, ref_h, margin)
            pc = dest_uv_to_pixel(uv_c, group, ref_w, ref_h, margin)
            min_x = max(0, int(math.floor(min(pa[0], pb[0], pc[0]))) - margin)
            max_x = min(atlas_w - 1, int(math.ceil(max(pa[0], pb[0], pc[0]))) + margin)
            min_y = max(0, int(math.floor(min(pa[1], pb[1], pc[1]))) - margin)
            max_y = min(atlas_h - 1, int(math.ceil(max(pa[1], pb[1], pc[1]))) + margin)
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    bc = barycentric(x + 0.5, y + 0.5, pa, pb, pc)
                    if bc is None:
                        continue
                    w0, w1, w2 = bc
                    src_u = src_a[0] * w0 + src_b[0] * w1 + src_c[0] * w2
                    src_v = src_a[1] * w0 + src_b[1] * w1 + src_c[1] * w2
                    color = sample_bilinear(src_pixels, src_w, src_h, src_u, src_v, fallback)
                    write_pixel(buffer, atlas_w, atlas_h, x, y, color)

    return dilate_alpha(buffer, atlas_w, atlas_h, margin)


def bake_slot_image_numpy(slot, source, faces, face_to_group, layout_groups, atlas_w, atlas_h, ref_w, ref_h, margin, src_pixels, src_w, src_h, fallback):
    group_by_index = {group["index"]: group for group in layout_groups}
    pixel_count = int(atlas_w) * int(atlas_h)
    buffer = array("f", [0.0]) * (pixel_count * 4)
    dest = np.frombuffer(buffer, dtype=np.float32).reshape(int(atlas_h), int(atlas_w), 4)
    src = np.frombuffer(src_pixels, dtype=np.float32).reshape(int(src_h), int(src_w), 4)

    for face_index, face in enumerate(faces):
        base_group = face_to_group.get(face_index)
        if not base_group:
            continue
        group = group_by_index.get(base_group["index"])
        if not group:
            continue
        src_triangles = list(face_triangles(face.get("source_uvs") or face["uvs"]))
        for tri_index, (uv_a, uv_b, uv_c) in enumerate(face_triangles(face["uvs"])):
            src_a, src_b, src_c = src_triangles[tri_index] if tri_index < len(src_triangles) else (uv_a, uv_b, uv_c)
            pa = dest_uv_to_pixel(uv_a, group, ref_w, ref_h, margin)
            pb = dest_uv_to_pixel(uv_b, group, ref_w, ref_h, margin)
            pc = dest_uv_to_pixel(uv_c, group, ref_w, ref_h, margin)
            min_x = max(0, int(math.floor(min(pa[0], pb[0], pc[0]))) - margin)
            max_x = min(int(atlas_w) - 1, int(math.ceil(max(pa[0], pb[0], pc[0]))) + margin)
            min_y = max(0, int(math.floor(min(pa[1], pb[1], pc[1]))) - margin)
            max_y = min(int(atlas_h) - 1, int(math.ceil(max(pa[1], pb[1], pc[1]))) + margin)
            if max_x < min_x or max_y < min_y:
                continue

            denom = ((pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1]))
            if abs(denom) < 1.0e-8:
                continue

            xs = np.arange(min_x, max_x + 1, dtype=np.float32) + 0.5
            bbox_w = max_x - min_x + 1
            max_cells = 1024 * 1024
            rows_per_chunk = max(1, min(max_y - min_y + 1, max_cells // max(1, bbox_w)))

            for y_start in range(min_y, max_y + 1, rows_per_chunk):
                y_end = min(max_y, y_start + rows_per_chunk - 1)
                ys = np.arange(y_start, y_end + 1, dtype=np.float32) + 0.5
                grid_x, grid_y = np.meshgrid(xs, ys)
                w0 = ((pb[1] - pc[1]) * (grid_x - pc[0]) + (pc[0] - pb[0]) * (grid_y - pc[1])) / denom
                w1 = ((pc[1] - pa[1]) * (grid_x - pc[0]) + (pa[0] - pc[0]) * (grid_y - pc[1])) / denom
                w2 = 1.0 - w0 - w1
                mask = (w0 >= -1.0e-5) & (w1 >= -1.0e-5) & (w2 >= -1.0e-5)
                if not mask.any():
                    continue

                src_u = src_a[0] * w0[mask] + src_b[0] * w1[mask] + src_c[0] * w2[mask]
                src_v = src_a[1] * w0[mask] + src_b[1] * w1[mask] + src_c[1] * w2[mask]
                colors = sample_bilinear_np(src, int(src_w), int(src_h), src_u.astype(np.float32), src_v.astype(np.float32))
                dest_slice = dest[y_start:y_end + 1, min_x:max_x + 1]
                dest_slice[mask] = colors

    return dilate_alpha(buffer, atlas_w, atlas_h, margin)


def create_or_replace_image(name, width, height, pixels):
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    image = bpy.data.images.new(name=name, width=width, height=height, alpha=True, float_buffer=False)
    image.pixels.foreach_set(pixels)
    image.update()
    return image


def write_png_rgba8(path, width, height, pixels):
    width = int(width)
    height = int(height)
    if np is not None:
        try:
            floats = np.frombuffer(pixels, dtype=np.float32, count=width * height * 4)
            rgba = np.clip(floats * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8, copy=False)
            rows = np.empty((height, width * 4 + 1), dtype=np.uint8)
            rows[:, 0] = 0
            rows[:, 1:] = rgba.reshape(height, width * 4)

            def chunk(kind, payload):
                return (
                    struct.pack(">I", len(payload))
                    + kind
                    + payload
                    + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
                )

            ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
            data = (
                b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(rows.tobytes(), level=1))
                + chunk(b"IEND", b"")
            )
            with open(path, "wb") as handle:
                handle.write(data)
            return
        except Exception as exc:
            print(f"[RZM TexWorks MC] NumPy PNG writer fallback: {exc}")

    rows = []
    idx = 0
    for _y in range(height):
        row = bytearray()
        row.append(0)
        for _x in range(width):
            row.append(max(0, min(255, int(round(float(pixels[idx]) * 255.0)))))
            row.append(max(0, min(255, int(round(float(pixels[idx + 1]) * 255.0)))))
            row.append(max(0, min(255, int(round(float(pixels[idx + 2]) * 255.0)))))
            row.append(max(0, min(255, int(round(float(pixels[idx + 3]) * 255.0)))))
            idx += 4
        rows.append(bytes(row))

    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(rows)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, level=1))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as handle:
        handle.write(data)


def pixel_average_rgba(pixels, sample_step=64):
    if not pixels:
        return (0.0, 0.0, 0.0, 0.0)
    r = g = b = a = 0.0
    count = 0
    stride = max(4, int(sample_step) * 4)
    for idx in range(0, len(pixels), stride):
        r += float(pixels[idx])
        g += float(pixels[idx + 1])
        b += float(pixels[idx + 2])
        a += float(pixels[idx + 3])
        count += 1
    if count <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    return (r / count, g / count, b / count, a / count)


def set_image_colorspace(image, slot):
    if not image:
        return
    colorspace = SLOT_COLORSPACES.get(slot, "sRGB")
    try:
        image.colorspace_settings.name = colorspace
    except Exception:
        pass


def manifest_rect(settings, atlas_h, x, y, w, h):
    x = int(x)
    y = int(y)
    w = int(w)
    h = int(h)
    if settings.y_origin == "UV_BOTTOM_LEFT":
        y = int(atlas_h) - y - h
    return [x, y, w, h]


def build_manifest(context, mat, slot_sources, objects, faces, islands, groups, layout_groups, atlas_w, atlas_h, ref_size, ref_slot, warnings):
    settings = get_settings(context)
    key = material_key(mat.name)
    active_slots = [slot for slot, src in slot_sources.items() if src["enabled"]]
    resources = {slot: cluster_file_stem(mat.name, slot) for slot in active_slots}
    rel_dir = getattr(settings, "output_subdir", OUTPUT_SUBDIR).replace("\\", "/")

    manifest_groups = []
    for group in sorted(layout_groups, key=lambda item: item["index"]):
        rect = manifest_rect(settings, atlas_h, group["x"], group["y"], group["w"], group["h"])
        content_rect = manifest_rect(
            settings,
            atlas_h,
            group["x"] + settings.vertex_margin_px,
            group["y"] + settings.vertex_margin_px,
            group["content_w"],
            group["content_h"],
        )
        manifest_groups.append({
            "index": int(group["index"]),
            "rect_px": rect,
            "content_rect_px": content_rect,
            "source_uv_bounds": [group["u_min"], group["v_min"], group["u_max"], group["v_max"]],
            "islands": list(group["island_indices"]),
            "face_count": len(group["face_indices"]),
        })

    packed_area = sum(int(g["w"]) * int(g["h"]) for g in layout_groups)
    return {
        "schema": 1,
        "kind": "RZ_TEXWORKS_MC_CLUSTER",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "material": mat.name,
        "material_key": key,
        "semantic_slots": list(SLOTS),
        "active_slots": active_slots,
        "reference_slot": ref_slot,
        "reference_size": [int(ref_size[0]), int(ref_size[1])],
        "atlas_size": [int(atlas_w), int(atlas_h)],
        "uv_authority": "TEXCOORD.xy",
        "y_origin": settings.y_origin,
        "output_dir": rel_dir,
        "resources": resources,
        "blocks": {slot: autoatlas_block_name(slot) for slot in active_slots},
        "groups": manifest_groups,
        "stats": {
            "objects": len(objects),
            "faces": len(faces),
            "uv_islands": len(islands),
            "stack_groups": len(groups),
            "packed_pixel_area": packed_area,
            "atlas_fill_percent": packed_area * 100.0 / max(1, atlas_w * atlas_h),
        },
        "objects": objects,
        "warnings": warnings,
    }


def calculate_cluster(context, use_preview_uv=False):
    settings = get_settings(context)
    if not settings.enabled:
        raise RuntimeError("TexWorks MC is disabled")
    mat = get_active_material(context)
    slot_sources = collect_slot_sources(mat)
    ref_w, ref_h, ref_slot = choose_reference_size(settings, slot_sources, mat)
    if use_preview_uv:
        faces, objects, warnings = collect_preview_cluster_faces(context, mat)
    else:
        faces, objects, warnings = collect_cluster_faces(context, mat)
    if not faces:
        raise RuntimeError(f"Material '{mat.name}' has no mesh faces in the current scene")

    for slot, source in slot_sources.items():
        image = source.get("image")
        if image and (int(image.size[0]), int(image.size[1])) != (ref_w, ref_h):
            warnings.append(f"{slot}: source {image.size[0]}x{image.size[1]} resampled to shared cluster layout {ref_w}x{ref_h}")
        if source.get("procedural"):
            warnings.append(f"{slot}: procedural/non-image node input is not baked yet, generated from solid fallback")
        if source["enabled"] and not image:
            warnings.append(f"{slot}: no image, generated from solid color at fallback/reference layout")

    margin = int(settings.vertex_margin_px)
    gap = int(settings.pack_gap_px)
    has_diffuse_texture = bool(slot_sources.get("Diffuse", {}).get("image"))
    rebuild_mode = "PREVIEW_REEXPORT" if use_preview_uv else ("TEXTURE_FACE_REPACK" if has_diffuse_texture else "NO_DIFFUSE_DENSE_PACK")
    if use_preview_uv:
        islands, layout_groups, face_to_group = twaa_core.build_single_preview_group(faces, ref_w, ref_h, margin)
        groups = layout_groups
        atlas_w = max(group["x"] + group["w"] for group in layout_groups)
        atlas_h = max(group["y"] + group["h"] for group in layout_groups)
    elif has_diffuse_texture:
        islands, groups, face_to_group = twaa_core.build_texture_bsp_groups(faces, ref_w, ref_h, margin)
        bounded = twaa_core.pack_groups_bounded(groups, gap=gap, max_w=ref_w, max_h=ref_h, power_of_two=False)
        if bounded is not None:
            layout_groups, atlas_w, atlas_h = bounded
        else:
            layout_groups, atlas_w, atlas_h = twaa_core.pack_groups(
                groups,
                gap=gap,
                max_size=int(settings.max_atlas_size),
                power_of_two=False,
            )
            warnings.append(
                f"Texture rebuild packed to {atlas_w}x{atlas_h}, larger than Diffuse/reference {ref_w}x{ref_h}. "
                "Packing kept larger source-space groups to avoid excessive face fragmentation."
            )
    else:
        islands, groups, face_to_group = twaa_core.build_no_texture_dense_groups(faces, ref_w, ref_h, margin)
        layout_groups, atlas_w, atlas_h = twaa_core.pack_groups(
            groups,
            gap=gap,
            max_size=int(settings.max_atlas_size),
            power_of_two=False,
        )
    manifest = build_manifest(
        context, mat, slot_sources, objects, faces, islands, groups, layout_groups,
        atlas_w, atlas_h, (ref_w, ref_h), ref_slot, warnings,
    )
    manifest["rebuild_mode"] = rebuild_mode
    if use_preview_uv:
        manifest["uv_source"] = preview_uv_name_for_material(mat)
    return {
        "material": mat,
        "slot_sources": slot_sources,
        "faces": faces,
        "objects": objects,
        "islands": islands,
        "groups": groups,
        "face_to_group": face_to_group,
        "layout_groups": layout_groups,
        "atlas_size": (atlas_w, atlas_h),
        "reference_size": (ref_w, ref_h),
        "reference_slot": ref_slot,
        "manifest": manifest,
    }


def bake_cluster_images(context, cluster):
    settings = get_settings(context)
    atlas_w, atlas_h = cluster["atlas_size"]
    ref_w, ref_h = cluster["reference_size"]
    key = material_key(cluster["material"].name)
    images = {}
    pixel_buffers = {}
    debug_average = {}
    for slot, source in cluster["slot_sources"].items():
        if not source["enabled"]:
            continue
        name = cluster["manifest"]["resources"][slot]
        pixels = bake_slot_image(
            slot,
            source,
            cluster["faces"],
            cluster["face_to_group"],
            cluster["layout_groups"],
            atlas_w,
            atlas_h,
            ref_w,
            ref_h,
            int(settings.vertex_margin_px),
            int(getattr(settings, "max_raster_pixels", DEFAULT_MAX_RASTER_PIXELS)),
        )
        debug_average[slot] = tuple(round(v, 6) for v in pixel_average_rgba(pixels))
        pixel_buffers[slot] = pixels
        image = create_or_replace_image(name, atlas_w, atlas_h, pixels)
        set_image_colorspace(image, slot)
        images[slot] = image
    cluster["images"] = images
    cluster["pixel_buffers"] = pixel_buffers
    cluster["manifest"]["debug_average_rgba"] = debug_average
    print(f"[RZM TexWorks MC] Rebuilt '{cluster['material'].name}' {atlas_w}x{atlas_h} avg={debug_average}")
    context.scene["rzm_tw_mc_last_manifest_json"] = json.dumps(cluster["manifest"], indent=2, sort_keys=True)
    text_name = f"{RESOURCE_PREFIX}.{key}.manifest"
    text = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
    text.clear()
    text.write(context.scene["rzm_tw_mc_last_manifest_json"])
    return images


def export_cluster_pngs(context, cluster, target_path=None):
    from ..operators.export_manager import get_target_path

    settings = get_settings(context)
    if target_path is None:
        target_path = get_target_path(context)
    if not target_path:
        raise RuntimeError("No export target path configured")

    key = material_key(cluster["material"].name)
    out_dir = os.path.join(bpy.path.abspath(target_path), settings.output_subdir)
    os.makedirs(out_dir, exist_ok=True)
    print(f"[RZM TexWorks MC] Export dir: {out_dir}")

    if "images" not in cluster:
        bake_cluster_images(context, cluster)

    written = {}
    for slot, image in cluster["images"].items():
        file_name = f"{cluster['manifest']['resources'][slot]}.png"
        file_path = os.path.join(out_dir, file_name)
        pixels = cluster.get("pixel_buffers", {}).get(slot)
        if pixels is None:
            pixels = array("f", [0.0]) * (image.size[0] * image.size[1] * 4)
            image.pixels.foreach_get(pixels)
        write_png_rgba8(file_path, image.size[0], image.size[1], pixels)
        image.name = file_name
        image.filepath = file_path
        image.filepath_raw = file_path
        written[slot] = file_path

    manifest_path = os.path.join(out_dir, f"{RESOURCE_PREFIX}.{key}.manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(cluster["manifest"], handle, indent=2, sort_keys=True)
    written["manifest"] = manifest_path
    return written


def atlas_uv_for_source_uv(uv, group, ref_w, ref_h, atlas_w, atlas_h, margin):
    x, y = dest_uv_to_pixel(uv, group, ref_w, ref_h, margin)
    return (x / max(1, atlas_w), 1.0 - (y / max(1, atlas_h)))


def apply_cluster_uv_layout(context, cluster):
    settings = get_settings(context)
    atlas_w, atlas_h = cluster["atlas_size"]
    ref_w, ref_h = cluster["reference_size"]
    margin = int(settings.vertex_margin_px)
    layout_by_index = {group["index"]: group for group in cluster["layout_groups"]}
    changed_objects = set()
    source_layers = {}

    for face_index, face in enumerate(cluster["faces"]):
        base_group = cluster["face_to_group"].get(face_index)
        if not base_group:
            continue
        group = layout_by_index.get(base_group["index"])
        if not group:
            continue
        obj = bpy.data.objects.get(face["object"])
        if not obj or obj.type != "MESH":
            continue
        mesh = obj.data
        source_name = face.get("uv_layer_name")
        if source_name and mesh.uv_layers.get(source_name) is None:
            if source_uv_layer_for_mesh(mesh) is None:
                continue
        elif source_uv_layer_for_mesh(mesh) is None:
            continue
        preview_layer = source_layers.get(mesh.name)
        if preview_layer is None:
            preview_layer = preview_uv_layer_for_mesh(mesh, cluster["material"])
            source_layers[mesh.name] = preview_layer
        for loop_index, old_uv in zip(face["loop_indices"], face["uvs"]):
            new_u, new_v = atlas_uv_for_source_uv(
                old_uv,
                group,
                ref_w,
                ref_h,
                atlas_w,
                atlas_h,
                margin,
            )
            preview_layer.data[loop_index].uv = (new_u, new_v)
        try:
            mesh.uv_layers.active = preview_layer
        except Exception:
            pass
        try:
            preview_layer.active = True
        except Exception:
            pass
        try:
            preview_layer.active_render = True
        except Exception:
            pass
        mesh.update()
        changed_objects.add(obj.name)

    return sorted(changed_objects)


def destructively_apply_preview_to_texcoord(context, mat):
    changed_objects = []
    for obj in context.scene.objects:
        if obj.type != "MESH":
            continue
        if not material_slot_indices(obj, mat):
            continue
        mesh = obj.data
        source_layer = source_uv_layer_for_mesh(mesh)
        preview_layer = mesh.uv_layers.get(preview_uv_name_for_material(mat))
        if not source_layer or not preview_layer:
            continue
        count = min(len(source_layer.data), len(preview_layer.data))
        for i in range(count):
            source_layer.data[i].uv = preview_layer.data[i].uv
        source_layer.name = TEXCOORD_UV_NAME
        try:
            mesh.uv_layers.active = source_layer
        except Exception:
            pass
        try:
            source_layer.active = True
            source_layer.active_render = True
        except Exception:
            pass
        try:
            mesh.uv_layers.remove(preview_layer)
        except Exception:
            pass
        mesh.update()
        changed_objects.append(obj.name)
    return sorted(set(changed_objects))


def upstream_image_nodes(socket, visited=None):
    if visited is None:
        visited = set()
    result = []
    if not socket or not socket.is_linked:
        return result
    for link in socket.links:
        node = link.from_node
        if not node or node.as_pointer() in visited:
            continue
        visited.add(node.as_pointer())
        if node.bl_idname == "ShaderNodeTexImage":
            result.append(node)
        for input_socket in getattr(node, "inputs", []):
            result.extend(upstream_image_nodes(input_socket, visited))
    return result


def replace_material_slot_images(mat, cluster, written=None):
    node = find_material_group_node(mat)
    if not node:
        return []
    changed = []
    slot_y = {slot: index * -260 for index, slot in enumerate(SLOTS)}
    for slot, image in cluster.get("images", {}).items():
        if slot not in node.inputs:
            continue
        if written and slot in written:
            try:
                image = bpy.data.images.load(written[slot], check_existing=True)
            except Exception:
                image = cluster.get("images", {}).get(slot, image)
            if image:
                image.name = os.path.basename(written[slot])
                image.filepath = written[slot]
                image.filepath_raw = written[slot]
        nodes = upstream_image_nodes(node.inputs[slot])
        if not nodes:
            tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex_node.location = (node.location.x - 430, node.location.y + slot_y.get(slot, 0))
            mat.node_tree.links.new(tex_node.outputs["Color"], node.inputs[slot])
            nodes = [tex_node]
        for idx, tex_node in enumerate(nodes):
            tex_node.location = (node.location.x - 430, node.location.y + slot_y.get(slot, 0) - idx * 220)
            tex_node.image = image
            set_image_colorspace(tex_node.image, slot)
            changed.append(f"{slot}:{tex_node.name}")
    return changed


def apply_cluster_to_material(context, cluster, target_path=None, written=None):
    if written is None:
        written = export_cluster_pngs(context, cluster, target_path=target_path)
    changed_objects = destructively_apply_preview_to_texcoord(context, cluster["material"])
    changed_nodes = replace_material_slot_images(cluster["material"], cluster, written=written)
    return {
        "written": written,
        "changed_objects": changed_objects,
        "changed_nodes": changed_nodes,
    }


def find_by_name(collection, name):
    for item in collection:
        if item.name == name:
            return item
    return None


def ensure_block(rzm, name):
    item = find_by_name(rzm.tw_blocks, name)
    if item:
        return item
    item = rzm.tw_blocks.add()
    item.name = name
    return item


def remove_legacy_dotted_autoatlas_blocks(rzm):
    removed = []
    legacy_prefix = f"{RESOURCE_PREFIX}."
    for index in range(len(rzm.tw_blocks) - 1, -1, -1):
        block = rzm.tw_blocks[index]
        if block.name.startswith(legacy_prefix):
            removed.append(block.name)
            rzm.tw_blocks.remove(index)
    return removed


def migrate_legacy_autoatlas_resource_name(name):
    if not name:
        return name
    prefix = f"{RESOURCE_PREFIX}."
    if not name.startswith(prefix):
        return name
    slot = name[len(prefix):]
    for known_slot in SLOTS:
        if slot == slot_file_suffix(known_slot):
            return autoatlas_block_name(known_slot)
    return f"{RESOURCE_PREFIX}{re.sub(r'[^A-Za-z0-9_]+', '_', slot).strip('_')}"


def migrate_legacy_autoatlas_references(rzm):
    changed = []
    for override in getattr(rzm, "tw_overrides", []):
        new_name = migrate_legacy_autoatlas_resource_name(override.resource_name)
        if new_name != override.resource_name:
            changed.append((override.resource_name, new_name))
            override.resource_name = new_name
        for binding in getattr(override, "bindings", []):
            new_name = migrate_legacy_autoatlas_resource_name(binding.resource_name)
            if new_name != binding.resource_name:
                changed.append((binding.resource_name, new_name))
                binding.resource_name = new_name
    return changed


def addon_preferences(context):
    addon_name = __package__.split(".")[0]
    addon = context.preferences.addons.get(addon_name)
    return addon.preferences if addon else None


def post_invert_settings(context):
    prefs = addon_preferences(context)
    return (
        bool(getattr(prefs, "tw_mc_post_invert_x", False)) if prefs else False,
        bool(getattr(prefs, "tw_mc_post_invert_y", True)) if prefs else True,
    )


def clear_collection(collection):
    for index in range(len(collection) - 1, -1, -1):
        collection.remove(index)


def ensure_mc_file_entry(rzm, resource_name):
    for item in rzm.tw_mc_files:
        if item.resource_name == resource_name:
            return item
    item = rzm.tw_mc_files.add()
    item.name = resource_name
    return item


def read_png_size(path):
    try:
        with open(path, "rb") as handle:
            header = handle.read(24)
    except Exception:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def resolve_mc_file_path(entry):
    rel_path = str(getattr(entry, "relative_path", "") or "").replace("\\", "/")
    if not rel_path:
        return None
    try:
        from ..operators.export_manager import get_target_path

        target_path = get_target_path(bpy.context)
    except Exception:
        target_path = None
    if not target_path:
        return None
    return os.path.join(bpy.path.abspath(target_path), rel_path)


def refresh_mc_file_resolution_from_disk(entry):
    path = resolve_mc_file_path(entry)
    if not path:
        return False
    size = read_png_size(path)
    if not size:
        return False
    w, h = int(size[0]), int(size[1])
    if w <= 0 or h <= 0:
        return False
    if int(entry.resolution[0]) != w or int(entry.resolution[1]) != h:
        entry.resolution = (w, h)
        return True
    return False


def sync_mc_file_entries(rzm, manifest):
    desired = set(manifest["resources"].values())
    key = manifest["material_key"]
    for slot, resource_name in manifest["resources"].items():
        entry = ensure_mc_file_entry(rzm, resource_name)
        entry.name = resource_name
        entry.material_name = manifest["material"]
        entry.material_key = key
        entry.slot_name = slot
        entry.resource_name = resource_name
        entry.relative_path = os.path.join(manifest["output_dir"], f"{resource_name}.png").replace("\\", "/")
        entry.block_name = manifest.get("blocks", {}).get(slot, autoatlas_block_name(slot))
        entry.resolution = tuple(manifest["atlas_size"])

    for index in range(len(rzm.tw_mc_files) - 1, -1, -1):
        item = rzm.tw_mc_files[index]
        if item.material_key == key and item.resource_name not in desired:
            rzm.tw_mc_files.remove(index)


def mc_entries_by_material(rzm):
    materials = {}
    for entry in rzm.tw_mc_files:
        refresh_mc_file_resolution_from_disk(entry)
        key = entry.material_key or material_key(entry.material_name)
        if not key:
            continue
        mat_data = materials.setdefault(key, {
            "material_key": key,
            "material_name": entry.material_name,
            "resolution": [1, 1],
            "slots": {},
        })
        if entry.material_name:
            mat_data["material_name"] = entry.material_name
        w = max(1, int(entry.resolution[0]))
        h = max(1, int(entry.resolution[1]))
        mat_data["resolution"][0] = max(mat_data["resolution"][0], w)
        mat_data["resolution"][1] = max(mat_data["resolution"][1], h)
        mat_data["slots"][entry.slot_name] = entry
    return materials


def pack_material_components(materials, settings):
    groups = []
    for index, mat_data in enumerate(materials.values()):
        w, h = mat_data["resolution"]
        groups.append({
            "index": index,
            "material_key": mat_data["material_key"],
            "material_name": mat_data["material_name"],
            "w": int(w),
            "h": int(h),
        })
    if not groups:
        return {}, 16, 16
    packed, atlas_w, atlas_h = twaa_core.pack_groups(
        groups,
        gap=0,
        max_size=int(settings.max_atlas_size),
        power_of_two=False,
    )
    atlas_w = round_up_to_multiple(atlas_w, 16)
    atlas_h = round_up_to_multiple(atlas_h, 16)
    return {group["material_key"]: group for group in packed}, atlas_w, atlas_h


def objects_using_material_name(mat_name):
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        return []
    objects = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            if slot.material == mat:
                objects.append(obj)
                break
    return objects


LEGACY_OBJECT_PROPS = (
    "TEXCOORD_POS_SIZE",
    "RZM_TW_MC_COMPONENT",
    "RZM_TW_MC_ATLAS_SIZE",
    "RZM_TW_MC_RECT",
    "RZM_TW_MC_VIRTUAL_ATLAS_SIZE",
    "RZM_TW_MC_VIRTUAL_RECT",
    "RZM_TW_MC_BLOCKS",
    "RZM_TW_MC_POST_INVERT_X",
    "RZM_TW_MC_POST_INVERT_Y",
)


def clear_legacy_tw_mc_object_props():
    changed = []
    for obj in bpy.data.objects:
        removed = False
        for key in LEGACY_OBJECT_PROPS:
            if key in obj:
                try:
                    del obj[key]
                    removed = True
                except Exception:
                    pass
        if removed:
            changed.append(obj.name)
    return changed


def rebuild_texworks_autoatlas_blocks(context):
    settings = get_settings(context)
    rzm = context.scene.rzm
    removed_legacy_blocks = remove_legacy_dotted_autoatlas_blocks(rzm)
    migrated_refs = migrate_legacy_autoatlas_references(rzm)
    materials = mc_entries_by_material(rzm)
    packed_by_mat, atlas_w, atlas_h = pack_material_components(materials, settings)
    if not materials:
        return {"materials": 0, "blocks": 0, "atlas_size": [atlas_w, atlas_h]}

    slots = sorted({slot for mat_data in materials.values() for slot in mat_data["slots"].keys()}, key=lambda s: SLOTS.index(s) if s in SLOTS else 999)
    block_names = [autoatlas_block_name(slot) for slot in slots]

    for slot in slots:
        block_name = autoatlas_block_name(slot)
        block = ensure_block(rzm, block_name)
        block.resource_name = block_name
        if hasattr(block, "create_block_resource"):
            block.create_block_resource = True
        if hasattr(block, "block_resource_size"):
            block.block_resource_size = (int(atlas_w), int(atlas_h))
        block.shader_type = "NORMAL" if slot == "NormalMap" else "DIFFUSE"
        block.backdrop_enabled = False
        clear_collection(block.components)

        for key, mat_data in sorted(materials.items()):
            entry = mat_data["slots"].get(slot)
            if not entry:
                continue
            rect = packed_by_mat.get(key)
            if not rect:
                continue
            comp = block.components.add()
            comp.name = key
            comp.base_resource_name = entry.resource_name
            comp.base_rect = (int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"]))
            comp.rect = (int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"]))
            comp.tw_is_expanded = False
            tw_slot = comp.slots.add()
            tw_slot.name = slot
            tw_slot.active = True
            tw_slot.rect = comp.rect
            tw_slot.calc_res_x = int(atlas_w)
            tw_slot.calc_res_y = int(atlas_h)
        block.active_component_index = 0 if block.components else -1

    cleaned_objects = clear_legacy_tw_mc_object_props()

    return {
        "materials": len(materials),
        "blocks": len(slots),
        "atlas_size": [int(atlas_w), int(atlas_h)],
        "objects": [],
        "cleaned_legacy_object_props": sorted(set(cleaned_objects)),
        "removed_legacy_blocks": removed_legacy_blocks,
        "migrated_legacy_references": migrated_refs,
    }


def register_cluster_files(context, cluster):
    rzm = context.scene.rzm
    sync_mc_file_entries(rzm, cluster["manifest"])
    return cluster["manifest"]


def sync_texworks_data(context, cluster, remove_missing=False):
    settings = get_settings(context)
    rzm = context.scene.rzm
    manifest = cluster["manifest"]

    sync_mc_file_entries(rzm, manifest)

    if settings.sync_blocks:
        layout_summary = rebuild_texworks_autoatlas_blocks(context)
        manifest["texworks_layout"] = layout_summary

    context.scene["rzm_tw_mc_last_manifest_json"] = json.dumps(manifest, indent=2, sort_keys=True)
    return manifest


def rebuild_active_material_cluster(context):
    cluster = calculate_cluster(context)
    bake_cluster_images(context, cluster)
    apply_cluster_uv_layout(context, cluster)
    export_cluster_pngs(context, cluster)
    register_cluster_files(context, cluster)
    return cluster


def export_active_preview_cluster(context):
    cluster = calculate_cluster(context, use_preview_uv=True)
    bake_cluster_images(context, cluster)
    export_cluster_pngs(context, cluster)
    register_cluster_files(context, cluster)
    return cluster


def apply_active_preview_cluster(context):
    if not active_material_has_preview_uv(context):
        cluster = calculate_cluster(context)
        bake_cluster_images(context, cluster)
        apply_cluster_uv_layout(context, cluster)
    else:
        cluster = calculate_cluster(context, use_preview_uv=True)
        bake_cluster_images(context, cluster)
    written = export_cluster_pngs(context, cluster)
    result = apply_cluster_to_material(context, cluster, written=written)
    register_cluster_files(context, cluster)
    return cluster, result
