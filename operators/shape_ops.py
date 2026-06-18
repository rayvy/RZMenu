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
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
