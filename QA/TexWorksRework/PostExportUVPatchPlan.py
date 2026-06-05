import json
import os

import bpy


RANGE_JSON_PROP = "RZM_EXPORT_RANGE_JSON"
CLUSTER_JSON_PROP = "rzm_autoatlas_cluster_manifest_json"


def iter_export_range_objects():
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        raw = obj.get(RANGE_JSON_PROP)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "component": obj.get("RZM_EXPORT_COMPONENT", ""),
                "vb_offset": int(obj.get("RZM_EXPORT_VB_OFFSET", 0)),
                "vb_count": int(obj.get("RZM_EXPORT_VB_COUNT", 0)),
                "vb_end": int(obj.get("RZM_EXPORT_VB_END", 0)),
            }
        yield obj, data


def load_cluster_manifest(context):
    raw = context.scene.get(CLUSTER_JSON_PROP)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:
        print(f"[RZM QA] Failed to parse cluster manifest: {exc}")
        return None


def build_patch_plan(context):
    manifest = load_cluster_manifest(context)
    ranges = []

    for obj, data in iter_export_range_objects():
        ranges.append({
            "object": obj.name,
            "component": data.get("component", ""),
            "part_fullname": data.get("part_fullname", ""),
            "vb_offset": int(data.get("vb_offset", 0)),
            "vb_count": int(data.get("vb_count", 0)),
            "vb_end": int(data.get("vb_end", 0)),
            "is_robust": bool(data.get("is_robust", False)),
            "has_vertex_map": bool(data.get("has_vertex_map", False)),
        })

    return {
        "schema": 1,
        "kind": "RZ_POST_EXPORT_UV_PATCH_PLAN_QA",
        "cluster_material": manifest.get("active_material") if manifest else None,
        "cluster_uv_layer": manifest.get("uv_layer") if manifest else None,
        "cluster_atlas_size": manifest.get("atlas_size") if manifest else None,
        "cluster_groups": manifest.get("groups", []) if manifest else [],
        "ranges": ranges,
        "notes": [
            "Dry-run only. Does not patch buffers.",
            "Future patcher should use export cache/ranges as authority and cluster manifest as UV transform source.",
        ],
    }


def write_patch_plan(context):
    plan = build_patch_plan(context)
    blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
    out_dir = os.path.join(blend_dir, "RZAutoAtlasQA")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "post_export_uv_patch_plan.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, sort_keys=True)
    print(f"[RZM QA] Wrote post-export UV patch plan: {path}")
    print(f"[RZM QA] Ranges: {len(plan['ranges'])}, groups: {len(plan['cluster_groups'])}")
    return path


class RZM_QA_OT_WritePostExportUVPatchPlan(bpy.types.Operator):
    bl_idname = "rzm_qa_texworks_atlas.write_post_export_uv_patch_plan"
    bl_label = "Write Post-Export UV Patch Plan"
    bl_description = "Dry-run metadata export for future post-export TEXCOORD buffer patching"

    def execute(self, context):
        path = write_patch_plan(context)
        self.report({"INFO"}, f"Wrote patch plan: {os.path.basename(path)}")
        return {"FINISHED"}


CLASSES = (RZM_QA_OT_WritePostExportUVPatchPlan,)


def register():
    for cls in CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()
    print("RZM QA PostExportUVPatchPlan registered.")
