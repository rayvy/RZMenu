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
#  SUB-MODULE 0: Mesh Backup (All visible meshes)
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
            MeshBackupSubModule(),               # [0] Бэкап всех мешей — ПЕРВЫМ
            XXMIMissingDataPredictorSubModule(), # [1] Добавляем COLOR/TEXCOORD
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

        print("[SafeExport] ═══ Done ═══")

        # False = не подавляем исключение. Blender сам покажет ошибку оператору.
        return False
