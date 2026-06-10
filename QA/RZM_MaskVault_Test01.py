bl_info = {
    "name": "RZM Mask Vault Test",
    "author": "OpenAI for Rayvich",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),
    "location": "3D View > Sidebar > RZM Mask Vault",
    "description": "Save a vertex group as hidden mesh attributes and restore it later",
    "category": "Mesh",
}

import bpy
import hashlib
import re
import struct
from bpy.props import EnumProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup


def active_mesh_object(context):
    obj = context.active_object
    if obj is None or obj.type != 'MESH':
        return None
    return obj


def require_object_mode(operator, context):
    obj = active_mesh_object(context)
    if obj is None:
        operator.report({'ERROR'}, "Select an active mesh object")
        return None
    if obj.mode != 'OBJECT':
        operator.report({'ERROR'}, "Switch the object to Object Mode first")
        return None
    return obj


def safe_slug(text):
    slug = re.sub(r'[^0-9A-Za-z_]+', '_', text.strip()).strip('_').lower()
    if not slug:
        slug = 'group'
    digest = hashlib.sha1(text.encode('utf-8')).hexdigest()[:8]
    return f"{slug[:32]}_{digest}"


def attribute_names(group_name):
    stem = f"rzm_anticollider_mask"
    return {
        'F32': stem + '_f32',
        'F16_LO': stem + '_f16_lo',
        'F16_HI': stem + '_f16_hi',
    }


def remove_attribute_if_present(mesh, name):
    attr = mesh.attributes.get(name)
    if attr is not None:
        mesh.attributes.remove(attr)


def create_attribute(mesh, name, data_type):
    remove_attribute_if_present(mesh, name)
    return mesh.attributes.new(name=name, type=data_type, domain='POINT')


def read_vertex_group_weights(obj, group_name):
    group = obj.vertex_groups.get(group_name)
    if group is None:
        raise RuntimeError(f'Vertex group "{group_name}" was not found')

    group_index = group.index
    values = [0.0] * len(obj.data.vertices)
    for vertex in obj.data.vertices:
        for membership in vertex.groups:
            if membership.group == group_index:
                values[vertex.index] = float(membership.weight)
                break
    return values


def signed_byte(value):
    return value if value < 128 else value - 256


def unsigned_byte(value):
    return value & 0xFF


def encode_float16(values):
    raw = bytearray(len(values) * 2)
    for index, value in enumerate(values):
        struct.pack_into('<e', raw, index * 2, float(value))
    low = [signed_byte(raw[index * 2]) for index in range(len(values))]
    high = [signed_byte(raw[index * 2 + 1]) for index in range(len(values))]
    return low, high


def decode_float16(low, high):
    raw = bytearray(len(low) * 2)
    for index in range(len(low)):
        raw[index * 2] = unsigned_byte(low[index])
        raw[index * 2 + 1] = unsigned_byte(high[index])
    return [struct.unpack_from('<e', raw, index * 2)[0] for index in range(len(low))]


def save_f32(mesh, group_name, values):
    names = attribute_names(group_name)
    attr = create_attribute(mesh, names['F32'], 'FLOAT')
    attr.data.foreach_set('value', values)
    mesh.update()


def save_f16(mesh, group_name, values):
    names = attribute_names(group_name)
    try:
        low_attr = create_attribute(mesh, names['F16_LO'], 'INT8')
        high_attr = create_attribute(mesh, names['F16_HI'], 'INT8')
    except Exception as exc:
        remove_attribute_if_present(mesh, names['F16_LO'])
        remove_attribute_if_present(mesh, names['F16_HI'])
        raise RuntimeError(
            'This Blender build does not expose INT8 mesh attributes. '
            'Use Float32 or run the script in Blender 4.4+.'
        ) from exc

    low, high = encode_float16(values)
    low_attr.data.foreach_set('value', low)
    high_attr.data.foreach_set('value', high)
    mesh.update()


def read_f32(mesh, group_name):
    name = attribute_names(group_name)['F32']
    attr = mesh.attributes.get(name)
    if attr is None:
        raise RuntimeError(f'Hidden Float32 attribute "{name}" was not found')
    if attr.domain != 'POINT' or attr.data_type != 'FLOAT':
        raise RuntimeError(f'Attribute "{name}" has an unexpected type')
    values = [0.0] * len(mesh.vertices)
    attr.data.foreach_get('value', values)
    return values


