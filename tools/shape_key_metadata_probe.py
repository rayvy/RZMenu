import json
import time
import traceback

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty


TEMP_PREFIX = "_RZM_SK_META_TEST_"
MESH_META_PROP = "rzm_shape_key_metadata"


def active_shape_key(context):
    obj = context.object
    if not obj or obj.type != "MESH" or not obj.data or not obj.data.shape_keys:
        return None, None
    keys = obj.data.shape_keys.key_blocks
    index = obj.active_shape_key_index
    if index < 0 or index >= len(keys):
        return obj, None
    return obj, keys[index]


def keyblock_info(key):
    return {
        "name": key.name,
        "value": key.value,
        "mute": key.mute,
        "lock_shape": getattr(key, "lock_shape", None),
        "vertex_group": key.vertex_group,
        "interpolation": key.interpolation,
        "slider_min": key.slider_min,
        "slider_max": key.slider_max,
        "relative_key": key.relative_key.name if key.relative_key else None,
        "custom_properties": custom_prop_dict(key),
        "point_count": len(key.data),
    }


def custom_prop_names(key):
    try:
        return list(key.keys())
    except Exception:
        return []


def custom_prop_dict(key):
    props = {}
    for name in custom_prop_names(key):
        try:
            props[name] = key[name]
        except Exception as exc:
            props[name] = f"<read failed: {exc}>"
    return props


def mesh_metadata(mesh):
    raw = mesh.get(MESH_META_PROP, "{}")
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
    elif isinstance(raw, dict):
        data = dict(raw)
    else:
        data = {}
    return data if isinstance(data, dict) else {}


def write_mesh_metadata(mesh, data):
    mesh[MESH_META_PROP] = json.dumps(data, ensure_ascii=False, sort_keys=True)


def active_shape_metadata(obj, key):
    data = mesh_metadata(obj.data)
    record = data.get(key.name, {})
    return record if isinstance(record, dict) else {}


def set_active_shape_metadata_value(obj, key, prop_name, value):
    data = mesh_metadata(obj.data)
    record = data.get(key.name, {})
    if not isinstance(record, dict):
        record = {}
    record[prop_name] = value
    data[key.name] = record
    write_mesh_metadata(obj.data, data)


def delete_active_shape_metadata_value(obj, key, prop_name):
    data = mesh_metadata(obj.data)
    record = data.get(key.name, {})
    if isinstance(record, dict) and prop_name in record:
        del record[prop_name]
        if record:
            data[key.name] = record
        else:
            data.pop(key.name, None)
        write_mesh_metadata(obj.data, data)
        return True
    return False


def encode_value(value, value_type):
    if value_type == "BOOL":
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value_type == "INT":
        return int(value)
    if value_type == "FLOAT":
        return float(value)
    if value_type == "JSON":
        return json.loads(value)
    return value


def capture_shape_key_data(obj, key):
    coords = [point.co.copy() for point in key.data]
    props = custom_prop_dict(key)
    return {
        "name": key.name,
        "coords": coords,
        "props": props,
        "value": key.value,
        "mute": key.mute,
        "lock_shape": getattr(key, "lock_shape", False),
        "vertex_group": key.vertex_group,
        "interpolation": key.interpolation,
        "slider_min": key.slider_min,
        "slider_max": key.slider_max,
        "relative_key": key.relative_key.name if key.relative_key else "",
        "index": obj.active_shape_key_index,
    }


def restore_shape_key_data(obj, snapshot):
    obj.shape_key_add(name=snapshot["name"], from_mix=False)
    key = obj.data.shape_keys.key_blocks[-1]

    count = min(len(key.data), len(snapshot["coords"]))
    for index in range(count):
        key.data[index].co = snapshot["coords"][index]

    key.value = snapshot["value"]
    key.mute = snapshot["mute"]
    if hasattr(key, "lock_shape"):
        key.lock_shape = snapshot["lock_shape"]
    key.vertex_group = snapshot["vertex_group"]
    key.interpolation = snapshot["interpolation"]
    key.slider_min = snapshot["slider_min"]
    key.slider_max = snapshot["slider_max"]

    rel_name = snapshot.get("relative_key")
    if rel_name and rel_name in obj.data.shape_keys.key_blocks:
        key.relative_key = obj.data.shape_keys.key_blocks[rel_name]

    for name, value in snapshot["props"].items():
        key[name] = value

    obj.active_shape_key_index = min(snapshot["index"], len(obj.data.shape_keys.key_blocks) - 1)
    return key


def remove_shape_key_by_index(context, obj, index):
    prev_active = context.view_layer.objects.active
    prev_selected = list(context.selected_objects)

    try:
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        context.view_layer.objects.active = obj
        obj.active_shape_key_index = index
        with context.temp_override(
            object=obj,
            active_object=obj,
            selected_objects=[obj],
            selected_editable_objects=[obj],
        ):
            bpy.ops.object.shape_key_remove()
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for selected in prev_selected:
            if selected and selected.name in bpy.data.objects:
                selected.select_set(True)
        if prev_active and prev_active.name in bpy.data.objects:
            context.view_layer.objects.active = prev_active


