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


def _idw_delta_batch(buf_verts_np, owner_data, target_data):
    """
    IDW interpolation – fully vectorised for scipy path, BVH fallback otherwise.
    buf_verts_np : (N, 3)  buffer verts owned by this object
    owner_data   : dict with 'coords','tri_verts','polys','kd','bvh'
    target_data  : (M, 3)  deformed mesh positions
    Returns (N, 3) deltas.
    """
    base_coords = owner_data['coords']   # (M, 3)
    kd          = owner_data['kd']
    bvh         = owner_data['bvh']
    deltas_np   = target_data - base_coords  # (M, 3)

    if kd is not None:
        # ── Fully-vectorised numpy/scipy path (no Python loops) ───────────
        tri_verts   = owner_data['tri_verts']          # (F, 3) int32
        _, face_ids = kd.query(buf_verts_np, workers=-1)  # (N,)
        face_v_idx  = tri_verts[face_ids]              # (N, 3)
        face_coords = base_coords[face_v_idx]          # (N, 3, 3)
        diff        = face_coords - buf_verts_np[:, np.newaxis, :]  # (N, 3, 3)
        sq_dist     = (diff * diff).sum(axis=2) + 1e-10             # (N, 3)
        w           = 1.0 / sq_dist                                  # (N, 3)
        face_deltas = deltas_np[face_v_idx]            # (N, 3, 3)
        out = (w[:, :, np.newaxis] * face_deltas).sum(axis=1) / w.sum(axis=1, keepdims=True)
        return out  # (N, 3)
    else:
        # ── Robust BVH fallback (no scipy) ───────────────────────────────
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
        return out  # (N, 3)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 FAST PATH  (direct offset write, no depsgraph, no KD tree)
# ─────────────────────────────────────────────────────────────────────────────
def _bake_with_direct_offsets(
    sk_owner_map, comp_cache, original_bytes, stride, buf_v_count, output_dir, base_name
):
    """
    FAST PATH — Phase 2.
    Uses pre-computed vb_offset + vb_count from the export cache to write
    shape key deltas directly into the buffer without ANY depsgraph evaluation,
    KD-tree, or IDW interpolation.

    Algorithm:
      For each sk_name:
        For each cached object that owns a segment of the buffer:
          1. Get its Blender shape_keys.data (raw, no scene update)
          2. Compute per-vertex delta vs. Basis  (numpy, vectorised)
          3. Write to buf_f32[vb_offset : vb_offset + vb_count, :3]

    Complexity: O(N_sk_verts)  instead of O(N_buf_verts × N_objects).
    Returns: True on success, False if any object was missing / vertex count mismatch.
    """
    stride_f32  = stride // 4
    obj_by_name = {o.name: o for o in bpy.data.objects}

    # Build name → blob entry lookup
    cache_objects = {entry['name']: entry for entry in comp_cache.get('objects', [])}

    any_written = False
    t_total     = time.perf_counter()

    for sk_name in list(sk_owner_map.keys()):
        t_sk = time.perf_counter()

        buf_f32       = np.frombuffer(bytes(original_bytes), dtype=np.float32) \
                          .reshape(buf_v_count, stride_f32).copy()
        matched_count = 0
        fallback_objs = []   # objects missing from cache → collected for caller

        # Collect direct owners from sk_owner_map
        sk_direct     = sk_owner_map[sk_name]['direct']
        sk_via_target = sk_owner_map[sk_name]['via_target']

        for obj in sk_direct:
            entry = cache_objects.get(obj.name)
            if entry is None:
                fallback_objs.append(obj)
                continue

            vb_off = entry['vb_offset']
            vb_cnt = entry['vb_count']

            if not (obj.data and obj.data.shape_keys):
                continue
            sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
            ba_blk = obj.data.shape_keys.reference_key
            if sk_blk is None or not sk_blk.data or not ba_blk.data:
                continue

            n = len(sk_blk.data)
            if n != vb_cnt:
                # Vertex count mismatch — scene may have been modified after export,
                # skip this object safely and log it
                print(f'    [CACHE] WARN {obj.name}: SK verts={n} != cached vb_count={vb_cnt}')
                fallback_objs.append(obj)
                continue

            sk_co = np.array([kp.co for kp in sk_blk.data], dtype=np.float32)
            ba_co = np.array([kp.co for kp in ba_blk.data], dtype=np.float32)
            delta = sk_co - ba_co      # (N, 3)

            nonzero = np.linalg.norm(delta, axis=1) > 1e-7
            if not nonzero.any():
                continue

            idx = np.where(nonzero)[0]
            buf_indices = vb_off + idx

            new_xyz = (buf_f32[buf_indices, :3] + delta[idx]).astype(np.float32)
            buf_f32[buf_indices, 0] = new_xyz[:, 0]
            buf_f32[buf_indices, 1] = new_xyz[:, 1]
            buf_f32[buf_indices, 2] = new_xyz[:, 2]
            matched_count += len(idx)

        clean_name = re.sub(r'[\\/:*?"<>|]', '_', sk_name).replace(' ', '_').replace('.', '_')
        out_name   = f'{base_name}_{clean_name}.buf'

        if matched_count > 0:
            with open(os.path.join(output_dir, out_name), 'wb') as f:
                f.write(buf_f32.tobytes())
            print(f'    [FAST] {out_name} ({matched_count} verts)  '
                  f't={time.perf_counter()-t_sk:.3f}s')
            any_written = True
        else:
            print(f'    [FAST] {out_name} — no delta')

        if fallback_objs:
            # Return fallback list so caller can decide to use spatial matching
            print(f'    [FAST] {len(fallback_objs)} objects need fallback: '
                  f'{[o.name for o in fallback_objs]}')

    print(f'  [TIMER] fast-path total: {time.perf_counter()-t_total:.3f}s')
    return any_written


