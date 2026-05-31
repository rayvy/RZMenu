import bpy
import bmesh
import time
from mathutils import Vector

# ============================================================
# 1. MIRROR CUT X (CLEAR LEFT)
# ============================================================

class RZM_ST_OT_MirrorCut(bpy.types.Operator):
    bl_idname = "rzm_st.mirror_cut"
    bl_label = "Mirror Cut X (Clear Left)"
    bl_description = "Slice active mesh at X=0, fill the cut, and remove left/inner part"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        
        # Запоминаем текущий режим
        original_mode = obj.mode
        
        try:
            # Переходим в режим редактирования
            if obj.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            
            # Выделяем все меши
            bpy.ops.mesh.select_all(action='SELECT')
            
            # Разрезаем
            # plane_co=(0,0,0) - точка разреза
            # plane_no=(1,0,0) - направление разреза (нормаль)
            # clear_inner=True - удаляет "левую" часть
            # use_fill=True - закрывает дырку на месте разреза
            bpy.ops.mesh.bisect(
                plane_co=(0, 0, 0), 
                plane_no=(1, 0, 0), 
                use_fill=True, 
                clear_inner=True, 
                clear_outer=False
            )
            
            # Возвращаемся в исходный режим
            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
                
            self.report({'INFO'}, f"Объект {obj.name} разрезан, левая часть удалена.")
            return {'FINISHED'}
            
        except Exception as e:
            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
            self.report({'ERROR'}, f"Ошибка при разрезании: {str(e)}")
            return {'CANCELLED'}

# ============================================================
# 2. VG SYMMETRIZE RENAME (MEDIAN)
# ============================================================

class RZM_ST_OT_VGSymRename(bpy.types.Operator):
    bl_idname = "rzm_st.vg_sym_rename_all"
    bl_label = "Symmetrize VG Names (Median)"
    bl_description = "Automatically find and rename mirrored vertex group pairs based on vertex medians"
    bl_options = {'REGISTER', 'UNDO'}

    TOLERANCE_CENTER = 0.001
    TOLERANCE_MIRROR = 0.01
    SUFFIX_LEFT = ".L"
    SUFFIX_RIGHT = ".R"

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH' and context.active_object.vertex_groups

    def get_vertex_group_median_world(self, obj, group_index):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        mesh = obj.evaluated_get(depsgraph).to_mesh()

        total_weight = 0
        weighted_position = Vector((0, 0, 0))

        if not mesh.vertices or not obj.vertex_groups:
            obj.to_mesh_clear()
            return None
            
        group_name = obj.vertex_groups[group_index].name
        vgroup = obj.vertex_groups.get(group_name)
        if not vgroup:
            obj.to_mesh_clear()
            return None

        group_index = vgroup.index

        for v in mesh.vertices:
            for g in v.groups:
                if g.group == group_index:
                    weight = g.weight
                    if weight > 0:
                        total_weight += weight
                        weighted_position += v.co * weight
        
        obj.to_mesh_clear()

        if total_weight > 0:
            return obj.matrix_world @ (weighted_position / total_weight)
            
        return None

    def force_unique_vertex_group_name(self, obj, desired_name):
        if desired_name not in obj.vertex_groups:
            return desired_name

        existing_group = obj.vertex_groups[desired_name]
        base = desired_name
        if '.' in base and base.rsplit('.', 1)[1].isdigit():
            base = base.rsplit('.', 1)[0]
            
        index = 1
        while True:
            new_name = f"{base}.{str(index).zfill(3)}"
            if new_name not in obj.vertex_groups:
                existing_group.name = new_name
                break
            index += 1

        return desired_name

    def execute(self, context):
        obj = context.active_object
        
        original_mode = obj.mode
        if obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        try:
            # 1. Предварительный расчет медиан для всех групп
            group_medians = {}
            for group in obj.vertex_groups:
                median = self.get_vertex_group_median_world(obj, group.index)
                if median:
                    group_medians[group.name] = median

            # 2. Обработка групп: поиск центральных и парных
            processed_groups = set()
            center_groups = []
            unpaired_groups = []
            
            for name, median in group_medians.items():
                if abs(median.x) < self.TOLERANCE_CENTER:
                    center_groups.append(name)
                    processed_groups.add(name)
            
            # Поиск пар
            group_names = list(group_medians.keys())
            pair_count = 0
            for name in group_names:
                if name in processed_groups:
                    continue

                original_pos = group_medians[name]
                mirrored_pos = Vector((-original_pos.x, original_pos.y, original_pos.z))

                best_match = None
                min_dist = float('inf')

                for other_name, other_pos in group_medians.items():
                    if other_name in processed_groups or other_name == name:
                        continue
                    
                    dist = (mirrored_pos - other_pos).length
                    if dist < min_dist and dist < self.TOLERANCE_MIRROR:
                        min_dist = dist
                        best_match = other_name
                
                # Переименование
                if best_match:
                    group_a = obj.vertex_groups[name]
                    group_b = obj.vertex_groups[best_match]
                    pos_a = group_medians[name]

                    if pos_a.x > 0:
                        right_group, left_group = group_a, group_b
                    else:
                        right_group, left_group = group_b, group_a
                    
                    base_name = left_group.name
                    # Очищаем суффиксы .L/.R если они были случайно у базы
                    if base_name.upper().endswith(('.L', '.R')):
                        base_name = base_name[:-2]
                    
                    new_left_name = self.force_unique_vertex_group_name(obj, base_name + self.SUFFIX_LEFT)
                    new_right_name = self.force_unique_vertex_group_name(obj, base_name + self.SUFFIX_RIGHT)

                    right_group.name = new_right_name
                    left_group.name = new_left_name

                    processed_groups.add(name)
                    processed_groups.add(best_match)
                    if name in group_medians: del group_medians[name]
                    if best_match in group_medians: del group_medians[best_match]
                    pair_count += 1
                else:
                    unpaired_groups.append(name)
                    processed_groups.add(name)

            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
                
            self.report({'INFO'}, f"Симметризация завершена: Найдено {pair_count} пар. Не найдено пар для {len(unpaired_groups)} групп.")
            return {'FINISHED'}

        except Exception as e:
            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
            self.report({'ERROR'}, f"Ошибка при симметризации: {str(e)}")
            return {'CANCELLED'}

