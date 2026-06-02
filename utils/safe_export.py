# RZMenu/utils/safe_export.py
#
# Координатор безопасного экспорта.
#
# Архитектура sub-modules (порядок важен):
#
#   [0] MeshBackupSubModule
#       pre_export  → obj.data.copy() для каждого видимого меша в сцене
#                     (копии НЕ привязаны к сцене — экспортеры их не видят)
#       post_export → ВСЕГДА восстанавливает исходный меш obj.data = backup_mesh,
#                     тем самым удаляя любые временные слои (COLOR, TEXCOORD)
#                     и возвращая меш в исходное чистое состояние.
#
#   [1] XXMIMissingDataPredictorSubModule
#       pre_export  → добавляет COLOR / TEXCOORD если нет (только XXMI-игры)
#       post_export → опциональная очистка (основная очистка происходит в MeshBackupSubModule)
#
#   [2] CurveVFXPreviewSubModule
#       pre_export  → убирает VFX preview модификаторы с кривых
#       post_export → восстанавливает их
#
# Порядок __exit__:
#   Вызвать sub.post_export() у всех в обратном порядке (это всегда восстановит исходное состояние)
#   return False → исключение НЕ подавляется (Blender сам отрапортует об ошибке)

import bpy

# ══════════════════════════════════════════════════════════════════════════════
#  SUB-MODULE 00: Vertex Group Reorder
# ══════════════════════════════════════════════════════════════════════════════

class VertexGroupReorderSubModule:
    """
    Sub-module to ensure consistent Vertex Group (VG) ordering.
    It moves vertex groups starting with 'mask' (case-insensitive) to the end of the list,
    preserving their relative order. This change is permanent and not restored.
    """
    def __init__(self):
        pass

    def pre_export(self, context):
        # Получаем только экспортируемые объекты через функцию предиктора
        from .xxmi_data_predictor import get_export_targets
        targets = get_export_targets(context)
        
        print(f"[SafeExport] [VGReorder] Сдвиг вертекс-групп MASK в конец для {len(targets)} мешей...")
        
        for obj in targets:
            if obj.type != 'MESH' or not obj.vertex_groups:
                continue
                
            orig_names = [vg.name for vg in obj.vertex_groups]
            
            # Разделяем на обычные группы и маски
            non_masks = []
            masks = []
            for name in orig_names:
                if name.lower().startswith("mask"):
                    masks.append(name)
                else:
                    non_masks.append(name)
            
            # Целевой порядок: обычные группы первыми, маски в самом конце
            target_order = non_masks + masks
            
            self._reorder_vertex_groups(obj, target_order)

    def post_export(self, context):
        pass

    def restore(self, context):
        pass

    def _reorder_vertex_groups(self, obj, target_order):
        vgs = obj.vertex_groups
        current_names = [vg.name for vg in vgs]
        
        # Если порядок уже совпадает с целевым, ничего не делаем
        if current_names == target_order:
            return
            
        # Сохраняем имя активной группы
        active_name = vgs.active.name if vgs.active else None
        
        # Сохраняем состояния блокировок (lock_weight)
        vg_locks = {vg.name: vg.lock_weight for vg in vgs}
        
        # Сохраняем веса всех вершин
        vert_weights = {}
        for v in obj.data.vertices:
            v_weights = []
            for g in v.groups:
                if g.group < len(current_names):
                    name = current_names[g.group]
                    v_weights.append((name, g.weight))
            if v_weights:
                vert_weights[v.index] = v_weights
                
        # Очищаем все группы вершин
        vgs.clear()
        
        # Создаем их заново в новом порядке
        name_to_vg = {}
        for name in target_order:
            name_to_vg[name] = vgs.new(name=name)
            
        # Восстанавливаем веса вершин
        for v_idx, weights in vert_weights.items():
            for name, weight in weights:
                if name in name_to_vg:
                    name_to_vg[name].add([v_idx], weight, 'REPLACE')
                    
        # Устанавливаем блокировки (все MASK-группы принудительно лочим)
        for name, vg in name_to_vg.items():
            if name.lower().startswith("mask"):
                vg.lock_weight = True
            else:
                vg.lock_weight = vg_locks.get(name, False)
                
        # Восстанавливаем активную группу
        if active_name and active_name in vgs:
            vgs.active = vgs[active_name]


