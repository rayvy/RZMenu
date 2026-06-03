# RZMenu/qt_editor/clipboard.py
import bpy
from . import structure
from . import signals
from . import blender_bridge

_INTERNAL_CLIPBOARD = []
_STYLE_CLIPBOARD = None

STYLE_FIELDS = (
    "color",
    "color_is_formula",
    "color_formula_r",
    "color_formula_g",
    "color_formula_b",
    "color_formula_a",
    "style_id",
    "disable_button_nums",
    "disable_button_popup",
    "disable_slider_nums",
    "disable_slider_blur",
    "disable_slider_prebuild_render",
    "slider_logic_invert_x",
    "slider_logic_invert_y",
    "disable_default_xy",
)


def _find_element_by_id(elem_id):
    if not bpy.context or not bpy.context.scene:
        return None
    for elem in bpy.context.scene.rzm.elements:
        if elem.id == elem_id:
            return elem
    return None


def _id_collection_values(collection, attr_name):
    return [getattr(item, attr_name) for item in collection]


def _replace_id_collection(collection, values, attr_name):
    old_values = _id_collection_values(collection, attr_name)
    new_values = [int(v) for v in values]
    if old_values == new_values:
        return False

    while len(collection):
        collection.remove(len(collection) - 1)

    for value in new_values:
        item = collection.add()
        setattr(item, attr_name, value)

    return True


def copy_style(source_id):
    global _STYLE_CLIPBOARD

    elem = _find_element_by_id(source_id)
    if not elem:
        return False

    data = {}
    for field in STYLE_FIELDS:
        if not hasattr(elem, field):
            continue
        value = getattr(elem, field)
        data[field] = list(value) if field == "color" else value

    data["preset_ids"] = [p.preset_id for p in elem.preset_ids] if hasattr(elem, "preset_ids") else []
    data["underlayer_preset_ids"] = [p.preset_id for p in elem.underlayer_preset_ids] if hasattr(elem, "underlayer_preset_ids") else []
    data["helper_ids"] = [h.helper_id for h in elem.helper_ids] if hasattr(elem, "helper_ids") else []

    _STYLE_CLIPBOARD = data
    return True


def has_style_clipboard():
    return _STYLE_CLIPBOARD is not None


def paste_style(target_ids):
    global _STYLE_CLIPBOARD

    if not _STYLE_CLIPBOARD or not target_ids:
        return 0
    if not bpy.context or not bpy.context.scene:
        return 0

    changed_count = 0
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        targets = [elem for elem in elements if elem.id in target_ids]

        for elem in targets:
            changed = False

            for field in STYLE_FIELDS:
                if field not in _STYLE_CLIPBOARD or not hasattr(elem, field):
                    continue

                new_value = _STYLE_CLIPBOARD[field]
                if field == "color":
                    current = list(getattr(elem, field))
                    if current != list(new_value):
                        setattr(elem, field, list(new_value)[:len(current)])
                        changed = True
                elif getattr(elem, field) != new_value:
                    setattr(elem, field, new_value)
                    changed = True

            if hasattr(elem, "preset_ids"):
                changed |= _replace_id_collection(elem.preset_ids, _STYLE_CLIPBOARD.get("preset_ids", []), "preset_id")
            if hasattr(elem, "underlayer_preset_ids"):
                changed |= _replace_id_collection(elem.underlayer_preset_ids, _STYLE_CLIPBOARD.get("underlayer_preset_ids", []), "preset_id")
            if hasattr(elem, "helper_ids"):
                changed |= _replace_id_collection(elem.helper_ids, _STYLE_CLIPBOARD.get("helper_ids", []), "helper_id")

            if changed:
                changed_count += 1

        if changed_count:
            blender_bridge.safe_undo_push("RZM: Paste Style")
            signals.SIGNALS.data_changed.emit()
            signals.SIGNALS.structure_changed.emit()
            signals.SIGNALS.transform_changed.emit()

    return changed_count

