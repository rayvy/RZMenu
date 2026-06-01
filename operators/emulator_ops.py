import bpy
import os
import time
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, UndefinedError

class TextFormatter:
    @staticmethod
    def extract_name_parts(name):
        if not isinstance(name, str):
            name = getattr(name, 'name', str(name))
        name = name.replace('$', '').replace('-', ' ').replace('.', ' ').replace('_', ' ')
        return [x.lower().strip() for x in name.split(' ') if x.strip()]

    def format_name_camel_case(self, name):
        return ''.join(x.capitalize() for x in self.extract_name_parts(name))

    def format_ini_swapvar(self, name):
        parts = self.extract_name_parts(name)
        return f"$swapvar_{'_'.join([x for x in parts if x and x not in ['var', 'swap']])}"
    
    def format_ini_drawvar(self, name):
        parts = self.extract_name_parts(name)
        return f"$draw_{'_'.join([x for x in parts if x])}"

    def format_hotkeys(self, hotkeys, join_arg=' '):
        if not hotkeys: return []
        return [join_arg.join(b.upper().strip().split()) for b in hotkeys.split(';') if b.strip()]

class RZM_OT_EmulatorExport(bpy.types.Operator):
    """Fast export of mod configuration to Emulator folder (skip 3D models)."""
    bl_idname = "rzm.emulator_export"
    bl_label = "Fast Emulator Export"
    bl_description = "Exports .ini config only to testpolygon/3dmigoto/Mods for rapid testing"

    def execute(self, context):
        start_time = time.time()
        scene = context.scene
        rzm = scene.rzm
        
        # --- Foolproof: Save and temporarily switch Game Type ---
        original_game = rzm.game.selection
        if original_game != 'EMULATOR':
            rzm.game.selection = 'EMULATOR'
            # Force update name just in case update callback is slow
            rzm.game.name = 'EMULATOR'
            
        try:
            addon_dir = Path(__file__).parent.parent
            testpolygon_dir = addon_dir / "testpolygon"
            mods_dir = testpolygon_dir / "3dmigoto" / "Mods" / "RZEmulatorMod"
            
            if not mods_dir.exists():
                mods_dir.mkdir(parents=True, exist_ok=True)
                
            ini_path = mods_dir / "mod.ini"
            
            templates_path = addon_dir / "rztemplate"
            env = Environment(loader=FileSystemLoader(str(templates_path)))
            # Регистрация фильтра fromjson для парсинга метаданных анимации
            env.filters['fromjson'] = json.loads

            from ..utils.shape_export_filter import prepare_shape_config_export_runtime
            prepare_shape_config_export_runtime(rzm)
            
            # Simplified Dummy Objects for Test Export (Empty components skips model code)
            class DummyObject:
                def __init__(self, name="Dummy"):
                    self.name = name
                    self.index_count = 0
                    self.vertex_count = 0
                    self.components = [] # EMPTY - skip model export
                    self.vertex_groups = []
                    self.data = type('obj', (object,), {'polygons': [], 'loops': []})()

            from .tier_ops import get_prefs
            prefs = get_prefs(context)
            author = prefs.author_name if prefs else "UNKNOWN"
            mod_title = f"{rzm.meta_data.character_name} ({rzm.meta_data.outfit_name})"

            render_context = {
                'mod_file': {
                    'name': mod_title,
                    'author': author,
                    'version': rzm.version_num if hasattr(rzm, 'version_num') else "1.0.0",
                    'game': rzm.game,
                    'components': [],
                },
                'scene': scene,
                'extracted_object': DummyObject("Extracted"),
                'merged_object': DummyObject("Merged"),
                'mod_info': type('ModInfo', (object,), {
                    'required_efmi_version': type('V', (object,), {'as_float': lambda: 1.0})(),
                    'mod_name': mod_title,
                    'mod_author': author,
                    'mod_desc': rzm.meta_data.description,
                    'mod_link': "",
                    'mod_logo': Path("logo.dds")
                })(),
                'buffers': {},
                'textures': [],
                'cfg': rzm.export_settings,
                'enumerate': enumerate,
                'formatter': TextFormatter(),
            }

            template = env.get_template("rz_uni.j2")
            rendered_content = template.render(render_context)
            
            # Post-process: Remove ;DEL lines and extra whitespace
            lines = [line for line in rendered_content.split('\n') if not line.strip().startswith(';DEL')]
            final_output = '\n'.join(lines)
            
            with open(ini_path, "w", encoding='utf-8') as f:
                f.write(final_output)
                
            elapsed = time.time() - start_time
            self.report({'INFO'}, f"Export Success! {os.path.basename(ini_path)} generated in {elapsed:.2f}s")
            
        except TemplateSyntaxError as e:
            self.report({'ERROR'}, f"Jinja2 Syntax Error at line {e.lineno}: {e.message}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        finally:
            if original_game != 'EMULATOR':
                rzm.game.selection = original_game

        return {'FINISHED'}

classes_to_register = [
    RZM_OT_EmulatorExport,
]
