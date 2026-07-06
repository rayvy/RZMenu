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
        rzm = context.scene.rzm
        game = rzm.game.selection if hasattr(rzm, "game") else "HonkaiStarRail"
        
        # Адаптивный список текстур в зависимости от игры
        game_mapping = {
            'GenshinImpact': ["Diffuse", "LightMap", "NormalMap", "ExtraMap"],
            'ArknightsEndfield': ["Diffuse", "NormalMap", "MaterialMap", "ExtraMap"],
            'WutheringWaves': ["Diffuse", "NormalMap", "MaterialMap", "ExtraMap"],
            'ZenlessZoneZero': ["Diffuse", "NormalMap", "LightMap", "MaterialMap", "GlowMap", "GlowGradient", "WengineFx", "ExtraMap"],
        }
        
        # По умолчанию (HSR или неизвестная игра) показываем стандартные слоты
        slots = game_mapping.get(game, ["Diffuse", "LightMap", "NormalMap", "MaterialMap", "ExtraMap"])
            
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
        row.prop(item, "toggle_start_index", text="Default")

class RZM_UL_Shapes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "shape_name", text="", emboss=False, icon='SHAPEKEY_DATA')
        row.prop(item, "shape_type", text="")
        row.label(text=f"SKC: {len(item.shape_keys)}")