def copy_elements(target_ids):
    global _INTERNAL_CLIPBOARD
    _INTERNAL_CLIPBOARD.clear()
    
    if not target_ids: return
    if not bpy.context or not bpy.context.scene: return
    elements = bpy.context.scene.rzm.elements
    
    elem_map = {e.id: e for e in elements}
    from .maths import get_global_pos

    for elem in elements:
        if elem.id in target_ids:
            gx, gy = get_global_pos(elem, elem_map)
            data = {
                "name": elem.element_name,
                "class": elem.elem_class,
                "pos": list(elem.position),
                "global_pos": [gx, gy],
                "size": list(elem.size),
                "color": list(elem.color) if hasattr(elem, "color") else [1,1,1,1],
                "alignment": elem.alignment,
                "text_align": elem.text_align,
                "text_id": elem.text_id,
                "hover_text_id": elem.hover_text_id,
                "tag": elem.tag,
                "priority": elem.priority,
                "is_main_window": elem.is_main_window,
                
                "pos_is_formula": elem.position_is_formula,
                "size_is_formula": elem.size_is_formula,
                "rotation_is_formula": getattr(elem, "rotation_is_formula", False),
                "transform_is_formula": getattr(elem, "transform_is_formula", False),

                "pos_formula_x": elem.position_formula_x,
                "pos_formula_y": elem.position_formula_y,
                "size_formula_x": elem.size_formula_x,
                "size_formula_y": elem.size_formula_y,
                "rotation": getattr(elem, "rotation", 0.0),
                "rotation_formula": getattr(elem, "rotation_formula", ""),
                "transform_formula": getattr(elem, "transform_formula", ""),
                
                "image_id": elem.image_id,
                "hover_image_id": getattr(elem, "hover_image_id", -1),
                "extramap_image_id": getattr(elem, "extramap_image_id", -1),
                "image_mode": elem.image_mode,
                "image_blending_mode": getattr(elem, "image_blending_mode", 'NONE'),
                "tile_uv": list(elem.tile_uv),
                "tile_size": list(elem.tile_size),
                "flip_x": getattr(elem, "flip_x", False),
                "flip_y": getattr(elem, "flip_y", False),

                "svg_scale": getattr(elem, "svg_scale", 1.0),
                "svg_offset": list(getattr(elem, "svg_offset", [0.0, 0.0])),
                
                "color_is_formula": elem.color_is_formula,
                "color_formula_r": elem.color_formula_r,
                "color_formula_g": elem.color_formula_g,
                "color_formula_b": elem.color_formula_b,
                "color_formula_a": elem.color_formula_a,
                "value_link_is_formula": elem.value_link_is_formula,
                "value_link_formula": elem.value_link_formula,
                
                "is_preset": getattr(elem, "is_preset", False),
                "is_helper": getattr(elem, "is_helper", False),
                "is_template_prefab": getattr(elem, "is_template_prefab", False),
                "template_prefab": getattr(elem, "template_prefab", 'MAIN_BLOCK'),
                
                "qt_preset_hide": getattr(elem, "qt_preset_hide", False),
                "preset_ids": [p.preset_id for p in elem.preset_ids] if hasattr(elem, "preset_ids") else [],
                "underlayer_preset_ids": [p.preset_id for p in elem.underlayer_preset_ids] if hasattr(elem, "underlayer_preset_ids") else [],
                "helper_ids": [h.helper_id for h in elem.helper_ids] if hasattr(elem, "helper_ids") else [],
                "export_tiers": [t.tier_id for t in elem.export_tiers] if hasattr(elem, "export_tiers") else [],

                "visibility_mode": elem.visibility_mode,
                "visibility_condition": elem.visibility_condition,
                "hide": getattr(elem, "qt_hide", False),
                "lock_pos": getattr(elem, "qt_lock_pos", False),
                "lock_size": getattr(elem, "qt_lock_size", False),
                "lock_ratio": getattr(elem, "qt_lock_ratio", False),
                "selectable": getattr(elem, "qt_selectable", True),
                
                "grid_cell_size": elem.grid_cell_size,
                "grid_min_cells": list(elem.grid_min_cells),
                "grid_max_cells": list(elem.grid_max_cells),
                "grid_wrap_mode": elem.grid_wrap_mode,
                
                "disable_button_nums": elem.disable_button_nums,
                "disable_button_popup": elem.disable_button_popup,
                "disable_slider_nums": getattr(elem, "disable_slider_nums", False),
                "disable_slider_blur": getattr(elem, "disable_slider_blur", False),
                "disable_slider_prebuild_render": getattr(elem, "disable_slider_prebuild_render", False),
                "slider_logic_invert_x": getattr(elem, "slider_logic_invert_x", False),
                "slider_logic_invert_y": getattr(elem, "slider_logic_invert_y", False),
                
                "hover_event_enabled": elem.hover_event_enabled,
                "hover_event_formula": elem.hover_event_formula,
                "click_event_enabled": elem.click_event_enabled,
                "click_event_formula": elem.click_event_formula,
                "hold_event_enabled": elem.hold_event_enabled,
                "hold_event_formula": elem.hold_event_formula,
                
                "conditional_images": [{"condition": ci.condition, "image_id": ci.image_id} for ci in elem.conditional_images],
                "text_mode": elem.text_mode,
                "text_id_is_data": getattr(elem, "text_id_is_data", False),
                "text_id_data_length": getattr(elem, "text_id_data_length", 1),
                "hover_text_id_is_data": getattr(elem, "hover_text_id_is_data", False),
                "hover_text_id_data_length": getattr(elem, "hover_text_id_data_length", 1),
                "conditional_texts": [
                    {
                        "condition": ct.condition, 
                        "text_id": ct.text_id,
                        "localized_texts": [{"lang": lt.language_index, "text": lt.text_id, "hover": lt.hover_text_id} for lt in ct.localized_texts]
                    } for ct in elem.conditional_texts
                ],
                "localized_texts": [{"lang": lt.language_index, "text": lt.text_id, "hover": lt.hover_text_id} for lt in elem.localized_texts],
                "value_links": [{"name": vl.value_name, "min": vl.value_min, "max": vl.value_max} for vl in elem.value_link],
                "fx": [fx.value for fx in elem.fx],
                "fn": [fn_item.function_name for fn_item in elem.fn],
                "properties": [{"key": p.key, "type": p.value_type, "s": p.string_value, "i": p.int_value, "f": p.float_value} for p in elem.properties],
                "toggles": [{"name": t.toggle_name, "bits": [b.value for b in t.bits]} for t in elem.toggles],
                "disable_default_xy": getattr(elem, "disable_default_xy", False),
                
                "style_id": getattr(elem, "style_id", -1),
                "font_slot": getattr(elem, "font_slot", 0),
                "is_tab_container": getattr(elem, "is_tab_container", False),
                "page_color": list(getattr(elem, "page_color", [0.5, 0.5, 0.5, 1.0])),
                "disable_export": getattr(elem, "disable_export", False),
                "trackable": getattr(elem, "trackable", False),
                "run_link_id": getattr(elem, "run_link_id", -1),
            }
            _INTERNAL_CLIPBOARD.append(data)

