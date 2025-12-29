# RZMenu/qt_editor/core.py
import bpy

# --- ЧТЕНИЕ (READ) ---

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
    """
    Возвращает данные для Инспектора.
    Стратегия: Возвращаем данные Активного элемента.
    Но добавляем флаг is_multi, чтобы UI знал, что мы редактируем группу.
    """
    if not bpy.context or not bpy.context.scene: return None
    elements = bpy.context.scene.rzm.elements
    
    # Ищем активный элемент
    target = next((e for e in elements if e.id == active_id), None)
    
    # Если активный удален, берем любой из выделенных
    if not target and selected_ids:
        first_id = list(selected_ids)[0]
        target = next((e for e in elements if e.id == first_id), None)

    if target:
        return {
            "exists": True,
            "id": target.id,
            "active_id": active_id,
            "selected_ids": list(selected_ids), # Превращаем set в list для передачи
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

# --- ПОДПИСИ (SIGNATURES) ---

def get_structure_signature():
    # Хэш структуры списка (для обновления Аутлайнера)
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        items.append((elem.id, elem.element_name, elem.elem_class))
    return hash(tuple(items))

def get_element_signature(active_id):
    # Хэш для Инспектора (следим за активным)
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

# --- ЗАПИСЬ (WRITE) ---

def safe_undo_push(message):
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                with bpy.context.temp_override(window=window, area=area):
                    bpy.ops.ed.undo_push(message=message)
                return
    # Fallback
    try: bpy.ops.ed.undo_push(message=message)
    except: pass

def update_property_multi(target_ids, prop_name, value, sub_index=None, fast_mode=False):
    """
    Применяет значение ко ВСЕМ переданным ID.
    Если fast_mode=True, не вызывает Undo (для драга).
    """
    if not target_ids: return
    
    changed = False
    elements = bpy.context.scene.rzm.elements
    
    for elem in elements:
        if elem.id in target_ids:
            current_val = getattr(elem, prop_name)
            
            # Векторное свойство (Position, Size)
            if sub_index is not None:
                if current_val[sub_index] != value:
                    current_val[sub_index] = value
                    changed = True
            # Скалярное свойство (Name, Class)
            else:
                if current_val != value:
                    setattr(elem, prop_name, value)
                    changed = True
                    
    if changed and not fast_mode:
        safe_undo_push(f"RZM: Change {prop_name}")

def move_elements_delta(target_ids, delta_x, delta_y):
    """
    Сдвигает группу элементов на смещение (Delta).
    Используется для перетаскивания во вьюпорте.
    """
    if not target_ids: return
    elements = bpy.context.scene.rzm.elements
    
    for elem in elements:
        if elem.id in target_ids:
            elem.position[0] += int(delta_x)
            elem.position[1] += int(delta_y)

def delete_elements(target_ids):
    if not target_ids: return
    
    # Удаляем с конца, чтобы не сбить индексы, хотя 'remove' по индексу работает иначе.
    # В CollectionProperty лучше собирать индексы для удаления.
    elements = bpy.context.scene.rzm.elements
    
    # Собираем индексы
    indices_to_remove = []
    for i, elem in enumerate(elements):
        if elem.id in target_ids:
            indices_to_remove.append(i)
            
    # Удаляем (важно: от большего к меньшему)
    for idx in sorted(indices_to_remove, reverse=True):
        elements.remove(idx)
        
    safe_undo_push("RZM: Delete Elements")

def reorder_elements(target_id, insert_after_id):
    # Reorder пока работает только для одного элемента (Drag&Drop сложен для мульти)
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

def commit_history(msg):
    safe_undo_push(msg)