class RZM_UL_ShapeKeys(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        shape = data
        if getattr(shape, "shape_type", "Linear") == "Anim":
            col = layout.column(align=True)
            row = col.row(align=True)
        else:
            row = layout.row(align=True)
        label = item.target_shape_name if item.target_shape_name else f"Legacy Key {item.key_name}"
        row.label(text=label, icon='SHAPEKEY_DATA')
        row.prop(item, "mode", text="")
        if item.mode == 'ADVANCED':
            row.prop(item, "input_range_min", text="From")
            row.prop(item, "input_range_max", text="To")
            row.prop(item, "multiplier", text="x")
        if getattr(shape, "shape_type", "Linear") == "Anim":
            timeline = col.row(align=True)
            timeline.prop(item, "anim_start_frame", text="Start", slider=True)
            timeline.prop(item, "anim_t2", text="Rise", slider=True)
            timeline.prop(item, "anim_t3", text="Fall", slider=True)
            timeline.prop(item, "anim_end_frame", text="End", slider=True)

class RZM_UL_ShapeClusterGroups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        lock_icon = 'LOCKED' if index == 0 else 'GROUP'
        row.prop(item, "group_name", text="", emboss=False, icon=lock_icon)
        if item.condition:
            row.label(text="cond", icon='FILTER')

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
        col.separator()
        col.prop(settings, "export_to_folder", text="Export to Folder")
        
        if settings.export_to_folder:
            col.prop(settings, "export_path", text="Path")
            col.prop(settings, "use_object_name", text="Use Object Name")
            capture_box.separator()
            row = capture_box.row(align=True)
            row.operator("rzm.capture_external", text="Capture External")
        else:
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

    def draw_namespace_identity(self, context, layout):
        scene = context.scene
        rzm = scene.rzm
        ns_box = layout.box()
        try:
            from ..operators.export_cache import get_cache
            from ..operators.export_manager import get_target_path
            from ..core.namespace_hash import namespace_from_context

            cache = get_cache()
            target_path = None
            try:
                target_path = get_target_path(context)
            except Exception:
                target_path = None
            namespace = namespace_from_context(context, export_cache=cache, target_path=target_path, create_seed=False)
            
            row = ns_box.row(align=True)
            row.label(text=f"namespace(WiP): {namespace.namespace}", icon='KEY_HLT')
            row.operator("rzm.copy_namespace", text="", icon='COPYDOWN')
            row.operator("rzm.reset_namespace_seed", text="", icon='FILE_REFRESH')
            
            row_edit = ns_box.row(align=True)
            addon_name = __package__.split(".")[0] if "." in __package__ else __package__
            prefs = context.preferences.addons.get(addon_name)
            
            row_edit.prop(rzm.meta_data, "character_name", text="Char")
            row_edit.prop(rzm.meta_data, "outfit_name", text="Skin")
            if prefs and prefs.preferences:
                row_edit.prop(prefs.preferences, "author_name", text="Author")
        except Exception as e:
            ns_box.label(text=f"Namespace unavailable: {e}", icon='ERROR')

    def draw(self, context):
        layout = self.layout
        # Namespace / Identity at the very top
        self.draw_namespace_identity(context, layout)
        layout.separator()
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

        # 3. SETUP & EXPORT BLOCKS
        self.draw_setup_block(context, layout)
        self.draw_export_management(context, layout)

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
        if scene.rzm_editor_mode == 'PRO':

            row.operator("rzm.autosetup_game", text="Auto-Setup Addon", icon='AUTO')
            row.operator("rzm.refresh_addon_data", text="Sync Data", icon='FILE_REFRESH')
        
        # Отображение путей целевого аддона
        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
            if hasattr(scene, "xxmi"):
                xxmi = scene.xxmi
                row_dump = box.row(align=True)
                row_dump.prop(xxmi, "dump_path", text="Dump")
                op_dump = row_dump.operator("rzm.select_folder", text="", icon='FILE_FOLDER')
                op_dump.target_type = 'xxmi_dump'
                
                row_dest = box.row(align=True)
                row_dest.prop(xxmi, "destination_path", text="Mod Folder")
                op_dest = row_dest.operator("rzm.select_folder", text="", icon='FILE_FOLDER')
                op_dest.target_type = 'xxmi_dest'
                
                box.separator()
                import_row = box.row(align=True)
                import_row.operator("rzm.quick_import", text="Quick Import", icon='IMPORT')
                import_row.operator("rzm.quick_asset_import", text="Quick Asset Import", icon='ASSET_MANAGER')
            else:
                box.label(text="XXMI Tools Not Active", icon='ERROR')
                
        elif game == 'ArknightsEndfield':
            if hasattr(scene, "efmi_tools_settings"):
                efmi = scene.efmi_tools_settings
                row_src = box.row(align=True)
                row_src.prop(efmi, "object_source_folder", text="Source")
                op_src = row_src.operator("rzm.select_folder", text="", icon='FILE_FOLDER')
                op_src.target_type = 'efmi_src'
                
                row_dest = box.row(align=True)
                row_dest.prop(efmi, "mod_output_folder", text="Output")
                op_dest = row_dest.operator("rzm.select_folder", text="", icon='FILE_FOLDER')
                op_dest.target_type = 'efmi_dest'
            else:
                box.label(text="EFMI Tools Not Active", icon='ERROR')

        elif game == 'WutheringWaves':
            if hasattr(scene, "wwmi_tools_settings"):
                wwmi = scene.wwmi_tools_settings
                row_src = box.row(align=True)
                row_src.prop(wwmi, "object_source_folder", text="Source")
                op_src = row_src.operator("rzm.select_folder", text="", icon='FILE_FOLDER')
                op_src.target_type = 'wwmi_src'
                
                row_dest = box.row(align=True)
                row_dest.prop(wwmi, "mod_output_folder", text="Output")
                op_dest = row_dest.operator("rzm.select_folder", text="", icon='FILE_FOLDER')
                op_dest.target_type = 'wwmi_dest'
            else:
                box.label(text="WWMI Tools Not Active", icon='ERROR')

    def draw_export_management(self, context, layout):
        scene = context.scene
        rzm = scene.rzm
        settings = rzm.export_settings
        if not settings: return
        
        box = layout.box()
        box.label(text="Export Management", icon='INFO')
        
        # Expose texture slots checkbox directly near the export buttons
        box.prop(rzm, "export_texture_slots", text="Export Texture Slots", icon='TEXTURE_DATA')


        
        is_pro = (scene.rzm_editor_mode == 'PRO')
        
        # --- PRIMARY EXPORT ---
        row = box.row(align=True)
        row.scale_y = 1.5
        
        if is_pro:
            # Fast Path Toggle next to Full Export
            icon = 'TRIA_RIGHT_BAR' if settings.force_fast_path else 'TRIA_RIGHT'
            row.prop(settings, "force_fast_path", text="", icon=icon, toggle=True)
            
        row.operator("rzm.full_export", text="Full Export", icon='EXPORT')
        
        # --- QUICK UPDATE GROUP ---
        q_col = box.column(align=True)
        q_row = q_col.row(align=True)
        q_row.scale_y = 1.5
        q_row.operator("rzm.quick_export_menu", text="⚡ Quick Update", icon='FILE_REFRESH')
        q_row.operator("rzm.quick_export_game_buffers", text="⚡ Game Buffers", icon='MESH_DATA')
        
        if is_pro:
            # Options immediately below the button
            opts_row = q_col.row(align=True)
            opts_row.prop(settings, "quick_update_resources", text="Resources", icon='IMAGE_DATA', toggle=True)
            opts_row.prop(settings, "quick_update_run_scripts", text="Scripts", icon='FILE_SCRIPT', toggle=True)
            
        # --- EXPORT VALIDATION / WARNINGS ---
        # Full validation scans the scene and XXMI metadata, so keep it explicit.
        # Running it from draw() makes Blender repeat the scan constantly.
        if is_pro:
            val_row = box.row(align=True)
            val_row.operator("rzm.select_problematic_objects", text="Check Export Warnings", icon='CHECKMARK')
        
        # --- EXPERIMENTAL OPTIMIZATION ---
        if is_pro:
            box.separator()
            exp_box = box.box()
            exp_box.label(text="Experimental Optimization", icon='MODIFIER')
            exp_box.operator("rzm.combined_optimization", text="Optimize .ini (Clean & Compress)", icon='MODIFIER')
            exp_row = exp_box.row(align=True)
            exp_row.operator("rzm.inquisitor_cleanup", text="Clean Up", icon='BRUSH_DATA')
            exp_row.operator("rzm.real_compression", text="Compress", icon='SEQ_STRIP_DUPLICATE')
            
            addon_name = __package__.split(".")[0] if "." in __package__ else __package__
            addon = context.preferences.addons.get(addon_name)
            if addon:
                exp_box.prop(addon.preferences, "create_backup", text="Create Backup")
            
            exp_box.separator()
            exp_box.prop(rzm.addons, "mirror_mesh", text="Mirror Mesh (X)", icon='MOD_MIRROR')
            exp_box.prop(rzm.addons, "export_vertex_debug", text="Export Vertex Evolution (.json)", icon='GHOST_ENABLED')




    def draw_captures_preview_ui(self, context, layout):
        # ... (implementation was likely already present or handled elsewhere) ...
        pass


    def draw_object_properties(self, context, layout):
        from ..core.utils import get_toggle_slot_occupancy, find_toggle_def
        scene = context.scene
        
        target_obj = context.active_object
        if not target_obj:
            layout.label(text="Select an object to see its properties.", icon='INFO')
            return

        if target_obj.type == 'CURVE':
            box = layout.box()
            box.label(text="RZ VFX Curve Settings", icon='CURVE_DATA')
            
            box.prop(target_obj, "rzm_curve_vfx_enabled", text="Enable Curve VFX")
            
            if target_obj.rzm_curve_vfx_enabled:
                # Section A: Texture & Particle Size
                gbox = box.box()
                gbox.label(text="Particle Geometry", icon='MESH_DATA')
                gcol = gbox.column(align=True)
                gcol.prop(target_obj, "rzm_curve_vfx_mesh_fx_type", text="Mesh Type")

                is_custom_mesh = (target_obj.rzm_curve_vfx_mesh_fx_type == "3")

                if is_custom_mesh:
                    gcol.separator()
                    gcol.label(text="Custom Mesh mode will be implemented someday —", icon='INFO')
                    gcol.label(text="though honestly, as the author, I have no intention")
                    gcol.label(text="to do so since I have no need for it myself.")
                    gcol.separator()
                    gcol.prop(target_obj, "rzm_curve_vfx_particle_size_start", text="Start Size Scale")
                    gcol.prop(target_obj, "rzm_curve_vfx_particle_size_end", text="End Size Scale")
                else:
                    # Standard size controls
                    tex_w = max(target_obj.rzm_curve_vfx_texture_size[0], 1)
                    gcol.prop(target_obj, "rzm_curve_vfx_particle_size_px", text="Particle Size (px)")
                    override_float = target_obj.rzm_curve_vfx_particle_size_base
                    if override_float > 0.0:
                        gcol.label(text=f"\u2192 float override: {override_float:.6f}")
                    else:
                        computed = target_obj.rzm_curve_vfx_particle_size_px / tex_w
                        gcol.label(text=f"\u2192 float: {computed:.6f}  ({target_obj.rzm_curve_vfx_particle_size_px}px / {tex_w})")
                    gcol.prop(target_obj, "rzm_curve_vfx_particle_size_base", text="Base Size")
                    gcol.prop(target_obj, "rzm_curve_vfx_particle_size_start", text="Start Size Scale")
                    gcol.prop(target_obj, "rzm_curve_vfx_particle_size_end", text="End Size Scale")
                    # UV info (read-only)
                    uv_off = target_obj.rzm_curve_vfx_uv_offset
                    uv_sc  = target_obj.rzm_curve_vfx_uv_scale
                    gcol.label(text=f"UV  Off=({uv_off[0]:.4f}, {uv_off[1]:.4f})  Scale=({uv_sc[0]:.4f}, {uv_sc[1]:.4f})", icon='IMAGE_DATA')

                # Section B: Path & Dispersion
                dbox = box.box()
                dbox.label(text="Path & Dispersion", icon='SPHERE')
                dcol = dbox.column(align=True)
                dcol.prop(target_obj, "rzm_curve_vfx_particle_count", text="Particle Count")
                dcol.prop(target_obj, "rzm_curve_vfx_dispersion_scale", text="Dispersion Scale")
                if scene.rzm.game.selection in ("GenshinImpact", "ZenlessZoneZero"):
                    dcol.separator()
                    dcol.prop(target_obj, "rzm_curve_vfx_color", text="ATTRIBUTE COLOR (Not the Diffuse Color!)")

                # Section C: Animation & Chaos
                abox = box.box()
                abox.label(text="Animation & Chaos", icon='TIME')
                acol = abox.column(align=True)
                acol.prop(target_obj, "rzm_curve_vfx_cycle_duration", text="Cycle Duration (sec)")
                acol.prop(target_obj, "rzm_curve_vfx_phase_randomness", text="Phase Randomness")
                acol.prop(target_obj, "rzm_curve_vfx_pos_randomness", text="Position Randomness")
                row = acol.row(align=True)
                row.prop(target_obj, "rzm_curve_vfx_size_rand_min", text="Size Rand Min")
                row.prop(target_obj, "rzm_curve_vfx_size_rand_max", text="Size Rand Max")
                acol.prop(target_obj, "rzm_curve_vfx_timeline_start_pos", text="Timeline Start")
                acol.prop(target_obj, "rzm_curve_vfx_timeline_mid_pos", text="Timeline Mid")
                acol.prop(target_obj, "rzm_curve_vfx_timeline_end_pos", text="Timeline End")
                acol.prop(target_obj, "rzm_curve_vfx_visibility_condition", text="Visibility Cond")

                # Section D: UV Settings
                uvbox = box.box()
                uvbox.label(text="UV Settings", icon='IMAGE_DATA')
                ucol = uvbox.column(align=True)

                size_col = ucol.column(align=True)
                size_col.label(text="UV PARTICLE SIZE")
                size_row = size_col.row(align=True)
                size_row.prop(target_obj, "rzm_curve_vfx_uv_scale", text="", index=0)
                size_row.prop(target_obj, "rzm_curve_vfx_uv_scale", text="", index=1)

                ucol.separator()
                ucol.prop(target_obj, "rzm_curve_vfx_animated_uv", text="Enable Animated UV")

                labels = ucol.row(align=True)
                labels.label(text="START")
                labels.label(text="MAIN")
                labels.label(text="END")

                uvrow = ucol.row(align=True)
                start_col = uvrow.column(align=True)
                start_col.enabled = target_obj.rzm_curve_vfx_animated_uv
                start_col.prop(target_obj, "rzm_curve_vfx_uv_dup_start", text="", index=0)
                start_col.prop(target_obj, "rzm_curve_vfx_uv_dup_start", text="", index=1)

                main_col = uvrow.column(align=True)
                main_col.prop(target_obj, "rzm_curve_vfx_uv_offset", text="", index=0)
                main_col.prop(target_obj, "rzm_curve_vfx_uv_offset", text="", index=1)

                end_col = uvrow.column(align=True)
                end_col.enabled = target_obj.rzm_curve_vfx_animated_uv
                end_col.prop(target_obj, "rzm_curve_vfx_uv_dup_end", text="", index=0)
                end_col.prop(target_obj, "rzm_curve_vfx_uv_dup_end", text="", index=1)

                _ou, _ov = target_obj.rzm_curve_vfx_uv_offset
                _sw, _sh = target_obj.rzm_curve_vfx_uv_scale
                _su, _sv = target_obj.rzm_curve_vfx_uv_dup_start
                _eu, _ev = target_obj.rzm_curve_vfx_uv_dup_end
                ucol.label(text=f"Offset=({_ou:.6f}, {_ov:.6f})  Scale=({_sw:.6f}, {_sh:.6f})")
                if target_obj.rzm_curve_vfx_animated_uv:
                    ucol.label(text=f"Start=({_su:.6f}, {_sv:.6f})  End=({_eu:.6f}, {_ev:.6f})")
                '''
                    uvcol.label(text=f"→ Float: Start=({_su/_tw:.4f}, {_sv/_th:.4f})  End=({_eu/_tw:.4f}, {_ev/_th:.4f})")
                
                uvbox.separator()
                
                # --- UV Calculator Sub-section ---
                ucol = uvbox.column(align=True)

                # Canvas size
                crow = ucol.row(align=True)
                crow.prop(target_obj, "rzm_curve_vfx_texture_size", text="", index=0)
                crow.label(text="×")
                crow.prop(target_obj, "rzm_curve_vfx_texture_size", text="", index=1)
                crow.label(text="px")

                # Sprite offset in atlas
                orow = ucol.row(align=True)
                orow.label(text="Offset:")
                orow.label(text="px (U, V)")

                # Sprite size in atlas
                srow = ucol.row(align=True)
                srow.label(text="×")
                srow.label(text="px")

                # Live result preview
                _tw = max(target_obj.rzm_curve_vfx_texture_size[0], 1)
                _th = max(target_obj.rzm_curve_vfx_texture_size[1], 1)
                ucol.label(text=f"→ Off=({_ou/_tw:.4f}, {_ov/_th:.4f})  Scale=({_sw/_tw:.4f}, {_sh/_th:.4f})")

                '''

                # Section E: Technical Weights
                wbox = box.box()
                wbox.label(text="Technical Weights", icon='MOD_VERTEX_WEIGHT')
                wbox.prop(target_obj, "rzm_curve_vfx_weight_reference", text="Reference Mesh")

                ref_mesh = target_obj.rzm_curve_vfx_weight_reference
                if ref_mesh:
                    wbox.label(text="Bake Mode: Sampling weights from " + ref_mesh.name, icon='INFO')
                else:
                    col_manual = wbox.column()
                    col_manual.prop(target_obj, "rzm_curve_vfx_weight_indices", index=0, text="Bone Index")

                # Section G: Utilities
                ubox = box.box()
                ubox.label(text="Utilities", icon='TOOL_SETTINGS')
                ubox.operator("rzm.toggle_curve_bevel",
                              text="Toggle Bevel Preview (0.01 \u2194 0)", icon='CURVE_DATA')

                ubox.separator()
                ubox.label(text="Preview", icon='RESTRICT_VIEW_OFF')
                
                op_row = ubox.row(align=True)
                op_row.operator("rzm.apply_vfx_preview",
                                text="Apply Preview", icon='NODETREE')
                op_row.operator("rzm.remove_vfx_preview",
                                text="Remove Preview", icon='X')

                # Validation
                box.separator()
                box.operator("rzm.validate_curve_vfx", text="Validate Curve VFX", icon='CHECKMARK')
        # --- MOD PRODUCER TIERS ---
        if context.scene.rzm_editor_mode == 'PRO':
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
                if toggle_def:
                    header.prop(toggle_def, "toggle_start_index", text="Default")
                op_sel_all = header.operator("rzm.select_objects_with_toggle", text="", icon='SELECT_SET')
                op_sel_all.toggle_name = base_name
                op_dec = header.operator("rzm.resize_object_toggle_bitmask", text="", icon='REMOVE', emboss=False)
                op_dec.toggle_name = key
                op_dec.delta = -1
                op_inc = header.operator("rzm.resize_object_toggle_bitmask", text="", icon='ADD', emboss=False)
                op_inc.toggle_name = key
                op_inc.delta = 1
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
        row.operator("rzm.sync_tex_slots_to_material", text="", icon='FILE_REFRESH')
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
                init_key = f"rzm.TexInitAttach.{slot_id}"
                
                # Используем колонку для группировки слота и его условия
                slot_col = box.column(align=True)
                row = slot_col.row(align=True)
                
                # Метка слота
                row.label(text=display_name, icon='IMAGE_DATA')
                
                # Поле пути к текстуре
                row.prop(target_obj, f'["{key}"]', text="")
                init_icon = 'CHECKBOX_HLT' if target_obj.get(init_key, False) else 'CHECKBOX_DEHLT'
                op_init = row.operator("rzm.toggle_object_tex_init_attach", text="", icon=init_icon, emboss=False)
                op_init.prop_key = key
                
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
        
        box.prop(target_obj, "DrawCondition", text="Draw Condition")
        if target_obj.type == 'MESH':
            box.prop(target_obj, "rzm_export_vg_anchor", text="VG Export Anchor")
        
        # List of active Custom Draws
        custom_draw_keys = sorted([key for key in target_obj.keys() if key.startswith("CustomDraw.")])
        if custom_draw_keys:
            col = box.column(align=True)
            for key in custom_draw_keys:
                r = col.row(align=True)
                r.label(text=key.replace("CustomDraw.", ""), icon='DOT')
                op = r.operator("rzm.remove_custom_draw", text="", icon='X', emboss=False)
                op.prop_name = key

        # --- HOVER DETECT ---
        hover_box = layout.box()
        hover_box.label(text="Hover / Click Detect", icon='RESTRICT_SELECT_OFF')

        current_mode = target_obj.get("rzm.Hover", 0)

        # Mode descriptions
        HOVER_MODES = [
            (0, "None",              "No hover/click detection",                     'X'),
            (1, "Collider",          "Register in ObjectMap only, no draw changes", 'MESH_CIRCLE'),
            (2, "Hide When Hovered", "Hidden when cursor is over this object",      'HIDE_ON'),
            (3, "Appear When Hov.", "Visible only when cursor is over this object", 'HIDE_OFF'),
        ]

        CLICK_MODES = [
            (4, "Click Collider",    "Register in ObjectMap on click, no draw changes", 'MESH_CIRCLE'),
            (5, "Hide When Clicked", "Hidden when object is clicked",                         'HIDE_ON'),
            (6, "Appear When Click", "Visible only when object is clicked",                   'HIDE_OFF'),
        ]

        JIGGLE_MODES = [
            (7, "Jiggle Collider", "Physics jiggle collider — activates jiggle shader for the component", 'PHYSICS'),
        ]

        row0 = hover_box.row(align=True)
        is_none_active = (current_mode == 0 or "rzm.Hover" not in target_obj)
        op = row0.operator("rzm.set_hover_mode", text="None", icon='X', depress=is_none_active)
        op.mode = 0

        hover_box.label(text="Hover Modes:")
        row1 = hover_box.row(align=True)
        for mode_val, label, tooltip, icon in HOVER_MODES[1:]:
            is_active = (current_mode == mode_val)
            op = row1.operator(
                "rzm.set_hover_mode",
                text=label,
                icon=icon,
                depress=is_active,
            )
            op.mode = mode_val

        hover_box.label(text="Click Modes:")
        row2 = hover_box.row(align=True)
        for mode_val, label, tooltip, icon in CLICK_MODES:
            is_active = (current_mode == mode_val)
            op = row2.operator(
                "rzm.set_hover_mode",
                text=label,
                icon=icon,
                depress=is_active,
            )
            op.mode = mode_val

        hover_box.label(text="Physics Modes:")
        row3 = hover_box.row(align=True)
        for mode_val, label, tooltip, icon in JIGGLE_MODES:
            is_active = (current_mode == mode_val)
            op = row3.operator(
                "rzm.set_hover_mode",
                text=label,
                icon=icon,
                depress=is_active,
            )
            op.mode = mode_val

        # Info line for current active mode
        if current_mode == 1:
            # Show the firstIndex hint for Collider
            hint_box = hover_box.box()
            hint_box.alert = False
            hint_col = hint_box.column(align=True)
            hint_col.label(text="Collider: registers in ObjectMap only.", icon='INFO')
            hint_col.label(text="No draw suppression or wrapping applied.")
            hint_col.label(text="Use $Detected == <firstIndex> in other modules.")
        elif current_mode == 2:
            hover_box.label(text="draw suppressed when $Detected == firstIndex", icon='INFO')
        elif current_mode == 3:
            hover_box.label(text="drawn only when $Detected == firstIndex", icon='INFO')
        elif current_mode == 4:
            hint_box = hover_box.box()
            hint_box.alert = False
            hint_col = hint_box.column(align=True)
            hint_col.label(text="Click Collider: registers in ObjectMap on click.", icon='INFO')
            hint_col.label(text="No draw suppression or wrapping applied.")
            hint_col.label(text="Use $Detected == <firstIndex> in other modules.")
        elif current_mode == 5:
            hover_box.label(text="draw suppressed when clicked ($Detected == firstIndex)", icon='INFO')
        elif current_mode == 6:
            hover_box.label(text="drawn only when clicked ($Detected == firstIndex)", icon='INFO')
        elif current_mode == 7:
            hint_box = hover_box.box()
            hint_box.alert = False
            hint_col = hint_box.column(align=True)
            hint_col.label(text="Jiggle Collider: activates jiggle physics for component.", icon='PHYSICS')
            hint_col.label(text="Triggers CustomShaderRZMJiggle when $Detected == firstIndex.")
            hint_col.label(text="Phase 2: per-object physics params below.")

        # --- JIGGLE CONFIG (Phase 2 — shown when mode == 7) ---
        if current_mode == 7:
            jbox = hover_box.box()
            jbox.label(text="Jiggle Physics Config", icon='PHYSICS')
            jcol = jbox.column(align=True)

            jcol.label(text="[ Phase 2 — not active in export yet ]", icon='INFO')
            jcol.separator()

            # Grab physics
            gbox = jbox.box()
            gbox.label(text="Grab", icon='RESTRICT_SELECT_OFF')
            gcol = gbox.column(align=True)
            gcol.prop(target_obj, '["rzm.Jiggle.radius"]',      text="Radius")
            gcol.prop(target_obj, '["rzm.Jiggle.strength"]',    text="Strength")
            gcol.prop(target_obj, '["rzm.Jiggle.falloff"]',     text="Falloff Power")
            gcol.prop(target_obj, '["rzm.Jiggle.drag_scale"]',  text="Drag Scale")
            gcol.prop(target_obj, '["rzm.Jiggle.grab_damp"]',   text="Grab Damping")
            gcol.prop(target_obj, '["rzm.Jiggle.grab_spring"]', text="Grab Spring")

            # Release physics
            rbox = jbox.box()
            rbox.label(text="Release", icon='LOOP_BACK')
            rcol = rbox.column(align=True)
            rcol.prop(target_obj, '["rzm.Jiggle.rel_damp"]',   text="Release Damping")
            rcol.prop(target_obj, '["rzm.Jiggle.rel_spring"]', text="Release Spring")
            rcol.prop(target_obj, '["rzm.Jiggle.rel_kick"]',   text="Release Kick")

            # Polish
            pbox = jbox.box()
            pbox.label(text="Polish", icon='SMOOTHCURVE')
            pcol = pbox.column(align=True)
            pcol.prop(target_obj, '["rzm.Jiggle.max_offset"]',     text="Max Offset")
            pcol.prop(target_obj, '["rzm.Jiggle.target_follow"]',  text="Target Follow")
            pcol.prop(target_obj, '["rzm.Jiggle.mouse_y"]',        text="Mouse Y Dir (+1/-1)")

        # --- ANTICOLLIDER MASK (shown for MESH objects always) ---
        if target_obj.type == 'MESH':
            mbox = layout.box()
            mbox.label(text="Jiggle Anticollider Mask", icon='MOD_VERTEX_WEIGHT')
            
            # Info block
            mesh = target_obj.data
            vg_exists = target_obj.vertex_groups.get("MASK ANTICOLLIDER") is not None
            attr_exists = mesh.attributes.get("rzm_anticollider_mask") is not None
            
            info_col = mbox.column(align=True)
            vg_status = "Exists" if vg_exists else "Missing"
            attr_status = "Exists" if attr_exists else "Missing"
            
            row_vg = info_col.row()
            row_vg.label(text=f"Group 'MASK ANTICOLLIDER': {vg_status}")
            if not vg_exists:
                row_vg.alert = True
                
            row_attr = info_col.row()
            row_attr.label(text=f"Attribute 'rzm_anticollider_mask': {attr_status}")
            if not attr_exists:
                row_attr.alert = True
                
            mbox.separator()
            
            # Action Buttons
            grid = mbox.column(align=True)
            grid.operator("rzm.save_mask_attribute", text="Bake to Mesh Attribute", icon='FILE_TICK')
            grid.operator("rzm.restore_mask_vertex_group", text="Restore to Vertex Group", icon='LOOP_BACK')
            grid.operator("rzm.fill_mask_weights", text="Fill Mask (1.0)", icon='BRUSH_DATA')
            
            row = mbox.row(align=True)
            row.operator("rzm.delete_mask_vertex_group", text="Delete VG", icon='TRASH')
            row.operator("rzm.delete_mask_mesh_attribute", text="Delete Attribute", icon='X')


# ... (Остальные панели без изменений) ...

class VIEW3D_PT_RZM_AutoMenuCreator(bpy.types.Panel):
    bl_label = "Auto Menu Creator"
    bl_idname = "VIEW3D_PT_rzm_auto_menu_creator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_parent_id = "VIEW3D_PT_rz_constructor_panel"
    bl_order = 98 

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_editor_mode == 'PRO'

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

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_editor_mode == 'PRO'

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
        
        box.separator()
        box.prop(rzm.addons, "export_vertex_debug", text="Export Vertex Debug (.json)", icon='GHOST_ENABLED')



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

class RZM_UL_CM_ComponentList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "blend_copy_enabled", text="")
            row.label(text=item.name if item.name else "<Empty Name>", icon='OUTLINER_OB_MESH')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OUTLINER_OB_MESH')

