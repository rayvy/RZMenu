import traceback

import bpy


MATERIALS = ["mat_CastoriceBodyE_Diffuse", "ZRPanties"]
BLEND_PATH = "G:/XXMI/ZZMI/Mods/Projects/YiXuanSuccubusSetupX.blend"
TARGET_PATH = "G:/XXMI/ZZMI/Mods/@RayvichYiXuanSporty"


def ensure_addon():
    try:
        bpy.ops.preferences.addon_enable(module="RZMenu")
    except Exception as exc:
        print(f"[TW_MC_MULTI] addon_enable skipped/failed: {exc}")


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
                print(f"[TW_MC_MULTI] Active object={obj.name} material={mat.name} slot={index}")
                return obj
    raise RuntimeError(f"No mesh object uses material: {mat_name}")


def main():
    ensure_addon()
    bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
    ensure_addon()
    from RZMenu.utils import texworks_mc

    last_cluster = None
    for mat_name in MATERIALS:
        select_material_object(mat_name)
        cluster = texworks_mc.rebuild_active_material_cluster(bpy.context)
        texworks_mc.export_cluster_pngs(bpy.context, cluster, target_path=TARGET_PATH)
        texworks_mc.sync_texworks_data(bpy.context, cluster)
        last_cluster = cluster

    rzm = bpy.context.scene.rzm
    print(f"[TW_MC_MULTI] tw_mc_files={[(e.material_key, e.slot_name, list(e.resolution)) for e in rzm.tw_mc_files]}")
    for block in rzm.tw_blocks:
        if block.name.startswith("RZAutoAtlas."):
            comps = [(comp.name, list(comp.rect)) for comp in block.components]
            print(f"[TW_MC_MULTI] block={block.name} comps={comps}")
    for obj in bpy.data.objects:
        if obj.type == "MESH" and "RZM_TW_MC_COMPONENT" in obj:
            print(
                f"[TW_MC_MULTI] obj={obj.name} comp={obj['RZM_TW_MC_COMPONENT']} "
                f"pos_size={list(obj['TEXCOORD_POS_SIZE'])} rect={list(obj['RZM_TW_MC_RECT'])} "
                f"atlas={list(obj['RZM_TW_MC_ATLAS_SIZE'])} inv=({obj['RZM_TW_MC_POST_INVERT_X']},{obj['RZM_TW_MC_POST_INVERT_Y']})"
            )
    return 0 if last_cluster else 1


try:
    raise SystemExit(main())
except Exception:
    traceback.print_exc()
    raise SystemExit(1)
