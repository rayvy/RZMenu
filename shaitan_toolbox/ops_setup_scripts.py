import bpy
import bmesh
import time
import re
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
# 2.5. CLEAN DUPLICATE SIDE SUFFIXES
# ============================================================

SIDE_MARKER_RE = re.compile(r"\.[LR](?=$|[A-Z0-9_.-])", re.IGNORECASE)


def clean_duplicate_side_markers(name: str) -> str:
    matches = list(SIDE_MARKER_RE.finditer(name))
    if len(matches) <= 1:
        return name

    parts = []
    cursor = 0
    for match in matches[:-1]:
        parts.append(name[cursor:match.start()])
        cursor = match.end()
    parts.append(name[cursor:])
    return "".join(parts)


def linked_armatures_for_meshes(meshes):
    armatures = []
    seen = set()
    for obj in meshes:
        for mod in obj.modifiers:
            armature_obj = getattr(mod, "object", None)
            if mod.type == "ARMATURE" and armature_obj and armature_obj.type == "ARMATURE":
                if armature_obj.name not in seen:
                    seen.add(armature_obj.name)
                    armatures.append(armature_obj)
    return armatures


class RZM_ST_OT_CleanDuplicateSideMarkers(bpy.types.Operator):
    bl_idname = "rzm_st.clean_duplicate_side_markers"
    bl_label = "Clean Duplicate .L/.R Markers"
    bl_description = "Remove duplicate .L/.R/.l/.r markers from selected vertex groups and linked armature bones, keeping the last one"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes:
            self.report({'WARNING'}, "No selected mesh objects")
            return {'CANCELLED'}

        renamed_groups = 0
        renamed_bones = 0

        for obj in selected_meshes:
            for vg in obj.vertex_groups:
                new_name = clean_duplicate_side_markers(vg.name)
                if new_name != vg.name:
                    vg.name = new_name
                    renamed_groups += 1

        for armature_obj in linked_armatures_for_meshes(selected_meshes):
            for bone in armature_obj.data.bones:
                new_name = clean_duplicate_side_markers(bone.name)
                if new_name != bone.name:
                    bone.name = new_name
                    renamed_bones += 1

        try:
            context.view_layer.update()
        except Exception:
            pass

        self.report({'INFO'}, f"Cleaned side markers: {renamed_groups} vertex groups, {renamed_bones} bones")
        return {'FINISHED'}


# ============================================================
# 2.6. CLEAR SELECTED SHAPE KEY VERTICES
# ============================================================

class RZM_ST_OT_ClearSelectedShapeKeyVertices(bpy.types.Operator):
    bl_idname = "rzm_st.clear_selected_shape_key_vertices"
    bl_label = "Clear Selected Shape Key Vertices"
    bl_description = "Reset selected vertices in mesh shape keys back to Basis"
    bl_options = {'REGISTER', 'UNDO'}

    active_only: bpy.props.BoolProperty(
        name="Active Shape Key Only",
        description="Only clear the active shape key instead of all non-Basis shape keys",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None
            and obj.type == 'MESH'
            and obj.data is not None
            and obj.data.shape_keys is not None
            and len(obj.data.shape_keys.key_blocks) > 1
        )

    def _selected_vertex_indices(self, obj):
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            return [vert.index for vert in bm.verts if vert.select]

        return [vert.index for vert in obj.data.vertices if vert.select]

    def _target_shape_keys(self, obj):
        shape_keys = obj.data.shape_keys
        key_blocks = shape_keys.key_blocks

        if self.active_only:
            active_index = obj.active_shape_key_index
            if active_index <= 0 or active_index >= len(key_blocks):
                return []
            return [key_blocks[active_index]]

        return [key for key in key_blocks if key != shape_keys.reference_key]

    def execute(self, context):
        obj = context.active_object
        original_mode = obj.mode

        try:
            selected_indices = self._selected_vertex_indices(obj)
            if not selected_indices:
                self.report({'WARNING'}, "No selected vertices found.")
                return {'CANCELLED'}

            if obj.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            shape_keys = obj.data.shape_keys
            basis = shape_keys.reference_key
            target_keys = self._target_shape_keys(obj)
            if not target_keys:
                self.report({'WARNING'}, "No target shape keys to clear.")
                return {'CANCELLED'}

            reset_count = 0
            for key in target_keys:
                for vertex_index in selected_indices:
                    key.data[vertex_index].co = basis.data[vertex_index].co
                    reset_count += 1

            obj.data.update()

            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)

            scope = "active shape key" if self.active_only else f"{len(target_keys)} shape keys"
            self.report(
                {'INFO'},
                f"Cleared {len(selected_indices)} selected vertices in {scope} ({reset_count} coordinates reset)."
            )
            return {'FINISHED'}

        except Exception as e:
            if obj and obj.mode != original_mode:
                try:
                    bpy.ops.object.mode_set(mode=original_mode)
                except Exception:
                    pass
            self.report({'ERROR'}, f"Failed to clear shape key vertices: {e}")
            return {'CANCELLED'}