# ══════════════════════════════════════════════════════════════════════════════
#  SUB-MODULE 1: Mesh Backup (All visible meshes)
# ══════════════════════════════════════════════════════════════════════════════

class ModifierBakeMaskCleanupSubModule:
    """
    Temporarily bakes viewport modifiers into export targets and removes mask*
    vertex groups before the external exporter normalizes weights.
    """
    def __init__(self):
        self._states = {}
        self._temp_objects = []
        self._anchor_layouts = {}

    @staticmethod
    def _is_mask_group(name):
        return str(name or "").casefold().startswith("mask")

    @staticmethod
    def _should_apply_modifier(mod):
        try:
            from ..operators.gret_shape_key_utils import ignored_modifier_types
            ignored_types = ignored_modifier_types
        except Exception:
            ignored_types = {
                'CLOTH', 'COLLISION', 'DYNAMIC_PAINT', 'EXPLODE', 'FLUID',
                'OCEAN', 'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SOFT_BODY',
            }
        return mod.show_viewport and mod.type not in ignored_types and mod.type != 'ARMATURE'

    def pre_export(self, context):
        from .xxmi_data_predictor import get_export_targets
        targets = get_export_targets(context)
        self._anchor_layouts = self._collect_anchor_layouts(targets)

        print(f"[SafeExport] [BakeMasks] Preparing {len(targets)} mesh target(s)...")

        for obj in targets:
            if obj.type != 'MESH' or not obj.data:
                continue

            modifier_mask = [self._should_apply_modifier(mod) for mod in obj.modifiers]
            has_modifiers = any(modifier_mask)
            has_masks = any(self._is_mask_group(vg.name) for vg in obj.vertex_groups)
            anchor = getattr(obj, "rzm_export_vg_anchor", None)
            has_anchor = bool(anchor and anchor.type == 'MESH')
            if not has_modifiers and not has_masks and not has_anchor:
                continue

            temp_obj = None
            try:
                self._states[obj.name] = self._capture_state(obj, modifier_mask)
                temp_obj = self._make_temp_object(context, obj)
                self._temp_objects.append(temp_obj)

                if has_modifiers:
                    self._apply_modifiers_on_temp(context, temp_obj, modifier_mask)

                baked_mesh = temp_obj.data.copy()
                baked_mesh.name = f"_RZM_SAFE_BAKED_{obj.name}"
                self._validate_mesh_for_export(baked_mesh, obj.name)

                obj.data = baked_mesh
                self._copy_vertex_groups_without_masks(obj, temp_obj)
                self._apply_anchor_layout_if_needed(context, obj)
                self._disable_applied_modifiers(obj, modifier_mask)
                self._refresh_export_object(context, obj)
                self._remove_temp_object(temp_obj)

                print(
                    f"  [BakeMasks] {obj.name}: baked={has_modifiers}, "
                    f"removed_masks={has_masks}"
                )
            except Exception as e:
                import traceback
                print(f"  [BakeMasks] Failed for '{obj.name}': {e}")
                traceback.print_exc()
                self._remove_temp_object(temp_obj)

    def post_export(self, context):
        self._restore_all(context)

    def restore(self, context):
        self._restore_all(context)

    def _capture_state(self, obj, modifier_mask):
        return {
            'obj': obj,
            'data': obj.data,
            'modifier_visibility': [
                (mod.name, mod.show_viewport)
                for mod in obj.modifiers
            ],
            'applied_modifier_names': [
                mod.name for mod, apply in zip(obj.modifiers, modifier_mask) if apply
            ],
            'vertex_groups': self._capture_vertex_groups(obj),
        }

    def _capture_vertex_groups(self, obj):
        group_names = [vg.name for vg in obj.vertex_groups]
        locks = {vg.name: vg.lock_weight for vg in obj.vertex_groups}
        weights = {}

        for vert in obj.data.vertices:
            entries = []
            for item in vert.groups:
                if item.group < len(group_names):
                    entries.append((group_names[item.group], item.weight))
            if entries:
                weights[vert.index] = entries

        return {
            'names': group_names,
            'locks': locks,
            'weights': weights,
            'active_index': obj.vertex_groups.active_index,
        }

    def _make_temp_object(self, context, obj):
        temp_obj = obj.copy()
        temp_obj.name = f"_RZM_SAFE_BAKE_{obj.name}"
        temp_obj.data = obj.data.copy()
        temp_obj.data.name = f"_RZM_SAFE_BAKE_MESH_{obj.name}"
        temp_obj.hide_viewport = False
        temp_obj.hide_set(False)
        temp_obj.hide_select = False

        collection = obj.users_collection[0] if obj.users_collection else context.scene.collection
        collection.objects.link(temp_obj)
        return temp_obj

    def _apply_modifiers_on_temp(self, context, temp_obj, modifier_mask):
        mask = list(modifier_mask[:32]) + [False] * max(0, 32 - len(modifier_mask))
        prev_active = context.view_layer.objects.active
        prev_selected = list(context.selected_objects)

        try:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')
            temp_obj.select_set(True)
            context.view_layer.objects.active = temp_obj
            with context.temp_override(
                object=temp_obj,
                active_object=temp_obj,
                selected_objects=[temp_obj],
                selected_editable_objects=[temp_obj],
            ):
                bpy.ops.rz.shape_key_apply_modifiers(modifier_mask=mask)
        finally:
            bpy.ops.object.select_all(action='DESELECT')
            for selected_obj in prev_selected:
                if selected_obj and selected_obj.name in bpy.data.objects:
                    selected_obj.select_set(True)
            if prev_active and prev_active.name in bpy.data.objects:
                context.view_layer.objects.active = prev_active

    def _copy_vertex_groups_without_masks(self, target_obj, source_obj):
        target_obj.vertex_groups.clear()
        source_group_names = [vg.name for vg in source_obj.vertex_groups]
        name_to_group = {}

        for source_vg in source_obj.vertex_groups:
            if self._is_mask_group(source_vg.name):
                continue
            target_vg = target_obj.vertex_groups.new(name=source_vg.name)
            target_vg.lock_weight = source_vg.lock_weight
            name_to_group[source_vg.name] = target_vg

        for vert in source_obj.data.vertices:
            for item in vert.groups:
                if item.group >= len(source_group_names):
                    continue
                group_name = source_group_names[item.group]
                target_vg = name_to_group.get(group_name)
                if target_vg:
                    target_vg.add([vert.index], item.weight, 'REPLACE')

    def _disable_applied_modifiers(self, obj, modifier_mask):
        for mod, apply in zip(obj.modifiers, modifier_mask):
            if apply:
                mod.show_viewport = False

    def _validate_mesh_for_export(self, mesh, obj_name):
        try:
            changed = mesh.validate(clean_customdata=False)
            mesh.update()
            if changed:
                print(f"  [BakeMasks] {obj_name}: baked mesh validation fixed invalid data")
        except Exception as e:
            print(f"  [BakeMasks] WARN: baked mesh validation failed for '{obj_name}': {e}")

    def _refresh_export_object(self, context, obj):
        try:
            obj.data.update()
            context.view_layer.update()
        except Exception as e:
            print(f"  [BakeMasks] WARN: export mesh refresh failed for '{obj.name}': {e}")

    def _remove_temp_object(self, temp_obj):
        if not temp_obj:
            return

        if temp_obj in self._temp_objects:
            self._temp_objects.remove(temp_obj)

        try:
            if temp_obj.name in bpy.data.objects:
                temp_data = temp_obj.data
                bpy.data.objects.remove(temp_obj, do_unlink=True)
                if temp_data and temp_data.users == 0:
                    bpy.data.meshes.remove(temp_data, do_unlink=True)
        except Exception as e:
            print(f"  [BakeMasks] Temp cleanup failed: {e}")

    def _restore_all(self, context):
        if not self._states and not self._temp_objects:
            return

        print(f"[SafeExport] [BakeMasks] Restoring {len(self._states)} mesh target(s)...")

        for state in list(self._states.values()):
            obj = state.get('obj')
            if not obj or obj.name not in bpy.data.objects:
                continue

            try:
                old_data = obj.data
                obj.data = state['data']
                self._restore_vertex_groups(obj, state['vertex_groups'])

                for mod_name, show_viewport in state['modifier_visibility']:
                    mod = obj.modifiers.get(mod_name)
                    if mod:
                        mod.show_viewport = show_viewport

                if old_data and old_data != state['data'] and old_data.users == 0:
                    bpy.data.meshes.remove(old_data, do_unlink=True)
            except Exception as e:
                import traceback
                print(f"  [BakeMasks] Restore failed for '{obj.name}': {e}")
                traceback.print_exc()

        for temp_obj in self._temp_objects:
            try:
                if temp_obj and temp_obj.name in bpy.data.objects:
                    temp_data = temp_obj.data
                    bpy.data.objects.remove(temp_obj, do_unlink=True)
                    if temp_data and temp_data.users == 0:
                        bpy.data.meshes.remove(temp_data, do_unlink=True)
            except Exception as e:
                print(f"  [BakeMasks] Temp cleanup failed: {e}")

        self._states.clear()
        self._temp_objects.clear()
        self._anchor_layouts.clear()

        try:
            context.view_layer.update()
        except Exception as e:
            print(f"[SafeExport] [BakeMasks] WARN: restore view_layer.update() failed: {e}")

    def _restore_vertex_groups(self, obj, state):
        obj.vertex_groups.clear()
        name_to_group = {}

        for name in state['names']:
            vg = obj.vertex_groups.new(name=name)
            vg.lock_weight = state['locks'].get(name, False)
            name_to_group[name] = vg

        for vert_index, entries in state['weights'].items():
            for name, weight in entries:
                vg = name_to_group.get(name)
                if vg:
                    vg.add([vert_index], weight, 'REPLACE')

        active_index = state.get('active_index', 0)
        if obj.vertex_groups and 0 <= active_index < len(obj.vertex_groups):
            obj.vertex_groups.active_index = active_index

    def _collect_anchor_layouts(self, targets):
        layouts = {}
        for obj in targets:
            anchor = getattr(obj, "rzm_export_vg_anchor", None)
            if not anchor or anchor.type != 'MESH':
                continue
            if anchor.name in layouts:
                continue
            layouts[anchor.name] = [
                vg.name for vg in anchor.vertex_groups
                if not self._is_mask_group(vg.name)
            ]
        return layouts

    def _apply_anchor_layout_if_needed(self, context, obj):
        anchor = getattr(obj, "rzm_export_vg_anchor", None)
        if not anchor or anchor.type != 'MESH':
            return

        target_order = self._anchor_layouts.get(anchor.name)
        if target_order is None:
            target_order = [
                vg.name for vg in anchor.vertex_groups
                if not self._is_mask_group(vg.name)
            ]

        if not target_order:
            return

        self._rebuild_vertex_groups_in_order(obj, target_order)
        self._normalize_vertex_groups(context, obj)
        print(f"  [BakeMasks] {obj.name}: aligned VG layout to anchor '{anchor.name}' ({len(target_order)} groups)")

    def _rebuild_vertex_groups_in_order(self, obj, target_order):
        current_names = [vg.name for vg in obj.vertex_groups]
        locks = {vg.name: vg.lock_weight for vg in obj.vertex_groups}
        weights_by_name = {}

        for vert in obj.data.vertices:
            for item in vert.groups:
                if item.group >= len(current_names):
                    continue
                group_name = current_names[item.group]
                if group_name not in target_order:
                    continue
                weights_by_name.setdefault(group_name, []).append((vert.index, item.weight))

        obj.vertex_groups.clear()
        name_to_group = {}

        for name in target_order:
            vg = obj.vertex_groups.new(name=name)
            vg.lock_weight = locks.get(name, False)
            name_to_group[name] = vg

        for name, entries in weights_by_name.items():
            vg = name_to_group.get(name)
            if not vg:
                continue
            for vert_index, weight in entries:
                vg.add([vert_index], weight, 'REPLACE')

    def _normalize_vertex_groups(self, context, obj):
        if not obj.vertex_groups:
            return

        prev_active = context.view_layer.objects.active
        prev_selected = list(context.selected_objects)
        prev_locks = {vg.name: vg.lock_weight for vg in obj.vertex_groups}

        try:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            for vg in obj.vertex_groups:
                vg.lock_weight = False

            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            with context.temp_override(
                object=obj,
                active_object=obj,
                selected_objects=[obj],
                selected_editable_objects=[obj],
            ):
                bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        finally:
            for vg in obj.vertex_groups:
                vg.lock_weight = prev_locks.get(vg.name, False)

            bpy.ops.object.select_all(action='DESELECT')
            for selected_obj in prev_selected:
                if selected_obj and selected_obj.name in bpy.data.objects:
                    selected_obj.select_set(True)
            if prev_active and prev_active.name in bpy.data.objects:
                context.view_layer.objects.active = prev_active


