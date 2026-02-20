#RZMenu/panels/ui_debug_panel.py
#AI Agent ignore this file, it's needed temporary solution that will be deleted later.
import bpy

# --- UI LISTS ---
class RZM_UL_Elements(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_val = 'FILE_FOLDER'
        if item.elem_class == 'ANCHOR': icon_val = 'PINNED'
        elif item.elem_class == 'BUTTON': icon_val = 'CHECKBOX_HLT'
        elif item.elem_class == 'SLIDER': icon_val = 'ARROW_LEFTRIGHT'
        elif item.elem_class == 'GRID_CONTAINER': icon_val = 'GRID'
        elif item.elem_class == 'TEXT': icon_val = 'TEXT'
        row = layout.row(align=True)
        row.label(text=f"ID: {item.id}", icon=icon_val)
        row.prop(item, "element_name", text="", emboss=False)

class RZM_UL_Images(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        col1 = row.column()
        sub_row = col1.row(align=True)
        if item.image_pointer and item.image_pointer.preview:
            sub_row.label(text="", icon_value=item.image_pointer.preview.icon_id)
        else:
            sub_row.label(text="", icon='IMAGE_DATA')
        sub_row.label(text=f"ID: {item.id}")
        col2 = row.column()
        col2.prop(item, "display_name", text="", emboss=False)
        sub_row2 = col2.row(align=True)
        icon_type = 'USER'
        if item.source_type == 'BASE': icon_type = 'SYSTEM'
        elif item.source_type == 'CAPTURED': icon_type = 'SCENE'
        sub_row2.label(text=item.source_type, icon=icon_type)
        if item.image_pointer:
            sub_row2.label(text=f"{item.image_pointer.size[0]}x{item.image_pointer.size[1]}px")
        else:
            sub_row2.label(text="<Missing>", icon='ERROR')
        col3 = row.column()
        if any(item.uv_size):
            col3.label(text=f"Atlas XY: {item.uv_coords[0]}, {item.uv_coords[1]}")
            col3.label(text=f"Atlas WH: {item.uv_size[0]}, {item.uv_size[1]}")
        else:
            col3.label(text="<Not Packed>")

class RZM_UL_Values(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "value_name", text="", emboss=False)
        row.prop(item, "value_type", text="")
        if item.value_type == 'INT':
            row.prop(item, "int_value", text="")
        elif item.value_type == 'FLOAT':
            row.prop(item, "float_value", text="")
        elif item.value_type == 'VECTOR':
            # Drawing 4 components of the vector
            row.prop(item, "vector_value", text="")

class RZM_UL_ProjectToggles(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "toggle_name", text="", emboss=False)
        row.prop(item, "toggle_length", text="Length")
        row.prop(item, "toggle_is_expanded", text="", icon='TRIA_DOWN' if item.toggle_is_expanded else 'TRIA_RIGHT', emboss=False)


# --- MENUS ---
class RZM_MT_ValueLinkMenu(bpy.types.Menu):
    bl_label = "Link to..."
    bl_idname = "RZM_MT_value_link_menu"

    def draw(self, context):
        layout = self.layout
        rzm = context.scene.rzm
        layout.label(text="Global Values", icon='IPO_SINE')
        if not rzm.rzm_values: layout.label(text="<None defined>", icon='INFO')
        for value in rzm.rzm_values:
            op = layout.operator("rzm.set_value_link", text=value.value_name); op.link_target = f"${value.value_name}"
        layout.separator()
        layout.label(text="Project Toggles", icon='CHECKBOX_HLT')
        if not rzm.toggle_definitions: layout.label(text="<None defined>", icon='INFO')
        for toggle_def in rzm.toggle_definitions:
            op = layout.operator("rzm.set_value_link", text=toggle_def.toggle_name); op.link_target = f"@{toggle_def.toggle_name}"
        layout.separator()
        layout.label(text="Shapes", icon='SHAPEKEY_DATA')
        if not rzm.shapes: layout.label(text="<None defined>", icon='INFO')
        for shape in rzm.shapes:
            op = layout.operator("rzm.set_value_link", text=shape.shape_name); op.link_target = f"#{shape.shape_name}"

class RZM_MT_TwFormatMenu(bpy.types.Menu):
    bl_label = "Select DXGI Format"
    bl_idname = "RZM_MT_tw_format_menu"

    def draw(self, context):
        layout = self.layout
        formats = ['DXGI_FORMAT_R8G8B8A8_TYPELESS', 'DXGI_FORMAT_R8G8B8A8_UNORM', 'DXGI_FORMAT_R8G8B8A8_UNORM_SRGB']
        for fmt in formats:
            op = layout.operator("rzm.set_tw_format", text=fmt)
            op.format_to_set = fmt

# --- Дебаг-панель ---
class VIEW3D_PT_RZConstructorDebugPanel(bpy.types.Panel):
    bl_label = "RZ Constructor"
    bl_idname = "VIEW3D_PT_rz_constructor_debug_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Construct Debug'

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_editor_mode == 'PRO' and context.scene.rzm_show_debug_panel

    def draw(self, context):
        layout = self.layout
        rzm = context.scene.rzm

        # --- SAFE DEPENDENCY CHECK ---
        # Проверяем, существует ли функция проверки зависимостей (добавляется в dependencies_panel)
        if hasattr(context.scene, "rzm_dependencies_met"):
            if not context.scene.rzm_dependencies_met(context):
                layout.label(text="Required libraries missing!", icon='ERROR')
                layout.label(text="Check 'RZ Dependencies' panel.", icon='INFO')
                # Если библиотеки нет, не крашимся, а просто выходим
                return 
        # -----------------------------

        self.draw_elements_editor(layout, rzm, context)
        active_idx = context.scene.rzm_active_element_index
        if 0 <= active_idx < len(rzm.elements):
            elem = rzm.elements[active_idx]
            self.draw_element_properties(layout, elem, context)
        layout.separator()
        box = layout.box()
        header_row = box.row(align=True)
        header_row.label(text="Project Image Library:")
        header_row.operator("rzm.update_atlas_layout", text="Update Atlas", icon='UV_SYNC_SELECT')
        header_row.operator("rzm.export_atlas", text="Export Atlas", icon='EXPORT')
        ops_row = box.row(align=True)
        ops_row.operator("rzm.add_image", text="Add Image", icon='ADD')
        ops_row.operator("rzm.remove_image", text="", icon='REMOVE')
        ops_row.operator("rzm.load_base_icons", text="Load Base Icons", icon='IMPORT')
        box.template_list("RZM_UL_Images", "", rzm, "images", context.scene, "rzm_active_image_index")
        layout.separator()
        box = layout.box()
        box.label(text="Project Global Values:")
        row = box.row(align=True)
        row.operator("rzm.add_value", text="Add", icon='ADD')
        row.operator("rzm.remove_value", text="", icon='REMOVE')
        box.template_list("RZM_UL_Values", "", rzm, "rzm_values", context.scene, "rzm_active_value_index")
        layout.separator()
        box = layout.box()
        box.label(text="Project Toggle Definitions:")
        row = box.row(align=True)
        row.operator("rzm.add_project_toggle", text="Add", icon='ADD')
        row.operator("rzm.remove_project_toggle", text="", icon='REMOVE')
        box.template_list("RZM_UL_ProjectToggles", "", rzm, "toggle_definitions", context.scene, "rzm_active_toggle_def_index")
        
        self.draw_global_mod_settings(layout, rzm)
        self.draw_addons_settings(layout, rzm)
        self.draw_tex_works_config(layout, rzm, context)
        self.draw_special_variables(layout, rzm)
        # self.draw_debug_tools(layout)

    def draw_elements_editor(self, layout, rzm, context):
        layout.separator()
        box = layout.box()
        box.label(text="UI Elements Editor:")
        row_add = box.row(align=True)
        row_add.prop(rzm, "element_to_add_class", text="")
        row_add.operator("rzm.add_element", text="Add", icon='ADD')
        row_ops = box.row(align=True)
        row_ops.operator("rzm.remove_element", text="Remove", icon='REMOVE')
        row_ops.operator("rzm.duplicate_element", text="Duplicate", icon='DUPLICATE')
        row_ops.operator("rzm.deselect_element", text="Deselect", icon='PANEL_CLOSE')
        row_list = layout.row()
        row_list.template_list("RZM_UL_Elements", "", rzm, "elements", context.scene, "rzm_active_element_index")
        col_move = row_list.column(align=True)
        col_move.operator("rzm.move_element_up", text="", icon='TRIA_UP')
        col_move.operator("rzm.move_element_down", text="", icon='TRIA_DOWN')

    def draw_element_properties(self, layout, elem, context):
        box = layout.box()
        box.label(text=f"Properties for: {elem.element_name} (ID: {elem.id})")
        
        self.draw_core_and_transform(box, elem)
        self.draw_content(box, elem, context)
        
        if elem.elem_class == 'ANCHOR':
            sub = box.box(); sub.label(text="Anchor Settings:"); sub.prop(elem, "is_main_window")
        elif elem.elem_class == 'GRID_CONTAINER':
            sub = box.box(); sub.label(text="Grid Settings:")
            col = sub.column(align=True); col.prop(elem, "grid_cell_size"); col.prop(elem, "grid_min_cells"); col.prop(elem, "grid_max_cells"); col.prop(elem, "grid_wrap_mode")

        if elem.elem_class in {'CONTAINER', 'GRID_CONTAINER', 'ANCHOR'}:
            self.draw_collection_ui(box, elem, "Advanced: FX Stack", "fx")
            self.draw_collection_ui(box, elem, "Advanced: FN Stack", "fn")

        self.draw_collection_ui(box, elem, "Advanced: Custom Properties", "properties")

    def draw_core_and_transform(self, layout, item):
        sub = layout.box()
        sub.label(text="Core & Transform:")
        col = sub.column(align=True)
        col.prop(item, "element_name"); col.prop(item, "parent_id"); col.prop(item, "priority"); col.prop(item, "tag"); col.prop(item, "elem_class")
        vis_box = sub.box()
        vis_box.prop(item, "visibility_mode", text="Visibility")
        if item.visibility_mode == 'CONDITIONAL':
            vis_box.prop(item, "visibility_condition", text="")
        row = sub.row(); row.prop(item, "position_is_formula", text="Position Formula")
        if item.position_is_formula:
            col = sub.column(align=True); col.prop(item, "position_formula_x", text="X"); col.prop(item, "position_formula_y", text="Y")
        else:
            label = "Position (Absolute)" if item.parent_id == -1 else "Position (Offset)"
            sub.prop(item, "position", text=label)
        row = sub.row(); row.prop(item, "size_is_formula", text="Size Formula")
        if item.size_is_formula:
            col = sub.column(align=True); col.prop(item, "size_formula_x", text="W"); col.prop(item, "size_formula_y", text="H")
        else:
            sub.prop(item, "size")
        sub.prop(item, "alignment")

    def draw_content(self, layout, item, context):
        sub = layout.box()
        sub.label(text="Content & Data Binding:")
        col = sub.column(align=True)
        col.prop(item, "image_mode", text="")
        if item.image_mode == 'SINGLE':
            col.prop(item, "image_id")
            if item.image_id == -9999:
                box = layout.box(); box.label(text="Image Missing!", icon='ERROR')
        else:
            list_box = col.box()
            row = list_box.row(align=True)
            row.label(text="Image List:")
            op_row = row.row(align=True)
            op_row.operator("rzm.add_conditional_image", text="", icon='ADD')
            op_row.operator("rzm.remove_conditional_image", text="", icon='REMOVE')
            for i, cond_img in enumerate(item.conditional_images):
                item_row = list_box.row(align=True)
                item_row.prop(cond_img, "image_id", text=f"[{i}] ID")
                if item.image_mode == 'CONDITIONAL_LIST':
                    item_row.prop(cond_img, "condition", text="")
        col.prop(item, "text_id")
        col.prop(item, "hover_text_id")
        if item.elem_class == 'TEXT':
            col.prop(item, "text_align")
        col.separator()
        col.prop(item, "tile_uv"); col.prop(item, "tile_size"); col.prop(item, "color")
        col.separator()
        
        link_box = col.box()
        row = link_box.row(align=True)
        row.label(text="Value Links:")
        row.menu(RZM_MT_ValueLinkMenu.bl_idname, text="Add from Menu", icon='ADD')
        
        for i, v_link in enumerate(item.value_link):
            link_row = link_box.row(align=True)
            link_row.prop(v_link, "value_name", text=f"[{i}]")
            
            if item.elem_class == 'SLIDER':
                sub_row = link_row.row(align=True)
                sub_row.prop(v_link, "value_min", text="Min")
                sub_row.prop(v_link, "value_max", text="Max")

            op = link_row.operator("rzm.remove_value_link", text="", icon='REMOVE')
            op.index_to_remove = i

        if item.elem_class == 'BUTTON':
            behavior_box = sub.box()
            behavior_box.label(text="Button Behavior:")
            behavior_box.prop(item, "disable_button_nums")
            behavior_box.prop(item, "disable_button_popup")

    def draw_collection_ui(self, layout, item, name, prop_name):
        box = layout.box()
        row = box.row()
        row.label(text=name)
        op_row = row.row(align=True)
        op = op_row.operator("rzm.list_action", text="", icon='ADD'); op.action = 'ADD'; op.collection = prop_name
        op = op_row.operator("rzm.list_action", text="", icon='REMOVE'); op.action = 'REMOVE'; op.collection = prop_name
        for sub_item in getattr(item, prop_name):
            if prop_name == 'fx': box.prop(sub_item, "value", text="")
            elif prop_name == 'fn': box.prop(sub_item, "function_name", text="")
            elif prop_name == 'properties':
                row_prop = box.row(align=True)
                row_prop.prop(sub_item, "key", text=""); row_prop.prop(sub_item, "value_type", text="")
                if sub_item.value_type == 'STRING': row_prop.prop(sub_item, "string_value", text="")
                elif sub_item.value_type == 'INT': row_prop.prop(sub_item, "int_value", text="")
                elif sub_item.value_type == 'FLOAT': row_prop.prop(sub_item, "float_value", text="")
    
    def draw_global_mod_settings(self, layout, rzm):
        layout.separator()
        box = layout.box()
        box.label(text="Global Mod Settings:")
        col = box.column(align=True)
        col.prop(rzm.config, "canvas_size")
        col.prop(rzm, "export_texture_slots")
        col.prop(rzm, "export_orfix_slots")
        col.prop(rzm, "export_toggle_swap_mode")

    def draw_addons_settings(self, layout, rzm):
        layout.separator()
        box = layout.box()
        box.label(text="Addons:")
        addons = rzm.addons
        col = box.column()
        row = col.row(align=True)
        row.prop(addons, "debugger_info"); row.prop(addons, "tex_works"); row.prop(addons, "vfx"); row.prop(addons, "facetexworkspreseted")
        
        if addons.debugger_info:
            box = col.box()
            box.label(text="Debug Variables (8)", icon='CONSOLE')
            grid = box.grid_flow(columns=2, align=True)
            for i in range(8):
                grid.prop(addons, f"debug_var_{i}", text=f"Var {i}")
        row = col.row(align=True)
        row.prop(addons, "shape_morph"); row.prop(addons, "shape_morph_anim")
        row = col.row(align=True)
        row.prop(addons, "dtoggle_compute"); row.prop(addons, "rtoggle_compute"); row.prop(addons, "frame_trace")
        box.separator()

    def draw_tex_works_config(self, layout, rzm, context):
        layout.separator()
        main_box = layout.box()
        main_box.label(text="TexWorks Core (New Format):", icon='TEXTURE')
        
        # --- 1. GLOBAL RESOURCES ---
        res_box = main_box.box()
        row = res_box.row(align=True); row.label(text="Resources:", icon='IMAGE_DATA')
        row.operator("rzm.add_tw_resource", text="", icon='ADD')
        row.operator("rzm.remove_tw_resource", text="", icon='REMOVE')
        
        for i, res in enumerate(rzm.tw_resources):
            r_box = res_box.box()
            row = r_box.row(align=True)
            row.prop(res, "name", text=f"[{i}]")
            row.prop(res, "type", text="")
            if res.type == 'ON_DISK':
                row.prop(res, "path", text="")
            
            row = r_box.row(align=True)
            row.prop(res, "resolution", text="Res")
            row.prop(res, "format", text="")

        # --- 2. GLOBAL OVERRIDES ---
        over_box = main_box.box()
        row = over_box.row(align=True); row.label(text="Overrides (3DMigoto):", icon='BLANK1')
        row.operator("rzm.add_tw_override", text="", icon='ADD')
        row.operator("rzm.remove_tw_override", text="", icon='REMOVE')
        
        for i, over in enumerate(rzm.tw_overrides):
            row = over_box.row(align=True)
            row.prop(over, "name", text=f"[{i}]")
            row.prop(over, "hash", text="Hash")
            row.prop(over, "resource_name", text="Res")

        # --- 3. GLOBAL MATERIALS ---
        mat_box = main_box.box()
        row = mat_box.row(align=True); row.label(text="Materials (Behavior):", icon='MATERIAL')
        row.operator("rzm.add_tw_material", text="", icon='ADD')
        row.operator("rzm.remove_tw_material", text="", icon='REMOVE')
        
        for i, mat in enumerate(rzm.tw_materials):
            m_box = mat_box.box()
            row = m_box.row(align=True)
            row.prop(mat, "name", text=f"[{i}]")
            row.prop(mat, "diffuse_blend_mode", text="")
            
            m_box.prop(mat, "parameters", text="Params (x46)")

        # --- 4. MAIN BLOCKS ---
        block_box = main_box.box()
        row = block_box.row(align=True)
        row.label(text="Blocks:", icon='NODETREE')
        row.operator("rzm.add_tw_block", text="", icon='ADD')
        row.operator("rzm.remove_tw_block", text="", icon='REMOVE')
        
        # Вкладки Блоков (Если блоков много)
        if rzm.tw_blocks:
            tabs = block_box.row(align=True)
            for i, block in enumerate(rzm.tw_blocks):
                is_active = (i == rzm.active_tw_block_index)
                btn_text = block.name if block.name else f"B{i}"
                # Оператор переключения активного блока
                op = tabs.operator("rzm.set_active_block", text=btn_text, depress=is_active)
                op.index = i

            # Отображаем только АКТИВНЫЙ блок
            b_idx = rzm.active_tw_block_index
            if 0 <= b_idx < len(rzm.tw_blocks):
                block = rzm.tw_blocks[b_idx]
                b_box = block_box.box()
                
                # Block Header
                row = b_box.row(align=True)
                row.prop(block, "name", text="Block Name")
                row.prop(block, "shader_type", text="")
                
                # Block Output Atlas
                row = b_box.row(align=True)
                row.prop(block, "resource_name", text="Output Atlas")
                
                # --- BACKDROP ---
                back_box = b_box.box()
                row = back_box.row(align=True)
                row.prop(block, "backdrop_enabled", text="Use Backdrop", icon='IMAGE_BACKGROUND')
                if block.backdrop_enabled:
                    row.prop(block, "backdrop_resource_name", text="Res")
                    row.prop(block, "backdrop_rect", text="Rect")

                # --- COMPONENTS (Вкладки) ---
                comp_section = b_box.box()
                c_header = comp_section.row(align=True)
                c_header.label(text="Components:", icon='GROUP')
                op = c_header.operator("rzm.add_tw_component", text="", icon='ADD'); op.block_index = b_idx
                
                if block.components:
                    c_tabs = comp_section.row(align=True)
                    for i, comp in enumerate(block.components):
                        is_active = (i == block.active_component_index)
                        c_btn_text = comp.name if comp.name else f"C{i}"
                        op = c_tabs.operator("rzm.set_active_component", text=c_btn_text, depress=is_active)
                        op.block_index = b_idx
                        op.index = i
                    
                    # Содержимое активного компонента
                    c_idx = block.active_component_index
                    if 0 <= c_idx < len(block.components):
                        comp = block.components[c_idx]
                        c_item = comp_section.box()
                        
                        # Настройки компонента
                        row = c_item.row(align=True)
                        row.prop(comp, "name", text="Name")
                        row.prop(comp, "mask_enabled", text="", icon='MOD_MASK')
                        op_rem = row.operator("rzm.remove_tw_component", text="", icon='X')
                        op_rem.block_index = b_idx
                        op_rem.index = c_idx
                        
                        split = c_item.split(factor=0.4)
                        split.prop(comp, "base_resource_name", text="Base Res")
                        split.prop(comp, "base_rect", text="Source")
                        c_item.prop(comp, "rect", text="Atlas Rect")

                        # --- SLOTS (Вкладки) ---
                        slot_section = c_item.box()
                        s_header = slot_section.row(align=True)
                        s_header.label(text="Slots:", icon='NODE_SEL')
                        op = s_header.operator("rzm.add_tw_slot", text="", icon='ADD')
                        op.block_index = b_idx; op.comp_index = c_idx

                        if comp.slots:
                            s_tabs = slot_section.row(align=True)
                            for i, slot in enumerate(comp.slots):
                                is_active = (i == comp.active_slot_index)
                                s_btn_text = slot.name if slot.name else f"S{i}"
                                op = s_tabs.operator("rzm.set_active_slot", text=s_btn_text, depress=is_active)
                                op.block_index = b_idx; op.comp_index = c_idx; op.index = i

                            # Содержимое активного слота
                            s_idx = comp.active_slot_index
                            if 0 <= s_idx < len(comp.slots):
                                slot = comp.slots[s_idx]
                                s_item = slot_section.box()
                                
                                # Настройки слота
                                row = s_item.row(align=True)
                                row.prop(slot, "active", text="")
                                row.prop(slot, "name", text="Slot Name")
                                row.operator("rzm.remove_tw_slot", text="", icon='X').block_index = b_idx; op.comp_index = c_idx; op.index = s_idx
                                
                                # --- UV CALCULATOR (Auto-Config) ---
                                calc_box = s_item.box()
                                calc_box.label(text="UV Calculator (Auto-Config):", icon='UV')
                                
                                # Resolution Controls
                                res_row = calc_box.row(align=True)
                                res_row.prop(slot, "calc_res_x", text="X")
                                res_row.prop(slot, "calc_res_y", text="Y")
                                
                                # Presets
                                pre_row = calc_box.row(align=True)
                                pre2 = pre_row.operator("rzm.set_slot_calc_res", text="Set 2048")
                                pre2.block_index = b_idx; pre2.comp_index = c_idx; pre2.slot_index = s_idx; pre2.res = 2048
                                
                                pre4 = pre_row.operator("rzm.set_slot_calc_res", text="Set 4096")
                                pre4.block_index = b_idx; pre4.comp_index = c_idx; pre4.slot_index = s_idx; pre4.res = 4096
                                
                                # Padding
                                calc_box.prop(slot, "calc_padding", text="Padding (Px)")
                                
                                # Calc Buttons
                                op_row = calc_box.row(align=True)
                                op0 = op_row.operator("rzm.calc_slot_config", text="Calculate Pass 0", icon='PLAY')
                                op0.block_index = b_idx; op0.comp_index = c_idx; op0.slot_index = s_idx; op0.target_pass = 0
                                
                                op1 = op_row.operator("rzm.calc_slot_config", text="Calculate Pass 1", icon='PLAY')
                                op1.block_index = b_idx; op1.comp_index = c_idx; op1.slot_index = s_idx; op1.target_pass = 1

                                # --- TRANSFORM GROUP (PASS 0) ---
                                t_box = s_item.box()
                                t_box.label(text="Transform (Pass 0 / Main):", icon='NODE_SOCKET_MATRIX')
                                col = t_box.column(align=True)
                                col.prop(slot, "rect", text="Atlas Rect")
                                
                                row = col.row(align=True)
                                row.prop(slot, "rotation")
                                row.prop(slot, "mirror", text="", icon='MOD_MIRROR', toggle=True)
                                row.prop(slot, "flip", text="", icon='UV_SYNC_SELECT', toggle=True)

                                # --- WARPING & LATTICE ---
                                w_box = s_item.box()
                                w_box.label(text="Warping & Lattice (3x3):", icon='GRID')
                                
                                # Pass 0 Warp
                                p0_w = w_box.box()
                                row = p0_w.row(align=True)
                                row.prop(slot, "warp_p0_enabled", text="Pass 0 Warp")
                                row.prop(slot, "warp_p0_debug", text="Debug", icon='CONSOLE')
                                if slot.warp_p0_enabled:
                                    grid = p0_w.grid_flow(columns=3, even_columns=True, even_rows=False, align=True)
                                    for i in range(9):
                                        col = grid.column(align=True)
                                        col.prop(slot, "warp_p0_grid", index=i*2, text="X")
                                        col.prop(slot, "warp_p0_grid", index=i*2+1, text="Y")
                                
                                # Pass 1 Warp (only if multi-pass enabled)
                                if slot.multi_pass_mode != 'NONE':
                                    p1_w = w_box.box()
                                    row = p1_w.row(align=True)
                                    row.prop(slot, "warp_p1_enabled", text="Pass 1 Warp")
                                    row.prop(slot, "warp_p1_debug", text="Debug", icon='CONSOLE')
                                    if slot.warp_p1_enabled:
                                        grid = p1_w.grid_flow(columns=3, even_columns=True, even_rows=False, align=True)
                                        for i in range(9):
                                            col = grid.column(align=True)
                                            col.prop(slot, "warp_p1_grid", index=i*2, text="X")
                                            col.prop(slot, "warp_p1_grid", index=i*2+1, text="Y")

                                # --- LAYERS (Вкладки) ---
                                layer_box = s_item.box()
                                l_header = layer_box.row(align=True)
                                l_header.label(text="Layers:", icon='STRANDS')
                                op = l_header.operator("rzm.add_tw_decal_layer", text="", icon='ADD')
                                op.block_index = b_idx; op.comp_index = c_idx; op.slot_index = s_idx
                                
                                if slot.decal_layers:
                                    l_tabs = layer_box.row(align=True)
                                    for i, layer in enumerate(slot.decal_layers):
                                        is_active = (i == slot.active_layer_index)
                                        l_btn_text = layer.name if layer.name else f"L{i}"
                                        op = l_tabs.operator("rzm.set_tw_active_layer", text=l_btn_text, depress=is_active)
                                        op.block_index = b_idx; op.comp_index = c_idx; op.slot_index = s_idx; op.index = i

                                    # Информация активного слоя
                                    l_idx = slot.active_layer_index
                                    if 0 <= l_idx < len(slot.decal_layers):
                                        active_layer = slot.decal_layers[l_idx]
                                        l_info = layer_box.box()
                                        
                                        row = l_info.row(align=True)
                                        row.prop(active_layer, "active", text="")
                                        row.prop(active_layer, "name", text="")
                                        
                                        row = l_info.row(align=True)
                                        row.prop(active_layer, "index", text="Idx")
                                        row.prop(active_layer, "count", text="Total")
                                        
                                        # Управление слоем (Перемещение/Удаление)
                                        ops = row.row(align=True)
                                        op_up = ops.operator("rzm.move_tw_item", icon='TRIA_UP', text="")
                                        op_up.collection_name = 'decal_layers'
                                        op_up.block_index = b_idx; op_up.comp_index = c_idx; op_up.slot_index = s_idx; op_up.index = l_idx; op_up.direction = 'UP'
                                        
                                        op_down = ops.operator("rzm.move_tw_item", icon='TRIA_DOWN', text="")
                                        op_down.collection_name = 'decal_layers'
                                        op_down.block_index = b_idx; op_down.comp_index = c_idx; op_down.slot_index = s_idx; op_down.index = l_idx; op_down.direction = 'DOWN'
                                        
                                        op_rem = ops.operator("rzm.remove_tw_decal_layer", icon='X', text="")
                                        op_rem.block_index = b_idx; op_rem.comp_index = c_idx; op_rem.slot_index = s_idx; op_rem.index = l_idx

                                # --- FX & MASKING ---
                                fx_box = s_item.box()
                                fx_box.label(text="Effects & Masking:", icon='MODIFIER')
                                
                                h_row = fx_box.row(align=True)
                                h_row.prop(slot, "hsv_enabled", text="HSV", icon='COLOR')
                                if slot.hsv_enabled:
                                    h_row.prop(slot, "hsv_link", text="")
                                    h_row.prop(slot, "hsv_mask_enabled", text="", icon='MOD_MASK')

                                m_box = fx_box.box()
                                m_row = m_box.row(align=True)
                                m_row.prop(slot, "mask_enabled", text="Slot Mask", icon='MOD_MASK')
                                if slot.mask_enabled:
                                    m_row.prop(slot, "mask_source", text="")
                                    m_row.prop(slot, "pass0_use_mask", text="P0")
                                    m_row.prop(slot, "pass1_use_mask", text="P1")

                                # --- MULTI-PASS ---
                                mp_box = s_item.box()
                                mp_box.prop(slot, "multi_pass_mode", text="Pass Mode")
                                if slot.multi_pass_mode != 'NONE':
                                    mp_box.label(text="Transform (Multi-pass):")
                                    mp_box.prop(slot, "multi_pass_rect", text="Atlas Rect")
                                    
                                    mp_row = mp_box.row(align=True)
                                    mp_row.prop(slot, "multi_pass_rotation", text="Rot")
                                    mp_row.prop(slot, "multi_pass_mirror", text="", icon='MOD_MIRROR', toggle=True)
                                    mp_row.prop(slot, "multi_pass_flip", text="", icon='UV_SYNC_SELECT', toggle=True)

    def draw_special_variables(self, layout, rzm):
        layout.separator()
        main_box = layout.box(); main_box.label(text="Special Variables:")
        cond_box = main_box.box(); row = cond_box.row(align=True); row.label(text="Conditions:")
        op_row = row.row(align=True); op_row.operator("rzm.add_condition", text="", icon='ADD'); op_row.operator("rzm.remove_condition", text="", icon='REMOVE')
        for item in rzm.conditions:
            row = cond_box.row(align=True); row.prop(item, "condition_name", text=""); row.prop(item, "condition_hash", text="Hash")
            
        shape_box = main_box.box()
        row = shape_box.row(align=True); row.label(text="Shapes:")
        op_row = row.row(align=True); op_row.operator("rzm.add_shape", text="", icon='ADD'); op_row.operator("rzm.remove_shape", text="", icon='REMOVE')
        
        for shape_idx, item in enumerate(rzm.shapes):
            s_box = shape_box.box()
            row = s_box.row(align=True); row.prop(item, "shape_name", text=""); row.prop(item, "shape_type", text="")
            
            if item.shape_type == 'Anim':
                s_box.prop(item, "anim_condition", text="Condition")

            keys_box = s_box.box()
            keys_row = keys_box.row(align=True)
            keys_row.label(text="Shape Keys:")
            
            op_row = keys_row.row(align=True)
            op_row.alignment = 'RIGHT'
            op_add = op_row.operator("rzm.add_shape_key", text="", icon='ADD'); op_add.shape_index = shape_idx
            op_rem = op_row.operator("rzm.remove_shape_key", text="", icon='REMOVE'); op_rem.shape_index = shape_idx

            for key_item in item.shape_keys:
                key_box = keys_box.box()
                key_box.prop(key_item, "key_name", text="Keyframe")
                key_box.prop(key_item, "mode")
                
                if key_item.mode == 'ADVANCED':
                    adv_col = key_box.column(align=True)
                    adv_col.label(text="Advanced Settings:")
                    range_row = adv_col.row(align=True)
                    range_row.prop(key_item, "input_range_min", text="Input Min")
                    range_row.prop(key_item, "input_range_max", text="Input Max")
                    adv_col.prop(key_item, "multiplier")

                if item.shape_type == 'Anim':
                    anim_box = key_box.box()
                    anim_box.label(text="Animation Settings:")
                    anim_box.prop(key_item, "anim_type_index", text="Type Index")
                    row = anim_box.row(align=True)
                    row.prop(key_item, "anim_start_frame", text="Start (0-1)")
                    row.prop(key_item, "anim_end_frame", text="End (0-1)")

    # def draw_debug_tools(self, layout):
    #     layout.separator()
    #     box = layout.box()
    #     box.label(text="Debug Tools:")
    #     row = box.row(align=True)
    #     row.operator("rzm.launch_viewer", text="Viewer")
    #     row.operator("rzm.launch_inspector", text="Inspector")

classes_to_register = [
    RZM_UL_Elements, RZM_UL_Images, RZM_UL_Values, RZM_UL_ProjectToggles,
    RZM_MT_ValueLinkMenu, RZM_MT_TwFormatMenu,
    VIEW3D_PT_RZConstructorDebugPanel
]
def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)