import bpy
import ast

from ..utils.gret_panel_patcher import PanelPatcher

def addon_prefs(context):
    addon_name = __package__.split(".")[0]
    addon = context.preferences.addons.get(addon_name)
    return addon.preferences if addon else None

def draw_material_context_button(self, context):
    prefs = addon_prefs(context)

    layout = self.layout
    row = layout.row(align=True)
    row.operator("rzm.tw_mc_question_dummy", text="", icon='QUESTION')
    if not (
        prefs
        and getattr(prefs, "dog_shit", False)
        and context.object is not None
        and context.object.type == "MESH"
    ):
        return
    row.operator("rzm.tw_mc_create_material", text="", icon='ADD')
    op = row.operator("rzm.tw_mc_ensure_material_node", text="", icon='NODETREE')
    op.rebuild_group = False
    op.connect_surface = False


class RZMContextMaterialPanelPatcher(PanelPatcher):
    fallback_func = staticmethod(draw_material_context_button)
    panel_type = None

    def visit_FunctionDef(self, node):
        super().generic_visit(node)
        if node.name != "draw":
            return node
        addon = ast.parse(
            "try:\n"
            "    row = self.layout.row(align=True)\n"
            "    row.operator('rzm.tw_mc_question_dummy', text='', icon='QUESTION')\n"
            "    addon = context.preferences.addons.get('RZMenu')\n"
            "    if not addon:\n"
            "        for addon_key, addon_entry in context.preferences.addons.items():\n"
            "            if str(addon_key).endswith('RZMenu'):\n"
            "                addon = addon_entry\n"
            "                break\n"
            "    prefs = addon.preferences if addon else None\n"
            "    if prefs and getattr(prefs, 'dog_shit', False) and context.object is not None and context.object.type == 'MESH':\n"
            "        row.operator('rzm.tw_mc_create_material', text='', icon='ADD')\n"
            "        op = row.operator('rzm.tw_mc_ensure_material_node', text='', icon='NODETREE')\n"
            "        op.rebuild_group = False\n"
            "        op.connect_surface = False\n"
            "except Exception:\n"
            "    pass"
        )
        node.body = addon.body + node.body
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


def register():
    panel_patchers.clear()
    for panel_type in material_context_panel_types():
        patcher = RZMContextMaterialPanelPatcher()
        patcher.panel_type = panel_type
        patcher.patch(debug=False)
        panel_patchers.append(patcher)
    print(f"[RZM TWAA] Material context hook patched {len(panel_patchers)} panel(s).")

def unregister():
    for patcher in reversed(panel_patchers):
        patcher.unpatch()
    panel_patchers.clear()