class RZM_UL_CM_PartList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "enabled", text="")
            row.label(text=item.name if item.name else "<Empty Name>", icon='MESH_DATA')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='MESH_DATA')


def draw_export_cache_info_ui(context, layout):
    box = layout.box()
    box.label(text="RZM Export Cache (Experimental)", icon='FILE_FOLDER')

    try:
        from ..operators.export_cache import get_cache
        cache = get_cache()
    except Exception as e:
        box.label(text=f"Cache read failed: {e}", icon='ERROR')
        return

    if not cache:
        box.label(text="No cache available. Run Full Export or Game Buffers first.", icon='INFO')
        row = box.row()
        row.enabled = False
        row.operator("rzm.export_transform_segment", text="Export DISABLED Transform INI", icon='EXPORT')
        return

    source = cache.get("source", "<unknown>")
    mod_name = cache.get("mod_name", "<unknown>")
    components = cache.get("components", {}) or {}
    object_count = sum(len((comp or {}).get("objects", []) or []) for comp in components.values())

    grid = box.grid_flow(columns=2, align=True)
    grid.label(text="Source:")
    grid.label(text=str(source))
    grid.label(text="Mod:")
    grid.label(text=str(mod_name))
    grid.label(text="Components:")
    grid.label(text=str(len(components)))
    grid.label(text="Objects:")
    grid.label(text=str(object_count))

    try:
        from ..operators.export_manager import get_target_path
        from ..core.namespace_hash import namespace_from_context

        try:
            target_path = get_target_path(context)
        except Exception:
            target_path = None
        namespace = namespace_from_context(context, export_cache=cache, target_path=target_path, create_seed=False)
        row = box.row(align=True)
        row.label(text=f"Namespace: {namespace.namespace}", icon='KEY_HLT')
        row.operator("rzm.copy_namespace", text="", icon='COPYDOWN')
        box.label(text=f"Character: {namespace.character_name} | Skin: {namespace.skin_name}", icon='INFO')
    except Exception as e:
        box.label(text=f"Namespace unavailable: {e}", icon='ERROR')

    box.operator("rzm.export_transform_segment", text="Export DISABLED Transform INI", icon='EXPORT')

    try:
        from ..core.ini_validation import validate_export_cache

        basic = validate_export_cache(cache)
        strict = validate_export_cache(cache, require_vertex_maps=True)
        if basic.ok:
            box.label(text="Basic cache validation: OK", icon='CHECKMARK')
        else:
            warn = box.box()
            warn.alert = True
            warn.label(text="Basic cache validation failed", icon='ERROR')
            for issue in basic.errors[:4]:
                warn.label(text=f"{issue.code}: {issue.message[:80]}")

        if strict.ok:
            box.label(text="Shape vertex maps: OK", icon='CHECKMARK')
        else:
            warn = box.box()
            warn.label(text="Shape vertex-map warnings", icon='ERROR')
            for issue in strict.errors[:5]:
                warn.label(text=f"{issue.code}: {issue.message[:80]}")
    except Exception as e:
        box.label(text=f"Validation unavailable: {e}", icon='ERROR')

    details = box.box()
    details.label(text="Component Ranges", icon='OUTLINER_OB_MESH')
    if not components:
        details.label(text="No components in cache.", icon='INFO')
        return

    for comp_index, (comp_name, comp_data) in enumerate(components.items()):
        if comp_index >= 6:
            details.label(text=f"... {len(components) - comp_index} more component(s)")
            break
        comp_data = comp_data or {}
        objects = comp_data.get("objects", []) or []
        cbox = details.box()
        cbox.label(
            text=f"{comp_name or '[Main]'} | verts={comp_data.get('n_verts', '?')} | objects={len(objects)}",
            icon='MESH_DATA',
        )
        for obj_index, obj_data in enumerate(objects[:4]):
            vb_offset = obj_data.get("vb_offset", "?")
            vb_count = obj_data.get("vb_count", "?")
            has_map = bool(obj_data.get("vertex_map"))
            icon = 'CHECKMARK' if has_map else 'ERROR'
            cbox.label(
                text=f"[{vb_offset} + {vb_count}] {obj_data.get('name', '<unnamed>')}",
                icon=icon,
            )
        if len(objects) > 4:
            cbox.label(text=f"... {len(objects) - 4} more object(s)")



