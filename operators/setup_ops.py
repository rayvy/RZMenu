# RZMenu/operators/setup_ops.py
import bpy
import os
import subprocess
import sys
from .export_manager import get_target_path
from ..utils.texture_collector import collect_missing_textures

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

classes_to_register = [
    RZM_OT_AddCustomScript, 
    RZM_OT_RemoveCustomScript, 
    RZM_OT_MoveCustomScript,
    RZM_OT_AutoSetupGame, 
    RZM_OT_RefreshAddonData, 
    RZM_OT_FullExport
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