# ============================================================
# 2.7. APPLY BASIS TO BASE MESH (SYNC COORDINATES)
# ============================================================

class RZM_ST_OT_SyncBaseMeshToBasis(bpy.types.Operator):
    bl_idname = "rzm_st.sync_base_mesh_to_basis"
    bl_label = "Apply Basis to Base Mesh"
    bl_description = "Copy vertex coordinates from Basis shape key to the raw base mesh vertices to prevent shifting"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None
            and obj.type == 'MESH'
            and obj.data is not None
            and obj.data.shape_keys is not None
        )

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        shape_keys = mesh.shape_keys
        basis = shape_keys.reference_key
        
        if not basis:
            self.report({'ERROR'}, "No reference Basis shape key found.")
            return {'CANCELLED'}
            
        original_mode = obj.mode
        if obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
            
        try:
            # 1. Copy coords
            for v in mesh.vertices:
                v.co = basis.data[v.index].co
                
            mesh.update()
            
            self.report({'INFO'}, "Basis coordinates successfully synchronized with raw base mesh.")
                
            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
                
            return {'FINISHED'}
            
        except Exception as e:
            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
            self.report({'ERROR'}, f"Failed to sync Basis coordinates: {str(e)}")
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
        bpy.context.view_layer.objects.active = donor

        bpy.ops.object.data_transfer(
            data_type="VGROUP_WEIGHTS",
            use_create=False,
            vert_mapping=self.VERTEX_MAPPING,
            layers_select_src="ALL",
            layers_select_dst="NAME",
            mix_mode="REPLACE",
            mix_factor=1.0
        )

        # Restore the target as active so the rest of the operator continues
        # to work with the receiver, not the source.
        bpy.context.view_layer.objects.active = target

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


# ============================================================
# 5. ALIGN VERTEX GROUPS BY INDEX & NAMING
# ============================================================

class RZM_ST_OT_VGWeightAlign(bpy.types.Operator):
    bl_idname = "rzm_st.vg_weight_align"
    bl_label = "Align VG Index & Naming (Source)"
    bl_description = "Reorder and add missing vertex groups to match selected source mesh index-by-index, preserving vertex weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        target = context.active_object
        
        # Heuristic to find source/donor mesh
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        donor = None
        
        if len(selected_meshes) == 2:
            donors = [obj for obj in selected_meshes if obj != target]
            if donors:
                donor = donors[0]
                
        if not donor and context.scene.rzm_st_reference_mesh:
            donor = context.scene.rzm_st_reference_mesh
            
        if not donor:
            self.report({'ERROR'}, "Source mesh not found. Select 2 meshes (donor and active target), or set Reference Mesh.")
            return {'CANCELLED'}
            
        if donor == target:
            self.report({'ERROR'}, "Source mesh cannot be the same as active target mesh.")
            return {'CANCELLED'}
            
        original_mode = target.mode
        if target.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
            
        try:
            if target.data.users > 1:
                target.data = target.data.copy()
                
            # 1. Save active weights
            names_by_index = {vg.index: vg.name for vg in target.vertex_groups}
            weights_by_vertex = []
            for vertex in target.data.vertices:
                v_weights = {}
                for element in vertex.groups:
                    name = names_by_index.get(element.group)
                    if name is not None:
                        v_weights[name] = element.weight
                weights_by_vertex.append(v_weights)
                
            # 2. Get donor groups
            donor_order = [vg.name for vg in donor.vertex_groups]
            donor_set = set(donor_order)
            
            # 3. Get target groups
            target_names = [vg.name for vg in target.vertex_groups]
            target_set = set(target_names)
            
            missing = [name for name in donor_order if name not in target_set]
            extra = [name for name in target_names if name not in donor_set]
            
            # 4. Construct final order
            final_order = donor_order + extra
            
            # 5. Clear and recreate groups
            target.vertex_groups.clear()
            for name in final_order:
                target.vertex_groups.new(name=name)
                
            # 6. Apply weights back to vertex groups using new indices
            index_by_name = {vg.name: vg.index for vg in target.vertex_groups}
            
            bm = bmesh.new()
            bm.from_mesh(target.data)
            deform_layer = bm.verts.layers.deform.verify()
            bm.verts.ensure_lookup_table()
            
            if len(bm.verts) != len(weights_by_vertex):
                raise RuntimeError("Vertex count mismatch during alignment.")
                
            for bm_vertex, vertex_weights in zip(bm.verts, weights_by_vertex):
                deform = bm_vertex[deform_layer]
                for group_index in list(deform.keys()):
                    del deform[group_index]
                for name, weight in vertex_weights.items():
                    new_index = index_by_name.get(name)
                    if new_index is not None and weight > 0.0:
                        deform[new_index] = weight
                        
            bm.to_mesh(target.data)
            bm.free()
            target.data.update()
            
            # Restore mode
            if target.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
                
            self.report({'INFO'}, f"Aligned vertex groups index-by-index. Added {len(missing)} missing, kept {len(extra)} extra.")
            return {'FINISHED'}
            
        except Exception as e:
            if target.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
            self.report({'ERROR'}, f"Failed to align vertex groups: {str(e)}")
            return {'CANCELLED'}


