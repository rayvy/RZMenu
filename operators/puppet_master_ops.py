# RZMenu/operators/puppet_master_ops.py
import bpy
import os
import re
import json
import time
import struct
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# --- HELPERS ---
def get_all_meshes_in_collection(collection, meshes_set, context, settings):
    view_layer = context.view_layer
    def find_layer_coll(root, target):
        if root.collection == target: return root
        for child in root.children:
            res = find_layer_coll(child, target)
            if res: return res
        return None

    lc = find_layer_coll(view_layer.layer_collection, collection)
    if lc:
        if lc.exclude: return
        if settings.get('ignore_hidden_coll', False) and not lc.is_visible: return

    for obj in collection.objects:
        if obj.type != 'MESH': continue
        if settings.get('ignore_hidden_obj', False) and obj.hide_get(view_layer=view_layer):
            continue
        meshes_set.add(obj)
            
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
    scene = context.scene
    rzm = scene.rzm
    game_name = rzm.game.name
    xxmi_list = ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']
    is_xxmi = game_name in xxmi_list
    
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
                    for obj in coll.all_objects:
                        if obj.type == 'MESH':
                            if settings['ignore_hidden_obj'] and obj.hide_get(): continue
                            comp_meshes.add(obj)
                
                for obj in context.view_layer.objects:
                    if obj.type != 'MESH': continue
                    if settings['ignore_hidden_obj'] and obj.hide_get(): continue
                    if obj.name.lower() == part_fullname.lower() or obj.name.lower().startswith(part_fullname.lower() + "."):
                        comp_meshes.add(obj)

            if comp_meshes:
                results[comp_name] = list(comp_meshes)
    else:
        base_objs = [o for o in context.view_layer.objects if o.type == 'MESH']
        for obj in base_objs:
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

    return results

# --- NUMPY SPATIAL INDEX ---
def _build_spatial_index(coords_np, tri_verts_np):
    if len(tri_verts_np) == 0:
        return None, None
    centroids = coords_np[tri_verts_np].mean(axis=1).astype(np.float32)
    try:
        from scipy.spatial import KDTree
        return KDTree(centroids), centroids
    except ImportError:
        try:
            import mathutils
            size = len(centroids)
            tree = mathutils.kdtree.KDTree(size)
            for i, c in enumerate(centroids):
                tree.insert(c, i)
            tree.balance()
            return tree, centroids
        except:
            return None, None

def _idw_delta_batch(buf_verts_np, owner_data, target_data):
    base_coords = owner_data['coords']
    kd          = owner_data['kd']
    bvh         = owner_data['bvh']
    deltas_np   = target_data - base_coords

    if kd is not None:
        try:
            from scipy.spatial import KDTree
            if isinstance(kd, KDTree):
                tri_verts   = owner_data['tri_verts']
                _, face_ids = kd.query(buf_verts_np, workers=-1)
                face_v_idx  = tri_verts[face_ids]
                face_coords = base_coords[face_v_idx]
                diff        = face_coords - buf_verts_np[:, np.newaxis, :]
                sq_dist     = (diff * diff).sum(axis=2) + 1e-10
                w           = 1.0 / sq_dist
                face_deltas = deltas_np[face_v_idx]
                out = (w[:, :, np.newaxis] * face_deltas).sum(axis=1) / w.sum(axis=1, keepdims=True)
                return out
        except ImportError: pass

        tri_verts = owner_data['tri_verts']
        out = np.zeros_like(buf_verts_np)
        for i, bv in enumerate(buf_verts_np):
            _, face_idx, _ = kd.find(bv)
            face_v_idx = tri_verts[face_idx]
            bv_face    = base_coords[face_v_idx]
            diff       = bv_face - bv
            sq_dist    = (diff * diff).sum(axis=1) + 1e-10
            w          = 1.0 / sq_dist
            out[i]     = (w[:, None] * deltas_np[face_v_idx]).sum(axis=0) / w.sum()
        return out
    else:
        polys    = owner_data['polys']
        face_ids = []
        for bv in buf_verts_np:
            _, _, face_idx, _ = bvh.find_nearest(Vector(bv))
            face_ids.append(face_idx if face_idx is not None else 0)
        face_ids = np.array(face_ids, dtype=np.int32)
        out = np.zeros_like(buf_verts_np)
        for n, (bv, fi) in enumerate(zip(buf_verts_np, face_ids)):
            face_v_idx = np.array(polys[fi])
            bv_face    = base_coords[face_v_idx]
            diff       = bv_face - bv
            sq_dist    = (diff * diff).sum(axis=1) + 1e-10
            w          = 1.0 / sq_dist
            out[n]     = (w[:, None] * deltas_np[face_v_idx]).sum(axis=0) / w.sum()
        return out

