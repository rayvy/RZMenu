# RZMenu/qt_editor/logic.py
import bpy

# --- ЧТЕНИЕ ДАННЫХ (Data Access) ---

def get_scene_info():
    if not bpy.context or not bpy.context.scene:
        return {"count": 0, "name": "No Scene"}
    rzm = bpy.context.scene.rzm
    return {
        "count": len(rzm.elements),
        "scene_name": bpy.context.scene.name,
        "mode": bpy.context.scene.rzm_editor_mode
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

def get_element_details(element_id):
    if not bpy.context or not bpy.context.scene: return None
    target = next((e for e in bpy.context.scene.rzm.elements if e.id == element_id), None)
    if target:
        return {
            "exists": True,
            "id": target.id,
            "name": target.element_name,
            "pos_x": target.position[0],
            "pos_y": target.position[1],
            "width": target.size[0],
            "height": target.size[1],
        }
    return None

# --- ГЕНЕРАЦИЯ ПОДПИСЕЙ (Signatures) ---
# Новая часть концепции: легкие слепки состояния

def get_structure_signature():
    """
    Хэш для Списка (Outliner).
    Зависит от: ID, Имени, Класса и Количества.
    Если меняется только позиция X/Y - этот хэш НЕ меняется (список не мигает).
    """
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        items.append((elem.id, elem.element_name, elem.elem_class))
    return tuple(items)

def get_element_signature(element_id):
    """
    Возвращает слепок свойств конкретного элемента.
    Нужен, чтобы понять, надо ли обновлять Инспектор.
    """
    if not bpy.context or not bpy.context.scene: return None
    target = next((e for e in bpy.context.scene.rzm.elements if e.id == element_id), None)
    
    if target:
        # Следим только за теми свойствами, которые отображаются в Инспекторе
        return (
            target.id,
            target.element_name,
            target.position[0],
            target.position[1],
            target.size[0],
            target.size[1]
        )
    return "DELETED" # Специальный маркер, если элемент исчез

# --- ЗАПИСЬ (WRITE) ---

def update_property(element_id, prop_name, value, sub_index=None):
    target = next((e for e in bpy.context.scene.rzm.elements if e.id == element_id), None)
    if target:
        current_val = getattr(target, prop_name)
        if sub_index is not None:
            if current_val[sub_index] == value: return
            current_val[sub_index] = value
        else:
            if current_val == value: return
            setattr(target, prop_name, value)
        bpy.ops.ed.undo_push(message=f"RZM UI Change: {prop_name}")

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

def get_viewport_signature():
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        items.append((elem.id, elem.position[0], elem.position[1], elem.size[0], elem.size[1]))
    return tuple(items)

def safe_undo_push(message):
    """
    Магическая функция, которая находит правильное окно Блендера
    и заставляет undo_push сработать, даже если мы в Qt.
    """
    # Ищем любое 3D окно или просто главное окно
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                # Подделываем контекст
                with bpy.context.temp_override(window=window, area=area):
                    bpy.ops.ed.undo_push(message=message)
                return
    
    # Если 3D View не нашли, пробуем просто с окном (менее надежно, но может сработать)
    if bpy.context.window_manager.windows:
         with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
             try:
                bpy.ops.ed.undo_push(message=message)
             except:
                 print("RZM: Could not find valid context for Undo")

def update_property_fast(element_id, prop_name, value, sub_index=None):
    """
    БЫСТРАЯ запись. Меняет данные, но НЕ создает Undo стейт.
    Используется во время перетаскивания (Drag).
    """
    target = next((e for e in bpy.context.scene.rzm.elements if e.id == element_id), None)
    if not target: return

    current_val = getattr(target, prop_name)
    if sub_index is not None:
        if current_val[sub_index] != value:
            current_val[sub_index] = value
    else:
        if current_val != value:
            setattr(target, prop_name, value)
            
    # НЕ вызываем undo_push здесь!

def commit_history(msg):
    """Вызывается ОДИН раз, когда мышку отпустили."""
    safe_undo_push(msg)

def reorder_elements(target_id, insert_after_id):
    """
    Перемещает элемент с target_id в позицию сразу после insert_after_id.
    Если insert_after_id is None, перемещает в начало списка.
    """
    if not bpy.context or not bpy.context.scene: return

    elements = bpy.context.scene.rzm.elements
    
    # 1. Ищем текущие индексы
    target_idx = -1
    anchor_idx = -1
    
    for i, elem in enumerate(elements):
        if elem.id == target_id:
            target_idx = i
        if insert_after_id is not None and elem.id == insert_after_id:
            anchor_idx = i
    
    # Если целевой элемент не найден - выходим
    if target_idx == -1:
        return

    # 2. Вычисляем новый индекс (to_index)
    to_index = 0
    
    if insert_after_id is None:
        # Перенос в самое начало
        to_index = 0
    else:
        # Если якорь не найден, ничего не делаем
        if anchor_idx == -1:
            return
            
        if target_idx == anchor_idx:
            return # Пытаемся вставить сами после себя

        # Логика смещения индексов для move(from, to):
        if target_idx < anchor_idx:
            # Двигаем ВНИЗ (target был выше anchor).
            # Пример: [A(0), B(1), C(2)]. Move A after B.
            # target=0, anchor=1. 
            # move(0, 1) -> [B, A, C]. A встает на индекс 1 (бывший B). B смещается на 0.
            # Результат: A после B.
            to_index = anchor_idx
        else:
            # Двигаем ВВЕРХ (target был ниже anchor).
            # Пример: [A(0), B(1), C(2)]. Move C after A.
            # target=2, anchor=0.
            # move(2, 1) -> [A, C, B]. C встает на индекс 1.
            # Нам нужно встать ПОСЛЕ anchor, т.е. anchor + 1.
            to_index = anchor_idx + 1

    # 3. Применяем перемещение
    # Защита от выхода за границы (хотя логика выше должна быть верной)
    max_idx = len(elements) - 1
    if to_index > max_idx: to_index = max_idx
    
    if target_idx != to_index:
        elements.move(target_idx, to_index)
        # Добавляем в историю Undo, чтобы перемещение можно было отменить
        safe_undo_push(message="RZM: Reorder List")