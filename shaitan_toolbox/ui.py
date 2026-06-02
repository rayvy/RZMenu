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
    
    if active_tab == 'SETUP_SCRIPTS':
        draw_setup_scripts_ui(self, context, layout)
    elif active_tab == 'BASE_MESH':
        draw_base_mesh_setup_ui(self, context, layout)
    elif active_tab == 'UV_PACKER':
        draw_uv_packer_ui(self, context, layout)
    elif active_tab == 'COLOR_ATTR':
        draw_color_attr_ui(self, context, layout)

def draw_setup_scripts_ui(self, context, layout):
    scene = context.scene
    
    # ─── Smart Weight Transfer ───
    box_transfer = layout.box()
    box_transfer.label(text="Smart Weight Transfer", icon='MOD_VERTEX_WEIGHT')
    
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    active_obj = context.active_object
    
    col_info = box_transfer.column(align=True)
    if len(selected_meshes) == 2 and active_obj and active_obj.type == 'MESH':
        donor = [obj for obj in selected_meshes if obj != active_obj][0]
        col_info.label(text=f"Donor (Source): {donor.name}", icon='MESH_DATA')
        col_info.label(text=f"Target (Active): {active_obj.name}", icon='CHECKMARK')
        box_transfer.separator()
        row_btn = box_transfer.row()
        row_btn.scale_y = 1.3
        row_btn.operator("rzm_st.smart_transfer", text="Run Smart Weight Transfer", icon='FILE_REFRESH')
    else:
        col_info.label(text="Select exactly 2 meshes to enable Smart Transfer", icon='INFO')
        col_info.label(text="(Active object will be the destination/target)", icon='QUESTION')
        box_transfer.separator()
        row_btn = box_transfer.row()
        row_btn.enabled = False
        row_btn.scale_y = 1.3
        row_btn.operator("rzm_st.smart_transfer", text="Smart Weight Transfer (Requires 2 Selected Meshes)", icon='FILE_REFRESH')

    layout.separator()

    # ─── Mesh & Vertex Group Tools ───
    box_tools = layout.box()
    box_tools.label(text="Mesh & Vertex Group Tools", icon='TOOL_SETTINGS')
    
    col_tools = box_tools.column(align=True)
    col_tools.scale_y = 1.2
    
    col_tools.operator("rzm_st.mirror_cut", text="Mirror Cut X (Clear Left)", icon='MOD_MIRROR')
    col_tools.operator("rzm_st.vg_sym_rename_all", text="Symmetrize VG Names (Median)", icon='MOD_MIRROR')
    col_tools.operator("rzm_st.clean_duplicate_side_markers", text="Clean duplicate .L/.R markers", icon='SORTALPHA')
    col_tools.operator("rzm_weights.vg_name_transfer", text="VG Name Transfer (by index)", icon='FILE_REFRESH')
    col_tools.operator("rzm_st.generate_bones", text="Generate Missing Bones", icon='BONE_DATA')

    box_tools.separator()
    box_tools.label(text="Shape Key Cleanup:", icon='SHAPEKEY_DATA')
    row_shape = box_tools.row(align=True)
    row_shape.scale_y = 1.2
    row_shape.operator("rzm_st.clear_selected_shape_key_vertices", text="Clear Selected Verts (All)", icon='SHAPEKEY_DATA').active_only = False
    row_shape.operator("rzm_st.clear_selected_shape_key_vertices", text="Active Only", icon='DOT').active_only = True
    
    # Comparison Mode Selector
    box_tools.separator()
    box_tools.label(text="Compare Vertex Groups:", icon='VIEW_PAN')
    row = box_tools.row(align=True)
    row.prop(scene, "rzm_st_vg_compare_mode", expand=True)
    
    # Опасная зона
    box_tools.separator()
    col_destructive = box_tools.column(align=True)
    col_destructive.scale_y = 1.2
    col_destructive.operator("rzm_st.delete_all_vg", text="Delete All Vertex Groups", icon='TRASH')

