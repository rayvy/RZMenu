import bpy


def shape_config_has_required_value_link(config):
    """Linear shape configs must explicitly declare a value link."""
    if getattr(config, "shape_type", "Linear") != "Linear":
        return True
    return bool(str(getattr(config, "value_link", "") or "").strip())

def shape_config_is_cluster_member(rzm, config):
    shape_name = getattr(config, "shape_name", "")
    if not shape_name:
        return False
    for shape in getattr(rzm, "shapes", []):
        for member in getattr(shape, "shape_keys", []):
            if getattr(member, "target_shape_name", "") == shape_name:
                return True
    return False


def shape_key_block_is_exportable(key_block):
    if not key_block:
        return False
    if getattr(key_block, "lock_shape", False):
        return False
    if getattr(key_block, "mute", False):
        return False
    return True


def resolve_shape_ref_object(ref):
    obj = getattr(ref, "obj", None)
    if obj:
        return obj

    obj_name = getattr(ref, "obj_name", "")
    if obj_name:
        return bpy.data.objects.get(obj_name)

    return None


def get_shape_key_block_for_object(obj, shape_name, include_modifier_targets=True):
    if not obj:
        return None

    if getattr(obj, "data", None) and getattr(obj.data, "shape_keys", None):
        key_block = obj.data.shape_keys.key_blocks.get(shape_name)
        if key_block:
            return key_block

    if include_modifier_targets:
        for mod in getattr(obj, "modifiers", []):
            if mod.type not in {"SURFACE_DEFORM", "SHRINKWRAP"}:
                continue
            if not getattr(mod, "show_viewport", True):
                continue
            target = getattr(mod, "target", None)
            if not target or not getattr(target, "data", None):
                continue
            shape_keys = getattr(target.data, "shape_keys", None)
            if not shape_keys:
                continue
            key_block = shape_keys.key_blocks.get(shape_name)
            if key_block:
                return key_block

    return None


def object_shape_key_is_exportable(obj, shape_name, include_modifier_targets=True):
    key_block = get_shape_key_block_for_object(
        obj,
        shape_name,
        include_modifier_targets=include_modifier_targets,
    )
    return shape_key_block_is_exportable(key_block)


def shape_config_is_exportable(config):
    if getattr(config, "disable_export", False):
        return False
    if not shape_config_has_required_value_link(config):
        return False

    shape_name = getattr(config, "shape_name", "")
    for ref in getattr(config, "affected_objects", []):
        obj = resolve_shape_ref_object(ref)
        if object_shape_key_is_exportable(obj, shape_name):
            return True

    return False


def prepare_shape_config_export_runtime(rzm):
    """Prepare plain PropertyGroup data that all Jinja renderers can read."""
    for config in rzm.shape_configs:
        if hasattr(config, "export_runtime_affected_objects"):
            config.export_runtime_affected_objects.clear()

        disabled = (
            getattr(config, "disable_export", False)
            or not shape_config_has_required_value_link(config)
            or not shape_config_is_cluster_member(rzm, config)
        )

        if not disabled:
            shape_name = getattr(config, "shape_name", "")
            for ref in getattr(config, "affected_objects", []):
                obj = resolve_shape_ref_object(ref)
                if not object_shape_key_is_exportable(obj, shape_name):
                    continue

                if hasattr(config, "export_runtime_affected_objects"):
                    export_ref = config.export_runtime_affected_objects.add()
                    export_ref.obj = obj
                    export_ref.obj_name = obj.name

            runtime_refs = getattr(config, "export_runtime_affected_objects", [])
            if len(runtime_refs) == 0:
                disabled = True

        if hasattr(config, "export_runtime_disabled"):
            config.export_runtime_disabled = disabled


def active_shape_configs(rzm):
    return [
        config for config in rzm.shape_configs
        if not getattr(config, "export_runtime_disabled", True)
    ]


def active_weight_shape_configs(rzm):
    return [
        config for config in active_shape_configs(rzm)
        if getattr(config, "bake_weights", False)
    ]


def object_names_match_component(obj, affected_names):
    if not obj:
        return False

    names_to_check = []
    if getattr(obj, "name", ""):
        names_to_check.append(obj.name.lower())
    if getattr(obj, "data", None) and getattr(obj.data, "name", ""):
        names_to_check.append(obj.data.name.lower())

    for a_name in affected_names:
        a_name = str(a_name).lower()
        for r_name in names_to_check:
            if (
                r_name == a_name
                or (
                    len(r_name) >= 3
                    and len(a_name) >= 3
                    and (a_name in r_name or r_name in a_name)
                )
            ):
                return True

    return False


def shape_config_matches_component(config, affected_names):
    if not shape_config_is_exportable(config):
        return False

    shape_name = getattr(config, "shape_name", "")
    for ref in getattr(config, "affected_objects", []):
        obj = resolve_shape_ref_object(ref)
        if not object_names_match_component(obj, affected_names):
            continue
        if object_shape_key_is_exportable(obj, shape_name):
            return True

    return False
