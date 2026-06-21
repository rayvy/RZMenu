import bpy
import numpy as np
from bpy.props import StringProperty, BoolProperty, IntProperty
from ..data.p_logic import ShapeKeyConfig, RZMObjectRef

def get_all_objects_recursive(context, collection, obj_set):
    """Helper to collect all mesh objects from a collection and its children."""
    view_objects = context.view_layer.objects
    for obj in collection.objects:
        if obj.name in view_objects:
            obj_set.add(obj)
    for child in collection.children:
        get_all_objects_recursive(context, child, obj_set)

def ensure_shape_default_group(shape):
    """Ensure every Shape manager has an undeletable group 0."""
    if len(shape.groups) == 0:
        group = shape.groups.add()
        group.group_name = "Default"
    elif not shape.groups[0].group_name:
        shape.groups[0].group_name = "Default"
    if shape.active_group_index < 0 or shape.active_group_index >= len(shape.groups):
        shape.active_group_index = 0

def get_shape_config(rzm, shape_name):
    for config in rzm.shape_configs:
        if config.shape_name == shape_name or getattr(config, "name", "") == shape_name:
            return config
    return None

def combine_conditions(*conditions):
    parts = [str(c).strip() for c in conditions if str(c or "").strip()]
    if not parts:
        return ""
    return " && ".join(f"({part})" for part in parts)

