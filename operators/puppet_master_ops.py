# RZMenu/operators/puppet_master_ops.py
# VERSION: 14.4 (CACHE FAST-PATH + SPATIAL FALLBACK)
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
    
    print("\n" + "="*70)
    print(f"[RZM] [DEBUG] COMPONENT DISCOVERY (v14.1 - NumPy Vectorized)")
    print(f"  -> Settings: {settings}")
    
    results = {}
    
    if is_xxmi:
        dump_path_prop = scene.xxmi.dump_path if hasattr(scene, "xxmi") else ""
        if not dump_path_prop: return {}
        dump_path = os.path.normpath(bpy.path.abspath(dump_path_prop))
        comp_metadata = load_xxmi_metadata(dump_path)
        if not comp_metadata: return {}

        for component in comp_metadata:
            comp_name = component.get("component_name", "")
            base_fullname = comp_name
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

    print(f"[RZM] [DEBUG] Discovery complete. Found {len(results)} groups.")
    return results

# ─────────────────────────────────────────────────────────────────────────────
# NUMPY SPATIAL INDEX
# Replaces per-vertex BVH calls with a bulk KD-query + IDW on face verts.
# Falls back gracefully if scipy is unavailable.
# ─────────────────────────────────────────────────────────────────────────────
def _build_spatial_index(coords_np, tri_verts_np):
    """
    Build a triangle-centroid KD-tree for fast nearest-triangle lookup.
    tri_verts_np: (F, 3) int32 array.  Returns (kd_tree, centroids) or (None, None).
    """
    try:
        from scipy.spatial import KDTree
    except ImportError:
        return None, None
    if len(tri_verts_np) == 0:
        return None, None
    centroids = coords_np[tri_verts_np].mean(axis=1).astype(np.float32)  # fully numpy
    return KDTree(centroids), centroids


def _precalc_idw_weights(buf_verts_np, owner_data):
    """Pre-calculates weights for IDW interpolation to reuse across multiple shape keys."""
    base_coords = owner_data['coords']
    kd          = owner_data['kd']
    bvh         = owner_data['bvh']
    if kd is not None:
        tri_verts   = owner_data['tri_verts']
        _, face_ids = kd.query(buf_verts_np, workers=-1)
        face_v_idx  = tri_verts[face_ids]
        face_coords = base_coords[face_v_idx]
        diff        = face_coords - buf_verts_np[:, np.newaxis, :]
        sq_dist     = (diff * diff).sum(axis=2) + 1e-10
        w           = 1.0 / sq_dist
        w_norm      = w / w.sum(axis=1, keepdims=True)
        return {'type': 'vectorised', 'face_v_idx': face_v_idx, 'w_norm': w_norm}
    else:
        polys       = owner_data['polys']
        face_v_idxs = []
        w_norms     = []
        for bv in buf_verts_np:
            _, _, face_idx, _ = bvh.find_nearest(Vector(bv))
            fi         = face_idx if face_idx is not None else 0
            face_v_idx = np.array(polys[fi])
            bv_face    = base_coords[face_v_idx]
            diff       = bv_face - bv
            sq_dist    = (diff * diff).sum(axis=1) + 1e-10
            w          = 1.0 / sq_dist
            w_norm     = w / w.sum()
            face_v_idxs.append(face_v_idx)
            w_norms.append(w_norm)
        return {'type': 'fallback', 'face_v_idxs': face_v_idxs, 'w_norms': w_norms}

def _apply_idw_deltas(precalc_data, deltas_np):
    """Applies pre-calculated weights to the vertex deltas."""
    if precalc_data['type'] == 'vectorised':
        face_v_idx = precalc_data['face_v_idx']
        w_norm     = precalc_data['w_norm']
        face_deltas = deltas_np[face_v_idx]
        return (w_norm[:, :, np.newaxis] * face_deltas).sum(axis=1)
    else:
        out = np.zeros((len(precalc_data['w_norms']), 3), dtype=np.float32)
        for i, (face_v_idx, w_norm) in enumerate(zip(precalc_data['face_v_idxs'], precalc_data['w_norms'])):
            out[i] = (w_norm[:, None] * deltas_np[face_v_idx]).sum(axis=0)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 FAST PATH  (direct offset write, no depsgraph, no KD tree)