class RZM_SKMetaSettings(bpy.types.PropertyGroup):
    prop_name: StringProperty(name="Name", default="rzm_shape_type")
    prop_value: StringProperty(name="Value", default="Anim")
    value_link: StringProperty(name="Value Link", default="")
    prop_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ("STRING", "String", ""),
            ("BOOL", "Bool", ""),
            ("INT", "Int", ""),
            ("FLOAT", "Float", ""),
            ("JSON", "JSON", ""),
        ],
        default="STRING",
    )
    preset: bpy.props.EnumProperty(
        name="Preset",
        items=[
            ("ANIM", "Anim", "Anim shape with default 0..1 frame window"),
            ("LINEAR", "Linear", "Linear shape"),
            ("VALUE_LINK", "Value Link", "Set value link from the field below"),
            ("BAKE_WEIGHTS", "Bake Weights", "Enable weight-shape export"),
            ("DISABLE", "Disable Export", "Disable this shape during discovery/export restore"),
            ("CLEAR", "Clear Shape Metadata", "Remove active shape metadata record"),
        ],
        default="ANIM",
    )
    stress_iterations: IntProperty(name="Iterations", default=50, min=1, max=5000)
    stress_recreate_key: BoolProperty(name="Recreate ShapeKey", default=True)
    stress_recreate_props: BoolProperty(name="Rewrite Props", default=True)


class RZM_OT_skmeta_print(bpy.types.Operator):
    bl_idname = "rzm_debug.skmeta_print"
    bl_label = "Print Active ShapeKey"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj, key = active_shape_key(context)
        if not key:
            self.report({"WARNING"}, "No active mesh shape key.")
            return {"CANCELLED"}
        print("[RZM SK META]", obj.name)
        print(json.dumps(keyblock_info(key), indent=2, ensure_ascii=False, default=str))
        self.report({"INFO"}, f"Printed {key.name} to console.")
        return {"FINISHED"}


class RZM_OT_skmeta_write(bpy.types.Operator):
    bl_idname = "rzm_debug.skmeta_write"
    bl_label = "Write Prop"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj, key = active_shape_key(context)
        settings = context.scene.rzm_skmeta_settings
        if not key:
            self.report({"WARNING"}, "No active mesh shape key.")
            return {"CANCELLED"}
        if not settings.prop_name.strip():
            self.report({"WARNING"}, "Property name is empty.")
            return {"CANCELLED"}

        try:
            set_active_shape_metadata_value(
                obj,
                key,
                settings.prop_name.strip(),
                encode_value(settings.prop_value, settings.prop_type),
            )
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Wrote mesh metadata {settings.prop_name} for {key.name}.")
        return {"FINISHED"}


class RZM_OT_skmeta_delete(bpy.types.Operator):
    bl_idname = "rzm_debug.skmeta_delete"
    bl_label = "Delete Prop"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj, key = active_shape_key(context)
        settings = context.scene.rzm_skmeta_settings
        if not key:
            self.report({"WARNING"}, "No active mesh shape key.")
            return {"CANCELLED"}
        name = settings.prop_name.strip()
        if delete_active_shape_metadata_value(obj, key, name):
            self.report({"INFO"}, f"Deleted {name}.")
        else:
            self.report({"INFO"}, f"{name} was not present.")
        return {"FINISHED"}


class RZM_OT_skmeta_apply_preset(bpy.types.Operator):
    bl_idname = "rzm_debug.skmeta_apply_preset"
    bl_label = "Apply Preset"
    bl_options = {"REGISTER", "UNDO"}

    preset: bpy.props.StringProperty(default="")

    def execute(self, context):
        obj, key = active_shape_key(context)
        settings = context.scene.rzm_skmeta_settings
        if not key:
            self.report({"WARNING"}, "No active mesh shape key.")
            return {"CANCELLED"}

        preset = self.preset or settings.preset
        if preset == "CLEAR":
            data = mesh_metadata(obj.data)
            existed = key.name in data
            data.pop(key.name, None)
            write_mesh_metadata(obj.data, data)
            self.report({"INFO"}, "Cleared metadata." if existed else "No metadata to clear.")
            return {"FINISHED"}

        if preset == "ANIM":
            values = {
                "rzm_shape_type": "Anim",
                "rzm_anim_start_frame": 0.0,
                "rzm_anim_end_frame": 1.0,
            }
        elif preset == "LINEAR":
            values = {"rzm_shape_type": "Linear"}
        elif preset == "VALUE_LINK":
            values = {"rzm_value_link": settings.value_link}
        elif preset == "BAKE_WEIGHTS":
            values = {"rzm_bake_weights": True}
        elif preset == "DISABLE":
            values = {"rzm_disable_export": True}
        else:
            self.report({"ERROR"}, f"Unknown preset: {preset}")
            return {"CANCELLED"}

        for name, value in values.items():
            set_active_shape_metadata_value(obj, key, name, value)

        self.report({"INFO"}, f"Applied {preset} metadata to {key.name}.")
        return {"FINISHED"}


