# RZMenu/operators/puppet_master_ops.py
# VERSION: 14.0 (MODULAR CONFIG & STRICT WHITELIST)
import bpy
import struct
import os
import re
import json
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# --- HELPERS ---
def get_all_meshes_in_collection(collection, meshes_set, context, settings):
    """
    Recursively adds visible meshes from non-excluded collections.
    Respects: ignore_hidden, ignore_nested, ignore_hidden_coll.
    """
    view_layer = context.view_layer
    
    # 1. Check if this specific collection is excluded/hidden
    def find_layer_coll(root, target):
        if root.collection == target: return root
        for child in root.children:
            res = find_layer_coll(child, target)
            if res: return res
        return None

    lc = find_layer_coll(view_layer.layer_collection, collection)
    if lc:
        if lc.exclude: return # Strict Exclusion
        if settings.get('ignore_hidden_coll', False) and not lc.is_visible: return

    # 2. Process objects in this collection
    for obj in collection.objects:
        if obj.type != 'MESH': continue
        
        # Filter: Hidden Objects
        if settings.get('ignore_hidden_obj', False) and obj.hide_get(view_layer=view_layer):
            continue
            
        meshes_set.add(obj)
            
    # 3. Process sub-collections if not ignored
    if not settings.get('ignore_nested', False):
        for child in collection.children:
            get_all_meshes_in_collection(child, meshes_set, context, settings)

def set_armature_visibility(objects, visible):
    for obj in objects:
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                mod.show_viewport = visible

def get_linked_targets(comp_objects):
    targets = set()
    for obj in comp_objects:
        for mod in obj.modifiers:
            if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                targets.add(mod.target)
    return list(targets)

def load_xxmi_metadata(dir_path):
    if not dir_path: return []
    json_path = os.path.join(dir_path, "hash.json")
    if not os.path.exists(json_path):
        if dir_path.endswith("hash.json") and os.path.exists(dir_path):
            json_path = dir_path
        else: return []
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

# --- CORE DISCOVERY ---
def get_components_to_process(context, per_component=False):
    """Returns mapping under logical component names based on modular settings."""
    scene = context.scene
    rzm = scene.rzm
    game_name = rzm.game.name
    xxmi_list = ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']
    is_xxmi = game_name in xxmi_list
    
    # --- Modular Visibility Settings ---
    settings = {
        'ignore_hidden_obj': False,
        'ignore_hidden_coll': False,
        'ignore_nested': False
    }
    
    if is_xxmi and hasattr(scene, "xxmi"):
        settings['ignore_hidden_obj'] = scene.xxmi.ignore_hidden
    elif game_name == 'ArknightsEndfield' and hasattr(scene, "efmi_tools_settings"):
        efmi = scene.efmi_tools_settings
        settings['ignore_hidden_obj'] = efmi.ignore_hidden_objects
        settings['ignore_hidden_coll'] = efmi.ignore_hidden_collections
        settings['ignore_nested'] = efmi.ignore_nested_collections
    
    print("\n" + "="*70)
    print(f"[RZM] [DEBUG] COMPONENT DISCOVERY (v14.0 - Modular Config)")
    print(f"  -> Settings: {settings}")
    
    results = {}
    
    if is_xxmi:
        dump_path_prop = scene.xxmi.dump_path if hasattr(scene, "xxmi") else ""
        if not dump_path_prop: return {}
        dump_path = os.path.normpath(bpy.path.abspath(dump_path_prop))
        mod_name = os.path.basename(dump_path)
        comp_metadata = load_xxmi_metadata(dump_path)
        if not comp_metadata: return {}

        for component in comp_metadata:
            comp_name = component.get("component_name", "")
            base_fullname = f"{mod_name}{comp_name}"
            classifications = component.get("object_classifications", [])
            
            comp_meshes = set()
            for part in classifications:
                part_fullname = base_fullname + part
                matching_collections = [c for c in bpy.data.collections if c.name.lower().startswith(part_fullname.lower())]
                for coll in matching_collections:
                    get_all_meshes_in_collection(coll, comp_meshes, context, settings)
            
            if comp_meshes:
                results[comp_name] = list(comp_meshes)
    else:
        # Legacy/EFMI fallback
        base_objs = [o for o in context.view_layer.objects if o.type == 'MESH']
        for obj in base_objs:
            # Filter by visibility/exclusion
            if settings['ignore_hidden_obj'] and obj.hide_get(): continue
            
            match = re.search(r"Component\s*(\d+)", obj.name, re.IGNORECASE)
            if match:
                results.setdefault(f"Component{match.group(1)}", []).append(obj)

    for key in results: results[key] = list(set(results[key]))

    if per_component and context.active_object:
        target_name = None
        for name, objs in results.items():
            if context.active_object in objs:
                target_name = name
                break
        if target_name: return {target_name: results[target_name]}
        return {}

    print(f"[RZM] [DEBUG] Discovery complete. Found {len(results)} groups.")
    return results

