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

        # --- 4. MAIN BLOCKS (The Core Structure) ---
        block_box = main_box.box()
        row = block_box.row(align=True); row.label(text="Blocks & Components:", icon='NODETREE')
        row.operator("rzm.add_tw_block", text="", icon='ADD')
        row.operator("rzm.remove_tw_block", text="", icon='REMOVE')
        
        for b_idx, block in enumerate(rzm.tw_blocks):
            b_box = block_box.box()
            
            # Block Header
            row = b_box.row(align=True)
            row.label(text=f"BLOCK {b_idx}:", icon='MODIFIER_ON')
            row.prop(block, "name", text="")
            row.prop(block, "shader_type", text="")
            
            # Block Output Atlas
            row = b_box.row(align=True)
            row.prop(block, "resource_name", text="Output Atlas")
            
            # Backdrop Settings
            back_box = b_box.box()
            row = back_box.row(align=True)
            row.prop(block, "backdrop_enabled", text="Use Backdrop", icon='IMAGE_BACKGROUND')
            if block.backdrop_enabled:
                row.prop(block, "backdrop_resource_name", text="Res")
                row.prop(block, "backdrop_rect", text="Rect")

            # Components within Block
            comp_box = b_box.box()
            c_header = comp_box.row(align=True)
            c_header.label(text="COMPONENTS:", icon='GROUP')
            op = c_header.operator("rzm.add_tw_component", text="", icon='ADD'); op.block_index = b_idx
            op = c_header.operator("rzm.remove_tw_component", text="", icon='REMOVE'); op.block_index = b_idx
            
            for c_idx, comp in enumerate(block.components):
                c_item = comp_box.box()
                
                # Component Header
                row = c_item.row(align=True)
                row.prop(comp, "name", text=f"Comp {c_idx}")
                row.prop(comp, "mask_enabled", text="", icon='MOD_MASK')
                
                # Component Base Settings
                split = c_item.split(factor=0.4)
                split.prop(comp, "base_resource_name", text="Base Res")
                split.prop(comp, "base_rect", text="Source")
                
                c_item.prop(comp, "rect", text="Atlas Rect")
                
                # Slots
                slot_box = c_item.box()
                s_header = slot_box.row(align=True)
                s_header.label(text="SLOTS:", icon='NODE_SEL')
                op = s_header.operator("rzm.add_tw_slot", text="", icon='ADD')
                op.block_index = b_idx; op.comp_index = c_idx
                op = s_header.operator("rzm.remove_tw_slot", text="", icon='REMOVE')
                op.block_index = b_idx; op.comp_index = c_idx
                
                for s_idx, slot in enumerate(comp.slots):
                    s_item = slot_box.box()
                    
                    # Slot Header
                    row = s_item.row(align=True)
                    row.prop(slot, "active", text="")
                    row.prop(slot, "name", text=f"Slot {s_idx}")
                    row.prop(slot, "rect", text="")
                    
                    # Decal Layers (Compact)
                    layer_box = s_item.box()
                    l_row = layer_box.row(align=True)
                    l_row.label(text="Layers:", icon='STRANDS')
                    op = l_row.operator("rzm.add_tw_decal_layer", text="", icon='ADD')
                    op.block_index = b_idx; op.comp_index = c_idx; op.slot_index = s_idx
                    
                    for l_idx, layer in enumerate(slot.decal_layers):
                        l_row = layer_box.row(align=True)
                        l_row.prop(layer, "active", text="")
                        l_row.prop(layer, "name", text="")
                        l_row.prop(layer, "index", text="Idx")
                        l_row.prop(layer, "count", text="Total")
                        
                        op = l_row.operator("rzm.move_tw_decal_layer", text="", icon='TRIA_UP')
                        op.block_index = b_idx; op.comp_index = c_idx; op.slot_index = s_idx; op.index = l_idx; op.direction = 'UP'
                        op = l_row.operator("rzm.remove_tw_decal_layer", text="", icon='X')
                        op.block_index = b_idx; op.comp_index = c_idx; op.slot_index = s_idx; op.index = l_idx

                    # HSV & Masking
                    lower_grid = s_item.column(align=True)
                    
                    # Slot Transform (Pass 0 / Main)
                    lower_grid.label(text="Transform (Pass 0):")
                    t_row = lower_grid.row(align=True)
                    t_row.prop(slot, "rotation")
                    t_row.prop(slot, "dummy")
                    t_row.prop(slot, "mirror", text="", icon='MOD_MIRROR', toggle=True)
                    t_row.prop(slot, "flip", text="", icon='UV_SYNC_SELECT', toggle=True)

                    h_row = lower_grid.row(align=True)
                    h_row.prop(slot, "hsv_enabled", text="HSV", icon='COLOR')
                    if slot.hsv_enabled:
                        h_row.prop(slot, "hsv_link", text="")
                        h_row.prop(slot, "hsv_mask_enabled", text="", icon='MOD_MASK')

                    m_row = lower_grid.row(align=True)
                    m_row.prop(slot, "mask_enabled", text="Slot Mask", icon='MOD_MASK')
                    if slot.mask_enabled:
                        m_row.prop(slot, "mask_source", text="")
                        m_row.prop(slot, "pass0_use_mask", text="P0")
                        m_row.prop(slot, "pass1_use_mask", text="P1")

                    p_row = lower_grid.row(align=True)
                    p_row.prop(slot, "multi_pass_mode", text="Pass")

                    if slot.multi_pass_mode != 'NONE':
                        mp_box = lower_grid.box()
                        mp_box.label(text="Transform (Multi-pass):")
                        mp_box.prop(slot, "multi_pass_rect")
                        
                        mp_row = mp_box.row(align=True)
                        mp_row.prop(slot, "multi_pass_rotation", text="Rot")
                        mp_row.prop(slot, "multi_pass_dummy", text="Dmy")
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