def draw_base_mesh_setup_ui(self, context, layout):
    from .ui_harmonizer import draw_base_mesh_setup_ui as draw_harmonizer
    draw_harmonizer(self, context, layout)

def draw_uv_packer_ui(self, context, layout):
    scene = context.scene
    
    box = layout.box()
    box.label(text="TexCoord / UV Packer", icon='UV_DATA')
    row_std = box.row()
    row_std.scale_y = 1.2
    row_std.operator("rzm_st.standardize_uvmap", text="Standardize UVMap (Active/Selected)", icon='UV_DATA')
    
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
        box_item.prop(item, "packing_mode", text="Pack Mode")
        
        if item.packing_mode == 'SHIFT':
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
        row_ops.operator("rzm_st.process_active_layer", text="Write parameter", icon="DRIVER").mode = "PARAM"
        row_ops.operator("rzm_st.process_active_layer", text="Apply offset", icon="UV").mode = "APPLY"
        
        # Кнопки применения
        box.separator()
        row_apply = box.row()
        row_apply.scale_y = 1.6
        row_apply.operator("rzm_st.process_active_layer", text="WRITE AND APPLY (ACTIVE)", icon="CHECKMARK").mode = "BOTH"
    else:
        box.label(text="Add a layer to the list using the + button", icon='INFO')

def draw_color_attr_ui(self, context, layout):
    from .ops_color_attr import format_color_info, get_selected_average_color, is_color_attr_panel_active

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
        row = grid.row(align=True)
        # Swatch to see color
        row.prop(item, "color", text="")
        # Direct brush paint button
        op = row.operator("rzm_st.paint_preset_color", text="", icon='BRUSH_DATA')
        op.index = i
        
    layout.separator()
    
    # ─── 2. DIRECT COLOR PICKER & TARGET LAYER ───
    box_picker = layout.box()
    box_picker.label(text="Direct Color Picker:", icon='COLOR')
    
    # Color wheel + Alpha slider
    box_picker.prop(scene, "rzm_st_paint_color", text="")
    box_picker.label(text=f"Current: {format_color_info(scene.rzm_st_paint_color)}")
    
    row_target = box_picker.row(align=True)
    row_target.prop(scene, "rzm_st_paint_target", text="Target Layer")
    
    # Display selected average color
    selected_color = get_selected_average_color(context) if is_color_attr_panel_active(context) else None
    row_median = box_picker.row(align=True)
    row_median.label(text="Selected Average:")
    row_median.operator("rzm_st.sample_color", text="Copy", icon='EYEDROPPER')
    box_picker.label(text=f"Selected: {format_color_info(selected_color)}")
    
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
    col_guide = box_cheat.column(align=True)
    
    if game == 'GenshinImpact':
        col_guide.label(text="R: Metallic (1.0 - Metal, 0.0 - Non-metal)")
        col_guide.label(text="G: Ambient Occlusion / Shadow (1.0 - Light, 0.0 - Dark)")
        col_guide.label(text="B: Z-Index / Render Depth (0.0 - Default)")
        col_guide.label(text="A: Outline Thickness (0.4 - Std, 0.2 - Thin, 0.0 - None)")
    elif game == 'HonkaiStarRail':
        col_guide.label(text="R: Roughness / Metallic (Surface Details)")
        col_guide.label(text="G: Glossiness (Specular reflections)")
        col_guide.label(text="B: Z-Index (Render Depth)")
        col_guide.label(text="A: Outline Thickness (0.4 - Std, 0.2 - Thin, 0.0 - None)")
    elif game == 'ZenlessZoneZero':
        col_guide.label(text="R: Roughness Map")
        col_guide.label(text="G: Metallic Map")
        col_guide.label(text="B: God knows")
        col_guide.label(text="A: Outline Thickness (0.4 - Std, 0.2 - Thin, 0.0 - None)")
    else: # Default/EFMI/WWMI
        col_guide.label(text="R: Red Channel (Game Specific)")
        col_guide.label(text="G: Green Channel (Game Specific)")
        col_guide.label(text="B: Blue Channel (Game Specific)")
        col_guide.label(text="A: Alpha Channel (Outline / Depth)")
