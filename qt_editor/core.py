# RZMenu/qt_editor/core.py
import bpy

# --- GLOBAL FLAGS ---
IS_UPDATING_FROM_QT = False 

# --- ЧТЕНИЕ (READ) ---

def get_active_object_safe():
    if getattr(bpy.context, "active_object", None):
        return bpy.context.active_object
    try:
        return bpy.context.view_layer.objects.active
    except AttributeError:
        return None

def get_selected_objects_safe():
    try:
        return bpy.context.selected_objects
    except AttributeError:
        try:
            return [o for o in bpy.context.view_layer.objects if o.select_get()]
        except:
            return []

def get_stable_context():
    if bpy.context.area and bpy.context.area.type == 'VIEW_3D':
        return bpy.context.copy()

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
    """
    Возвращает плоский список для Outliner.
    Исправлено: добавлены parent_id и флаги состояния.
    """
    results = []
    if not bpy.context or not bpy.context.scene: return results
    
    for elem in bpy.context.scene.rzm.elements:
        # Безопасное получение атрибутов с дефолтами
        pid = getattr(elem, "parent_id", -1)
        is_h = getattr(elem, "qt_hide", False)
        is_s = getattr(elem, "qt_selectable", True)
        
        results.append({
            "id": elem.id,
            "name": elem.element_name,
            "class_type": elem.elem_class,
            "parent_id": pid,
            "is_hidden": is_h,
            "is_selectable": is_s
        })
    return results

def get_selection_details(selected_ids, active_id):
    """
    Данные для Inspector.
    Исправлено: конвертация цветов, чтение доп. свойств.
    """
    if not bpy.context or not bpy.context.scene: return None
    elements = bpy.context.scene.rzm.elements
    target = next((e for e in elements if e.id == active_id), None)
    
    if not target and selected_ids:
        first_id = list(selected_ids)[0]
        target = next((e for e in elements if e.id == first_id), None)

    if target:
        img_id = getattr(target, "image_id", -1)
        
        # Конвертация цвета в список (blender prop array -> list)
        color_vals = [1.0, 1.0, 1.0, 1.0]
        if hasattr(target, "color"):
            color_vals = list(target.color)
            if len(color_vals) == 3: color_vals.append(1.0)

        # Сборка словаря
        data = {
            "exists": True,
            "id": target.id,
            "active_id": active_id,
            "selected_ids": list(selected_ids),
            "name": target.element_name,
            "class_type": target.elem_class,
            "pos_x": target.position[0],
            "pos_y": target.position[1],
            "width": target.size[0],
            "height": target.size[1],
            "image_id": img_id,
            "color": color_vals,
            "is_hidden": getattr(target, "qt_hide", False),
            "is_locked": getattr(target, "qt_locked", False), # Предполагаем наличие qt_locked
            "is_multi": len(selected_ids) > 1
        }

        # Специфичные свойства (например для Grid)
        if hasattr(target, "grid_cell_size"):
            data["grid_cell_size"] = target.grid_cell_size
            
        return data
        
    return None

def get_viewport_data():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    
    for elem in bpy.context.scene.rzm.elements:
        img_id = getattr(elem, "image_id", -1)
        pid = getattr(elem, "parent_id", -1)
        text_content = getattr(elem, "text_string", elem.element_name)
        
        # Color Conversion
        color_list = None
        if hasattr(elem, "color"):
            color_list = list(elem.color) # [r, g, b] or [r, g, b, a]
            if len(color_list) == 3: color_list.append(1.0)
        
        results.append({
            "id": elem.id, 
            "name": elem.element_name,
            "class_type": elem.elem_class,
            "pos_x": elem.position[0], 
            "pos_y": elem.position[1],
            "width": elem.size[0], 
            "height": elem.size[1],
            "image_id": img_id,
            "parent_id": pid,
            "text_content": text_content,
            "color": color_list,
            "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True),
            "is_locked": getattr(elem, "qt_locked", False)
        })
    return results

