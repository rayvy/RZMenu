# RZMenu/operators/transform_segment_export.py
import os
import sys
from pathlib import Path

import bpy

from .export_manager import get_target_path


ADDON_DIR = Path(__file__).parent.parent
LIBS_DIR = ADDON_DIR / "libs"
if str(LIBS_DIR) not in sys.path:
    sys.path.append(str(LIBS_DIR))

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    Environment = None
    FileSystemLoader = None


def _build_template_context(context, export_cache):
    scene = context.scene
    return {
        "scene": scene,
        "rzm_is_quick_export": True,
        "rzm_export_cache": export_cache,
        "mod_file": None,
        "extracted_object": None,
        "merged_object": None,
        "mod_info": None,
        "buffers": {},
        "textures": [],
        "cfg": None,
    }


class RZM_OT_ExportTransformSegment(bpy.types.Operator):
    """Write experimental shape/VFX transform runtime into a separate disabled INI."""

    bl_idname = "rzm.export_transform_segment"
    bl_label = "Export Transform Segment"
    bl_description = "Experimental: write shape/VFX transform runtime to DISABLED<Character>.TRANSFORM.ini using the current export cache"
    bl_options = {"REGISTER"}

    template_name: bpy.props.StringProperty(default="rz_transform_segment.j2")

    def execute(self, context):
        if Environment is None:
            self.report({"ERROR"}, "Jinja2 is not available in RZMenu/libs.")
            return {"CANCELLED"}

        target_path = get_target_path(context)
        if not target_path:
            self.report({"ERROR"}, "Export path is not set.")
            return {"CANCELLED"}

        try:
            os.makedirs(target_path, exist_ok=True)
        except Exception as e:
            self.report({"ERROR"}, f"Cannot create export path: {e}")
            return {"CANCELLED"}

        try:
            from .export_cache import get_cache

            export_cache = get_cache()
        except Exception as e:
            self.report({"ERROR"}, f"Cannot read RZM export cache: {e}")
            return {"CANCELLED"}

        if not export_cache or not export_cache.get("components"):
            self.report({"ERROR"}, "RZM export cache is empty. Run Full Export or Game Buffers first.")
            return {"CANCELLED"}

        try:
            from ..core.ini_validation import validate_export_cache, validate_ini_text

            cache_result = validate_export_cache(export_cache)
            if not cache_result.ok:
                details = "; ".join(f"{i.code}: {i.message}" for i in cache_result.errors[:3])
                self.report({"ERROR"}, f"Export cache is invalid: {details}")
                return {"CANCELLED"}

            strict_result = validate_export_cache(export_cache, require_vertex_maps=True)
            if not strict_result.ok:
                print("[RZM Transform Segment] Cache vertex-map strict validation warnings:")
                for issue in strict_result.errors[:12]:
                    print(f"  - {issue.code}: {issue.message}")
                self.report({"WARNING"}, "Cache has missing/partial vertex maps. Segment written as experimental.")
        except Exception as e:
            print(f"[RZM Transform Segment] Cache validation skipped: {e}")
            validate_ini_text = None

        try:
            from ..utils.shape_export_filter import prepare_shape_config_export_runtime

            prepare_shape_config_export_runtime(context.scene.rzm)
        except Exception as e:
            print(f"[RZM Transform Segment] Shape runtime preparation failed: {e}")

        try:
            from ..utils.vfx_buffer_patcher import pre_collect_vfx_vertex_counts

            pre_collect_vfx_vertex_counts(context)
        except Exception as e:
            print(f"[RZM Transform Segment] VFX pre-collect failed: {e}")

        try:
            env = Environment(
                loader=FileSystemLoader(str(ADDON_DIR / "rztemplate")),
                trim_blocks=True,
                lstrip_blocks=True,
                keep_trailing_newline=True,
            )
            env.globals["enumerate"] = enumerate
            env.globals["zip"] = zip
            env.globals["len"] = len
            template = env.get_template(self.template_name)
            rendered = template.render(_build_template_context(context, export_cache))
        except Exception as e:
            self.report({"ERROR"}, f"Transform template render failed: {e}")
            import traceback

            traceback.print_exc()
            return {"CANCELLED"}

        try:
            if validate_ini_text is not None:
                ini_result = validate_ini_text(
                    rendered,
                    segment="transform",
                    require_mod_block_tags=True,
                    forbid_placeholders=True,
                )
                if not ini_result.ok:
                    details = "; ".join(f"{i.code}: {i.message}" for i in ini_result.errors[:3])
                    self.report({"ERROR"}, f"Rendered transform INI is invalid: {details}")
                    return {"CANCELLED"}
        except Exception as e:
            print(f"[RZM Transform Segment] Rendered INI validation skipped: {e}")

        try:
            from ..core.namespace_hash import namespace_from_context

            namespace = namespace_from_context(
                context,
                export_cache=export_cache,
                target_path=target_path,
                create_seed=True,
            )
            character = namespace.character_name
        except Exception as e:
            print(f"[RZM Transform Segment] Namespace resolve failed, using fallback: {e}")
            character = "CharacterName"
        output_path = os.path.join(target_path, f"DISABLED{character}.TRANSFORM.ini")

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(rendered)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to write transform segment: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Transform segment written: {os.path.basename(output_path)}")
        print(f"[RZM Transform Segment] Wrote {output_path}")
        return {"FINISHED"}


classes_to_register = [
    RZM_OT_ExportTransformSegment,
]