# ============================================================
# 6. SETUP ARMATURE (STAGE 1 & 2)
# ============================================================

def classify_bone(name):
    nl = name.lower()
    
    # 1. Hidden Helpers
    if (any(x in nl for x in ["twist", "scale", "adj", "offset", "extra", "att", "tweak", "helper", "cf", "corrective", "knee", "elbow"]) or 
        name.startswith("+") or 
        # Helpers for limbs
        (any(limb in nl for limb in ["calf", "toe", "hand", "thigh", "foot", "clavicle", "upperarm", "forearm", "elbow"]) and
         not nl.startswith("bip001") and
         not any(f in nl for f in ["finger", "toe0.", "toe0 ", "toe0_"]))):
        return "Hidden Helpers"
        
    # 2. Face
    is_face = False
    if any(x in nl for x in ["face", "brow", "jaw", "lip", "cheek", "nose", "mouth", "tongue", "eyelash", "tooth", "teeth"]):
        is_face = True
    if "eye" in nl:
        is_face = True
    if "ear" in nl and "forearm" not in nl:
        is_face = True
        
    if is_face:
        if "head" not in nl or "bip001" not in nl:
            return "Face"
            
    # 3. Hair
    if any(x in nl for x in ["hair", "bang", "fringe", "lock", "ponytail", "pigtail", "ahoge"]):
        return "Hair"
        
    # 4. Skirt
    if "skirt" in nl:
        return "Skirt"
        
    # 5. Cloth
    if any(x in nl for x in ["cloth", "dress", "sleeve", "ribbon", "cape", "coat", "jacket", "pant", "apron", "frill", "belt", "bowknot", "cuff"]):
        return "Cloth"
        
    # 6. Weapon
    is_weapon = False
    if any(x in nl for x in ["weapon", "sword", "shield", "claymore", "marionette", "prop"]):
        is_weapon = True
    if "bow" in nl and "elbow" not in nl:
        is_weapon = True
        
    if is_weapon:
        return "Weapon"
        
    # 7. Main
    main_keywords = ["bip001", "pelvis", "spine", "neck", "head", "clavicle", "upperarm", "forearm", "hand", "thigh", "calf", "foot", "toe0", "finger"]
    if any(x in nl for x in main_keywords):
        return "Main"
        
    return "Other"