def combine_group_conditions(groups):
    parts = [str(getattr(group, "condition", "") or "").strip() for group in groups]
    parts = [part for part in parts if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return f"({parts[0]})"
    return "(" + " || ".join(f"({part})" for part in parts) + ")"

def member_group_indices(member, shape):
    raw = str(getattr(member, "group_indices", "") or "").strip()
    if raw:
        result = set()
        for part in raw.split(","):
            try:
                idx = int(part.strip())
            except ValueError:
                continue
            if idx >= 0:
                result.add(idx)
        if result:
            return sorted(result)
    return [max(0, getattr(member, "group_index", 0))]

def set_member_group_indices(member, indices):
    cleaned = sorted({idx for idx in indices if idx >= 0})
    if not cleaned:
        cleaned = [0]
    member.group_index = cleaned[0]
    member.group_indices = ",".join(str(idx) for idx in cleaned)

def apply_shape_member_to_config(shape, member, rzm):
    config = get_shape_config(rzm, member.target_shape_name)
    if not config:
        return False

    ensure_shape_default_group(shape)
    indices = member_group_indices(member, shape) if getattr(shape, "use_multi_groups", False) else [0]
    groups = [
        shape.groups[idx]
        for idx in indices
        if 0 <= idx < len(shape.groups)
    ]
    if not groups:
        groups = [shape.groups[0]]

    config.value_link = shape.shape_name
    config.disable_export = False
    config.shape_type = shape.shape_type
    config.condition = combine_conditions(combine_group_conditions(groups), member.condition)
    config.fallback_value = groups[0].fallback_value if groups else member.fallback_value
    override_group = next(
        (
            group for group in groups
            if getattr(group, "override_switch_condition", "")
            and getattr(group, "override_switch_value_link", "")
        ),
        None
    )
    if getattr(shape, "shape_type", "Linear") == "Anim" and override_group:
        config.override_switch_condition = override_group.override_switch_condition
        config.override_switch_value_link = override_group.override_switch_value_link
    else:
        config.override_switch_condition = ""
        config.override_switch_value_link = ""
    config.multiplier = member.multiplier
    config.input_range_min = member.input_range_min
    config.input_range_max = member.input_range_max
    config.anim_type_index = member.anim_type_index
    config.anim_start_frame = member.anim_start_frame
    config.anim_t2 = member.anim_t2
    config.anim_t3 = member.anim_t3
    config.anim_end_frame = member.anim_end_frame
    return True

class RZM_OT_ShapeKeyExport(bpy.types.Operator):
    """Scan collections and discover shape keys to generate ShapeKeyConfig."""
    bl_idname = "rzm.shape_key_export"
    bl_label = "Discover Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        
        # 1. Collect all objects from discovery collections
        target_objects = set()
        for coll_ptr in rzm.shape_discovery_collections:
            if coll_ptr.collection:
                get_all_objects_recursive(context, coll_ptr.collection, target_objects)
        
        if not target_objects:
            self.report({'WARNING'}, "No objects found in discovery collections.")
            return {'CANCELLED'}

        # 2. Discover shape keys
        # discovered_shapes: {name: {objects: [obj1, obj2], type: 'LINEAR', ...}}
        discovered_shapes = {}

        for obj in target_objects:
            if obj.type != 'MESH':
                continue
            
            # Direct shape keys
            if obj.data.shape_keys:
                for kb in obj.data.shape_keys.key_blocks:
                    if kb == kb.relative_key: # Skip basis
                        continue
                    self.add_to_discovered(discovered_shapes, kb.name, obj)

            # Modifiers (Shrinkwrap, SurfaceDeform)
            for mod in obj.modifiers:
                target = None
                if mod.type == 'SHRINKWRAP':
                    target = mod.target
                elif mod.type == 'SURFACE_DEFORM':
                    target = mod.target
                
                if target and target.type == 'MESH' and target.data.shape_keys:
                    for kb in target.data.shape_keys.key_blocks:
                        if kb == kb.relative_key:
                            continue
                        # Use prefix or just same name? User said "inherit". 
                        # Usually it means if the target has a shape key, the source object "inherits" its effect.
                        self.add_to_discovered(discovered_shapes, kb.name, obj)

        # 3. Preserve settings from CURRENT native shapes AND legacy shapes
        # We store current settings to avoid losing manual value_link/disable_export/etc.
        current_settings = {}
        for c in rzm.shape_configs:
            current_settings[c.shape_name] = {
                'type': c.shape_type,
                'link': c.value_link,
                'condition': c.condition,
                'disable': c.disable_export,
                'random': c.mark_random,
                'min': c.slider_min,
                'max': c.slider_max,
                # New animation properties
                'multiplier': c.multiplier,
                'inverse': c.inverse,
                'anim_type': c.anim_type_index,
                'start': c.anim_start_frame,
                'end': c.anim_end_frame,
                'anim_t2': c.anim_t2,
                'anim_t3': c.anim_t3,
                'over_cond': c.override_switch_condition,
                'over_link': c.override_switch_value_link,
                'range_min': c.input_range_min,
                'range_max': c.input_range_max,
                'bake_weights': c.bake_weights,
                'parent_shape': c.parent_shape,
                'fallback_value': c.fallback_value,
                'sparse_vertex_count': c.sparse_vertex_count,
                'sparse_vertex_counts': getattr(c, 'sparse_vertex_counts', ""),
            }

        legacy_settings = {s.shape_name: s for s in rzm.shapes if s.shape_name}

        # 4. Update shape_configs
        rzm.shape_configs.clear()
        
        for name, data in discovered_shapes.items():
            config = rzm.shape_configs.add()
            config.shape_name = name
            config.name = name # Sync for search
            
            # 1. Restore from previous NATIVE config (most specific)
            if name in current_settings:
                s = current_settings[name]
                config.shape_type = s['type']
                config.value_link = s['link']
                config.condition = s['condition']
                config.disable_export = s['disable']
                config.mark_random = s['random']
                config.slider_min = s['min']
                config.slider_max = s['max']
                # New animation properties
                config.multiplier = s['multiplier']
                config.inverse = s['inverse']
                config.anim_type_index = s['anim_type']
                config.anim_start_frame = s['start']
                config.anim_end_frame = s['end']
                config.anim_t2 = s.get('anim_t2', 0.5)
                config.anim_t3 = s.get('anim_t3', 0.5)
                config.override_switch_condition = s['over_cond']
                config.override_switch_value_link = s['over_link']
                config.input_range_min = s['range_min']
                config.input_range_max = s['range_max']
                config.bake_weights = s.get('bake_weights', False)
                config.parent_shape = s.get('parent_shape', "")
                config.fallback_value = s.get('fallback_value', 0.0)
                config.sparse_vertex_count = s.get('sparse_vertex_count', 0)
                config.sparse_vertex_counts = s.get('sparse_vertex_counts', "")
            # 2. Fallback to Legacy config if first time discovery
            elif name in legacy_settings:
                legacy = legacy_settings[name]
                config.shape_type = legacy.shape_type
                config.anim_condition = legacy.anim_condition
                # Fallback for anim properties from legacy if they exist there
                if hasattr(legacy, 'multiplier'): config.multiplier = legacy.multiplier
                # (Add other legacy checks if needed, but usually discovery is from fresh)
            
            # Add affected objects
            for obj in data['objects']:
                ref = config.affected_objects.add()
                ref.obj = obj
                ref.obj_name = obj.name

        for shape in rzm.shapes:
            ensure_shape_default_group(shape)
            for member in shape.shape_keys:
                apply_shape_member_to_config(shape, member, rzm)

        self.report({'INFO'}, f"Discovered {len(rzm.shape_configs)} shape configurations.")
        return {'FINISHED'}

    def add_to_discovered(self, discovered_shapes, name, obj):
        if name not in discovered_shapes:
            discovered_shapes[name] = {'objects': set()}
        discovered_shapes[name]['objects'].add(obj)

class RZM_OT_SelectAffectedObjects(bpy.types.Operator):
    """Select all Blender objects affected by this shape configuration."""
    bl_idname = "rzm.select_affected_objects"
    bl_label = "Select Affected"
    bl_options = {'REGISTER', 'UNDO'}
    
    config_index: bpy.props.IntProperty()

    def execute(self, context):
        rzm = context.scene.rzm
        if not (0 <= self.config_index < len(rzm.shape_configs)):
            return {'CANCELLED'}
        
        config = rzm.shape_configs[self.config_index]
        bpy.ops.object.select_all(action='DESELECT')
        
        found = 0
        for ref in config.affected_objects:
            obj = ref.obj
            if not obj and ref.obj_name:
                obj = bpy.data.objects.get(ref.obj_name)
            
            if obj:
                obj.select_set(True)
                context.view_layer.objects.active = obj
                found += 1
        
        if found:
            self.report({'INFO'}, f"Selected {found} objects for {config.shape_name}")
        else:
            self.report({'WARNING'}, "No valid objects found for selection.")
        
        return {'FINISHED'}

class RZM_OT_AddShapeDiscoveryCollection(bpy.types.Operator):
    bl_idname = "rzm.add_shape_discovery_collection"
    bl_label = "Add Collection"
    def execute(self, context):
        context.scene.rzm.shape_discovery_collections.add()
        return {'FINISHED'}

class RZM_OT_RemoveShapeDiscoveryCollection(bpy.types.Operator):
    bl_idname = "rzm.remove_shape_discovery_collection"
    bl_label = "Remove Collection"
    def execute(self, context):
        rzm = context.scene.rzm
        idx = context.scene.rzm_active_shape_coll_index
        if 0 <= idx < len(rzm.shape_discovery_collections):
            rzm.shape_discovery_collections.remove(idx)
            context.scene.rzm_active_shape_coll_index = max(0, idx - 1)
        return {'FINISHED'}

class RZM_OT_SetAllShapeExport(bpy.types.Operator):
    """Enable or disable export for all discovered shape keys."""
    bl_idname = "rzm.set_all_shape_export"
    bl_label = "Set All Shape Export"
    bl_options = {'REGISTER', 'UNDO'}
    
    state: bpy.props.BoolProperty(name="State", default=True)

    def execute(self, context):
        rzm = context.scene.rzm
        count = 0
        for config in rzm.shape_configs:
            # Note: disable_export=True means EXPORT IS OFF. 
            # state=True means we WANT export, so disable_export=False.
            config.disable_export = not self.state
            count += 1
        
        status = "Enabled" if self.state else "Disabled"
        self.report({'INFO'}, f"{status} export for {count} shapes.")
        return {'FINISHED'}

class RZM_OT_SetAnimFrame(bpy.types.Operator):
    """Set active shape config start/end frame from current timeline (normalized)."""
    bl_idname = "rzm.set_anim_frame"
    bl_label = "Set Frame"
    bl_options = {'REGISTER', 'UNDO'}

    target: bpy.props.StringProperty() # 'start' or 'end'

    def execute(self, context):
        scene = context.scene
        rzm = scene.rzm
        idx = scene.rzm_active_shape_config_index
        if not (0 <= idx < len(rzm.shape_configs)):
            self.report({'WARNING'}, "No active shape configuration.")
            return {'CANCELLED'}
        
        config = rzm.shape_configs[idx]
        current = scene.frame_current
        start = scene.frame_start
        end = scene.frame_end
        
        if end == start:
            normalized = 0.0
        else:
            normalized = (current - start) / (end - start)
            normalized = max(0.0, min(1.0, normalized))
        
        if self.target == 'start':
            config.anim_start_frame = normalized
            self.report({'INFO'}, f"Set Start Frame to {normalized:.3f}")
        else:
            config.anim_end_frame = normalized
            self.report({'INFO'}, f"Set End Frame to {normalized:.3f}")
            
        return {'FINISHED'}

class RZM_OT_GlobalShapeMaster(bpy.types.Operator):
    """Apply a value to all discovered shape configurations and their objects."""
    bl_idname = "rzm.global_shape_master"
    bl_label = "Apply Global Shape Value"
    bl_options = {'REGISTER', 'UNDO'}
    
    value: bpy.props.FloatProperty(name="Value", default=0.0)

    def execute(self, context):
        rzm = context.scene.rzm
        count = 0
        for config in rzm.shape_configs:
            # Setting this triggers the update_native_shape_sync callback in p_logic.py
            config.sync_value = self.value
            count += 1
        
        self.report({'INFO'}, f"Applied {self.value} to {count} shape configurations.")
        return {'FINISHED'}

class RZM_OT_CleanupTrashShapes(bpy.types.Operator):
    """Scan discovery collections and delete shape keys that are identical to the Basis."""
    bl_idname = "rzm.cleanup_trash_shapes"
    bl_label = "Cleanup Trash Shapes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        
        # 1. Collect all objects from discovery collections
        target_objects = set()
        for coll_ptr in rzm.shape_discovery_collections:
            if coll_ptr.collection:
                get_all_objects_recursive(context, coll_ptr.collection, target_objects)
        
        if not target_objects:
            self.report({'WARNING'}, "No objects found in discovery collections.")
            return {'CANCELLED'}

        deleted_count = 0
        objects_processed = 0
        
        for obj in target_objects:
            if obj.type != 'MESH' or not obj.data.shape_keys:
                continue
            
            objects_processed += 1
            basis = obj.data.shape_keys.reference_key
            num_points = len(basis.data)
            
            # Get Basis coordinates
            basis_co = np.empty(num_points * 3, dtype=np.float32)
            basis.data.foreach_get("co", basis_co)
            
            # Find shapes to remove
            to_remove = []
            for kb in obj.data.shape_keys.key_blocks:
                if kb == basis:
                    continue
                
                kb_co = np.empty(num_points * 3, dtype=np.float32)
                kb.data.foreach_get("co", kb_co)
                
                # Compare arrays (atol=1e-6 as proposed)
                if np.allclose(kb_co, basis_co, atol=1e-6):
                    to_remove.append(kb)
            
            # Execute removal
            for kb in to_remove:
                obj.shape_key_remove(kb)
                deleted_count += 1
        
        self.report({'INFO'}, f"Deleted {deleted_count} empty shape keys across {objects_processed} objects.")
        return {'FINISHED'}

class RZM_OT_AdjustAnimTimeline(bpy.types.Operator):
    """Adjust active shape config animation timeline range/hold properties visually."""
    bl_idname = "rzm.adjust_anim_timeline"
    bl_label = "Adjust Timeline"
    bl_options = {'REGISTER', 'UNDO'}
    
    action: bpy.props.StringProperty()
    config_index: bpy.props.IntProperty()
    
    def execute(self, context):
        rzm = context.scene.rzm
        if not (0 <= self.config_index < len(rzm.shape_configs)):
            return {'CANCELLED'}
        config = rzm.shape_configs[self.config_index]
        
        step = 0.05
        
        t1 = config.anim_start_frame
        t2 = config.anim_t2
        t3 = config.anim_t3
        t4 = config.anim_end_frame
        
        if self.action == 'SHIFT_LEFT':
            delta = min(step, t1)
            config.anim_start_frame = max(0.0, t1 - delta)
            config.anim_t2 = max(0.0, t2 - delta)
            config.anim_t3 = max(0.0, t3 - delta)
            config.anim_end_frame = max(0.0, t4 - delta)
        elif self.action == 'SHIFT_RIGHT':
            delta = min(step, 1.0 - t4)
            config.anim_end_frame = min(1.0, t4 + delta)
            config.anim_t3 = min(1.0, t3 + delta)
            config.anim_t2 = min(1.0, t2 + delta)
            config.anim_start_frame = min(1.0, t1 + delta)
        elif self.action == 'EXPAND':
            config.anim_start_frame = max(0.0, t1 - step)
            config.anim_end_frame = min(1.0, t4 + step)
        elif self.action == 'SHRINK':
            if (t4 - t1) > 2 * step:
                config.anim_start_frame = min(t2, t1 + step)
                config.anim_end_frame = max(t3, t4 - step)
        elif self.action == 'MORE_HOLD':
            config.anim_t2 = max(t1, t2 - step)
            config.anim_t3 = min(t4, t3 + step)
        elif self.action == 'LESS_HOLD':
            if (t3 - t2) > step:
                config.anim_t2 = min(t3, t2 + step)
                config.anim_t3 = max(t2, t3 - step)
        elif self.action == 'SHIFT_HOLD_LEFT':
            if (t2 - step) >= t1:
                config.anim_t2 -= step
                config.anim_t3 -= step
        elif self.action == 'SHIFT_HOLD_RIGHT':
            if (t3 + step) <= t4:
                config.anim_t2 += step
                config.anim_t3 += step
                
        # Force UI update
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()
        return {'FINISHED'}

class RZM_OT_AddShapeClusterGroup(bpy.types.Operator):
    """Add a variant group to the active Shape manager."""
    bl_idname = "rzm.add_shape_cluster_group"
    bl_label = "Add Shape Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        idx = context.scene.rzm_active_shape_index
        if not (0 <= idx < len(rzm.shapes)):
            self.report({'WARNING'}, "No active Shape manager.")
            return {'CANCELLED'}

        shape = rzm.shapes[idx]
        ensure_shape_default_group(shape)
        group = shape.groups.add()
        group.group_name = f"Group {len(shape.groups) - 1}"
        shape.active_group_index = len(shape.groups) - 1
        return {'FINISHED'}

class RZM_OT_EnsureShapeDefaultGroup(bpy.types.Operator):
    """Create missing default group 0 on the active Shape manager."""
    bl_idname = "rzm.ensure_shape_default_group"
    bl_label = "Initialize Default Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        idx = context.scene.rzm_active_shape_index
        if not (0 <= idx < len(rzm.shapes)):
            return {'CANCELLED'}
        ensure_shape_default_group(rzm.shapes[idx])
        return {'FINISHED'}

class RZM_OT_RemoveShapeClusterGroup(bpy.types.Operator):
    """Remove the active variant group. Group 0 is permanent."""
    bl_idname = "rzm.remove_shape_cluster_group"
    bl_label = "Remove Shape Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        shape_idx = context.scene.rzm_active_shape_index
        if not (0 <= shape_idx < len(rzm.shapes)):
            self.report({'WARNING'}, "No active Shape manager.")
            return {'CANCELLED'}

        shape = rzm.shapes[shape_idx]
        ensure_shape_default_group(shape)
        group_idx = shape.active_group_index
        if group_idx <= 0:
            self.report({'WARNING'}, "Default group 0 cannot be removed.")
            return {'CANCELLED'}

        shape.groups.remove(group_idx)
        for member in shape.shape_keys:
            indices = []
            for member_group_index in member_group_indices(member, shape):
                if member_group_index == group_idx:
                    continue
                if member_group_index > group_idx:
                    member_group_index -= 1
                indices.append(member_group_index)
            set_member_group_indices(member, indices or [0])
        shape.active_group_index = max(0, min(group_idx - 1, len(shape.groups) - 1))
        return {'FINISHED'}

class RZM_OT_AddShapeClusterMember(bpy.types.Operator):
    """Add the active ShapeKeyConfig to the active Shape manager/group."""
    bl_idname = "rzm.add_shape_cluster_member"
    bl_label = "Add SKC To Manager"
    bl_options = {'REGISTER', 'UNDO'}

    target_shape_name: bpy.props.StringProperty(default="")

    def execute(self, context):
        rzm = context.scene.rzm
        shape_idx = context.scene.rzm_active_shape_index
        config_idx = context.scene.rzm_active_shape_config_index
        if not (0 <= shape_idx < len(rzm.shapes)):
            self.report({'WARNING'}, "No active Shape manager.")
            return {'CANCELLED'}

        target_name = self.target_shape_name.strip() or context.scene.rzm_shape_member_candidate.strip()
        config = get_shape_config(rzm, target_name) if target_name else None
        if not config and 0 <= config_idx < len(rzm.shape_configs):
            config = rzm.shape_configs[config_idx]
        if not config:
            self.report({'WARNING'}, "No active ShapeKeyConfig.")
            return {'CANCELLED'}

        shape = rzm.shapes[shape_idx]
        ensure_shape_default_group(shape)

        initial_group = shape.active_group_index if getattr(shape, "use_multi_groups", False) else 0
        for member in shape.shape_keys:
            if member.target_shape_name == config.shape_name and initial_group in member_group_indices(member, shape):
                apply_shape_member_to_config(shape, member, rzm)
                self.report({'INFO'}, f"{config.shape_name} is already in this group.")
                return {'FINISHED'}

        member = shape.shape_keys.add()
        member.target_shape_name = config.shape_name
        set_member_group_indices(member, [initial_group])
        member.multiplier = config.multiplier
        member.input_range_min = config.input_range_min
        member.input_range_max = config.input_range_max
        member.anim_type_index = config.anim_type_index
        member.anim_start_frame = config.anim_start_frame
        member.anim_t2 = config.anim_t2
        member.anim_t3 = config.anim_t3
        member.anim_end_frame = config.anim_end_frame
        member.fallback_value = config.fallback_value
        apply_shape_member_to_config(shape, member, rzm)
        context.scene.rzm_shape_member_candidate = ""
        self.report({'INFO'}, f"Added {config.shape_name} to {shape.shape_name}.")
        return {'FINISHED'}

class RZM_OT_RemoveShapeClusterMember(bpy.types.Operator):
    """Remove a SKC member from a Shape manager."""
    bl_idname = "rzm.remove_shape_cluster_member"
    bl_label = "Remove SKC From Manager"
    bl_options = {'REGISTER', 'UNDO'}

    member_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        rzm = context.scene.rzm
        shape_idx = context.scene.rzm_active_shape_index
        if not (0 <= shape_idx < len(rzm.shapes)):
            return {'CANCELLED'}
        shape = rzm.shapes[shape_idx]
        idx = self.member_index if self.member_index >= 0 else context.scene.rzm_active_shape_key_index
        if not (0 <= idx < len(shape.shape_keys)):
            return {'CANCELLED'}

        target = shape.shape_keys[idx].target_shape_name
        shape.shape_keys.remove(idx)
        context.scene.rzm_active_shape_key_index = max(0, min(idx - 1, len(shape.shape_keys) - 1))

        still_linked = any(member.target_shape_name == target for member in shape.shape_keys)
        config = get_shape_config(rzm, target)
        if config and config.value_link == shape.shape_name and not still_linked:
            config.value_link = ""
        return {'FINISHED'}

class RZM_OT_SyncShapeCluster(bpy.types.Operator):
    """Push active Shape manager settings into its linked ShapeKeyConfig entries."""
    bl_idname = "rzm.sync_shape_cluster"
    bl_label = "Sync Shape Manager"
    bl_options = {'REGISTER', 'UNDO'}

    shape_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        rzm = context.scene.rzm
        idx = self.shape_index if self.shape_index >= 0 else context.scene.rzm_active_shape_index
        if not (0 <= idx < len(rzm.shapes)):
            self.report({'WARNING'}, "No active Shape manager.")
            return {'CANCELLED'}

        shape = rzm.shapes[idx]
        ensure_shape_default_group(shape)
        synced = 0
        missing = 0
        for member in shape.shape_keys:
            if apply_shape_member_to_config(shape, member, rzm):
                synced += 1
            else:
                missing += 1

        self.report({'INFO'}, f"Synced {synced} SKC entries. Missing: {missing}.")
        return {'FINISHED'}

class RZM_OT_SetShapeClusterGroup(bpy.types.Operator):
    """Set the active group on the selected Shape manager."""
    bl_idname = "rzm.set_shape_cluster_group"
    bl_label = "Set Shape Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_index: bpy.props.IntProperty(default=0)

    def execute(self, context):
        rzm = context.scene.rzm
        shape_idx = context.scene.rzm_active_shape_index
        if not (0 <= shape_idx < len(rzm.shapes)):
            return {'CANCELLED'}
        shape = rzm.shapes[shape_idx]
        ensure_shape_default_group(shape)
        if 0 <= self.group_index < len(shape.groups):
            shape.active_group_index = self.group_index
            return {'FINISHED'}
        return {'CANCELLED'}

class RZM_OT_ToggleShapeMemberGroup(bpy.types.Operator):
    """Toggle active member membership in a group."""
    bl_idname = "rzm.toggle_shape_member_group"
    bl_label = "Toggle Member Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_index: bpy.props.IntProperty(default=0)

    def execute(self, context):
        rzm = context.scene.rzm
        shape_idx = context.scene.rzm_active_shape_index
        member_idx = context.scene.rzm_active_shape_key_index
        if not (0 <= shape_idx < len(rzm.shapes)):
            return {'CANCELLED'}
        shape = rzm.shapes[shape_idx]
        if not (0 <= member_idx < len(shape.shape_keys)):
            return {'CANCELLED'}
        ensure_shape_default_group(shape)
        if not (0 <= self.group_index < len(shape.groups)):
            return {'CANCELLED'}

        member = shape.shape_keys[member_idx]
        indices = set(member_group_indices(member, shape))
        if self.group_index in indices and len(indices) > 1:
            indices.remove(self.group_index)
        else:
            indices.add(self.group_index)
        set_member_group_indices(member, indices)
        apply_shape_member_to_config(shape, member, rzm)
        return {'FINISHED'}

class RZM_OT_AdjustShapeMemberTimeline(bpy.types.Operator):
    """Adjust active Shape manager member animation envelope."""
    bl_idname = "rzm.adjust_shape_member_timeline"
    bl_label = "Adjust Member Timeline"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.StringProperty()

    def execute(self, context):
        rzm = context.scene.rzm
        shape_idx = context.scene.rzm_active_shape_index
        member_idx = context.scene.rzm_active_shape_key_index
        if not (0 <= shape_idx < len(rzm.shapes)):
            return {'CANCELLED'}
        shape = rzm.shapes[shape_idx]
        if not (0 <= member_idx < len(shape.shape_keys)):
            return {'CANCELLED'}
        member = shape.shape_keys[member_idx]

        step = 0.05
        t1 = member.anim_start_frame
        t2 = member.anim_t2
        t3 = member.anim_t3
        t4 = member.anim_end_frame

        if self.action == 'SHIFT_LEFT':
            delta = min(step, t1)
            member.anim_start_frame = max(0.0, t1 - delta)
            member.anim_t2 = max(0.0, t2 - delta)
            member.anim_t3 = max(0.0, t3 - delta)
            member.anim_end_frame = max(0.0, t4 - delta)
        elif self.action == 'SHIFT_RIGHT':
            delta = min(step, 1.0 - t4)
            member.anim_end_frame = min(1.0, t4 + delta)
            member.anim_t3 = min(1.0, t3 + delta)
            member.anim_t2 = min(1.0, t2 + delta)
            member.anim_start_frame = min(1.0, t1 + delta)
        elif self.action == 'EXPAND':
            member.anim_start_frame = max(0.0, t1 - step)
            member.anim_end_frame = min(1.0, t4 + step)
        elif self.action == 'SHRINK':
            if (t4 - t1) > 2 * step:
                member.anim_start_frame = min(t2, t1 + step)
                member.anim_end_frame = max(t3, t4 - step)
        elif self.action == 'MORE_HOLD':
            member.anim_t2 = max(member.anim_start_frame, t2 - step)
            member.anim_t3 = min(member.anim_end_frame, t3 + step)
        elif self.action == 'LESS_HOLD':
            if (t3 - t2) > step:
                member.anim_t2 = min(t3, t2 + step)
                member.anim_t3 = max(t2, t3 - step)

        apply_shape_member_to_config(shape, member, rzm)
        return {'FINISHED'}

class RZM_OT_CopyShapeMemberTimelineToGroup(bpy.types.Operator):
    """Copy the active cluster member timeline to every member in the same group."""
    bl_idname = "rzm.copy_shape_member_timeline_to_group"
    bl_label = "Apply Timeline To Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        shape_idx = context.scene.rzm_active_shape_index
        member_idx = context.scene.rzm_active_shape_key_index
        if not (0 <= shape_idx < len(rzm.shapes)):
            return {'CANCELLED'}
        shape = rzm.shapes[shape_idx]
        if not (0 <= member_idx < len(shape.shape_keys)):
            return {'CANCELLED'}

        source = shape.shape_keys[member_idx]
        source_groups = set(member_group_indices(source, shape))
        count = 0
        for member in shape.shape_keys:
            if not source_groups.intersection(member_group_indices(member, shape)):
                continue
            member.anim_type_index = source.anim_type_index
            member.anim_start_frame = source.anim_start_frame
            member.anim_t2 = source.anim_t2
            member.anim_t3 = source.anim_t3
            member.anim_end_frame = source.anim_end_frame
            apply_shape_member_to_config(shape, member, rzm)
            count += 1

        self.report({'INFO'}, f"Applied timeline to {count} SKC members.")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_ShapeKeyExport,
    RZM_OT_SelectAffectedObjects,
    RZM_OT_AddShapeDiscoveryCollection,
    RZM_OT_RemoveShapeDiscoveryCollection,
    RZM_OT_SetAllShapeExport,
    RZM_OT_SetAnimFrame,
    RZM_OT_GlobalShapeMaster,
    RZM_OT_CleanupTrashShapes,
    RZM_OT_AdjustAnimTimeline,
    RZM_OT_AddShapeClusterGroup,
    RZM_OT_EnsureShapeDefaultGroup,
    RZM_OT_RemoveShapeClusterGroup,
    RZM_OT_AddShapeClusterMember,
    RZM_OT_RemoveShapeClusterMember,
    RZM_OT_SyncShapeCluster,
    RZM_OT_SetShapeClusterGroup,
    RZM_OT_ToggleShapeMemberGroup,
    RZM_OT_AdjustShapeMemberTimeline,
    RZM_OT_CopyShapeMemberTimelineToGroup,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