# --- CORE BAKE ---
def bake_component_shapes(context, base_name, comp_objects, mod_root, limit, single_shape_name=None, full_export_mode=False):
    """Bake shapes with strict whitelisting from context.scene.rzm.shape_configs."""
    vb0_path = None
    dump_name = os.path.basename(os.path.normpath(bpy.path.abspath(context.scene.xxmi.dump_path))) if hasattr(context.scene, "xxmi") else ""

    # Path Priority
    patterns = [f"{base_name}Position.buf", f"{base_name}_VB0.buf", f"{base_name}.buf"]
    if dump_name:
        patterns.insert(0, f"{dump_name}{base_name}Position.buf")
        patterns.insert(1, f"{dump_name}{base_name}_VB0.buf")
    
    subfolders = ["", "Meshes", "Buffers"]
    for sub in subfolders:
        curr_dir = os.path.join(mod_root, sub) if sub else mod_root
        if not os.path.exists(curr_dir): continue
        for p in patterns:
            test_path = os.path.join(curr_dir, p)
            if os.path.exists(test_path):
                vb0_path = test_path
                break
        if vb0_path: break
    
    # Fuzzy Fallback
    if not vb0_path:
        for sub in subfolders:
            curr_dir = os.path.join(mod_root, sub) if sub else mod_root
            if not os.path.exists(curr_dir): continue
            for f in os.listdir(curr_dir):
                f_low = f.lower()
                if f_low.endswith(".buf") and base_name.lower() in f_low and ("position" in f_low or "vb0" in f_low):
                    vb0_path = os.path.join(curr_dir, f)
                    break
            if vb0_path: break

    if not vb0_path: return False

    output_dir = os.path.join(mod_root, "SK")
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    with open(vb0_path, "rb") as f:
        original_data = bytearray(f.read())

    # Stride
    game = context.scene.rzm.game.name
    stride = 40 if game in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'} else (16 if game in {'ArknightsEndfield', 'WutheringWaves'} else 32)
    
    buf_v_count = len(original_data) // stride
    linked_targets = get_linked_targets(comp_objects)
    all_involved = comp_objects + list(set(linked_targets))
    
    # --- v14.0: SOURCE OF TRUTH WHITELIST ---
    rzm = context.scene.rzm
    
    if single_shape_name:
        # If manual "Bake Selection", we bypass the whitelist for just that one shape
        all_keys = {single_shape_name}
    else:
        # Strictly follow the Discover Shape Keys results stored in shape_configs
        all_keys = {c.shape_name for c in rzm.shape_configs if not c.disable_export}
        
    if not all_keys: return True

    print(f"\n[RZM] [BAKE] Component: '{base_name}' | Shapes: {len(all_keys)}")

    depsgraph = context.evaluated_depsgraph_get()
    sk_snapshot = {}
    for obj in all_involved:
        if obj.data and obj.data.shape_keys:
            sk_snapshot[obj] = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}

    set_armature_visibility(all_involved, False)
    mirror_states = {}
    for obj in comp_objects:
        mirror_states[obj] = []
        for mod in obj.modifiers:
            if mod.type == 'MIRROR' and mod.show_viewport:
                mirror_states[obj].append((mod, mod.use_mirror_merge, mod.use_clip))
                mod.use_mirror_merge, mod.use_clip = False, False

    try:
        # BASIS Cache
        base_cache = {}
        for obj in comp_objects:
            for a_obj in all_involved:
                if a_obj.data.shape_keys:
                    for sk in a_obj.data.shape_keys.key_blocks: sk.value = 0.0
            bpy.context.view_layer.update()
            b_obj_eval = obj.evaluated_get(depsgraph)
            b_eval = b_obj_eval.to_mesh()
            b_coords = [v.co.copy() for v in b_eval.vertices]
            p_indices = [list(p.vertices) for p in b_eval.polygons]
            bvh = BVHTree.FromPolygons(b_coords, p_indices) if b_coords else None
            base_cache[obj] = {'coords': b_coords, 'polys': p_indices, 'bvh': bvh}
            b_obj_eval.to_mesh_clear()

        for sk_name in all_keys:
            print(f"  [SK] Submitting: '{sk_name}'")
            current_buf = bytearray(original_data)
            active_objs = []
            
            for obj in all_involved:
                if obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = 1.0 if sk.name == sk_name else 0.0
            bpy.context.view_layer.update()

            target_cache = {}
            for obj in comp_objects:
                is_active = (obj.data.shape_keys and sk_name in obj.data.shape_keys.key_blocks)
                if not is_active:
                    for mod in obj.modifiers:
                        if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                            t = mod.target
                            if t.data and t.data.shape_keys and sk_name in t.data.shape_keys.key_blocks:
                                is_active = True
                                break
                if is_active:
                    t_obj_eval = obj.evaluated_get(depsgraph)
                    t_eval = t_obj_eval.to_mesh()
                    t_coords = [v.co.copy() for v in t_eval.vertices]
                    t_obj_eval.to_mesh_clear()
                    if len(t_coords) == len(base_cache[obj]['coords']):
                        target_cache[obj] = t_coords
                        active_objs.append(obj)

            if not active_objs: continue

            matched_count = 0
            for i in range(buf_v_count):
                if i > 0 and i % 50000 == 0:
                    print(f"      [HEARTBEAT] Vertex {i} / {buf_v_count}...")
                off = i * stride
                orig_v = Vector(struct.unpack_from("<3f", original_data, off))
                owner_obj, best_dist, best_face = None, float('inf'), None
                for obj, data in base_cache.items():
                    if not data['bvh']: continue
                    loc, normal, face_idx, dist = data['bvh'].find_nearest(orig_v)
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

            clean_sk_name = re.sub(r'[\\/:*?"<>|]', '_', sk_name).replace(" ", "_").replace(".", "_")
            out_name = f"{base_name}_VB0_{clean_sk_name}.buf"
            with open(os.path.join(output_dir, out_name), "wb") as f:
                f.write(current_buf)
            print(f"    -> [DONE] {out_name} ({matched_count} verts)")

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

