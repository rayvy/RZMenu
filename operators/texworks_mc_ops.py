import json

import bpy

from ..utils import texworks_mc


def trigger_refresh():
    try:
        from .texworks_ops import trigger_refresh as refresh
        refresh()
    except Exception:
        pass


class RZM_OT_TwMcCalculateCluster(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_calculate_cluster"
    bl_label = "Calculate MC Cluster"
    bl_description = "Analyze the active material cluster and write a manifest without exporting PNG files"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            cluster = texworks_mc.calculate_cluster(context)
            context.scene["rzm_tw_mc_last_manifest_json"] = json.dumps(
                cluster["manifest"],
                indent=2,
                sort_keys=True,
            )
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        stats = cluster["manifest"]["stats"]
        self.report(
            {'INFO'},
            f"MC cluster: {stats['faces']} faces, {stats['stack_groups']} groups, {cluster['atlas_size'][0]}x{cluster['atlas_size'][1]}"
        )
        return {'FINISHED'}


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
    bl_description = "Rebuild active material cluster images inside the .blend file"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            cluster = texworks_mc.rebuild_active_material_cluster(context)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Rebuilt {len(cluster.get('images', {}))} cluster image(s): {cluster['atlas_size'][0]}x{cluster['atlas_size'][1]}"
        )
        return {'FINISHED'}


class RZM_OT_TwMcExportCluster(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_export_cluster"
    bl_label = "Export MC Cluster PNG"
    bl_description = "Rebuild and export active material cluster PNG files into Textures/DynAtlas"
    bl_options = {'REGISTER', 'UNDO'}

    sync_texworks: bpy.props.BoolProperty(
        name="Sync TexWorks",
        default=False,
        description="Update TexWorks resources and cluster block after export",
    )

    def execute(self, context):
        try:
            cluster = texworks_mc.rebuild_active_material_cluster(context)
            written = texworks_mc.export_cluster_pngs(context, cluster)
            if self.sync_texworks:
                texworks_mc.sync_texworks_data(context, cluster)
                trigger_refresh()
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported MC cluster: {len(written) - 1} PNG(s)")
        return {'FINISHED'}


class RZM_OT_TwMcApplyCluster(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_apply_cluster"
    bl_label = "Apply MC Cluster"
    bl_description = "Export PNG files, replace material images, and destructively apply packed UV layout"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            cluster = texworks_mc.rebuild_active_material_cluster(context)
            result = texworks_mc.apply_cluster_to_material(context, cluster)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Applied MC cluster: {len(result['changed_objects'])} object(s), {len(result['changed_nodes'])} image node(s)"
        )
        return {'FINISHED'}


class RZM_OT_TwMcSyncCluster(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_sync_cluster"
    bl_label = "Sync MC TexWorks Data"
    bl_description = "Update TexWorks resources and cluster rect block from the active material cluster"
    bl_options = {'REGISTER', 'UNDO'}

    remove_missing: bpy.props.BoolProperty(
        name="Remove Missing",
        default=False,
        description="Remove old auto resources for the same material if the current cluster no longer produces them",
    )

    def execute(self, context):
        try:
            cluster = texworks_mc.calculate_cluster(context)
            texworks_mc.sync_texworks_data(context, cluster, remove_missing=self.remove_missing)
            trigger_refresh()
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report({'INFO'}, f"Synced TexWorks MC: {cluster['manifest']['material_key']}")
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_TwMcCalculateCluster,
    RZM_OT_TwMcCreateMaterial,
    RZM_OT_TwMcEnsureMaterialNode,
    RZM_OT_TwMcRebuildCluster,
    RZM_OT_TwMcExportCluster,
    RZM_OT_TwMcApplyCluster,
    RZM_OT_TwMcSyncCluster,
]
