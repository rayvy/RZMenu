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

class AnchorLayoutCleanupSubModule:
    """
    Handles vertex group reordering to match the anchor object if rzm_export_vg_anchor is set.
    """
    def __init__(self):
        self._temp_objects = []
        self._original_states = {}
        self._prev_active = None
        self._prev_selected = []

    def pre_export(self, context):
        self._temp_objects.clear()
        self._original_states.clear()
        self._prev_active = context.view_layer.objects.active
        self._prev_selected = list(context.selected_objects)

        targets_by_obj = self._collect_anchor_targets(context)
        if not targets_by_obj:
            return

        print(f"[SafeExport] [AnchorLayout] Creating temporary export instances for {len(targets_by_obj)} mesh target(s)...")

        for obj, component_names in targets_by_obj.items():
            if obj.type != 'MESH' or not obj.data:
                continue

            anchor = getattr(obj, "rzm_export_vg_anchor", None)
            if not anchor or anchor.type != 'MESH' or not anchor.vertex_groups:
                continue

            original_state = self._store_original_object_state(obj)
            self._original_states[obj] = original_state
            obj.name = original_state['temp_source_name']

            for coll in original_state['collections']:
                try:
                    coll.objects.unlink(obj)
                except Exception:
                    pass

            for index, component_name in enumerate(component_names):
                temp_obj = self._make_temp_object(context, obj, original_state, component_name, index, len(component_names))
                self._prepare_anchor_layout(context, temp_obj, anchor)
                self._temp_objects.append(temp_obj)

        if self._temp_objects:
            bpy.ops.object.select_all(action='DESELECT')
            for temp_obj in self._temp_objects:
                try:
                    temp_obj.select_set(True)
                except Exception:
                    pass
            context.view_layer.objects.active = self._temp_objects[0]
            context.view_layer.update()

    def post_export(self, context):
        self._restore_all(context)

    def restore(self, context):
        self._restore_all(context)

    def _collect_anchor_targets(self, context):
        ordered = {}

        try:
            from .component_collector import ComponentCollector
            components = ComponentCollector(context).get_components(force_fallback=False)
        except Exception as e:
            print(f"  [AnchorLayout] Component collection failed, falling back to scene scan: {e}")
            components = {}

        for component_name, objects in (components or {}).items():
            for obj in objects:
                if self._has_export_anchor(obj):
                    ordered.setdefault(obj, [])
                    if component_name not in ordered[obj]:
                        ordered[obj].append(component_name)

        for obj in context.scene.objects:
            if self._has_export_anchor(obj):
                ordered.setdefault(obj, [None])

        return ordered

    def _has_export_anchor(self, obj):
        if not obj or obj.type != 'MESH' or not obj.data:
            return False
        if "RZM_BACKUP" in obj.name or "_RZM_SAFE" in obj.name:
            return False
        anchor = getattr(obj, "rzm_export_vg_anchor", None)
        return bool(anchor and anchor.type == 'MESH' and anchor.vertex_groups)

    def _store_original_object_state(self, obj):
        original_name = obj.name
        return {
            'name': original_name,
            'temp_source_name': f"{original_name}_RZM_SAFE_SOURCE",
            'collections': list(obj.users_collection),
            'hide_viewport': obj.hide_viewport,
            'hide_render': obj.hide_render,
            'hide_select': obj.hide_select,
            'selected': obj.select_get(),
        }

    def _make_temp_object(self, context, source_obj, original_state, component_name, index, total_count):
        temp_obj = source_obj.copy()
        temp_obj.data = source_obj.data.copy()
        temp_obj.name = self._make_temp_name(original_state['name'], component_name, index, total_count)
        temp_obj.data.name = f"{temp_obj.name}_Mesh"
        temp_obj.hide_viewport = False
        temp_obj.hide_render = False
        temp_obj.hide_select = False
        temp_obj["RZM_SAFE_EXPORT_TEMP"] = True
        temp_obj["RZM_SAFE_EXPORT_SOURCE"] = original_state['name']
        if component_name:
            temp_obj["RZM_SAFE_EXPORT_COMPONENT"] = component_name

        target_collections = self._component_collections(original_state['collections'], component_name)
        if not target_collections:
            target_collections = [context.scene.collection]

        for coll in target_collections:
            try:
                coll.objects.link(temp_obj)
            except RuntimeError:
                pass

        return temp_obj

    def _make_temp_name(self, original_name, component_name, index, total_count):
        if total_count <= 1 or not component_name:
            return original_name

        safe_component = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in component_name)
        if safe_component.lower() in original_name.lower():
            return original_name

        return f"{safe_component}_{original_name}"

    def _component_collections(self, collections, component_name):
        if not component_name:
            return collections

        matches = [
            coll for coll in collections
            if self._component_name_matches(coll.name, component_name)
        ]
        return matches or collections

    @staticmethod
    def _component_name_matches(candidate, component_name):
        def clean(value):
            return "".join(ch.lower() for ch in str(value) if ch.isalnum())

        candidate_key = clean(candidate)
        component_key = clean(component_name)
        return bool(component_key and component_key in candidate_key)

    def _prepare_anchor_layout(self, context, obj, anchor):
        anchor_order = [vg.name for vg in anchor.vertex_groups]
        if not anchor_order:
            return

        state = self._capture_vertex_groups(obj)
        preserved_tail = self._get_preserved_tail_groups(obj, anchor_order)
        target_order = [
            name for name in anchor_order
            if name not in preserved_tail and not self._is_mask_vertex_group(name)
        ]

        self._rebuild_vertex_groups_in_order(obj, target_order)
        self._normalize_vertex_groups(context, obj)
        if preserved_tail:
            self._append_preserved_vertex_groups(obj, state, preserved_tail)

        print(
            f"  [AnchorLayout] {obj.name}: temp export VG layout aligned to "
            f"'{anchor.name}'"
            + (f", preserved {len(preserved_tail)} helper VG(s) at tail" if preserved_tail else "")
        )

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

    def _restore_vertex_groups(self, obj, state):
        obj.vertex_groups.clear()
        name_to_group = {}

        for name in state['names']:
            vg = obj.vertex_groups.new(name=name)
            vg.lock_weight = state['locks'].get(name, False)
            name_to_group[name] = vg

        # Group by weight to batch vg.add calls (massive performance boost!)
        from collections import defaultdict
        group_weights = defaultdict(lambda: defaultdict(list)) # vg_name -> weight -> [v_indices]

        for vert_index, entries in state['weights'].items():
            for name, weight in entries:
                group_weights[name][weight].append(vert_index)

        for name, weight_map in group_weights.items():
            vg = name_to_group.get(name)
            if vg:
                for weight, indices in weight_map.items():
                    vg.add(indices, weight, 'REPLACE')

        active_index = state.get('active_index', 0)
        if obj.vertex_groups and 0 <= active_index < len(obj.vertex_groups):
            obj.vertex_groups.active_index = active_index

    @staticmethod
    def _is_mask_vertex_group(name):
        return name.lower().startswith("mask")

    def _get_modifier_vertex_group_names(self, obj):
        names = set()

        for mod in getattr(obj, "modifiers", []):
            try:
                props = mod.bl_rna.properties
            except Exception:
                props = []

            for prop in props:
                identifier = getattr(prop, "identifier", "")
                if "vertex_group" not in identifier:
                    continue

                try:
                    value = getattr(mod, identifier)
                except Exception:
                    continue

                if isinstance(value, str) and value:
                    names.add(value)

        return names

    def _get_preserved_tail_groups(self, obj, anchor_order):
        anchor_names = set(anchor_order)
        modifier_group_names = self._get_modifier_vertex_group_names(obj)
        preserved = []

        for vg in obj.vertex_groups:
            name = vg.name
            if self._is_mask_vertex_group(name):
                preserved.append(name)
            elif name not in anchor_names and name in modifier_group_names:
                preserved.append(name)

        return preserved

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

        # Batch write weights
        for name, entries in weights_by_name.items():
            vg = name_to_group.get(name)
            if not vg:
                continue
            
            # Group entries by weight
            from collections import defaultdict
            weight_map = defaultdict(list)
            for vert_index, weight in entries:
                weight_map[weight].append(vert_index)
                
            for weight, indices in weight_map.items():
                vg.add(indices, weight, 'REPLACE')

    def _append_preserved_vertex_groups(self, obj, state, preserved_names):
        existing_names = {vg.name for vg in obj.vertex_groups}
        name_to_group = {}

        for name in preserved_names:
            if name in existing_names:
                continue
            vg = obj.vertex_groups.new(name=name)
            vg.lock_weight = state['locks'].get(name, False)
            name_to_group[name] = vg
            existing_names.add(name)

        if not name_to_group:
            return

        from collections import defaultdict
        group_weights = defaultdict(lambda: defaultdict(list))

        for vert_index, entries in state['weights'].items():
            for name, weight in entries:
                if name in name_to_group:
                    group_weights[name][weight].append(vert_index)

        for name, weight_map in group_weights.items():
            vg = name_to_group.get(name)
            if not vg:
                continue

            for weight, indices in weight_map.items():
                vg.add(indices, weight, 'REPLACE')

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

    def _restore_all(self, context):
        if not self._temp_objects and not self._original_states:
            return

        print(
            f"[SafeExport] [AnchorLayout] Removing {len(self._temp_objects)} temp object(s) "
            f"and restoring {len(self._original_states)} source object(s)..."
        )

        for temp_obj in list(self._temp_objects):
            try:
                mesh = temp_obj.data
                bpy.data.objects.remove(temp_obj, do_unlink=True)
                if mesh and mesh.users == 0:
                    bpy.data.meshes.remove(mesh, do_unlink=True)
            except ReferenceError:
                pass
            except Exception as e:
                print(f"  [AnchorLayout] Error removing temp object: {e}")

        for obj, state in list(self._original_states.items()):
            try:
                if obj and obj.name in bpy.data.objects:
                    obj.name = state['name']
                    obj.hide_viewport = state['hide_viewport']
                    obj.hide_render = state['hide_render']
                    obj.hide_select = state['hide_select']
                    for coll in state['collections']:
                        if obj.name not in coll.objects:
                            coll.objects.link(obj)
            except ReferenceError:
                pass
            except Exception as e:
                print(f"  [AnchorLayout] Error restoring source object '{state.get('name', '<unknown>')}': {e}")

        try:
            bpy.ops.object.select_all(action='DESELECT')
            for selected_obj in self._prev_selected:
                try:
                    if selected_obj and selected_obj.name in bpy.data.objects:
                        selected_obj.select_set(True)
                except ReferenceError:
                    pass
            if self._prev_active and self._prev_active.name in bpy.data.objects:
                context.view_layer.objects.active = self._prev_active
        except Exception as e:
            print(f"  [AnchorLayout] Error restoring selection: {e}")

        self._temp_objects.clear()
        self._original_states.clear()
        self._prev_active = None
        self._prev_selected = []

        try:
            context.view_layer.update()
        except Exception:
            pass


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