# --- SIGNATURES ---
def get_structure_signature():
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        # Добавляем visibility flags в сигнатуру, чтобы Outliner обновлял иконки
        is_h = getattr(elem, "qt_hide", False)
        is_s = getattr(elem, "qt_selectable", True)
        items.append((elem.id, elem.element_name, elem.elem_class, elem.parent_id, is_h, is_s))
    return hash(tuple(items))

def get_element_signature(active_id):
    if not bpy.context or not bpy.context.scene: return None
    target = next((e for e in bpy.context.scene.rzm.elements if e.id == active_id), None)
    if target:
        img_id = getattr(target, "image_id", -1)
        is_h = getattr(target, "qt_hide", False)
        is_l = getattr(target, "qt_locked", False)
        # Сигнатура изменения данных
        return hash((target.id, target.element_name, target.position[:], target.size[:], img_id, is_h, is_l))
    return "DELETED"

def get_viewport_signature():
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        img_id = getattr(elem, "image_id", -1)
        pid = getattr(elem, "parent_id", -1)
        is_h = getattr(elem, "qt_hide", False)
        is_s = getattr(elem, "qt_selectable", True)
        items.append((elem.id, elem.position[0], elem.position[1], elem.size[0], elem.size[1], img_id, pid, is_h, is_s))
    return hash(tuple(items))

# --- MATH CONVERSION ---

def to_qt_coords(blender_x, blender_y):
    """ Blender: Y Up -> Qt: Y Down """
    return int(blender_x), int(-blender_y)

def to_blender_delta(qt_dx, qt_dy):
    """ Qt Delta (Y Down) -> Blender Delta (-Y) """
    return int(qt_dx), int(-qt_dy)

def get_active_object_safe():
    if getattr(bpy.context, "active_object", None):
        return bpy.context.active_object
    try:
        return bpy.context.view_layer.objects.active
    except AttributeError:
        return None

def get_selected_objects_safe():
    try:
        return bpy.context.selected_objects
    except AttributeError:
        try:
            return [o for o in bpy.context.view_layer.objects if o.select_get()]
        except:
            return []

