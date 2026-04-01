import bpy
import os
import json
import zipfile
import re
from pathlib import Path
from .serialization import rzm_to_dict, dict_to_rzm
from ..data.p_settings import log_amc

# Gitignore-like system for prefabs
# Key is the prefab type (MAIN_BLOCK, PAGE_BLOCK, BUTTONS)
# Values are properties that should BE IGNORED during template-to-scene reconstruction
RZMIgnoreMap = {
    'ANY': ['id', 'parent_id', 'element_name', 'is_template_prefab', 'template_prefab'], # Always ignore these
    'MAIN_BLOCK': ['position', 'position_is_formula', 'position_formula_x', 'position_formula_y', 'alignment'],
    'PAGE_BLOCK': [], # User mentioned no specific ignores for Page Block yet
    'BUTTONS': ['value_link', 'value_link_is_formula', 'value_link_formula', 'toggles'],
}

def find_active_toggles(context):
    """
    Scans all mesh objects in the scene for 'rzm.Toggle.X' custom properties.
    Returns a sorted list of unique toggle names.
    """
    toggles = set()
    # Check all objects for custom properties starting with rzm.Toggle.
    for obj in context.scene.objects:
        if obj.type != 'MESH': continue
        for key in obj.keys():
            if key.startswith("rzm.Toggle."):
                toggle_name = key.replace("rzm.Toggle.", "")
                if toggle_name:
                    toggles.add(toggle_name)
    
    # Sort alphabetically for consistent menu layout
    return sorted(list(toggles))

def find_matching_icon(context, toggle_name):
    """
    Modular search algorithm for icons. 
    Searches in base_icons and custom_asset_library.
    Returns the image_id of the found icon or -1.
    """
    # 1. Prepare search patterns
    # Normalize name: Toggle_Hair -> hair
    clean_name = toggle_name.lower().replace("toggle_", "").strip()
    
    # 2. Get Search Paths
    addon_dir = Path(__file__).parent.parent
    search_dirs = [addon_dir / "base_icons"]
    
    # Check addon preferences for custom library
    prefs = context.preferences.addons[__package__.split('.')[0]].preferences
    if prefs.custom_asset_library:
        custom_path = Path(bpy.path.abspath(prefs.custom_asset_library))
        if custom_path.exists():
            search_dirs.insert(0, custom_path) # Search custom first

    # 3. Scanning
    # We look for files that contain the clean_name
    for s_dir in search_dirs:
        if not s_dir.exists(): continue
        for f in s_dir.iterdir():
            if f.is_file() and f.suffix.lower() in {'.png', '.dds', '.tga', '.jpg'}:
                # Pattern match: 9965_item_boots.png matches 'boots'
                if clean_name in f.name.lower():
                    # Found! Now check if it's already in our scene images
                    img_id = get_or_load_image(context, f)
                    if img_id != -1:
                        return img_id
    
    return -1

def get_or_load_image(context, file_path):
    """Utility to load an image into RZMenu and return its ID."""
    rzm = context.scene.rzm
    filename = file_path.name
    
    # Check if already loaded by comparing filepath
    for rzm_img in rzm.images:
        if rzm_img.image_pointer and bpy.path.abspath(rzm_img.image_pointer.filepath) == str(file_path):
            return rzm_img.id
            
    # Load new
    try:
        bl_img = bpy.data.images.load(str(file_path), check_existing=True)
        bl_img.pack()
        
        new_rzm_img = rzm.images.add()
        # Find next free ID
        existing_ids = {i.id for i in rzm.images}
        new_id = 1
        while new_id in existing_ids: new_id += 1
        
        new_rzm_img.id = new_id
        new_rzm_img.display_name = filename
        new_rzm_img.source_type = 'CUSTOM'
        new_rzm_img.image_pointer = bl_img
        return new_id
    except:
        return -1

def instantiate_prefab(context, target_elem, source_data, prefab_type):
    """
    Applies template data to a scene element, respecting the RZMIgnoreMap.
    """
    ignores = RZMIgnoreMap.get('ANY', []) + RZMIgnoreMap.get(prefab_type, [])
    
    # Filter data
    filtered_data = {k: v for k, v in source_data.items() if k not in ignores}
    
    # Apply
    dict_to_rzm(filtered_data, target_elem)