class MeshBackupSubModule:
    """
    Резервное копирование и восстановление всей геометрии (Mesh) для всех видимых мешей.
    Это гарантирует, что любые изменения меша (добавление COLOR/TEXCOORD,
    изменение/запекание shape keys, применение модификаторов) будут полностью
    откачены после завершения экспорта.
    """
    def __init__(self):
        # Словарь {obj_name: (obj_ref, backup_mesh)}
        self._backups = {}

    def pre_export(self, context):
        self._backups.clear()
        
        # Получаем только экспортируемые объекты через функцию предиктора
        from .xxmi_data_predictor import get_export_targets
        targets = get_export_targets(context)
            
        print(f"[SafeExport] [MeshBackup] Создание резервных копий для {len(targets)} мешей...")
        
        for obj in targets:
            try:
                # Копируем только блок данных Mesh
                backup = obj.data.copy()
                backup.name = f"_RZM_SAFE_BACKUP_{obj.name}"
                self._backups[obj.name] = (obj, backup)
            except Exception as e:
                print(f"  [MeshBackup] Не удалось создать копию для '{obj.name}': {e}")

    def post_export(self, context):
        """
        Штатное и аварийное восстановление.
        Всегда возвращает оригинальный меш на место и удаляет измененный/временный.
        """
        if not self._backups:
            return

        print(f"[SafeExport] [MeshBackup] Восстановление исходного состояния для {len(self._backups)} мешей...")
        
        for obj_name, (obj, backup) in self._backups.items():
            try:
                # Проверяем, существует ли еще объект
                if obj and obj.name in context.scene.objects:
                    old_data = obj.data
                    obj.data = backup
                    
                    # Безопасно удаляем измененный меш
                    if old_data and old_data.users == 0:
                        bpy.data.meshes.remove(old_data, do_unlink=True)
            except Exception as e:
                print(f"  [MeshBackup] Ошибка при восстановлении '{obj_name}': {e}")
                
        self._backups.clear()
        print("[SafeExport] [MeshBackup] Восстановление завершено.")
        
    def restore(self, context):
        # Восстановление происходит в post_export, вызываем его
        self.post_export(context)