def paste_elements(target_x=None, target_y=None, offset=20, parent_id=-1, mode='GLOBAL'):
    global _INTERNAL_CLIPBOARD
    if not _INTERNAL_CLIPBOARD: return []
    
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return []
        rzm = bpy.context.scene.rzm
        elements = rzm.elements
        new_ids = []

        # Map for coordinate math
        elem_map = {e.id: e for e in elements}

        offset_x = 0
        offset_y = 0
        
        # Calculate offset based on target (usually mouse)
        # For LOCAL mode, we ignore mouse target to ensure absolute 1:1 values as requested
        if mode != 'LOCAL' and target_x is not None and target_y is not None:
            ref_key = "global_pos" if mode == 'GLOBAL' else "pos"
            min_x = min(item[ref_key][0] for item in _INTERNAL_CLIPBOARD)
            min_y = min(item[ref_key][1] for item in _INTERNAL_CLIPBOARD)
            offset_x = target_x - min_x
            offset_y = target_y - min_y
        else:
            offset_x = offset
            offset_y = -offset

        from .maths import get_local_pos_from_global

        for item in _INTERNAL_CLIPBOARD:
            new_id = structure.get_next_available_id(elements)
            new_elem = elements.add()
            new_id = new_elem.id = new_id
            new_elem.element_name = item["name"] + "_copy"
            new_elem.elem_class = item["class"]
            
            if mode == 'LOCAL':
                # 1:1 Preservation (ignore parent transforms)
                new_elem.parent_id = parent_id
                new_elem.position[0] = item["pos"][0] + offset_x
                new_elem.position[1] = item["pos"][1] + offset_y
            else:
                # GLOBAL Preservation (default)
                # Calculate new target global pos
                gx = item.get("global_pos", item["pos"])[0] + offset_x
                gy = item.get("global_pos", item["pos"])[1] + offset_y
                
                # Parenting & Coord Conversion
                if parent_id != -1:
                    new_elem.parent_id = parent_id
                    lx, ly = get_local_pos_from_global(gx, gy, parent_id, elem_map)
                    new_elem.position = (int(lx), int(ly))
                else:
                    new_elem.parent_id = -1
                    new_elem.position = (int(gx), int(gy))
            
            new_elem.size = item["size"]
            new_elem.rotation = item.get("rotation", 0.0)
            
            # Simple Props
            new_elem.color = item.get("color", [1,1,1,1])
            new_elem.alignment = item.get("alignment", "BOTTOM_LEFT")
            new_elem.text_align = item.get("text_align", "LEFT")
            new_elem.text_id = item.get("text_id", "")
            new_elem.hover_text_id = item.get("hover_text_id", "")
            new_elem.tag = item.get("tag", "")
            new_elem.priority = item.get("priority", 0)
            new_elem.qt_priority = item.get("qt_priority", 0)
            new_elem.is_main_window = item.get("is_main_window", False)
            new_elem.is_tab_container = item.get("is_tab_container", False)
            new_elem.page_color = item.get("page_color", [0.5, 0.5, 0.5, 1.0])
            
            new_elem.position_is_formula = item.get("pos_is_formula", False)
            new_elem.size_is_formula = item.get("size_is_formula", False)
            new_elem.rotation_is_formula = item.get("rotation_is_formula", False)
            new_elem.transform_is_formula = item.get("transform_is_formula", False)

            new_elem.position_formula_x = item.get("pos_formula_x", "")
            new_elem.position_formula_y = item.get("pos_formula_y", "")
            new_elem.size_formula_x = item.get("size_formula_x", "")
            new_elem.size_formula_y = item.get("size_formula_y", "")
            new_elem.rotation_formula = item.get("rotation_formula", "")
            new_elem.transform_formula = item.get("transform_formula", "")
            
            # Image Props
            new_elem.image_id = item.get("image_id", -1)
            new_elem.hover_image_id = item.get("hover_image_id", -1)
            new_elem.extramap_image_id = item.get("extramap_image_id", -1)
            new_elem.image_mode = item.get("image_mode", "SINGLE")
            new_elem.image_blending_mode = item.get("image_blending_mode", "NONE")
            new_elem.tile_uv = item.get("tile_uv", [0,0])
            new_elem.tile_size = item.get("tile_size", [1,1])
            new_elem.flip_x = item.get("flip_x", False)
            new_elem.flip_y = item.get("flip_y", False)

            new_elem.svg_scale = item.get("svg_scale", 1.0)
            new_elem.svg_offset = item.get("svg_offset", [0.0, 0.0])
            
            new_elem.color_is_formula = item.get("color_is_formula", False)
            new_elem.color_formula_r = item.get("color_formula_r", "1")
            new_elem.color_formula_g = item.get("color_formula_g", "1")
            new_elem.color_formula_b = item.get("color_formula_b", "1")
            new_elem.color_formula_a = item.get("color_formula_a", "1")
            new_elem.value_link_is_formula = item.get("value_link_is_formula", False)
            new_elem.value_link_formula = item.get("value_link_formula", "")
            
            new_elem.is_preset = item.get("is_preset", False)
            new_elem.is_helper = item.get("is_helper", False)
            new_elem.is_template_prefab = item.get("is_template_prefab", False)
            new_elem.template_prefab = item.get("template_prefab", 'MAIN_BLOCK')
            new_elem.qt_preset_hide = item.get("qt_preset_hide", False)
            
            new_elem.visibility_mode = item.get("visibility_mode", "ALWAYS")
            new_elem.visibility_condition = item.get("visibility_condition", "")
            new_elem.qt_hide = item.get("hide", False)
            new_elem.qt_lock_pos = item.get("lock_pos", False)
            new_elem.qt_lock_size = item.get("lock_size", False)
            new_elem.qt_lock_ratio = item.get("lock_ratio", False)
            new_elem.qt_selectable = item.get("selectable", True)
            
            new_elem.grid_cell_size = item.get("grid_cell_size", 50)
            new_elem.grid_min_cells = item.get("grid_min_cells", [1,1])
            new_elem.grid_max_cells = item.get("grid_max_cells", [1,1])
            new_elem.grid_wrap_mode = item.get("grid_wrap_mode", "SCROLL")
            
            new_elem.disable_button_nums = item.get("disable_button_nums", False)
            new_elem.disable_button_popup = item.get("disable_button_popup", False)
            new_elem.disable_slider_nums = item.get("disable_slider_nums", False)
            new_elem.disable_slider_blur = item.get("disable_slider_blur", False)
            new_elem.disable_slider_prebuild_render = item.get("disable_slider_prebuild_render", False)
            new_elem.slider_logic_invert_x = item.get("slider_logic_invert_x", False)
            new_elem.slider_logic_invert_y = item.get("slider_logic_invert_y", False)
            
            new_elem.hover_event_enabled = item.get("hover_event_enabled", False)
            new_elem.hover_event_formula = item.get("hover_event_formula", "")
            new_elem.click_event_enabled = item.get("click_event_enabled", False)
            new_elem.click_event_formula = item.get("click_event_formula", "")
            new_elem.hold_event_enabled = item.get("hold_event_enabled", False)
            new_elem.hold_event_formula = item.get("hold_event_formula", "")
            
            new_elem.text_mode = item.get("text_mode", "SINGLE")
            new_elem.text_id_is_data = item.get("text_id_is_data", False)
            new_elem.text_id_data_length = item.get("text_id_data_length", 1)
            new_elem.hover_text_id_is_data = item.get("hover_text_id_is_data", False)
            new_elem.hover_text_id_data_length = item.get("hover_text_id_data_length", 1)
            
            new_elem.style_id = item.get("style_id", -1)
            new_elem.font_slot = item.get("font_slot", 0)
            new_elem.disable_export = item.get("disable_export", False)
            new_elem.trackable = item.get("trackable", False)
            new_elem.run_link_id = item.get("run_link_id", -1)

            # Collections
            if "preset_ids" in item:
                for pid in item["preset_ids"]:
                    new_p = new_elem.preset_ids.add()
                    new_p.preset_id = pid
            if "underlayer_preset_ids" in item:
                for pid in item["underlayer_preset_ids"]:
                    new_p = new_elem.underlayer_preset_ids.add()
                    new_p.preset_id = pid
            if "helper_ids" in item:
                for hid in item["helper_ids"]:
                    new_h = new_elem.helper_ids.add()
                    new_h.helper_id = hid
            if "export_tiers" in item:
                for tid in item["export_tiers"]:
                    new_t = new_elem.export_tiers.add()
                    new_t.tier_id = tid

            for ci in item.get("conditional_images", []):
                new_ci = new_elem.conditional_images.add()
                new_ci.condition = ci["condition"]
                new_ci.image_id = ci["image_id"]
                
            for vl in item.get("value_links", []):
                new_vl = new_elem.value_link.add()
                new_vl.value_name = vl["name"]
                new_vl.value_min = vl["min"]
                new_vl.value_max = vl["max"]
                
            for fx_val in item.get("fx", []):
                new_fx = new_elem.fx.add()
                new_fx.value = fx_val
                
            for fn_val in item.get("fn", []):
                new_fn = new_elem.fn.add()
                new_fn.function_name = fn_val
                
            for p_item in item.get("properties", []):
                new_p = new_elem.properties.add()
                new_p.key = p_item["key"]
                new_p.value_type = p_item["type"]
                new_p.string_value = p_item["s"]
                new_p.int_value = p_item["i"]
                new_p.float_value = p_item["f"]
                
            for t_item in item.get("toggles", []):
                new_t = new_elem.toggles.add()
                new_t.toggle_name = t_item["name"]
                for b_val in t_item.get("bits", []):
                    new_b = new_t.bits.add()
                    new_b.value = b_val
                
            new_elem.disable_default_xy = item.get("disable_default_xy", False)

            for ct in item.get("conditional_texts", []):
                new_ct = new_elem.conditional_texts.add()
                new_ct.condition = ct["condition"]
                new_ct.text_id = ct["text_id"]
                if "localized_texts" in ct:
                    for lt in ct["localized_texts"]:
                        new_lt = new_ct.localized_texts.add()
                        new_lt.language_index = lt["lang"]
                        new_lt.text_id = lt["text"]
                        new_lt.hover_text_id = lt["hover"]

            for lt in item.get("localized_texts", []):
                new_lt = new_elem.localized_texts.add()
                new_lt.language_index = lt["lang"]
                new_lt.text_id = lt["text"]
                new_lt.hover_text_id = lt["hover"]
            
            new_ids.append(new_id)

            
            new_ids.append(new_id)
            
        blender_bridge.safe_undo_push("RZM: Paste")
        signals.SIGNALS.structure_changed.emit()
        signals.SIGNALS.transform_changed.emit()
        return new_ids

    finally:
        signals.IS_UPDATING_FROM_QT = False
