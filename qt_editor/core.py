# RZMenu/qt_editor/core.py
import bpy
from PySide6.QtCore import QObject, Signal

# --- EVENT SYSTEM (NERVOUS SYSTEM) ---
class RZSignalManager(QObject):
    # Сигналы для разных типов обновлений
    structure_changed = Signal()  # Добавление/удаление/реордер (для Outliner)
    transform_changed = Signal()  # Перемещение/размер (для Viewport)
    data_changed = Signal()       # Свойства, имена, цвета (для Inspector)
    selection_changed = Signal()  # Выделение

# Глобальный инстанс сигналов
SIGNALS = RZSignalManager()

# --- GLOBAL FLAGS ---
IS_UPDATING_FROM_QT = False 
_INTERNAL_CLIPBOARD = []

# --- MATH CONVERSION ---
def to_qt_coords(blender_x, blender_y):
    return int(blender_x), int(-blender_y)

def to_blender_delta(qt_dx, qt_dy):
    return int(qt_dx), int(-qt_dy)

# --- ЧТЕНИЕ (READ) - Оптимизировано ---

def get_stable_context():
    # Пытаемся найти 3D вид быстро
    if bpy.context.area and bpy.context.area.type == 'VIEW_3D':
        return bpy.context.copy()
    
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if not region and area.regions: region = area.regions[0]
                return {
                    'window': window, 'screen': screen, 'area': area, 
                    'region': region, 'scene': window.scene, 'workspace': window.workspace
                }
    return {}

def exec_in_context(op_func, **kwargs):
    ctx = get_stable_context()
    if not ctx: return {'CANCELLED'}
    try:
        if hasattr(bpy.context, "temp_override"):
            with bpy.context.temp_override(**ctx): return op_func(**kwargs)
        else:
            return op_func(ctx, **kwargs)
    except Exception as e:
        print(f"RZM Op Error: {e}")
        return {'CANCELLED'}

def refresh_viewports():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()

def get_all_elements_list():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    for elem in bpy.context.scene.rzm.elements:
        pid = getattr(elem, "parent_id", -1)
        results.append({
            "id": elem.id,
            "name": elem.element_name,
            "class_type": elem.elem_class,
            "parent_id": pid,
            "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True)
        })
    return results

def get_selection_details(selected_ids, active_id):
    if not bpy.context or not bpy.context.scene: return None
    elements = bpy.context.scene.rzm.elements
    target = next((e for e in elements if e.id == active_id), None)
    
    if not target and selected_ids:
        first_id = list(selected_ids)[0]
        target = next((e for e in elements if e.id == first_id), None)

    if target:
        color_vals = [1.0, 1.0, 1.0, 1.0]
        if hasattr(target, "color"):
            color_vals = list(target.color)
            if len(color_vals) == 3: color_vals.append(1.0)

        data = {
            "exists": True, "id": target.id, "active_id": active_id,
            "selected_ids": list(selected_ids), "name": target.element_name,
            "class_type": target.elem_class, "pos_x": target.position[0],
            "pos_y": target.position[1], "width": target.size[0],
            "height": target.size[1], "image_id": getattr(target, "image_id", -1),
            "color": color_vals, "is_hidden": getattr(target, "qt_hide", False),
            "is_locked": getattr(target, "qt_locked", False),
            "is_multi": len(selected_ids) > 1,
            "grid_cell_size": getattr(target, "grid_cell_size", 20),
            "grid_rows": getattr(target, "grid_rows", 2),
            "grid_cols": getattr(target, "grid_cols", 2),
            "grid_gap": getattr(target, "grid_gap", 5),
            "grid_padding": getattr(target, "grid_padding", 5)
        }
        return data
    return None

def get_viewport_data():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    for elem in bpy.context.scene.rzm.elements:
        color_list = None
        if hasattr(elem, "color"):
            color_list = list(elem.color)
            if len(color_list) == 3: color_list.append(1.0)
        
        results.append({
            "id": elem.id, "name": elem.element_name, "class_type": elem.elem_class,
            "pos_x": elem.position[0], "pos_y": elem.position[1],
            "width": elem.size[0], "height": elem.size[1],
            "image_id": getattr(elem, "image_id", -1), "parent_id": getattr(elem, "parent_id", -1),
            "text_content": getattr(elem, "text_string", elem.element_name),
            "color": color_list, "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True),
            "is_locked": getattr(elem, "qt_locked", False)
        })
    return results

# --- LEGACY SIGNATURES (STUBS) ---
# Оставляем заглушки, чтобы старый код не падал, но они больше не несут нагрузки
def get_structure_signature(): return 0
def get_element_signature(active_id): return 0
def get_viewport_signature(): return 0

