# RZMenu/panels/main_ui.py
import bpy
import os

# --- Меню для назначения тогглов ---
class RZM_MT_AssignToggleMenu(bpy.types.Menu):
    bl_label = "Assign Toggle"
    bl_idname = "RZM_MT_assign_toggle_menu"
    def draw(self, context):
        # FIX IMPORT: helpers -> core.utils
        from ..core.utils import get_assignable_toggles 
        layout = self.layout
        assignable = get_assignable_toggles(context)
        if not assignable:
            layout.label(text="No Toggles to Assign", icon='INFO')
            return
        for name in assignable:
            op = layout.operator("rzm.assign_object_toggle", text=name)
            op.toggle_name = name

class RZM_MT_AssignTexSlotMenu(bpy.types.Menu):
    bl_label = "Assign TexSlot"
    bl_idname = "RZM_MT_assign_tex_slot_menu"
    def draw(self, context):
        layout = self.layout
        slots = ["Diffuse", "LightMap", "NormalMap", "MaterialMap", "ExtraMap"]
        for s in slots:
            op = layout.operator("rzm.assign_object_tex_slot", text=s)
            op.slot_name = s

class VIEW3D_PT_RZConstructorPanel(bpy.types.Panel):
    bl_label = "RZ Constructor"
    bl_idname = "VIEW3D_PT_rz_constructor_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_order = 0
    
    # ... (draw_capture_pro_ui и draw_captures_preview_ui оставляем без изменений) ...
    def draw_capture_pro_ui(self, context, layout):
        settings = context.scene.rzm_capture_settings
        capture_box = layout.box()
        capture_box.label(text="Image Capture (Pro)", icon='RESTRICT_RENDER_OFF')
        col = capture_box.column(align=True)
        col.label(text="Shading Mode:")
        col.prop(settings, "shading_mode", text="")
        if settings.shading_mode == 'RENDERED':
            col.prop(settings, "add_temp_light")
        col.separator()
        col.prop(settings, "use_overlays", text="Include Viewport Overlays")
        col.prop(settings, "resolution", text="Image Size (px)")
        capture_box.separator()
        row = capture_box.row(align=True)
        row.prop(context.scene, "rzm_capture_overwrite_id", text="Overwrite ID")
        row.operator("rzm.capture_image", text="Capture")

    def draw_captures_preview_ui(self, context, layout):
        scene = context.scene
        rzm = scene.rzm
        captured_images = sorted(
            [img for img in rzm.images if img.source_type == 'CAPTURED'],
            key=lambda i: i.id, reverse=True
        )
        preview_box = layout.box()
        row = preview_box.row()
        icon = 'TRIA_DOWN' if scene.rzm_show_captures_preview else 'TRIA_RIGHT'
        row.prop(scene, "rzm_show_captures_preview", text="CAPTURE PREVIEW", icon=icon, emboss=False)
        if scene.rzm_show_captures_preview:
            if not captured_images:
                preview_box.label(text="No captured images yet.", icon='INFO')
                return
            grid = preview_box.column_flow(columns=4, align=True)
            for rzm_image in captured_images:
                item_box = grid.box()
                if rzm_image.image_pointer:
                    item_box.template_ID_preview(rzm_image, "image_pointer", rows=3, cols=3, hide_buttons=True)
                else:
                    item_box.label(text="<Missing>", icon='ERROR')
                info_row = item_box.row(align=True)
                info_row.alignment = 'LEFT'
                name_row = info_row.split(factor=0.85)
                name_row.label(text=f"ID {rzm_image.id}: {rzm_image.display_name}")
                op = info_row.operator("rzm.remove_image", text="", icon='TRASH', emboss=False)
                op.image_id_to_remove = rzm_image.id

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rzm = scene.rzm

        # 1. LAUNCH QT EDITOR (Now at the top)
        row = layout.row(align=True)
        row.scale_y = 1.2
        
        # Safety Check for PySide6
        try:
            import PySide6
            row.operator("rzm.launch_qt_editor", text="LAUNCH", icon='EXPORT')
        except ImportError:
            error_box = layout.box()
            error_box.alert = True
            error_box.label(text="Something got wrong or PySide6 is not installed,", icon='ERROR')
            error_box.label(text="install or re-check dependencies in 'RZ Dependencies' panel.")
            
        layout.separator()

        # 2. TARGET GAME SELECTION
        game_box = layout.box()
        row = game_box.row()
        row.label(text="Target Game:", icon='COLOR_RED') 
        row.prop(rzm.game, "selection", text="")

        # 3. SETUP & INFO BLOCKS
        self.draw_setup_block(context, layout)
        self.draw_info_block(context, layout)

        layout.separator()

        # 4. CAPTURE TOOLS (Collapsible)
        cap_box = layout.box()
        row = cap_box.row()
        icon = 'TRIA_DOWN' if scene.rzm_show_capture_tools else 'TRIA_RIGHT'
        row.prop(scene, "rzm_show_capture_tools", text="CAPTURE TOOLS", icon=icon, emboss=False)
        
        if scene.rzm_show_capture_tools:
            self.draw_capture_pro_ui(context, cap_box)
            # Auto Capture
            cap_box.operator("rzm.auto_capture", text="Auto-Capture Icons", icon='AUTO')

        layout.separator()

        # 5. OBJECT PROPERTIES
        self.draw_object_properties(context, layout)
        
        layout.separator()

        # 6. EDITOR MODE
        mode_box = layout.box()
        mode_box.label(text="Editor Mode:")
        row = mode_box.row(align=True)
        row.prop(scene, "rzm_editor_mode", expand=True)

        if scene.rzm_editor_mode == 'PRO':
            mode_box.prop(scene, "rzm_show_debug_panel", text="Show Debug Panel", toggle=True, icon='GHOST_ENABLED')

        layout.separator()

        # 7. CAPTURES PREVIEW
        self.draw_captures_preview_ui(context, layout)
        
        # 8. FILE MANAGEMENT (At the very bottom)
        # We will add it after any children panels are drawn? No, Blender puts children after.
        # But we can put a divider here.
        layout.separator()
        file_box = layout.box()
        file_box.label(text="Project Files (.rzm)", icon='FILE_BLEND')
        row = file_box.row(align=True)
        row.operator("rzm.save_template", text="Save Scene")
        row.operator("rzm.load_template", text="Load Scene")
        row.operator("rzm.reset_scene", text="", icon='TRASH')

    def draw_setup_block(self, context, layout):
        scene = context.scene
        rzm = scene.rzm
        game = rzm.game.selection
        
        box = layout.box()
        box.label(text="Setup: Addon Configuration", icon='SETTINGS')
        
        row = box.row(align=True)
        row.operator("rzm.autosetup_game", text="Auto-Setup Addon", icon='AUTO')
        row.operator("rzm.refresh_addon_data", text="Sync Data", icon='FILE_REFRESH')
        
        # Отображение путей целевого аддона
        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
            if hasattr(scene, "xxmi"):
                xxmi = scene.xxmi
                box.prop(xxmi, "dump_path", text="Dump")
                box.prop(xxmi, "destination_path", text="Mod Folder")
                box.prop(xxmi, "template_path", text="Template")
                box.prop(xxmi, "use_custom_template")
            else:
                box.label(text="XXMI Tools Not Active", icon='ERROR')
                
        elif game == 'ArknightsEndfield':
            if hasattr(scene, "efmi_tools_settings"):
                efmi = scene.efmi_tools_settings
                box.prop(efmi, "object_source_folder", text="Source")
                box.prop(efmi, "mod_output_folder", text="Output")
                box.prop(efmi, "custom_template_path", text="Template")
                box.prop(efmi, "use_custom_template")
            else:
                box.label(text="EFMI Tools Not Active", icon='ERROR')

        elif game == 'WutheringWaves':
            if hasattr(scene, "wwmi_tools_settings"):
                wwmi = scene.wwmi_tools_settings
                box.prop(wwmi, "object_source_folder", text="Source")
                box.prop(wwmi, "mod_output_folder", text="Output")
                box.prop(wwmi, "custom_template_path", text="Template")
                box.prop(wwmi, "use_custom_template")
            else:
                box.label(text="WWMI Tools Not Active", icon='ERROR')

    def draw_info_block(self, context, layout):
        scene = context.scene
        rzm = scene.rzm
        game = rzm.game.selection
        settings = rzm.export_settings
        
        box = layout.box()
        box.label(text="Export Management", icon='INFO')
        
        # Единая кнопка экспорта для всех игр
        row = box.row()
        row.scale_y = 1.5
        row.operator("rzm.full_export", text="Export Mod (with auto-setup)", icon='EXPORT')
        
        # --- Custom Scripts Management ---
        script_box = box.column(align=True)
        row = script_box.row(align=True)
        icon = 'TRIA_DOWN' if settings.show_custom_scripts else 'TRIA_RIGHT'
        row.prop(settings, "show_custom_scripts", text="POST-EXPORT SCRIPTS", icon=icon, toggle=True, emboss=False)
        
        if settings.show_custom_scripts:
            # List of scripts
            row = script_box.row()
            row.template_list("RZM_UL_CustomScriptList", "", settings, "custom_scripts", settings, "custom_scripts_index", rows=3)
            
            # Side buttons
            col = row.column(align=True)
            col.operator("rzm.add_custom_script", text="", icon='ADD')
            col.operator("rzm.remove_custom_script", text="", icon='REMOVE').index = settings.custom_scripts_index
            col.separator()
            op_up = col.operator("rzm.move_custom_script", text="", icon='TRIA_UP')
            op_up.index = settings.custom_scripts_index
            op_up.direction = 'UP'
            op_down = col.operator("rzm.move_custom_script", text="", icon='TRIA_DOWN')
            op_down.index = settings.custom_scripts_index
            op_down.direction = 'DOWN'
            
            # Details for active script
            if settings.custom_scripts and settings.custom_scripts_index >= 0:
                try:
                    active_script = settings.custom_scripts[settings.custom_scripts_index]
                    script_box.prop(active_script, "path", text="")
                    
                    details = script_box.column(align=True)
                    details.prop(active_script, "args", icon='CONSOLE')
                    
                    row = details.row(align=True)
                    row.prop(active_script, "auto_input", toggle=True)
                    row.prop(active_script, "use_timeout", toggle=True)
                    if active_script.use_timeout:
                        row.prop(active_script, "timeout", text="sec")
                except IndexError:
                    pass

        if game == 'EMULATOR':
            box.label(text="Running in Emulator mode (No game addon needed)")


    def draw_captures_preview_ui(self, context, layout):
        # ... (implementation was likely already present or handled elsewhere) ...
        pass


    def draw_object_properties(self, context, layout):
        from ..core.utils import get_toggle_slot_occupancy, find_toggle_def
        
        target_obj = context.active_object
        if not target_obj:
            layout.label(text="Select an object to see its properties.", icon='INFO')
            return

        # --- TOGGLES ---
        box = layout.box()
        row = box.row(align=True)
        row.label(text="RZ-Toggles", icon='CHECKBOX_HLT')
        row.menu("RZM_MT_assign_toggle_menu", text="Assign", icon="ADD")
        
        toggle_keys = sorted([key for key in target_obj.keys() if key.startswith("rzm.Toggle.")])

        if not toggle_keys:
            box.label(text="No toggles assigned.", icon='INFO')
        else:
            for key in toggle_keys:
                value = target_obj.get(key)
                if value is None: continue
                
                base_name = key.replace("rzm.Toggle.", "", 1)
                sub_box = box.box()
                
                header = sub_box.row(align=True)
                toggle_def = find_toggle_def(context, base_name)
                
                if toggle_def:
                    icon_exp = 'TRIA_DOWN' if toggle_def.show_occupancy else 'TRIA_RIGHT'
                    header.prop(toggle_def, "show_occupancy", text="", icon=icon_exp, emboss=False)
                
                header.label(text=base_name, icon='OUTLINER_OB_MESH')
                op_sel_all = header.operator("rzm.select_objects_with_toggle", text="", icon='SELECT_SET')
                op_sel_all.toggle_name = base_name
                op_rem = header.operator("rzm.remove_object_toggle", text="", icon='X', emboss=False)
                op_rem.toggle_name = key

                bits_row = sub_box.row(align=True)
                try:
                    bits_list = list(value)
                except:
                    bits_list = []

                for i, bit in enumerate(bits_list):
                    icon = 'CHECKBOX_HLT' if bit else 'CHECKBOX_DEHLT'
                    op_bit = bits_row.operator("rzm.toggle_object_bit", text="", icon=icon, emboss=False)
                    op_bit.toggle_name = key
                    op_bit.bit_index = i
                
                if toggle_def and toggle_def.show_occupancy:
                    occupancy = get_toggle_slot_occupancy(context, base_name)
                    info_col = sub_box.column(align=True)
                    info_col.separator()
                    if not any(occupancy):
                        info_col.label(text="All other slots free", icon='INFO')
                    else:
                        for i in range(len(bits_list)):
                            slot_row = info_col.row(align=True)
                            slot_row.alignment = 'LEFT'
                            if i in occupancy:
                                op_sel_slot = slot_row.operator("rzm.select_occupying_objects", text="", icon='RESTRICT_SELECT_ON')
                                op_sel_slot.toggle_name = base_name
                                op_sel_slot.slot_index = i
                                slot_row.label(text=f"Slot {i+1}:", icon='CHECKBOX_HLT')
                                names = ", ".join(occupancy[i])
                                if len(names) > 30: names = names[:27] + "..."
                                slot_row.label(text=names)
                            else:
                                slot_row.label(text="", icon='BLANK1')
                                slot_row.label(text=f"Slot {i+1}: <Free>", icon='CHECKBOX_DEHLT')

        # --- TEXSLOTS ---
        box = layout.box()
        row = box.row(align=True)
        row.label(text="RZ-TexSlots", icon='TEXTURE_DATA')
        row.menu("RZM_MT_assign_tex_slot_menu", text="Assign", icon="ADD")

        tex_keys = sorted([key for key in target_obj.keys() if key.startswith("rzm.TexSlot.")])
        if not tex_keys:
            box.label(text="No texture slots assigned.", icon='INFO')
        else:
            for key in tex_keys:
                display_name = key.replace("rzm.TexSlot.", "")
                row = box.row(align=True)
                
                # Используем split для четкого разделения имени и поля ввода
                split = row.split(factor=0.3)
                split.label(text=display_name, icon='IMAGE_DATA')
                
                # Поле ввода и кнопка удаления в одной группе
                sub = split.row(align=True)
                sub.prop(target_obj, f'["{key}"]', text="")
                op_rem = sub.operator("rzm.remove_object_tex_slot", text="", icon='X', emboss=False)
                op_rem.prop_key = key

        # --- CUSTOM DRAW ---
        box = layout.box()
        row = box.row(align=True)
        row.label(text="Custom Draw", icon='BRUSH_DATA')
        row.menu("RZM_MT_add_custom_draw_menu", text="Add", icon="ADD")
        
        # Skip Draw Toggle
        skip_draw = target_obj.get("SkipDraw", False)
        icon = 'CHECKBOX_HLT' if skip_draw else 'CHECKBOX_DEHLT'
        box.operator("rzm.toggle_skip_draw", text="Skip Draw", icon=icon)
        
        # List of active Custom Draws
        custom_draw_keys = sorted([key for key in target_obj.keys() if key.startswith("CustomDraw.")])
        if custom_draw_keys:
            col = box.column(align=True)
            for key in custom_draw_keys:
                r = col.row(align=True)
                r.label(text=key.replace("CustomDraw.", ""), icon='DOT')
                op = r.operator("rzm.remove_custom_draw", text="", icon='X', emboss=False)
                op.prop_name = key