def draw_component_manager_ui(context, layout):
    scene = context.scene
    rzm = scene.rzm
    cm = rzm.component_manager
    
    layout.label(text="Component Manager", icon='OUTLINER_OB_MESH')
    header_row = layout.row(align=True)
    header_row.prop(cm, "dump_path", text="")
    header_row.operator("rzm.cm_update_from_dump", text="Update", icon='FILE_REFRESH')
    
    row = layout.row(align=True)
    row.prop(rzm.addons, "frame_trace", text="Frame Trace Active", toggle=True)
    if rzm.addons.frame_trace:
        box_ft = layout.box()
        box_ft.prop(rzm.addons, "frame_trace_speed", text="Speed")
        box_ft.prop(rzm.addons, "frame_trace_length", text="Length (Copies)")
        box_ft.prop(rzm.addons, "frame_trace_threshold", text="Distance Threshold")
        
        # Группа цветов градиента
        col_box = box_ft.box()
        col_box.label(text="Trace Gradient Colors", icon='COLOR')
        col_box.prop(rzm.addons, "frame_trace_color_start", text="Start")
        col_box.prop(rzm.addons, "frame_trace_color_mid", text="Mid")
        col_box.prop(rzm.addons, "frame_trace_color_end", text="End")
    
    layout.separator()
    layout.row().prop(cm, "active_tab", expand=True)
    
    if cm.active_tab == 'BLEND_COPY':
        b_box = layout.box()
        b_box.label(text="BlendCopy (Components)", icon='MOD_BOOLEAN')
        b_box.template_list("RZM_UL_CM_ComponentList", "", cm, "components", scene, "rzm_cm_active_comp_index", rows=5)
        
    elif cm.active_tab == 'TEST_SUBCOMP':
        t_box = layout.box()
        t_box.label(text="TestSubComp (SubComponents)", icon='GROUP_VERTEX')
        
        for i, comp in enumerate(cm.components):
            c_box = t_box.box()
            c_box.label(text=f"Component: {comp.name if comp.name else '<Empty>'}", icon='OUTLINER_OB_MESH')
            if comp.parts:
                for part in comp.parts:
                    row = c_box.row(align=True)
                    row.prop(part, "enabled", text="")
                    row.label(text=part.name, icon='MESH_DATA')
            else:
                c_box.label(text="No subcomponents", icon='INFO')

    elif cm.active_tab == 'CACHE_INFO':
        draw_export_cache_info_ui(context, layout)