def calculate_grid_layout(context, elements, settings):
    """
    Calculates and applies (x, y) positions for a list of elements based on grid settings.
    Settings: margin_x, margin_y, padding_x, padding_y, base_button_width, base_button_height
    """
    if not elements: return
    
    # Current simplistic approach: fit within Page Block width
    # For now, let's just do a row-based layout.
    # TODO: In the future, we can read the PAGE_BLOCK width to wrap rows.
    
    cur_x = settings.margin_x
    cur_y = settings.margin_y
    
    for i, elem in enumerate(elements):
        elem.position = (cur_x, cur_y)
        
        # Move right
        cur_x += settings.base_button_width + settings.padding_x
        
        # Simple wrap logic (e.g., 5 buttons per row)
        # In a real scenario, we'd check against canvas/parent width.
        if (i + 1) % 8 == 0:
            cur_x = settings.margin_x
            cur_y += settings.base_button_height + settings.padding_y

def format_toggle_label(name):
    """Converts @shoes_bottom to 'Shoes bottom'."""
    # Remove @ prefix
    res = name.replace("@", "")
    # Replace separators with spaces
    res = res.replace("_", " ").replace(".", " ")
    # Capitalize first letter
    if res:
        res = res[0].upper() + res[1:]
    return res

def apply_button_logic(context, btn_el, toggle_name, settings):
    """Handles renaming of text elements and assignment of icons based on UI settings."""
    rzm = context.scene.rzm
    
    # 1. Rename Text Children
    if settings.button_rename_text:
        formatted_label = format_toggle_label(toggle_name)
        # Search for TEXT elements that are DIRECT children of this button
        for child in rzm.elements:
            if child.parent_id == btn_el.id and child.elem_class == 'TEXT':
                child.text_id = formatted_label
                log_amc(context, f"    - Renamed text child to '{formatted_label}'")
    
    # 2. Assignment logic (ValueLink)
    # Clear existing template links and add the dynamic one
    btn_el.value_link.clear()
    link = btn_el.value_link.add()
    link.value_name = f"@{toggle_name}"
    
    # 3. Auto-Icon Find
    if settings.button_auto_icons:
        icon_id = find_matching_icon(context, toggle_name)
        if icon_id != -1:
            btn_el.image_id = icon_id
            log_amc(context, f"    - Auto-assigned icon ID: {icon_id}")

def execute_data_zones(context, manifest):
    """
    v4.1 Tiered Zones:
    - BLACK: Wipe #Shapes.
    - RED: Wipe Snippets/Vars.
    - YELLOW: Merge Fonts/Metadata. Template Priority.
    - GREEN: Merge Toggles. Project Priority.
    """
    rzm = context.scene.rzm
    
    # 1. [BLACK] - Shapes
    log_amc(context, "[Black Zone] Wiping Shapes.")
    rzm.shapes.clear()
    
    # 2. [RED] - Snippets & Variables
    log_amc(context, "[Red Zone] Replacing Snippets and Variables.")
    config_data = manifest.get('config', {})
    rzm.config.pre_snippet = config_data.get('pre_snippet', "")
    rzm.config.post_snippet = config_data.get('post_snippet', "")
    
    rzm.rzm_values.clear()
    for v_dict in manifest.get('variables', []):
        new_v = rzm.rzm_values.add()
        dict_to_rzm(v_dict, new_v)
        
    # 3. [YELLOW] - Metadata & Fonts
    meta_data = manifest.get('meta_data', {}) # [FIX] AttributeError: metadata -> meta_data
    if not meta_data: meta_data = manifest.get('metadata', {}) # Fallback for old templates
    if meta_data.get('keybind'): rzm.meta_data.menu_keybind = meta_data['keybind']
    
    # Fonts (Yellow Merge)
    font_data_list = manifest.get('fonts', [])
    if font_data_list:
        log_amc(context, "[Yellow Zone] Merging Fonts...")
        for f_dict in font_data_list:
            slot_idx = f_dict.get('slot_index', -1)
            if 0 <= slot_idx < len(rzm.fonts):
                dict_to_rzm(f_dict, rzm.fonts[slot_idx])
    
    # 4. [GREEN] - Toggles (Project Priority)
    log_amc(context, "[Green Zone] Merging Toggles.")
    template_toggles = manifest.get('toggles', [])
    for t_dict in template_toggles:
        tname = t_dict.get('toggle_name')
        if tname and not any(t.toggle_name == tname for t in rzm.toggle_definitions):
            new_t = rzm.toggle_definitions.add()
            dict_to_rzm(t_dict, new_t)

