import bpy

def draw_shaitan_toolbox(self, context, layout):
    """
    Основной метод отрисовки Shaitan Toolbox.
    Вызывается из main_ui.py.
    """
    scene = context.scene
    
    # ─── ТАБЫ ШАЙТАНА ───
    row = layout.row(align=True)
    row.prop(scene, "rzm_st_sub_tab", expand=True)
    
    layout.separator()
    
    active_tab = scene.rzm_st_sub_tab
    
    if active_tab == 'BASE_MESH':
        draw_base_mesh_setup_ui(self, context, layout)
    elif active_tab == 'UV_PACKER':
        draw_uv_packer_ui(self, context, layout)
    elif active_tab == 'COLOR_ATTR':
        draw_color_attr_ui(self, context, layout)

def draw_base_mesh_setup_ui(self, context, layout):
    scene = context.scene
    
    # Под-табы для Base Mesh Setup
    row = layout.row(align=True)
    row.prop(scene, "rzm_st_base_mesh_sub_tab", expand=True)
    
    layout.separator()
    
    sub_tab = scene.rzm_st_base_mesh_sub_tab
    
    if sub_tab == 'PRIMARY':
        box = layout.box()
        box.label(text="Armature & Project Setup (Phase 3 Placeholder)", icon='ARMATURE_DATA')
        
        col = box.column(align=True)
        col.prop(scene, "rzm_st_target_armature")
        col.prop(scene, "rzm_st_reference_mesh")
        
        box.separator()
        box.operator("rzm_st.body_rename_placeholder", text="Rename Components", icon='SORTALPHA')
        box.label(text="Полная логика ренеймера будет подключена в Фазе 3.", icon='INFO')
        
    elif sub_tab == 'SMALL_TOOLS':
        box = layout.box()
        box.label(text="Vertex Group Symmetry (Symmetrize VG)", icon='MOD_MIRROR')
        
        col = box.column(align=True)
        col.prop(scene, "rzm_st_symmetry_direction")
        col.prop(scene, "rzm_st_rename_associated_bones")
        
        box.separator()
        box.operator("rzm_st.symmetrize_vg_names", text="Symmetrize Active VG Name", icon='FILE_REFRESH')
        
        # Заглушки для других будущих инструментов
        box.separator()
        box.label(text="Другие инструменты (Фаза 3):", icon='TOOL_SETTINGS')
        col_coming = box.column(align=True)
        col_coming.active = False
        col_coming.label(text="- Project Index Map")
        col_coming.label(text="- Weight Reorder/Remap")
        col_coming.label(text="- Armature Clean")

def draw_uv_packer_ui(self, context, layout):
    scene = context.scene
    
    box = layout.box()
    box.label(text="TexCoord / UV Packer", icon='UV_DATA')
    
    # Список UV-слоев (UIList)
    row = box.row()
    row.template_list("RZM_ST_UL_List", "", scene, "rzm_st_texcoord_list", scene, "rzm_st_texcoord_list_index", rows=4)
    
    col_btn = row.column(align=True)
    col_btn.operator("rzm_st.texcoord_list_add", text="", icon='ADD')
    col_btn.operator("rzm_st.texcoord_list_remove", text="", icon='REMOVE')
    
    # Настройки выбранного элемента
    idx = scene.rzm_st_texcoord_list_index
    lst = scene.rzm_st_texcoord_list
    if 0 <= idx < len(lst):
        item = lst[idx]
        
        box_item = box.box()
        box_item.prop(item, "target_name", text="Target UV Name")
        
        row_grid = box_item.row(align=True)
        row_grid.prop(item, "grid_x", text="Grid X")
        row_grid.prop(item, "grid_y", text="Grid Y")
        
        # Квадратная сетка кнопок для выбора ячейки
        grid_box = box_item.box()
        grid_box.label(text="Position Selector (Top-Left is 0,0)", icon='GRID')
        
        for y in range(item.grid_y):
            row_cell = grid_box.row(align=True)
            for x in range(item.grid_x):
                is_selected = (item.pos_x == x and item.pos_y == y)
                op = row_cell.operator("rzm_st.set_grid_cell", text=f"{x},{y}", depress=is_selected)
                op.x = x
                op.y = y
                
        # Опциональные кнопки
        row_ops = box_item.row(align=True)
        row_ops.scale_y = 1.2
        row_ops.operator("rzm_st.process_active_layer", text="Записать параметр", icon="DRIVER").mode = "PARAM"
        row_ops.operator("rzm_st.process_active_layer", text="Применить сдвиг", icon="UV").mode = "APPLY"
        
        # Кнопки применения
        box.separator()
        row_apply = box.row()
        row_apply.scale_y = 1.6
        row_apply.operator("rzm_st.process_active_layer", text="ЗАПИСАТЬ И ПРИМЕНИТЬ (АКТИВНЫЙ)", icon="CHECKMARK").mode = "BOTH"
    else:
        box.label(text="Добавьте слой в список кнопкой +", icon='INFO')

