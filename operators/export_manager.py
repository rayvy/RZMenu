#RZMenu/operators/export_manager.py
import bpy
import os
import shutil
import shlex
import subprocess
from pathlib import Path

def get_target_path(context, is_full=False):
    """Reliably get export path based on game context (XXMI/EFMI/WWMI -> Custom)."""
    rzm = context.scene.rzm
    settings = rzm.export_settings
    game = rzm.game.selection
    path = ""
    
    # 1. Try to take the path from game tool settings if enabled
    if settings.use_game_path:
        # Hoyoverse (XXMI)
        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
            if hasattr(context.scene, 'xxmi') and hasattr(context.scene.xxmi, 'destination_path'):
                path = context.scene.xxmi.destination_path
        
        # Endfield (EFMI)
        elif game == 'ArknightsEndfield':
            if hasattr(context.scene, 'efmi_tools_settings'):
                path = context.scene.efmi_tools_settings.mod_output_folder

        # Wuthering Waves (WWMI)
        elif game == 'WutheringWaves':
            if hasattr(context.scene, 'wwmi_tools_settings'):
                path = context.scene.wwmi_tools_settings.mod_output_folder

    # 2. Fallback to custom path if still empty
    if not path:
        path = settings.custom_path
        
    if not path:
        return None
        
    # Convert // relative paths to absolute
    abs_path = bpy.path.abspath(path)
    
    # 3. Handle Full Export Redirection (Neighboring place)
    if is_full and settings.use_neighbor_export:
        p = Path(abs_path)
        # Append _RZM suffix to the folder name
        abs_path = str(p.parent / (p.name + "_RZM"))

    return abs_path

def run_custom_scripts(context, target_path):
    """Executes post-export scripts defined in RZM settings."""
    rzm = context.scene.rzm
    settings = rzm.export_settings
    
    if not settings.show_custom_scripts:
        print("DEBUG: Skipping custom post-export scripts (show_custom_scripts=False)")
        return
        
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

def generate_readme(context, target_path, overwrite=False):
    """Generates a ReadMe.txt using the 3-part description system."""
    from .tier_ops import get_prefs
    rzm = context.scene.rzm
    meta = rzm.meta_data
    prefs = get_prefs(context)
    
    readme_path = os.path.join(target_path, "ReadMe.txt")
    if os.path.exists(readme_path) and not overwrite:
        print("DEBUG: ReadMe.txt already exists and overwrite is disabled. Skipping ReadMe generation.")
        return True
    
    # Dynamic Title: Character (Outfit)
    mod_title = f"{meta.character_name} ({meta.outfit_name})"
    
    # 3-Part Description
    pre = prefs.pre_description if prefs else ""
    lore = meta.description
    post = prefs.post_description if prefs else ""
    
    # Author from Global Prefs
    author = prefs.author_name if prefs else "UNKNOWN"

    content = f"""; ===========     ABOUT     =============
; "{mod_title}"
; Author: {author}
; Version: {meta.version_num}
; Game: {rzm.game.name}
; Keybind: {meta.menu_keybind}
; Requirements: {meta.requirements}
; Credits: {meta.community_respect}
; Generated by RZMenu Constructor

{pre}
{lore}
{post}

; ===========   TERMS OF USE   ==========
; Redistribution or resale of this mod is not allowed
; without permission.
"""
    try:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"RZM ReadMe Error: {e}")
        return False

class RZM_OT_InitializeMod(bpy.types.Operator):
    """Copies the Basic Pack files and creates the mod structure."""
    bl_idname = "rzm.initialize_mod"
    bl_label = "Initialize Mod Files"
    bl_description = "Copies scripts and shaders from the RZMenu Basic Pack into the mod folder"
    
    def execute(self, context):
        settings = context.scene.rzm.export_settings
        target_path = get_target_path(context)
        
        # Проверки на дурака
        if not target_path:
            self.report({'ERROR'}, "Path not set! Check XXMI settings or Custom Path.")
            return {'CANCELLED'}
            
        if not os.path.exists(target_path):
            try:
                os.makedirs(target_path, exist_ok=True)
            except Exception as e:
                self.report({'ERROR'}, f"Cannot create folder: {e}")
                return {'CANCELLED'}
            
        # 1. Ищем папку basic_pack внутри аддона
        # operators/export_manager.py -> (parent) -> operators -> (parent) -> RZMenu -> basic_pack
        addon_dir = Path(__file__).parent.parent
        basic_pack_src = addon_dir / "basic_pack"
        
        if not basic_pack_src.exists():
            self.report({'ERROR'}, f"Critical: 'basic_pack' folder missing in addon! Path: {basic_pack_src}")
            return {'CANCELLED'}
            
        from .tier_ops import get_prefs
        prefs = get_prefs(context)
        custom_basic_pack_src = None
        if prefs and prefs.custom_basic_pack:
            custom_basic_pack_src = Path(bpy.path.abspath(prefs.custom_basic_pack))
            if not custom_basic_pack_src.exists():
                self.report({'WARNING'}, f"Custom Basic Pack folder not found: {custom_basic_pack_src}")
                custom_basic_pack_src = None
            
        # 2. Копирование файлов
        copied_count = 0
        copied_from_core = set()
        
        try:
            # 2.1 Копирование файлов ядра (basic_pack)
            for root, dirs, files in os.walk(basic_pack_src):
                rel_path = Path(root).relative_to(basic_pack_src)
                target_dir = Path(target_path) / rel_path
                
                if not target_dir.exists():
                    target_dir.mkdir(parents=True, exist_ok=True)
                    
                for file in files:
                    src_file = Path(root) / file
                    dst_file = target_dir / file
                    
                    # Копируем если файла нет ИЛИ если разрешена перезапись
                    if not dst_file.exists() or settings.overwrite_scripts:
                        shutil.copy2(src_file, dst_file)
                        copied_count += 1
                        copied_from_core.add(str(dst_file.resolve()))
                        
            # 2.2 Копирование файлов кастомного пака поверх
            if custom_basic_pack_src:
                for root, dirs, files in os.walk(custom_basic_pack_src):
                    rel_path = Path(root).relative_to(custom_basic_pack_src)
                    target_dir = Path(target_path) / rel_path
                    
                    if not target_dir.exists():
                        target_dir.mkdir(parents=True, exist_ok=True)
                        
                    for file in files:
                        src_file = Path(root) / file
                        dst_file = target_dir / file
                        
                        # Перезаписываем если:
                        # - файла не было в target_path
                        # - или включена перезапись
                        # - или файл был только что скопирован из ядра
                        if not dst_file.exists() or settings.overwrite_scripts or str(dst_file.resolve()) in copied_from_core:
                            shutil.copy2(src_file, dst_file)
                            copied_count += 1
                            
        except Exception as e:
            self.report({'ERROR'}, f"Copy Failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # 3. Создаем ReadMe
        generate_readme(context, target_path, overwrite=settings.overwrite_scripts)
        
        self.report({'INFO'}, f"Success! Copied {copied_count} files to {os.path.basename(target_path)}.")
        
        # 4. Сразу обновляем атлас, чтобы все работало из коробки
        if hasattr(bpy.ops.rzm, 'export_atlas'):
            bpy.ops.rzm.export_atlas()
        
        return {'FINISHED'}

# Стандартная регистрация для оператора
classes_to_register = [
    RZM_OT_InitializeMod
]
