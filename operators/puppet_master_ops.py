# RZMenu/operators/puppet_master_ops.py
import bpy
import struct
import os
import re
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def set_armature_visibility(objects, visible):
    """Disables armatures for clean deformation baking."""
    for obj in objects:
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                mod.show_viewport = visible

def get_linked_targets(comp_objects):
    """Finds 'Puppet Master' targets (Body) that clothing is linked to."""
    targets = set()
    for obj in comp_objects:
        for mod in obj.modifiers:
            if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                targets.add(mod.target)
    return list(targets)

def get_components_to_process(context, per_component=False):
    """
    Returns a dict mapping comp_id -> list of objects.
    Logic differs by game type.
    """
    rzm = context.scene.rzm
    game = rzm.game.name
    results = {}

    base_objs = [o for o in context.view_layer.objects if o.type == 'MESH']
    is_xxmi = game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']
    
    print("\n" + "="*50)
    print(f"--- [DEBUG] COMPONENT DISCOVERY (Game: {game}) ---")
    
    processed_objs = set()
    
    if is_xxmi:
        print("[Mode: Collection Matching]")
        for coll in bpy.data.collections:
            match = re.search(r"Component\s*(\d+)", coll.name, re.IGNORECASE)
            if match:
                comp_id = match.group(1)
                for obj in coll.objects:
                    if obj.type == 'MESH' and obj.name in context.view_layer.objects:
                        results.setdefault(comp_id, []).append(obj)
                        processed_objs.add(obj)
                        print(f"  -> [INC] '{obj.name}' assigned to Comp {comp_id} (via Coll: '{coll.name}')")
    else:
        print("[Mode: Object Name Matching (EFMI/WWMI)]")
        for obj in base_objs:
            match = re.search(r"Component\s*(\d+)", obj.name, re.IGNORECASE)
            if match:
                comp_id = match.group(1)
                results.setdefault(comp_id, []).append(obj)
                processed_objs.add(obj)
                print(f"  -> [INC] '{obj.name}' assigned to Comp {comp_id} (via Regex)")
            else:
                print(f"  -> [EXC] '{obj.name}' skipped (No 'Component N' in name)")

    for cid in results:
        results[cid] = list(set(results[cid]))
            
    if per_component and context.active_object:
        print("\n--- [DEBUG] FILTER: Active Component Only ---")
        target_comp_id = None
        for cid, objs in results.items():
            if context.active_object in objs:
                target_comp_id = cid
                break
        
        if target_comp_id:
            print(f"  -> Kept only Comp {target_comp_id} (contains active '{context.active_object.name}')")
            print("="*50)
            return {target_comp_id: results.get(target_comp_id, [])}
        print("  -> Active object does not belong to any Component! Returning empty.")
        print("="*50)
        return {}

    print("="*50)
    return results