# ─────────────────────────────────────────────────────────────────────────────
def _bake_with_direct_offsets(
    sk_owner_map, comp_cache, original_bytes, stride, buf_v_count, output_dir, base_name, dump_name
):
    """
    FAST PATH — Phase 2.
    Uses pre-computed vb_offset + vb_count from the export cache to write
    shape key deltas directly into the buffer without ANY depsgraph evaluation,
    KD-tree, or IDW interpolation.
    """
    stride_f32  = stride // 4
    cache_objects = {entry['name']: entry for entry in comp_cache.get('objects', [])}
    any_written = False
    t_total     = time.perf_counter()

    for sk_name in list(sk_owner_map.keys()):
        t_sk = time.perf_counter()
        buf_f32       = np.frombuffer(bytes(original_bytes), dtype=np.float32) \
                          .reshape(buf_v_count, stride_f32).copy()
        matched_count = 0
        fallback_objs = []

        sk_direct     = sk_owner_map[sk_name]['direct']
        for obj in sk_direct:
            entry = cache_objects.get(obj.name)
            if entry is None:
                fallback_objs.append(obj)
                continue
            vb_off = entry['vb_offset']
            vb_cnt = entry['vb_count']
            if not (obj.data and obj.data.shape_keys): continue
            sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
            ba_blk = obj.data.shape_keys.reference_key
            if sk_blk is None or not sk_blk.data or not ba_blk.data: continue
            n = len(sk_blk.data)
            if n != vb_cnt:
                fallback_objs.append(obj)
                continue
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

        # --- Sanitization and XXMI Character Prefix ---
        is_xxmi = bpy.context.scene.rzm.game.name in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}
        raw_base = (dump_name + base_name) if is_xxmi else base_name
        clean_base = re.sub(r'[ !@#$%^&*()+\-={}|[\]\\:";\'<>?,./]', '_', raw_base)
        clean_name = re.sub(r'[ !@#$%^&*()+\-={}|[\]\\:";\'<>?,./]', '_', sk_name)
        out_name   = f'{clean_base}_{clean_name}.buf'

        if matched_count > 0:
            with open(os.path.join(output_dir, out_name), 'wb') as f:
                f.write(buf_f32.tobytes())
            print(f'    [FAST] {out_name} ({matched_count} verts)  t={time.perf_counter()-t_sk:.3f}s')
            any_written = True
        else:
            print(f'    [FAST] {out_name} — no delta')

    print(f'  [TIMER] fast-path total: {time.perf_counter()-t_total:.3f}s')
    return any_written


def _scan_sk_owners(comp_objects, all_keys):
    result = {}
    for sk_name in all_keys:
        direct     = []
        via_target = []
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