def draw_material_transfer_ui(context, layout):
    scene = context.scene
    cm = scene.rzm.component_manager
    
    if not cm.components:
        layout.label(text="No components loaded in Component Manager.", icon='INFO')
        return
        
    layout.label(text="Assign subcomponent geometry to draw on targets:", icon='NONE')
    
    for comp in cm.components:
        # We only show components that have parts/subcomponents
        if not comp.parts:
            continue
            
        comp_box = layout.box()
        comp_box.label(text=f"Component: {comp.name}", icon='OUTLINER_OB_MESH')
        
        for part in comp.parts:
            part_box = comp_box.box()
            row = part_box.row()
            row.label(text=f"Target: {part.name}", icon='MESH_DATA')
            
            # Button to add donor
            add_op = row.operator("rzm.add_transfer_donor", text="Add Donor", icon='ADD')
            add_op.target_comp = comp.name
            add_op.target_part = part.name
            
            # Draw list of donors
            if part.donors:
                col = part_box.column(align=True)
                for idx, donor in enumerate(part.donors):
                    d_row = col.row(align=True)
                    d_row.label(text=f"↳ Donor: {donor.component_name} -> {donor.part_name}", icon='LINKED')
                    rem_op = d_row.operator("rzm.remove_transfer_donor", text="", icon='TRASH')
                    rem_op.target_comp = comp.name
                    rem_op.target_part = part.name
                    rem_op.donor_index = idx

def draw_shape_keys_simple_ui(context, layout):
    scene = context.scene
    rzm = scene.rzm

    sources_box = layout.box()
    sources_row = sources_box.row(align=True)
    sources_row.label(text="Sources:", icon='GROUP')
    sources_row.operator("rzm.add_shape_discovery_collection", text="", icon='ADD')
    sources_row.operator("rzm.remove_shape_discovery_collection", text="", icon='REMOVE')
    sources_row.operator("rzm.shape_key_export", text="Discover", icon='FILE_REFRESH')
    sources_box.template_list(
        "RZM_UL_ShapeDiscoveryCollections", "",
        rzm, "shape_discovery_collections",
        scene, "rzm_active_shape_coll_index",
        rows=3
    )

    manager_box = layout.box()
    manager_header = manager_box.row(align=True)
    manager_header.label(text="Clusters:", icon='LINKED')
    manager_header.operator("rzm.add_shape", text="", icon='ADD')
    rem_shape = manager_header.operator("rzm.remove_shape", text="", icon='REMOVE')
    rem_shape.shape_index = scene.rzm_active_shape_index
    sync_shape = manager_header.operator("rzm.sync_shape_cluster", text="Sync", icon='FILE_REFRESH')
    sync_shape.shape_index = scene.rzm_active_shape_index
    manager_box.template_list(
        "RZM_UL_Shapes", "",
        rzm, "shapes",
        scene, "rzm_active_shape_index",
        rows=5
    )

    if not (rzm.shapes and 0 <= scene.rzm_active_shape_index < len(rzm.shapes)):
        available_box = layout.box()
        available_box.label(text="Create a cluster first, then add ShapeKey members.", icon='INFO')
        return

    active_shape = rzm.shapes[scene.rzm_active_shape_index]
    has_groups = len(active_shape.groups) > 0

    details = manager_box.box()
    row = details.row(align=True)
    row.label(text=f"Variable: {active_shape.shape_name}", icon='DOT')
    row.prop(active_shape, "use_multi_groups", text="Advanced Groups Configuration")

    active_group = active_shape.groups[active_shape.active_group_index] if (
        has_groups and 0 <= active_shape.active_group_index < len(active_shape.groups)
    ) else None

    if active_shape.use_multi_groups:
        group_box = details.box()
        group_header = group_box.row(align=True)
        group_header.label(text="Groups:", icon='GROUP')
        if has_groups:
            group_header.operator("rzm.add_shape_cluster_group", text="", icon='ADD')
            group_header.operator("rzm.remove_shape_cluster_group", text="", icon='REMOVE')
        else:
            group_header.operator("rzm.ensure_shape_default_group", text="Initialize", icon='ADD')

        if has_groups:
            group_buttons = group_box.row(align=True)
            for group_index, group in enumerate(active_shape.groups):
                label = group.group_name if group.group_name else f"Group {group_index}"
                op = group_buttons.operator(
                    "rzm.set_shape_cluster_group",
                    text=label,
                    depress=(group_index == active_shape.active_group_index)
                )
                op.group_index = group_index

            if active_group:
                row = group_box.row(align=True)
                row.prop(active_group, "group_name", text="Name")
                row.prop(active_group, "preview_value", text="Preview", slider=True)
                group_box.prop(active_group, "condition", text="Condition")
                group_box.prop(active_group, "fallback_value", text="Fallback")
                if active_shape.shape_type == 'Anim':
                    over = group_box.box()
                    over.label(text="Anim Override:", icon='DRIVER')
                    over.prop(active_group, "override_switch_condition", text="Condition")
                    over.prop(active_group, "override_switch_value_link", text="Value Link")
    else:
        if active_group:
            details.prop(active_group, "preview_value", text="Preview", slider=True)

    member_box = details.box()
    member_header = member_box.row(align=True)
    member_header.label(text="Members:", icon='SHAPEKEY_DATA')
    member_header.prop_search(scene, "rzm_shape_member_candidate", rzm, "shape_configs", text="")
    member_header.operator("rzm.remove_shape_cluster_member", text="", icon='REMOVE')
    member_box.template_list(
        "RZM_UL_ShapeKeys", "",
        active_shape, "shape_keys",
        scene, "rzm_active_shape_key_index",
        rows=4
    )

    if (
        active_shape.use_multi_groups
        and has_groups
        and active_shape.shape_keys
        and 0 <= scene.rzm_active_shape_key_index < len(active_shape.shape_keys)
    ):
        member = active_shape.shape_keys[scene.rzm_active_shape_key_index]
        edit = member_box.box()
        edit.label(text=f"Target: {member.target_shape_name if member.target_shape_name else '<empty>'}", icon='DOT')
        group_row = edit.row(align=True)
        group_row.label(text="Groups:")
        raw_groups = {
            part.strip()
            for part in str(getattr(member, "group_indices", "") or "").split(",")
            if part.strip()
        }
        if not raw_groups:
            raw_groups = {str(member.group_index)}
        for group_index, group in enumerate(active_shape.groups):
            op = group_row.operator(
                "rzm.toggle_shape_member_group",
                text=group.group_name if group.group_name else f"G{group_index}",
                depress=(str(group_index) in raw_groups)
            )
            op.group_index = group_index

    available_box = layout.box()
    available_header = available_box.row(align=True)
    icon = 'TRIA_DOWN' if scene.rzm_show_available_shape_keys else 'TRIA_RIGHT'
    available_header.prop(scene, "rzm_show_available_shape_keys", text="Available Shape Keys", icon=icon, emboss=False)
    available_header.operator("rzm.import_shape_key_config", text="", icon='IMPORT')
    available_header.operator("rzm.export_shape_key_config", text="", icon='EXPORT')

    if scene.rzm_show_available_shape_keys:
        available_box.template_list(
            "RZM_UL_ShapeConfigs", "",
            rzm, "shape_configs",
            scene, "rzm_active_shape_config_index",
            rows=6
        )
        if rzm.shape_configs and 0 <= scene.rzm_active_shape_config_index < len(rzm.shape_configs):
            active_conf = rzm.shape_configs[scene.rzm_active_shape_config_index]
            selected_row = available_box.row(align=True)
            selected_row.label(text=active_conf.shape_name, icon='DOT')
            selected_row.prop(active_conf, "shape_type", text="")
            select_op = selected_row.operator("rzm.select_affected_objects", text="", icon='RESTRICT_SELECT_OFF')
            select_op.config_index = scene.rzm_active_shape_config_index

