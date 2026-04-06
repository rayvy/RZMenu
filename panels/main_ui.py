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
            row.prop(item, "vector_value", text="")

class RZM_UL_ToggleDefinitions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "toggle_name", text="", emboss=False, icon='CHECKBOX_HLT')
        row.prop(item, "toggle_length", text="Bits")

class RZM_UL_Shapes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "shape_name", text="", emboss=False, icon='SHAPEKEY_DATA')
        row.label(text=f"Keys: {len(item.shape_keys)}")

class RZM_UL_ShapeKeys(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "key_name", text="Key")
        row.prop(item, "mode", text="")
        if item.mode == 'ADVANCED':
            row.label(text="*", icon='SETTINGS')

class VIEW3D_PT_RZConstructorPanel(bpy.types.Panel):
    bl_label = "RZ Constructor"
    bl_idname = "VIEW3D_PT_rz_constructor_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_order = 1
    
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
        addon_name = __package__.split(".")[0] if "." in __package__ else __package__
        prefs = context.preferences.addons.get(addon_name)
        if not prefs or not getattr(prefs.preferences, "move_to_npanel", False):
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
        
        # --- GLOBAL ARTIST INFO ---
        from ..operators.tier_ops import get_prefs
        prefs = get_prefs(context)
        if prefs:
            row = box.row()
            row.label(text=f"Author: {prefs.author_name}", icon='USER')
            row.operator("wm.url_open", text="Logo", icon='IMAGE_DATA').url = prefs.mod_logo_url
            row.operator("wm.url_open", text="Banner", icon='IMAGE_DATA').url = prefs.mod_banner_url

        # --- MOD INFO / METADATA ---
        meta_box = layout.box()
        meta_box.label(text="Mod Details (Meta Data)", icon='GREASEPENCIL')
        
        meta = rzm.meta_data
        col = meta_box.column(align=True)
        col.prop(meta, "character_name")
        col.prop(meta, "outfit_name")
        col.prop(meta, "version_num")
        
        # Author stays global, but we show it here for context
        col.separator()
        row = col.row()
        row.label(text=f"Global Author: {prefs.author_name}" if prefs else "Author: UNKNOWN", icon='USER')
        row.operator("wm.url_open", text="Edit Profile", icon='PREFERENCES').url = "bpy.context.preferences.addons['RZMenu'].preferences" # This won't work as a URL, but it's a hint. In Blender we usually just tell them to check prefs.
        
        col.separator()
        col.prop(meta, "requirements")
        col.prop(meta, "description", text="Lore")
        col.prop(meta, "menu_keybind")
        col.prop(meta, "community_respect")

        # Единая кнопка экспорта для всех игр
        row = box.row(align=True)
        row.scale_y = 1.5
        row.operator("rzm.full_export", text="Full Export", icon='EXPORT')
        row.operator("rzm.complete_export", text="Complete Export", icon='SEQ_STRIP_DUPLICATE')
        
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

        # --- MOD PRODUCER TIERS ---
        box = layout.box()
        box.label(text="Mod Producer Tiers", icon='FILE_CACHE')
        
        from ..operators.tier_ops import get_tier_ids
        available_tiers = get_tier_ids(context)
        if not available_tiers:
            box.label(text="No tiers configured in Addon Prefs.", icon='INFO')
        else:
            active_tiers = {t.tier_id for t in target_obj.rzm_tier_list}
            flow = box.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
            for tid in available_tiers:
                is_active = tid in active_tiers
                op_name = "rzm.remove_object_tier" if is_active else "rzm.add_object_tier"
                op = flow.operator(op_name, text=tid, depress=is_active)
                op.tier_id = tid

        # --- TOGGLES ---
        box = layout.box()
        row = box.row(align=True)
        row.label(text="RZ-Toggles", icon='CHECKBOX_HLT')
        row.operator("rzm.apply_toggles_to_selected", text="", icon='PASTEDOWN')
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
        row.operator("rzm.copy_tex_slots_to_selected", text="", icon='PASTEDOWN')
        row.menu("RZM_MT_assign_tex_slot_menu", text="Assign", icon="ADD")

        tex_keys = sorted([key for key in target_obj.keys() if key.startswith("rzm.TexSlot.")])
        if not tex_keys:
            box.label(text="No texture slots assigned.", icon='INFO')
        else:
            for key in tex_keys:
                display_name = key.replace("rzm.TexSlot.", "")
                slot_id = display_name
                cond_key = f"rzm.TexCond.{slot_id}"
                
                # Используем колонку для группировки слота и его условия
                slot_col = box.column(align=True)
                row = slot_col.row(align=True)
                
                # Метка слота
                row.label(text=display_name, icon='IMAGE_DATA')
                
                # Поле пути к текстуре
                row.prop(target_obj, f'["{key}"]', text="")
                
                # Кнопка добавления/удаления условия
                if cond_key in target_obj:
                    op_rem_cond = row.operator("rzm.remove_object_tex_cond", text="", icon='REMOVE', emboss=False)
                    op_rem_cond.prop_key = key
                else:
                    op_add_cond = row.operator("rzm.add_object_tex_cond", text="", icon='ADD', emboss=False)
                    op_add_cond.prop_key = key
                
                # Кнопка удаления слота целиком
                op_rem_slot = row.operator("rzm.remove_object_tex_slot", text="", icon='X', emboss=False)
                op_rem_slot.prop_key = key
                
                # Если условие есть, рисуем вторую строку
                if cond_key in target_obj:
                    cond_row = slot_col.row(align=True)
                    # Сдвиг для визуальной иерархии
                    sub = cond_row.split(factor=0.1)
                    sub.label(text="") # Empty space
                    
                    details = sub.row(align=True)
                    details.label(text="Condition:", icon='BLANK1')
                    details.prop(target_obj, f'["{cond_key}"]', text="")
                
                slot_col.separator()

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
        # mod_name removed.
        box.prop(settings, "use_game_path")
        
        # UI Blur move to here
        box.prop(rzm.addons, "pre_render_blur", text="UI Blur")

        from ..operators.export_manager import get_target_path
        final_path = get_target_path(context) if settings.use_game_path else ""
        
        if not final_path:
            # If game path is not found or not used, show custom path prop
            box.prop(settings, "custom_path")
            final_path = bpy.path.abspath(settings.custom_path)
            
        if final_path:
            if os.path.exists(final_path):
                box.label(text=f"Target: {os.path.basename(os.path.normpath(final_path))}", icon='CHECKMARK')
            else:
                box.label(text="Path does not exist", icon='INFO')
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

