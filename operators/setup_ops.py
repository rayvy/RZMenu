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


classes_to_register = [
    RZM_OT_AddCustomScript,
    RZM_OT_RemoveCustomScript,
    RZM_OT_MoveCustomScript,
    RZM_OT_AutoSetupGame,
    RZM_OT_RefreshAddonData,
    RZM_OT_FullExport,
    RZM_OT_BatchExport,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
