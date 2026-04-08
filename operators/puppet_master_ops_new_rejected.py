# RZMenu/operators/puppet_master_ops.py
import bpy
import struct
import os
import re
import json
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def set_armature_visibility(objects, visible):
    """Disables armatures for clean deformation baking."""
    for obj in objects:
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                mod.show_viewport = visible

def sanitize_name(name):
    """Python implementation of format_var macro from utils.j2."""
    if not name: return ""
    # 1. Remove prefixes
    res = name.lstrip('$@#~')
    # 2. Split and join with underscore (collapses multiple whitespaces)
    return "_".join(res.split())

def get_linked_targets(comp_objects):
    """Finds 'Puppet Master' targets (Body) that clothing is linked to."""
    targets = set()
    for obj in comp_objects:
        if obj.type != 'MESH': continue
        for mod in obj.modifiers:
            if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                targets.add(mod.target)
    return list(targets)

def load_xxmi_metadata(dir_path):
    """
    Parses hash.json to create a mapping of collection names to ComponentN names.
    Also prints a detailed summary of the component architecture.
    """
    mapping = {}
    if not dir_path: return mapping
    
    json_path = os.path.join(dir_path, "hash.json")
    if not os.path.exists(json_path):
        if dir_path.endswith("hash.json") and os.path.exists(dir_path):
            json_path = dir_path
        else:
            return mapping
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print("\n--- [METADATA] Components & Materials Architecture ---")
        total_materials = 0
        
        for i, item in enumerate(data):
            msg = f" [{i}] {item.get('component_name', 'Unnamed')}"
            base_name = item.get("component_name", f"Component{i}")
            
            # 1. Base Mapping
            mapping[base_name.lower()] = f"Component{i}"
            mapping[f"component{i}"] = f"Component{i}"
            
            # 2. Classification/Sub-Component Mapping
            classifications = item.get("object_classifications", [])
            if classifications:
                total_materials += len(classifications)
                msg += f" (Materials: {', '.join(classifications)}) -> {len(classifications)} buffers"
                for cls in classifications:
                    fname = f"Component{i}{cls}"
                    mapping[cls.lower()] = fname
                    mapping[f"{base_name}{cls}".lower()] = fname
            else:
                total_materials += 1
                msg += " (Single Material) -> 1 buffer"
                # Even if no classifications, we should allow matching by index/name
                fname = f"Component{i}"
                mapping[base_name.lower()] = fname
                mapping[f"component{i}"] = fname
            
            print(msg)
            
        print("-" * 50)
        print(f"Total Logical Components (Material Buffers): {total_materials}")
        print("-" * 50)
        
    except Exception as e:
        print(f"[RZM] Metadata Error parsing {json_path}: {e}")
        
    return mapping

def find_component_mapping_recursive(obj, mapping):
    """Traverses up the collection hierarchy to find a matching component name."""
    # Mapping of collection -> parent collection to allow upward traversal
    parent_map = {}
    for c in bpy.data.collections:
        for child in c.children:
            parent_map[child] = c

    # Check all collections this object belongs to
    for coll in obj.users_collection:
        curr = coll
        visited = set()
        while curr and curr not in visited:
            visited.add(curr)
            name_low = curr.name.lower()
            
            # 1. Direct match
            if name_low in mapping:
                return mapping[name_low]
            
            # 2. Clean name match (remove .001 etc)
            clean_name = re.sub(r"\.\d+$", "", name_low).strip()
            if clean_name in mapping:
                return mapping[clean_name]

            # 3. Move up to parent collection
            curr = parent_map.get(curr)
            
    return None