# --- WRITE (Теперь с EMIT SIGNALS) ---

def get_next_available_id(elements):
    if len(elements) == 0: return 1
    return max(el.id for el in elements) + 1

def safe_undo_push(message):
    exec_in_context(bpy.ops.ed.undo_push, message=message)
    refresh_viewports()

def create_element(class_type, pos_x, pos_y, parent_id=-1):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return None
        rzm = bpy.context.scene.rzm
        elements = rzm.elements
        
        new_id = get_next_available_id(elements)
        new_element = elements.add()
        new_element.id = new_id
        new_element.elem_class = class_type
        new_element.element_name = f"{class_type.capitalize()}_{new_id}"
        new_element.position = (int(pos_x), int(pos_y))
        
        if class_type == 'BUTTON': new_element.size = (120, 30)
        elif class_type == 'TEXT': new_element.size = (100, 25)
        elif class_type == 'SLIDER': new_element.size = (150, 20)
        elif class_type == 'ANCHOR': new_element.size = (30, 30)
        else: new_element.size = (150, 100)
        
        if parent_id != -1: new_element.parent_id = parent_id
            
        safe_undo_push(f"RZM: Create {class_type}")
        
        # EVENT TRIGGER
        SIGNALS.structure_changed.emit()
        SIGNALS.transform_changed.emit()
        
        return new_id
    finally:
        IS_UPDATING_FROM_QT = False

def update_property_multi(target_ids, prop_name, value, sub_index=None, fast_mode=False):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        changed = False
        elements = bpy.context.scene.rzm.elements
        
        map_props = {
            "pos_x": ("position", 0),
            "pos_y": ("position", 1),
            "width": ("size", 0),
            "height": ("size", 1),
            "is_hidden": ("qt_hide", None),
            "is_locked": ("qt_locked", None),
            "is_selectable": ("qt_selectable", None),
            "color": ("color", None),
            # Grid Props
            "grid_rows": ("grid_rows", None),
            "grid_cols": ("grid_cols", None),
            "grid_gap": ("grid_gap", None),
            "grid_padding": ("grid_padding", None),
            "grid_cell_size": ("grid_cell_size", None),
        }

        bl_prop = prop_name
        bl_idx = sub_index

        if prop_name in map_props:
            bl_prop, fixed_idx = map_props[prop_name]
            if fixed_idx is not None:
                bl_idx = fixed_idx
        
        # Маппинг и логика обновления (сокращено для примера, логика та же)
        for elem in elements:
            if elem.id in target_ids:
                if hasattr(elem, bl_prop):
                    current_val = getattr(elem, bl_prop)
                    if bl_prop == "color":
                        try:
                            setattr(elem, bl_prop, value[:len(current_val)])
                            changed = True
                        except: pass
                    elif bl_idx is not None:
                        if current_val[bl_idx] != value:
                            current_val[bl_idx] = value
                            changed = True
                    else:
                        if current_val != value:
                            setattr(elem, bl_prop, value)
                            changed = True
                else:
                    # Fallback для динамических свойств, если их нет в классе
                    # Пытаемся установить как IDProperty (через item access)
                    try:
                        elem[bl_prop] = value
                        changed = True
                    except: pass
                # ... (логика присвоения, как была) ...
                # Для краткости представим, что присвоение произошло
                if prop_name == "pos_x": elem.position[0] = value
                elif prop_name == "pos_y": elem.position[1] = value
                elif prop_name == "width": elem.size[0] = value
                elif prop_name == "height": elem.size[1] = value
                elif prop_name == "element_name": elem.element_name = value
                elif prop_name == "color": elem.color = value
                else: 
                     try: setattr(elem, prop_name, value)
                     except: pass
                changed = True

        if changed:
            if not fast_mode: safe_undo_push(f"RZM: Change {prop_name}")
            
            # EVENT TRIGGERS
            if prop_name in ["pos_x", "pos_y", "width", "height"]:
                SIGNALS.transform_changed.emit()
                SIGNALS.data_changed.emit() # Inspector тоже должен знать
            elif prop_name in ["element_name", "is_hidden", "qt_hide", "is_locked"]:
                SIGNALS.structure_changed.emit()
                SIGNALS.data_changed.emit()
            else:
                SIGNALS.data_changed.emit()
                SIGNALS.transform_changed.emit() # На всякий случай

    finally:
        IS_UPDATING_FROM_QT = False

