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
    prefs = context.preferences.addons.get('RZMenu')
    if not prefs:
        layout.label(text="Error loading Addon Preferences", icon='ERROR')
        return
        
    prefs = prefs.preferences
    
    box = layout.box()
    box.label(text="Color Attribute Paint (Phase 2 Placeholder)", icon='COLOR')
    
    # Отобразим список пресетов палитры для теста
    box.label(text="Global Palette (Addon level):", icon='GROUP')
    
    # 4 дефолтных пресета
    grid = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
    for item in prefs.rzm_st_palette[:4]:
        row = grid.row(align=True)
        # Маленький цветной квадрат
        row.prop(item, "color", text="", emboss=False)
        op = row.operator("rzm_st.apply_color_preset", text=item.name)
        op.preset_name = item.name
        
    box.separator()
    box.label(text="Полная логика палитры (до 16 слотов), direct picker,", icon='INFO')
    box.label(text="определение выделенных вершин в Edit Mode и шпаргалка", icon='INFO')
    box.label(text="будут реализованы в Фазе 2.", icon='INFO')
