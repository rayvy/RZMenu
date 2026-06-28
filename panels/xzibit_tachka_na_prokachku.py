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

    try:
        from ..utils.component_resolver import resolve_object_from_snapshot
        match, snapshot = resolve_object_from_snapshot(context, obj)
    except Exception:
        match, snapshot = None, {}

    info = box.column(align=True)
    info.scale_y = 0.82
    if not snapshot:
        info.label(text="Component resolver: no snapshot", icon='INFO')
        info.operator("rzm.cm_update_from_dump", text="Build snapshot", icon='FILE_REFRESH')
        return

    if not snapshot.get("supported", False):
        reason = snapshot.get("reason", "Unsupported or invalid snapshot")
        info.label(text=f"Component resolver: {reason}", icon='INFO')
        return

    stats = snapshot.get("stats", {})
    summary = (
        f"Resolver: {stats.get('components', 0)} comps / "
        f"{stats.get('parts', 0)} parts / {stats.get('mapped_objects', 0)} objects"
    )
    info.label(text=summary, icon='OUTLINER_OB_GROUP_INSTANCE')

    if match:
        part = match.get("part") or "<component root>"
        info.label(text=f"{obj.name}: {match.get('component', '<unknown>')} / {part}", icon='MESH_DATA')
        if match.get("collection"):
            info.label(text=f"Collection: {match['collection']}", icon='OUTLINER_COLLECTION')
    else:
        info.label(text=f"{obj.name}: not mapped by XXMI collection snapshot", icon='ERROR')

    component_name = match.get("component") if match else ""
    component = next(
        (item for item in snapshot.get("components", []) if item.get("name") == component_name),
        None,
    )
    if component:
        textures = component.get("textures", {})
        tex_bits = []
        for tex_name in ("Diffuse", "LightMap", "NormalMap", "MaterialMap", "GlowMap", "ExtraMap"):
            if tex_name in textures:
                formats = ",".join(textures[tex_name].get("formats", [])) or "?"
                tex_bits.append(f"{tex_name}:{formats}")
        if tex_bits:
            info.label(text="Textures: " + " | ".join(tex_bits[:4]), icon='TEXTURE')


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


def draw_solid_shading_preset_header(self, context):
    prefs = addon_prefs(context)
    if not (prefs and getattr(prefs, "dog_shit", False)):
        return

    space = getattr(context, "space_data", None)
    if not space or space.type != 'VIEW_3D':
        return

    layout = self.layout
    row = layout.row(align=True)
    flat_texture = row.operator("rzm.xzibit_solid_shading_preset", text="", icon='TEXTURE')
    flat_texture.preset = 'FLAT_TEXTURE'
    flat_attribute = row.operator("rzm.xzibit_solid_shading_preset", text="", icon='GROUP_VCOL')
    flat_attribute.preset = 'FLAT_ATTRIBUTE'

    row.separator()

    studio_texture = row.operator("rzm.xzibit_solid_shading_preset", text="", icon='TEXTURE')
    studio_texture.preset = 'STUDIO_TEXTURE'
    studio_material = row.operator("rzm.xzibit_solid_shading_preset", text="", icon='MATERIAL')
    studio_material.preset = 'STUDIO_MATERIAL'
    studio_attribute = row.operator("rzm.xzibit_solid_shading_preset", text="", icon='GROUP_VCOL')
    studio_attribute.preset = 'STUDIO_ATTRIBUTE'

    row.separator()

    no_outline = row.operator("rzm.xzibit_solid_shading_preset", text="", icon='MOD_OUTLINE')
    no_outline.preset = 'STUDIO_MATERIAL_NO_OUTLINE'


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
    if hasattr(bpy.types, "VIEW3D_HT_header"):
        bpy.types.VIEW3D_HT_header.append(draw_solid_shading_preset_header)
    print(f"[RZM TWAA] Material context hook patched {len(panel_patchers)} panel(s).")

def unregister():
    if hasattr(bpy.types, "VIEW3D_HT_header"):
        try:
            bpy.types.VIEW3D_HT_header.remove(draw_solid_shading_preset_header)
        except Exception:
            pass
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