def get_components_to_process(context, per_component=False):
    """
    Returns a dict mapping comp_id -> list of objects.
    Logic differs by game type.
    """
    rzm = context.scene.rzm
    game = rzm.game.selection
    results = {}

    base_objs = [o for o in context.view_layer.objects if o.type == 'MESH']
    is_xxmi = game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']
    
    print("\n" + "="*50)
    print(f"--- [DEBUG] COMPONENT DISCOVERY (Game: {game}) ---")
    
    processed_objs = set()
    
    if is_xxmi:
        dump_path = ""
        if hasattr(context.scene, "xxmi") and hasattr(context.scene.xxmi, "dump_path"):
            if context.scene.xxmi.dump_path:
                dump_path = bpy.path.abspath(context.scene.xxmi.dump_path)
        
        if not dump_path:
            print("[Puppet Master] ERROR: XXMI Dump Path is empty! Please set it in XXMI tool settings.")
            return {}
            
        print(f"Checking for hash.json in: {dump_path}")
        mapping = load_xxmi_metadata(dump_path)
        
        if not mapping:
            print(f"[Puppet Master] ERROR: hash.json not found in Dump Path: {dump_path}")
            print("This is required for XXMI metadata matching.")
            return {}
            
        print(f"[Mode: Metadata Matching] Activated using mapping from: {dump_path}")

        for obj in base_objs:
            if obj.name not in context.view_layer.objects: continue
            
            # 1. Try metadata mapping (recursive collection check)
            comp_fullname = find_component_mapping_recursive(obj, mapping)
            
            if comp_fullname:
                results.setdefault(comp_fullname, []).append(obj)
                processed_objs.add(obj)
                print(f"  -> [INC] '{obj.name}' -> {comp_fullname} (via Metadata)")
                continue

            # 2. Try direct collection name regex (fallback)
            for coll in obj.users_collection:
                match = re.search(r"Component\s*(\d+)", coll.name, re.IGNORECASE)
                if match:
                    comp_id = match.group(1)
                    comp_fullname = f"Component{comp_id}"
                    results.setdefault(comp_fullname, []).append(obj)
                    processed_objs.add(obj)
                    print(f"  -> [INC] '{obj.name}' -> {comp_fullname} (via Coll Regex)")
                    break
    else:
        print("[Mode: Object Name Matching (EFMI/WWMI)]")
        for obj in base_objs:
            match = re.search(r"Component\s*(\d+)", obj.name, re.IGNORECASE)
            if match:
                comp_fullname = f"Component{match.group(1)}"
                results.setdefault(comp_fullname, []).append(obj)
                processed_objs.add(obj)
                print(f"  -> [INC] '{obj.name}' assigned to {comp_fullname} (via Regex)")
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

def bake_component_shapes(context, comp_fullname, comp_objects, mod_root, limit, single_shape_name=None, full_export_mode=False):
    """Core baking logic for a single component."""
    vb0_filename = f"{comp_fullname}_VB0.buf"
    vb0_path = os.path.join(mod_root, "Meshes", vb0_filename)
    
    if not os.path.exists(vb0_path):
        alt_path = os.path.join(mod_root, "Meshes", f"{comp_fullname}.buf")
        if os.path.exists(alt_path):
            vb0_path = alt_path
        else:
            print(f"[Puppet Master] Skipped '{comp_fullname}': Buffer not found at {vb0_path}")
            return False

    output_dir = os.path.join(mod_root, "SK")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(vb0_path, "rb") as f:
        original_data = bytearray(f.read())

    game = context.scene.rzm.game.selection
    stride = 32
    if game in ['ZenlessZoneZero', 'HonkaiStarRail']: stride = 40
    elif game in ['ArknightsEndfield', 'WutheringWaves']: stride = 16
    
    buf_v_count = len(original_data) // stride
    linked_targets = get_linked_targets(comp_objects)
    all_involved = comp_objects + linked_targets
    
    all_keys = set()
    if single_shape_name:
        all_keys.add(single_shape_name)
    else:
        for o in all_involved:
            if o.data.shape_keys:
                all_keys.update([sk.name for sk in o.data.shape_keys.key_blocks if sk != o.data.shape_keys.key_blocks[0]])

    depsgraph = context.evaluated_depsgraph_get()
    
    sk_snapshot = {}
    for obj in all_involved:
        if obj.data and obj.data.shape_keys:
            sk_snapshot[obj] = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}

    if full_export_mode:
        disabled_shapes = set()
    else:
        disabled_shapes = {c.shape_name for c in context.scene.rzm.shape_configs if c.disable_export}
    
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
        for obj in all_involved:
            if obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks: sk.value = 0.0
        bpy.context.view_layer.update()

        base_cache = {}
        for obj in comp_objects:
            b_obj_eval = obj.evaluated_get(depsgraph)
            b_eval = b_obj_eval.to_mesh()
            b_coords = [v.co.copy() for v in b_eval.vertices]
            p_indices = [list(p.vertices) for p in b_eval.polygons]
            bvh = BVHTree.FromPolygons(b_coords, p_indices) if b_coords else None
            base_cache[obj] = {'coords': b_coords, 'polys': p_indices, 'bvh': bvh}
            b_obj_eval.to_mesh_clear()

        for sk_name in all_keys:
            if sk_name in disabled_shapes: continue
            
            print(f"\n  [DEBUG] Evaluating shape key '{sk_name}':")
            current_buf = bytearray(original_data)
            active_objs = []
            for obj in comp_objects:
                is_active = False
                if obj.data.shape_keys and sk_name in obj.data.shape_keys.key_blocks:
                    is_active = True
                else:
                    for mod in obj.modifiers:
                        if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                            t = mod.target
                            if t.data and t.data.shape_keys and sk_name in t.data.shape_keys.key_blocks:
                                is_active = True
                                break
                if is_active: active_objs.append(obj)

            if not active_objs: continue

            for obj in all_involved:
                if obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = 1.0 if sk.name == sk_name else 0.0
            bpy.context.view_layer.update()

            target_cache = {}
            for obj in active_objs:
                t_obj_eval = obj.evaluated_get(depsgraph)
                t_eval = t_obj_eval.to_mesh()
                target_cache[obj] = [v.co.copy() for v in t_eval.vertices]
                t_obj_eval.to_mesh_clear()

            matched_count = 0
            for i in range(buf_v_count):
                off = i * stride
                orig_v = Vector(struct.unpack_from("<3f", original_data, off))
                
                owner_obj, best_dist, best_face = None, float('inf'), None
                for obj, data in base_cache.items():
                    if not data['bvh']: continue
                    loc, normal, face_idx, dist = data['bvh'].find_nearest(orig_v)
                    if face_idx is not None:
                        if dist < best_dist - 1e-5:
                            best_dist, owner_obj, best_face = dist, obj, face_idx
                        elif abs(dist - best_dist) <= 1e-5 and obj in target_cache:
                            owner_obj, best_face = obj, face_idx

                if owner_obj and best_dist <= limit and owner_obj in target_cache:
                    face_verts = base_cache[owner_obj]['polys'][best_face]
                    b_coords, t_coords = base_cache[owner_obj]['coords'], target_cache[owner_obj]
                    total_w, blended_delta = 0.0, Vector((0,0,0))
                    for v_idx in face_verts:
                        w = 1.0 / ((b_coords[v_idx] - orig_v).length**2 + 1e-10)
                        blended_delta += (t_coords[v_idx] - b_coords[v_idx]) * w
                        total_w += w
                    final_delta = blended_delta / total_w
                    if final_delta.length > 1e-7:
                        struct.pack_into("<3f", current_buf, off, *(orig_v + final_delta))
                        matched_count += 1

            clean_sk_name = sanitize_name(sk_name)
            out_name = f"{comp_fullname}_VB0_{clean_sk_name}.buf"
            with open(os.path.join(output_dir, out_name), "wb") as f:
                f.write(current_buf)
            print(f"[Puppet Master] Baked {sk_name} for '{comp_fullname}' ({matched_count} verts)")

    finally:
        for obj, states in sk_snapshot.items():
            if obj.data and obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks:
                    if sk.name in states: sk.value = states[sk.name]
        set_armature_visibility(all_involved, True)
        for obj, mods in mirror_states.items():
            for mod, merge, clip in mods:
                mod.use_mirror_merge, mod.use_clip = merge, clip

    return True

