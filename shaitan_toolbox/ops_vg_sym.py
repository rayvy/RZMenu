import bpy
import re
from collections import defaultdict
from mathutils import Vector


SIDE_SUFFIX_RE = re.compile(r"^(.*)\.([LRlr])(\.\d{3})?$")


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


def mirror_vertex_group_name(name, existing_names):
    """Return the mirrored .L/.R group name if that counterpart exists."""
    match = SIDE_SUFFIX_RE.match(name)
    if not match:
        return name

    base, side, numeric_suffix = match.groups()
    mirror_side = "R" if side == "L" else "L" if side == "R" else "r" if side == "l" else "l"
    mirrored_name = f"{base}.{mirror_side}{numeric_suffix or ''}"
    return mirrored_name if mirrored_name in existing_names else name


def vertex_weight_map(obj, vertex_index, group_names):
    weights = {}
    for item in obj.data.vertices[vertex_index].groups:
        if item.weight > 0.0 and 0 <= item.group < len(group_names):
            weights[group_names[item.group]] = float(item.weight)
    return weights


def remap_weight_map(weights, existing_names):
    remapped = defaultdict(float)
    for name, weight in weights.items():
        remapped[mirror_vertex_group_name(name, existing_names)] += weight
    return dict(remapped)


def average_weight_maps(first, second):
    averaged = {}
    for name in set(first) | set(second):
        weight = (first.get(name, 0.0) + second.get(name, 0.0)) * 0.5
        if weight > 0.0:
            averaged[name] = weight
    return averaged


def find_exact_mirror_vertex_pairs(mesh):
    coord_to_indices = defaultdict(list)
    for vertex in mesh.vertices:
        coord_to_indices[(vertex.co.x, vertex.co.y, vertex.co.z)].append(vertex.index)

    pairs = []
    center_indices = []
    skipped = 0
    visited = set()

    for coord, indices in coord_to_indices.items():
        if coord in visited:
            continue

        mirror_coord = (-coord[0], coord[1], coord[2])
        mirror_indices = coord_to_indices.get(mirror_coord)

        if mirror_indices is None:
            skipped += len(indices)
            visited.add(coord)
            continue

        if mirror_coord == coord:
            center_indices.extend(indices)
            visited.add(coord)
            continue

        visited.add(coord)
        visited.add(mirror_coord)

        if len(indices) != len(mirror_indices):
            skipped += len(indices) + len(mirror_indices)
            continue

        for left_index, right_index in zip(sorted(indices), sorted(mirror_indices)):
            pairs.append((left_index, right_index))

    return pairs, center_indices, skipped


def make_center_vertex_weight_map(weights, existing_names):
    result = dict(weights)
    processed = set()

    for name, weight in list(weights.items()):
        if name in processed:
            continue

        mirror_name = mirror_vertex_group_name(name, existing_names)
        if mirror_name == name:
            continue

        mirror_weight = weights.get(mirror_name, 0.0)
        average = (weight + mirror_weight) * 0.5
        if average > 0.0:
            result[name] = average
            result[mirror_name] = average
        else:
            result.pop(name, None)
            result.pop(mirror_name, None)
        processed.add(name)
        processed.add(mirror_name)

    return result


def write_vertex_weights(obj, vertex_maps):
    if not vertex_maps:
        return

    group_by_name = {vg.name: vg for vg in obj.vertex_groups}
    processed_indices = sorted(vertex_maps)
    original_locks = {vg.name: vg.lock_weight for vg in obj.vertex_groups}
    assigned_by_group = defaultdict(list)

    for vertex_index in processed_indices:
        for item in obj.data.vertices[vertex_index].groups:
            assigned_by_group[item.group].append(vertex_index)

    try:
        for vg in obj.vertex_groups:
            vg.lock_weight = False

        for vg in obj.vertex_groups:
            assigned_indices = assigned_by_group.get(vg.index)
            if assigned_indices:
                vg.remove(assigned_indices)

        batched = defaultdict(lambda: defaultdict(list))
        for vertex_index, weights in vertex_maps.items():
            for name, weight in weights.items():
                if weight > 0.0 and name in group_by_name:
                    batched[name][float(weight)].append(vertex_index)

        for name, weight_to_indices in batched.items():
            group = group_by_name[name]
            for weight, indices in weight_to_indices.items():
                group.add(indices, weight, 'REPLACE')
    finally:
        for vg in obj.vertex_groups:
            vg.lock_weight = original_locks.get(vg.name, False)


def symmetrize_mesh_vertex_weights_exact(obj):
    mesh = obj.data
    pairs, center_indices, skipped = find_exact_mirror_vertex_pairs(mesh)
    group_names = [vg.name for vg in obj.vertex_groups]
    existing_names = set(group_names)
    vertex_maps = {}

    for first_index, second_index in pairs:
        first_weights = vertex_weight_map(obj, first_index, group_names)
        second_weights = vertex_weight_map(obj, second_index, group_names)
        second_as_first = remap_weight_map(second_weights, existing_names)

        averaged_first = average_weight_maps(first_weights, second_as_first)
        averaged_second = remap_weight_map(averaged_first, existing_names)

        vertex_maps[first_index] = averaged_first
        vertex_maps[second_index] = averaged_second

    for vertex_index in center_indices:
        weights = vertex_weight_map(obj, vertex_index, group_names)
        vertex_maps[vertex_index] = make_center_vertex_weight_map(weights, existing_names)

    write_vertex_weights(obj, vertex_maps)
    mesh.update()

    return {
        "pairs": len(pairs),
        "center": len(center_indices),
        "skipped": skipped,
        "processed": len(vertex_maps),
    }


class RZM_ST_OT_SymmetrizeVGWeightsExact(bpy.types.Operator):
    bl_idname = "rzm_st.symmetrize_vg_weights_exact"
    bl_label = "Symmetrize VG Weights (Exact)"
    bl_description = "Symmetrize selected mesh vertex weights using exact raw mesh X mirror coordinates"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' and obj.vertex_groups for obj in context.selected_objects)

    def execute(self, context):
        targets = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.vertex_groups]
        if not targets:
            self.report({'ERROR'}, "Select at least one mesh with vertex groups")
            return {'CANCELLED'}

        active_obj = context.view_layer.objects.active
        original_mode = active_obj.mode if active_obj else 'OBJECT'
        if active_obj and original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        processed_objects = 0
        total_pairs = 0
        total_center = 0
        total_skipped = 0

        try:
            for obj in targets:
                result = symmetrize_mesh_vertex_weights_exact(obj)
                processed_objects += 1
                total_pairs += result["pairs"]
                total_center += result["center"]
                total_skipped += result["skipped"]
        finally:
            if active_obj:
                context.view_layer.objects.active = active_obj
                if original_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode=original_mode)

        self.report(
            {'INFO'},
            f"Symmetrized weights: {processed_objects} object(s), {total_pairs} mirror pairs, "
            f"{total_center} center verts, {total_skipped} skipped"
        )
        return {'FINISHED'}

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
    RZM_ST_OT_SymmetrizeVGWeightsExact,
    RZM_ST_OT_SymmetrizeVGNames,
    RZM_ST_OT_SymmetrizeVGNamesConfirm,
]
