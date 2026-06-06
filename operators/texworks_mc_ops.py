import bpy

from ..utils import texworks_mc


def trigger_refresh():
    try:
        from .texworks_ops import trigger_refresh as refresh
        refresh()
    except Exception:
        pass


class RZM_OT_TwMcCreateMaterial(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_create_material"
    bl_label = "Create RZM Material"
    bl_description = "Create and assign a new material with the RZM TexWorks MC node group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            mat = texworks_mc.create_empty_material(context, assign=True)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Created material: {mat.name}")
        return {'FINISHED'}


class RZM_OT_TwMcQuestionDummy(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_question_dummy"
    bl_label = "RZM Material Hook Probe"
    bl_description = "Diagnostic no-op button for the native material panel hook"
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.report({'INFO'}, "RZM material panel hook is active")
        return {'FINISHED'}


class RZM_OT_TwMcEnsureMaterialNode(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_ensure_material_node"
    bl_label = "Add RZM MC Node"
    bl_description = "Add or update the RZM TexWorks MC node group in the active material"
    bl_options = {'REGISTER', 'UNDO'}

    rebuild_group: bpy.props.BoolProperty(
        name="Rebuild Group Definition",
        default=False,
        description="Force rebuild the shared RZM TexWorks Material node group schema",
    )
    connect_surface: bpy.props.BoolProperty(
        name="Connect Preview Surface",
        default=False,
        description="Connect the node group's preview shader output to Material Output",
    )

    def execute(self, context):
        mat = context.object.active_material if context.object else None
        try:
            texworks_mc.ensure_material_node(
                mat,
                rebuild_group=self.rebuild_group,
                connect_surface=self.connect_surface,
            )
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, f"RZM MC node ready: {mat.name}")
        return {'FINISHED'}


class RZM_OT_TwMcRebuildCluster(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_rebuild_cluster"
    bl_label = "Rebuild MC Cluster"
    bl_description = "Rebuild active material cluster, create preview UV, export PNG files, and register cluster files"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            cluster = texworks_mc.rebuild_active_material_cluster(context)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Rebuilt/exported {len(cluster.get('images', {}))} cluster PNG(s): {cluster['atlas_size'][0]}x{cluster['atlas_size'][1]}"
        )
        return {'FINISHED'}


class RZM_OT_TwMcExportCluster(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_export_cluster"
    bl_label = "Export MC Preview PNG"
    bl_description = "Export active material cluster from the current RZAutoAtlas.UV.preview layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            cluster = texworks_mc.export_active_preview_cluster(context)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported MC preview: {len(cluster.get('images', {}))} PNG(s)")
        return {'FINISHED'}


class RZM_OT_TwMcApplyCluster(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_apply_cluster"
    bl_label = "Apply MC Cluster"
    bl_description = "Export PNG files, replace material images, and destructively apply packed UV layout"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            _cluster, result = texworks_mc.apply_active_preview_cluster(context)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Applied MC cluster: {len(result['changed_objects'])} object(s), {len(result['changed_nodes'])} image node(s)"
        )
        return {'FINISHED'}


class RZM_OT_TwMcBuildAutoAtlasLayout(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_build_autoatlas_layout"
    bl_label = "Build MC TexWorks Layout"
    bl_description = "Rebuild all TWAA RZAutoAtlas blocks from registered material cluster PNGs and write post-export TEXCOORD params"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            layout_summary = texworks_mc.rebuild_texworks_autoatlas_blocks(context)
            trigger_refresh()
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Built TWAA layout: {layout_summary.get('materials', 0)} material(s), atlas={layout_summary.get('atlas_size', [0, 0])}"
        )
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_TwMcCreateMaterial,
    RZM_OT_TwMcQuestionDummy,
    RZM_OT_TwMcEnsureMaterialNode,
    RZM_OT_TwMcRebuildCluster,
    RZM_OT_TwMcExportCluster,
    RZM_OT_TwMcApplyCluster,
    RZM_OT_TwMcBuildAutoAtlasLayout,
]
