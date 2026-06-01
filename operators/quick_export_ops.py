import bpy
import os
import re
from pathlib import Path
from ..core.j2_exporter import RZMenuJ2Exporter
from .export_manager import get_target_path, run_custom_scripts

class RZM_OT_QuickExportMenu(bpy.types.Operator):
    """Regenerate only UI and logic sections of the .ini file without re-exporting geometry."""
    bl_idname = "rzm.quick_export_menu"
    bl_label = "Quick Update"
    bl_description = "Regenerate UI sections, export fonts/atlas, and run scripts while preserving geometry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_dir = get_target_path(context)
        if not target_dir or not os.path.exists(target_dir):
            self.report({'ERROR'}, "Export path not set or invalid! Set it in Export Manager first.")
            return {'CANCELLED'}

        # 1. Resource Export (Atlas & Fonts)
        settings = context.scene.rzm.export_settings
        if settings.quick_update_resources:
            print("RZMenu Quick Update: Exporting resources (Atlas & Fonts)...")
            try:
                bpy.ops.rzm.export_atlas()
                bpy.ops.rzm.export_fonts()
            except Exception as e:
                self.report({'WARNING'}, f"Resource export failed: {e}")

        # 2. Find the target .ini using heuristic
        ini_path = self.find_target_ini(target_dir)
        if not ini_path:
            self.report({'ERROR'}, "Suitable .ini file not found in export directory (skipping DISABLED/ARCHIVED).")
            return {'CANCELLED'}

        print(f"RZMenu Quick Update: Target file identified as {os.path.basename(ini_path)}")

        # 2. Extract MOD-BLOCK from existing file
        mod_block_content, has_tags = self.extract_mod_block(ini_path)
        if not has_tags:
            self.report({'WARNING'}, "MOD-BLOCK tags not found. Geometry/Mesh data will NOT be preserved in this update.")
            mod_block_content = "; [MOD-BLOCK NOT FOUND - Standalone UI Mode]"

        # 3. Render new .ini with menu_only=True
        exporter = RZMenuJ2Exporter(context)
        try:
            new_ini_rendered = exporter.render(menu_only=True)
        except Exception as e:
            self.report({'ERROR'}, f"Template rendering failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # 4. Replace placeholder with old MOD-BLOCK
        # The space/newline handling should be careful
        placeholder = ";[RZM-QUICK-UPDATE-PLACEHOLDER]"
        if placeholder not in new_ini_rendered:
            self.report({'ERROR'}, "Internal Error: Placeholder not found in rendered template! Check rz_uni.j2.")
            return {'CANCELLED'}
            
        final_ini = new_ini_rendered.replace(placeholder, mod_block_content.strip("\n\r"))

        # 5. Write back to file
        try:
            with open(ini_path, 'w', encoding='utf-8') as f:
                f.write(final_ini)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write .ini file: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"⚡ Quick Update Successful: {os.path.basename(ini_path)}")

        # 6. Post-Export Scripts
        if settings.quick_update_run_scripts:
            print("RZMenu Quick Update: Executing post-export scripts...")
            run_custom_scripts(context, target_dir)

        return {'FINISHED'}

    def find_target_ini(self, directory):
        """
        Heuristic to find the main .ini file:
        - Must end with .ini
        - Must not start with DISABLED or ARCHIVED (case-insensitive)
        - If multiple candidates, pick the largest one.
        """
        candidates = []
        for file in os.listdir(directory):
            name_up = file.upper()
            if file.lower().endswith(".ini") and not name_up.startswith(("DISABLED", "ARCHIVED")):
                full_path = os.path.join(directory, file)
                if os.path.isfile(full_path):
                    candidates.append((full_path, os.path.getsize(full_path)))
        
        if not candidates:
            return None
            
        # Sort by size descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def extract_mod_block(self, ini_path):
        """
        Extracts content strictly BETWEEN the MOD-BLOCK tags.
        Returns (content, has_tags).
        """
        try:
            if not os.path.exists(ini_path):
                return "", False

            with open(ini_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            start_tag = ";[META-INFO] [START] [MOD-BLOCK]"
            end_tag = ";[META-INFO] [END] [MOD-BLOCK]"
            
            start_idx = content.find(start_tag)
            end_idx = content.find(end_tag)
            
            if start_idx == -1 or end_idx == -1:
                return "", False
            
            # Content starts after the start tag
            block_start = start_idx + len(start_tag)
            # And ends before the end tag
            return content[block_start : end_idx], True
            
        except Exception as e:
            print(f"RZMenu Error during mod block extraction: {e}")
            return "", False

class RZM_OT_QuickExportGameBuffers(bpy.types.Operator):
    """Export only game buffers (XXMI/EFMI/WWMI) without regenerating RZMenu UI assets or Atlas."""
    bl_idname = "rzm.quick_export_game_buffers"
    bl_label = "Quick Export Game Buffers"
    bl_description = "Does not export RZMenu resource buffers; exports only the game buffers for XXMI/EFMI, plus the VFX patcher when VFX effects are present"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..utils.safe_export import SafeExport
        with SafeExport(context):
            return self.execute_internal(context)

    def execute_internal(self, context):
        rzm = context.scene.rzm
        game = rzm.game.selection
        target_path = get_target_path(context)
        
        if not target_path:
            self.report({'ERROR'}, "Export path not set! Initialize path in settings first.")
            return {'CANCELLED'}

        # Save original states of properties
        saved_xxmi = {}
        saved_efmi = {}

        # Get instances of settings
        xxmi = getattr(context.scene, "xxmi", None)
        efmi = getattr(context.scene, "efmi_tools_settings", None)

        # XXMI properties to save
        if xxmi:
            for prop in ["write_ini", "write_buffers"]:
                if hasattr(xxmi, prop):
                    saved_xxmi[prop] = getattr(xxmi, prop)

        # EFMI properties to save
        if efmi:
            for prop in ["write_ini"]:
                if hasattr(efmi, prop):
                    saved_efmi[prop] = getattr(efmi, prop)

        # Apply forced values
        try:
            if xxmi:
                if "write_ini" in saved_xxmi:
                    xxmi.write_ini = False
                if "write_buffers" in saved_xxmi:
                    xxmi.write_buffers = True
            if efmi:
                if "write_ini" in saved_efmi:
                    efmi.write_ini = False

            # Just target game export (without atlas, fonts, or rzm buffer packing)
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

            # Run Puppet Master Baking (Automated Post-Export) if enabled
            if getattr(rzm.addons, "export_shapekeys", False):
                try:
                    print("[RZM Quick Game Buffers] Triggering Puppet Master Baking (Full Mode)...")
                    bpy.ops.rzm.puppet_master_bake(full_export_mode=True)
                except Exception as e:
                    self.report({'WARNING'}, f"Puppet Master bake failed: {e}")

            # Run custom post-export scripts
            run_custom_scripts(context, target_path)

        except Exception as export_err:
            self.report({'ERROR'}, f"Export failed: {export_err}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        finally:
            # Restore saved states
            if xxmi:
                for prop, val in saved_xxmi.items():
                    try:
                        setattr(xxmi, prop, val)
                    except Exception:
                        pass
            if efmi:
                for prop, val in saved_efmi.items():
                    try:
                        setattr(efmi, prop, val)
                    except Exception:
                        pass

        self.report({'INFO'}, "Quick Game Buffers Export Successful!")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_QuickExportMenu,
    RZM_OT_QuickExportGameBuffers,
]
