# RZMenu/qt_editor/core.py
import bpy

# --- GLOBAL FLAGS ---
# Если True, значит изменение инициировано нами (из Qt),
# и мы не должны триггерить полную перерисовку UI в ответ на depsgraph.
IS_UPDATING_FROM_QT = False 

# --- ЧТЕНИЕ (READ) ---

def get_active_object_safe():
    """
    Безопасный способ получить активный объект, 
    даже если фокус у окна Qt, а не у 3D Viewport.
    """
    # 1. Если контекст есть (мышь над Blender), берем быстро
    if getattr(bpy.context, "active_object", None):
        return bpy.context.active_object
    
    # 2. Если контекст потерян (мышь над Qt), берем через слой
    # Это спасает от AttributeError: 'Context' object has no attribute 'active_object'
    try:
        return bpy.context.view_layer.objects.active
    except AttributeError:
        return None

def get_selected_objects_safe():
    try:
        return bpy.context.selected_objects
    except AttributeError:
        # Fallback через view_layer
        try:
            return [o for o in bpy.context.view_layer.objects if o.select_get()]
        except:
            return []

def get_stable_context():
    """
    Ищет валидный 3D Viewport.
    Оптимизация: Сначала быстрый чек, потом перебор.
    """
    # 1. Сначала пробуем текущий
    if bpy.context.area and bpy.context.area.type == 'VIEW_3D':
        return bpy.context.copy()

    # 2. Ищем перебором (как было)
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if not region and area.regions: 
                    region = area.regions[0]
                    
                return {
                    'window': window,
                    'screen': screen,
                    'area': area,
                    'region': region,
                    'scene': window.scene,
                    'workspace': window.workspace,
                }
    return {}

def exec_in_context(op_func, **kwargs):
    ctx = get_stable_context()
    if not ctx:
        return {'CANCELLED'}
    try:
        if hasattr(bpy.context, "temp_override"):
            with bpy.context.temp_override(**ctx):
                return op_func(**kwargs)
        else:
            return op_func(ctx, **kwargs)
    except Exception as e:
        print(f"RZM Op Error: {e}")
        return {'CANCELLED'}

def refresh_viewports():
    """Обновляет 3D окна Blender"""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def get_scene_info():
    if not bpy.context or not bpy.context.scene:
        return {"count": 0, "name": "No Scene"}
    rzm = bpy.context.scene.rzm
    return {
        "count": len(rzm.elements),
        "scene_name": bpy.context.scene.name,
    }

def get_all_elements_list():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    for elem in bpy.context.scene.rzm.elements:
        results.append({
            "id": elem.id,
            "name": elem.element_name,
            "class_type": elem.elem_class,
        })
    return results

def get_selection_details(selected_ids, active_id):
    if not bpy.context or not bpy.context.scene: return None
    elements = bpy.context.scene.rzm.elements
    target = next((e for e in elements if e.id == active_id), None)
    
    # Логика: если активный не найден среди элементов (например это меш),
    # пробуем найти первый из выделенных
    if not target and selected_ids:
        first_id = list(selected_ids)[0]
        target = next((e for e in elements if e.id == first_id), None)

    if target:
        return {
            "exists": True,
            "id": target.id,
            "active_id": active_id,
            "selected_ids": list(selected_ids),
            "name": target.element_name,
            "pos_x": target.position[0],
            "pos_y": target.position[1],
            "width": target.size[0],
            "height": target.size[1],
            "is_multi": len(selected_ids) > 1
        }
    return None

def get_viewport_data():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    for elem in bpy.context.scene.rzm.elements:
        results.append({
            "id": elem.id, 
            "name": elem.element_name,
            "pos_x": elem.position[0], "pos_y": elem.position[1],
            "width": elem.size[0], "height": elem.size[1],
        })
    return results

# --- ПОДПИСИ (SIGNATURES) - Оставляем как есть ---
def get_structure_signature():
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        items.append((elem.id, elem.element_name, elem.elem_class))
    return hash(tuple(items))