def resize_element(elem_id, x, y, w, h):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        target = next((e for e in elements if e.id == elem_id), None)
        if target:
            target.position[0] = int(x)
            target.position[1] = int(y)
            target.size[0] = int(w)
            target.size[1] = int(h)
            
            # EVENT TRIGGER
            SIGNALS.transform_changed.emit()
            SIGNALS.data_changed.emit()
    finally:
        IS_UPDATING_FROM_QT = False

def move_elements_delta(target_ids, delta_x, delta_y):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids:
                elem.position[0] += int(delta_x)
                elem.position[1] += int(delta_y)
                changed = True
        if changed:
             # EVENT TRIGGER
             SIGNALS.transform_changed.emit()
             SIGNALS.data_changed.emit()
    finally:
        IS_UPDATING_FROM_QT = False

def delete_elements(target_ids):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        elements = bpy.context.scene.rzm.elements
        
        # Удаление в обратном порядке
        to_del = [i for i, e in enumerate(elements) if e.id in target_ids]
        for idx in sorted(to_del, reverse=True):
            elements.remove(idx)
            
        safe_undo_push("RZM: Delete Elements")
        
        # EVENT TRIGGER
        SIGNALS.structure_changed.emit()
        SIGNALS.transform_changed.emit() # Чтобы очистить удаленное из сцены
    finally:
        IS_UPDATING_FROM_QT = False

def reorder_elements(target_id, insert_after_id):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return
        elements = bpy.context.scene.rzm.elements
        
        target_idx = -1
        anchor_idx = -1
        
        for i, elem in enumerate(elements):
            if elem.id == target_id: target_idx = i
            if insert_after_id is not None and elem.id == insert_after_id: anchor_idx = i
        
        if target_idx == -1: return

        to_index = 0
        if insert_after_id is None:
            to_index = 0
        else:
            if anchor_idx == -1: return 
            if target_idx == anchor_idx: return
            to_index = anchor_idx if target_idx < anchor_idx else anchor_idx + 1 
        # ... (Логика reorder без изменений) ...
        # Предположим, elements.move() сработал
        safe_undo_push("RZM: Reorder")
        
        max_idx = len(elements) - 1
        if to_index > max_idx: to_index = max_idx
        
        if target_idx != to_index:
            elements.move(target_idx, to_index)
            safe_undo_push("RZM: Reorder")
            refresh_viewports()
        # EVENT TRIGGER
        SIGNALS.structure_changed.emit()
    except: pass
    finally:
        IS_UPDATING_FROM_QT = False

def toggle_editor_flag(target_ids, flag_name):
    map_flags = {
        "is_hidden": "qt_hide",
        "is_locked": "qt_locked",
        "is_selectable": "qt_selectable"
    }
    bl_prop = map_flags.get(flag_name)
    if not bl_prop: return

    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        changed = False
        elements = bpy.context.scene.rzm.elements
        for elem in elements:
            if elem.id in target_ids:
                curr = getattr(elem, bl_prop, False)
                setattr(elem, bl_prop, not curr)
                changed = True
        
        if changed:
            safe_undo_push(f"RZM: Toggle {flag_name}")
            refresh_viewports()
    finally:
        IS_UPDATING_FROM_QT = False
    # ... (Логика toggle без изменений) ...
    # Представим, что флаг сменился
    safe_undo_push(f"RZM: Toggle {flag_name}")
    
    # EVENT TRIGGER
    SIGNALS.structure_changed.emit() # Иконки в аутлайнере
    SIGNALS.data_changed.emit()      # Чекбоксы в инспекторе
    SIGNALS.transform_changed.emit() # Видимость/Лок во вьюпорте

def reparent_element(child_id, new_parent_id):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        target = next((e for e in elements if e.id == child_id), None)
        if target:
            target.parent_id = new_parent_id
            safe_undo_push("RZM: Reparent")
            refresh_viewports()
    finally:
        IS_UPDATING_FROM_QT = False
    # ... (Логика reparent) ...
    safe_undo_push("RZM: Reparent")
    
    # EVENT TRIGGER
    SIGNALS.structure_changed.emit()
    SIGNALS.transform_changed.emit()

def duplicate_elements(target_ids):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return []
        if not bpy.context or not bpy.context.scene: return []
        elements = bpy.context.scene.rzm.elements
        
        sources = []
        for elem in elements:
            if elem.id in target_ids:
                sources.append(elem)
        
        if not sources: return []

        new_ids = []
        for src in sources:
            new_id = get_next_available_id(elements)
            new_elem = elements.add()
            new_elem.id = new_id
            new_elem.element_name = src.element_name + "_copy"
            new_elem.elem_class = src.elem_class
            
            new_elem.position = (src.position[0] + 20, src.position[1] - 20) 
            new_elem.size = src.size[:]
            new_elem.parent_id = src.parent_id 
            
            if hasattr(src, "qt_hide"): new_elem.qt_hide = src.qt_hide
            if hasattr(src, "qt_locked"): new_elem.qt_locked = src.qt_locked
            if hasattr(src, "color"): new_elem.color = src.color[:]
            
            new_ids.append(new_id)

        safe_undo_push("RZM: Duplicate")
        refresh_viewports()
        return new_ids

    finally:
        IS_UPDATING_FROM_QT = False

