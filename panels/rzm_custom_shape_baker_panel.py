# RZMenu/panels/rzm_custom_shape_baker_panel.py
import bpy

def draw_shape_key_baker_tools(self, context):
    obj = context.object
    if not obj or obj.type != 'MESH':
        return

    layout = self.layout
    
    # Create a clean box for RZ Shape Key tools
    box = layout.box()
    box.label(text="RZ Shape Key Tools", icon='TOOL_SETTINGS')
    
    # 1. Bake Shape Keys button
    selected_meshes = [item for item in context.selected_objects if item and item.type == 'MESH']
    row_bake = box.row(align=True)
    
    if len(selected_meshes) == 2 and obj in selected_meshes:
        donor = [item for item in selected_meshes if item != obj][0]
        row_bake.operator(
            "rzm.bake_shape_keys_custom", 
            text=f"Bake Shapes from {donor.name}", 
            icon='SHAPEKEY_DATA'
        )
    else:
        row_disabled = row_bake.row()
        row_disabled.enabled = False
        row_disabled.operator(
            "rzm.bake_shape_keys_custom", 
            text="Bake Shapes (Select 2 Meshes)", 
            icon='SHAPEKEY_DATA'
        )

    # 2. Reset Shape Key Vertices button (only visible when a non-Basis shape key is active)
    if obj.data.shape_keys and obj.active_shape_key and obj.active_shape_key != obj.data.shape_keys.reference_key:
        row_reset = box.row(align=True)
        row_reset.operator(
            "rzm.reset_shape_key_vertices", 
            text=f"Reset Vertices ({obj.active_shape_key.name})", 
            icon='LOOP_FORWARDS'
        )

def register():
    if hasattr(bpy.types, "DATA_PT_shape_keys"):
        bpy.types.DATA_PT_shape_keys.append(draw_shape_key_baker_tools)

def unregister():
    if hasattr(bpy.types, "DATA_PT_shape_keys"):
        try:
            bpy.types.DATA_PT_shape_keys.remove(draw_shape_key_baker_tools)
        except Exception:
            pass