def draw_color_attr_ui(self, context, layout):
    prefs_addon = context.preferences.addons.get('RZMenu')
    if not prefs_addon:
        layout.label(text="Error loading Addon Preferences", icon='ERROR')
        return
        
    prefs = prefs_addon.preferences
    scene = context.scene
    rzm = scene.rzm
    game = rzm.game.selection
    
    # ─── 1. GLOBAL PALETTE PRESETS (4x4 Grid) ───
    box_palette = layout.box()
    box_palette.label(text="Global Palette Presets (16 slots):", icon='NONE')
    
    grid = box_palette.grid_flow(columns=4, align=True)
    for i, item in enumerate(prefs.rzm_st_palette):
        col_slot = grid.column(align=True)
        col_slot.prop(item, "color", text="")
        
        row_btn = col_slot.row(align=True)
        # Small buttons for load/save
        load_op = row_btn.operator("rzm_st.load_preset", text="L")
        load_op.index = i
        save_op = row_btn.operator("rzm_st.save_preset", text="S")
        save_op.index = i
        
    layout.separator()
    
    # ─── 2. DIRECT COLOR PICKER & TARGET LAYER ───
    box_picker = layout.box()
    box_picker.label(text="Direct Color Picker:", icon='COLOR')
    
    # Color wheel + Alpha slider
    box_picker.prop(scene, "rzm_st_paint_color", text="")
    
    row_target = box_picker.row(align=True)
    row_target.prop(scene, "rzm_st_paint_target", text="Target Layer")
    
    # Display selected median color
    row_median = box_picker.row(align=True)
    row_median.prop(scene, "rzm_st_median_color", text="Selected Median")
    
    # Paint buttons
    layout.separator()
    col_ops = layout.column(align=True)
    col_ops.scale_y = 1.5
    col_ops.operator("rzm_st.paint_color", text="PAINT ACTIVE COLOR", icon='BRUSH_DATA')
    
    col_clear = layout.column(align=True)
    col_clear.operator("rzm_st.clear_color", text="Remove Target Layer", icon='TRASH')
    
    layout.separator()
    
    # ─── 3. GAME-SPECIFIC CHEAT SHEET ───
    box_cheat = layout.box()
    box_cheat.label(text=f"Cheat Sheet: {game}", icon='INFO')
    
    # Define channels config based on game
    if game == 'GenshinImpact':
        channels = [
            ('R', 'Metallic (1.0: Metal, 0.0: Non-metal)', [(1.0, "Metal"), (0.0, "Non-Metal")]),
            ('G', 'Ambient Occlusion / Light Shadow', [(1.0, "Light"), (0.0, "Shadow")]),
            ('B', 'Z-Index (Render Depth / Layers)', [(0.0, "Default")]),
            ('A', 'Outline Thickness', [(0.4, "Standard"), (0.2, "Thin"), (0.1, "Very Thin"), (0.0, "None")]),
        ]
    elif game == 'HonkaiStarRail':
        channels = [
            ('R', 'Roughness / Metallic (Surface Details)', [(1.0, "Max"), (0.0, "Min")]),
            ('G', 'Glossiness (Specular reflections)', [(1.0, "Glossy"), (0.0, "Matte")]),
            ('B', 'Z-Index (Render Depth)', [(0.0, "Default")]),
            ('A', 'Outline Thickness / Width', [(0.4, "Standard"), (0.2, "Thin"), (0.0, "None")]),
        ]
    elif game == 'ZenlessZoneZero':
        channels = [
            ('R', 'Roughness Map', [(1.0, "Max"), (0.0, "Min")]),
            ('G', 'Metallic Map', [(1.0, "Metal"), (0.0, "Non-Metal")]),
            ('B', 'Custom / Emission / Hair Shadow', [(0.0, "Default")]),
            ('A', 'Outline Thickness (Border)', [(0.4, "Standard"), (0.2, "Thin"), (0.0, "None")]),
        ]
    else: # Default/EFMI
        channels = [
            ('R', 'Red Channel (Game Specific)', [(1.0, "1.0"), (0.0, "0.0")]),
            ('G', 'Green Channel (Game Specific)', [(1.0, "1.0"), (0.0, "0.0")]),
            ('B', 'Blue Channel (Game Specific)', [(1.0, "1.0"), (0.0, "0.0")]),
            ('A', 'Alpha Channel (Outline / Depth)', [(1.0, "1.0"), (0.4, "0.4"), (0.0, "0.0")]),
        ]
        
    for char, desc, helpers in channels:
        col_chan = box_cheat.column(align=True)
        col_chan.label(text=f"{char}: {desc}")
        
        row_help = col_chan.row(align=True)
        for val, label in helpers:
            op = row_help.operator("rzm_st.set_channel_value", text=label)
            op.channel = char
            op.value = val