def read_f16(mesh, group_name):
    names = attribute_names(group_name)
    low_attr = mesh.attributes.get(names['F16_LO'])
    high_attr = mesh.attributes.get(names['F16_HI'])
    if low_attr is None or high_attr is None:
        raise RuntimeError('Hidden Float16 byte attributes were not found')
    if low_attr.domain != 'POINT' or high_attr.domain != 'POINT':
        raise RuntimeError('Float16 attributes are not stored on the POINT domain')
    if low_attr.data_type != 'INT8' or high_attr.data_type != 'INT8':
        raise RuntimeError('Float16 attributes have an unexpected type')

    low = [0] * len(mesh.vertices)
    high = [0] * len(mesh.vertices)
    low_attr.data.foreach_get('value', low)
    high_attr.data.foreach_get('value', high)
    return decode_float16(low, high)


def overwrite_vertex_group(obj, group_name, values):
    group = obj.vertex_groups.get(group_name)
    if group is None:
        group = obj.vertex_groups.new(name=group_name)
    else:
        group.remove(list(range(len(obj.data.vertices))))

    restored = 0
    for index, weight in enumerate(values):
        weight = float(weight)
        if weight > 0.0:
            group.add([index], min(max(weight, 0.0), 1.0), 'REPLACE')
            restored += 1
    obj.data.update()
    return restored


def bytes_label(size):
    if size < 1024:
        return f'{size} B'
    if size < 1024 * 1024:
        return f'{size / 1024:.2f} KiB'
    return f'{size / (1024 * 1024):.2f} MiB'


class RZM_MaskVaultSettings(PropertyGroup):
    group_name: StringProperty(
        name='Vertex Group',
        default='MASK TEST',
        description='Vertex group to save, delete, and restore',
    )
    precision: EnumProperty(
        name='Storage',
        items=(
            ('F32', 'Float32', 'One hidden FLOAT attribute: 4 bytes per vertex'),
            ('F16', 'Float16', 'Two hidden INT8 attributes containing IEEE-754 half bits: 2 bytes per vertex'),
        ),
        default='F32',
    )


class RZM_OT_SaveMaskAttribute(Operator):
    bl_idname = 'rzm_mask_vault.save_attribute'
    bl_label = 'Save / Overwrite Attribute'
    bl_description = 'Copy the selected vertex group into hidden mesh attributes'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = require_object_mode(self, context)
        if obj is None:
            return {'CANCELLED'}

        settings = context.scene.rzm_mask_vault_settings
        try:
            values = read_vertex_group_weights(obj, settings.group_name)
            if settings.precision == 'F32':
                save_f32(obj.data, settings.group_name, values)
                storage = 'Float32'
            else:
                save_f16(obj.data, settings.group_name, values)
                storage = 'Float16 packed into two INT8 attributes'
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        nonzero = sum(1 for value in values if value > 0.0)
        self.report({'INFO'}, f'Saved {len(values)} vertices, {nonzero} weighted, as {storage}')
        return {'FINISHED'}


class RZM_OT_DeleteVertexGroup(Operator):
    bl_idname = 'rzm_mask_vault.delete_group'
    bl_label = 'Delete Vertex Group'
    bl_description = 'Delete the visible vertex group while keeping hidden attributes intact'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = require_object_mode(self, context)
        if obj is None:
            return {'CANCELLED'}

        group_name = context.scene.rzm_mask_vault_settings.group_name
        group = obj.vertex_groups.get(group_name)
        if group is None:
            self.report({'WARNING'}, f'Vertex group "{group_name}" does not exist')
            return {'CANCELLED'}

        obj.vertex_groups.remove(group)
        self.report({'INFO'}, f'Deleted vertex group "{group_name}"')
        return {'FINISHED'}