def draw_toolbox_content(self, context):
    layout = self.layout
    scene = context.scene
    rzm = scene.rzm
    
    # ─── TAB SELECTION AT THE VERY TOP ───
    row_tab = layout.row(align=True)
    row_tab.prop(scene, "rzm_toolbox_mode", expand=True)
    
    layout.separator()
    
    if scene.rzm_toolbox_mode == 'SHAITAN':
        from ..shaitan_toolbox.ui import draw_shaitan_toolbox
        draw_shaitan_toolbox(self, context, layout)
        return
    elif scene.rzm_toolbox_mode != 'TEXWORKS':
        # 1. ALWAYS SHOW MESH PROPERTIES AT TOP
        VIEW3D_PT_RZConstructorPanel.draw_object_properties(self, context, layout)
        return

    layout.separator(factor=1.0)

    section_row = layout.row(align=True)
    section_row.prop(scene, "rzm_configs_tab", expand=True)

    if scene.rzm_configs_tab == 'COMPONENTS':
        box = layout.box()
        draw_component_manager_ui(context, box)
        return

    if scene.rzm_configs_tab == 'MATERIAL_TRANSFER':
        box = layout.box()
        draw_material_transfer_ui(context, box)
        return

    if scene.rzm_configs_tab == 'TEXWORKS':
        box = layout.box()
        box.label(text="TEXWORKS", icon='TEXTURE')
        from .ui_debug_panel import VIEW3D_PT_RZConstructorDebugPanel
        VIEW3D_PT_RZConstructorDebugPanel.draw_tex_works_config(self, box, rzm, context)
        return

    layout.separator(factor=1.0)

    # 2. PROJECT CONFIGURATION
    box = layout.box()
    # box.label(text="PROJECT CONFIGURATION", icon='SETTINGS')
    # box.label(text="Run Links & Keybinds → Qt 'Run Links' panel", icon='INFO')
    
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

    elif tab in {'SHAPES', 'NATIVE_SHAPES'}:
        # --- Merged ShapeKey manager + SKC system ---
        legacy_ui = getattr(rzm.addons, "legacy_sk_ui", False)
        if not legacy_ui:
            draw_shape_keys_simple_ui(context, box)
            return

        box.row(align=True).prop(scene, "rzm_shape_keys_ui_mode", expand=True)
        if scene.rzm_shape_keys_ui_mode == 'SIMPLE':
            draw_shape_keys_simple_ui(context, box)
            return

        box.prop(rzm.addons, "export_shapekeys", text="Enable Shape Keys Export", icon='OUTLINER_OB_MESH')
        if rzm.addons.export_shapekeys:

            manager_box = box.box()
            manager_box.label(text="Shape Managers / Clusters:", icon='SHAPEKEY_DATA')
            row_m = manager_box.row(align=True)
            row_m.operator("rzm.add_shape", text="Add Manager", icon='ADD')
            rem_shape = row_m.operator("rzm.remove_shape", text="", icon='REMOVE')
            rem_shape.shape_index = scene.rzm_active_shape_index
            sync_shape = row_m.operator("rzm.sync_shape_cluster", text="Sync Manager", icon='FILE_REFRESH')
            sync_shape.shape_index = scene.rzm_active_shape_index
            manager_box.template_list("RZM_UL_Shapes", "", rzm, "shapes", scene, "rzm_active_shape_index", rows=4)

            if rzm.shapes and 0 <= scene.rzm_active_shape_index < len(rzm.shapes):
                active_shape = rzm.shapes[scene.rzm_active_shape_index]
                if len(active_shape.groups) == 0:
                    init_row = manager_box.row(align=True)
                    init_row.operator("rzm.add_shape_cluster_group", text="Initialize Default Group", icon='ADD')
                detail_box = manager_box.box()
                detail_box.prop(active_shape, "shape_name", text="Manager Variable")
                detail_box.prop(active_shape, "shape_type", text="Type")
                detail_box.prop(active_shape, "sync_value", text="Preview Value", slider=True)
                detail_box.prop(active_shape, "disable_export", text="Disable Variable Export")

                group_box = detail_box.box()
                group_row = group_box.row(align=True)
                group_row.label(text="Groups:", icon='GROUP')
                group_row.operator("rzm.add_shape_cluster_group", text="", icon='ADD')
                group_row.operator("rzm.remove_shape_cluster_group", text="", icon='REMOVE')
                group_box.template_list(
                    "RZM_UL_ShapeClusterGroups", "",
                    active_shape, "groups",
                    active_shape, "active_group_index",
                    rows=3
                )
                if active_shape.groups and 0 <= active_shape.active_group_index < len(active_shape.groups):
                    active_group = active_shape.groups[active_shape.active_group_index]
                    group_box.prop(active_group, "group_name")
                    group_box.prop(active_group, "condition")

                member_box = detail_box.box()
                member_row = member_box.row(align=True)
                member_row.label(text="Cluster Members:", icon='LINKED')
                member_row.operator("rzm.add_shape_cluster_member", text="Add Active SKC", icon='ADD')
                member_row.operator("rzm.remove_shape_cluster_member", text="", icon='REMOVE')
                member_box.template_list(
                    "RZM_UL_ShapeKeys", "",
                    active_shape, "shape_keys",
                    scene, "rzm_active_shape_key_index",
                    rows=5
                )
                if active_shape.shape_keys and 0 <= scene.rzm_active_shape_key_index < len(active_shape.shape_keys):
                    member = active_shape.shape_keys[scene.rzm_active_shape_key_index]
                    edit_box = member_box.box()
                    edit_box.prop(member, "target_shape_name", text="Target SKC")
                    edit_box.prop(member, "group_index", text="Group")
                    edit_box.prop(member, "condition")
                    edit_box.prop(member, "fallback_value")
                    edit_box.prop(member, "mode")
                    if member.mode == 'ADVANCED':
                        r = edit_box.row(align=True)
                        r.prop(member, "input_range_min", text="From")
                        r.prop(member, "input_range_max", text="To")
                        edit_box.prop(member, "multiplier")
                    if active_shape.shape_type == 'Anim':
                        edit_box.prop(member, "anim_type_index")
                        r = edit_box.row(align=True)
                        r.prop(member, "anim_start_frame", text="Start")
                        r.prop(member, "anim_t2", text="Rise")
                        r = edit_box.row(align=True)
                        r.prop(member, "anim_t3", text="Fall")
                        r.prop(member, "anim_end_frame", text="End")

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

            sk_export_box = box.box()
            sk_export_box.label(text="ShapeKey Export Settings:", icon='MOD_MIRROR')
            sk_export_box.prop(rzm.addons, "shape_key_invert_x", text="InvertX")
            
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
            cfg_header = box.row(align=True)
            cfg_header.label(text="Discovered Configurations:", icon='SHAPEKEY_DATA')
            cfg_io = cfg_header.row(align=True)
            cfg_io.alignment = 'RIGHT'
            cfg_io.operator("rzm.import_shape_key_config", text="", icon='IMPORT')
            cfg_io.operator("rzm.export_shape_key_config", text="", icon='EXPORT')
            box.template_list("RZM_UL_ShapeConfigs", "", rzm, "shape_configs", scene, "rzm_active_shape_config_index")
            
            if rzm.shape_configs and 0 <= scene.rzm_active_shape_config_index < len(rzm.shape_configs):
                active_conf = rzm.shape_configs[scene.rzm_active_shape_config_index]
                c_box = box.box()
                c_box.prop(active_conf, "shape_name")
                
                row = c_box.row(align=True)
                row.prop(active_conf, "disable_export", text="Disable Export", icon='HIDE_OFF')
                row.prop(active_conf, "bake_weights", text="Bake Weights", icon='MOD_VERTEX_WEIGHT')
                row.prop(active_conf, "force_export", text="Force Export", icon='IMPORT')
                
                if active_conf.bake_weights:
                    c_box.prop(active_conf, "parent_shape", text="Parent Shape", icon='LINKED')
                
                c_box.prop(active_conf, "shape_type")
                
                # Core values for all types
                c_box.prop(active_conf, "sync_value", text="Sync Value (Global Name)", slider=True)
                m_row = c_box.row(align=True)
                m_row.prop(active_conf, "multiplier")
                m_row.prop(active_conf, "inverse")

                # --- Input Range Remap ---
                range_box = c_box.box()
                rmin = active_conf.input_range_min
                rmax = active_conf.input_range_max
                uses_range = (abs(rmin) > 0.001 or abs(rmax - 1.0) > 0.001)
                range_header = range_box.row(align=True)
                range_header.label(text="Input Range:", icon='ARROW_LEFTRIGHT')
                if uses_range:
                    range_header.label(text=f"[{rmin:.3f} → {rmax:.3f}] ↦ [0, 1]", icon='INFO')
                else:
                    range_header.label(text="Full Range (0 → 1)", icon='CHECKMARK')
                r_row = range_box.row(align=True)
                r_row.prop(active_conf, "input_range_min", text="From")
                r_row.prop(active_conf, "input_range_max", text="To")
                
                if active_conf.shape_type == 'Anim':
                    anim_box = c_box.box()
                    anim_box.label(text="Animation Settings:")
                    anim_box.prop(active_conf, "anim_type_index")
                    
                    # Visual Timeline Display
                    t1 = active_conf.anim_start_frame
                    t2 = active_conf.anim_t2
                    t3 = active_conf.anim_t3
                    t4 = active_conf.anim_end_frame

                    visual_timeline = anim_box.box()
                    visual_timeline.label(text="Visual Timeline (Envelope):", icon='TIME')
                    
                    # Construct unicode visual bar (20 segments)
                    bar_chars = []
                    for i in range(20):
                        mid = i * 0.05 + 0.025
                        if mid < t1 or mid > t4:
                            bar_chars.append("░")
                        elif mid < t2:
                            bar_chars.append("╱")
                        elif mid > t3:
                            bar_chars.append("╲")
                        else:
                            bar_chars.append("█")
                    
                    bar_str = "".join(bar_chars)
                    
                    # Render the visual bar as a large, centered text block
                    row_bar = visual_timeline.row(align=True)
                    row_bar.scale_y = 1.2
                    row_bar.alignment = 'CENTER'
                    row_bar.label(text=bar_str)
                    
                    # Render key values in a row
                    row_lbl = visual_timeline.row(align=True)
                    row_lbl.label(text=f"Start: {t1:.2f}")
                    row_lbl.label(text=f"Rise End: {t2:.2f}")
                    row_lbl.label(text=f"Fall Start: {t3:.2f}")
                    row_lbl.label(text=f"End: {t4:.2f}")

                    # Sliders
                    slider_box = visual_timeline.box()
                    slider_box.prop(active_conf, "anim_start_frame", slider=True, text="1. Start")
                    slider_box.prop(active_conf, "anim_t2", slider=True, text="2. Rise End")
                    slider_box.prop(active_conf, "anim_t3", slider=True, text="3. Fall Start")
                    slider_box.prop(active_conf, "anim_end_frame", slider=True, text="4. End")

                    # Controls / Operators
                    ctrl_row1 = visual_timeline.row(align=True)
                    op_l = ctrl_row1.operator("rzm.adjust_anim_timeline", text="Shift Left", icon='TRIA_LEFT')
                    op_l.action = 'SHIFT_LEFT'
                    op_l.config_index = scene.rzm_active_shape_config_index
                    
                    op_r = ctrl_row1.operator("rzm.adjust_anim_timeline", text="Shift Right", icon='TRIA_RIGHT')
                    op_r.action = 'SHIFT_RIGHT'
                    op_r.config_index = scene.rzm_active_shape_config_index

                    ctrl_row2 = visual_timeline.row(align=True)
                    op_exp = ctrl_row2.operator("rzm.adjust_anim_timeline", text="Expand Window", icon='ADD')
                    op_exp.action = 'EXPAND'
                    op_exp.config_index = scene.rzm_active_shape_config_index

                    op_shr = ctrl_row2.operator("rzm.adjust_anim_timeline", text="Shrink Window", icon='REMOVE')
                    op_shr.action = 'SHRINK'
                    op_shr.config_index = scene.rzm_active_shape_config_index

                    ctrl_row3 = visual_timeline.row(align=True)
                    op_mhl = ctrl_row3.operator("rzm.adjust_anim_timeline", text="Shift Hold L", icon='BACK')
                    op_mhl.action = 'SHIFT_HOLD_LEFT'
                    op_mhl.config_index = scene.rzm_active_shape_config_index
                    
                    op_mhr = ctrl_row3.operator("rzm.adjust_anim_timeline", text="Shift Hold R", icon='FORWARD')
                    op_mhr.action = 'SHIFT_HOLD_RIGHT'
                    op_mhr.config_index = scene.rzm_active_shape_config_index

                    ctrl_row4 = visual_timeline.row(align=True)
                    op_mh = ctrl_row4.operator("rzm.adjust_anim_timeline", text="More Hold", icon='ASSET_MANAGER')
                    op_mh.action = 'MORE_HOLD'
                    op_mh.config_index = scene.rzm_active_shape_config_index

                    op_lh = ctrl_row4.operator("rzm.adjust_anim_timeline", text="Less Hold", icon='COLLAPSEMENU')
                    op_lh.action = 'LESS_HOLD'
                    op_lh.config_index = scene.rzm_active_shape_config_index
                    
                    over_box = anim_box.box()
                    over_box.label(text="Manual Override (Anim -> Linear):")
                    over_box.prop(active_conf, "override_switch_condition")
                    over_box.prop(active_conf, "override_switch_value_link")
                    
                c_box.prop(active_conf, "value_link")
                c_box.prop(active_conf, "condition")
                c_box.prop(active_conf, "fallback_value")
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
        
        header_row = box.row()
        # Left side: Active toggle
        header_row.prop(br, "is_enabled", text="Active", toggle=True)
        
        # Right side: Config Import/Export
        config_row = header_row.row(align=True)
        config_row.alignment = 'RIGHT'
        config_row.operator("rzm.import_config", text="", icon='IMPORT')
        config_row.operator("rzm.export_config", text="", icon='EXPORT').config_type = 'BLEND_RESIZE'

        if br.is_enabled:
            # 1. Master Groups (12 Slots)
            m_box = box.box()
            m_box.label(text="Master Resize Groups (12 Slots)", icon='GROUP_BONE')
            
            m_box.row().operator("rzm.br_add_group", text="Add Group", icon='ADD')
            
            for i, group in enumerate(br.groups):
                row = m_box.row(align=True)
                row.prop(group, "slot_id", text="")
                row.prop(group, "name", text="")
                row.prop(group, "value_link", text="Link")
                row.operator("rzm.br_remove_group", text="", icon='REMOVE').index = i
                
            # 2. Component Mappings
            c_box = box.box()
            c_box.label(text="Component Mappings", icon='NONE')
            
            c_box.row().operator("rzm.br_add_comp", text="Add Component", icon='ADD')
            
            col = c_box.column(align=True)
            for i, comp in enumerate(br.component_mappings):
                row = col.row(align=True)
                row.prop(comp, "name", text="")
                
                if scene.rzm_active_br_comp_index == i:
                    row.label(icon='CHECKMARK')
                else:
                    row.operator("rzm.br_select_comp", text="Select").index = i
                    
                row.operator("rzm.br_remove_comp", text="", icon='REMOVE').index = i

            # 3. Baked Layers for active component
            if 0 <= scene.rzm_active_br_comp_index < len(br.component_mappings):
                comp_idx = scene.rzm_active_br_comp_index
                active_comp = br.component_mappings[comp_idx]
                
                l_box_root = box.box()
                header = l_box_root.row()
                header.label(text=f"Baked Layers: {active_comp.name}", icon='RENDER_ANIMATION')
                
                header.operator("rzm.br_bake_layer", text="Bake from Active Bones", icon='FILE_REFRESH').comp_index = comp_idx
                
                l_box_root.row().operator("rzm.br_add_layer", text="Add Empty Layer", icon='ADD')
                
                for i, layer in enumerate(active_comp.layers):
                    l_box = l_box_root.box()
                    row = l_box.row()
                    row.prop(layer, "name", text="")
                    
                    group_name = "None"
                    for g in br.groups:
                        if g.slot_id == layer.slot_id:
                            group_name = g.name
                            break
                    
                    row.prop(layer, "slot_id", text="Slot")
                    row.label(text=group_name)
                    row.label(text=f"Bones: {layer.bone_count}")
                    op_rem = row.operator("rzm.br_remove_layer", text="", icon='REMOVE')
                    op_rem.comp_index = comp_idx
                    op_rem.layer_index = i
                    
                    # Layer Details (Coordinates)
                    header_c = l_box.row()
                    header_c.label(text="Spatial Anchor (Coordinates)", icon='EMPTY_AXIS')
                    cop_row = header_c.row(align=True)
                    op_c = cop_row.operator("rzm.br_copy_coords", icon='COPYDOWN', text="")
                    op_c.comp_index = comp_idx
                    op_c.layer_index = i
                    op_p = cop_row.operator("rzm.br_paste_coords", icon='PASTEDOWN', text="")
                    op_p.comp_index = comp_idx
                    op_p.layer_index = i

                    flow = l_box.grid_flow(columns=3, align=True)
                    flow.prop(layer, "head_mapped", text="Head")
                    flow.prop(layer, "bone_x_mapped", text="X Axis")
                    flow.prop(layer, "bone_y_mapped", text="Y Axis")
                    
                    # Bones inside layer
                    b_row = l_box.row()
                    b_row.label(text="Bones:")
                    b_op = b_row.operator("rzm.br_add_layer_bone", text="", icon='ADD')
                    b_op.comp_index = comp_idx
                    b_op.layer_index = i
                    
                    for j, bone in enumerate(layer.bones):
                        b_r = l_box.row(align=True)
                        b_r.prop(bone, "bone_index", text="ID")
                        
                        b_r.prop(bone, "scale_mapped", text="S")
                        b_r.prop(bone, "offset_mapped", text="T")
                        b_r.prop(bone, "rotation_euler_mapped", text="R")

                        c_op = b_r.operator("rzm.br_copy_bone_coords", text="", icon='COPYDOWN')
                        c_op.comp_index = comp_idx
                        c_op.layer_index = i
                        c_op.bone_index = j
                        
                        p_op = b_r.operator("rzm.br_paste_bone_coords", text="", icon='PASTEDOWN')
                        p_op.comp_index = comp_idx
                        p_op.layer_index = i
                        p_op.bone_index = j

                        b_rm = b_r.operator("rzm.br_remove_layer_bone", text="", icon='REMOVE')
                        b_rm.comp_index = comp_idx
                        b_rm.layer_index = i
                        b_rm.bone_index = j

            box.separator()
            box.label(text="Export saves configurations inside the addon's .ini output. No external buffers needed.", icon='INFO')

        elif tab == 'BLEND_RESIZE':
            # --- BLEND RESIZE SYSTEM ---
            br = rzm.addons.blend_resize
            
            header_row = box.row()
            # Left side: Active toggle
            header_row.prop(br, "is_enabled", text="Active", toggle=True)
            
            # Right side: Config Import/Export
            config_row = header_row.row(align=True)
            config_row.alignment = 'RIGHT'
            config_row.operator("rzm.import_config", text="", icon='IMPORT')
            op_exp = config_row.operator("rzm.export_config", text="", icon='EXPORT')
            op_exp.config_type = 'BLEND_RESIZE'

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
                        
                        group_name = "None"
                        for g in br.groups:
                            if g.slot_id == layer.slot_id:
                                group_name = g.name
                                break
                        
                        row.prop(layer, "slot_id", text="Slot")
                        row.label(text=group_name)
                        row.label(text=f"Bones: {layer.bone_count}")
                        op = row.operator("rzm.br_remove_layer", text="", icon='REMOVE')
                        op.comp_index = comp_idx
                        op.layer_index = i
                        
                        # Layer Details (Coordinates)
                        header_c = l_box.row()
                        header_c.label(text="Spatial Anchor (Coordinates)", icon='EMPTY_AXIS')
                        cop_row = header_c.row(align=True)
                        op_c = cop_row.operator("rzm.br_copy_coords", icon='COPYDOWN', text="")
                        op_c.comp_index = comp_idx
                        op_c.layer_index = i
                        op_p = cop_row.operator("rzm.br_paste_coords", icon='PASTEDOWN', text="")
                        op_p.comp_index = comp_idx
                        op_p.layer_index = i

                        flow = l_box.grid_flow(columns=3, align=True)
                        flow.prop(layer, "head_mapped", text="Head")
                        flow.prop(layer, "bone_x_mapped", text="X Axis")
                        flow.prop(layer, "bone_y_mapped", text="Y Axis")
                        
                        # Bones inside layer
                        b_row = l_box.row()
                        b_row.label(text="Bones:")
                        b_op = b_row.operator("rzm.br_add_layer_bone", text="", icon='ADD')
                        b_op.comp_index = comp_idx
                        b_op.layer_index = i
                        
                        for j, bone in enumerate(layer.bones):
                            b_r = l_box.row(align=True)
                            b_r.prop(bone, "bone_index", text="ID")
                            
                            b_r.prop(bone, "scale_mapped", text="S")
                            b_r.prop(bone, "offset_mapped", text="T")
                            b_r.prop(bone, "rotation_euler_mapped", text="R")

                            c_op = b_r.operator("rzm.br_copy_bone_coords", text="", icon='COPYDOWN')
                            c_op.comp_index = comp_idx
                            c_op.layer_index = i
                            c_op.bone_index = j
                            
                            p_op = b_r.operator("rzm.br_paste_bone_coords", text="", icon='PASTEDOWN')
                            p_op.comp_index = comp_idx
                            p_op.layer_index = i
                            p_op.bone_index = j

                            b_rm = b_r.operator("rzm.br_remove_layer_bone", text="", icon='REMOVE')
                            b_rm.comp_index = comp_idx
                            b_rm.layer_index = i
                            b_rm.bone_index = j

                box.separator()
                box.label(text="Export saves configurations inside the addon's .ini output. No external buffers needed.", icon='INFO')