class TWAATextureExportValidatorSubModule:
    """Ensures generated TWAA material textures exist before the game exporter runs."""

    def pre_export(self, context):
        try:
            addon_name = __package__.split(".")[0] if "." in __package__ else __package__
            addon = context.preferences.addons.get(addon_name)
            prefs = addon.preferences if addon else None
            if prefs and not getattr(prefs, "tw_mc_pre_export_validate_textures", True):
                print("[SafeExport] [TWAA] Pre-export texture validator disabled.")
                return

            from . import texworks_mc

            summary = texworks_mc.validate_twaa_export_textures(
                context,
                auto_export=True,
                rebuild_layout=True,
            )
            if not summary.get("enabled", True):
                print("[SafeExport] [TWAA] Texture validator skipped: disabled.")
                return
            if summary.get("exported_slots") or summary.get("registered"):
                print(
                    "[SafeExport] [TWAA] Texture validator repaired "
                    f"{summary.get('exported_slots', 0)} exported slot(s), "
                    f"{summary.get('registered', 0)} existing registration(s)."
                )
            elif summary.get("warnings"):
                print(f"[SafeExport] [TWAA] Texture validator warnings: {summary['warnings'][:3]}")
            else:
                print(
                    "[SafeExport] [TWAA] Texture validator OK: "
                    f"{summary.get('materials', 0)} material(s), "
                    f"{summary.get('checked_slots', 0)} slot(s)."
                )
        except Exception as exc:
            import traceback

            print(f"[SafeExport] [TWAA] Texture validator failed: {exc}")
            traceback.print_exc()

    def post_export(self, context):
        pass

    def restore(self, context):
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN: SafeExport context manager
# ══════════════════════════════════════════════════════════════════════════════

