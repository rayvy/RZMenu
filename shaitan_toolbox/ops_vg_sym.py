import bpy
from mathutils import Vector

def get_armature_linked_to_mesh(obj):
    """Finds the armature linked to the mesh through a modifier."""
    if not obj: return None
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            return mod.object
    return None

def calculate_all_vg_centers_optimized(obj):
    """
    Computes the centers of ALL vertex groups in a SINGLE pass over the mesh vertices.
    Returns a dictionary {group_index: world_center}.
    """
    if not obj or obj.type != 'MESH':
        return {}

    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh_eval = obj.evaluated_get(depsgraph)
    mesh = mesh_eval.to_mesh()

    num_groups = len(obj.vertex_groups)
    weighted_positions = [Vector((0.0, 0.0, 0.0)) for _ in range(num_groups)]
    total_weights = [0.0] * num_groups

    for v in mesh.vertices:
        for g in v.groups:
            if g.weight > 0.0001:
                weighted_positions[g.group] += v.co * g.weight
                total_weights[g.group] += g.weight

    mesh_eval.to_mesh_clear()

    world_centers = {}
    obj_matrix_world = obj.matrix_world
    for i in range(num_groups):
        if total_weights[i] > 0.0001:
            local_center = weighted_positions[i] / total_weights[i]
            world_centers[i] = obj_matrix_world @ local_center
            
    return world_centers

class RZM_ST_OT_SymmetrizeVGNames(bpy.types.Operator):
    bl_idname = "rzm_st.symmetrize_vg_names"
    bl_label = "Symmetrize VG Names"
    bl_description = "Find the mirrored group for the active one and rename both (and the bones)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        scene = context.scene

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "The active object must be a Mesh")
            return {'CANCELLED'}

        active_vg = obj.vertex_groups.active
        if not active_vg:
            self.report({'ERROR'}, "No active vertex group. Select a group in the list")
            return {'CANCELLED'}
        
        all_centers = calculate_all_vg_centers_optimized(obj)

        active_vg_center = all_centers.get(active_vg.index)
        if not active_vg_center:
            self.report({'ERROR'}, f"Could not compute the center of group '{active_vg.name}'. It may be empty.")
            return {'CANCELLED'}

        symmetry_direction = scene.rzm_st_symmetry_direction
        
        if symmetry_direction == 'DEFAULT':
            is_left_side = active_vg_center.x > -0.001
            is_right_side = active_vg_center.x < 0.001
        else:
            is_left_side = active_vg_center.x < 0.001
            is_right_side = active_vg_center.x > -0.001

        if not is_left_side and not is_right_side:
            self.report({'WARNING'}, "The active group is centered. Side cannot be determined.")
            return {'CANCELLED'}

        candidates = []
        for vg in obj.vertex_groups:
            if vg.index == active_vg.index or vg.name.upper().endswith(('.L', '.R')):
                continue

            vg_center = all_centers.get(vg.index)
            if not vg_center:
                continue

            if symmetry_direction == 'DEFAULT':
                is_opposite = (is_left_side and vg_center.x < -0.001) or \
                              (is_right_side and vg_center.x > 0.001)
            else:
                is_opposite = (is_left_side and vg_center.x > 0.001) or \
                              (is_right_side and vg_center.x < -0.001)
            
            if is_opposite:
                mirrored_pos = Vector((-active_vg_center.x, active_vg_center.y, active_vg_center.z))
                distance = (vg_center - mirrored_pos).length
                candidates.append((vg.name, distance))
        
        if not candidates:
            self.report({'INFO'}, "No suitable mirrored groups were found on the opposite side.")
            return {'CANCELLED'}

        candidates.sort(key=lambda x: x[1])

        def draw_menu(self, context):
            layout = self.layout
            direction_note = "(inverted)" if symmetry_direction == 'INVERTED' else ""
            layout.label(text=f"Direction: {symmetry_direction} {direction_note}")
            for vg_name, dist in candidates[:15]:
                op = layout.operator(RZM_ST_OT_SymmetrizeVGNamesConfirm.bl_idname, text=f"{vg_name} (dist: {dist:.3f})")
                op.active_vg_name = active_vg.name
                op.mirror_vg_name = vg_name
                op.is_active_left = is_left_side
                op.symmetry_direction = symmetry_direction

        context.window_manager.popup_menu(draw_menu, title="Choose mirrored group")
        return {'FINISHED'}

