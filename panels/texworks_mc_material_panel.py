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

    row = layout.row(align=True)
    row.operator("rzm.tw_mc_create_material", text="New RZM Material", icon='ADD')
    op = row.operator("rzm.tw_mc_ensure_material_node", text="Add/Update Node", icon='NODETREE')
    op.rebuild_group = False
    op.connect_surface = False

    row = layout.row(align=True)
    op = row.operator("rzm.tw_mc_ensure_material_node", text="Connect Preview", icon='MATERIAL')
    op.rebuild_group = False
    op.connect_surface = True
    op = row.operator("rzm.tw_mc_ensure_material_node", text="Rebuild Schema", icon='FILE_REFRESH')
    op.rebuild_group = True
    op.connect_surface = False

    layout.separator()
    row = layout.row(align=True)
    row.operator("rzm.tw_mc_rebuild_cluster", text="Rebuild", icon='FILE_REFRESH')
    if texworks_mc.active_material_has_preview_uv(context):
        row.operator("rzm.tw_mc_export_cluster", text="Export", icon='EXPORT')
    row.operator("rzm.tw_mc_apply_cluster", text="Apply", icon='CHECKMARK')
    row.operator("rzm.tw_mc_fix_texture_steps", text="", icon='MOD_UVPROJECT')
    row.operator("rzm.tw_mc_export_material_textures", text="", icon='IMAGE_DATA')
    row.operator("rzm.tw_mc_select_preview_material_objects", text="", icon='UV_SYNC_SELECT')

    if mc:
        box = layout.box()
        box.prop(mc, "enabled", text="Material Combiner")
        box.prop(mc, "auto_assign_registered_clusters", text="Auto Assign Registered Clusters")
        row = box.row(align=True)
        row.prop(mc, "default_resolution", text="Default Fallback")
        row.prop(mc, "reference_slot", text="")
        row = box.row(align=True)
        row.prop(mc, "vertex_margin_px", text="Margin")
        row.prop(mc, "pack_gap_px", text="Gap")
        row.prop(mc, "max_atlas_size", text="Max")
        box.prop(mc, "max_raster_pixels", text="CPU Pixel Limit")

    if mat:
        node = texworks_mc.find_material_group_node(mat)
        if node and "Default Resolution X" in node.inputs and "Default Resolution Y" in node.inputs:
            box = layout.box()
            box.label(text="Material Fallback Resolution", icon='NODETREE')
            row = box.row(align=True)
            row.prop(node.inputs["Default Resolution X"], "default_value", text="X")
            row.prop(node.inputs["Default Resolution Y"], "default_value", text="Y")
            box.label(text="Allowed: 128, 256, 512, 1024, 2048, 4096", icon='INFO')
        layout.label(text=f"Active: {mat.name}", icon='MATERIAL')
    else:
        layout.label(text="No active material", icon='ERROR')


class RZM_PT_TexWorksMCShaderPanel(bpy.types.Panel):
    bl_label = "RZ Construct Material Panel"
    bl_idname = "RZM_PT_texworks_mc_shader_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'RZ Construct'

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
    RZM_PT_TexWorksMCShaderPanel,
]
