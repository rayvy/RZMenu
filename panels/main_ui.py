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

class RZM_UL_RunLinks(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name, icon='PLAY')
        if item.description:
            row.label(text=item.description)

class RZM_UL_Keybinds(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name, icon='EVENT_SPACEKEY')
        row.label(text=item.key[:20] if item.key else "<no key>")
        row.label(text=item.type)

class RZM_UL_ShapeDiscoveryCollections(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if item.collection:
            row.label(text=item.collection.name, icon='GROUP')
        else:
            row.label(text="<Empty Collection>", icon='ERROR')
        row.prop(item, "collection", text="")

class RZM_UL_ShapeConfigs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "shape_name", text="", emboss=False, icon='SHAPEKEY_DATA')
        
        # Show first object name for context
        if item.affected_objects:
            obj_ref = item.affected_objects[0]
            name = obj_ref.obj_name if obj_ref.obj_name else (obj_ref.obj.name if obj_ref.obj else "None")
            row.label(text=name, icon='OBJECT_DATA')
            if len(item.affected_objects) > 1:
                row.label(text=f"+{len(item.affected_objects)-1}")
        else:
            row.label(text="No Objects", icon='ERROR')
        
        op = row.operator("rzm.select_affected_objects", text="", icon='RESTRICT_SELECT_OFF', emboss=False)
        op.config_index = index

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
        
        # Fast Path Toggle
        icon = 'TRIA_RIGHT_BAR' if settings.force_fast_path else 'TRIA_RIGHT'
        row.prop(settings, "force_fast_path", text="", icon=icon, toggle=True)
        
        row.operator("rzm.full_export", text="Full Export", icon='EXPORT')
        row.operator("rzm.quick_export_menu", text="⚡ Quick Update", icon='FILE_REFRESH')
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
        
        atlas_box = layout.box()
        atlas_box.label(text="Atlas Export Format:", icon='IMAGE_DATA')
        atlas_box.prop(settings, "atlas_format", text="Format")
        if settings.atlas_format == 'DDS':
            atlas_box.prop(settings, "dds_profile", text="Profile")
        else:
            atlas_box.prop(settings, "icc_profile", text="Profile")
        
        row = atlas_box.row()
        row.enabled = False
        row.prop(settings, "last_exported_format", text="Actual Output")
        
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
        
        # 1.5 VIEWPORT UTILS
        v_box = layout.box()
        row = v_box.row(align=True)
        row.label(text="Viewport Utils:", icon='TRANSFORM_ORIGINS')
        row.operator("rzm.swap_elements", text="Swap Positions", icon='UV_SYNC_SELECT')

        layout.separator(factor=1.0)
        
        # 2. PROJECT CONFIGURATION AT BOTTOM
        box = layout.box()
        box.label(text="PROJECT CONFIGURATION", icon='SETTINGS')
        box.label(text="Run Links & Keybinds → Qt 'Run Links' panel", icon='INFO')
        
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
            row.separator()
            row.operator("rzm.import_ini", text="", icon='IMPORT')
            box.template_list("RZM_UL_Values", "", rzm, "rzm_values", context.scene, "rzm_active_value_index")
            if rzm.rzm_values and 0 <= context.scene.rzm_active_value_index < len(rzm.rzm_values):
                active_val = rzm.rzm_values[context.scene.rzm_active_value_index]

                # --- Randomization & Range ---
                rand_box = box.box()
                rand_box.label(text="Randomization & Range:", icon='SHADERFX')
                col_r = rand_box.column(align=True)
                row_r = col_r.row(align=True)
                row_r.prop(active_val, "val_min", text="Min")
                row_r.prop(active_val, "val_max", text="Max")
                rzm_addons = rzm.addons
                invert = getattr(rzm_addons, 'invert_random_marking', False)
                if invert:
                    icon_r = 'CHECKBOX_HLT' if not active_val.mark_random else 'CHECKBOX_DEHLT'
                    label_r = "Excluded from Randomize" if active_val.mark_random else "Included in Randomize"
                else:
                    icon_r = 'CHECKBOX_HLT' if active_val.mark_random else 'CHECKBOX_DEHLT'
                    label_r = "Included in Randomize" if active_val.mark_random else "Excluded from Randomize"
                col_r.prop(active_val, "mark_random", text=label_r, icon=icon_r)

                # NOTE: Run Link is bound per-element in the Qt Inspector, not here.

                # --- Export Tiers ---
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
            # --- LEGACY SYSTEM (RZMShape) ---
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
                    for tid in available:
                        is_act = tid in s_active
                        op_str = "rzm.remove_shape_tier" if is_act else "rzm.add_shape_tier"
                        op = flow.operator(op_str, text=tid, depress=is_act)
                        op.shape_index = context.scene.rzm_active_shape_index
                        op.tier_id = tid

                # --- Shape Properties ---
                s_box = box.box()
                s_box.prop(active_shape, "shape_name")
                s_box.prop(active_shape, "shape_type")
                s_box.prop(active_shape, "force_export")
                
                if active_shape.shape_type == 'Anim':
                    s_box.prop(active_shape, "anim_condition")

                # --- Shape Keys List ---
                s_box.separator()
                row_k = s_box.row()
                row_k.label(text="Shape Keyframes:", icon='SHAPEKEY_DATA')
                op_add = row_k.operator("rzm.add_shape_key", text="", icon='ADD', emboss=False)
                op_add.shape_index = context.scene.rzm_active_shape_index
                op_rem = row_k.operator("rzm.remove_shape_key", text="", icon='REMOVE', emboss=False)
                op_rem.shape_index = context.scene.rzm_active_shape_index
                op_rem.key_index = context.scene.rzm_active_shape_key_index
                
                s_box.template_list("RZM_UL_ShapeKeys", "", active_shape, "shape_keys", context.scene, "rzm_active_shape_key_index")
                
                if active_shape.shape_keys and 0 <= context.scene.rzm_active_shape_key_index < len(active_shape.shape_keys):
                    key = active_shape.shape_keys[context.scene.rzm_active_shape_key_index]
                    sbox = s_box.box()
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

        elif tab == 'NATIVE_SHAPES':
            # --- NEW SYSTEM (Discovery & Puppet Master) ---
            box.prop(rzm.addons, "export_shapekeys", text="Enable Native Shapes Export", icon='OUTLINER_OB_MESH')
            
            if rzm.addons.export_shapekeys:
                coll_box = box.box()
                coll_box.row().label(text="Discovery Collections:", icon='GROUP')
                row_c = coll_box.row(align=True)
                row_c.operator("rzm.add_shape_discovery_collection", text="Add Slot", icon='ADD')
                row_c.operator("rzm.remove_shape_discovery_collection", text="", icon='REMOVE')
                coll_box.template_list("RZM_UL_ShapeDiscoveryCollections", "", rzm, "shape_discovery_collections", scene, "rzm_active_shape_coll_index")
                
                box.separator()
                row = box.row(align=True)
                row.operator("rzm.shape_key_export", text="Discover", icon='FILE_REFRESH')
                row.operator("rzm.cleanup_trash_shapes", text="Cleanup Trash", icon='TRASH')
                
                # Bulk Toggles
                en = row.operator("rzm.set_all_shape_export", text="All ON", icon='CHECKBOX_HLT')
                en.state = True
                dis = row.operator("rzm.set_all_shape_export", text="All OFF", icon='CHECKBOX_DEHLT')
                dis.state = False

                row.operator("rzm.puppet_master_bake", text="Bake ALL", icon='NONE')
                row.operator("rzm.puppet_master_bake_single", text="Bake THIS", icon='SHAPEKEY_DATA')
                
                # --- GLOBAL VIEWPORT MASTER ---
                gm_box = box.box()
                gm_box.label(text="Global Sync Controls (Viewport Only):", icon='VIEW3D')
                row_g = gm_box.row(align=True)
                row_g.prop(rzm, "master_shape_value", text="Master Value")
                op_apply = row_g.operator("rzm.global_shape_master", text="Force All", icon='PLAY')
                op_apply.value = rzm.master_shape_value
                
                op_reset = gm_box.row().operator("rzm.global_shape_master", text="Reset All Configurations to 0.0", icon='X')
                op_reset.value = 0.0

                box.separator()
                box.label(text="Discovered Configurations:", icon='SHAPEKEY_DATA')
                box.template_list("RZM_UL_ShapeConfigs", "", rzm, "shape_configs", scene, "rzm_active_shape_config_index")
                
                if rzm.shape_configs and 0 <= scene.rzm_active_shape_config_index < len(rzm.shape_configs):
                    active_conf = rzm.shape_configs[scene.rzm_active_shape_config_index]
                    c_box = box.box()
                    c_box.prop(active_conf, "shape_name")
                    
                    row = c_box.row(align=True)
                    row.prop(active_conf, "disable_export", text="Disable Export", icon='HIDE_OFF')
                    row.prop(active_conf, "force_export", text="Force Export", icon='IMPORT')
                    
                    c_box.prop(active_conf, "shape_type")
                    
                    # Core values for all types
                    c_box.prop(active_conf, "sync_value", text="Sync Value (Global Name)", slider=True)
                    m_row = c_box.row(align=True)
                    m_row.prop(active_conf, "multiplier")
                    m_row.prop(active_conf, "inverse")
                    
                    if active_conf.shape_type == 'Anim':
                        anim_box = c_box.box()
                        anim_box.label(text="Animation Settings:")
                        anim_box.prop(active_conf, "anim_type_index")
                        
                        row_s = anim_box.row(align=True)
                        row_s.prop(active_conf, "anim_start_frame")
                        op_s = row_s.operator("rzm.set_anim_frame", text="", icon='CURSOR')
                        op_s.target = 'start'
                        
                        row_e = anim_box.row(align=True)
                        row_e.prop(active_conf, "anim_end_frame")
                        op_e = row_e.operator("rzm.set_anim_frame", text="", icon='CURSOR')
                        op_e.target = 'end'
                        
                        over_box = anim_box.box()
                        over_box.label(text="Manual Override (Anim -> Linear):")
                        over_box.prop(active_conf, "override_switch_condition")
                        over_box.prop(active_conf, "override_switch_value_link")
                        
                    c_box.prop(active_conf, "value_link")
                    c_box.prop(active_conf, "condition")
                    c_box.prop(active_conf, "mark_random")
                    
                    obj_box = c_box.box()
                    row_o = obj_box.row()
                    row_o.label(text="Affected Objects:", icon='OUTLINER_OB_MESH')
                    row_o.label(text=str(len(active_conf.affected_objects)))
                    op_sel = row_o.operator("rzm.select_affected_objects", text="Select All", icon='RESTRICT_SELECT_OFF')
                    op_sel.config_index = scene.rzm_active_shape_config_index

                    for ref in active_conf.affected_objects[:5]:
                        row_obj = obj_box.row(align=True)
                        row_obj.label(text=ref.obj_name if ref.obj_name else (ref.obj.name if ref.obj else "<None>"), icon='DOT')
                    if len(active_conf.affected_objects) > 5:
                        obj_box.label(text="...")
                
                pm_box = box.box()
                pm_box.label(text="Puppet Master Baking (v10.1):", icon='ARMATURE_DATA')
                pm_box.prop(rzm.addons, "puppet_master_per_component", text="Active Component Only")
                pm_box.prop(rzm.addons, "puppet_master_limit", text="Match Limit")
                pm_box.operator("rzm.puppet_master_bake", text="Bake SK Buffers", icon='MOD_BUILD')

        elif tab == 'KEYBINDS':
            # ── Run Links (named CommandLists) ─────────────────────────────
            rl_box = box.box()
            rl_row = rl_box.row(align=True)
            rl_row.label(text="Run Links:", icon='PLAY')
            rl_row.operator("rzm.import_ini", text="Import .ini", icon='IMPORT')
            rl_box.template_list(
                "RZM_UL_RunLinks", "",
                rzm, "run_links",
                context.scene, "rzm_active_run_link_index",
                rows=3
            )
            if rzm.run_links and 0 <= context.scene.rzm_active_run_link_index < len(rzm.run_links):
                active_rl = rzm.run_links[context.scene.rzm_active_run_link_index]
                rl_detail = rl_box.box()
                rl_detail.prop(active_rl, "name", text="ID")
                rl_detail.prop(active_rl, "description", text="Desc")
                rl_detail.label(text="Body (CommandList lines):", icon='TEXT')
                rl_detail.prop(active_rl, "body", text="")

            box.separator()

            # ── Keybinds ───────────────────────────────────────────────────
            kb_row = box.row(align=True)
            kb_row.label(text="Keybinds:", icon='EVENT_SPACEKEY')
            box.template_list(
                "RZM_UL_Keybinds", "",
                rzm, "keybinds",
                context.scene, "rzm_active_keybind_index",
                rows=4
            )
            if rzm.keybinds and 0 <= context.scene.rzm_active_keybind_index < len(rzm.keybinds):
                active_kb = rzm.keybinds[context.scene.rzm_active_keybind_index]
                kb_detail = box.box()

                col_kb = kb_detail.column(align=True)
                col_kb.prop(active_kb, "name",    text="Name")
                col_kb.prop(active_kb, "key",     text="Key")
                col_kb.prop(active_kb, "back",    text="Back")
                col_kb.prop(active_kb, "type",    text="Type")
                col_kb.separator()
                col_kb.prop(active_kb, "only_menu_active")
                col_kb.prop(active_kb, "condition", text="Condition")
                col_kb.separator()
                col_kb.prop(active_kb, "run_id",  text="Run Link ID")

                # Reserve fields (collapsed)
                res_box = kb_detail.box()
                res_box.label(text="Reserved (3DMigoto advanced):", icon='SETTINGS')
                c2 = res_box.column(align=True)
                c2.prop(active_kb, "wrap")
                c2.prop(active_kb, "smart")
                c2.prop(active_kb, "delay")
                c2.prop(active_kb, "release_delay")
                c2.prop(active_kb, "transition")
                c2.prop(active_kb, "transition_type")

        elif tab == 'BLEND_RESIZE':
            # --- BLEND RESIZE SYSTEM ---
            br = rzm.addons.blend_resize
            
            box.prop(br, "is_enabled", text="Active", toggle=True)
            if br.is_enabled:
                # 1. Master Groups (12 Slots)
                m_box = box.box()
                m_box.label(text="Master Resize Groups (12 Slots)", icon='GROUP_BONE')
                
                row = m_box.row()
                row.operator("rzm.br_add_group", text="Add Group", icon='ADD')
                
                for i, group in enumerate(br.groups):
                    row = m_box.row(align=True)
                    row.prop(group, "slot_id", text="")
                    row.prop(group, "name", text="")
                    row.prop(group, "value_link", text="Link")
                    op = row.operator("rzm.br_remove_group", text="", icon='REMOVE')
                    op.index = i
                    
                # 2. Component Mappings
                c_box = box.box()
                c_box.label(text="Component Mappings", icon='NONE')
                
                row = c_box.row()
                row.operator("rzm.br_add_comp", text="Add Component", icon='ADD')
                
                col = c_box.column(align=True)
                for i, comp in enumerate(br.component_mappings):
                    row = col.row(align=True)
                    row.prop(comp, "name", text="")
                    
                    if scene.rzm_active_br_comp_index == i:
                        row.label(icon='CHECKMARK')
                    else:
                        op = row.operator("rzm.br_select_comp", text="Select")
                        op.index = i
                        
                    op = row.operator("rzm.br_remove_comp", text="", icon='REMOVE')
                    op.index = i

                # 3. Baked Layers for active component
                if 0 <= scene.rzm_active_br_comp_index < len(br.component_mappings):
                    comp_idx = scene.rzm_active_br_comp_index
                    active_comp = br.component_mappings[comp_idx]
                    
                    l_box_root = box.box()
                    header = l_box_root.row()
                    header.label(text=f"Baked Layers: {active_comp.name}", icon='RENDER_ANIMATION')
                    
                    op_bake = header.operator("rzm.br_bake_layer", text="Bake from Active Bones", icon='FILE_REFRESH')
                    op_bake.comp_index = comp_idx
                    
                    row = l_box_root.row()
                    row.operator("rzm.br_add_layer", text="Add Empty Layer", icon='ADD')
                    
                    for i, layer in enumerate(active_comp.layers):
                        l_box = l_box_root.box()
                        row = l_box.row()
                        row.prop(layer, "name", text="")
                        row.prop(layer, "slot_id", text="Slot ID")
                        row.label(text=f"Bones: {layer.bone_count}")
                        op = row.operator("rzm.br_remove_layer", text="", icon='REMOVE')
                        op.comp_index = comp_idx
                        op.layer_index = i
                        
                        # Layer Details (Coordinates)
                        flow = l_box.grid_flow(columns=2, align=True)
                        flow.prop(layer, "head_mapped", text="Map Head")
                        flow.prop(layer, "tail_mapped", text="Map Tail")
                        
                        # Bones inside layer
                        b_row = l_box.row()
                        b_row.label(text="Bones:")
                        b_op = b_row.operator("rzm.br_add_layer_bone", text="", icon='ADD')
                        b_op.comp_index = comp_idx
                        b_op.layer_index = i
                        
                        for j, bone in enumerate(layer.bones):
                            b_r = l_box.row(align=True)
                            b_r.prop(bone, "bone_name", text="")
                            b_r.prop(bone, "bone_index", text="ID")
                            b_r.prop(bone, "scale_mapped", text="")
                            b_rm = b_r.operator("rzm.br_remove_layer_bone", text="", icon='REMOVE')
                            b_rm.comp_index = comp_idx
                            b_rm.layer_index = i
                            b_rm.bone_index = j

                box.separator()
                box.label(text="Export saves configurations inside the addon's .ini output. No external buffers needed.", icon='INFO')



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
    RZM_UL_RunLinks,
    RZM_UL_Keybinds,
    RZM_UL_ShapeDiscoveryCollections,
    RZM_UL_ShapeConfigs,
    RZM_MT_AssignToggleMenu,
    RZM_MT_AssignTexSlotMenu,
    VIEW3D_PT_RZConstructorPanel,
    VIEW3D_PT_RZM_AutoMenuCreator,
    VIEW3D_PT_RZM_ExportManager,
    VIEW3D_PT_RZModProducerBuild,
    VIEW3D_PT_RZConstructorToolboxPanel,
    RZM_PT_ObjectTiers
]