class RZM_OT_RestoreVertexGroup(Operator):
    bl_idname = 'rzm_mask_vault.restore_group'
    bl_label = 'Restore / Overwrite Vertex Group'
    bl_description = 'Create the vertex group again or overwrite its current weights from hidden attributes'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = require_object_mode(self, context)
        if obj is None:
            return {'CANCELLED'}

        settings = context.scene.rzm_mask_vault_settings
        try:
            if settings.precision == 'F32':
                values = read_f32(obj.data, settings.group_name)
                storage = 'Float32'
            else:
                values = read_f16(obj.data, settings.group_name)
                storage = 'Float16'
            restored = overwrite_vertex_group(obj, settings.group_name, values)
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report({'INFO'}, f'Restored "{settings.group_name}" from {storage}: {restored} weighted vertices')
        return {'FINISHED'}


class RZM_OT_RoundTripTest(Operator):
    bl_idname = 'rzm_mask_vault.round_trip_test'
    bl_label = 'Save -> Delete -> Restore'
    bl_description = 'Perform the complete round-trip test in one click'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = require_object_mode(self, context)
        if obj is None:
            return {'CANCELLED'}

        settings = context.scene.rzm_mask_vault_settings
        try:
            values = read_vertex_group_weights(obj, settings.group_name)
            if settings.precision == 'F32':
                save_f32(obj.data, settings.group_name, values)
                restored_values = read_f32(obj.data, settings.group_name)
                storage = 'Float32'
            else:
                save_f16(obj.data, settings.group_name, values)
                restored_values = read_f16(obj.data, settings.group_name)
                storage = 'Float16'

            group = obj.vertex_groups.get(settings.group_name)
            if group is not None:
                obj.vertex_groups.remove(group)
            restored = overwrite_vertex_group(obj, settings.group_name, restored_values)
            max_error = max((abs(a - b) for a, b in zip(values, restored_values)), default=0.0)
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report({'INFO'}, f'{storage} round trip complete: {restored} weighted vertices, max error {max_error:.8f}')
        return {'FINISHED'}


class RZM_PT_MaskVault(Panel):
    bl_label = 'RZM Mask Vault'
    bl_idname = 'RZM_PT_mask_vault'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZM Mask Vault'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rzm_mask_vault_settings
        obj = active_mesh_object(context)

        layout.prop(settings, 'group_name')
        layout.prop(settings, 'precision', expand=True)

        column = layout.column(align=True)
        column.operator('rzm_mask_vault.save_attribute', icon='FILE_TICK')
        column.operator('rzm_mask_vault.delete_group', icon='TRASH')
        column.operator('rzm_mask_vault.restore_group', icon='LOOP_BACK')
        layout.separator()
        layout.operator('rzm_mask_vault.round_trip_test', icon='PLAY')

        box = layout.box()
        box.label(text='Status')
        if obj is None:
            box.label(text='Select a mesh object', icon='ERROR')
            return

        mesh = obj.data
        names = attribute_names(settings.group_name)
        group_exists = obj.vertex_groups.get(settings.group_name) is not None
        f32_exists = mesh.attributes.get(names['F32']) is not None
        f16_exists = mesh.attributes.get(names['F16_LO']) is not None and mesh.attributes.get(names['F16_HI']) is not None
        vertex_count = len(mesh.vertices)

        box.label(text=f'Object: {obj.name}')
        box.label(text=f'Vertices: {vertex_count:,}')
        box.label(text=f'Visible group: {"YES" if group_exists else "NO"}')
        box.label(text=f'Hidden Float32: {"YES" if f32_exists else "NO"} | {bytes_label(vertex_count * 4)}')
        box.label(text=f'Hidden Float16: {"YES" if f16_exists else "NO"} | {bytes_label(vertex_count * 2)}')

        details = layout.box()
        details.label(text='Hidden attribute names')
        details.label(text=names['F32'])
        details.label(text=names['F16_LO'])
        details.label(text=names['F16_HI'])


classes = (
    RZM_MaskVaultSettings,
    RZM_OT_SaveMaskAttribute,
    RZM_OT_DeleteVertexGroup,
    RZM_OT_RestoreVertexGroup,
    RZM_OT_RoundTripTest,
    RZM_PT_MaskVault,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rzm_mask_vault_settings = PointerProperty(type=RZM_MaskVaultSettings)


def unregister():
    del bpy.types.Scene.rzm_mask_vault_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
