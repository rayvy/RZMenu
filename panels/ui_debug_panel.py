#RZMenu/panels/ui_debug_panel.py
#AI Agent ignore this file, it's needed temporary solution that will be deleted later.
import bpy
from ..utils import texworks_mc


def twaa_active_export_objects(context):
    layer_collection = getattr(context.view_layer, "active_layer_collection", None)
    collection = layer_collection.collection if layer_collection else None
    if collection is None:
        return set()

    objects = set()

    def visit(coll):
        for obj in coll.objects:
            objects.add(obj)
        for child in coll.children:
            visit(child)

    visit(collection)
    return objects


def twaa_objects_for_material_key(material_key):
    objects = []
    seen = set()
    for mat in bpy.data.materials:
        if texworks_mc.material_key(mat.name) != material_key:
            continue
        for obj in texworks_mc.objects_using_material_name(mat.name):
            if obj.name not in seen:
                objects.append(obj)
                seen.add(obj.name)
    return objects


# --- UI LISTS ---
class RZM_UL_Elements(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_val = 'FILE_FOLDER'
        if item.elem_class == 'ANCHOR': icon_val = 'PINNED'
        elif item.elem_class == 'BUTTON': icon_val = 'CHECKBOX_HLT'
        elif item.elem_class == 'SLIDER': icon_val = 'ARROW_LEFTRIGHT'
        elif item.elem_class == 'GRID_CONTAINER': icon_val = 'GRID'
        elif item.elem_class == 'TEXT': icon_val = 'TEXT'
        elif item.elem_class == 'VECTOR_BOX': icon_val = 'MESH_GRID'
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
        
        active_img_idx = context.scene.rzm_active_image_index
        if 0 <= active_img_idx < len(rzm.images):
            img = rzm.images[active_img_idx]
            img_box = box.box()
            img_box.label(text=f"Image Properties ({img.display_name}):")
            img_box.prop(img, "fit_mode")
            
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
        self.draw_ux_sandbox(layout, rzm)
        # self.draw_debug_tools(layout)

    def draw_ux_sandbox(self, layout, rzm):
        layout.separator()
        box = layout.box()
        box.label(text="UX Sandbox & Future Roadmap (2026):", icon='NONE')
        row = box.row(align=True)
        row.operator("rzm.launch_apple_demo", text="Apple UX Demo", icon='SOLO_ON')
        
        row = box.row(align=True)
        row.operator("rzm.launch_gfx_test", text="Graphics Editor (Planned)", icon='IMAGE_DATA')
        row.operator("rzm.launch_3d_test", text="3D Preview (Planned)", icon='VIEW3D')
        
        box.label(text="See qt_editor/TASKLIST0_UIUX_REWORK.md", icon='INFO')

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
            
            if item.elem_class in {'SLIDER', 'VECTOR_BOX'}:
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

        if item.elem_class == 'SLIDER':
            behavior_box = sub.box()
            behavior_box.label(text="Slider Behavior:")
            behavior_box.prop(item, "disable_slider_nums")
            behavior_box.prop(item, "disable_slider_blur")
            behavior_box.prop(item, "disable_slider_prebuild_render")

        if item.elem_class == 'VECTOR_BOX':
            behavior_box = sub.box()
            behavior_box.label(text="Vector Box Behavior:")
            behavior_box.prop(item, "disable_default_xy")

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
        col.prop(rzm, "export_toggle_swap_mode")
        
        box.label(text="Advanced Snippets (Debugging Only):")
        box.prop(rzm.config, "pre_snippet")
        box.prop(rzm.config, "post_snippet")

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

        # FUTURE: 3D Preview Integration
        # Add 'Select Body' operator to pick a Blender object as a preview target.
        # This will allow live-checking decals on 3D geometry from the UI.
        
        # --- TABS ---
        row = main_box.row(align=True)
        row.prop(rzm, "tw_active_tab", expand=True)
        
        active_tab = rzm.tw_active_tab
        show_tags = rzm.tw_show_tags
        show_details = rzm.tw_show_res_details
        
        # Header with Show Tags/Details toggles
        header_row = main_box.row(align=True)
        header_row.alignment = 'RIGHT'
        header_row.prop(rzm, "tw_show_res_details", text="Show Details", icon='INFO', toggle=True)
        header_row.prop(rzm, "tw_show_tags", text="Show Tags", icon='HIDE_OFF' if show_tags else 'HIDE_ON', toggle=True)
        
        if active_tab == 'TWAA':
            mc = getattr(rzm, "tw_mc", None)
            twaa_box = main_box.box()
            twaa_box.label(text="TexWorks AutoAtlas:", icon='NODE_MATERIAL')
            if mc:
                row = twaa_box.row(align=True)
                row.prop(mc, "enabled", text="Enabled")
                row.operator("rzm.tw_mc_build_autoatlas_layout", text="Build TWAA Layout", icon='LINKED')

                settings_row = twaa_box.row(align=True)
                settings_row.prop(mc, "default_resolution", text="Fallback")
                settings_row.prop(mc, "reference_slot", text="")

                settings_row = twaa_box.row(align=True)
                settings_row.prop(mc, "vertex_margin_px", text="Margin")
                settings_row.prop(mc, "pack_gap_px", text="Gap")
                settings_row.prop(mc, "max_atlas_size", text="Max")
                settings_row.prop(mc, "max_raster_pixels", text="CPU")

                twaa_box.prop(mc, "output_subdir", text="Output")

                row = twaa_box.row(align=True)
                op = row.operator("rzm.tw_mc_select_all_material_objects", text="Select All TWAA Objects", icon='RESTRICT_SELECT_OFF')
                op.active_export_only = False
                op = row.operator("rzm.tw_mc_select_all_material_objects", text="Active Export Only", icon='OUTLINER_COLLECTION')
                op.active_export_only = True

                twaa_box.label(text=f"Registered cluster files: {len(rzm.tw_mc_files)}")
                skipped = getattr(rzm, "tw_mc_skipped", None)
                if skipped and len(skipped):
                    skip_box = twaa_box.box()
                    skip_box.label(text=f"Skipped materials: {len(skipped)}", icon='ERROR')
                    for item in skipped:
                        row = skip_box.row(align=True)
                        label = item.material_name or item.material_key or item.name
                        row.label(text=label, icon='MATERIAL')
                        row.label(text=item.slot_name or "-")
                        row.label(text=f"{int(item.resolution[0])}x{int(item.resolution[1])}")
                        row.label(text=item.reason)

                active_export_objects = twaa_active_export_objects(context)
                material_rows = {}
                for entry in rzm.tw_mc_files:
                    key = entry.material_key or texworks_mc.material_key(entry.material_name)
                    row_data = material_rows.setdefault(key, {
                        "material_name": entry.material_name,
                        "slots": [],
                        "paths": [],
                    })
                    if entry.material_name:
                        row_data["material_name"] = entry.material_name
                    if entry.slot_name not in row_data["slots"]:
                        row_data["slots"].append(entry.slot_name)
                    if entry.relative_path:
                        row_data["paths"].append(entry.relative_path)

                for key, row_data in material_rows.items():
                    objects = twaa_objects_for_material_key(key)
                    active_count = sum(
                        1 for obj in objects
                        if obj in active_export_objects and obj.visible_get(view_layer=context.view_layer)
                    )
                    inactive_count = max(0, len(objects) - active_count)
                    row = twaa_box.row(align=True)
                    row.label(text=row_data["material_name"] or key, icon='MATERIAL')
                    row.label(text=f"A:{active_count} I:{inactive_count}")
                    row.label(text=", ".join(row_data["slots"]))
                    op = row.operator("rzm.tw_mc_select_material_objects", text="", icon='RESTRICT_SELECT_OFF')
                    op.material_key = key
                    op.active_export_only = False
                    op.extend = False
                    op = row.operator("rzm.tw_mc_select_material_objects", text="", icon='OUTLINER_COLLECTION')
                    op.material_key = key
                    op.active_export_only = True
                    op.extend = False
                    op = row.operator("rzm.tw_mc_select_preview_material_objects", text="", icon='UV_SYNC_SELECT')
                    op.material_key = key
                    op.extend = False
            else:
                twaa_box.label(text="TWAA settings are not registered", icon='ERROR')

        # --- 1. GLOBAL RESOURCES ---
        elif active_tab == 'RESOURCES':
            res_box = main_box.box()
            header = res_box.row(align=True); header.label(text="Resources:", icon='IMAGE_DATA')
            header.operator("rzm.add_tw_resource", text="", icon='ADD')
            header.operator("rzm.remove_tw_resource", text="", icon='REMOVE')
            header.operator("rzm.clear_tw_resources", text="Clear All", icon='X')
            
            for i, res in enumerate(rzm.tw_resources):
                if show_details:
                    r_box = res_box.box()
                    row = r_box.row(align=True)
                    row.prop(res, "qt_favorite", text="", icon='SOLO_ON' if res.qt_favorite else 'SOLO_OFF', emboss=False)
                    row.prop(res, "name", text=f"[{i}]")
                    if show_tags:
                        row.prop(res, "qt_tag", text="")
                    
                    # Move/Remove Ops
                    ops = row.row(align=True)
                    op_up = ops.operator("rzm.move_tw_item", icon='TRIA_UP', text="")
                    op_up.collection_name = 'resources'; op_up.index = i; op_up.direction = 'UP'
                    op_down = ops.operator("rzm.move_tw_item", icon='TRIA_DOWN', text="")
                    op_down.collection_name = 'resources'; op_down.index = i; op_down.direction = 'DOWN'
                    op_rem = ops.operator("rzm.remove_tw_resource", icon='X', text="")
                    op_rem.index = i
                    
                    row = r_box.row(align=True)
                    row.separator(factor=2)
                    row.prop(res, "type", text="")
                    if res.type == 'ON_DISK':
                        row.prop(res, "path", text="")
                    
                    row = r_box.row(align=True)
                    row.separator(factor=2)
                    row.prop(res, "resolution", text="Res")
                    row.prop(res, "format", text="")
                else:
                    # COMPACT VIEW (Single Row)
                    row = res_box.row(align=True)
                    row.prop(res, "qt_favorite", text="", icon='SOLO_ON' if res.qt_favorite else 'SOLO_OFF', emboss=False)
                    row.prop(res, "name", text=f"[{i}]")
                    row.prop(res, "type", text="")
                    if res.type == 'ON_DISK':
                        row.prop(res, "path", text="")
                    
                    if show_tags:
                        row.prop(res, "qt_tag", text="")
                    
                    # Move/Remove Ops
                    ops = row.row(align=True)
                    op_up = ops.operator("rzm.move_tw_item", icon='TRIA_UP', text="")
                    op_up.collection_name = 'resources'; op_up.index = i; op_up.direction = 'UP'
                    op_down = ops.operator("rzm.move_tw_item", icon='TRIA_DOWN', text="")
                    op_down.collection_name = 'resources'; op_down.index = i; op_down.direction = 'DOWN'
                    op_rem = ops.operator("rzm.remove_tw_resource", icon='X', text="")
                    op_rem.index = i

                res_box.separator(factor=0.5)

        # --- 2. GLOBAL OVERRIDES ---
        elif active_tab == 'OVERRIDES':
            over_box = main_box.box()
            header = over_box.row(align=True); header.label(text="Overrides (3DMigoto):", icon='BLANK1')
            header.operator("rzm.add_tw_override", text="", icon='ADD')
            header.operator("rzm.remove_tw_override", text="", icon='REMOVE')
            header.operator("rzm.clear_tw_overrides", text="Clear All", icon='X')
            
            over_box.operator("rzm.tw_res_over_fill", text="ResOver Fill (Auto-Import)", icon='IMPORT')

            for i, over in enumerate(rzm.tw_overrides):
                # Using a sub-box for better grouping and spacing even in single row
                o_box = over_box.box()
                row = o_box.row(align=True)
                row.prop(over, "qt_favorite", text="", icon='SOLO_ON' if over.qt_favorite else 'SOLO_OFF', emboss=False)
                row.prop(over, "name", text=f"[{i}]")
                row.prop(over, "hash", text="")
                row.prop(over, "override_mode", text="")
                if over.override_mode == 'IB_DIRECT':
                    op_add_bind = row.operator("rzm.add_tw_override_binding", text="", icon='ADD')
                    op_add_bind.override_index = i
                    if not over.bindings and over.resource_name:
                        row.prop(over, "slot_target", text="Fallback")
                        row.prop(over, "resource_name", text="")
                else:
                    row.prop(over, "resource_name", text="")
                
                if show_tags:
                    row.prop(over, "qt_tag", text="")
                
                # Move/Remove Ops
                ops = row.row(align=True)
                op_up = ops.operator("rzm.move_tw_item", icon='TRIA_UP', text="")
                op_up.collection_name = 'overrides'; op_up.index = i; op_up.direction = 'UP'
                op_down = ops.operator("rzm.move_tw_item", icon='TRIA_DOWN', text="")
                op_down.collection_name = 'overrides'; op_down.index = i; op_down.direction = 'DOWN'
                op_rem = ops.operator("rzm.remove_tw_override", icon='X', text="")
                op_rem.index = i

                if over.override_mode == 'IB_DIRECT':
                    for b_idx, binding in enumerate(over.bindings):
                        b_row = o_box.row(align=True)
                        b_row.separator(factor=2)
                        b_row.prop(binding, "custom_target", text="Free")
                        b_row.prop(binding, "tex_type", text="TexType")
                        b_row.prop(binding, "resource_name", text="TexName")
                        op_b_rem = b_row.operator("rzm.remove_tw_override_binding", icon='X', text="")
                        op_b_rem.override_index = i
                        op_b_rem.index = b_idx
                
                over_box.separator(factor=0.3)

        # --- 3. GLOBAL MATERIALS ---
        elif active_tab == 'MATERIALS':
            mat_box = main_box.box()
            header = mat_box.row(align=True); header.label(text="Materials (Behavior):", icon='MATERIAL')
            header.operator("rzm.add_tw_material", text="", icon='ADD')
            header.operator("rzm.remove_tw_material", text="", icon='REMOVE')
            
            for i, mat in enumerate(rzm.tw_materials):
                m_box = mat_box.box()
                row = m_box.row(align=True)
                row.prop(mat, "name", text=f"[{i}]")
                
                # Move/Remove Ops
                ops = row.row(align=True)
                op_up = ops.operator("rzm.move_tw_item", icon='TRIA_UP', text="")
                op_up.collection_name = 'materials'; op_up.index = i; op_up.direction = 'UP'
                op_down = ops.operator("rzm.move_tw_item", icon='TRIA_DOWN', text="")
                op_down.collection_name = 'materials'; op_down.index = i; op_down.direction = 'DOWN'
                op_rem = ops.operator("rzm.remove_tw_material", icon='X', text="")
                op_rem.index = i
                
                row = m_box.row(align=True)
                row.prop(mat, "diffuse_blend_mode", text="")
                m_box.prop(mat, "parameters", text="Params (x46)")

        # --- 4. MAIN BLOCKS ---
        elif active_tab == 'BLOCKS':
            block_box = main_box.box()
            header = block_box.row(align=True)
            header.label(text="Blocks:", icon='NODETREE')
            header.operator("rzm.add_tw_block", text="", icon='ADD')
            header.operator("rzm.duplicate_tw_block", text="", icon='DUPLICATE')
            header.operator("rzm.rescale_active_tw_block", text="Rescale", icon='FULLSCREEN_ENTER')
            header.operator("rzm.remove_tw_block", text="", icon='REMOVE')
            
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
                row = b_box.row(align=True)
                row.prop(block, "create_block_resource", text="Create Block Resource")
                if block.create_block_resource:
                    row.prop(block, "block_resource_size", text="Block Size")

                # Shader Config (x46/x47)
                conf_box = b_box.box()
                conf_box.label(text="Shader Settings:", icon='SETTINGS')
                conf_box.prop(block, "shader_config", text="Color Control (x46)")
                conf_box.prop(block, "shader_overlay", text="Color Overlay (x47)")

                shared_box = b_box.box()
                shared_box.label(text="Shared Resources:", icon='LINKED')
                shared_box.prop(block, "use_shared_textures")
                if block.use_shared_textures:
                    shared_box.prop(block, "shared_textures_block")
                shared_box.prop(block, "uv_rescale")
                
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
                        # RZM_TW: Button for Easy Mask
                        if comp.mask_enabled or comp.hsv_mask_enabled:
                            op_mask = row.operator("rzm.tw_create_easy_mask", text="", icon='BRUSH_DATA')
                            op_mask.block_idx = b_idx
                            op_mask.comp_idx = c_idx
                            op_mask.slot_idx = -1
                        
                        op_rem = row.operator("rzm.remove_tw_component", text="", icon='X')
                        op_rem.block_index = b_idx
                        op_rem.index = c_idx

                        shared_c_box = c_item.box()
                        shared_c_box.label(text="Shared Config:", icon='LINKED')
                        row = shared_c_box.row(align=True)
                        row.prop(comp, "use_shared_config", text="Share")
                        if comp.use_shared_config:
                            row.prop(comp, "shared_config_block", text="Block")
                            row.prop(comp, "shared_config_component", text="Comp")
                        
                        split = c_item.split(factor=0.4)
                        split.prop(comp, "base_resource_name", text="Base Res")
                        split.prop(comp, "base_rect", text="Source")
                        
                        # --- TexMorph Row ---
                        m_row = c_item.row(align=True)
                        m_row.prop(comp, "tex_morph_enabled", text="TexMorph", icon='MOD_UVPROJECT')
                        if comp.tex_morph_enabled:
                            m_row.prop(comp, "tex_morph_resource_name", text="Res")
                            m_row.prop(comp, "tex_morph_link", text="Link")
                        
                        c_item.prop(comp, "rect", text="Atlas Rect")

                        # --- FX & MASKING (Component) ---
                        h_row = c_item.row(align=True)
                        h_row.prop(comp, "hsv_enabled", text="HSV", icon='COLOR')
                        if comp.hsv_enabled:
                            h_row.prop(comp, "hsv_link", text="")
                            h_row.prop(comp, "hsv_mask_enabled", text="", icon='MOD_MASK')

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
                                
                                ops_ext = calc_box.operator("rzm.calc_splitted_island_config", text="Calc Splitted Island (Exp)", icon='MOD_UVPROJECT')
                                ops_ext.block_index = b_idx; ops_ext.comp_index = c_idx; ops_ext.slot_index = s_idx

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
                                h_row.prop(slot, "hsv_only", text="Only")
                                if slot.hsv_enabled:
                                    h_row.prop(slot, "hsv_link", text="")
                                    h_row.prop(slot, "hsv_mask_enabled", text="", icon='MOD_MASK')

                                m_box = fx_box.box()
                                m_row = m_box.row(align=True)
                                m_row.prop(slot, "mask_enabled", text="Slot Mask", icon='MOD_MASK')
                                # RZM_TW: Button for Easy Mask
                                if slot.mask_enabled or slot.hsv_mask_enabled:
                                    op_mask = m_row.operator("rzm.tw_create_easy_mask", text="", icon='BRUSH_DATA')
                                    op_mask.block_idx = b_idx
                                    op_mask.comp_idx = c_idx
                                    op_mask.slot_idx = s_idx

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
    RZM_UL_Elements, RZM_UL_Images, RZM_UL_ProjectToggles,
    RZM_MT_ValueLinkMenu, RZM_MT_TwFormatMenu,
    VIEW3D_PT_RZConstructorDebugPanel
]
def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