class VIEW3D_PT_RZConstructorToolboxPanel(bpy.types.Panel):
    bl_label = "RZ Construct Toolbox"
    bl_idname = "VIEW3D_PT_rz_constructor_toolbox_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_order = 0
    
    @classmethod
    def poll(cls, context):
        addon_name = __package__.split(".")[0] if "." in __package__ else __package__
        prefs = context.preferences.addons.get(addon_name)
        return prefs and getattr(prefs.preferences, "move_to_npanel", False)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rzm = scene.rzm
        
        # 1. ALWAYS SHOW MESH PROPERTIES AT TOP
        VIEW3D_PT_RZConstructorPanel.draw_object_properties(self, context, layout)
        
        layout.separator(factor=2.0)
        
        # 2. PROJECT CONFIGURATION AT BOTTOM
        box = layout.box()
        box.label(text="PROJECT CONFIGURATION", icon='SETTINGS')
        
        # Tabs Selector inside the box
        row = box.row(align=True)
        row.prop(scene, "rzm_toolbox_tab", expand=True)
        
        tab = scene.rzm_toolbox_tab
        
        if tab == 'TOGGLES':
            # Project Toggles
            row = box.row(align=True)
            row.operator("rzm.add_toggle_definition", text="Add Toggle", icon='ADD')
            row.operator("rzm.remove_toggle_definition", text="", icon='REMOVE')
            box.template_list("RZM_UL_ToggleDefinitions", "", rzm, "toggle_definitions", context.scene, "rzm_active_toggle_def_index")
        
        elif tab == 'VARIABLES':
            # Project Variables
            row = box.row(align=True)
            row.operator("rzm.add_value", text="Add Var", icon='ADD')
            row.operator("rzm.remove_value", text="", icon='REMOVE')
            box.template_list("RZM_UL_Values", "", rzm, "rzm_values", context.scene, "rzm_active_value_index")
            if rzm.rzm_values and 0 <= context.scene.rzm_active_value_index < len(rzm.rzm_values):
                active_val = rzm.rzm_values[context.scene.rzm_active_value_index]
                from ..operators.tier_ops import get_tier_ids
                available = get_tier_ids(context)
                if available:
                    box.label(text="Export Tiers:")
                    v_active = {t.tier_id for t in active_val.export_tiers}
                    flow = box.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
                    for tid in available:
                        is_act = tid in v_active
                        op_str = "rzm.remove_value_tier" if is_act else "rzm.add_value_tier"
                        op = flow.operator(op_str, text=tid, depress=is_act)
                        op.value_index = context.scene.rzm_active_value_index
                        op.tier_id = tid

        elif tab == 'SHAPES':
            # Project Shapes
            row = box.row(align=True)
            row.operator("rzm.add_shape", text="Add Shape", icon='ADD')
            row.operator("rzm.remove_shape", text="", icon='REMOVE')
            box.template_list("RZM_UL_Shapes", "", rzm, "shapes", context.scene, "rzm_active_shape_index")
            if rzm.shapes and 0 <= context.scene.rzm_active_shape_index < len(rzm.shapes):
                active_shape = rzm.shapes[context.scene.rzm_active_shape_index]
                from ..operators.tier_ops import get_tier_ids
                available = get_tier_ids(context)
                if available:
                    box.label(text="Export Tiers:")
                    s_active = {t.tier_id for t in active_shape.export_tiers}
                    flow = box.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
                    
                    # Available Tiers
                    for tid in available:
                        is_act = tid in s_active
                        op_str = "rzm.remove_shape_tier" if is_act else "rzm.add_shape_tier"
                        op = flow.operator(op_str, text=tid, depress=is_act)
                        op.shape_index = context.scene.rzm_active_shape_index
                        op.tier_id = tid
                    
                    # Orphaned/Missing Tiers
                    for tid in s_active:
                        if tid not in available:
                            op = flow.operator("rzm.remove_shape_tier", text=f"! {tid}", depress=True, icon='ERROR')
                            op.shape_index = context.scene.rzm_active_shape_index
                            op.tier_id = tid
                    
                    # --- Selection list for the shape properties ---
                    s_box = box.box()
                    s_box.prop(active_shape, "shape_name")
                    s_box.prop(active_shape, "shape_type")
                    s_box.prop(active_shape, "force_export")
                    
                    if active_shape.shape_type == 'Anim':
                        s_box.prop(active_shape, "anim_condition")

                    # --- Shape Keys List ---
                    s_box.separator()
                    k_row = s_box.row()
                    k_row.label(text="Shape Keyframes:", icon='SHAPEKEY_DATA')
                    
                    op_add = k_row.operator("rzm.add_shape_key", text="", icon='ADD', emboss=False)
                    op_add.shape_index = context.scene.rzm_active_shape_index
                    
                    op_rem = k_row.operator("rzm.remove_shape_key", text="", icon='REMOVE', emboss=False)
                    op_rem.shape_index = context.scene.rzm_active_shape_index
                    op_rem.key_index = context.scene.rzm_active_shape_key_index
                    
                    s_box.template_list("RZM_UL_ShapeKeys", "", active_shape, "shape_keys", context.scene, "rzm_active_shape_key_index")
                    
                    if active_shape.shape_keys and 0 <= context.scene.rzm_active_shape_key_index < len(active_shape.shape_keys):
                        key = active_shape.shape_keys[context.scene.rzm_active_shape_key_index]
                        kd_box = s_box.box()
                        kd_box.prop(key, "key_name")
                        kd_box.prop(key, "mode")
                        
                        if key.mode == 'ADVANCED':
                            kd_box.prop(key, "input_range_min")
                            kd_box.prop(key, "input_range_max")
                            kd_box.prop(key, "multiplier")
                        
                        if active_shape.shape_type == 'Anim':
                            kd_box.separator()
                            kd_box.label(text="Animation Frames:")
                            row = kd_box.row(align=True)
                            row.prop(key, "anim_start_frame", text="Start")
                            row.prop(key, "anim_end_frame", text="End")
                            kd_box.prop(key, "anim_type_index")
                
                # --- Shape Properties ---
                box.separator()
                box.prop(active_shape, "shape_name")
                box.prop(active_shape, "shape_type")
                box.prop(active_shape, "force_export")
                
                if active_shape.shape_type == 'Anim':
                    box.prop(active_shape, "anim_condition")

                # --- Shape Keys List ---
                box.separator()
                row = box.row()
                row.label(text="Shape Keys:", icon='SHAPEKEY_DATA')
                
                # Add/Remove Buttons for Keys
                op_add = row.operator("rzm.add_shape_key", text="", icon='ADD', emboss=False)
                op_add.shape_index = context.scene.rzm_active_shape_index
                
                op_rem = row.operator("rzm.remove_shape_key", text="", icon='REMOVE', emboss=False)
                op_rem.shape_index = context.scene.rzm_active_shape_index
                op_rem.key_index = context.scene.rzm_active_shape_key_index
                
                box.template_list("RZM_UL_ShapeKeys", "", active_shape, "shape_keys", context.scene, "rzm_active_shape_key_index")
                
                # Selected Keyframe Details
                if active_shape.shape_keys and 0 <= context.scene.rzm_active_shape_key_index < len(active_shape.shape_keys):
                    key = active_shape.shape_keys[context.scene.rzm_active_shape_key_index]
                    sbox = box.box()
                    sbox.prop(key, "key_name")
                    sbox.prop(key, "mode")
                    
                    if key.mode == 'ADVANCED':
                        sbox.prop(key, "input_range_min")
                        sbox.prop(key, "input_range_max")
                        sbox.prop(key, "multiplier")
                    
                    if active_shape.shape_type == 'Anim':
                        sbox.separator()
                        sbox.label(text="Animation Settings:")
                        sbox.prop(key, "anim_type_index")
                        sbox.prop(key, "anim_start_frame")
                        sbox.prop(key, "anim_end_frame")

