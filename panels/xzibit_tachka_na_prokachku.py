import bpy
import ast

from ..utils.gret_panel_patcher import PanelPatcher

def addon_prefs(context):
    addon_name = __package__.split(".")[0]
    addon = context.preferences.addons.get(addon_name)
    return addon.preferences if addon else None

def draw_material_context_button(self, context):
    prefs = addon_prefs(context)

    if not (
        prefs
        and getattr(prefs, "dog_shit", False)
        and context.object is not None
        and context.object.type == "MESH"
    ):
        return

    layout = self.layout
    col = layout.column(align=True)

    col.operator(
        "rzm.tw_mc_create_material",
        text="",
        icon='ADD'
    )

    op = col.operator(
        "rzm.tw_mc_ensure_material_node",
        text="",
        icon='NODETREE'
    )
    op.rebuild_group = False
    op.connect_surface = False


class RZMContextMaterialPanelPatcher(PanelPatcher):
    fallback_func = staticmethod(draw_material_context_button)
    panel_type = None

    def __init__(self):
        super().__init__()
        self._inserted = False

    def _addon_nodes(self):
        return ast.parse(
            "try:\n"
            "    target_layout = locals().get('col', self.layout)\n"
            "    addon = context.preferences.addons.get('RZMenu')\n"
            "    if not addon:\n"
            "        for addon_key, addon_entry in context.preferences.addons.items():\n"
            "            if str(addon_key).endswith('RZMenu'):\n"
            "                addon = addon_entry\n"
            "                break\n"
            "    prefs = addon.preferences if addon else None\n"
            "    if prefs and getattr(prefs, 'dog_shit', False) and context.object is not None and context.object.type == 'MESH':\n"
            "        col = target_layout.column(align=True)\n"
            "        col.operator('rzm.tw_mc_create_material', text='', icon='ADD')\n"
            "        op = col.operator('rzm.tw_mc_ensure_material_node', text='', icon='NODETREE')\n"
            "        op.rebuild_group = False\n"
            "        op.connect_surface = False\n"
            "except Exception:\n"
            "    pass"
        ).body

    def visit_FunctionDef(self, node):
        if node.name != "draw":
            return self.generic_visit(node)
        self._inserted = False
        node = self.generic_visit(node)
        if not self._inserted:
            node.body = self._addon_nodes() + node.body
        return node

    def visit_Expr(self, node):
        self.generic_visit(node)
        try:
            call = node.value
            is_context_menu = (
                getattr(call.func, "attr", "") == "menu"
                and call.args
                and getattr(call.args[0], "value", "") == "MATERIAL_MT_context_menu"
            )
            if is_context_menu:
                self._inserted = True
                return [node, *self._addon_nodes()]
        except Exception:
            pass
        return node


def material_context_panel_types():
    names = (
        "EEVEE_MATERIAL_PT_context_material",
        "MATERIAL_PT_context_material",
        "CYCLES_PT_context_material",
    )
    panels = []
    seen = set()
    for name in names:
        panel = getattr(bpy.types, name, None)
        if panel and panel not in seen:
            panels.append(panel)
            seen.add(panel)
    return panels


panel_patchers = []


def draw_xxmi_preparation_header(self, context):
    obj = context.object
    if not obj or obj.type != 'MESH':
        return

    layout = self.layout
    box = layout.box()
    row = box.row(align=True)
    row.operator("rzm.xzibit_xxmi_preparation", text="XXMI Preparation", icon='TOOL_SETTINGS')

    selected_meshes = [
        item for item in context.selected_objects
        if item and item.type == 'MESH' and item.data
    ]
    if len(selected_meshes) == 2 and context.active_object in selected_meshes:
        row.operator(
            "rzm.xzibit_xxmi_preparation_with_weights",
            text="",
            icon='MOD_DATA_TRANSFER',
        )


def draw_uv_texcoord_quick_button(self, context):
    obj = context.object
    if not obj or obj.type != 'MESH':
        return

    layout = self.layout
    row = layout.row(align=True)
    row.operator(
        "rzm.xzibit_rename_active_uv_texcoord",
        text="Active to TEXCOORD.xy",
        icon='UV_DATA',
    )


def draw_color_attribute_quick_button(self, context):
    obj = context.object
    if not obj or obj.type != 'MESH':
        return

    layout = self.layout
    row = layout.row(align=True)
    row.operator(
        "rzm.xzibit_create_color_attribute",
        text="Create / Activate COLOR",
        icon='GROUP_VCOL',
    )


def register():
    panel_patchers.clear()
    for panel_type in material_context_panel_types():
        patcher = RZMContextMaterialPanelPatcher()
        patcher.panel_type = panel_type
        patcher.patch(debug=False)
        panel_patchers.append(patcher)
    if hasattr(bpy.types, "DATA_PT_context_mesh"):
        bpy.types.DATA_PT_context_mesh.prepend(draw_xxmi_preparation_header)
    if hasattr(bpy.types, "DATA_PT_uv_texture"):
        bpy.types.DATA_PT_uv_texture.append(draw_uv_texcoord_quick_button)
    if hasattr(bpy.types, "DATA_PT_vertex_colors"):
        bpy.types.DATA_PT_vertex_colors.append(draw_color_attribute_quick_button)
    print(f"[RZM TWAA] Material context hook patched {len(panel_patchers)} panel(s).")

def unregister():
    if hasattr(bpy.types, "DATA_PT_vertex_colors"):
        try:
            bpy.types.DATA_PT_vertex_colors.remove(draw_color_attribute_quick_button)
        except Exception:
            pass
    if hasattr(bpy.types, "DATA_PT_uv_texture"):
        try:
            bpy.types.DATA_PT_uv_texture.remove(draw_uv_texcoord_quick_button)
        except Exception:
            pass
    if hasattr(bpy.types, "DATA_PT_context_mesh"):
        try:
            bpy.types.DATA_PT_context_mesh.remove(draw_xxmi_preparation_header)
        except Exception:
            pass
    for patcher in reversed(panel_patchers):
        patcher.unpatch()
    panel_patchers.clear()