def get_stable_context():
    if bpy.context.area and bpy.context.area.type == 'VIEW_3D':
        return bpy.context.copy()

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
        pid = getattr(elem, "parent_id", -1)
        is_h = getattr(elem, "qt_hide", False)
        is_s = getattr(elem, "qt_selectable", True)
        
        results.append({
            "id": elem.id,
            "name": elem.element_name,
            "class_type": elem.elem_class,
            "parent_id": pid,
            "is_hidden": is_h,
            "is_selectable": is_s
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
        img_id = getattr(target, "image_id", -1)
        
        color_vals = [1.0, 1.0, 1.0, 1.0]
        if hasattr(target, "color"):
            color_vals = list(target.color)
            if len(color_vals) == 3: color_vals.append(1.0)

        data = {
            "exists": True,
            "id": target.id,
            "active_id": active_id,
            "selected_ids": list(selected_ids),
            "name": target.element_name,
            "class_type": target.elem_class,
            "pos_x": target.position[0],
            "pos_y": target.position[1],
            "width": target.size[0],
            "height": target.size[1],
            "image_id": img_id,
            "color": color_vals,
            "is_hidden": getattr(target, "qt_hide", False),
            "is_locked": getattr(target, "qt_locked", False),
            "is_multi": len(selected_ids) > 1
        }

        if hasattr(target, "grid_cell_size"):
            data["grid_cell_size"] = target.grid_cell_size
            
        return data
        
    return None

def get_viewport_data():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    
    for elem in bpy.context.scene.rzm.elements:
        img_id = getattr(elem, "image_id", -1)
        pid = getattr(elem, "parent_id", -1)
        text_content = getattr(elem, "text_string", elem.element_name)
        
        color_list = None
        if hasattr(elem, "color"):
            color_list = list(elem.color) 
            if len(color_list) == 3: color_list.append(1.0)
        
        results.append({
            "id": elem.id, 
            "name": elem.element_name,
            "class_type": elem.elem_class,
            "pos_x": elem.position[0], 
            "pos_y": elem.position[1],
            "width": elem.size[0], 
            "height": elem.size[1],
            "image_id": img_id,
            "parent_id": pid,
            "text_content": text_content,
            "color": color_list,
            "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True),
            "is_locked": getattr(elem, "qt_locked", False)
        })
    return results

def get_structure_signature():
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        is_h = getattr(elem, "qt_hide", False)
        is_s = getattr(elem, "qt_selectable", True)
        items.append((elem.id, elem.element_name, elem.elem_class, elem.parent_id, is_h, is_s))
    return hash(tuple(items))

def get_element_signature(active_id):
    if not bpy.context or not bpy.context.scene: return None
    target = next((e for e in bpy.context.scene.rzm.elements if e.id == active_id), None)
    if target:
        img_id = getattr(target, "image_id", -1)
        is_h = getattr(target, "qt_hide", False)
        is_l = getattr(target, "qt_locked", False)
        return hash((target.id, target.element_name, target.position[:], target.size[:], img_id, is_h, is_l))
    return "DELETED"

def get_viewport_signature():
    if not bpy.context or not bpy.context.scene: return None
    items = []
    for elem in bpy.context.scene.rzm.elements:
        img_id = getattr(elem, "image_id", -1)
        pid = getattr(elem, "parent_id", -1)
        is_h = getattr(elem, "qt_hide", False)
        is_s = getattr(elem, "qt_selectable", True)
        items.append((elem.id, elem.position[0], elem.position[1], elem.size[0], elem.size[1], img_id, pid, is_h, is_s))
    return hash(tuple(items))

# --- MATH CONVERSION ---

def to_qt_coords(blender_x, blender_y):
    """ Blender: Y Up -> Qt: Y Down """
    return int(blender_x), int(-blender_y)

def to_blender_delta(qt_dx, qt_dy):
    """ Qt Delta (Y Down) -> Blender Delta (-Y) """
    return int(qt_dx), int(-qt_dy)

# --- WRITE ---

def get_next_available_id(elements):
    if len(elements) == 0: return 1
    max_id = 0
    for el in elements:
        if el.id > max_id: max_id = el.id
    return max_id + 1

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
        
        if parent_id != -1:
            new_element.parent_id = parent_id
            
        safe_undo_push(f"RZM: Create {class_type}")
        refresh_viewports()
        return new_id
    finally:
        IS_UPDATING_FROM_QT = False

def safe_undo_push(message):
    exec_in_context(bpy.ops.ed.undo_push, message=message)
    refresh_viewports()

def commit_history(msg):
    safe_undo_push(msg)

def unhide_all_elements():
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if getattr(elem, "qt_hide", False):
                elem.qt_hide = False
                changed = True
        
        if changed:
            safe_undo_push("RZM: Unhide All")
            refresh_viewports()
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
            "color": ("color", None)
        }

        bl_prop = prop_name
        bl_idx = sub_index

        if prop_name in map_props:
            bl_prop, fixed_idx = map_props[prop_name]
            if fixed_idx is not None:
                bl_idx = fixed_idx
        
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
        
        if changed:
            refresh_viewports()
        if changed and not fast_mode:
            safe_undo_push(f"RZM: Change {prop_name}")
    finally:
        IS_UPDATING_FROM_QT = False

def resize_element(elem_id, x, y, w, h):
    """
    Атомарное обновление позиции и размера.
    """
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        target = next((e for e in elements if e.id == elem_id), None)
        if target:
            # Обновляем все 4 свойства разом
            target.position[0] = int(x)
            target.position[1] = int(y)
            target.size[0] = int(w)
            target.size[1] = int(h)
            refresh_viewports()
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