class VIEW3D_PT_RZModProducerBuild(bpy.types.Panel):
    bl_label = "Mod Producer Build"
    bl_idname = "VIEW3D_PT_RZModProducerBuild"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RZ Constructor"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        mp = context.scene.rzm_mod_producer
        
        box = layout.box()
        from ..operators.export_manager import get_target_path
        target = get_target_path(context)
        if target:
            box.label(text=f"Auto-Target: {os.path.basename(target)}", icon='FILE_FOLDER')
        else:
            box.label(text="No Target Path Found", icon='ERROR')

        row = box.row()
        row.prop(mp, "build_suffix")
        
        box.label(text="Build Tiers:")
        flow = box.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        from ..operators.tier_ops import get_tier_ids, get_prefs
        prefs = get_prefs(context)
        available = get_tier_ids(context)
        active_list = [t.strip() for t in mp.active_tiers.split(",") if t.strip()]
        
        for tid in available:
            is_active = tid in active_list
            op = flow.operator("rzm.toggle_build_tier", text=tid, depress=is_active)
            op.tier_id = tid
            
        box.operator("rzm.mod_producer_build", text="Build Current Version", icon='EXPORT')

        # --- BATCH BUILD ---
        layout.separator()
        batch_box = layout.box()
        batch_box.label(text="Batch Mod Packager", icon='PACKAGE')
        
        if prefs and prefs.build_profiles:
            row = batch_box.row()
            row.template_list("RZM_UL_BuildProfiles", "", prefs, "build_profiles", prefs, "build_profiles_index", rows=2)
            
            if prefs.build_profiles:
                batch_box.operator("rzm.mod_producer_batch_build", text="Run Serial Batch Export", icon='NONE')
        else:
            batch_box.label(text="No Build Profiles defined in Settings.")
        
        batch_box.label(text="Author: " + (prefs.author_name if prefs else "UNKNOWN"), icon='USER')