class RZM_ST_OT_SetupArmature(bpy.types.Operator):
    bl_idname = "rzm_st.setup_armature"
    bl_label = "Setup Armature"
    bl_description = "Standardize bone names, calculate bone roll to POS_X, sort into collections, and reposition bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        
        # Save current mode
        original_mode = obj.mode
        
        # Ensure we are in Object Mode to safely rename bones on the armature
        if obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
            
        try:
            # Stage 1: Rename bones
            renamed_count = 0
            for bone in armature.bones:
                old_name = bone.name
                name = old_name
                
                # Check left side
                has_l = False
                if " L " in name:
                    name = name.replace(" L ", " ")
                    has_l = True
                if " l " in name:
                    name = name.replace(" l ", " ")
                    has_l = True
                if "_L_" in name:
                    name = name.replace("_L_", "_")
                    has_l = True
                if "_l_" in name:
                    name = name.replace("_l_", "_")
                    has_l = True
                if name.endswith(" L"):
                    name = name[:-2]
                    has_l = True
                if name.endswith(" l"):
                    name = name[:-2]
                    has_l = True
                if name.endswith("_L"):
                    name = name[:-2]
                    has_l = True
                if name.endswith("_l"):
                    name = name[:-2]
                    has_l = True
                    
                # Check right side
                has_r = False
                if " R " in name:
                    name = name.replace(" R ", " ")
                    has_r = True
                if " r " in name:
                    name = name.replace(" r ", " ")
                    has_r = True
                if "_R_" in name:
                    name = name.replace("_R_", "_")
                    has_r = True
                if "_r_" in name:
                    name = name.replace("_r_", "_")
                    has_r = True
                if name.endswith(" R"):
                    name = name[:-2]
                    has_r = True
                if name.endswith(" r"):
                    name = name[:-2]
                    has_r = True
                if name.endswith("_R"):
                    name = name[:-2]
                    has_r = True
                if name.endswith("_r"):
                    name = name[:-2]
                    has_r = True
                    
                # Normalize spaces (e.g. double spaces to single space)
                while "  " in name:
                    name = name.replace("  ", " ")
                name = name.strip()
                
                # Append suffix
                if has_l:
                    if not name.endswith(".L"):
                        name = name + ".L"
                if has_r:
                    if not name.endswith(".R"):
                        name = name + ".R"
                        
                if name != old_name:
                    bone.name = name
                    renamed_count += 1
            
            self.report({'INFO'}, f"Stage 1 Complete: Renamed {renamed_count} bones.")
            
            # Stage 3: Themed Bone Collections (sorting bones)
            colls = {}
            for cat in ["Main", "Hidden Helpers", "Face", "Hair", "Skirt", "Cloth", "Weapon", "Other"]:
                c = armature.collections.get(cat)
                if not c:
                    c = armature.collections.new(cat)
                colls[cat] = c
                
            colls["Hidden Helpers"].is_visible = False
            
            for bone in list(armature.bones):
                cat = classify_bone(bone.name)
                # Unassign from other collections
                for c in list(armature.collections):
                    c.unassign(bone)
                # Assign to correct collection
                colls[cat].assign(bone)
                
            # Clean up empty non-custom collections
            for c in list(armature.collections):
                if c.name not in colls and len(c.bones) == 0:
                    armature.collections.remove(c)
                    
            self.report({'INFO'}, "Stage 3 Complete: Sorted bones into themed collections.")
            
            # Stage 4: Bone Repositioning (Parent-to-Child, ONLY Main bones)
            bpy.ops.object.mode_set(mode='EDIT')
            ebs = armature.edit_bones
            
            repositioned_count = 0
            for eb in ebs:
                nl = eb.name.lower()
                eb_cat = classify_bone(eb.name)
                
                # Only reposition Main skeleton bones! Skip all others (Hair, Face, Skirt, Helpers, Cloth, etc.)
                if eb_cat != "Main":
                    continue
                    
                # Special Case: Head goes straight up by 0.2m along global Z
                if "head" in nl and "bip001" in nl:
                    eb.tail = eb.head + Vector((0.0, 0.0, 0.2))
                    repositioned_count += 1
                    continue
                    
                children = eb.children
                # Filter children to be in the exact same collection (Main)
                valid_children = [child for child in children if classify_bone(child.name) == eb_cat]
                
                target_child = None
                if len(valid_children) == 1:
                    target_child = valid_children[0]
                elif len(valid_children) > 1:
                    # Multi-child priority rules
                    if "pelvis" in nl:
                        for child in valid_children:
                            if "spine" in child.name.lower():
                                target_child = child
                                break
                    elif "spine" in nl:
                        for child in valid_children:
                            if "spine" in child.name.lower() or "neck" in child.name.lower():
                                target_child = child
                                break
                    elif "neck" in nl:
                        for child in valid_children:
                            if "head" in child.name.lower():
                                target_child = child
                                break
                    elif "hand" in nl:
                        for child in valid_children:
                            if "finger2" in child.name.lower():
                                target_child = child
                                break
                        if not target_child:
                            for child in valid_children:
                                if "finger1" in child.name.lower():
                                    target_child = child
                                    break
                                    
                    # Fallback to first if priority didn't match
                    if not target_child:
                        target_child = valid_children[0]
                        
                if target_child:
                    diff = target_child.head - eb.head
                    if diff.length > 0.001:
                        eb.tail = target_child.head
                        repositioned_count += 1
                else:
                    # Terminal bone rules: Point in parent direction
                    if eb.parent:
                        parent_dir = (eb.parent.tail - eb.parent.head)
                        if parent_dir.length > 0.001:
                            eb.tail = eb.head + parent_dir.normalized() * eb.length
                            repositioned_count += 1

            # Stage 2: Calculate Roll (POS_X) - Executed AFTER repositioning
            for eb in ebs:
                eb.select = True
                eb.select_head = True
                eb.select_tail = True
            
            if ebs:
                ebs.active = ebs[0]
                
            # Perform roll calculation
            bpy.ops.armature.calculate_roll(type='POS_X')

            # Restore original mode
            if original_mode != 'EDIT':
                bpy.ops.object.mode_set(mode=original_mode)
                
            self.report({'INFO'}, f"Armature Setup Complete! Renamed {renamed_count} bones, sorted collections, repositioned {repositioned_count} bones, and calculated roll (POS_X).")
            return {'FINISHED'}
            
        except Exception as e:
            try:
                if obj.mode != original_mode:
                    bpy.ops.object.mode_set(mode=original_mode)
            except Exception:
                pass
            self.report({'ERROR'}, f"Failed to setup armature: {str(e)}")
            return {'CANCELLED'}