class TWAAPreExportUVSubModule:
    """Builds non-destructive TWAA export meshes with pre-offset TEXCOORD.xy UVs."""

    def __init__(self):
        self._temp_objects = []
        self._source_states = {}
        self._prev_active = None
        self._prev_selected = []

    def pre_export(self, context):
        from . import texworks_mc

        self._temp_objects.clear()
        self._source_states.clear()
        self._prev_active = context.view_layer.objects.active
        self._prev_selected = list(context.selected_objects)

        layouts = texworks_mc.twaa_block_layouts_by_material(context)
        if not layouts:
            return

        targets = [
            obj for obj in list(context.scene.objects)
            if self._is_candidate(context, obj, layouts, texworks_mc)
        ]
        if not targets:
            return

        total_loops = 0
        split_objects = 0
        print(f"[SafeExport] [TWAA PreUV] Preparing {len(targets)} TWAA mesh target(s) before export...")

        for obj in targets:
            try:
                created, patched = self._replace_with_twaa_temps(context, obj, layouts, texworks_mc)
                split_objects += max(0, created - 1)
                total_loops += patched
            except Exception as exc:
                import traceback
                print(f"[SafeExport] [TWAA PreUV] ERROR preparing '{getattr(obj, 'name', '<unknown>')}': {exc}")
                traceback.print_exc()

        if self._temp_objects:
            try:
                bpy.ops.object.select_all(action='DESELECT')
                for obj in self._temp_objects:
                    obj.select_set(True)
                context.view_layer.objects.active = self._temp_objects[0]
            except Exception:
                pass
            print(
                f"[SafeExport] [TWAA PreUV] Ready: temp_objects={len(self._temp_objects)} "
                f"extra_splits={split_objects} patched_loops={total_loops}"
            )

    def post_export(self, context):
        self._restore_all(context)

    def restore(self, context):
        self._restore_all(context)

    def _is_candidate(self, context, obj, layouts, texworks_mc):
        if not obj or obj.type != 'MESH' or not obj.data:
            return False
        if obj.name.endswith("_RZM_TWAA_SOURCE") or obj.get("RZM_TWAA_EXPORT_TEMP"):
            return False
        if "_RZM_SAFE_SOURCE" in obj.name:
            return False
        if getattr(obj, "hide_viewport", False) or getattr(obj, "hide_render", False):
            return False
        return texworks_mc.object_has_twaa_material_faces(context, obj, layouts=layouts)

    def _store_source_state(self, obj):
        return {
            "name": obj.name,
            "source_name": f"{obj.name}_RZM_TWAA_SOURCE",
            "collections": list(obj.users_collection),
            "hide_viewport": obj.hide_viewport,
            "hide_render": obj.hide_render,
            "hide_select": obj.hide_select,
            "selected": obj.select_get(),
        }

    def _replace_with_twaa_temps(self, context, source_obj, layouts, texworks_mc):
        state = self._store_source_state(source_obj)
        self._source_states[source_obj] = state
        source_obj.name = state["source_name"]
        for coll in state["collections"]:
            try:
                coll.objects.unlink(source_obj)
            except Exception:
                pass

        used_indices = texworks_mc.object_used_material_indices(source_obj)
        if not used_indices:
            return 0, 0
        split_by_material = len(used_indices) > 1
        created = 0
        patched = 0

        for material_index in used_indices:
            temp_obj = source_obj.copy()
            temp_obj.data = source_obj.data.copy()
            temp_obj.name = self._temp_name(state["name"], source_obj, material_index, split_by_material, texworks_mc)
            temp_obj.data.name = f"{temp_obj.name}_Mesh"
            temp_obj.hide_viewport = False
            temp_obj.hide_render = False
            temp_obj.hide_select = False
            temp_obj["RZM_TWAA_EXPORT_TEMP"] = True
            temp_obj["RZM_TWAA_EXPORT_SOURCE"] = state["name"]
            temp_obj["RZM_TWAA_EXPORT_MATERIAL_INDEX"] = int(material_index)

            if split_by_material:
                texworks_mc.prune_mesh_to_material_index(temp_obj.data, material_index)

            summary = texworks_mc.apply_twaa_layout_to_object_uv(context, temp_obj, layouts=layouts)
            patched += int(summary.get("patched_loops", 0) or 0)

            for coll in state["collections"] or [context.scene.collection]:
                try:
                    coll.objects.link(temp_obj)
                except RuntimeError:
                    pass
            self._temp_objects.append(temp_obj)
            created += 1

        if split_by_material:
            print(f"  [TWAA PreUV] {state['name']}: separate by material -> {created} temp object(s)")
        return created, patched

    def _temp_name(self, original_name, source_obj, material_index, split_by_material, texworks_mc):
        if not split_by_material:
            return original_name
        mat = None
        if 0 <= int(material_index) < len(source_obj.material_slots):
            mat = source_obj.material_slots[int(material_index)].material
        suffix = texworks_mc.material_key(mat.name if mat else f"Material{material_index}")
        return f"{original_name}__{suffix}"

    def _restore_all(self, context):
        if not self._temp_objects and not self._source_states:
            return

        print(
            f"[SafeExport] [TWAA PreUV] Removing {len(self._temp_objects)} temp object(s) "
            f"and restoring {len(self._source_states)} source object(s)..."
        )

        for temp_obj in list(self._temp_objects):
            try:
                mesh = temp_obj.data
                bpy.data.objects.remove(temp_obj, do_unlink=True)
                if mesh and mesh.users == 0:
                    bpy.data.meshes.remove(mesh, do_unlink=True)
            except ReferenceError:
                pass
            except Exception as exc:
                print(f"  [TWAA PreUV] Error removing temp object: {exc}")

        for obj, state in list(self._source_states.items()):
            try:
                if obj and obj.name in bpy.data.objects:
                    obj.name = state["name"]
                    obj.hide_viewport = state["hide_viewport"]
                    obj.hide_render = state["hide_render"]
                    obj.hide_select = state["hide_select"]
                    for coll in state["collections"]:
                        try:
                            if obj.name not in coll.objects:
                                coll.objects.link(obj)
                        except Exception:
                            pass
            except ReferenceError:
                pass
            except Exception as exc:
                print(f"  [TWAA PreUV] Error restoring source '{state.get('name', '<unknown>')}': {exc}")

        try:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in self._prev_selected:
                try:
                    if obj and obj.name in bpy.data.objects:
                        obj.select_set(True)
                except ReferenceError:
                    pass
            if self._prev_active and self._prev_active.name in bpy.data.objects:
                context.view_layer.objects.active = self._prev_active
        except Exception:
            pass

        self._temp_objects.clear()
        self._source_states.clear()
        self._prev_active = None
        self._prev_selected = []

        try:
            context.view_layer.update()
        except Exception:
            pass


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
        addon = context.preferences.addons.get(addon_name)
        pref = addon.preferences if addon else None
        temp_cleanup = getattr(pref, "safe_export_temp_cleanup", False)

        if temp_cleanup:
            # Альтернативный экспериментальный режим (удаление слоев после экспорта)
            self.sub_modules = [
                # VertexGroupReorderSubModule(),     # Standalone candidate: manually move mask* VG to the end.
                AnchorLayoutCleanupSubModule(),      # [0] Handle anchor VGs layout and restoration.
                TWAATextureExportValidatorSubModule(), # [TWAA] Validate/export missing material textures.
                TWAAPreExportUVSubModule(),          # [TWAA] Temp split by material + pre-offset TEXCOORD.xy.
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
                AnchorLayoutCleanupSubModule(),      # [0] Handle anchor VGs layout and restoration.
                TWAATextureExportValidatorSubModule(), # [TWAA] Validate/export missing material textures.
                TWAAPreExportUVSubModule(),          # [TWAA] Temp split by material + pre-offset TEXCOORD.xy.
                predictor,                           # [1] Добавляем COLOR/TEXCOORD перманентно
                # MeshBackupSubModule(),             # Отключено: вызывает краши depsgraph из-за подмены мешей
                CurveVFXPreviewSubModule(),          # [2] Убираем VFX preview
            ]

    def __enter__(self):
        from .export_timing import measure

        print("[SafeExport] ═══ Старт pre-export ═══")

        # Принудительная синхронизация depsgraph перед началом работы.
        # Предотвращает EXCEPTION_ACCESS_VIOLATION в build_materials при
        # работе с мешами у которых есть модификаторы или shape keys.
        try:
            with measure("safe_export.pre.view_layer_update"):
                self.context.view_layer.update()
        except Exception as e:
            print(f"[SafeExport] WARN: view_layer.update() failed: {e}")

        for sub in self.sub_modules:
            try:
                with measure(f"safe_export.pre.{sub.__class__.__name__}"):
                    sub.pre_export(self.context)
            except Exception as e:
                import traceback
                print(f"[SafeExport] ОШИБКА в pre_export ({sub.__class__.__name__}): {e}")
                traceback.print_exc()

        # Повторная синхронизация после добавления UV/COLOR слоёв предиктором,
        # чтобы XXMI Tools видел актуальное состояние мешей.
        try:
            with measure("safe_export.pre.post_update"):
                self.context.view_layer.update()
        except Exception as e:
            print(f"[SafeExport] WARN: post-pre_export view_layer.update() failed: {e}")

        print("[SafeExport] ═══ pre-export завершён ═══")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        from .export_timing import measure

        had_error = exc_type is not None

        if had_error:
            print(f"[SafeExport] ══ ОШИБКА ЭКСПОРТА: {exc_type.__name__}: {exc_val} ══")
            print("[SafeExport] Запуск аварийного restore (обратный порядок)...")
            for sub in reversed(self.sub_modules):
                if hasattr(sub, 'restore'):
                    try:
                        with measure(f"safe_export.restore.{sub.__class__.__name__}"):
                            sub.restore(self.context)
                    except Exception as e:
                        import traceback
                        print(f"[SafeExport] ОШИБКА в restore ({sub.__class__.__name__}): {e}")
                        traceback.print_exc()

        print("[SafeExport] ═══ Старт post-export cleanup ═══")
        # LEGACY: post-export TWAA buffer patching is disabled.
        # TWAA now prepares temp export meshes before export and writes final TEXCOORD.xy there.
        # Keep utils/twaa_texcoord_patcher.py intact for diagnostics/future fallback.
        if False and not had_error:
            try:
                with measure("safe_export.post.twaa_texcoord_patcher"):
                    summary = self._twaa_texcoord_patcher(self.context)
                if summary.get("patched_vertices", 0):
                    print(
                        "[SafeExport] [TWAA] Patched "
                        f"{summary['patched_vertices']} TEXCOORD vertices across "
                        f"{summary['objects']} object(s), {summary['files']} file(s)."
                    )
                elif summary.get("warnings"):
                    print(f"[SafeExport] [TWAA] No TEXCOORD patch applied: {summary['warnings'][:3]}")
            except Exception as e:
                import traceback
                print(f"[SafeExport] ERROR in TWAA post-export TEXCOORD patcher: {e}")
                traceback.print_exc()
        for sub in reversed(self.sub_modules):
            try:
                with measure(f"safe_export.post.{sub.__class__.__name__}"):
                    sub.post_export(self.context)
            except Exception as e:
                import traceback
                print(f"[SafeExport] ОШИБКА в post_export ({sub.__class__.__name__}): {e}")
                traceback.print_exc()

        try:
            with measure("safe_export.post.view_layer_update"):
                self.context.view_layer.update()
        except Exception as e:
            print(f"[SafeExport] WARN: post-export view_layer.update() failed: {e}")

        print("[SafeExport] ═══ Done ═══")

        # False = не подавляем исключение. Blender сам покажет ошибку оператору.
        return False