def reconstruct_branch(context, old_root_id, manifest, new_parent_id, global_id_map, prefab_type=None, current_prefix=""):
    """
    v4.1: Recursively clones branch and returns a local id_map to maintain reference integrity within clones.
    """
    rzm = context.scene.rzm
    elements_data = manifest.get('elements', [])
    source_data = next((e for e in elements_data if e.get('id') == old_root_id), None)
    if not source_data: return None, {}
    
    # Create element
    new_el = rzm.elements.add()
    existing_ids = {e.id for e in rzm.elements if e != new_el}
    new_id = 1
    while new_id in existing_ids: new_id += 1
    new_el.id = new_id
    new_el.parent_id = new_parent_id
    
    local_map = {old_root_id: new_id}
    
    # --- NAMING ---
    orig_name = source_data.get('element_name', "NewElement")
    is_support = source_data.get('is_helper') or source_data.get('is_preset')
    
    if prefab_type:
        new_el.element_name = prefab_type
        if prefab_type.startswith("BUTTON_"): current_prefix = prefab_type
    elif not is_support and current_prefix:
        new_el.element_name = f"{current_prefix}_{orig_name}"
    else:
        new_el.element_name = orig_name
    
    # --- APPLY DATA ---
    ignores = RZMIgnoreMap.get('ANY', [])
    if prefab_type:
        category = "BUTTONS" if prefab_type.startswith("BUTTON_") else prefab_type
        ignores += RZMIgnoreMap.get(category, [])
        log_amc(context, f"  > Building branch: {new_el.element_name}")
    
    filtered_data = {k: v for k, v in source_data.items() if k not in ignores}
    dict_to_rzm(filtered_data, new_el)
    
    # --- VISIBILITY FIX ---
    # Enforce hidden state strictly for support elements after data injection
    if is_support:
        new_el.qt_hide = True

    # --- RECURSION ---
    for child_data in elements_data:
        if child_data.get('parent_id') == old_root_id:
            _, sub_map = reconstruct_branch(context, child_data.get('id'), manifest, new_id, global_id_map, current_prefix=current_prefix)
            local_map.update(sub_map)
            
    return new_el, local_map

def finalize_references_v4(context, elements_and_maps, global_id_map, manifest):
    """
    Sophisticated remapping: For each element, prioritize its LOCAL branch map, then GLOBAL map.
    """
    rzm = context.scene.rzm
    log_amc(context, "Finalizing all ID references (v4.1)...")
    
    for element, local_map in elements_and_maps:
        # Get original template data for this element
        old_id = next((oid for oid, nid in local_map.items() if nid == element.id), None)
        if not old_id: continue # Should not happen
        
        old_data = next((e for e in manifest.get('elements', []) if e.get('id') == old_id), None)
        if not old_data: continue
        
        # Helper: Try Local, then Global
        def remap_id(oid):
            if oid in local_map: return local_map[oid]
            if oid in global_id_map: return global_id_map[oid]
            return -1

        # Remap preset_ids
        for i, p_ref in enumerate(element.preset_ids):
            if i < len(old_data.get('preset_ids', [])):
                new_id = remap_id(old_data['preset_ids'][i]['preset_id'])
                if new_id != -1: p_ref.preset_id = new_id
                
        # Remap underlayer_preset_ids
        for i, p_ref in enumerate(element.underlayer_preset_ids):
            if i < len(old_data.get('underlayer_preset_ids', [])):
                new_id = remap_id(old_data['underlayer_preset_ids'][i]['preset_id'])
                if new_id != -1: p_ref.preset_id = new_id
                
        # Remap helper_ids
        for i, h_ref in enumerate(element.helper_ids):
            if i < len(old_data.get('helper_ids', [])):
                new_id = remap_id(old_data['helper_ids'][i]['helper_id'])
                if new_id != -1: h_ref.helper_id = new_id