class RZM_OT_skmeta_gc(bpy.types.Operator):
    bl_idname = "rzm_debug.skmeta_gc"
    bl_label = "Clean Metadata"
    bl_options = {"REGISTER", "UNDO"}

    scope: bpy.props.EnumProperty(
        name="Scope",
        items=[
            ("ACTIVE", "Active Mesh", ""),
            ("ALL", "All Meshes", ""),
        ],
        default="ACTIVE",
    )

    def execute(self, context):
        meshes = []
        if self.scope == "ACTIVE":
            obj = context.object
            if obj and obj.type == "MESH" and obj.data:
                meshes = [obj.data]
        else:
            meshes = list(bpy.data.meshes)

        removed_shapes = 0
        removed_mesh_props = 0
        scanned = 0

        for mesh in meshes:
            if MESH_META_PROP not in mesh:
                continue
            scanned += 1
            data = mesh_metadata(mesh)
            keys = mesh.shape_keys.key_blocks if mesh.shape_keys else []
            existing = {key.name for key in keys}
            cleaned = {
                name: record
                for name, record in data.items()
                if name in existing and isinstance(record, dict)
            }
            removed_shapes += len(data) - len(cleaned)
            if cleaned:
                write_mesh_metadata(mesh, cleaned)
            else:
                del mesh[MESH_META_PROP]
                removed_mesh_props += 1

        self.report(
            {"INFO"},
            f"GC scanned {scanned} mesh(es), removed {removed_shapes} stale shape record(s), "
            f"cleared {removed_mesh_props} empty mesh prop(s).",
        )
        return {"FINISHED"}


class RZM_OT_skmeta_stress(bpy.types.Operator):
    bl_idname = "rzm_debug.skmeta_stress"
    bl_label = "Stress Test On Temp Copy"
    bl_options = {"REGISTER"}

    def execute(self, context):
        source_obj, source_key = active_shape_key(context)
        settings = context.scene.rzm_skmeta_settings
        if not source_key:
            self.report({"WARNING"}, "No active mesh shape key.")
            return {"CANCELLED"}

        temp_obj = None
        start = time.perf_counter()
        try:
            temp_mesh = source_obj.data.copy()
            temp_obj = source_obj.copy()
            temp_obj.name = TEMP_PREFIX + source_obj.name
            temp_obj.data = temp_mesh
            context.scene.collection.objects.link(temp_obj)
            temp_obj.active_shape_key_index = source_obj.active_shape_key_index

            key = temp_obj.data.shape_keys.key_blocks[temp_obj.active_shape_key_index]
            set_active_shape_metadata_value(temp_obj, key, "_rzm_probe_sentinel", "alive")
            set_active_shape_metadata_value(temp_obj, key, "_rzm_probe_counter", 0)
            snapshot = capture_shape_key_data(temp_obj, key)

            depsgraph = context.evaluated_depsgraph_get()
            for index in range(settings.stress_iterations):
                if settings.stress_recreate_props:
                    set_active_shape_metadata_value(temp_obj, key, "_rzm_probe_counter", index)
                    set_active_shape_metadata_value(
                        temp_obj,
                        key,
                        "_rzm_probe_json",
                        {"iteration": index, "name": key.name},
                    )

                key.value = 1.0 if index % 2 else 0.0
                key.mute = bool(index % 3 == 0)
                context.view_layer.update()
                depsgraph.update()
                _ = temp_obj.evaluated_get(depsgraph)

                if settings.stress_recreate_key:
                    active_index = temp_obj.active_shape_key_index
                    snapshot = capture_shape_key_data(temp_obj, key)
                    remove_shape_key_by_index(context, temp_obj, active_index)
                    key = restore_shape_key_data(temp_obj, snapshot)
                    context.view_layer.update()
                    depsgraph.update()

                if active_shape_metadata(temp_obj, key).get("_rzm_probe_sentinel") != "alive":
                    raise RuntimeError(f"Sentinel lost at iteration {index}")

            elapsed = time.perf_counter() - start
            print(
                f"[RZM SK META] Stress OK: {settings.stress_iterations} iterations "
                f"in {elapsed:.3f}s on temp copy."
            )
            self.report({"INFO"}, f"Stress OK: {settings.stress_iterations} iterations.")
        except Exception as exc:
            print("[RZM SK META] Stress FAILED")
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            if temp_obj and temp_obj.name in bpy.data.objects:
                temp_data = temp_obj.data
                bpy.data.objects.remove(temp_obj, do_unlink=True)
                if temp_data and temp_data.users == 0:
                    bpy.data.meshes.remove(temp_data, do_unlink=True)

        return {"FINISHED"}


