# RZMenu/operators/rzm_custom_shape_baker_ops.py
import bpy
import bmesh
from .rzm_surface_baker import transfer_surface_shape_keys

class RZM_OT_BakeShapeKeysCustom(bpy.types.Operator):
    bl_idname = "rzm.bake_shape_keys_custom"
    bl_label = "Bake Shape Keys (Tangent-Space Bind)"
    bl_description = "Transfer shape keys from selected donor mesh to active target mesh"
    bl_options = {'REGISTER', 'UNDO'}

    overwrite: bpy.props.BoolProperty(
        name="Overwrite Existing",
        description="Delete existing shape keys on the target mesh before baking if they have the same name",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        selected = [obj for obj in context.selected_objects if obj and obj.type == 'MESH']
        return len(selected) == 2 and context.active_object in selected

    def execute(self, context):
        target = context.active_object
        selected = [obj for obj in context.selected_objects if obj and obj.type == 'MESH']
        donor = [obj for obj in selected if obj != target][0]

        if not donor.data.shape_keys or not donor.data.shape_keys.key_blocks:
            self.report({'WARNING'}, f"Donor mesh '{donor.name}' has no shape keys to transfer.")
            return {'CANCELLED'}

        # Get all non-basis shape key names
        sk_names = [
            kb.name for kb in donor.data.shape_keys.key_blocks 
            if kb != donor.data.shape_keys.reference_key
        ]

        if not sk_names:
            self.report({'WARNING'}, f"Donor mesh '{donor.name}' has only Basis shape key.")
            return {'CANCELLED'}

        # Remember target's original mode
        original_mode = target.mode
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        try:
            # Overwrite logic
            if self.overwrite and target.data.shape_keys:
                for name in sk_names:
                    kb = target.data.shape_keys.key_blocks.get(name)
                    if kb:
                        target.shape_key_remove(kb)

            # Perform the transfer
            transfer_surface_shape_keys(target, donor, sk_names)
            
            # Select target shape key to something active if possible
            if target.data.shape_keys and target.data.shape_keys.key_blocks:
                # set active to the first baked shape key
                for name in sk_names:
                    idx = target.data.shape_keys.key_blocks.find(name)
                    if idx != -1:
                        target.active_shape_key_index = idx
                        break

            self.report({'INFO'}, f"Successfully baked {len(sk_names)} shape keys from '{donor.name}' to '{target.name}'.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to bake shape keys: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        finally:
            if target.mode != original_mode:
                try:
                    bpy.ops.object.mode_set(mode=original_mode)
                except Exception:
                    pass

        return {'FINISHED'}


class RZM_OT_ResetShapeKeyVertices(bpy.types.Operator):
    bl_idname = "rzm.reset_shape_key_vertices"
    bl_label = "Reset Selected Shape Key Vertices"
    bl_description = "Reset selected vertices in active shape key back to Basis coordinates"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None
            and obj.type == 'MESH'
            and obj.data is not None
            and obj.data.shape_keys is not None
            and obj.active_shape_key is not None
            and obj.active_shape_key != obj.data.shape_keys.reference_key
        )

    def execute(self, context):
        obj = context.active_object
        active_key = obj.active_shape_key
        basis_key = obj.data.shape_keys.reference_key

        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)
            shape_layer = bm.verts.layers.shape.get(active_key.name)
            basis_layer = bm.verts.layers.shape.get(basis_key.name)

            if not basis_layer:
                self.report({'ERROR'}, "Basis shape key layer not found in BMesh.")
                return {'CANCELLED'}

            reset_count = 0
            for v in bm.verts:
                if v.select:
                    v.co = v[basis_layer]
                    if shape_layer:
                        v[shape_layer] = v[basis_layer]
                    reset_count += 1

            if reset_count > 0:
                bmesh.update_edit_mesh(obj.data)
                self.report({'INFO'}, f"Reset {reset_count} selected vertices in '{active_key.name}' back to Basis.")
            else:
                self.report({'WARNING'}, "No selected vertices found to reset.")
                return {'CANCELLED'}

        else: # Object Mode
            selected_indices = [v.index for v in obj.data.vertices if v.select]
            if not selected_indices:
                self.report({'WARNING'}, "No selected vertices found to reset.")
                return {'CANCELLED'}

            reset_count = 0
            for idx in selected_indices:
                active_key.data[idx].co = basis_key.data[idx].co
                reset_count += 1

            obj.data.update()
            self.report({'INFO'}, f"Reset {reset_count} selected vertices in '{active_key.name}' back to Basis.")

        return {'FINISHED'}


classes_to_register = [
    RZM_OT_BakeShapeKeysCustom,
    RZM_OT_ResetShapeKeyVertices,
]
