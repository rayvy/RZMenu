import bpy
from bpy.props import StringProperty, BoolProperty, IntProperty
from ..data.p_logic import ShapeKeyConfig, RZMObjectRef

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
                self.get_all_objects_recursive(coll_ptr.collection, target_objects)
        
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
                'anim_type': c.anim_type_index,
                'start': c.anim_start_frame,
                'end': c.anim_end_frame,
                'over_cond': c.override_switch_condition,
                'over_link': c.override_switch_value_link
            }

        legacy_settings = {s.shape_name: s for s in rzm.shapes if s.shape_name}

        # 4. Update shape_configs
        rzm.shape_configs.clear()
        
        for name, data in discovered_shapes.items():
            config = rzm.shape_configs.add()
            config.shape_name = name
            
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
                config.anim_type_index = s['anim_type']
                config.anim_start_frame = s['start']
                config.anim_end_frame = s['end']
                config.override_switch_condition = s['over_cond']
                config.override_switch_value_link = s['over_link']
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

    def get_all_objects_recursive(self, collection, obj_set):
        for obj in collection.objects:
            obj_set.add(obj)
        for child in collection.children:
            self.get_all_objects_recursive(child, obj_set)

    def add_to_discovered(self, discovered_shapes, name, obj):
        if name not in discovered_shapes:
            discovered_shapes[name] = {'objects': set()}
        discovered_shapes[name]['objects'].add(obj)

class RZM_OT_SelectAffectedObjects(bpy.types.Operator):
    """Select all Blender objects affected by this shape configuration."""
    bl_idname = "rzm.select_affected_objects"
    bl_label = "Select Affected"
    bl_options = {'REGISTER', 'UNDO'}
    
    config_index: IntProperty()

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

classes_to_register = [
    RZM_OT_ShapeKeyExport,
    RZM_OT_SelectAffectedObjects,
    RZM_OT_AddShapeDiscoveryCollection,
    RZM_OT_RemoveShapeDiscoveryCollection,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