def bake_component_shapes(context, comp_id, comp_objects, mod_root, limit):
    """Core baking logic for a single component."""
    # 1. Prepare paths
    # Standard: Meshes/ComponentN_VB0.buf
    # Output: SK/ (Standardized)
    vb0_path = os.path.join(mod_root, "Meshes", f"Component{comp_id}_VB0.buf")
    output_dir = os.path.join(mod_root, "SK")
    
    if not os.path.exists(vb0_path):
        print(f"[Puppet Master] Skipped Comp {comp_id}: VB0 not found at {vb0_path}")
        return False

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(vb0_path, "rb") as f:
        original_data = bytearray(f.read())

    # Detect stride from game type or assume 32 (Genshin) as default
    game = context.scene.rzm.game.name
    stride = 32
    if game in ['ZenlessZoneZero', 'HonkaiStarRail']: stride = 40
    elif game in ['ArknightsEndfield', 'WutheringWaves']: stride = 16
    
    buf_v_count = len(original_data) // stride
    linked_targets = get_linked_targets(comp_objects)
    all_involved = comp_objects + linked_targets
    
    # Collect all unique shape keys
    all_keys = set()
    for o in all_involved:
        if o.data.shape_keys:
            all_keys.update([sk.name for sk in o.data.shape_keys.key_blocks if sk != o.data.shape_keys.key_blocks[0]])

    depsgraph = context.evaluated_depsgraph_get()
    
    # Snapshot shape keys before doing anything so we can restore them later
    sk_snapshot = {}
    for obj in all_involved:
        if obj.data and obj.data.shape_keys:
            sk_snapshot[obj] = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}

    disabled_shapes = {c.shape_name for c in context.scene.rzm.shape_configs if c.disable_export}
    
    # 2. Disable armatures and protect Mirror (if any)
    set_armature_visibility(all_involved, False)
    mirror_states = {}
    for obj in comp_objects:
        mirror_states[obj] = []
        for mod in obj.modifiers:
            if mod.type == 'MIRROR' and mod.show_viewport:
                mirror_states[obj].append((mod, mod.use_mirror_merge, mod.use_clip))
                mod.use_mirror_merge = False
                mod.use_clip = False

    try:
        # 3. Cache BASIS state
        for obj in all_involved:
            if obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks: sk.value = 0.0
        bpy.context.view_layer.update()

        base_cache = {} # obj -> {coords, polys, bvh}
        for obj in comp_objects:
            b_obj_eval = obj.evaluated_get(depsgraph)
            b_eval = b_obj_eval.to_mesh()
            
            b_coords = [v.co.copy() for v in b_eval.vertices]
            p_indices = [list(p.vertices) for p in b_eval.polygons]
            bvh = BVHTree.FromPolygons(b_coords, p_indices) if b_coords else None
            
            base_cache[obj] = {
                'coords': b_coords,
                'polys': p_indices,
                'bvh': bvh
            }
            b_obj_eval.to_mesh_clear()

        # 4. Loop through shape keys
        for sk_name in all_keys:
            if sk_name in disabled_shapes:
                continue
            
            print(f"\n  [DEBUG] Evaluating shape key '{sk_name}':")
            current_buf = bytearray(original_data)
            
            active_objs = []
            for obj in comp_objects:
                is_active = False
                reason = "None"
                if obj.data.shape_keys and sk_name in obj.data.shape_keys.key_blocks:
                    is_active = True
                    reason = "Has direct Shape Key"
                else:
                    for mod in obj.modifiers:
                        if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                            if mod.type == 'SURFACE_DEFORM' and not getattr(mod, 'is_bound', False):
                                reason = f"Skipped: unbound {mod.name}"
                                continue
                            t = mod.target
                            if t.data and t.data.shape_keys and sk_name in t.data.shape_keys.key_blocks:
                                is_active = True
                                reason = f"Inherited via {mod.type} from '{t.name}'"
                                break
                
                if is_active:
                    active_objs.append(obj)
                    print(f"    -> [ACTIVE] '{obj.name}' ({reason})")
                else:
                    print(f"    -> [IGNORE] '{obj.name}' ({reason})")

            if not active_objs: 
                print(f"    -> No active objects found. Skipping shape key.")
                continue

            # Activate shape key
            for obj in all_involved:
                if obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = 1.0 if sk.name == sk_name else 0.0
            bpy.context.view_layer.update()

            # Cache TARGET state
            target_cache = {}
            for obj in active_objs:
                t_obj_eval = obj.evaluated_get(depsgraph)
                t_eval = t_obj_eval.to_mesh()
                t_coords = [v.co.copy() for v in t_eval.vertices]
                t_obj_eval.to_mesh_clear()
                
                if len(t_coords) == len(base_cache[obj]['coords']):
                    target_cache[obj] = t_coords

            # 5. Injection
            matched_count = 0
            obj_bake_stats = {obj: 0 for obj in active_objs}
            
            for i in range(buf_v_count):
                off = i * stride
                orig_v = Vector(struct.unpack_from("<3f", original_data, off))
                
                owner_obj = None
                best_dist = float('inf')
                best_face = None
                
                for obj, data in base_cache.items():
                    if not data['bvh']: continue
                    loc, normal, face_idx, dist = data['bvh'].find_nearest(orig_v)
                    if face_idx is not None:
                        # Fix for alphabetical bug: Tie-breaker prioritizing Active objects
                        is_current_active = obj in target_cache
                        is_best_active = owner_obj in target_cache if owner_obj else False
                        
                        if dist < best_dist - 1e-5:
                            best_dist = dist
                            owner_obj = obj
                            best_face = face_idx
                        elif abs(dist - best_dist) <= 1e-5:
                            if is_current_active and not is_best_active:
                                best_dist = dist
                                owner_obj = obj
                                best_face = face_idx

                if owner_obj and best_dist <= limit:
                    if owner_obj in target_cache:
                        face_verts = base_cache[owner_obj]['polys'][best_face]
                        b_coords = base_cache[owner_obj]['coords']
                        t_coords = target_cache[owner_obj]
                        
                        total_w = 0.0
                        blended_delta = Vector((0,0,0))
                        
                        for v_idx in face_verts:
                            v_dist = (b_coords[v_idx] - orig_v).length
                            weight = 1.0 / (v_dist**2 + 1e-10)
                            blended_delta += (t_coords[v_idx] - b_coords[v_idx]) * weight
                            total_w += weight
                        
                        final_delta = blended_delta / total_w
                        if final_delta.length > 1e-7:
                            struct.pack_into("<3f", current_buf, off, *(orig_v + final_delta))
                            matched_count += 1
                            obj_bake_stats[owner_obj] += 1

            clean_sk_name = sk_name.replace(" ", "_")
            out_name = f"Component{comp_id}_VB0_{clean_sk_name}.buf"
            with open(os.path.join(output_dir, out_name), "wb") as f:
                f.write(current_buf)
            
            print(f"    -> [BAKE REPORT] {sk_name}:")
            for obj, count in obj_bake_stats.items():
                if count > 0:
                    print(f"       + '{obj.name}' received {count} deformed vertices.")
                else:
                    print(f"       ! '{obj.name}' received 0 deformed vertices. (Maybe overlaps blocked it, or no shape change?)")
            
            print(f"[Puppet Master] Baked {sk_name} for Comp {comp_id} ({matched_count} verts)")

    finally:
        for obj, states in sk_snapshot.items():
            if obj.data and obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks:
                    if sk.name in states:
                        sk.value = states[sk.name]
        
        set_armature_visibility(all_involved, True)
        for obj, mods in mirror_states.items():
            for mod, merge, clip in mods:
                mod.use_mirror_merge = merge
                mod.use_clip = clip

    return True

class RZM_OT_PuppetMasterBake(bpy.types.Operator):
    bl_idname = "rzm.puppet_master_bake"
    bl_label = "Bake Puppet Master Shapes"
    bl_description = "Bake shape keys into buffers using Puppet Master v10.1 logic"

    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root):
            self.report({'ERROR'}, "Invalid export path!")
            return {'CANCELLED'}

        addons = context.scene.rzm.addons
        per_component = addons.puppet_master_per_component
        limit = addons.puppet_master_limit

        print("-" * 30)
        print(f"[Puppet Master] Starting Bake. Limit: {limit}")
        
        components = get_components_to_process(context, per_component)
        if not components:
            self.report({'WARNING'}, "No components found to process.")
            return {'CANCELLED'}

        for comp_id, objs in components.items():
            bake_component_shapes(context, comp_id, objs, mod_root, limit)

        self.report({'INFO'}, "Puppet Master baking finished.")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_PuppetMasterBake,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