# ─────────────────────────────────────────────────────────────────────────────
# CORE BAKE
# ─────────────────────────────────────────────────────────────────────────────
def bake_component_shapes(context, base_name, comp_objects, mod_root, limit,
                          single_shape_name=None, full_export_mode=False):
    vb0_path = None
    dump_name = (os.path.basename(os.path.normpath(bpy.path.abspath(context.scene.xxmi.dump_path)))
                 if hasattr(context.scene, "xxmi") and context.scene.xxmi.dump_path else "")

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

    game = context.scene.rzm.game.name
    stride = (40 if game in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}
              else 16 if game in {'ArknightsEndfield', 'WutheringWaves'}
              else 32)
    
    buf_v_count = len(original_data) // stride
    
    rzm = context.scene.rzm
    if single_shape_name:
        all_keys = {single_shape_name}
    else:
        all_keys = {c.shape_name for c in rzm.shape_configs if not c.disable_export}
    if not all_keys: return True

    sk_owner_map = _scan_sk_owners(comp_objects, all_keys)
    if not sk_owner_map: return True

    active_objects = list({o for owners in sk_owner_map.values() for o in owners['direct'] + owners['via_target']})

    try:
        from .export_cache import component_cache
        comp_cache = component_cache(base_name)
    except Exception:
        comp_cache = None

    if comp_cache is not None:
        _bake_with_direct_offsets(sk_owner_map, comp_cache, original_bytes, stride, buf_v_count, output_dir, base_name, dump_name)
        return True

    raw_np     = np.frombuffer(original_bytes, dtype=np.uint8)
    float_view = raw_np.reshape(buf_v_count, stride).view(np.float32).reshape(buf_v_count, stride // 4)
    buf_xyz    = float_view[:, :3].astype(np.float64)

    linked_targets = get_linked_targets(active_objects)
    all_involved   = active_objects + list(set(linked_targets))
    depsgraph = context.evaluated_depsgraph_get()

    sk_snapshot = {obj: {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks} for obj in all_involved if obj.data and obj.data.shape_keys}
    set_armature_visibility(all_involved, False)
    mirror_states = {obj: [(mod, mod.use_mirror_merge, mod.use_clip) for mod in obj.modifiers if mod.type == 'MIRROR' and mod.show_viewport] for obj in active_objects}
    for obj, mods in mirror_states.items():
        for mod, _, _ in mods: mod.use_mirror_merge, mod.use_clip = False, False

    try:
        for a_obj in all_involved:
            if a_obj.data and a_obj.data.shape_keys:
                for sk in a_obj.data.shape_keys.key_blocks: sk.value = 0.0
        context.view_layer.update()
        depsgraph.update()

        base_cache = {}
        for obj in active_objects:
            eval_obj  = obj.evaluated_get(depsgraph)
            b_eval    = eval_obj.to_mesh()
            coords    = np.array([v.co for v in b_eval.vertices], dtype=np.float64)
            polys     = [list(p.vertices) for p in b_eval.polygons]
            loop_tris = b_eval.calc_loop_triangles()
            tri_verts = np.array([[lt.vertices[0], lt.vertices[1], lt.vertices[2]] for lt in loop_tris], dtype=np.int32) if loop_tris else np.zeros((0, 3), dtype=np.int32)
            eval_obj.to_mesh_clear()
            kd, centroids = _build_spatial_index(coords, tri_verts)
            base_cache[obj] = {'coords': coords, 'tri_verts': tri_verts, 'polys': polys, 'kd': kd, 'centroids': centroids, 'bvh': None if kd is not None else BVHTree.FromPolygons([Vector(c) for c in coords], polys)}

        owner_map, _ = _assign_owners_bulk(buf_xyz, base_cache, limit)
        idw_cache = {obj: {'mask': (owner_map == id(obj)), 'precalc': _precalc_idw_weights(buf_xyz[owner_map == id(obj)], ob_cache)} for obj, ob_cache in base_cache.items() if (owner_map == id(obj)).any()}

        stride_f32 = stride // 4
        for sk_name, owners in sk_owner_map.items():
            for obj in all_involved:
                if obj.data and obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks: sk.value = 1.0 if sk.name == sk_name else 0.0
            context.view_layer.update()
            depsgraph.update()

            target_cache = {obj: np.array([v.co for v in obj.evaluated_get(depsgraph).to_mesh().vertices], dtype=np.float64) for obj in owners['direct'] + owners['via_target'] if obj in base_cache}
            buf_f32 = np.frombuffer(bytes(original_data), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
            matched_count = 0

            for obj, t_coords in target_cache.items():
                if obj not in idw_cache: continue
                imap = idw_cache[obj]
                deltas = _apply_idw_deltas(imap['precalc'], t_coords - base_cache[obj]['coords'])
                nonzero = np.linalg.norm(deltas, axis=1) > 1e-7
                if not nonzero.any(): continue
                indices = np.where(imap['mask'])[0][nonzero]
                new_xyz = (buf_xyz[indices] + deltas[nonzero]).astype(np.float32)
                buf_f32[indices, 0:3] = new_xyz
                matched_count += len(indices)

            is_xxmi = game in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}
            raw_base = (dump_name + base_name) if is_xxmi else base_name
            clean_base = re.sub(r'[ !@#$%^&*()+\-={}|[\]\\:";\'<>?,./]', '_', raw_base)
            clean_shape = re.sub(r'[ !@#$%^&*()+\-={}|[\]\\:";\'<>?,./]', '_', sk_name)
            out_name = f"{clean_base}_{clean_shape}.buf"
            if matched_count > 0:
                with open(os.path.join(output_dir, out_name), "wb") as f:
                    f.write(buf_f32.tobytes())

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


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS for vectorised bake
# ─────────────────────────────────────────────────────────────────────────────

def _log_buf_path(vb0_path, stride, game):
    """Print the multi-path search result (replaces old inline prints)."""
    fname = os.path.basename(vb0_path)
    print(f"[RZM] [BAKE] Multi-Path Search (Root -> Meshes/ -> Buffers/):")
    print(f"  -> [HIT] Found at: {fname}")
    print(f"  -> [INFO] Stride: {stride} (Game: {game})")


def _assign_owners_bulk(buf_xyz, base_cache, limit):
    """
    For every buffer vertex decide which mesh object "owns" it by nearest BVH/KD distance.
    Returns:
        owner_map  : (N,) int64 – id() of owner object, or 0 if beyond limit / no owner
        dist_map   : (N,) float64 – actual nearest distance
    """
    N          = len(buf_xyz)
    owner_map  = np.zeros(N, dtype=np.int64)
    dist_map   = np.full(N, np.inf, dtype=np.float64)

    has_scipy = base_cache and next(iter(base_cache.values()))['kd'] is not None

    if has_scipy:
        for obj, data in base_cache.items():
            kd          = data['kd']
            centroids   = data['centroids']
            dists, _    = kd.query(buf_xyz, workers=-1)   # (N,) centroid distances

            improve = dists < dist_map - 1e-5
            owner_map[improve] = id(obj)
            dist_map[improve]  = dists[improve]

        # Zero out vertices beyond limit (centroid-distance is an approximation, keep limit loose)
        beyond = dist_map > limit
        owner_map[beyond] = 0
    else:
        # BVH fallback (no scipy) – per vertex, same as before but using mathutils BVHTree
        for i, bv in enumerate(buf_xyz):
            mv = Vector(bv)
            for obj, data in base_cache.items():
                bvh = data['bvh']
                if bvh is None: continue
                _, _, _, dist = bvh.find_nearest(mv)
                if dist < dist_map[i] - 1e-5:
                    dist_map[i]  = dist
                    owner_map[i] = id(obj)
        beyond = dist_map > limit
        owner_map[beyond] = 0

    return owner_map, dist_map


# ─────────────────────────────────────────────────────────────────────────────
# OPERATORS
# ─────────────────────────────────────────────────────────────────────────────
class RZM_OT_PuppetMasterBake(bpy.types.Operator):
    bl_idname    = "rzm.puppet_master_bake"
    bl_label     = "Bake Puppet Master Shapes"
    bl_description = "Bake shape keys using strictly RZMenu Shape Configs (v14.3)"
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
            bake_component_shapes(context, base_name, objs, mod_root, limit,
                                  full_export_mode=self.full_export_mode)
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
        if not (0 <= context.scene.rzm_active_shape_config_index < len(rzm.shape_configs)):
            return {'CANCELLED'}
        target_shape = rzm.shape_configs[context.scene.rzm_active_shape_config_index].shape_name
        limit        = rzm.addons.puppet_master_limit
        components   = get_components_to_process(context, per_component=False)
        if not components: return {'CANCELLED'}
        for base_name, objs in components.items():
            bake_component_shapes(context, base_name, objs, mod_root, limit,
                                  single_shape_name=target_shape)
        return {'FINISHED'}


classes_to_register = [RZM_OT_PuppetMasterBake, RZM_OT_PuppetMasterBakeSingle]

def register():
    for cls in classes_to_register: bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register): bpy.utils.unregister_class(cls)