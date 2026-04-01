import bpy
import os
from bpy_extras.io_utils import ExportHelper

class RZM_OT_AMC_RefreshStats(bpy.types.Operator):
    bl_idname = "rzm.amc_refresh_stats"
    bl_label = "Refresh Stats"
    bl_description = "Refreshes the toggle and mesh count"

    def execute(self, context):
        auto_menu = context.scene.rzm.auto_menu
        
        # Collect toggles
        project_toggles = context.scene.rzm.toggle_definitions
        auto_menu.stat_toggles_count = len(project_toggles)
        
        # Count meshes with toggles
        meshes_with_toggles = set()
        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
            for key in obj.keys():
                if key.startswith("rzm.Toggle."):
                    meshes_with_toggles.add(obj.name)
                    break
                    
        auto_menu.stat_meshes_count = len(meshes_with_toggles)
        self.report({'INFO'}, f"Found {auto_menu.stat_toggles_count} toggles and {auto_menu.stat_meshes_count} meshes.")
        return {'FINISHED'}

class RZM_OT_AMC_PackTemplate(bpy.types.Operator, ExportHelper):
    bl_idname = "rzm.amc_pack_template"
    bl_label = "Pack .rzmct Template"
    bl_description = "Packs marked prefab elements and their dependencies into a .rzmct file"
    
    filename_ext = ".rzmct"
    filter_glob: bpy.props.StringProperty(
        default="*.rzmct",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        from ..core.rzmct_manager import pack_template
        success = pack_template(context, self.filepath)
        if success:
            self.report({'INFO'}, f"Successfully packed template to {self.filepath}")
        else:
            self.report({'ERROR'}, "Failed to pack template. See console for details.")
        return {'FINISHED'}

class RZM_OT_AMC_LoadTemplate(bpy.types.Operator):
    bl_idname = "rzm.amc_load_template"
    bl_label = "Load .rzmct Template"
    bl_description = "Loads a template configuration (does not apply to scene yet)"

    def execute(self, context):
        self.report({'INFO'}, "Load Template stub.")
        return {'FINISHED'}

class RZM_OT_AMC_BuildMenu(bpy.types.Operator):
    bl_idname = "rzm.amc_build_menu"
    bl_label = "Build Auto Menu"
    bl_description = "Generates the menu structure into the current scene based on the loaded template"

    def execute(self, context):
        self.report({'INFO'}, "Build Menu stub.")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AMC_RefreshStats,
    RZM_OT_AMC_PackTemplate,
    RZM_OT_AMC_LoadTemplate,
    RZM_OT_AMC_BuildMenu,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