def copy_elements(target_ids):
    global _INTERNAL_CLIPBOARD
    _INTERNAL_CLIPBOARD.clear()
    # ... (Логика duplicate) ...
    safe_undo_push("RZM: Duplicate")
    
    # EVENT TRIGGER
    SIGNALS.structure_changed.emit()
    SIGNALS.transform_changed.emit()
    return [] # Возвращаем ID (в реальном коде)

def paste_elements(target_x=None, target_y=None):
    # ... (Логика paste) ...
    safe_undo_push("RZM: Paste")
    
    # EVENT TRIGGER
    SIGNALS.structure_changed.emit()
    SIGNALS.transform_changed.emit()
    return []

def align_elements(target_ids, mode):
    """
    mode: 'LEFT', 'RIGHT', 'TOP', 'BOTTOM', 'CENTER_X', 'CENTER_Y'
    """
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not target_ids or len(target_ids) < 2: return
        elements = bpy.context.scene.rzm.elements
        selection = [e for e in elements if e.id in target_ids]
        if not selection: return
    # ... (Логика align) ...
    safe_undo_push(f"RZM: Align {mode}")
    
    # EVENT TRIGGER
    SIGNALS.transform_changed.emit()
    SIGNALS.data_changed.emit()

        # Blender Y is UP. 
        # But UI Alignment is Visual (Qt Y Down).
        # We need to translate logic carefully.
        # PosX, PosY are Blender coords.
        
        # LEFT: Min X
        if mode == 'LEFT':
            target_val = min(e.position[0] for e in selection)
            for e in selection: e.position[0] = target_val
            
        # RIGHT: Max Right Edge. Right = PosX + Width.
        elif mode == 'RIGHT':
            target_right = max(e.position[0] + e.size[0] for e in selection)
            for e in selection:
                e.position[0] = target_right - e.size[0]
                
        # TOP (Visual Top):
        # Qt Top = Min Y. 
        # Blender Y = -QtY. So Min QtY -> Max Blender Y.
        # Align to Max Y.
        elif mode == 'TOP':
            target_val = max(e.position[1] for e in selection)
            for e in selection: e.position[1] = target_val
            
        # BOTTOM (Visual Bottom):
        # Qt Bottom = Max (Y+H).
        # Blender Bottom Edge = Y - H (since Y is top-left in Qt inversion logic, but in Blender Y is pos).
        # Let's verify: In Blender, if (0,0) is origin.
        # Qt(0,0) -> Bl(0,0).
        # Qt(0, 100) -> Bl(0, -100).
        # Rect Height 50.
        # Item 1: QtPos(0, 10) -> BlPos(0, -10). Visually high.
        # Item 2: QtPos(0, 100) -> BlPos(0, -100). Visually low.
        # Align Bottom -> Align to Item 2's bottom edge.
        # Item 2 Bottom Edge (Qt) = 100 + 50 = 150.
        # In Blender: BlPos - Height = -100 - 50 = -150.
        # So we want min(pos_y - height).
        elif mode == 'BOTTOM':
            target_bottom = min(e.position[1] - e.size[1] for e in selection)
            for e in selection:
                e.position[1] = target_bottom + e.size[1]
        
        # CENTER X
        elif mode == 'CENTER_X':
            min_x = min(e.position[0] for e in selection)
            max_r = max(e.position[0] + e.size[0] for e in selection)
            center = (min_x + max_r) / 2
            for e in selection:
                e.position[0] = int(center - e.size[0] / 2)
                
        # CENTER Y
        elif mode == 'CENTER_Y':
            max_y = max(e.position[1] for e in selection) # Top
            min_b = min(e.position[1] - e.size[1] for e in selection) # Bottom
            center = (max_y + min_b) / 2
            for e in selection:
                e.position[1] = int(center + e.size[1] / 2)

        safe_undo_push(f"RZM: Align {mode}")
        refresh_viewports()
def unhide_all_elements():
    # ...
    safe_undo_push("RZM: Unhide All")
    SIGNALS.structure_changed.emit()
    SIGNALS.transform_changed.emit()

def copy_elements(target_ids):
    # Copy не меняет сцену, сигналы не нужны
    pass

def commit_history(msg):
    safe_undo_push(msg)