# ══════════════════════════════════════════════════════════════════════════════
#  SUB-MODULE 2: Curve VFX Preview
# ══════════════════════════════════════════════════════════════════════════════

class CurveVFXPreviewSubModule:
    """Sub-module to safely remove and restore VFX Curve previews during export."""

    def __init__(self):
        self.affected_curves = []

    def pre_export(self, context):
        self.affected_curves = []
        for obj in context.scene.objects:
            if obj.type != 'CURVE':
                continue

            is_vfx_curve = False
            if "RZM.CURVE_VFX" in obj:
                is_vfx_curve = True
            elif hasattr(obj, "rzm_curve_vfx") and obj.rzm_curve_vfx:
                is_vfx_curve = True

            if not is_vfx_curve:
                continue

            preview_mods = [
                mod for mod in obj.modifiers
                if mod.name.lower().startswith("rzm_vfx_preview")
            ]

            if preview_mods:
                for mod in preview_mods:
                    obj.modifiers.remove(mod)
                self.affected_curves.append(obj.name)
                print(f"[SafeExport] [CurveVFX] Removed {len(preview_mods)} modifiers from curve '{obj.name}'")

    def restore(self, context):
        self.post_export(context)

    def post_export(self, context):
        if not self.affected_curves:
            return

        from ..operators.vfx_preview_geonode_apply import apply_vfx_preview_to_object

        for name in self.affected_curves:
            obj = context.scene.objects.get(name)
            if not obj:
                continue
            try:
                apply_vfx_preview_to_object(context, obj)
                print(f"[SafeExport] [CurveVFX] Restored preview on curve '{obj.name}'")
            except Exception as e:
                print(f"[SafeExport] [CurveVFX] Failed to restore preview on curve '{obj.name}': {e}")

        self.affected_curves = []


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN: SafeExport context manager
# ══════════════════════════════════════════════════════════════════════════════

