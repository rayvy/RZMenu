# RZMenu/operators/material_transfer_ops.py
import bpy
from bpy.props import StringProperty, IntProperty, EnumProperty

class RZM_OT_AddTransferDonor(bpy.types.Operator):
    bl_idname = "rzm.add_transfer_donor"
    bl_label = "Select Donor SubComponent"
    bl_options = {'UNDO'}

    target_comp: StringProperty()
    target_part: StringProperty()

    def get_donors_callback(self, context):
        items = []
        cm = context.scene.rzm.component_manager
        for comp in cm.components:
            for part in comp.parts:
                # Avoid adding self as donor
                if comp.name == self.target_comp and part.name == self.target_part:
                    continue
                identifier = f"{comp.name}:{part.name}"
                label = f"{comp.name} -> {part.name}"
                items.append((identifier, label, ""))
        if not items:
            items.append(("", "No other subcomponents available", ""))
        return items

    donor_selection: EnumProperty(
        name="Donor",
        description="Select the subcomponent to copy/transfer material from",
        items=get_donors_callback
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not self.donor_selection or self.donor_selection == "":
            return {'CANCELLED'}
        comp_name, part_name = self.donor_selection.split(":")

        cm = context.scene.rzm.component_manager
        target_part_obj = None
        for comp in cm.components:
            if comp.name == self.target_comp:
                for part in comp.parts:
                    if part.name == self.target_part:
                        target_part_obj = part
                        break

        if target_part_obj:
            # Check for duplicates
            for d in target_part_obj.donors:
                if d.component_name == comp_name and d.part_name == part_name:
                    self.report({'WARNING'}, "This donor is already added.")
                    return {'CANCELLED'}
            new_d = target_part_obj.donors.add()
            new_d.component_name = comp_name
            new_d.part_name = part_name
            self.report({'INFO'}, f"Added donor {comp_name} -> {part_name}")
            
            # Redraw UI
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            return {'FINISHED'}

        return {'CANCELLED'}

class RZM_OT_RemoveTransferDonor(bpy.types.Operator):
    bl_idname = "rzm.remove_transfer_donor"
    bl_label = "Remove Material Transfer Donor"
    bl_options = {'UNDO'}

    target_comp: StringProperty()
    target_part: StringProperty()
    donor_index: IntProperty()

    def execute(self, context):
        cm = context.scene.rzm.component_manager
        for comp in cm.components:
            if comp.name == self.target_comp:
                for part in comp.parts:
                    if part.name == self.target_part:
                        if 0 <= self.donor_index < len(part.donors):
                            part.donors.remove(self.donor_index)
                            # Redraw UI
                            for area in context.screen.areas:
                                if area.type == 'VIEW_3D':
                                    area.tag_redraw()
                            return {'FINISHED'}
        return {'CANCELLED'}

classes_to_register = [
    RZM_OT_AddTransferDonor,
    RZM_OT_RemoveTransferDonor,
]
