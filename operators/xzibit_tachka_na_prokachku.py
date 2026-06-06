import bpy


TEXCOORD_LAYER_NAME = "TEXCOORD.xy"
COLOR_ATTR_NAME = "COLOR"


def iter_target_meshes(context, active_only=False):
    active = context.active_object
    if active_only:
        return [active] if active and active.type == 'MESH' and active.data else []

    selected = [
        obj for obj in context.selected_objects
        if obj and obj.type == 'MESH' and obj.data
    ]
    if selected:
        return selected
    if active and active.type == 'MESH' and active.data:
        return [active]
    return []


def unique_layer_name(collection, base_name, skip=None):
    names = {item.name for item in collection if item != skip}
    if base_name not in names:
        return base_name
    index = 1
    while True:
        candidate = f"{base_name}.old{index:03d}"
        if candidate not in names:
            return candidate
        index += 1


def ensure_texcoord_xy(obj):
    mesh = obj.data
    uv_layers = mesh.uv_layers

    if not uv_layers:
        layer = uv_layers.new(name=TEXCOORD_LAYER_NAME)
    else:
        layer = uv_layers.active or uv_layers[0]
        existing = uv_layers.get(TEXCOORD_LAYER_NAME)
        if existing and existing != layer:
            existing.name = unique_layer_name(uv_layers, TEXCOORD_LAYER_NAME, skip=existing)
        layer.name = TEXCOORD_LAYER_NAME

    mesh.uv_layers.active = layer
    layer.active_render = True
    mesh.update()
    return layer


def ensure_color_attribute(obj):
    mesh = obj.data
    if not hasattr(mesh, "color_attributes"):
        raise RuntimeError("Mesh color attributes API is not available")

    layer = mesh.color_attributes.get(COLOR_ATTR_NAME)
    if layer is None:
        layer = mesh.color_attributes.new(
            name=COLOR_ATTR_NAME,
            type='BYTE_COLOR',
            domain='CORNER',
        )
    mesh.color_attributes.active_color = layer
    index = mesh.color_attributes.find(layer.name)
    if index >= 0:
        mesh.color_attributes.active_color_index = index
    mesh.update()
    return layer


def prepare_xxmi_mesh(obj):
    ensure_texcoord_xy(obj)
    ensure_color_attribute(obj)


class RZM_OT_XzibitRenameActiveUVTexcoord(bpy.types.Operator):
    bl_idname = "rzm.xzibit_rename_active_uv_texcoord"
    bl_label = "Rename Active UV to TEXCOORD.xy"
    bl_description = "Rename the active UV layer to TEXCOORD.xy, or create it when the mesh has no UV layers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(iter_target_meshes(context))

    def execute(self, context):
        objects = iter_target_meshes(context, active_only=True)
        for obj in objects:
            ensure_texcoord_xy(obj)
        self.report({'INFO'}, f"TEXCOORD.xy prepared on {len(objects)} object(s).")
        return {'FINISHED'}


class RZM_OT_XzibitCreateColorAttribute(bpy.types.Operator):
    bl_idname = "rzm.xzibit_create_color_attribute"
    bl_label = "Create COLOR Attribute"
    bl_description = "Create or activate a CORNER/BYTE COLOR attribute named COLOR"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(iter_target_meshes(context))

    def execute(self, context):
        objects = iter_target_meshes(context, active_only=True)
        failed = 0
        for obj in objects:
            try:
                ensure_color_attribute(obj)
            except Exception as exc:
                failed += 1
                print(f"[RZM XXMI Preparation] {obj.name}: COLOR failed: {exc}")
        if failed:
            self.report({'WARNING'}, f"COLOR prepared on {len(objects) - failed}, failed {failed}.")
        else:
            self.report({'INFO'}, f"COLOR prepared on {len(objects)} object(s).")
        return {'FINISHED'} if failed < len(objects) else {'CANCELLED'}


class RZM_OT_XzibitXXMIPreparation(bpy.types.Operator):
    bl_idname = "rzm.xzibit_xxmi_preparation"
    bl_label = "XXMI Preparation"
    bl_description = "Prepare selected meshes for XXMI export: TEXCOORD.xy UV layer and COLOR attribute"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(iter_target_meshes(context))

    def execute(self, context):
        objects = iter_target_meshes(context)
        failed = 0
        for obj in objects:
            try:
                prepare_xxmi_mesh(obj)
            except Exception as exc:
                failed += 1
                print(f"[RZM XXMI Preparation] {obj.name}: preparation failed: {exc}")
        if failed:
            self.report({'WARNING'}, f"Prepared {len(objects) - failed}, failed {failed}.")
        else:
            self.report({'INFO'}, f"XXMI Preparation done on {len(objects)} object(s).")
        return {'FINISHED'} if failed < len(objects) else {'CANCELLED'}


class RZM_OT_XzibitXXMIPreparationWithWeights(bpy.types.Operator):
    bl_idname = "rzm.xzibit_xxmi_preparation_with_weights"
    bl_label = "XXMI Preparation + Weights"
    bl_description = "For exactly two selected meshes: transfer weights from the non-active donor to active target, then prepare TEXCOORD.xy and COLOR"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        selected = [
            obj for obj in context.selected_objects
            if obj and obj.type == 'MESH' and obj.data
        ]
        return len(selected) == 2 and context.active_object in selected

    def execute(self, context):
        target = context.active_object
        try:
            transfer = getattr(bpy.ops.rzm_st, "smart_transfer", None)
            if transfer is None:
                self.report({'ERROR'}, "rzm_st.smart_transfer is not registered")
                return {'CANCELLED'}
            result = transfer()
            if 'CANCELLED' in result:
                return {'CANCELLED'}
            prepare_xxmi_mesh(target)
        except Exception as exc:
            self.report({'ERROR'}, f"XXMI Preparation + Weights failed: {exc}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Transferred weights and prepared {target.name}.")
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_XzibitRenameActiveUVTexcoord,
    RZM_OT_XzibitCreateColorAttribute,
    RZM_OT_XzibitXXMIPreparation,
    RZM_OT_XzibitXXMIPreparationWithWeights,
]