# --- FILENAMING (RESTORED) ---
def _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name):
    raw_base   = (dump_name + base_name) if is_xxmi else base_name
    clean_base = re.sub(r'[\\/:*?"<>|]', '_', raw_base).replace(' ', '_').replace('.', '_')
    clean_sk   = re.sub(r'[\\/:*?"<>|]', '_', sk_name).replace(' ', '_').replace('.', '_')
    return f"{clean_base}_{clean_sk}.buf"

# --- PHASE 2 FAST PATH (RESTORED PARTIAL FALLBACK) ---
def _bake_with_direct_offsets(sk_owner_map, comp_cache, original_bytes, stride, buf_v_count, output_dir, base_name, dump_name, is_xxmi):
    stride_f32  = stride // 4
    cache_objects = {entry['name']: entry for entry in comp_cache.get('objects', [])}
    
    # Track which objects succeed and which fail
    fallback_objs_per_sk = {} 

    for sk_name in list(sk_owner_map.keys()):
        buf_f32       = np.frombuffer(bytes(original_bytes), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
        matched_count = 0
        fallback_this = []

        sk_direct     = sk_owner_map[sk_name]['direct']
        sk_via_target = sk_owner_map[sk_name]['via_target']

        for obj in sk_direct:
            entry = cache_objects.get(obj.name)
            if entry is None:
                fallback_this.append(obj)
                continue

            vb_off = entry['vb_offset']
            vb_cnt = entry['vb_count']

            if not (obj.data and obj.data.shape_keys): continue
            sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
            ba_blk = obj.data.shape_keys.reference_key
            if sk_blk is None or not sk_blk.data or not ba_blk.data: continue

            n = len(sk_blk.data)
            v_map = entry.get('vertex_map')
            m_idx = entry.get('mat_idx', 0)
            
            if v_map and len(v_map) == vb_cnt:
                import mathutils
                if m_idx == 1:   
                    mat = obj.matrix_world
                elif m_idx == 2: 
                    root_obj_name = comp_cache.get('root_obj')
                    root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else None
                    mat = root_obj.matrix_world.inverted() @ obj.matrix_world if root_obj else mathutils.Matrix.Identity(4)
                else:            
                    mat = mathutils.Matrix.Identity(4)
                
                sk_co = np.array([kp.co for kp in sk_blk.data], dtype=np.float32)
                ba_co = np.array([kp.co for kp in ba_blk.data], dtype=np.float32)
                
                mat_rot = np.array(mat.to_3x3(), dtype=np.float32)
                delta_local = sk_co - ba_co
                delta_mapped = (delta_local @ mat_rot.T)[v_map]
                
                nonzero = np.linalg.norm(delta_mapped, axis=1) > 1e-7
                if not nonzero.any(): continue
                
                idx = np.where(nonzero)[0]
                buf_indices = vb_off + idx
                
                new_xyz = (buf_f32[buf_indices, :3] + delta_mapped[idx]).astype(np.float32)
                buf_f32[buf_indices, 0] = new_xyz[:, 0]
                buf_f32[buf_indices, 1] = new_xyz[:, 1]
                buf_f32[buf_indices, 2] = new_xyz[:, 2]
                matched_count += len(idx)

            elif n == vb_cnt:
                sk_co = np.array([kp.co for kp in sk_blk.data], dtype=np.float32)
                ba_co = np.array([kp.co for kp in ba_blk.data], dtype=np.float32)
                delta = sk_co - ba_co
                nonzero = np.linalg.norm(delta, axis=1) > 1e-7
                if not nonzero.any(): continue
                    
                idx = np.where(nonzero)[0]
                buf_indices = vb_off + idx
                new_xyz = (buf_f32[buf_indices, :3] + delta[idx]).astype(np.float32)
                buf_f32[buf_indices, 0] = new_xyz[:, 0]
                buf_f32[buf_indices, 1] = new_xyz[:, 1]
                buf_f32[buf_indices, 2] = new_xyz[:, 2]
                matched_count += len(idx)
                
            else:
                fallback_this.append(obj)

        out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
        
        # Only write if we matched something or if we don't have ANY fallbacks for this key
        if matched_count > 0:
            with open(os.path.join(output_dir, out_name), 'wb') as f:
                f.write(buf_f32.tobytes())
                
        fallback_objs_per_sk[sk_name] = fallback_this

    # True only if absolutely NO objects fell back across ALL shapekeys
    all_ok = all(len(v) == 0 for v in fallback_objs_per_sk.values())
    return all_ok, fallback_objs_per_sk

def _scan_sk_owners(comp_objects, all_keys):
    result = {}
    for sk_name in all_keys:
        direct, via_target = [], []
        for obj in comp_objects:
            if not (obj.data and obj.data.shape_keys):
                for mod in obj.modifiers:
                    if (mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'}
                            and mod.show_viewport and mod.target
                            and mod.target.data and mod.target.data.shape_keys
                            and sk_name in mod.target.data.shape_keys.key_blocks):
                        via_target.append(obj)
                        break
                continue

            sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
            if sk_blk is not None:
                ba_blk = obj.data.shape_keys.reference_key
                if sk_blk.data and ba_blk.data:
                    sk_co = np.array([kp.co for kp in sk_blk.data], dtype=np.float32)
                    ba_co = np.array([kp.co for kp in ba_blk.data], dtype=np.float32)
                    if np.any(np.abs(sk_co - ba_co) > 1e-7):
                        direct.append(obj)
                        continue
            for mod in obj.modifiers:
                if (mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'}
                        and mod.show_viewport and mod.target
                        and mod.target.data and mod.target.data.shape_keys
                        and sk_name in mod.target.data.shape_keys.key_blocks):
                    via_target.append(obj)
                    break

        if direct or via_target:
            result[sk_name] = {'direct': direct, 'via_target': via_target}
    return result

# --- CORE BAKE ---
def bake_component_shapes(context, base_name, comp_objects, mod_root, limit, single_shape_name=None, full_export_mode=False):
    vb0_path = None
    dump_name = (os.path.basename(os.path.normpath(bpy.path.abspath(context.scene.xxmi.dump_path)))
                 if hasattr(context.scene, "xxmi") else "")

    game = context.scene.rzm.game.name
    is_xxmi = game in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}

    # Path Search
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

    if not vb0_path: return False

    output_dir = os.path.join(mod_root, "SK")
    os.makedirs(output_dir, exist_ok=True)

    with open(vb0_path, "rb") as f:
        original_bytes = f.read()
    original_data = bytearray(original_bytes)

    stride = 40 if is_xxmi else 16 if game in {'ArknightsEndfield', 'WutheringWaves'} else 32
    buf_v_count = len(original_data) // stride
    
    rzm = context.scene.rzm
    all_keys = {single_shape_name} if single_shape_name else {c.shape_name for c in rzm.shape_configs if not c.disable_export}
    if not all_keys: return True

    sk_owner_map = _scan_sk_owners(comp_objects, all_keys)

    # RESTORED: FILTERED PLACEHOLDERS
    # Creates zero-delta .buf files for keys so the engine does not complain about missing files.
    for sk_name in sk_owner_map.keys() if sk_owner_map else all_keys:
        out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
        with open(os.path.join(output_dir, out_name), "wb") as f:
            f.write(original_bytes)

    if not sk_owner_map:
        print(f"  [PRE-SCAN] No real shape keys found — skipping component (placeholders saved)")
        return True

    try:
        from .export_cache import component_cache
        comp_cache = component_cache(base_name)
    except Exception:
        comp_cache = None

    # FAST PATH with Fallback evaluation
    sk_owner_map_slow = sk_owner_map
    if comp_cache is not None:
        print(f"  [CACHE] HIT — using direct offset write")
        fast_ok, fallback_map = _bake_with_direct_offsets(
            sk_owner_map, comp_cache, original_bytes, stride, buf_v_count, output_dir, base_name, dump_name, is_xxmi
        )
        if fast_ok:
            return True # Everything worked perfectly in Fast Path!
            
        print(f"  [CACHE] Some objects missed mapping, falling back to Spatial Path")
        # Isolate ONLY the objects that failed Fast Path
        sk_owner_map_slow = {}
        for sk_name, owners in sk_owner_map.items():
            fb = fallback_map.get(sk_name, [])
            if fb:
                sk_owner_map_slow[sk_name] = {'direct': fb, 'via_target': owners['via_target']}
        
        if not sk_owner_map_slow:
            return True

    # SLOW PATH (Spatial IDW for fallbacks)
    print(f"  [PHASE 1] Spatial Matching (Slow Path)")
    raw_np     = np.frombuffer(original_bytes, dtype=np.uint8)
    float_view = raw_np.reshape(buf_v_count, stride).view(np.float32).reshape(buf_v_count, stride // 4)
    buf_xyz    = float_view[:, :3].astype(np.float64)

    active_objects_set = set()
    for owners in sk_owner_map_slow.values():
        active_objects_set.update(owners['direct'])
        active_objects_set.update(owners['via_target'])
    active_objects = list(active_objects_set)

    linked_targets = get_linked_targets(active_objects)
    all_involved   = active_objects + list(set(linked_targets))
    depsgraph = context.evaluated_depsgraph_get()

    sk_snapshot = {}
    for obj in all_involved:
        if obj.data and obj.data.shape_keys:
            sk_snapshot[obj] = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}

    set_armature_visibility(all_involved, False)
    mirror_states = {}
    for obj in active_objects:
        mirror_states[obj] = []
        for mod in obj.modifiers:
            if mod.type == 'MIRROR' and mod.show_viewport:
                mirror_states[obj].append((mod, mod.use_mirror_merge, mod.use_clip))
                mod.use_mirror_merge, mod.use_clip = False, False

    try:
        for a_obj in all_involved:
            if a_obj.data and a_obj.data.shape_keys:
                for sk in a_obj.data.shape_keys.key_blocks:
                    sk.value = 0.0
        context.view_layer.update()
        depsgraph.update()

        base_cache = {}
        for obj in active_objects:
            eval_obj  = obj.evaluated_get(depsgraph)
            b_eval    = eval_obj.to_mesh()
            
            # Align evaluated mesh to buffer orientation based on Cache (if available)
            import mathutils
            m_idx = 0
            if comp_cache:
                for entry in comp_cache.get('objects', []):
                    if entry['name'] == obj.name:
                        m_idx = entry.get('mat_idx', 0)
                        break
            
            if m_idx == 1: mat = obj.matrix_world
            elif m_idx == 2:
                root_obj_name = comp_cache.get('root_obj')
                root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else active_objects[0]
                mat = root_obj.matrix_world.inverted() @ obj.matrix_world
            else: mat = mathutils.Matrix.Identity(4)

            coords    = np.array([np.array(mat @ v.co, dtype=np.float64) for v in b_eval.vertices], dtype=np.float64)
            mat_rot   = np.array(mat.to_3x3(), dtype=np.float64)
            
            polys     = [list(p.vertices) for p in b_eval.polygons]
            loop_tris = b_eval.calc_loop_triangles()
            tri_verts = np.array([[lt.vertices[0], lt.vertices[1], lt.vertices[2]] for lt in loop_tris], dtype=np.int32) if loop_tris else np.zeros((0, 3), dtype=np.int32)
            eval_obj.to_mesh_clear()

            kd, centroids = _build_spatial_index(coords, tri_verts)
            bvh = None if kd is not None else BVHTree.FromPolygons([Vector(c) for c in coords], polys)
            
            base_cache[obj] = {
                'coords': coords, 'tri_verts': tri_verts, 'polys': polys,
                'kd': kd, 'centroids': centroids, 'bvh': bvh, 'mat_rot': mat_rot
            }

        def _assign_owners_bulk(buf_xyz, base_cache, limit):
            N = len(buf_xyz)
            owner_map, dist_map = np.zeros(N, dtype=np.int64), np.full(N, np.inf, dtype=np.float64)
            has_scipy = base_cache and next(iter(base_cache.values()))['kd'] is not None

            if has_scipy:
                for obj, data in base_cache.items():
                    dists, _ = data['kd'].query(buf_xyz, workers=-1)
                    improve = dists < dist_map - 1e-5
                    owner_map[improve], dist_map[improve] = id(obj), dists[improve]
                owner_map[dist_map > limit] = 0
            else:
                for i, bv in enumerate(buf_xyz):
                    mv = Vector(bv)
                    for obj, data in base_cache.items():
                        if data['bvh'] is None: continue
                        _, _, _, dist = data['bvh'].find_nearest(mv)
                        if dist < dist_map[i] - 1e-5:
                            dist_map[i], owner_map[i] = dist, id(obj)
                owner_map[dist_map > limit] = 0
            return owner_map, dist_map

        owner_map, dist_map = _assign_owners_bulk(buf_xyz, base_cache, limit)
        stride_f32 = stride // 4

        for sk_name, owners in sk_owner_map_slow.items():
            sk_direct, sk_via_target = owners['direct'], owners['via_target']

            for obj in all_involved:
                if obj.data and obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = 1.0 if sk.name == sk_name else 0.0
            context.view_layer.update()
            depsgraph.update()

            target_cache = {}
            for obj in sk_direct + sk_via_target:
                if obj not in base_cache: continue
                eval_obj = obj.evaluated_get(depsgraph)
                t_eval   = eval_obj.to_mesh()
                
                mat_rot = base_cache[obj]['mat_rot']
                t_coords = np.array([np.array(mat_rot @ v.co, dtype=np.float64) for v in t_eval.vertices], dtype=np.float64)
                
                eval_obj.to_mesh_clear()
                if len(t_coords) == len(base_cache[obj]['coords']):
                    target_cache[obj] = t_coords

            if not target_cache: continue

            out_name  = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
            out_path  = os.path.join(output_dir, out_name)
            
            # LOAD EXISTING BUFFER SO WE DON'T OVERWRITE FAST PATH PROGRESS
            if os.path.exists(out_path):
                with open(out_path, "rb") as _f:
                    _base_bytes = _f.read()
                buf_f32 = np.frombuffer(_base_bytes, dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
            else:
                buf_f32 = np.frombuffer(bytes(original_data), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
                
            matched_count = 0

            for obj, t_coords in target_cache.items():
                mask = (owner_map == id(obj))
                if not mask.any(): continue
                
                buf_sub      = buf_xyz[mask]
                deltas       = _idw_delta_batch(buf_sub, base_cache[obj], t_coords)
                nonzero      = np.linalg.norm(deltas, axis=1) > 1e-7
                if not nonzero.any(): continue
                
                indices      = np.where(mask)[0][nonzero]
                valid_deltas = deltas[nonzero]
                new_xyz      = (buf_xyz[indices] + valid_deltas).astype(np.float32)
                
                buf_f32[indices, 0] = new_xyz[:, 0]
                buf_f32[indices, 1] = new_xyz[:, 1]
                buf_f32[indices, 2] = new_xyz[:, 2]
                matched_count += len(indices)

            if matched_count > 0:
                with open(out_path, "wb") as f:
                    f.write(buf_f32.tobytes())
                print(f"    -> [DONE] {out_name} ({matched_count} verts merged via Slow Path)")

    finally:
        for obj, states in sk_snapshot.items():
            if obj.data and obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks:
                    if sk.name in states:
                        sk.value = states[sk.name]
        set_armature_visibility(all_involved, True)
        for obj, mods in mirror_states.items():
            for mod, merge, clip in mods:
                mod.use_mirror_merge, mod.use_clip = merge, clip

    return True

class RZM_OT_PuppetMasterBake(bpy.types.Operator):
    bl_idname    = "rzm.puppet_master_bake"
    bl_label     = "Bake Puppet Master Shapes"
    bl_description = "Bake shape keys using strictly RZMenu Shape Configs"
    full_export_mode: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root): return {'CANCELLED'}
        addons       = context.scene.rzm.addons
        per_component = False if self.full_export_mode else addons.puppet_master_per_component
        limit        = addons.puppet_master_limit
        components   = get_components_to_process(context, per_component)
        if not components: return {'CANCELLED'}
        for base_name, objs in components.items():
            bake_component_shapes(context, base_name, objs, mod_root, limit, full_export_mode=self.full_export_mode)
        return {'FINISHED'}

class RZM_OT_PuppetMasterBakeSingle(bpy.types.Operator):
    bl_idname    = "rzm.puppet_master_bake_single"
    bl_label     = "Bake Selected Shape Key"
    bl_description = "Bake the active shape regardless of whitelist"

    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root): return {'CANCELLED'}
        rzm = context.scene.rzm
        if not (0 <= context.scene.rzm_active_shape_config_index < len(rzm.shape_configs)): return {'CANCELLED'}
        target_shape = rzm.shape_configs[context.scene.rzm_active_shape_config_index].shape_name
        limit        = rzm.addons.puppet_master_limit
        components   = get_components_to_process(context, per_component=False)
        if not components: return {'CANCELLED'}
        for base_name, objs in components.items():
            bake_component_shapes(context, base_name, objs, mod_root, limit, single_shape_name=target_shape)
        return {'FINISHED'}

classes_to_register = [RZM_OT_PuppetMasterBake, RZM_OT_PuppetMasterBakeSingle]

def register():
    for cls in classes_to_register: bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register): bpy.utils.unregister_class(cls)