def get_shape_key_items(self, context):
    obj = context.active_object
    if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
        return [("", "No Shape Keys", "")]
    
    items = []
    basis = obj.data.shape_keys.reference_key
    for kb in obj.data.shape_keys.key_blocks:
        if kb == basis:
            continue
        items.append((kb.name, kb.name, f"Merge into {kb.name}"))
        
    if not items:
        return [("", "No Shape Keys", "")]
    return items


class RZM_ST_ShapeMergeItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    keep: bpy.props.BoolProperty(default=False)


class RZM_ST_OT_MergeShapeKeys(bpy.types.Operator):
    """Merge selected source shape keys into a target shape key by summing offsets"""
    bl_idname = "rzm_st.merge_shape_keys"
    bl_label = "Merge Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    create_new_target: bpy.props.BoolProperty(
        name="Create New Target",
        description="Merge into a new shape key instead of an existing one",
        default=False
    )
    
    new_target_name: bpy.props.StringProperty(
        name="New Target Name",
        description="Name of the new shape key to create and merge into",
        default="MergedShape"
    )

    target_shape: bpy.props.EnumProperty(
        name="Target Shape Key",
        description="The shape key that will receive the merged offsets",
        items=get_shape_key_items
    )

    filter_pattern: bpy.props.StringProperty(
        name="Filter Sources",
        description="Filter shape keys in the list below by name",
        default=""
    )

    delete_sources: bpy.props.BoolProperty(
        name="Delete Sources after Merge",
        description="Remove the matched source shape keys from the object after they are merged",
        default=True
    )

    sources: bpy.props.CollectionProperty(type=RZM_ST_ShapeMergeItem)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None
            and obj.type == 'MESH'
            and obj.data is not None
            and obj.data.shape_keys is not None
        )

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            self.report({'ERROR'}, "Active object is not a mesh or has no shape keys.")
            return {'CANCELLED'}

        # Clear and repopulate sources collection
        self.sources.clear()
        
        basis = obj.data.shape_keys.reference_key
        # Add all shape keys (except basis)
        for kb in obj.data.shape_keys.key_blocks:
            if kb == basis:
                continue
            item = self.sources.add()
            item.name = kb.name
            item.keep = False  # Always False by default! No auto-decisions.

        # Trigger properties dialog
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        layout.prop(self, "create_new_target")
        if self.create_new_target:
            layout.prop(self, "new_target_name")
            target_name = self.new_target_name.strip()
        else:
            layout.prop(self, "target_shape")
            target_name = self.target_shape
            
        layout.prop(self, "delete_sources")
        
        box = layout.box()
        box.label(text="Select Shape Keys to Merge:", icon='SHAPEKEY_DATA')
        
        # Search/Filter field (no auto-selection, just visual filtering)
        box.prop(self, "filter_pattern", icon='VIEWZOOM')
        
        col = box.column(align=True)
        any_drawn = False
        
        import fnmatch
        pattern = f"*{self.filter_pattern.lower()}*" if self.filter_pattern else "*"
        
        for item in self.sources:
            # Exclude current target shape key from the sources list
            if item.name == target_name:
                continue
            
            # Filter visually
            if not fnmatch.fnmatch(item.name.lower(), pattern):
                continue
                
            col.prop(item, "keep", text=item.name)
            any_drawn = True
            
        if not any_drawn:
            if self.filter_pattern:
                col.label(text="No shape keys match filter.", icon='INFO')
            else:
                col.label(text="No shape keys available.", icon='INFO')

    def execute(self, context):
        import numpy as np

        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            self.report({'ERROR'}, "Active object is not a mesh or has no shape keys.")
            return {'CANCELLED'}

        target_name = self.new_target_name.strip() if self.create_new_target else self.target_shape
        if not target_name:
            self.report({'ERROR'}, "No target shape key name specified.")
            return {'CANCELLED'}

        shape_keys = obj.data.shape_keys
        basis = shape_keys.reference_key
        num_verts = len(basis.data)

        # Retrieve selected shape key blocks from checked sources
        source_kbs = []
        for item in self.sources:
            if item.keep and item.name != target_name:
                kb = shape_keys.key_blocks.get(item.name)
                if kb:
                    source_kbs.append(kb)

        if not source_kbs:
            self.report({'WARNING'}, "No source shape keys were selected for merge.")
            return {'FINISHED'}

        # Get basis coordinates
        basis_co = np.empty(num_verts * 3, dtype=np.float32)
        basis.data.foreach_get("co", basis_co)
        basis_co = basis_co.reshape((num_verts, 3))

        total_offset = np.zeros((num_verts, 3), dtype=np.float32)
        target_kb = shape_keys.key_blocks.get(target_name)

        if target_kb:
            target_co = np.empty(num_verts * 3, dtype=np.float32)
            target_kb.data.foreach_get("co", target_co)
            target_co = target_co.reshape((num_verts, 3))
            total_offset += (target_co - basis_co)
        else:
            # Create new target shape key
            target_kb = obj.shape_key_add(name=target_name, from_mix=False)
            self.report({'INFO'}, f"Created new target shape key '{target_name}'")

        # Accumulate offsets from selected keys
        for src_kb in source_kbs:
            src_co = np.empty(num_verts * 3, dtype=np.float32)
            src_kb.data.foreach_get("co", src_co)
            src_co = src_co.reshape((num_verts, 3))
            total_offset += (src_co - basis_co)

        # Apply merged coordinates
        new_target_co = basis_co + total_offset
        target_kb.data.foreach_set("co", new_target_co.ravel())
        obj.data.update()

        # Delete sources if requested
        deleted_names = []
        if self.delete_sources:
            for kb in source_kbs:
                deleted_names.append(kb.name)
                obj.shape_key_remove(kb)

        msg = f"Merged {len(source_kbs)} shape keys into '{target_name}'."
        if deleted_names:
            msg += f" Deleted {len(deleted_names)} source keys."
        self.report({'INFO'}, msg)
        
        return {'FINISHED'}


# Регистрация классов
classes_to_register = [
    RZM_ST_ShapeMergeItem,
    RZM_ST_OT_MirrorCut,
    RZM_ST_OT_VGSymRename,
    RZM_ST_OT_CleanDuplicateSideMarkers,
    RZM_ST_OT_ClearSelectedShapeKeyVertices,
    RZM_ST_OT_DeleteAllVG,
    RZM_ST_OT_SmartTransfer,
    RZM_ST_OT_GenerateBones,
    RZM_ST_OT_VGWeightAlign,
    RZM_ST_OT_SyncBaseMeshToBasis,
    RZM_ST_OT_SetupArmature,
    RZM_ST_OT_MergeShapeKeys,
]
