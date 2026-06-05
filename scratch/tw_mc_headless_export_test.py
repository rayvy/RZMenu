import os
import sys
import traceback

import bpy


MAT_NAME = sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].startswith("-") else "mat_CastoriceBodyE_Diffuse"
BLEND_PATH = "G:/XXMI/ZZMI/Mods/Projects/YiXuanSuccubusSetupX.blend"
TARGET_PATH = "G:/XXMI/ZZMI/Mods/@RayvichYiXuanSporty"


def ensure_addon():
    try:
        bpy.ops.preferences.addon_enable(module="RZMenu")
    except Exception as exc:
        print(f"[TW_MC_TEST] addon_enable skipped/failed: {exc}")


def select_material_object(mat_name):
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        raise RuntimeError(f"Material not found: {mat_name}")

    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for index, slot in enumerate(obj.material_slots):
            if slot.material == mat:
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                obj.active_material_index = index
                print(f"[TW_MC_TEST] Active object={obj.name} material={mat.name} slot={index}")
                return obj
    raise RuntimeError(f"No mesh object uses material: {mat_name}")


def main():
    ensure_addon()
    if bpy.data.filepath.replace("\\", "/").lower() != BLEND_PATH.lower():
        bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
        ensure_addon()
    select_material_object(MAT_NAME)

    from RZMenu.utils import texworks_mc

    cluster = texworks_mc.rebuild_active_material_cluster(bpy.context)
    print(f"[TW_MC_TEST] rebuilt images={list(cluster.get('images', {}).keys())}")
    written = texworks_mc.export_cluster_pngs(bpy.context, cluster, target_path=TARGET_PATH)
    print(f"[TW_MC_TEST] written={written}")
    texworks_mc.sync_texworks_data(bpy.context, cluster)
    print("[TW_MC_TEST] sync done")
    rzm = bpy.context.scene.rzm
    for block in rzm.tw_blocks:
        if block.name.startswith("RZAutoAtlas."):
            print(f"[TW_MC_TEST] block={block.name} components={[comp.name for comp in block.components]}")
    return 0


try:
    raise SystemExit(main())
except Exception:
    traceback.print_exc()
    raise SystemExit(1)
