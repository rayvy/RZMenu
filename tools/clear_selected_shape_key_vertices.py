"""
Reset selected mesh vertices in shape keys back to Basis.

Usage in Blender:
1. Select a mesh object.
2. Select vertices in Edit Mode, or leave selected vertices in Object Mode.
3. Run this script from Blender Text Editor.

By default it clears selected vertices in all non-Basis shape keys.
Set ACTIVE_SHAPE_KEY_ONLY = True to affect only the active shape key.
"""

import bpy
import bmesh


ACTIVE_SHAPE_KEY_ONLY = False
EPSILON = 0.0


def selected_vertex_indices(obj):
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        return [vert.index for vert in bm.verts if vert.select]

    return [vert.index for vert in obj.data.vertices if vert.select]


def shape_keys_to_clear(obj):
    keys = obj.data.shape_keys.key_blocks

    if ACTIVE_SHAPE_KEY_ONLY:
        active_index = obj.active_shape_key_index
        if active_index <= 0 or active_index >= len(keys):
            return []
        return [keys[active_index]]

    return [key for key in keys if key != obj.data.shape_keys.reference_key]


def clear_selected_shape_key_vertices(context):
    obj = context.active_object
    if not obj or obj.type != "MESH":
        raise RuntimeError("Active object must be a mesh.")

    shape_keys = obj.data.shape_keys
    if not shape_keys or len(shape_keys.key_blocks) <= 1:
        raise RuntimeError(f"Object '{obj.name}' has no non-Basis shape keys.")

    original_mode = obj.mode
    selected_indices = selected_vertex_indices(obj)
    if not selected_indices:
        raise RuntimeError("No selected vertices found.")

    if original_mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    basis = shape_keys.reference_key
    target_keys = shape_keys_to_clear(obj)
    if not target_keys:
        raise RuntimeError("No target shape keys to clear.")

    changed = 0
    for key in target_keys:
        for vertex_index in selected_indices:
            basis_co = basis.data[vertex_index].co
            if EPSILON > 0.0 and (key.data[vertex_index].co - basis_co).length <= EPSILON:
                continue
            key.data[vertex_index].co = basis_co
            changed += 1

    obj.data.update()

    if original_mode != "OBJECT":
        bpy.ops.object.mode_set(mode=original_mode)

    print(
        f"[RZM] Cleared shape-key data on {len(selected_indices)} selected vertices "
        f"across {len(target_keys)} shape keys ({changed} coordinates reset)."
    )


clear_selected_shape_key_vertices(bpy.context)
