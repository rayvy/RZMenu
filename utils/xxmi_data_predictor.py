# RZMenu/utils/xxmi_data_predictor.py
#
# Sub-module для SafeExport — автоматически добирает недостающие данные
# которые XXMI требует, но не может сам подставить (в отличие от EFMI/WWMI).
#
# Логика:
#   pre_export  → добавляет COLOR / TEXCOORD слои если их нет
#   post_export → удаляет всё что добавил (откат в исходное состояние)
#   restore     → то же самое (вызывается при ошибке экспорта)
#
# ТОЛЬКО для XXMI-игры: GenshinImpact, ZenlessZoneZero, HonkaiStarRail

import re

import bpy
import numpy as np

XXMI_GAMES = frozenset({'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'})

# Дефолтный цвет COLOR: FF8080, alpha = 0.3
# vertex_colors API хранит в linear float (0-1)
# 0xFF = 255 → 1.0,  0x80 = 128 → 128/255 ≈ 0.502
DEFAULT_COLOR = (1.0, 0.502, 0.502, 0.3)


def is_clean_texcoord_export_name(name):
    name = str(name or "").strip()
    if not name:
        return False
    upper = name.upper()
    if "RZM_BACKUP" in upper:
        return False
    if re.search(r"\.\d+$", name):
        return False
    return bool(re.fullmatch(r"TEXCOORD\d*\.xy", name))


def assign_dummy_uv_coordinates(obj, uv_layer):
    """
    Проецирует меш по оси Z (плоское проецирование в bounding box)
    для создания простейшей корректной развертки-заглушки.
    """
    mesh = obj.data
    n_loops = len(mesh.loops)
    n_verts = len(mesh.vertices)
    
    if n_loops == 0 or n_verts == 0:
        return

    try:
        # Получаем индексы вершин для каждого loop
        loop_vert_indices = np.empty(n_loops, dtype=np.int32)
        mesh.loops.foreach_get('vertex_index', loop_vert_indices)
        
        # Получаем координаты вершин
        coords = np.empty(n_verts * 3, dtype=np.float32)
        mesh.vertices.foreach_get('co', coords)
        coords = coords.reshape(-1, 3)
        
        # Проецируем X, Y
        xs = coords[:, 0]
        ys = coords[:, 1]
        
        min_x, max_x = xs.min(), xs.max()
        min_y, max_y = ys.min(), ys.max()
        
        range_x = (max_x - min_x) if (max_x - min_x) > 1e-5 else 1.0
        range_y = (max_y - min_y) if (max_y - min_y) > 1e-5 else 1.0
        
        # Нормализуем в диапазон [0.0, 1.0]
        u_coords = (xs - min_x) / range_x
        v_coords = (ys - min_y) / range_y
        
        # Переносим координаты на loops
        loop_uvs = np.empty(n_loops * 2, dtype=np.float32)
        loop_uvs[0::2] = u_coords[loop_vert_indices]
        loop_uvs[1::2] = v_coords[loop_vert_indices]
        
        uv_layer.data.foreach_set('uv', loop_uvs)
    except Exception as e:
        print(f"  [Predictor] Ошибка генерации координат развертки для {obj.name}: {e}")


