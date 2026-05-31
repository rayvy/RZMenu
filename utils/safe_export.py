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

        self.sub_modules = [
            VertexGroupReorderSubModule(),       # [0] Сортируем VG в конец/по алфавиту
            MeshBackupSubModule(),               # [1] Бэкап всех мешей
            XXMIMissingDataPredictorSubModule(), # [2] Добавляем COLOR/TEXCOORD
            CurveVFXPreviewSubModule(),          # [3] Убираем VFX preview
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
