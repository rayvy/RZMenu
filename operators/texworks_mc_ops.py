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


def active_export_collection_objects(context):
    layer_collection = getattr(context.view_layer, "active_layer_collection", None)
    collection = layer_collection.collection if layer_collection else None
    if collection is None:
        return set()

    result = set()

    def visit(coll):
        for obj in coll.objects:
            result.add(obj)
        for child in coll.children:
            visit(child)

    visit(collection)
    return result


def tw_mc_material_keys(context):
    rzm = context.scene.rzm
    return {
        entry.material_key or texworks_mc.material_key(entry.material_name)
        for entry in rzm.tw_mc_files
        if entry.material_key or entry.material_name
    }


def objects_for_tw_mc_material_key(material_key):
    material_key = str(material_key or "")
    mats = [
        mat for mat in bpy.data.materials
        if texworks_mc.material_key(mat.name) == material_key
    ]
    objects = []
    seen = set()
    for mat in mats:
        for obj in texworks_mc.objects_using_material_name(mat.name):
            if obj.name not in seen:
                objects.append(obj)
                seen.add(obj.name)
    return objects


class RZM_OT_TwMcSelectMaterialObjects(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_select_material_objects"
    bl_label = "Select TWAA Material Objects"
    bl_description = "Select mesh objects using this registered TWAA Blender material"
    bl_options = {'REGISTER', 'UNDO'}

    material_key: bpy.props.StringProperty(name="Material Key")
    active_export_only: bpy.props.BoolProperty(
        name="Active Export Collection Only",
        default=False,
    )
    extend: bpy.props.BoolProperty(name="Extend Selection", default=False)

    def execute(self, context):
        objects = objects_for_tw_mc_material_key(self.material_key)
        if self.active_export_only:
            active_objects = active_export_collection_objects(context)
            objects = [
                obj for obj in objects
                if obj in active_objects and obj.visible_get(view_layer=context.view_layer)
            ]

        if not self.extend:
            bpy.ops.object.select_all(action='DESELECT')

        for obj in objects:
            obj.select_set(True)

        if objects:
            context.view_layer.objects.active = objects[0]

        self.report({'INFO'}, f"Selected {len(objects)} object(s) for {self.material_key}.")
        return {'FINISHED'}


class RZM_OT_TwMcSelectAllMaterialObjects(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_select_all_material_objects"
    bl_label = "Select All TWAA Material Objects"
    bl_description = "Select mesh objects using any registered TWAA Blender material"
    bl_options = {'REGISTER', 'UNDO'}

    active_export_only: bpy.props.BoolProperty(
        name="Active Export Collection Only",
        default=False,
    )

    def execute(self, context):
        keys = tw_mc_material_keys(context)
        objects = []
        seen = set()
        for key in keys:
            for obj in objects_for_tw_mc_material_key(key):
                if obj.name not in seen:
                    objects.append(obj)
                    seen.add(obj.name)

        if self.active_export_only:
            active_objects = active_export_collection_objects(context)
            objects = [
                obj for obj in objects
                if obj in active_objects and obj.visible_get(view_layer=context.view_layer)
            ]

        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.select_set(True)

        if objects:
            context.view_layer.objects.active = objects[0]

        self.report({'INFO'}, f"Selected {len(objects)} TWAA object(s).")
        return {'FINISHED'}


class RZM_OT_TwMcSelectPreviewMaterialObjects(bpy.types.Operator):
    bl_idname = "rzm.tw_mc_select_preview_material_objects"
    bl_label = "Select TWAA Preview UV Objects"
    bl_description = "Select objects using this material and make TWAA.<Material> the active UV layer when present"
    bl_options = {'REGISTER', 'UNDO'}

    material_key: bpy.props.StringProperty(name="Material Key")
    extend: bpy.props.BoolProperty(name="Extend Selection", default=False)

    def execute(self, context):
        key = self.material_key
        if not key:
            mat = context.object.active_material if context.object else None
            if not mat:
                self.report({'WARNING'}, "No material key or active material")
                return {'CANCELLED'}
            key = texworks_mc.material_key(mat.name)

        objects = objects_for_tw_mc_material_key(key)
        if not self.extend:
            bpy.ops.object.select_all(action='DESELECT')

        mats = [
            mat for mat in bpy.data.materials
            if texworks_mc.material_key(mat.name) == key
        ]
        preview_names = {texworks_mc.preview_uv_name_for_material(mat) for mat in mats}
        active_preview = 0
        missing_preview = 0
        for obj in objects:
            obj.select_set(True)
            layer = None
            for preview_name in preview_names:
                layer = obj.data.uv_layers.get(preview_name)
                if layer:
                    break
            if layer:
                try:
                    obj.data.uv_layers.active = layer
                    layer.active_render = True
                    active_preview += 1
                except Exception:
                    missing_preview += 1
            else:
                missing_preview += 1

        if objects:
            context.view_layer.objects.active = objects[0]

        self.report(
            {'INFO'},
            f"Selected {len(objects)} object(s), preview active on {active_preview}, missing {missing_preview}."
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
    RZM_OT_TwMcSelectMaterialObjects,
    RZM_OT_TwMcSelectAllMaterialObjects,
    RZM_OT_TwMcSelectPreviewMaterialObjects,
]