# ... (Остальные панели без изменений) ...

class VIEW3D_PT_RZM_AutoMenuCreator(bpy.types.Panel):
    bl_label = "Auto Menu Creator"
    bl_idname = "VIEW3D_PT_rzm_auto_menu_creator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_parent_id = "VIEW3D_PT_rz_constructor_panel"
    bl_order = 98 

    def draw(self, context):
        layout = self.layout
        rzm = context.scene.rzm
        auto_menu = rzm.auto_menu
        
        # Statistics
        stat_box = layout.box()
        stat_box.label(text="Scene Context:", icon='VIEW3D')
        
        row = stat_box.row()
        row.label(text=f"Total Toggles Found: {auto_menu.stat_toggles_count}", icon='DOT')
        row.label(text=f"Meshes Using Toggles: {auto_menu.stat_meshes_count}", icon='MESH_DATA')
        stat_box.operator("rzm.amc_refresh_stats", text="Refresh Stats", icon='FILE_REFRESH')
        
        # --- Action Buttons (Fixed at Top for easy access) ---
        act_box = layout.box()
        act_box.label(text="Process:", icon='PLAY')
        
        row = act_box.row(align=True)
        row.prop(auto_menu, "last_loaded_rzmct", text="")
        row.operator("rzm.amc_load_template", text="Load", icon='FILE_FOLDER')

        row = act_box.row(align=True)
        row.operator("rzm.amc_pack_template", text="Pack Template", icon='PACKAGE')
        row.operator("rzm.amc_build_menu", text="Build!", icon='MOD_BUILD')

        # --- Configuration Blocks ---
        layout.separator()
        
        # 1. MAIN BLOCK
        main_box = layout.box()
        main_box.label(text="Main Block Overrides:", icon='NONE')
        col = main_box.column(align=True)
        col.prop(auto_menu, "main_pos")
        col.prop(auto_menu, "main_size")
        
        # 2. PAGE BLOCK
        page_box = layout.box()
        page_box.label(text="Page Block Layout:", icon='NONE')
        col = page_box.column(align=True)
        col.prop(auto_menu, "page_pos")
        col.prop(auto_menu, "page_size")
        
        row = col.row(align=True)
        row.prop(auto_menu, "margin_x")
        row.prop(auto_menu, "margin_y")
        row = col.row(align=True)
        row.prop(auto_menu, "padding_x")
        row.prop(auto_menu, "padding_y")

        # 3. BUTTONS
        btn_box = layout.box()
        btn_box.label(text="Button Spawning:", icon='NONE')
        col = btn_box.column(align=True)
        row = col.row(align=True)
        row.prop(auto_menu, "base_button_width", text="W")
        row.prop(auto_menu, "base_button_height", text="H")
        
        col.separator()
        row = col.row(align=True)
        row.prop(auto_menu, "button_auto_icons", toggle=True, icon='IMAGE_DATA')
        row.prop(auto_menu, "button_rename_text", toggle=True, icon='TEXT')
        
        # Actions
        act_box = layout.box()
        act_box.label(text="Actions:", icon='PLAY')
        act_box.operator("rzm.amc_pack_template", text="Pack .rzmct", icon='PACKAGE')
        
        row = act_box.row(align=True)
        row.prop(auto_menu, "last_loaded_rzmct", text="")
        row.operator("rzm.amc_load_template", text="Load", icon='FILE_FOLDER')
        
        act_box.operator("rzm.amc_build_menu", text="Build Auto Menu", icon='MOD_BUILD')
        
        # Log Box
        layout.separator()
        log_box = layout.box()
        log_box.label(text="Build Log:", icon='TEXT')
        col = log_box.column(align=True)
        # Using a label for each line to simulate a multi-line box
        for line in auto_menu.auto_menu_log.split('\n'):
            col.label(text=line)