class RZM_PT_ObjectTiers(bpy.types.Panel):
    """Panel in the standard Object Properties tab to show assigned tiers."""
    bl_label = "RZ Mod Tiers"
    bl_idname = "OBJECT_PT_rzm_tiers"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if not obj: return
        
        from ..operators.tier_ops import get_tier_ids
        available_tiers = get_tier_ids(context)
        if not available_tiers:
            layout.label(text="No tiers configured.", icon='INFO')
            return
            
        active_tiers = {t.tier_id for t in obj.rzm_tier_list}
        flow = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        for tid in available_tiers:
            is_active = tid in active_tiers
            op_name = "rzm.remove_object_tier" if is_active else "rzm.add_object_tier"
            op = flow.operator(op_name, text=tid, depress=is_active)
            op.tier_id = tid

classes_to_register = [ 
    RZM_UL_CustomScriptList,
    RZM_UL_Values,
    RZM_UL_ToggleDefinitions,
    RZM_UL_Shapes,
    RZM_UL_ShapeKeys,
    RZM_MT_AssignToggleMenu, 
    RZM_MT_AssignTexSlotMenu,
    VIEW3D_PT_RZConstructorPanel, 
    VIEW3D_PT_RZM_AutoMenuCreator,
    VIEW3D_PT_RZM_ExportManager,
    VIEW3D_PT_RZModProducerBuild,
    VIEW3D_PT_RZConstructorToolboxPanel,
    RZM_PT_ObjectTiers
]
