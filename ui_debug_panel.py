# rz_gui_constructor/ui_debug_panel.py
import bpy
from .dependencies import check_dependencies

# --- UI LISTS ---
class RZM_UL_Elements(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_val = 'FILE_FOLDER'
        if item.elem_class == 'ANCHOR': icon_val = 'PINNED'
        elif item.elem_class == 'BUTTON': icon_val = 'CHECKBOX_HLT'
        elif item.elem_class == 'SLIDER': icon_val = 'ARROW_LEFTRIGHT'
        elif item.elem_class == 'GRID_CONTAINER': icon_val = 'GRID'
        row = layout.row(align=True)
        row.label(text=f"ID: {item.id}", icon=icon_val)
        row.prop(item, "element_name", text="", emboss=False)

class RZM_UL_Images(bpy.types.UIList):
    """UIList для отображения изображений проекта."""
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
    """UIList для отображения глобальных переменных (Values)."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "value_name", text="", emboss=False)
        row.prop(item, "value_type", text="")
        if item.value_type == 'INT':
            row.prop(item, "int_value", text="")
        elif item.value_type == 'FLOAT':
            row.prop(item, "float_value", text="")

class RZM_UL_ProjectToggles(bpy.types.UIList):
    """UIList для отображения глобальных тогглов в дебаг-панели."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "toggle_name", text="", emboss=False)
        row.prop(item, "toggle_length", text="Length")
        row.prop(item, "toggle_is_expanded", text="", icon='TRIA_DOWN' if item.toggle_is_expanded else 'TRIA_RIGHT', emboss=False)

class RZM_MT_ValueLinkMenu(bpy.types.Menu):
    bl_label = "Link to..."
    bl_idname = "RZM_MT_value_link_menu"

    def draw(self, context):
        layout = self.layout
        rzm = context.scene.rzm
        layout.label(text="Global Values", icon='IPO_SINE')
        if not rzm.rzm_values:
            layout.label(text="<None defined>", icon='INFO')
        for value in rzm.rzm_values:
            op = layout.operator("rzm.set_value_link", text=value.value_name)
            op.link_target = f"${value.value_name}"
        layout.separator()
        layout.label(text="Project Toggles", icon='CHECKBOX_HLT')
        if not rzm.toggle_definitions:
            layout.label(text="<None defined>", icon='INFO')
        for toggle_def in rzm.toggle_definitions:
            op = layout.operator("rzm.set_value_link", text=toggle_def.toggle_name)
            op.link_target = f"@{toggle_def.toggle_name}"

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
        if not check_dependencies():
            layout.label(text="PySide6 не найден!", icon='ERROR'); return

        rzm = context.scene.rzm

        self.draw_elements_editor(layout, rzm, context)
        
        active_idx = context.scene.rzm_active_element_index
        if active_idx >= 0 and active_idx < len(rzm.elements):
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
        
        box.template_list(
            "RZM_UL_Images", "", rzm, "images",
            context.scene, "rzm_active_image_index"
        )
        layout.separator()
        box = layout.box()
        box.label(text="Project Global Values:")
        row = box.row(align=True)
        row.operator("rzm.add_value", text="Add", icon='ADD')
        row.operator("rzm.remove_value", text="", icon='REMOVE')
        box.template_list(
            "RZM_UL_Values", "", rzm, "rzm_values",
            context.scene, "rzm_active_value_index"
        )
        
        layout.separator()
        box = layout.box()
        box.label(text="Project Toggle Definitions:")
        row = box.row(align=True)
        row.operator("rzm.add_project_toggle", text="Add", icon='ADD')
        row.operator("rzm.remove_project_toggle", text="", icon='REMOVE')
        box.template_list("RZM_UL_ProjectToggles", "", rzm, "toggle_definitions", context.scene, "rzm_active_toggle_def_index")
        
        self.draw_global_mod_settings(layout, rzm)
        self.draw_addons_settings(layout, rzm)
        self.draw_tex_works_config(layout, rzm) 
        self.draw_special_variables(layout, rzm)
        self.draw_debug_tools(layout)

    # --- HELPER-ФУНКЦИИ ДЛЯ ЧИСТОТЫ КОДА ---
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

    def draw_content(self, layout, item, context):
        sub = layout.box()
        sub.label(text="Content & Data Binding:")
        col = sub.column(align=True)
        
        col.prop(item, "image_id")
        if item.image_id == -9999:
            box = layout.box()
            box.label(text="Image Missing!", icon='ERROR')
        col.prop(item, "text_id")
        col.prop(item, "hover_text_id")
        col.separator()
        col.prop(item, "tile_uv")
        col.prop(item, "tile_size")
        col.prop(item, "color")
        col.separator()
        row = col.row(align=True)
        row.prop(item, "value_link", text="Link")
        row.menu(RZM_MT_ValueLinkMenu.bl_idname, text="", icon='DOWNARROW_HLT')
        if item.value_link.startswith('$'):
            col.prop(item, "value_link_max", text="Max Value")

    def draw_collection_ui(self, layout, item, name, prop_name):
        box = layout.box()
        row = box.row()
        row.label(text=name)
        op_row = row.row(align=True)
        op = op_row.operator("rzm.list_action", text="", icon='ADD'); op.action = 'ADD'; op.collection = prop_name
        op = op_row.operator("rzm.list_action", text="", icon='REMOVE'); op.action = 'REMOVE'; op.collection = prop_name
        for sub_item in getattr(item, prop_name):
            if prop_name == 'fx':
                box.prop(sub_item, "value", text="")
            elif prop_name == 'fn':
                box.prop(sub_item, "function_name", text="")
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
        row.prop(addons, "debugger_info")
        row.prop(addons, "tex_works") 
        row.prop(addons, "vfx")
        
        row = col.row(align=True)
        row.prop(addons, "shape_morph")
        row.prop(addons, "shape_morph_anim")
        row.prop(addons, "shape_morph_jiggle")
        
        row = col.row(align=True)
        row.prop(addons, "dtoggle_compute")
        row.prop(addons, "rtoggle_compute")
        
        box.separator()
        
        row = box.row(align=True)
        row.prop(addons, "sandevistan_gi")
        row.prop(addons, "sandevistan_zzz")
        row.prop(addons, "sandevistan_hsr")
        row.prop(addons, "sandevistan_wuwa")
        
        box.separator()

    def draw_tex_works_config(self, layout, rzm):
        if not rzm.addons.tex_works:
            return
            
        layout.separator()
        main_box = layout.box()
        main_box.label(text="TexWorks Configuration:")
        
        addons = rzm.addons
        
        config_box = main_box.box()
        row = config_box.row(align=True)
        row.label(text="Global Texture Configurations:")
        op_row = row.row(align=True)
        op_row.operator("rzm.add_tw_config", text="", icon='ADD') 
        op_row.operator("rzm.remove_tw_config", text="", icon='REMOVE')

        for item in addons.tw_texture_configs:
            row = config_box.row(align=True)
            row.prop(item, "tw_config_name", text="")
            row.prop(item, "tw_color_space", text="")
            
            sub_box = config_box.box()
            sub_box.label(text=f"Atlas Settings for '{item.tw_config_name}':")
            atlas_settings = item.tw_atlas_settings
            col = sub_box.column(align=True)
            row_size = col.row(align=True)
            row_size.prop(atlas_settings, "tw_width", text="W")
            row_size.prop(atlas_settings, "tw_height", text="H")
            col.prop(atlas_settings, "tw_format", text="Format")
            row_params = col.row(align=True)
            row_params.prop(atlas_settings, "tw_array", text="Array")
            row_params.prop(atlas_settings, "tw_msaa", text="MSAA")
            row_params.prop(atlas_settings, "tw_mips", text="Mips")

        textures_box = main_box.box()
        row = textures_box.row(align=True)
        row.label(text="Atlas Textures:")
        op_row = row.row(align=True)
        op_row.operator("rzm.add_tw_texture", text="", icon='ADD')
        op_row.operator("rzm.remove_tw_texture", text="", icon='REMOVE')

        for item in addons.tw_textures:
            item_box = textures_box.box()
            row = item_box.row()
            
            icon = 'TRIA_DOWN' if item.tw_is_expanded else 'TRIA_RIGHT'
            row.prop(item, "tw_is_expanded", text="", icon=icon, emboss=False)
            row.prop(item, "tw_name", text="")
            
            if item.tw_is_expanded:
                main_col = item_box.column(align=True)
                main_col.prop(item, "tw_position", text="Position (X,Y)")
                main_col.prop(item, "tw_size", text="Size (W,H)")
                
                main_col.separator()
                
                decal_box = main_col.box()
                decal_box.label(text="Decals:")
                decal_box.prop(item, "tw_use_decal_tattoo")
                decal_box.prop(item, "tw_use_decal_cum")
                
                hsv_box = main_col.box()
                hsv_box.prop(item, "tw_use_hsv")
                if item.tw_use_hsv:
                    hsv_box.prop(item, "tw_hsv_mode", text="Mode")
                    hsv_box.prop(item, "tw_hsv_value_link", text="Link")
                    
                morph_box = main_col.box()
                morph_box.prop(item, "tw_use_morph")
                if item.tw_use_morph:
                    morph_box.prop(item, "tw_morph_target_name", text="Target")
                    morph_box.prop(item, "tw_morph_value_link", text="Link")


    def draw_special_variables(self, layout, rzm):
        layout.separator()
        main_box = layout.box()
        main_box.label(text="Special Variables:")

        cond_box = main_box.box()
        row = cond_box.row(align=True)
        row.label(text="Conditions:")
        op_row = row.row(align=True)
        op_row.operator("rzm.add_condition", text="", icon='ADD')
        op_row.operator("rzm.remove_condition", text="", icon='REMOVE')
        
        for item in rzm.conditions:
            row = cond_box.row(align=True)
            row.prop(item, "condition_name", text="")
            row.prop(item, "condition_hash", text="Hash")
            
        shape_box = main_box.box()
        row = shape_box.row(align=True)
        row.label(text="Shapes:")
        op_row = row.row(align=True)
        op_row.operator("rzm.add_shape", text="", icon='ADD')
        op_row.operator("rzm.remove_shape", text="", icon='REMOVE')
        
        for item in rzm.shapes:
            row = shape_box.row(align=True)
            row.prop(item, "name", text="")
            row.prop(item, "shape_type", text="")
            row.prop(item, "keyframes", text="")

    def draw_debug_tools(self, layout):
        layout.separator()
        box = layout.box()
        box.label(text="Debug Tools:")
        row = box.row(align=True)
        row.operator("rzm.launch_viewer", text="Viewer")
        row.operator("rzm.launch_inspector", text="Inspector")

classes_to_register = [
    RZM_UL_Elements,
    RZM_UL_Images,
    RZM_UL_Values,
    RZM_UL_ProjectToggles,
    RZM_MT_ValueLinkMenu,
    VIEW3D_PT_RZConstructorDebugPanel
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)