class VIEW3D_PT_RZConstructorToolboxPanel_Internal(bpy.types.Panel):
    bl_label = "RZ Construct Toolbox"
    bl_idname = "VIEW3D_PT_rz_constructor_toolbox_panel_internal"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_order = 100

    @classmethod
    def poll(cls, context):
        addon_name = __package__.split(".")[0] if "." in __package__ else __package__
        prefs = context.preferences.addons.get(addon_name)
        return prefs and not getattr(prefs.preferences, "move_to_npanel", False)

    def draw(self, context):
        draw_toolbox_content(self, context)


class VIEW3D_PT_RZConstructorToolboxPanel_External(bpy.types.Panel):
    bl_label = "RZ Construct Toolbox"
    bl_idname = "VIEW3D_PT_rz_constructor_toolbox_panel_external"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor Toolbox'
    bl_order = 0

    @classmethod
    def poll(cls, context):
        addon_name = __package__.split(".")[0] if "." in __package__ else __package__
        prefs = context.preferences.addons.get(addon_name)
        return prefs and getattr(prefs.preferences, "move_to_npanel", True)

    def draw(self, context):
        draw_toolbox_content(self, context)



class VIEW3D_PT_RZModProducerBuild(bpy.types.Panel):
    bl_label = "Mod Producer Build"
    bl_idname = "VIEW3D_PT_RZModProducerBuild"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RZ Constructor"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_editor_mode == 'PRO'

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

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_editor_mode == 'PRO'

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