class VIEW3D_PT_RZM_ExportManager(bpy.types.Panel):
    bl_label = "Mod Export Manager"
    bl_idname = "VIEW3D_PT_rzm_export_manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_parent_id = "VIEW3D_PT_rz_constructor_panel"
    bl_order = 99 

    def draw(self, context):
        layout = self.layout
        rzm = context.scene.rzm
        if not hasattr(rzm, "export_settings") or not rzm.export_settings:
            layout.label(text="Settings loading...", icon='INFO')
            return
        settings = rzm.export_settings
        box = layout.box()
        box.label(text="Target Settings:", icon='FILE_FOLDER')
        box.prop(settings, "mod_name")
        box.prop(settings, "use_xxmi_path")
        
        # UI Blur move to here
        box.prop(rzm.addons, "pre_render_blur", text="UI Blur")

        final_path = ""
        if settings.use_xxmi_path:
             if hasattr(context.scene, 'xxmi') and hasattr(context.scene.xxmi, 'destination_path'):
                 final_path = context.scene.xxmi.destination_path
        if not final_path:
            final_path = settings.custom_path
            box.prop(settings, "custom_path")
        if final_path:
            abs_path = bpy.path.abspath(final_path)
            if os.path.exists(abs_path):
                box.label(text=f"Target: .../{os.path.basename(os.path.normpath(abs_path))}", icon='CHECKMARK')
            else:
                box.label(text="Target does not exist", icon='INFO')
        else:
            box.label(text="No path set", icon='ERROR')
        
        box.prop(settings, "icc_profile")
        
        layout.separator()
        if hasattr(bpy.ops.rzm, "export_atlas"):
            row = layout.row()
            row.scale_y = 1.3
            row.operator("rzm.export_atlas", text="Update Atlas (Quick)", icon='FILE_REFRESH')
        col = layout.column(align=True)
        col.separator()
        col.label(text="Initialization:", icon='PACKAGE')
        sub_box = col.box()
        sub_box.prop(settings, "overwrite_scripts", text="Force Overwrite")
        if hasattr(bpy.ops.rzm, "initialize_mod"):
            sub_box.operator("rzm.initialize_mod", text="Initialize Mod", icon='MOD_BUILD')

        tw_box = col.box()
        tw_box.operator("rzm.tw_export_hierarchy", text="Export Hierarchy", icon='FILE_FOLDER')
        tw_box.operator("rzm.tw_debug_sync", text="Debug Sync", icon='CONSOLE')


class RZM_UL_CustomScriptList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "enabled", text="")
            name = os.path.basename(item.path) if item.path else "New Script"
            row.label(text=name, icon='FILE_SCRIPT')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_SCRIPT')

classes_to_register = [ 
    RZM_UL_CustomScriptList,
    RZM_MT_AssignToggleMenu, 
    RZM_MT_AssignTexSlotMenu,
    VIEW3D_PT_RZConstructorPanel, 
    VIEW3D_PT_RZM_AutoMenuCreator,
    VIEW3D_PT_RZM_ExportManager
]
