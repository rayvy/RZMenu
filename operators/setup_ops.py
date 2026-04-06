# RZMenu/operators/setup_ops.py
import bpy
import os
import subprocess
import sys
from pathlib import Path
from .export_manager import get_target_path
from ..utils.texture_collector import collect_missing_textures

# Kill-switch: Set to False once EFMI-Tools ships a native batch_export (v2.0+).
# While True, RZMenu implements a manual frame-loop workaround.
EFMI_BATCH_EXPORT_ENABLED = True

class RZM_OT_AddCustomScript(bpy.types.Operator):
    bl_idname = "rzm.add_custom_script"
    bl_label = "Add Custom Script"
    bl_description = "Add a new script entry to the post-export list"

    def execute(self, context):
        context.scene.rzm.export_settings.custom_scripts.add()
        return {'FINISHED'}

class RZM_OT_RemoveCustomScript(bpy.types.Operator):
    bl_idname = "rzm.remove_custom_script"
    bl_label = "Remove Custom Script"
    bl_description = "Remove the selected script entry"
    
    index: bpy.props.IntProperty()

    def execute(self, context):
        scripts = context.scene.rzm.export_settings.custom_scripts
        scripts.remove(self.index)
        return {'FINISHED'}

class RZM_OT_MoveCustomScript(bpy.types.Operator):
    bl_idname = "rzm.move_custom_script"
    bl_label = "Move Custom Script"
    bl_description = "Change script execution order"
    
    index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])

    def execute(self, context):
        scripts = context.scene.rzm.export_settings.custom_scripts
        neighbor = self.index - 1 if self.direction == 'UP' else self.index + 1
        scripts.move(self.index, neighbor)
        return {'FINISHED'}

class RZM_OT_AutoSetupGame(bpy.types.Operator):
    bl_idname = "rzm.autosetup_game"
    bl_label = "Auto-Setup Addon Settings"
    bl_description = "Automatically configure external addon (XXMI/EFMI/WWMI) with RZMenu template"

    def execute(self, context):
        scene = context.scene
        rzm = scene.rzm
        game = rzm.game.selection
        
        # Determine RZMenu addon directory path
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        template_path = os.path.join(addon_dir, "rztemplate", "rz_uni.j2")
        
        if not os.path.exists(template_path):
            self.report({'ERROR'}, f"Root RZ-Template not found: {template_path}")
            return {'CANCELLED'}

        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
            if hasattr(scene, "xxmi"):
                xxmi = scene.xxmi
                xxmi.use_custom_template = True
                xxmi.template_path = template_path
                try:
                    xxmi.game = game
                except:
                    self.report({'WARNING'}, f"Could not set XXMI game mode to {game}")
                self.report({'INFO'}, f"XXMI Tools: Configured with rz_uni.j2 ({game})")
            else:
                self.report({'WARNING'}, "XXMI Tools addon is not active or properties missing.")
                
        elif game == 'WutheringWaves':
            if hasattr(scene, "wwmi_tools_settings"):
                wwmi = scene.wwmi_tools_settings
                wwmi.use_custom_template = True
                wwmi.custom_template_source = 'EXTERNAL'
                wwmi.custom_template_path = template_path
                self.report({'INFO'}, "WWMI Tools: Configured with rz_uni.j2")
            else:
                self.report({'WARNING'}, "WWMI Tools addon is not active or properties missing.")

        elif game == 'ArknightsEndfield':
            if hasattr(scene, "efmi_tools_settings"):
                efmi = scene.efmi_tools_settings
                efmi.use_custom_template = True
                efmi.custom_template_source = 'EXTERNAL'
                efmi.custom_template_path = template_path
                self.report({'INFO'}, "EFMI Tools: Configured with rz_uni.j2")
            else:
                self.report({'WARNING'}, "EFMI Tools addon is not active or properties missing.")
        
        else:
            self.report({'INFO'}, f"No specific skip/setup logic for {game}")
        
        return {'FINISHED'}