# ============================================================
# 3. DELETE ALL VERTEX GROUPS
# ============================================================

class RZM_ST_OT_DeleteAllVG(bpy.types.Operator):
    bl_idname = "rzm_st.delete_all_vg"
    bl_label = "Delete All Vertex Groups"
    bl_description = "Delete all vertex groups from all selected mesh objects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        return len(selected_meshes) > 0

    def execute(self, context):
        deleted_count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                vgs = len(obj.vertex_groups)
                obj.vertex_groups.clear()
                deleted_count += vgs
                
        self.report({'INFO'}, f"Удалено {deleted_count} групп вершин на выделенных объектах.")
        return {'FINISHED'}

# ============================================================
# 4. SMART WEIGHT TRANSFER
# ============================================================

class RZM_ST_OT_SmartTransfer(bpy.types.Operator):
    bl_idname = "rzm_st.smart_transfer"
    bl_label = "Smart Weight Transfer"
    bl_description = "Transfer missing weights from active/selected mesh, locking and preserving mask groups"
    bl_options = {'REGISTER', 'UNDO'}

    IGNORE_PREFIX = "mask"
    VERTEX_MAPPING = "POLYINTERP_NEAREST"

    @classmethod
    def poll(cls, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        # Требуется ровно 2 меш-объекта, при этом активный должен быть мешем
        return len(selected_meshes) == 2 and context.active_object and context.active_object.type == 'MESH'

    def is_mask(self, name: str) -> bool:
        return name.casefold().startswith(self.IGNORE_PREFIX.casefold())

    def get_group_names(self, obj, include_masks=True):
        if include_masks:
            return [vg.name for vg in obj.vertex_groups]
        return [vg.name for vg in obj.vertex_groups if not self.is_mask(vg.name)]

    def ensure_object_mode(self, obj):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

    def capture_weights(self, obj, allowed_names=None):
        names_by_index = {vg.index: vg.name for vg in obj.vertex_groups}
        result = []
        for vertex in obj.data.vertices:
            vertex_weights = {}
            for element in vertex.groups:
                name = names_by_index.get(element.group)
                if name is None:
                    continue
                if allowed_names is not None and name not in allowed_names:
                    continue
                vertex_weights[name] = element.weight
            result.append(vertex_weights)
        return result

    def rebuild_groups_and_weights(self, obj, ordered_names, weights_by_vertex):
        self.ensure_object_mode(obj)
        for vg in obj.vertex_groups:
            vg.lock_weight = False

        bpy.ops.object.vertex_group_remove(all=True)

        for name in ordered_names:
            obj.vertex_groups.new(name=name)

        index_by_name = {vg.name: vg.index for vg in obj.vertex_groups}
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            deform_layer = bm.verts.layers.deform.verify()
            bm.verts.ensure_lookup_table()

            if len(bm.verts) != len(weights_by_vertex):
                raise RuntimeError(
                    "Количество вершин изменилось во время операции. "
                    "Скрипт остановлен, чтобы не записать веса криво."
                )

            for bm_vertex, vertex_weights in zip(bm.verts, weights_by_vertex):
                deform = bm_vertex[deform_layer]
                for group_index in list(deform.keys()):
                    del deform[group_index]
                for name, weight in vertex_weights.items():
                    new_index = index_by_name.get(name)
                    if new_index is not None and weight != 0.0:
                        deform[new_index] = weight

            bm.to_mesh(obj.data)
            obj.data.update()
        finally:
            bm.free()

    def run_native_weight_transfer(self, donor, target):
        bpy.ops.object.select_all(action="DESELECT")
        donor.select_set(True)
        target.select_set(True)
        bpy.context.view_layer.objects.active = target

        bpy.ops.object.data_transfer(
            data_type="VGROUP_WEIGHTS",
            use_create=False,
            vert_mapping=self.VERTEX_MAPPING,
            layers_select_src="ALL",
            layers_select_dst="NAME",
            mix_mode="REPLACE",
            mix_factor=1.0
        )

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        target = context.active_object
        
        donors = [obj for obj in selected_meshes if obj != target]
        if len(donors) != 1:
            self.report({'ERROR'}, "Нужно выделить ровно два меша: Донор и Активный Таргет.")
            return {'CANCELLED'}
            
        donor = donors[0]
        original_mode = target.mode

        try:
            self.ensure_object_mode(target)

            if target.data.users > 1:
                target.data = target.data.copy()

            donor_order = self.get_group_names(donor, include_masks=False)
            donor_set = set(donor_order)

            target_masks = [vg.name for vg in target.vertex_groups if self.is_mask(vg.name)]
            target_normal = self.get_group_names(target, include_masks=False)

            common = [name for name in target_normal if name in donor_set]
            missing = [name for name in donor_order if target.vertex_groups.get(name) is None]
            extra = [name for name in target_normal if name not in donor_set]

            # 1. Удалить лишние группы таргета, кроме mask
            for name in extra:
                vg = target.vertex_groups.get(name)
                if vg:
                    target.vertex_groups.remove(vg)

            # 2. Создать отсутствующие группы заранее
            for name in missing:
                if target.vertex_groups.get(name) is None:
                    target.vertex_groups.new(name=name)

            # 3. Сохранить общие веса и маски
            protected_names = set(common) | set(target_masks)
            protected_weights = self.capture_weights(target, allowed_names=protected_names)

            # 4. Временно поставить замки
            for vg in target.vertex_groups:
                vg.lock_weight = (vg.name in protected_names)

            # 5. Выполнить Data Transfer
            if missing:
                self.run_native_weight_transfer(donor, target)

            # 6. Собрать итоговые веса
            transferred_weights = self.capture_weights(target)
            final_weights = []

            for transferred, protected in zip(transferred_weights, protected_weights):
                merged = {name: weight for name, weight in transferred.items() if name not in protected_names}
                merged.update(protected)
                final_weights.append(merged)

            # 7. Пересобрать порядок (донор вверху, маски внизу)
            final_order = donor_order + target_masks
            current_order = [vg.name for vg in target.vertex_groups]

            if current_order != final_order or missing or extra:
                self.rebuild_groups_and_weights(target, ordered_names=final_order, weights_by_vertex=final_weights)

            # 8. Финальные замки
            for vg in target.vertex_groups:
                vg.lock_weight = self.is_mask(vg.name)

            # Возврат в исходный режим
            if target.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
                
            self.report({'INFO'}, f"Smart Weight Transfer завершен успешно для {target.name}.")
            return {'FINISHED'}

        except Exception as e:
            if target.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
            self.report({'ERROR'}, f"Ошибка при Smart Transfer: {str(e)}")
            return {'CANCELLED'}


class RZM_ST_OT_GenerateBones(bpy.types.Operator):
    bl_idname = "rzm_st.generate_bones"
    bl_label = "Generate Missing Bones"
    bl_description = "Generate armature bones for missing vertex groups (hidden and grouped, excluding masks)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'WARNING'}, "No MESH objects selected")
            return {'CANCELLED'}

        processed_count = 0
        total_bones_created = 0
        total_bones_deleted = 0

        # Helper to check for mask prefix
        def is_mask(name: str) -> bool:
            return name.strip().casefold().startswith("mask")

        # Let's helper function to calculate VG centroids (world space)
        def get_vg_centroids(obj):
            vgs = obj.vertex_groups
            centroids = {}
            if not vgs:
                return centroids
            group_sums = {vg.index: Vector((0.0, 0.0, 0.0)) for vg in vgs}
            group_counts = {vg.index: 0 for vg in vgs}
            matrix_world = obj.matrix_world
            
            for v in obj.data.vertices:
                co = matrix_world @ v.co
                for g in v.groups:
                    idx = g.group
                    if idx in group_sums:
                        group_sums[idx] += co
                        group_counts[idx] += 1
                        
            for vg in vgs:
                idx = vg.index
                count = group_counts[idx]
                if count > 0:
                    centroids[vg.name] = group_sums[idx] / count
                else:
                    # Fallback to local center
                    local_center = sum((Vector(corner) for corner in obj.bound_box), Vector()) / 8
                    centroids[vg.name] = matrix_world @ local_center
            return centroids

        for obj in selected_objects:
            # Look for armature modifier
            armature_modifier = None
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object and mod.object.type == 'ARMATURE':
                    armature_modifier = mod
                    break
            
            if not armature_modifier:
                continue

            armature_obj = armature_modifier.object
            armature = armature_obj.data
            
            # Save original active & selection
            orig_selection = list(context.selected_objects)
            orig_active = context.view_layer.objects.active
            orig_obj_mode = obj.mode
            
            # 1. Calculate vertex group centroids
            centroids = get_vg_centroids(obj)
            
            # Find non-mask vertex groups
            mesh_vg_names = [vg.name for vg in obj.vertex_groups if not is_mask(vg.name)]
            
            # Identify missing bones
            existing_bones = {bone.name for bone in armature.bones}
            missing_bone_names = [name for name in mesh_vg_names if name not in existing_bones]
            
            # Identify mask bones to delete
            mask_bones_to_delete = [bone.name for bone in armature.bones if is_mask(bone.name)]

            # Switch armature to edit mode
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            
            context.view_layer.objects.active = armature_obj
            armature_obj.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
            
            edit_bones = armature.edit_bones
            
            # A. Delete mask bones
            deleted_count = 0
            for name in mask_bones_to_delete:
                eb = edit_bones.get(name)
                if eb:
                    edit_bones.remove(eb)
                    deleted_count += 1
            total_bones_deleted += deleted_count
            
            # B. Generate missing bones
            created_count = 0
            new_bone_names = []
            
            for name in missing_bone_names:
                # Calculate local coordinate for head from world centroid
                world_co = centroids.get(name)
                if world_co is None:
                    local_head = Vector((0.0, 0.0, 0.0))
                else:
                    local_head = armature_obj.matrix_world.inverted() @ world_co
                
                # Edit bone creation
                eb = edit_bones.new(name)
                eb.head = local_head
                eb.tail = local_head + Vector((0.0, 0.05, 0.0)) # Small offset
                
                # Find closest existing bone to parent to (excluding newly created ones)
                closest_bone = None
                min_dist = float('inf')
                
                for other_eb in edit_bones:
                    if other_eb.name == name or other_eb.name in missing_bone_names:
                        continue
                    dist = (other_eb.head - local_head).length
                    if dist < min_dist:
                        min_dist = dist
                        closest_bone = other_eb
                
                # If we found a closest bone and it is within 0.4 meters (local units)
                if closest_bone and min_dist < 0.4:
                    eb.parent = closest_bone
                    eb.use_connect = False
                
                # Hide edit bone
                eb.hide = True
                new_bone_names.append(name)
                created_count += 1
                
            total_bones_created += created_count
            
            # Go back to object mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # C. Assign bones to "Hidden Helpers" bone collection and hide them (in object mode)
            if new_bone_names:
                hidden_coll = armature.collections.get("Hidden Helpers")
                if hidden_coll is None:
                    hidden_coll = armature.collections.new("Hidden Helpers")
                    hidden_coll.is_visible = False
                
                for bname in new_bone_names:
                    bone = armature.bones.get(bname)
                    if bone:
                        hidden_coll.assign(bone)
                        bone.hide = True
            
            # Restore selection and active
            bpy.ops.object.select_all(action='DESELECT')
            for sel_obj in orig_selection:
                if sel_obj.name in bpy.data.objects:
                    sel_obj.select_set(True)
            context.view_layer.objects.active = orig_active
            if orig_active and orig_active.mode != orig_obj_mode:
                try:
                    bpy.ops.object.mode_set(mode=orig_obj_mode)
                except Exception:
                    pass
                
            processed_count += 1

        try: context.view_layer.update()
        except: pass

        self.report({'INFO'}, f"Processed {processed_count} mesh(es). Created {total_bones_created} missing bones, deleted {total_bones_deleted} mask bones.")
        return {'FINISHED'}


# Регистрация классов
classes_to_register = [
    RZM_ST_OT_MirrorCut,
    RZM_ST_OT_VGSymRename,
    RZM_ST_OT_DeleteAllVG,
    RZM_ST_OT_SmartTransfer,
    RZM_ST_OT_GenerateBones,
]