def generate_menu(context):
    """
    v4.1: Bugfixes (AttributeError, Fonts), Support Hiding, and Stable ID Remapping.
    """
    rzm = context.scene.rzm
    auto_menu = rzm.auto_menu
    log_amc(context, "--- Auto Menu Build Started (v4.1) ---", reset=True)
    
    if not auto_menu.last_loaded_rzmct or not os.path.exists(auto_menu.last_loaded_rzmct):
        log_amc(context, "ERROR: No template loaded.")
        return False
        
    from .rzmct_manager import unpack_template
    manifest = unpack_template(context, auto_menu.last_loaded_rzmct)
    if not manifest: return False
    
    # 1. Zones
    execute_data_zones(context, manifest)
    
    # 2. Context
    active_toggles = find_active_toggles(context)
    log_amc(context, f"[Green Zone] Project toggles: {len(active_toggles)}")
    
    # 3. Clear Elements
    rzm.elements.clear()
    context.scene.rzm_active_element_index = 0
    
    # 4. Identification
    prefabs = manifest.get('elements', [])
    main_root_data = next((p for p in prefabs if p.get('template_prefab') == 'MAIN_BLOCK'), None)
    page_root_data = next((p for p in prefabs if p.get('template_prefab') == 'PAGE_BLOCK'), None)
    button_root_data = next((p for p in prefabs if p.get('template_prefab') == 'BUTTONS'), None)
    
    if not main_root_data:
        log_amc(context, "ERROR: MAIN_BLOCK missing.")
        return False
        
    global_id_map = {} 
    elements_mapping_registry = [] # List of (new_element, local_id_map)
    
    # 5. Build Global Main/Page
    main_el, m_map = reconstruct_branch(context, main_root_data['id'], manifest, -1, global_id_map, 'MAIN_BLOCK')
    global_id_map.update(m_map)
    elements_mapping_registry.append((main_el, m_map))
    main_el.position = tuple(auto_menu.main_pos)
    main_el.size = tuple(auto_menu.main_size)
    
    page_el = None
    if page_root_data:
        page_el, p_map = reconstruct_branch(context, page_root_data['id'], manifest, main_el.id, global_id_map, 'PAGE_BLOCK')
        global_id_map.update(p_map)
        elements_mapping_registry.append((page_el, p_map))
        page_el.position = tuple(auto_menu.page_pos)
        page_el.size = tuple(auto_menu.page_size)
    
    # 6. Support Migration (Crucial to do BEFORE buttons for global references)
    log_amc(context, "Migrating support elements (Step 1)...")
    for elem_data in prefabs:
        old_id = elem_data.get('id')
        # If it wasn't part of Main/Page branches
        if old_id not in global_id_map:
            sup_el, s_map = reconstruct_branch(context, old_id, manifest, -1, global_id_map)
            global_id_map.update(s_map)
            elements_mapping_registry.append((sup_el, s_map))

    # 7. Build Dynamic Buttons
    generated_buttons = []
    if button_root_data and page_el:
        log_amc(context, f"Building {len(active_toggles)} clones of button prefab...")
        for toggle_name in active_toggles:
            btn_name = f"BUTTON_{toggle_name}"
            btn_el, b_map = reconstruct_branch(context, button_root_data['id'], manifest, page_el.id, global_id_map, btn_name)
            # Add to registry (so its internal elements keep their links)
            elements_mapping_registry.append((btn_el, b_map))
            # Also need to add children of this button clone to registry
            # Actually, reconstruct_branch for kids also adds to b_map.
            # We need to add every single NEW element in the clone to the registry.
            # Let's fix that.
            
            apply_button_logic(context, btn_el, toggle_name, auto_menu)
            generated_buttons.append(btn_el)
    
    # [PATCH] Register every element found in local maps to the registry for remapping
    # Since reconstruct_branch currently returns the ROOT only, we'll re-scan added elements.
    final_registry = []
    for _, l_map in elements_mapping_registry:
        for old_id, new_id in l_map.items():
            new_el = next((e for e in rzm.elements if e.id == new_id), None)
            if new_el: final_registry.append((new_el, l_map))

    # 11. Finalize references (Now with global/local priority)
    finalize_references_v4(context, final_registry, global_id_map, manifest)
    
    # 12. Layout
    calculate_grid_layout(context, generated_buttons, auto_menu)
    log_amc(context, "--- Auto Menu Build Finished Successfully (v4.1) ---")
    return True
