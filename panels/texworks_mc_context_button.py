import bpy

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
    row = layout.row(align=True)
    row.operator("rzm.tw_mc_create_material", text="", icon='ADD')
    op = row.operator("rzm.tw_mc_ensure_material_node", text="", icon='NODETREE')
    op.rebuild_group = False
    op.connect_surface = False

def register():
    target_panel = getattr(bpy.types, "MATERIAL_PT_context_material", None)
    if target_panel:
        try:
            target_panel.prepend(draw_material_context_button)
        except Exception:
            try:
                target_panel.append(draw_material_context_button)
            except Exception as e:
                print(f"Error appending draw_material_context_button: {e}")

def unregister():
    target_panel = getattr(bpy.types, "MATERIAL_PT_context_material", None)
    if target_panel:
        try:
            target_panel.remove(draw_material_context_button)
        except Exception:
            pass