class RZM_OT_PuppetMasterBake(bpy.types.Operator):
    bl_idname = "rzm.puppet_master_bake"
    bl_label = "Bake Puppet Master Shapes"
    bl_description = "Bake shape keys into buffers using Puppet Master metadata logic"

    full_export_mode: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root):
            self.report({'ERROR'}, "Invalid export path!")
            return {'CANCELLED'}

        addons = context.scene.rzm.addons
        per_component = False if self.full_export_mode else addons.puppet_master_per_component
        limit = addons.puppet_master_limit

        print("-" * 30)
        print(f"[Puppet Master] Starting Bake. Limit: {limit} (Full Export Mode: {self.full_export_mode})")
        
        components = get_components_to_process(context, per_component)
        if not components:
            self.report({'WARNING'}, "No components found to process.")
            return {'CANCELLED'}

        for comp_fullname, objs in components.items():
            bake_component_shapes(context, comp_fullname, objs, mod_root, limit, full_export_mode=self.full_export_mode)

        self.report({'INFO'}, "Puppet Master baking finished.")
        return {'FINISHED'}

class RZM_OT_PuppetMasterBakeSingle(bpy.types.Operator):
    bl_idname = "rzm.puppet_master_bake_single"
    bl_label = "Bake Selected Shape (All Components)"
    bl_description = "Bake only the currently selected shape key across all detected components"

    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root):
            self.report({'ERROR'}, "Invalid export path!")
            return {'CANCELLED'}

        rzm = context.scene.rzm
        if not (0 <= context.scene.rzm_active_shape_config_index < len(rzm.shape_configs)):
            self.report({'ERROR'}, "No active shape configuration selected!")
            return {'CANCELLED'}
        
        target_shape = rzm.shape_configs[context.scene.rzm_active_shape_config_index].shape_name
        limit = rzm.addons.puppet_master_limit

        print("-" * 30)
        print(f"[Puppet Master] Baking Single Shape: {target_shape}. Limit: {limit}")
        
        components = get_components_to_process(context, per_component=False)
        if not components:
            self.report({'WARNING'}, "No components found to process.")
            return {'CANCELLED'}

        for comp_fullname, objs in components.items():
            bake_component_shapes(context, comp_fullname, objs, mod_root, limit, single_shape_name=target_shape)

        self.report({'INFO'}, f"Baking finished for shape: {target_shape}")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_PuppetMasterBake,
    RZM_OT_PuppetMasterBakeSingle,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
