import bpy

from ..utils import texworks_mc


def addon_prefs(context):
    addon_name = __package__.split(".")[0]
    addon = context.preferences.addons.get(addon_name)
    return addon.preferences if addon else None


def draw_mc_tools(layout, context):
    obj = context.object
    mat = obj.active_material if obj else None
    rzm = context.scene.rzm
    mc = getattr(rzm, "tw_mc", None)

    # ── Node management ────────────────────────────────────────────────
    row = layout.row(align=True)
    row.operator("rzm.tw_mc_create_material",        text="New RZM Material", icon='ADD')
    op = row.operator("rzm.tw_mc_ensure_material_node", text="Add/Update Node", icon='NODETREE')
    op.rebuild_group = False
    op.connect_surface = False

    row = layout.row(align=True)
    op = row.operator("rzm.tw_mc_ensure_material_node", text="Connect Preview", icon='MATERIAL')
    op.rebuild_group = False
    op.connect_surface = True
    op = row.operator("rzm.tw_mc_ensure_material_node", text="Rebuild Schema",  icon='FILE_REFRESH')
    op.rebuild_group = True
    op.connect_surface = False

    layout.separator()

    # ── Export / atlas ─────────────────────────────────────────────────
    row = layout.row(align=True)
    row.operator("rzm.tw_mc_rebuild_cluster",  text="Rebuild",  icon='FILE_REFRESH')
    if texworks_mc.active_material_has_preview_uv(context):
        row.operator("rzm.tw_mc_export_cluster", text="Export", icon='EXPORT')
    row.operator("rzm.tw_mc_apply_cluster",           text="Apply",   icon='CHECKMARK')
    row.operator("rzm.tw_mc_fix_texture_steps",       text="",        icon='MOD_UVPROJECT')
    row.operator("rzm.tw_mc_export_material_textures", text="",       icon='IMAGE_DATA')
    row.operator("rzm.tw_mc_select_preview_material_objects", text="", icon='UV_SYNC_SELECT')

    if mc:
        box = layout.box()
        box.prop(mc, "enabled",                         text="Material Combiner")
        box.prop(mc, "auto_assign_registered_clusters", text="Auto Assign Registered Clusters")
        row = box.row(align=True)
        row.prop(mc, "default_resolution", text="Default Fallback")
        row.prop(mc, "reference_slot",     text="")
        row = box.row(align=True)
        row.prop(mc, "vertex_margin_px", text="Margin")
        row.prop(mc, "pack_gap_px",      text="Gap")
        row.prop(mc, "max_atlas_size",   text="Max")
        box.prop(mc, "max_raster_pixels", text="CPU Pixel Limit")

    if mat:
        node = texworks_mc.find_material_group_node(mat)

        # ── Fallback resolution (shown on the node itself) ─────────────
        if node and "Default Resolution X" in node.inputs and "Default Resolution Y" in node.inputs:
            box = layout.box()
            box.label(text="Texture Export Resolution", icon='NODETREE')
            row = box.row(align=True)
            row.prop(node.inputs["Default Resolution X"], "default_value", text="X")
            row.prop(node.inputs["Default Resolution Y"], "default_value", text="Y")
            box.label(text="Allowed: 128 / 256 / 512 / 1024 / 2048 / 4096", icon='INFO')

        layout.separator()

        # ── TWAA export toggle ─────────────────────────────────────────
        box = layout.box()
        box.label(text=f"Material: {mat.name}", icon='MATERIAL')
        box.prop(mat, "disable_twaa_export", text="Disable TWAA Sync Export")

        # ── Game preset ────────────────────────────────────────────────
        current_preset = mat.get("rzm_preset", "—")
        box2 = layout.box()
        box2.label(text=f"Active preset: {current_preset}", icon='SHADERFX')
        box2.operator("rzm.tw_mc_apply_game_preset", text="Re-Apply Game Preset", icon='PLAY')
    else:
        layout.label(text="No active material", icon='ERROR')


# ── Operator: apply / re-apply game preset ─────────────────────────────────
class RZM_OT_ApplyGamePreset(bpy.types.Operator):
    """Re-apply the game-specific PBR preset wiring to the shared node group"""
    bl_idname = "rzm.tw_mc_apply_game_preset"
    bl_label  = "Apply Game Preset"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.active_material is not None)

    def execute(self, context):
        mat  = context.object.active_material
        rzm  = context.scene.rzm
        game = rzm.game.selection if rzm and hasattr(rzm, "game") else ""
        texworks_mc.apply_game_preset(mat, game)
        preset = mat.get("rzm_preset", "DEFAULT")
        self.report({'INFO'}, f"Applied preset: {preset}")
        return {'FINISHED'}


class RZM_PT_TexWorksMCShaderPanel(bpy.types.Panel):
    bl_label       = "RZ Construct Material Panel"
    bl_idname      = "RZM_PT_texworks_mc_shader_panel"
    bl_space_type  = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category    = 'RZ Construct'

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return bool(
            context.object is not None
            and context.object.type == "MESH"
            and space
            and space.type == 'NODE_EDITOR'
            and getattr(space, "tree_type", "") == 'ShaderNodeTree'
        )

    def draw(self, context):
        draw_mc_tools(self.layout, context)


classes_to_register = [
    RZM_OT_ApplyGamePreset,
    RZM_PT_TexWorksMCShaderPanel,
]