class SafeExport:
    """
    Контекстный менеджер безопасного экспорта.

    Использование:
        with SafeExport(context):
            bpy.ops.xxmi.exportadvanced()

    Гарантирует:
    - Откат всех изменений после экспорта (независимо от успеха/ошибки)
    - Аварийное восстановление shape keys при краше экспортера
    - Добавление недостающих COLOR/TEXCOORD перед XXMI (и их удаление после)
    - Удаление VFX preview модификаторов перед экспортом (восстановление после)
    """

    def __init__(self, context):
        self.context = context

        # Импортируем здесь чтобы избежать circular imports при загрузке модуля
        from .xxmi_data_predictor import XXMIMissingDataPredictorSubModule

        # Читаем настройку очистки временных слоев из настроек аддона
        addon_name = __package__.split(".")[0] if "." in __package__ else __package__
        pref = context.preferences.addons[addon_name].preferences
        temp_cleanup = getattr(pref, "safe_export_temp_cleanup", False)

        if temp_cleanup:
            # Альтернативный экспериментальный режим (удаление слоев после экспорта)
            self.sub_modules = [
                # VertexGroupReorderSubModule(),     # Standalone candidate: manually move mask* VG to the end.
                ModifierBakeMaskCleanupSubModule(),  # [0] Bake modifiers, export without mask* VG, then restore.
                # MeshBackupSubModule(),             # Отключено: вызывает краши depsgraph из-за подмены мешей
                XXMIMissingDataPredictorSubModule(), # [1] Добавляем COLOR/TEXCOORD
                CurveVFXPreviewSubModule(),          # [2] Убираем VFX preview
            ]
        else:
            # Режим по умолчанию (COLOR/TEXCOORD добавляются перманентно)
            predictor = XXMIMissingDataPredictorSubModule()
            predictor.disable_cleanup = True

            self.sub_modules = [
                # VertexGroupReorderSubModule(),     # Standalone candidate: manually move mask* VG to the end.
                ModifierBakeMaskCleanupSubModule(),  # [0] Bake modifiers, export without mask* VG, then restore.
                predictor,                           # [1] Добавляем COLOR/TEXCOORD перманентно
                # MeshBackupSubModule(),             # Отключено: вызывает краши depsgraph из-за подмены мешей
                CurveVFXPreviewSubModule(),          # [2] Убираем VFX preview
            ]

    def __enter__(self):
        print("[SafeExport] ═══ Старт pre-export ═══")

        # Принудительная синхронизация depsgraph перед началом работы.
        # Предотвращает EXCEPTION_ACCESS_VIOLATION в build_materials при
        # работе с мешами у которых есть модификаторы или shape keys.
        try:
            self.context.view_layer.update()
        except Exception as e:
            print(f"[SafeExport] WARN: view_layer.update() failed: {e}")

        for sub in self.sub_modules:
            try:
                sub.pre_export(self.context)
            except Exception as e:
                import traceback
                print(f"[SafeExport] ОШИБКА в pre_export ({sub.__class__.__name__}): {e}")
                traceback.print_exc()

        # Повторная синхронизация после добавления UV/COLOR слоёв предиктором,
        # чтобы XXMI Tools видел актуальное состояние мешей.
        try:
            self.context.view_layer.update()
        except Exception as e:
            print(f"[SafeExport] WARN: post-pre_export view_layer.update() failed: {e}")

        print("[SafeExport] ═══ pre-export завершён ═══")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        had_error = exc_type is not None

        if had_error:
            print(f"[SafeExport] ══ ОШИБКА ЭКСПОРТА: {exc_type.__name__}: {exc_val} ══")
            print("[SafeExport] Запуск аварийного restore (обратный порядок)...")
            for sub in reversed(self.sub_modules):
                if hasattr(sub, 'restore'):
                    try:
                        sub.restore(self.context)
                    except Exception as e:
                        import traceback
                        print(f"[SafeExport] ОШИБКА в restore ({sub.__class__.__name__}): {e}")
                        traceback.print_exc()

        print("[SafeExport] ═══ Старт post-export cleanup ═══")
        for sub in reversed(self.sub_modules):
            try:
                sub.post_export(self.context)
            except Exception as e:
                import traceback
                print(f"[SafeExport] ОШИБКА в post_export ({sub.__class__.__name__}): {e}")
                traceback.print_exc()

        try:
            self.context.view_layer.update()
        except Exception as e:
            print(f"[SafeExport] WARN: post-export view_layer.update() failed: {e}")

        print("[SafeExport] ═══ Done ═══")

        # False = не подавляем исключение. Blender сам покажет ошибку оператору.
        return False