class RZM_OT_RefreshAddonData(bpy.types.Operator):
    bl_idname = "rzm.refresh_addon_data"
    bl_label = "Refresh Addon Data"
    bl_description = "Force synchronized update of external addon properties"

    def execute(self, context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        
        self.report({'INFO'}, "Addon data view refreshed")
        return {'FINISHED'}

class RZM_OT_FullExport(bpy.types.Operator):
    bl_idname = "rzm.full_export"
    bl_label = "Export Full Mod"
    bl_description = "Run RZ internal exports (Atlas, Fonts) and then call game-specific mod exporter"

    execute_init: bpy.props.BoolProperty(default=True)
    execute_post: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        rzm = context.scene.rzm
        game = rzm.game.selection
        target_path = get_target_path(context)
        
        print("-" * 30)
        print(f"DEBUG: RZM Full Export Start")
        print(f"DEBUG: Target Path: {target_path}")
        
        if not target_path:
            self.report({'ERROR'}, "Export path not set! Initialize path in settings first.")
            return {'CANCELLED'}

        # -1. Texture Collection & Missing Resources Check
        try:
            missing_count = collect_missing_textures(context)
            if missing_count > 0:
                print(f"[RZM Full Export] Marked {missing_count} missing textures for auto-generation.")
        except Exception as e:
            self.report({'WARNING'}, f"Texture collection failed: {e}")

        # 0. Auto-Setup & Initialization Check
        if self.execute_init:
            try:
                bpy.ops.rzm.autosetup_game()
            except Exception as e:
                self.report({'WARNING'}, f"Auto-Setup failed: {e}")

        # Проверка на наличие папки modules
        modules_path = os.path.join(target_path, "modules")
        if not os.path.exists(modules_path):
            print(f"DEBUG: 'modules' folder not found at {modules_path}. Calling initialize_mod...")
            try:
                bpy.ops.rzm.initialize_mod()
            except Exception as e:
                self.report({'ERROR'}, f"Auto-Initialization failed: {e}")
                return {'CANCELLED'}
        else:
            print(f"DEBUG: 'modules' folder found. Skipping initialization.")
            
        # 1. Export Atlas
        try:
            bpy.ops.rzm.export_atlas()
        except Exception as e:
            self.report({'ERROR'}, f"Atlas export failed: {e}")
            return {'CANCELLED'}
        
        # 2. Font Maker (Export Fonts)
        try:
            bpy.ops.rzm.export_fonts()
        except Exception as e:
            self.report({'ERROR'}, f"Font export failed: {e}")
            return {'CANCELLED'}
        
        # 3. Target Game Export
        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
            if hasattr(bpy.ops, "xxmi"):
                bpy.ops.xxmi.exportadvanced()
            else:
                self.report({'ERROR'}, "XXMI Tools not found. Cannot export mod.")
                return {'CANCELLED'}
                
        elif game == 'WutheringWaves':
            if hasattr(bpy.ops, "wwmi_tools"):
                bpy.ops.wwmi_tools.export_mod()
            else:
                self.report({'ERROR'}, "WWMI Tools not found. Cannot export mod.")
                return {'CANCELLED'}

        elif game == 'ArknightsEndfield':
            if hasattr(bpy.ops, "efmi_tools"):
                bpy.ops.efmi_tools.export_mod()
            else:
                self.report({'ERROR'}, "EFMI Tools not found. Cannot export mod.")
                return {'CANCELLED'}
        
        # 4. Custom Scripts Execution
        settings = rzm.export_settings
        if settings.show_custom_scripts:
            import shlex
            print(f"DEBUG: Running custom post-export scripts...")
            for script in settings.custom_scripts:
                if not script.enabled or not script.path:
                    continue
                
                script_path = bpy.path.abspath(script.path)
                if not os.path.exists(script_path):
                    print(f"DEBUG WARNING: Script not found: {script_path}")
                    continue
                
                print(f"DEBUG: Executing: {os.path.basename(script_path)}")
                
                try:
                    # Construct command
                    if script_path.lower().endswith(".py"):
                        cmd = ["python", script_path]
                    else:
                        cmd = [script_path]
                    
                    # Add arguments
                    if script.args:
                        try:
                            cmd.extend(shlex.split(script.args))
                        except Exception as e:
                            print(f"DEBUG WARNING: Argument splitting failed: {e}. Using raw split.")
                            cmd.extend(script.args.split())
                    
                    # Prepare Popen
                    proc = subprocess.Popen(
                        cmd, 
                        cwd=target_path, 
                        stdin=subprocess.PIPE if script.auto_input else None,
                        stdout=None, # Show in Blender console
                        stderr=None
                    )
                    
                    # Manage execution
                    try:
                        timeout = script.timeout if script.use_timeout else None
                        
                        if script.auto_input:
                            # Send Enter (\n), Space, and 123 sequence
                            input_seq = b"\n \n123\n"
                            proc.communicate(input=input_seq, timeout=timeout)
                        else:
                            proc.wait(timeout=timeout)
                            
                    except subprocess.TimeoutExpired:
                        print(f"DEBUG ERROR: Script '{os.path.basename(script_path)}' timed out ({script.timeout}s). Killing process!")
                        proc.kill()
                        proc.wait() # Ensure it's cleaned up
                        
                except Exception as e:
                    print(f"DEBUG ERROR: Runtime error for script {script_path}: {e}")
        else:
            print("DEBUG: Skipping custom post-export scripts (execute_post=False)")

        print(f"DEBUG: RZM Full Export Finished")
        print("-" * 30)
        
        return {'FINISHED'}


class RZM_OT_BatchExport(bpy.types.Operator):
    """Batch export: generates numbered subfolders (1, 2, 3...) per frame.
    Disables texture copying and INI generation for duplicate frames.
    """
    bl_idname = "rzm.batch_export"
    bl_label = "Batch Export Mod"
    bl_description = (
        "Run RZ internal exports (Atlas, Fonts) and then call game-specific "
        "BATCH exporter — creates numbered subfolders per frame without "
        "duplicating textures or INI files"
    )

    execute_init: bpy.props.BoolProperty(default=True)

    def _run_common_pre_export(self, context, target_path):
        """Runs Atlas and Fonts export. Returns False on failure."""
        # -1. Texture collection
        try:
            missing_count = collect_missing_textures(context)
            if missing_count > 0:
                print(f"[RZM Batch] Marked {missing_count} missing textures.")
        except Exception as e:
            self.report({'WARNING'}, f"Texture collection failed: {e}")

        # 0. Auto-Setup
        if self.execute_init:
            try:
                bpy.ops.rzm.autosetup_game()
            except Exception as e:
                self.report({'WARNING'}, f"Auto-Setup failed: {e}")

        # Ensure modules folder exists
        modules_path = os.path.join(target_path, "modules")
        if not os.path.exists(modules_path):
            try:
                bpy.ops.rzm.initialize_mod()
            except Exception as e:
                self.report({'ERROR'}, f"Auto-Initialization failed: {e}")
                return False

        # 1. Export Atlas
        try:
            bpy.ops.rzm.export_atlas()
        except Exception as e:
            self.report({'ERROR'}, f"Atlas export failed: {e}")
            return False

        # 2. Export Fonts
        try:
            bpy.ops.rzm.export_fonts()
        except Exception as e:
            self.report({'ERROR'}, f"Font export failed: {e}")
            return False

        return True

    def _batch_xxmi(self, context):
        """Batch export via XXMI's native ExportAdvancedBatched operator."""
        if not hasattr(bpy.ops, "xxmi"):
            self.report({'ERROR'}, "XXMI Tools not found. Cannot batch export.")
            return False

        xxmi = context.scene.xxmi

        # Save original settings
        saved = {
            "copy_textures": xxmi.copy_textures,
            "write_ini": xxmi.write_ini,
            "apply_modifiers_and_shapekeys": xxmi.apply_modifiers_and_shapekeys,
            "batch_pattern": xxmi.batch_pattern,
        }

        print("[RZM Batch] Overriding XXMI settings for batch mode...")
        try:
            xxmi.copy_textures = False
            xxmi.write_ini = False
            xxmi.apply_modifiers_and_shapekeys = True
            xxmi.batch_pattern = "#"

            print("[RZM Batch] Calling xxmi.exportadvancedbatched()...")
            bpy.ops.xxmi.exportadvancedbatched()
            print("[RZM Batch] XXMI batch export finished.")
        except Exception as e:
            self.report({'ERROR'}, f"XXMI batch export failed: {e}")
            return False
        finally:
            print("[RZM Batch] Restoring XXMI settings...")
            for k, v in saved.items():
                try:
                    setattr(xxmi, k, v)
                except Exception:
                    pass

        return True

    def _batch_efmi(self, context):
        """Batch export for EFMI via manual frame-loop workaround.
        Creates subfolders: base_folder/1/, base_folder/2/, etc.
        Kill-switch: EFMI_BATCH_EXPORT_ENABLED = False disables this path.
        """
        if not EFMI_BATCH_EXPORT_ENABLED:
            self.report({'WARNING'}, (
                "EFMI batch export is disabled (EFMI_BATCH_EXPORT_ENABLED=False). "
                "Use standard Export Mod instead."
            ))
            return False

        if not hasattr(context.scene, "efmi_tools_settings"):
            self.report({'ERROR'}, "EFMI-Tools not found. Cannot batch export.")
            return False

        efmi = context.scene.efmi_tools_settings
        scene = context.scene

        if not efmi.mod_output_folder:
            self.report({'ERROR'}, "EFMI Mod Output Folder is not set!")
            return False

        base_dir = Path(bpy.path.abspath(efmi.mod_output_folder))
        frame_start = scene.frame_start
        frame_end = scene.frame_end
        original_frame = scene.frame_current

        # Force start from 1 for ArknightsEndfield (Usually frame 0 is original mesh)
        game = context.scene.rzm.game.selection
        if game == 'ArknightsEndfield' and frame_start < 1:
            frame_start = 1
            print(f"[RZM Batch EFMI] Forcing frame_start to 1 for Endfield.")

        # Save original settings
        saved = {
            "mod_output_folder": efmi.mod_output_folder,
            "copy_textures": efmi.copy_textures,
            "write_ini": efmi.write_ini,
            "apply_all_modifiers": efmi.apply_all_modifiers,
        }

        print(f"[RZM Batch EFMI] Overriding settings. Base dir: {base_dir}")
        print(f"[RZM Batch EFMI] Frame range: {frame_start} -> {frame_end}")

        try:
            efmi.copy_textures = False
            efmi.write_ini = False
            efmi.apply_all_modifiers = True

            for frame in range(frame_start, frame_end + 1):
                print(f"[RZM Batch EFMI] >>> Frame {frame}")

                scene.frame_set(frame)

                frame_dir = base_dir / str(frame)
                frame_dir.mkdir(parents=True, exist_ok=True)

                efmi.mod_output_folder = str(frame_dir) + os.sep

                try:
                    bpy.ops.efmi_tools.export_mod()
                    print(f"[RZM Batch EFMI] Frame {frame} — OK")
                except Exception as e:
                    print(f"[RZM Batch EFMI] Frame {frame} — FAILED: {e}")
                    self.report({'WARNING'}, f"EFMI frame {frame} export failed: {e}")

        except Exception as e:
            self.report({'ERROR'}, f"EFMI batch loop failed: {e}")
            return False
        finally:
            print("[RZM Batch EFMI] Restoring original settings...")
            for k, v in saved.items():
                try:
                    setattr(efmi, k, v)
                except Exception:
                    pass
            scene.frame_set(original_frame)
            print("[RZM Batch EFMI] Done.")

        return True

    def execute(self, context):
        rzm = context.scene.rzm
        game = rzm.game.selection
        target_path = get_target_path(context)

        print("-" * 40)
        print(f"[RZM] Batch Export Start — Game: {game}")
        print(f"[RZM] Target path: {target_path}")

        if not target_path:
            self.report({'ERROR'}, "Export path not set!")
            return {'CANCELLED'}

        # Pre-export (Atlas, Fonts, Init)
        if not self._run_common_pre_export(context, target_path):
            return {'CANCELLED'}

        # Game-specific batch
        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
            ok = self._batch_xxmi(context)
        elif game == 'ArknightsEndfield':
            ok = self._batch_efmi(context)
        elif game == 'WutheringWaves':
            self.report({'INFO'}, (
                "Batch export is not needed for WutheringWaves — "
                "shape keys are handled natively by WWMI."
            ))
            return {'CANCELLED'}
        else:
            self.report({'WARNING'}, f"No batch export configured for game: {game}")
            return {'CANCELLED'}

        if not ok:
            return {'CANCELLED'}

        print(f"[RZM] Batch Export Finished.")
        print("-" * 40)
        return {'FINISHED'}


class RZM_OT_CompleteExport(bpy.types.Operator):
    bl_idname = "rzm.complete_export"
    bl_label = "Complete Export (Test Modifiers)"
    bl_description = "Creates experimental backup, applies modifiers safely, then exports Full + Batch"

    export_filter_mode: bpy.props.EnumProperty(
        name="Export Targets",
        items=[
            ('SELECTED', "Selected Only", "Export only selected visible objects"),
            ('COLLECTION', "Active Collection", "Export objects in the active collection"),
            ('ALL_VISIBLE', "All Visible", "Export all visible meshes"),
        ],
        default='SELECTED'
    )
    
    ignore_hidden: bpy.props.BoolProperty(
        name="Ignore Hidden",
        description="Skip objects hidden in viewport",
        default=True
    )
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
        
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_filter_mode")
        layout.prop(self, "ignore_hidden")

    def execute(self, context):
        print("====== QUANTUM COMPLETE EXPORT ======")
        pref = context.preferences.addons[__package__.split('.')[0]].preferences
        blacklist_raw = getattr(pref, "modifier_blacklist", "Surface Deform, Data Transfer, Armature")
        blacklist = [x.strip().lower() for x in blacklist_raw.split(',') if x.strip()]
        
        # 1. Gather original objects
        targets = []
        if self.export_filter_mode == 'SELECTED':
            base_list = context.selected_objects
        elif self.export_filter_mode == 'COLLECTION':
            if context.view_layer.active_layer_collection:
                base_list = context.view_layer.active_layer_collection.collection.objects
            else:
                base_list = []
        else:
            base_list = context.view_layer.objects
            
        for o in base_list:
            if o.type != 'MESH': continue
            if self.ignore_hidden and (o.hide_viewport or o.hide_get() or not o.visible_get()): continue
            # Avoid picking up our own helpers or quantum copies if they linger
            if "RZM_BACKUP" in o.name: continue
            targets.append(o)
            
        if not targets:
            self.report({'WARNING'}, "No valid mesh targets found for export.")
            return {'CANCELLED'}
            
        scene = context.scene
        original_frame = scene.frame_current
        
        # Frame sync
        if scene.frame_start < 1:
            scene.frame_start = 1
            
        quantum_copies = []
        original_objects = []
        original_collections_map = {}
        original_names_map = {}
        
        print(f"[RZM Complete] Creating quantum duplicates for {len(targets)} objects...")
        for obj in targets:
            temp_obj = obj.copy()
            if obj.data:
                temp_obj.data = obj.data.copy()
                
            # Name swapping so EFMI exports the correct name
            orig_name = obj.name
            original_names_map[obj] = orig_name
            obj.name = orig_name + "_ORIGINAL_BACKUP"
            temp_obj.name = orig_name
                
            # Save original collections
            colls = list(obj.users_collection)
            original_collections_map[obj] = colls
            
            # Put quantum duplicate where original lived
            for coll in colls:
                coll.objects.link(temp_obj)
            if not colls:
                context.scene.collection.objects.link(temp_obj)
                
            # Safely UNLINK original from collections so EFMI cannot see it or iterate over it
            for coll in colls:
                coll.objects.unlink(obj)
                
            quantum_copies.append(temp_obj)
            original_objects.append(obj)
            
        from ..utils.modifier_utils import apply_modifiers_for_object_with_shape_keys
            
        try:
            print("[RZM Complete] Processing modifiers...")
            bpy.ops.object.select_all(action='DESELECT')
            
            for temp_obj in quantum_copies:
                context.view_layer.objects.active = temp_obj
                temp_obj.select_set(True)
                
                # Check Subsurf
                has_subsurf = False
                subsurf_idx = -1
                for i, mod in enumerate(temp_obj.modifiers):
                    if mod.type == 'SUBSURF': # Subdivision Surface
                        has_subsurf = True
                        subsurf_idx = i
                        break
                        
                # Add Triangulate modifier
                tri_mod = temp_obj.modifiers.new(name="RZM_Triangulate", type='TRIANGULATE')
                
                if has_subsurf:
                    target_idx = subsurf_idx + 1
                    try:
                        bpy.ops.object.modifier_move_to_index(modifier=tri_mod.name, index=target_idx)
                    except Exception as e:
                        print(f"  -> WARNING: Could not move Triangulate: {e}")
                else:
                    try:
                        bpy.ops.object.modifier_move_to_index(modifier=tri_mod.name, index=0)
                    except:
                        pass
                    
                # Collect allowed modifiers in order
                mods_to_apply = []
                for mod in temp_obj.modifiers:
                    type_str = mod.type.replace('_', ' ').lower()
                    if mod.name.lower() in blacklist or type_str in blacklist or type_str.title() in [b.title() for b in blacklist]:
                        print(f"  -> Skipping blacklisted modifier: {mod.name}")
                        continue
                    mods_to_apply.append(mod.name)
                    
                if mods_to_apply:
                    if temp_obj.data.shape_keys:
                        print(f"  -> Applying {len(mods_to_apply)} modifiers on {temp_obj.name} (WITH SHAPEKEYS)")
                        success, err = apply_modifiers_for_object_with_shape_keys(context, temp_obj, mods_to_apply, disable_armatures=False)
                        if not success:
                            self.report({'WARNING'}, f"EFMI error on {temp_obj.name}: {err}")
                    else:
                        print(f"  -> Applying {len(mods_to_apply)} modifiers on {temp_obj.name} (NO SHAPEKEYS)")
                        for mod_name in mods_to_apply:
                            try:
                                bpy.ops.object.modifier_apply(modifier=mod_name)
                            except Exception as e:
                                print(f"  -> Failed to apply {mod_name}: {e}")
                                
                bpy.ops.object.select_all(action='DESELECT')
                
            print("[RZM Complete] Modifiers processed. Triggering Export Pipeline...")
            
            # Select quantum copies for export
            bpy.ops.object.select_all(action='DESELECT')
            for qc in quantum_copies:
                try: qc.select_set(True)
                except: pass
            if quantum_copies:
                context.view_layer.objects.active = quantum_copies[0]
                
            print("  [>] Calling Full Export...")
            bpy.ops.rzm.full_export(execute_post=False)
            
            print("  [>] Calling Batch Export...")
            bpy.ops.rzm.batch_export(execute_init=False)
            
            # Run Post scripts
            settings = context.scene.rzm.export_settings
            if settings.show_custom_scripts:
                print("  [>] Executing Post Scripts...")
                import shlex
                import subprocess
                import os
                from .export_manager import get_target_path
                target_path = get_target_path(context)
                
                if target_path and os.path.exists(target_path):
                    for script in settings.custom_scripts:
                        if not script.enabled or not script.path: continue
                        script_path = bpy.path.abspath(script.path)
                        if not os.path.exists(script_path): continue
                        
                        try:
                            cmd = ["python", script_path] if script_path.lower().endswith(".py") else [script_path]
                            if script.args:
                                try: cmd.extend(shlex.split(script.args))
                                except: cmd.extend(script.args.split())
                                
                            proc = subprocess.Popen(
                                cmd, cwd=target_path,
                                stdin=subprocess.PIPE if script.auto_input else None,
                                stdout=None, stderr=None
                            )
                            try:
                                to = script.timeout if script.use_timeout else None
                                if script.auto_input:
                                    proc.communicate(input=b"\n \n123\n", timeout=to)
                                else:
                                    proc.wait(timeout=to)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                        except Exception as script_e:
                            print(f"Error in custom script: {script_e}")

            self.report({'INFO'}, "Complete Export Finished Successfully")

        except Exception as e:
            self.report({'ERROR'}, f"Complete Export Failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            print("[RZM Complete] Cleaning up quantum duplicates...")
            try: scene.frame_set(original_frame)
            except: pass

            for qc in quantum_copies:
                try:
                    mesh_data = qc.data
                    bpy.data.objects.remove(qc, do_unlink=True)
                    if mesh_data and mesh_data.users == 0:
                        bpy.data.meshes.remove(mesh_data, do_unlink=True)
                except ReferenceError:
                    pass
                    
            bpy.ops.object.select_all(action='DESELECT')
            for orig in original_objects:
                try:
                    # Restore Name
                    if orig in original_names_map:
                        orig.name = original_names_map[orig]
                    
                    # Relink back to collections
                    if orig in original_collections_map:
                        for coll in original_collections_map[orig]:
                            if orig.name not in coll.objects:
                                coll.objects.link(orig)
                                
                    orig.hide_viewport = False
                    orig.select_set(True)
                except ReferenceError:
                    pass
                    
            if original_objects:
                try: context.view_layer.objects.active = original_objects[0]
                except ReferenceError: pass
                
            print("====== COMPLETE EXPORT DONE ======")

        return {'FINISHED'}


classes_to_register = [
    RZM_OT_AddCustomScript,
    RZM_OT_RemoveCustomScript,
    RZM_OT_MoveCustomScript,
    RZM_OT_AutoSetupGame,
    RZM_OT_RefreshAddonData,
    RZM_OT_FullExport,
    RZM_OT_BatchExport,
    RZM_OT_CompleteExport,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