def apply_uv_math(obj, target_name, grid_x, grid_y, pos_x, pos_y):
    """
    Автономная функция для применения UV сжатия/сдвига.
    Копирует координаты из исходного UV слоя и применяет сетку.
    """
    mesh = obj.data
    src_uv = mesh.uv_layers.get("UVMap") or (mesh.uv_layers[0] if mesh.uv_layers else None)
    if not src_uv:
        return False
    
    if target_name in mesh.uv_layers:
        try:
            mesh.uv_layers.remove(mesh.uv_layers[target_name])
        except Exception:
            pass
        
    try:
        # Устанавливаем active слой, чтобы новый слой скопировал его координаты
        mesh.uv_layers.active = src_uv
        target_layer = mesh.uv_layers.new(name=target_name)
    except Exception as e:
        print(f"  [Predictor] Не удалось создать UV слой {target_name}: {e}")
        return False
        
    if not target_layer:
        return False
    
    layer_len = len(mesh.loops)
    if layer_len == 0:
        return True

    try:
        uvs = np.empty(layer_len * 2, dtype=np.float32)
        target_layer.data.foreach_get("uv", uvs)
        uvs = uvs.reshape(-1, 2)
        
        math_pos_y = (grid_y - 1) - pos_y
        
        scale_x = 1.0 / max(1, grid_x)
        scale_y = 1.0 / max(1, grid_y)
        
        offset_x = pos_x * scale_x
        offset_y = math_pos_y * scale_y
        
        uvs[:, 0] = uvs[:, 0] * scale_x + offset_x
        uvs[:, 1] = uvs[:, 1] * scale_y + offset_y
        
        target_layer.data.foreach_set("uv", uvs.flatten())
        return True
    except Exception as e:
        print(f"  [Predictor] Ошибка UV математики для {obj.name} ({target_name}): {e}")
        return False
    

def standardize_texcoord_xy(obj):
    """
    Ensure TEXCOORD.xy exists without creating extra authoring UV clutter.
    If TEXCOORD.xy is missing, rename the first available UV layer to TEXCOORD.xy.
    If no UV exists, create TEXCOORD.xy and assign dummy coordinates.
    """
    if not obj or obj.type != 'MESH' or obj.data is None:
        return False, "not_mesh"

    mesh = obj.data
    if "TEXCOORD.xy" in mesh.uv_layers:
        return False, "exists"

    if mesh.uv_layers:
        old_name = mesh.uv_layers[0].name
        mesh.uv_layers[0].name = "TEXCOORD.xy"
        mesh.uv_layers.active = mesh.uv_layers[0]
        return True, f"renamed:{old_name}"

    uv_layer = mesh.uv_layers.new(name="TEXCOORD.xy")
    if uv_layer:
        assign_dummy_uv_coordinates(obj, uv_layer)
        return True, "created_dummy"

    return False, "failed"


def get_export_targets(context):
    """
    Возвращает целевые MESH объекты для экспорта.
    Для максимальной надежности собирает:
    1) Все меши компонентов из ComponentCollector (с форсированием обхода сцены force_fallback=True)
    2) Все выделенные меши
    3) Все меши в активной коллекции
    4) Все видимые/скрытые меши сцены в качестве фолбека (если список пуст)
    """
    targets = []
    
    # 1. Собираем меши из ComponentCollector (всегда обходим сцену, не доверяя старому кэшу)
    try:
        from .component_collector import ComponentCollector
        collector = ComponentCollector(context)
        components = collector.get_components(force_fallback=True)
        if components:
            for objs in components.values():
                for obj in objs:
                    if obj and obj.type == 'MESH' and obj.data is not None:
                        if obj not in targets:
                            targets.append(obj)
    except Exception as e:
        print(f"[SafeExport] Ошибка сбора компонентов через ComponentCollector: {e}")

    # 2. Добавляем выделенные меши
    try:
        for obj in context.selected_objects:
            if obj and obj.type == 'MESH' and obj.data is not None:
                if obj not in targets:
                    targets.append(obj)
    except Exception:
        pass

    # 3. Добавляем меши из активной коллекции
    try:
        if context.view_layer.active_layer_collection:
            active_coll = context.view_layer.active_layer_collection.collection
            for obj in active_coll.all_objects:
                if obj and obj.type == 'MESH' and obj.data is not None:
                    if obj not in targets:
                        targets.append(obj)
    except Exception as e:
        print(f"[SafeExport] Ошибка сбора объектов из активной коллекции: {e}")

    # 4. Фолбек: берём ВСЕ меши сцены если список пуст
    for obj in context.scene.objects:
        if obj and obj.type == 'MESH' and obj.data is not None:
            if obj not in targets:
                targets.append(obj)

    # Фильтруем список от вспомогательных объектов RZMenu
    final_targets = []
    for obj in targets:
        # Пропускаем только наши внутренние backup-объекты
        if "RZM_BACKUP" in obj.name or "_RZM_SAFE" in obj.name:
            continue
        final_targets.append(obj)

    return final_targets