# --- OPERATORS ---
class RZM_OT_PuppetMasterBake(bpy.types.Operator):
    bl_idname = "rzm.puppet_master_bake"
    bl_label = "Bake Puppet Master Shapes"
    bl_description = "Bake shape keys using strictly RZMenu Shape Configs (v14.0)"
    full_export_mode: bpy.props.BoolProperty(default=False)
    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root): return {'CANCELLED'}
        addons = context.scene.rzm.addons
        per_component = False if self.full_export_mode else addons.puppet_master_per_component
        limit = addons.puppet_master_limit
        components = get_components_to_process(context, per_component)
        if not components: return {'CANCELLED'}
        for base_name, objs in components.items():
            bake_component_shapes(context, base_name, objs, mod_root, limit, full_export_mode=self.full_export_mode)
        return {'FINISHED'}

class RZM_OT_PuppetMasterBakeSingle(bpy.types.Operator):
    bl_idname = "rzm.puppet_master_bake_single"
    bl_label = "Bake Selected Shape Key"
    bl_description = "Bake the active shape regardless of whitelist"
    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root): return {'CANCELLED'}
        rzm = context.scene.rzm
        if not (0 <= context.scene.rzm_active_shape_config_index < len(rzm.shape_configs)): return {'CANCELLED'}
        target_shape = rzm.shape_configs[context.scene.rzm_active_shape_config_index].shape_name
        limit = rzm.addons.puppet_master_limit
        components = get_components_to_process(context, per_component=False)
        if not components: return {'CANCELLED'}
        for base_name, objs in components.items():
            bake_component_shapes(context, base_name, objs, mod_root, limit, single_shape_name=target_shape)
        return {'FINISHED'}

classes_to_register = [RZM_OT_PuppetMasterBake, RZM_OT_PuppetMasterBakeSingle]
def register():
    for cls in classes_to_register: bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(classes_to_register): bpy.utils.unregister_class(cls)