class VIEW3D_PT_RZConstructorAdvancedPanel(bpy.types.Panel):
    bl_label = "RZ Constructor Advanced"
    bl_idname = "VIEW3D_PT_rz_constructor_advanced_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RZ Constructor'
    bl_parent_id = "VIEW3D_PT_rz_constructor_panel"
    bl_order = 5

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_editor_mode == 'PRO'

    def draw(self, context):
        self.draw_info_block(context, self.layout)

    def draw_info_block(self, context, layout):
        scene = context.scene
        rzm = scene.rzm
        game = rzm.game.selection
        if not hasattr(rzm, "export_settings") or not rzm.export_settings:
            return
        settings = rzm.export_settings
        
        box = layout.box()
        box.label(text="Export Management", icon='INFO')
        
        # --- GLOBAL ARTIST INFO ---
        from ..operators.tier_ops import get_prefs
        prefs = get_prefs(context)
        if prefs:
            row = box.row()
            row.label(text=f"Author: {prefs.author_name}", icon='USER')

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
        # In Blender we usually just tell them to check prefs.
        
        col.separator()
        col.prop(meta, "requirements")
        if hasattr(col, "textbox"):
            col.label(text="Lore:")
            col.textbox(meta, "description")
        else:
            col.prop(meta, "description", text="Lore")
        col.prop(meta, "menu_keybind")
        col.prop(meta, "community_respect")
        
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


classes_to_register = [
    RZM_UL_CM_ComponentList,
    RZM_UL_CM_PartList,
    RZM_UL_CustomScriptList,
    RZM_UL_Values,
    RZM_UL_ToggleDefinitions,
    RZM_UL_Shapes,
    RZM_UL_ShapeKeys,
    RZM_UL_ShapeClusterGroups,
    RZM_UL_RunLinks,
    RZM_UL_Keybinds,
    RZM_UL_ShapeDiscoveryCollections,
    RZM_UL_ShapeConfigs,
    RZM_MT_AssignToggleMenu,
    RZM_MT_AssignTexSlotMenu,
    VIEW3D_PT_RZConstructorPanel,
    VIEW3D_PT_RZConstructorAdvancedPanel,
    VIEW3D_PT_RZM_AutoMenuCreator,
    VIEW3D_PT_RZM_ExportManager,
    VIEW3D_PT_RZModProducerBuild,
    VIEW3D_PT_RZConstructorToolboxPanel_Internal,
    VIEW3D_PT_RZConstructorToolboxPanel_External,
    RZM_PT_ObjectTiers
]