def get_element_signature(active_id):
    if not bpy.context or not bpy.context.scene: return None
    target = next((e for e in bpy.context.scene.rzm.elements if e.id == active_id), None)
    if target:
        return hash((target.id, target.element_name, target.position[:], target.size[:]))
    return "DELETED"

def get_viewport_signature():
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        items.append((elem.id, elem.position[0], elem.position[1], elem.size[0], elem.size[1]))
    return hash(tuple(items))

# --- ЗАПИСЬ (WRITE) С ОПТИМИЗАЦИЕЙ ---

def get_next_available_id(elements):
    if len(elements) == 0: return 1
    max_id = 0
    for el in elements:
        if el.id > max_id: max_id = el.id
    return max_id + 1

def create_element(class_type, pos_x, pos_y, parent_id=-1):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True  # Блокируем обновление UI от depsgraph
    try:
        if not bpy.context or not bpy.context.scene: return None
        rzm = bpy.context.scene.rzm
        elements = rzm.elements
        
        new_id = get_next_available_id(elements)
        new_element = elements.add()
        new_element.id = new_id
        
        try:
            new_element.elem_class = class_type
        except TypeError:
            new_element.elem_class = 'CONTAINER'

        new_element.element_name = f"{class_type.capitalize()}_{new_id}"
        new_element.position = (int(pos_x), int(pos_y))
        
        # Размеры
        if class_type == 'BUTTON': new_element.size = (120, 30)
        elif class_type == 'TEXT': new_element.size = (100, 25)
        elif class_type == 'SLIDER': new_element.size = (150, 20)
        elif class_type == 'ANCHOR': new_element.size = (30, 30)
        else: new_element.size = (150, 100)
        
        if parent_id != -1 and hasattr(new_element, "parent_id"):
            new_element.parent_id = parent_id

        if class_type == 'GRID_CONTAINER':
            if hasattr(new_element, "grid_min_cells"): new_element.grid_min_cells = (1, 1)
            if hasattr(new_element, "grid_max_cells"): new_element.grid_max_cells = (5, 5)
            if hasattr(new_element, "grid_cell_size"): new_element.grid_cell_size = 64
            
        safe_undo_push(f"RZM: Create {class_type}")
        refresh_viewports()
        return new_id
    finally:
        IS_UPDATING_FROM_QT = False # Снимаем блокировку

def safe_undo_push(message):
    exec_in_context(bpy.ops.ed.undo_push, message=message)
    refresh_viewports()

def commit_history(msg):
    safe_undo_push(msg)

def update_property_multi(target_ids, prop_name, value, sub_index=None, fast_mode=False):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        changed = False
        elements = bpy.context.scene.rzm.elements
        
        for elem in elements:
            if elem.id in target_ids:
                current_val = getattr(elem, prop_name)
                if sub_index is not None:
                    if current_val[sub_index] != value:
                        current_val[sub_index] = value
                        changed = True
                else:
                    if current_val != value:
                        setattr(elem, prop_name, value)
                        changed = True
        
        if changed:
            refresh_viewports()
            
        if changed and not fast_mode:
            safe_undo_push(f"RZM: Change {prop_name}")
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
            refresh_viewports()
    finally:
        IS_UPDATING_FROM_QT = False

def delete_elements(target_ids):
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        elements = bpy.context.scene.rzm.elements
        indices_to_remove = []
        for i, elem in enumerate(elements):
            if elem.id in target_ids:
                indices_to_remove.append(i)
        
        for idx in sorted(indices_to_remove, reverse=True):
            elements.remove(idx)
            
        safe_undo_push("RZM: Delete Elements")
        refresh_viewports()
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
        
        max_idx = len(elements) - 1
        if to_index > max_idx: to_index = max_idx
        if target_idx != to_index:
            elements.move(target_idx, to_index)
            safe_undo_push("RZM: Reorder")
            refresh_viewports()
    finally:
        IS_UPDATING_FROM_QT = False