class RZM_ST_OT_SymmetrizeVGNamesConfirm(bpy.types.Operator):
    bl_idname = "rzm_st.symmetrize_vg_names_confirm"
    bl_label = "Confirm VG Symmetrize"
    bl_options = {'INTERNAL', 'UNDO'}

    active_vg_name: bpy.props.StringProperty()
    mirror_vg_name: bpy.props.StringProperty()
    is_active_left: bpy.props.BoolProperty()
    symmetry_direction: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.object
        scene = context.scene
        
        old_active_name = self.active_vg_name
        old_mirror_name = self.mirror_vg_name
        
        active_vg = obj.vertex_groups.get(old_active_name)
        mirror_vg = obj.vertex_groups.get(old_mirror_name)

        if not active_vg or not mirror_vg:
            self.report({'ERROR'}, "One of the groups was not found. Operation cancelled")
            return {'CANCELLED'}

        base_name = old_active_name.rsplit('.', 1)[0] if old_active_name.upper().endswith(('.L', '.R')) else old_active_name
        
        suffix_active = ".L" if self.is_active_left else ".R"
        suffix_mirror = ".R" if self.is_active_left else ".L"
            
        new_name_active = f"{base_name}{suffix_active}"
        new_name_mirror = f"{base_name}{suffix_mirror}"
        
        if new_name_mirror in obj.vertex_groups and new_name_mirror != mirror_vg.name:
             self.report({'ERROR'}, f"Group name '{new_name_mirror}' is already in use")
             return {'CANCELLED'}
        if new_name_active in obj.vertex_groups and new_name_active != active_vg.name:
             self.report({'ERROR'}, f"Group name '{new_name_active}' is already in use")
             return {'CANCELLED'}
        
        # 1. Безопасное переименование групп вершин
        temp_name_vg = "___TEMP_VG_RENAME___" + mirror_vg.name
        mirror_vg.name = temp_name_vg
        active_vg.name = new_name_active
        mirror_vg = obj.vertex_groups[temp_name_vg]
        mirror_vg.name = new_name_mirror
        
        # 2. Переименование связанных костей (если включено в настройках)
        rename_bones = scene.rzm_st_rename_associated_bones
        bones_renamed = 0
        
        if rename_bones:
            armature_obj = get_armature_linked_to_mesh(obj)
            if armature_obj and armature_obj.type == 'ARMATURE':
                armature_data = armature_obj.data
                
                bone_active = armature_data.bones.get(old_active_name)
                bone_mirror = armature_data.bones.get(old_mirror_name)
                
                if bone_active or bone_mirror:
                    temp_bone_name = "___TEMP_BONE_RENAME___"
                    
                    if bone_mirror:
                        bone_mirror.name = temp_bone_name
                        
                    if bone_active:
                        bone_active.name = new_name_active
                        bones_renamed += 1
                        
                    if bone_mirror:
                        b_mirror = armature_data.bones.get(temp_bone_name)
                        if b_mirror:
                            b_mirror.name = new_name_mirror
                            bones_renamed += 1

        direction_info = " (inverted)" if self.symmetry_direction == 'INVERTED' else ""
        
        if bones_renamed > 0:
            self.report({'INFO'}, f"Success{direction_info}: groups and {bones_renamed} bone(s) renamed to '{new_name_active}' and '{new_name_mirror}'")
        elif rename_bones and get_armature_linked_to_mesh(obj):
            self.report({'INFO'}, f"Groups renamed{direction_info}. Matching bones were not found.")
        else:
            self.report({'INFO'}, f"Groups renamed{direction_info}: '{new_name_active}' and '{new_name_mirror}'")
            
        return {'FINISHED'}

classes_to_register = [
    RZM_ST_OT_SymmetrizeVGNames,
    RZM_ST_OT_SymmetrizeVGNamesConfirm,
]
