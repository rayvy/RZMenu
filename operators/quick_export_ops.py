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
        mod_block_content = self.extract_mod_block(ini_path)
        if mod_block_content is None:
            self.report({'ERROR'}, "MOD-BLOCK tags not found in existing .ini. Please perform a Full Export first to initialize the file structure.")
            return {'CANCELLED'}

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
        Returns None if tags are missing or malformed.
        """
        try:
            with open(ini_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            start_tag = ";[META-INFO] [START] [MOD-BLOCK]"
            end_tag = ";[META-INFO] [END] [MOD-BLOCK]"
            
            start_idx = content.find(start_tag)
            end_idx = content.find(end_tag)
            
            if start_idx == -1 or end_idx == -1:
                return None
            
            # Content starts after the start tag
            block_start = start_idx + len(start_tag)
            # And ends before the end tag
            return content[block_start : end_idx]
            
        except Exception as e:
            print(f"RZMenu Error during mod block extraction: {e}")
            return None

classes_to_register = [RZM_OT_QuickExportMenu]