class RZM_PT_skmeta_probe(bpy.types.Panel):
    bl_label = "RZMenu ShapeKey Metadata"
    bl_idname = "RZM_PT_skmeta_probe"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"
    bl_parent_id = "DATA_PT_shape_keys"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rzm_skmeta_settings
        obj, key = active_shape_key(context)

        if not obj:
            layout.label(text="Select a mesh object.", icon="INFO")
            return
        if not key:
            layout.label(text="Select a shape key.", icon="INFO")
            return

        row = layout.row(align=True)
        row.label(text=key.name, icon="SHAPEKEY_DATA")
        row.label(text=f"{key.value:.3f}")

        box = layout.box()
        box.label(text=f"Mesh: {obj.data.name}", icon="MESH_DATA")
        box.label(text=f"Mute {key.mute} | Lock {getattr(key, 'lock_shape', False)}")
        custom_props = custom_prop_dict(key)
        box.label(text=f"Points: {len(key.data)} | KeyBlock Props: {len(custom_props)}")

        props_box = layout.box()
        props_box.label(text="KeyBlock Custom Properties", icon="INFO")
        if custom_props:
            for name, value in custom_props.items():
                props_box.label(text=f"{name} = {value}")
        else:
            props_box.label(text="<not supported / none>")

        meta_box = layout.box()
        meta_box.label(text=f"Mesh Metadata: {MESH_META_PROP}", icon="MESH_DATA")
        metadata = active_shape_metadata(obj, key)
        if metadata:
            for name, value in metadata.items():
                meta_box.label(text=f"{name} = {value}")
        else:
            meta_box.label(text="<none for active shape>")

        preset = layout.box()
        preset.label(text="Presets", icon="PRESET")
        row = preset.row(align=True)
        row.operator("rzm_debug.skmeta_apply_preset", text="Anim").preset = "ANIM"
        row.operator("rzm_debug.skmeta_apply_preset", text="Linear").preset = "LINEAR"
        row.operator("rzm_debug.skmeta_apply_preset", text="Weights").preset = "BAKE_WEIGHTS"
        row.operator("rzm_debug.skmeta_apply_preset", text="Disable").preset = "DISABLE"
        row.operator("rzm_debug.skmeta_apply_preset", text="", icon="X").preset = "CLEAR"
        row = preset.row(align=True)
        row.prop(settings, "value_link")
        row.operator("rzm_debug.skmeta_apply_preset", text="", icon="LINKED").preset = "VALUE_LINK"

        edit = layout.box()
        edit.label(text="Manual Property", icon="OPTIONS")
        row = edit.row(align=True)
        row.prop(settings, "prop_name")
        row.prop(settings, "prop_type", text="")
        edit.prop(settings, "prop_value")
        row = edit.row(align=True)
        row.operator("rzm_debug.skmeta_write", icon="FILE_TICK")
        row.operator("rzm_debug.skmeta_delete", icon="TRASH")
        row.operator("rzm_debug.skmeta_print", icon="CONSOLE")

        clean = layout.box()
        clean.label(text="Maintenance", icon="TRASH")
        row = clean.row(align=True)
        row.operator("rzm_debug.skmeta_gc", text="Clean Active").scope = "ACTIVE"
        row.operator("rzm_debug.skmeta_gc", text="Clean All").scope = "ALL"

        stress = layout.box()
        stress.label(text="Reliability Stress", icon="MODIFIER")
        stress.prop(settings, "stress_iterations")
        stress.prop(settings, "stress_recreate_props")
        stress.prop(settings, "stress_recreate_key")
        stress.operator("rzm_debug.skmeta_stress", icon="PLAY")


classes = (
    RZM_SKMetaSettings,
    RZM_OT_skmeta_print,
    RZM_OT_skmeta_write,
    RZM_OT_skmeta_delete,
    RZM_OT_skmeta_apply_preset,
    RZM_OT_skmeta_gc,
    RZM_OT_skmeta_stress,
    RZM_PT_skmeta_probe,
)


def unregister():
    if hasattr(bpy.types.Scene, "rzm_skmeta_settings"):
        del bpy.types.Scene.rzm_skmeta_settings
    for cls in reversed(classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)


def register():
    for cls in classes:
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
        bpy.utils.register_class(cls)
    bpy.types.Scene.rzm_skmeta_settings = bpy.props.PointerProperty(type=RZM_SKMetaSettings)


register()
print("[RZM SK META] Probe UI registered. Open Properties > Object Data > Shape Keys.")