def get_export_issues(context):
    """
    Сканирует меши на наличие проблем перед экспортом (отсутствие UV, COLOR, доп. слоев).
    Возвращает список [(obj, ["описание проблемы", ...]), ...]
    """
    targets = get_export_targets(context)
    issues = []
    
    if not targets:
        return issues

    predictor = XXMIMissingDataPredictorSubModule()
    
    # Валидация актуальна только для XXMI игр
    game = predictor._get_game(context)
    if game not in XXMI_GAMES:
        return issues
        
    expected_uvs = predictor._get_texcoord_targets(context)
    expected_colors = predictor._get_target_colors(context)

    for obj in targets:
        obj_issues = []
        if not obj.data.uv_layers:
            obj_issues.append("Missing all UV maps (Needs unwrap)")
        else:
            for (name, gx, gy, px, py) in expected_uvs:
                if name not in obj.data.uv_layers:
                    obj_issues.append(f"Missing UV layer '{name}'")
                    
        for col_name in expected_colors:
            if col_name not in obj.data.vertex_colors:
                obj_issues.append(f"Missing Color layer '{col_name}'")
                
        if obj_issues:
            issues.append((obj, obj_issues))
            
    return issues


class XXMIMissingDataPredictorSubModule:
    """
    Предиктор недостающих данных для XXMI экспорта.
    """

    def __init__(self):
        self._added_color   = []   # list of (obj_name, col_name)
        self._added_uv      = []   # list of (obj_name, uv_layer_name)
        self._active        = False

    def _get_game(self, context):
        try:
            return context.scene.rzm.game.selection
        except Exception:
            return None

    def _get_texcoord_targets(self, context):
        """
        Возвращает список целевых TEXCOORD слоев и их параметров сжатия.
        Формат: [(name, grid_x, grid_y, pos_x, pos_y)]
        Использует все уникальные имена UV из сцены, а также из texcoord_list.
        """
        target_names = set()
        
        # 1. Читаем из rzm_st_texcoord_list и старого texcoord_list в сцене
        for list_name in ("rzm_st_texcoord_list", "texcoord_list"):
            try:
                lst = getattr(context.scene, list_name, None)
                if lst:
                    for item in lst:
                        if item.target_name and is_clean_texcoord_export_name(item.target_name):
                            target_names.add(item.target_name)
            except Exception:
                pass

        # 2. Добавляем имена UV слоев, найденные у любых других мешей сцены
        for o in context.scene.objects:
            if o.type == 'MESH' and o.data is not None:
                for uv in o.data.uv_layers:
                    if is_clean_texcoord_export_name(uv.name):
                        target_names.add(uv.name)

        # 3. Дефолты если совсем ничего нет
        target_names.update(['TEXCOORD.xy', 'TEXCOORD1.xy', 'TEXCOORD2.xy'])

        # Конструируем параметры (по умолчанию 1x1 сдвиг)
        targets = []
        for name in sorted(target_names):
            gx, gy, px, py = 1, 1, 0, 0
            try:
                found = False
                for list_name in ("rzm_st_texcoord_list", "texcoord_list"):
                    lst = getattr(context.scene, list_name, None)
                    if lst:
                        for item in lst:
                            if item.target_name == name:
                                gx, gy, px, py = item.grid_x, item.grid_y, item.pos_x, item.pos_y
                                found = True
                                break
                    if found:
                        break
            except Exception:
                pass
            targets.append((name, gx, gy, px, py))
            
        return targets

    def _get_target_colors(self, context):
        """Возвращает список ожидаемых vertex color слоев."""
        color_names = {'COLOR'}
        for o in context.scene.objects:
            if o.type == 'MESH' and o.data is not None:
                for col in o.data.vertex_colors:
                    color_names.add(col.name)
        return sorted(color_names)

    def _add_color_attribute(self, obj, name):
        """Добавляет vertex color layer с дефолтным значением."""
        try:
            layer = obj.data.vertex_colors.new(name=name, do_init=False)
            color = DEFAULT_COLOR
            n = len(obj.data.loops)
            if n > 0:
                flat = color * n
                layer.data.foreach_set('color', flat)
            self._added_color.append((obj.name, name))
            print(f"  [Predictor] {obj.name}: добавлен вершинный цвет '{name}' (FF8080 α=0.3)")
        except Exception as e:
            print(f"  [Predictor] {obj.name}: не удалось добавить цвет '{name}': {e}")

    def pre_export(self, context):
        game = self._get_game(context)
        if game not in XXMI_GAMES:
            self._active = False
            return

        self._active = True
        self._added_color.clear()
        self._added_uv.clear()

        print("[SafeExport] [Predictor] Проверка недостающих данных для XXMI...")

        # Получаем только экспортируемые меши
        targets = get_export_targets(context)
        expected_uvs = self._get_texcoord_targets(context)
        expected_colors = self._get_target_colors(context)
        print(
            f"[SafeExport] [Predictor] Targets={len(targets)}, "
            f"UVs={', '.join(name for name, *_ in expected_uvs)}"
        )

        for obj in targets:
            try:
                # 1. Проверяем развертку вообще
                if not obj.data.uv_layers:
                    print(f"  [Predictor] У объекта '{obj.name}' отсутствует развертка! Создаем заглушку...")
                    try:
                        uv_layer = obj.data.uv_layers.new(name="UVMap")
                        if uv_layer:
                            assign_dummy_uv_coordinates(obj, uv_layer)
                            self._added_uv.append((obj.name, "UVMap"))
                    except Exception as e:
                        print(f"  [Predictor] Не удалось инициализировать базовую развертку для {obj.name}: {e}")
                        continue

                # 2. Проверяем COLOR слои
                if "TEXCOORD.xy" not in obj.data.uv_layers:
                    changed, reason = standardize_texcoord_xy(obj)
                    if changed:
                        print(f"  [Predictor] {obj.name}: TEXCOORD.xy standardized ({reason})")

                for col_name in expected_colors:
                    if col_name not in obj.data.vertex_colors:
                        self._add_color_attribute(obj, col_name)

                # 3. Проверяем TEXCOORD слои
                for (name, gx, gy, px, py) in expected_uvs:
                    if name == "TEXCOORD.xy":
                        continue
                    if name not in obj.data.uv_layers:
                        success = apply_uv_math(obj, name, gx, gy, px, py)
                        if success:
                            self._added_uv.append((obj.name, name))
                            
            except Exception as e:
                print(f"  [Predictor] Ошибка обработки объекта '{obj.name}': {e}")

        if self._added_color or self._added_uv:
            print(f"[SafeExport] [Predictor] Добавлено: "
                  f"{len(self._added_color)} COLOR, "
                  f"{len(self._added_uv)} UV слоёв.")
        else:
            print("[SafeExport] [Predictor] Все данные в порядке — ничего не добавлено.")

    def _cleanup(self, context):
        """Удаляет все добавленные слои."""
        removed_color = 0
        removed_uv = 0

        for obj_name, col_name in self._added_color:
            obj = context.scene.objects.get(obj_name)
            if not obj or obj.data is None:
                continue
            layer = obj.data.vertex_colors.get(col_name)
            if layer:
                try:
                    obj.data.vertex_colors.remove(layer)
                    removed_color += 1
                except Exception:
                    pass

        for obj_name, layer_name in self._added_uv:
            obj = context.scene.objects.get(obj_name)
            if not obj or obj.data is None:
                continue
            layer = obj.data.uv_layers.get(layer_name)
            if layer:
                try:
                    obj.data.uv_layers.remove(layer)
                    removed_uv += 1
                except Exception:
                    pass

        self._added_color.clear()
        self._added_uv.clear()

        if removed_color or removed_uv:
            print(f"[SafeExport] [Predictor] Откат предиктора: удалено {removed_color} COLOR, {removed_uv} UV слоёв.")

    def restore(self, context):
        if not self._active or getattr(self, "disable_cleanup", False):
            return
        self._cleanup(context)

    def post_export(self, context):
        if not self._active or getattr(self, "disable_cleanup", False):
            return
        self._cleanup(context)
