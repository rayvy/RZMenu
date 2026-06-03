import os
import sys
import bpy
from pathlib import Path
from .text_packer import get_text_mapping_for_j2
from .image_packer import get_image_mapping_for_j2
from .style_packer import pack_styles
from .element_static_map import export_element_static_map
from .element_blacklist import export_element_blacklist

# Add libs to sys.path so we can import jinja2
ADDON_DIR = Path(__file__).parent.parent
LIBS_DIR = ADDON_DIR / "libs"
if str(LIBS_DIR) not in sys.path:
    sys.path.append(str(LIBS_DIR))

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    # Fallback or error reporting if libs are missing
    print("RZMenu Error: jinja2 not found in libs directory!")
    Environment = None
    FileSystemLoader = None

class StubModFile:
    """Mock object for mod_file to prevent template errors during Quick Export."""
    def __init__(self):
        self.components = []
        self.extracted_object = None
        self.merged_object = None
        self.buffers = []
        self.textures = []
        self.cfg = None

class RZMenuJ2Exporter:
    """Standalone Jinja2 renderer for RZMenu templates."""
    
    def __init__(self, context):
        self.context = context
        self.template_dir = ADDON_DIR / "rztemplate"
        
        if Environment:
            self.env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
                keep_trailing_newline=True
            )
            
            # Add basic globals
            self.env.globals['enumerate'] = enumerate
            self.env.globals['zip'] = zip
            self.env.globals['len'] = len
        else:
            self.env = None

    def render(self, template_name="rz_uni.j2", menu_only=False) -> str:
        """Renders the specified template with the current scene context."""
        if not self.env:
            return "; ERROR: Jinja2 Environment not initialized!"
            
        template = self.env.get_template(template_name)
        
        # Build context
        mod_file = StubModFile()
        scene = self.context.scene
        if not menu_only:
            try:
                from ..utils.shape_export_filter import prepare_shape_config_export_runtime
                prepare_shape_config_export_runtime(scene.rzm)
            except Exception as e:
                print(f"[RZM] Shape export runtime prepare failed: {e}")

        # Pre-collect VFX vertex counts from curves before rendering template
        try:
            from ..utils.vfx_buffer_patcher import pre_collect_vfx_vertex_counts
            pre_collect_vfx_vertex_counts(self.context)
        except Exception as e:
            print(f"[RZM-VFX] Error pre-collecting VFX vertex counts: {e}")
        
        try:
            from ..operators.export_cache import get_cache
            export_cache = get_cache()
        except Exception:
            export_cache = None

        # 1. Pack Texts, Styles & Static Element Map
        elem_static_flags = {}
        try:
            from ..operators.export_manager import get_target_path
            export_path = get_target_path(self.context)
            if export_path:
                # This now updates scene.rzm.text_mapping_json internally
                get_text_mapping_for_j2(scene, export_path)
                get_image_mapping_for_j2(scene, export_path)
                pack_styles(scene, export_path)
                # Phase 0.5/0.5.5: Export ElementStaticMap and BlackList buffers
                if scene.rzm and scene.rzm.elements:
                    static_map_path = str(Path(export_path) / 'res' / 'element_static_map.buf')
                    elem_static_flags = export_element_static_map(
                        scene.rzm.elements, static_map_path, scene.rzm.image_mapping
                    )
                    blacklist_path = str(Path(export_path) / 'res' / 'element_blacklist.buf')
                    export_element_blacklist(scene.rzm.elements, blacklist_path)
                print(f"RZMenu: All resource buffers (text, images, styles, static_map) packed to {export_path}")
        except Exception as e:
            print(f"RZMenu Text Packing Error: {e}")

        ctx = {
            'scene': scene,
            'mod_file': mod_file,
            'rzm_is_quick_export': menu_only,
            'rzm_export_cache': export_cache,
            # Phase 0.5/0.5.5: static flags per element id for j2 template
            'elem_static_flags': elem_static_flags,
            # Placeholder variables for EFMI/XXMI specific logic
            'extracted_object': None,
            'merged_object': None,
            'mod_info': None,
            'buffers': [],
            'textures': [],
            'cfg': None,
        }
        
        return template.render(ctx)