def _scan_sk_owners(comp_objects, all_keys):
    """
    Walk every comp_object WITHOUT touching the depsgraph.
    For each sk_name in all_keys:
      - 'direct'     : objects whose shape_keys.data differs from basis (real delta)
      - 'via_target' : objects whose SD/SW modifier target holds the SK
    Returns { sk_name → {'direct': [...], 'via_target': [...]} }
    Only includes entries where at least one contributor exists.
    """
    result = {}
    for sk_name in all_keys:
        direct     = []
        via_target = []
        for obj in comp_objects:
            if not (obj.data and obj.data.shape_keys):
                # No shape keys at all – only check modifiers
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
                        continue  # confirmed real delta, skip modifier check
            # SK absent or dummy – check if a modifier target owns it
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
    """Bake shapes – v14.3: pre-scan then targeted build (no wasted KD work)."""
    vb0_path = None
    dump_name = (os.path.basename(os.path.normpath(bpy.path.abspath(context.scene.xxmi.dump_path)))
                 if hasattr(context.scene, "xxmi") else "")

    # ── Path search ───────────────────────────────────────────────────────────
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
    
    if not vb0_path:  # fuzzy fallback
        for sub in subfolders:
            curr_dir = os.path.join(mod_root, sub) if sub else mod_root
            if not os.path.exists(curr_dir): continue
            for f in os.listdir(curr_dir):
                f_low = f.lower()
                if f_low.endswith(".buf") and base_name.lower() in f_low and \
                   ("position" in f_low or "vb0" in f_low):
                    vb0_path = os.path.join(curr_dir, f)
                    break
            if vb0_path: break

    if not vb0_path: return False

    output_dir = os.path.join(mod_root, "SK")
    os.makedirs(output_dir, exist_ok=True)

    with open(vb0_path, "rb") as f:
        original_bytes = f.read()
    original_data = bytearray(original_bytes)

    # ── Stride ────────────────────────────────────────────────────────────────
    game = context.scene.rzm.game.name
    stride = (40 if game in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}
              else 16 if game in {'ArknightsEndfield', 'WutheringWaves'}
              else 32)

    buf_v_count = len(original_data) // stride
    
    # ── Whitelist ─────────────────────────────────────────────────────────────
    rzm = context.scene.rzm
    if single_shape_name:
        all_keys = {single_shape_name}
    else:
        all_keys = {c.shape_name for c in rzm.shape_configs if not c.disable_export}
    if not all_keys:
        return True

    # ── PRE-SCAN (no depsgraph) ───────────────────────────────────────────────
    # Find exactly which objects own each SK and eliminate dummies.
    # If nothing survives → skip this entire component with zero depsgraph cost.
    _t0 = time.perf_counter()
    sk_owner_map = _scan_sk_owners(comp_objects, all_keys)
    _t_prescan = time.perf_counter()

    print(f"\n[RZM] [BAKE] Group: '{base_name}'")
    _log_buf_path(vb0_path, stride, game)
    print(f"[RZM] [BAKE] Vertices in buffer: {buf_v_count} | Shapes to bake: {len(all_keys)}")
    print(f"  [TIMER] Pre-scan: {_t_prescan - _t0:.3f}s")

    if not sk_owner_map:
        print(f"  [PRE-SCAN] No real shape keys found — skipping component entirely")
        return True

    # Collect the minimal set of objects that actually need processing
    active_objects: set = set()
    for owners in sk_owner_map.values():
        active_objects.update(owners['direct'])
        active_objects.update(owners['via_target'])
    active_objects = list(active_objects)

    print(f"  [PRE-SCAN] {len(sk_owner_map)} SK(s) | {len(active_objects)} active object(s) "
          f"(of {len(comp_objects)} in component)")

    # ── PHASE 2 FAST PATH ─────────────────────────────────────────────────────
    # If the export cache has offset data for this component, use direct writes.
    # Falls through to spatial matching only on cache miss or vertex count mismatch.
    try:
        from .export_cache import component_cache
        comp_cache = component_cache(base_name)
    except Exception:
        comp_cache = None

    if comp_cache is not None:
        print(f"  [CACHE] HIT — using direct offset write (Phase 2, no KD/IDW)")
        _bake_with_direct_offsets(
            sk_owner_map, comp_cache, original_bytes, stride, buf_v_count,
            output_dir, base_name
        )
        return True

    print(f"  [CACHE] MISS — spatial matching fallback (Phase 1)")

    # ── Read buffer XYZ into numpy once ──────────────────────────────────────
    raw_np     = np.frombuffer(original_bytes, dtype=np.uint8)
    float_view = raw_np.reshape(buf_v_count, stride).view(np.float32).reshape(buf_v_count, stride // 4)
    buf_xyz    = float_view[:, :3].astype(np.float64)  # (N, 3)


    # ── Setup scene state ─────────────────────────────────────────────────────
    linked_targets = get_linked_targets(active_objects)  # only for active subset
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
        # ── BASIS cache (active objects only) ────────────────────────────────
        _t_scene_reset = time.perf_counter()
        for a_obj in all_involved:
            if a_obj.data and a_obj.data.shape_keys:
                for sk in a_obj.data.shape_keys.key_blocks:
                    sk.value = 0.0
        context.view_layer.update()
        depsgraph.update()
        print(f"  [TIMER] Scene reset + basis update: {time.perf_counter() - _t_scene_reset:.3f}s")

        _t_cache_start = time.perf_counter()
        base_cache = {}
        for obj in active_objects:
            _t_obj = time.perf_counter()
            eval_obj  = obj.evaluated_get(depsgraph)
            b_eval    = eval_obj.to_mesh()
            coords    = np.array([v.co for v in b_eval.vertices], dtype=np.float64)
            polys     = [list(p.vertices) for p in b_eval.polygons]
            loop_tris = b_eval.calc_loop_triangles()
            tri_verts = np.array(
                [[lt.vertices[0], lt.vertices[1], lt.vertices[2]] for lt in loop_tris],
                dtype=np.int32,
            ) if loop_tris else np.zeros((0, 3), dtype=np.int32)
            eval_obj.to_mesh_clear()

            _t_kd = time.perf_counter()
            kd, centroids = _build_spatial_index(coords, tri_verts)
            bvh = None if kd is not None else BVHTree.FromPolygons(
                [Vector(c) for c in coords], polys
            )
            base_cache[obj] = {
                'coords': coords, 'tri_verts': tri_verts, 'polys': polys,
                'kd': kd, 'centroids': centroids, 'bvh': bvh,
            }
            _t_obj_end = time.perf_counter()
            print(f"    [TIMER] {obj.name[:40]}: mesh={_t_kd-_t_obj:.3f}s  KD={_t_obj_end-_t_kd:.3f}s  verts={len(coords)}")
        print(f"  [TIMER] base_cache total ({len(active_objects)} objs): {time.perf_counter()-_t_cache_start:.3f}s")

        # Owner assignment — only against active_objects (small subset now)
        _t_owners = time.perf_counter()
        owner_map, dist_map = _assign_owners_bulk(buf_xyz, base_cache, limit)
        print(f"  [TIMER] _assign_owners_bulk ({len(base_cache)} objs × {buf_v_count} verts): {time.perf_counter()-_t_owners:.3f}s")

        # ── Per-shape loop (iterate pre-scanned map, no redundant checks) ────
        stride_f32 = stride // 4
        for sk_name, owners in sk_owner_map.items():
            sk_direct     = owners['direct']
            sk_via_target = owners['via_target']

            print(f"  [SK] Submitting: '{sk_name}'")

            # Activate SK on all involved, then update
            _t_sk = time.perf_counter()
            for obj in all_involved:
                if obj.data and obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = 1.0 if sk.name == sk_name else 0.0
            context.view_layer.update()
            depsgraph.update()
            print(f"    [TIMER] SK activate + scene update: {time.perf_counter()-_t_sk:.3f}s")

            # Evaluate only the pre-confirmed active objects
            _t_eval = time.perf_counter()
            target_cache = {}
            for obj in sk_direct + sk_via_target:
                if obj not in base_cache:
                    continue
                eval_obj = obj.evaluated_get(depsgraph)
                t_eval   = eval_obj.to_mesh()
                t_coords = np.array([v.co for v in t_eval.vertices], dtype=np.float64)
                eval_obj.to_mesh_clear()
                if len(t_coords) == len(base_cache[obj]['coords']):
                    target_cache[obj] = t_coords
            print(f"    [TIMER] target_cache eval ({len(target_cache)} objs): {time.perf_counter()-_t_eval:.3f}s")

            if not target_cache:
                continue

            # ── Fully-vectorised delta application ────────────────────────────
            _t_delta = time.perf_counter()
            buf_f32 = np.frombuffer(
                bytes(original_data), dtype=np.float32
            ).reshape(buf_v_count, stride_f32).copy()
            matched_count = 0

            for obj, t_coords in target_cache.items():
                _t_idw = time.perf_counter()
                mask = (owner_map == id(obj))
                if not mask.any():
                    continue
                buf_sub      = buf_xyz[mask]
                deltas       = _idw_delta_batch(buf_sub, base_cache[obj], t_coords)
                nonzero      = np.linalg.norm(deltas, axis=1) > 1e-7
                if not nonzero.any():
                    continue
                indices      = np.where(mask)[0][nonzero]
                valid_deltas = deltas[nonzero]
                new_xyz      = (buf_xyz[indices] + valid_deltas).astype(np.float32)
                buf_f32[indices, 0] = new_xyz[:, 0]
                buf_f32[indices, 1] = new_xyz[:, 1]
                buf_f32[indices, 2] = new_xyz[:, 2]
                matched_count += len(indices)
                print(f"    [TIMER] IDW {obj.name[:35]}: owned={mask.sum()} nz={nonzero.sum()} t={time.perf_counter()-_t_idw:.3f}s")
            print(f"    [TIMER] delta total: {time.perf_counter()-_t_delta:.3f}s  matched={matched_count}")

            clean_name = re.sub(r'[\\/:*?"<>|]', '_', sk_name).replace(" ", "_").replace(".", "_")
            out_name   = f"{base_name}_{clean_name}.buf"
            if matched_count > 0:
                with open(os.path.join(output_dir, out_name), "wb") as f:
                    f.write(buf_f32.tobytes())
                print(f"    -> [DONE] {out_name} ({matched_count} verts)")
            else:
                print(f"    -> [SKIP] {out_name} (No deltas)")

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