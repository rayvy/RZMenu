import bpy

class RZM_ST_OT_BodyRenamePlaceholder(bpy.types.Operator):
    bl_idname = "rzm_st.body_rename_placeholder"
    bl_label = "Rename Components"
    bl_description = "Body rename feature (Coming Soon)"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        # We keep this disabled to show a disabled "Coming Soon" button
        return False

    def execute(self, context):
        return {'FINISHED'}

classes_to_register = [
    RZM_ST_OT_BodyRenamePlaceholder,
]
