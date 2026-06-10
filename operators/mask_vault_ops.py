# RZMenu/operators/mask_vault_ops.py
import bpy

def get_target_mesh_objects(context):
    """
    Returns all selected mesh objects.
    If none selected, falls back to the active object if it is a mesh.
    """
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if not selected_meshes and context.active_object and context.active_object.type == 'MESH':
        selected_meshes = [context.active_object]
    return selected_meshes

def save_mask_attribute(obj):
    group = obj.vertex_groups.get("MASK ANTICOLLIDER")
    if not group:
        return False, "Vertex group 'MASK ANTICOLLIDER' not found"
    
    group_index = group.index
    num_verts = len(obj.data.vertices)
    values = [0.0] * num_verts
    
    # Read weights from vertex group
    for vertex in obj.data.vertices:
        for membership in vertex.groups:
            if membership.group == group_index:
                values[vertex.index] = float(membership.weight)
                break
                
    # Overwrite the FLOAT POINT attribute
    attr = obj.data.attributes.get("rzm_anticollider_mask")
    if attr:
        obj.data.attributes.remove(attr)
        
    attr = obj.data.attributes.new(name="rzm_anticollider_mask", type='FLOAT', domain='POINT')
    attr.data.foreach_set('value', values)
    obj.data.update()
    return True, f"Baked {sum(1 for v in values if v > 0.0)} weights to 'rzm_anticollider_mask'"

def restore_mask_vertex_group(obj):
    attr = obj.data.attributes.get("rzm_anticollider_mask")
    if not attr:
        return False, "Attribute 'rzm_anticollider_mask' not found"
        
    num_verts = len(obj.data.vertices)
    values = [0.0] * num_verts
    attr.data.foreach_get('value', values)
    
    group = obj.vertex_groups.get("MASK ANTICOLLIDER")
    if group is None:
        group = obj.vertex_groups.new(name="MASK ANTICOLLIDER")
    else:
        group.remove(list(range(num_verts)))
        
    for idx, val in enumerate(values):
        if val > 0.0:
            group.add([idx], val, 'REPLACE')
            
    obj.data.update()
    return True, f"Restored {sum(1 for v in values if v > 0.0)} weights to 'MASK ANTICOLLIDER'"

def fill_mask_weights(obj, weight=1.0):
    group = obj.vertex_groups.get("MASK ANTICOLLIDER")
    if group is None:
        group = obj.vertex_groups.new(name="MASK ANTICOLLIDER")
        
    num_verts = len(obj.data.vertices)
    group.remove(list(range(num_verts)))
    group.add(list(range(num_verts)), weight, 'REPLACE')
    obj.data.update()
    return True, f"Filled with weight {weight}"

def delete_mask_vertex_group(obj):
    group = obj.vertex_groups.get("MASK ANTICOLLIDER")
    if group:
        obj.vertex_groups.remove(group)
        return True, "Removed 'MASK ANTICOLLIDER' group"
    return False, "Group not found"

def delete_mask_attribute(obj):
    attr = obj.data.attributes.get("rzm_anticollider_mask")
    if attr:
        obj.data.attributes.remove(attr)
        obj.data.update()
        return True, "Removed 'rzm_anticollider_mask' attribute"
    return False, "Attribute not found"


class RZM_OT_SaveMaskAttribute(bpy.types.Operator):
    bl_idname = "rzm.save_mask_attribute"
    bl_label = "Bake Mask to Attribute"
    bl_description = "Bake 'MASK ANTICOLLIDER' weights to custom attribute 'rzm_anticollider_mask'"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        old_mode = None
        if active_obj and active_obj.mode != 'OBJECT':
            old_mode = active_obj.mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
        targets = get_target_mesh_objects(context)
        if not targets:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
            
        success_count = 0
        for obj in targets:
            ok, msg = save_mask_attribute(obj)
            if ok:
                success_count += 1
            else:
                self.report({'WARNING'}, f"{obj.name}: {msg}")
                
        if old_mode:
            bpy.ops.object.mode_set(mode=old_mode)
            
        self.report({'INFO'}, f"Baked mask attribute for {success_count}/{len(targets)} objects")
        return {'FINISHED'}


class RZM_OT_RestoreMaskVertexGroup(bpy.types.Operator):
    bl_idname = "rzm.restore_mask_vertex_group"
    bl_label = "Restore Mask to Vertex Group"
    bl_description = "Restore 'MASK ANTICOLLIDER' weights from attribute 'rzm_anticollider_mask'"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        old_mode = None
        if active_obj and active_obj.mode != 'OBJECT':
            old_mode = active_obj.mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
        targets = get_target_mesh_objects(context)
        if not targets:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
            
        success_count = 0
        for obj in targets:
            ok, msg = restore_mask_vertex_group(obj)
            if ok:
                success_count += 1
            else:
                self.report({'WARNING'}, f"{obj.name}: {msg}")
                
        if old_mode:
            bpy.ops.object.mode_set(mode=old_mode)
            
        self.report({'INFO'}, f"Restored mask group for {success_count}/{len(targets)} objects")
        return {'FINISHED'}


class RZM_OT_FillMaskWeights(bpy.types.Operator):
    bl_idname = "rzm.fill_mask_weights"
    bl_label = "Fill Mask (1.0)"
    bl_description = "Create and fill 'MASK ANTICOLLIDER' vertex group with 1.0 weight"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        old_mode = None
        if active_obj and active_obj.mode != 'OBJECT':
            old_mode = active_obj.mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
        targets = get_target_mesh_objects(context)
        if not targets:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
            
        for obj in targets:
            fill_mask_weights(obj, 1.0)
            
        if old_mode:
            bpy.ops.object.mode_set(mode=old_mode)
            
        self.report({'INFO'}, f"Filled mask group for {len(targets)} objects")
        return {'FINISHED'}


class RZM_OT_DeleteMaskVertexGroup(bpy.types.Operator):
    bl_idname = "rzm.delete_mask_vertex_group"
    bl_label = "Delete Mask VG"
    bl_description = "Delete the 'MASK ANTICOLLIDER' vertex group"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        old_mode = None
        if active_obj and active_obj.mode != 'OBJECT':
            old_mode = active_obj.mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
        targets = get_target_mesh_objects(context)
        if not targets:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
            
        success_count = 0
        for obj in targets:
            ok, msg = delete_mask_vertex_group(obj)
            if ok:
                success_count += 1
                
        if old_mode:
            bpy.ops.object.mode_set(mode=old_mode)
            
        self.report({'INFO'}, f"Deleted mask group for {success_count}/{len(targets)} objects")
        return {'FINISHED'}


class RZM_OT_DeleteMaskMeshAttribute(bpy.types.Operator):
    bl_idname = "rzm.delete_mask_mesh_attribute"
    bl_label = "Delete Mask Attribute"
    bl_description = "Delete the 'rzm_anticollider_mask' custom attribute"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        old_mode = None
        if active_obj and active_obj.mode != 'OBJECT':
            old_mode = active_obj.mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
        targets = get_target_mesh_objects(context)
        if not targets:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
            
        success_count = 0
        for obj in targets:
            ok, msg = delete_mask_attribute(obj)
            if ok:
                success_count += 1
                
        if old_mode:
            bpy.ops.object.mode_set(mode=old_mode)
            
        self.report({'INFO'}, f"Deleted mask attribute for {success_count}/{len(targets)} objects")
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_SaveMaskAttribute,
    RZM_OT_RestoreMaskVertexGroup,
    RZM_OT_FillMaskWeights,
    RZM_OT_DeleteMaskVertexGroup,
    RZM_OT_DeleteMaskMeshAttribute,
]
