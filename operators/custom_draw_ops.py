# RZMenu/operators/custom_draw_ops.py
import bpy

class RZM_OT_AddCustomDraw(bpy.types.Operator):
    """Adds a Custom Draw property to the active object."""
    bl_idname = "rzm.add_custom_draw"
    bl_label = "Add Custom Draw"
    bl_options = {'REGISTER', 'UNDO'}

    draw_type: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}
        
        prop_name = f"CustomDraw.{self.draw_type}"
        obj[prop_name] = 1
        
        return {'FINISHED'}

class RZM_OT_RemoveCustomDraw(bpy.types.Operator):
    """Removes a Custom Draw property from the active object."""
    bl_idname = "rzm.remove_custom_draw"
    bl_label = "Remove Custom Draw"
    bl_options = {'REGISTER', 'UNDO'}

    prop_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}
        
        if self.prop_name in obj:
            del obj[self.prop_name]
        
        return {'FINISHED'}

class RZM_OT_ToggleSkipDraw(bpy.types.Operator):
    """Toggles the SkipDraw property on the active object."""
    bl_idname = "rzm.toggle_skip_draw"
    bl_label = "Toggle Skip Draw"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}
        
        current_val = obj.get("SkipDraw", False)
        # If it doesn't exist or is False, set to True (1)
        # If it's True, set to False (0)
        obj["SkipDraw"] = 1 if not current_val else 0
        
        return {'FINISHED'}

class RZM_MT_AddCustomDrawMenu(bpy.types.Menu):
    bl_label = "Add Custom Draw"
    bl_idname = "RZM_MT_add_custom_draw_menu"

    def draw(self, context):
        layout = self.layout
        draw_options = [
            "FRAMETRACE",
            "XRAY.ENHANCED",
            "XRAY",
            "XRAY.BACK",
            "XRAY.FRONT",
            "XRAY.ENDFIELD",
            "TRANSPARENT",
            "TRANSPARENT.OUTER",
            "TRANSPARENT.INNER",
            "TRANSPARENT.ENDFIELD"
        ]
        
        for opt in draw_options:
            op = layout.operator("rzm.add_custom_draw", text=opt)
            op.draw_type = opt

class RZM_OT_SetHoverMode(bpy.types.Operator):
    """Sets the rzm.Hover detection mode on the active object.
    
    Mode values:
      0 = remove property (no hover/click detection)
      1 = Collider          – registers in ObjectMap, no draw changes (Hover)
      2 = HideWhenHovered   – hidden when cursor is over it
      3 = AppearWhenHovered – visible only when cursor is over it
      4 = ClickCollider     – registers in ObjectMap on click, no draw changes
      5 = HideWhenClicked   – hidden when clicked
      6 = AppearWhenClicked – visible only when clicked
    """
    bl_idname = "rzm.set_hover_mode"
    bl_label = "Set Hover Mode"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.IntProperty(
        name="Mode",
        default=0,
        min=0, max=6
    )

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}

        if self.mode == 0:
            # Remove the property entirely
            if "rzm.Hover" in obj:
                del obj["rzm.Hover"]
        else:
            obj["rzm.Hover"] = self.mode

        return {'FINISHED'}


classes_to_register = (
    RZM_OT_AddCustomDraw,
    RZM_OT_RemoveCustomDraw,
    RZM_OT_ToggleSkipDraw,
    RZM_OT_SetHoverMode,
    RZM_MT_AddCustomDrawMenu,
)
