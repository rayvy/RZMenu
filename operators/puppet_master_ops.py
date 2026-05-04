# RZMenu/operators/puppet_master_ops.py
#
# Hybrid Pipeline v5 (Pre-Baked Exact Match + Slow Path Fallback)
#   1. EXACT MATCH PATH (Fast) — Для объектов с собственными шейпкеями.
#      - Объекты без модов читаются напрямую.
#      - Объекты с модами и SurfaceDeform предварительно запекаются через 
#        rzm_surface_baker и rz.shape_key_apply_modifiers.
#      - Дельты наносятся на буфер через топологический v_map или точный KD-Tree.
#   2. SLOW PATH (Fallback) — Включается автоматически, если Exact Match 
#      или Pre-Bake не сработали (ошибки, новые игры без кэша и т.д.).
#      Используется пространственная барицентрическая интерполяция через BVH.
#
import bpy
import os
import re
import json
import time
import struct
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# DISCOVERY
# ---------------------------------------------------------------------------

def get_components_to_process(context, per_component=False):
    scene = context.scene
    rzm   = scene.rzm
    game_name = rzm.game.name
    xxmi_list = ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']
    is_xxmi   = game_name in xxmi_list

    settings = {
        'ignore_hidden_obj':  False,
        'ignore_hidden_coll': False,
        'ignore_nested':      False,
    }
    if is_xxmi and hasattr(scene, "xxmi"):
        settings['ignore_hidden_obj'] = scene.xxmi.ignore_hidden
    elif game_name == 'ArknightsEndfield' and hasattr(scene, "efmi_tools_settings"):
        efmi = scene.efmi_tools_settings
        settings['ignore_hidden_obj']  = efmi.ignore_hidden_objects
        settings['ignore_hidden_coll'] = efmi.ignore_hidden_collections
        settings['ignore_nested']      = efmi.ignore_nested_collections

    results = {}

    if is_xxmi:
        dump_path_prop = scene.xxmi.dump_path if hasattr(scene, "xxmi") else ""
        if not dump_path_prop: return {}
        dump_path    = os.path.normpath(bpy.path.abspath(dump_path_prop))
        mod_name     = os.path.basename(dump_path)
        comp_metadata = load_xxmi_metadata(dump_path)
        if not comp_metadata: return {}
        for component in comp_metadata:
            comp_name   = component.get("component_name", "")
            base_fullname = f"{mod_name}{comp_name}"
            classifications = component.get("object_classifications", [])
            comp_meshes = set()
            for part in classifications:
                part_fullname = base_fullname + part
                for coll in bpy.data.collections:
                    if coll.name.lower().startswith(part_fullname.lower()):
                        for obj in coll.all_objects:
                            if obj.type == 'MESH':
                                if settings['ignore_hidden_obj'] and obj.hide_get(): continue
                                comp_meshes.add(obj)
                for obj in context.view_layer.objects:
                    if obj.type != 'MESH': continue
                    if settings['ignore_hidden_obj'] and obj.hide_get(): continue
                    if (obj.name.lower() == part_fullname.lower() or
                            obj.name.lower().startswith(part_fullname.lower() + ".")):
                        comp_meshes.add(obj)
            if comp_meshes:
                results[comp_name] = list(comp_meshes)
    else:
        for obj in context.view_layer.objects:
            if obj.type != 'MESH': continue
            if settings['ignore_hidden_obj'] and obj.hide_get(): continue
            match = re.search(r"Component\s*(\d+)", obj.name, re.IGNORECASE)
            if match:
                results.setdefault(f"Component{match.group(1)}", []).append(obj)

    for key in results:
        results[key] = list(set(results[key]))

    if per_component and context.active_object:
        target_name = None
        for name, objs in results.items():
            if context.active_object in objs:
                target_name = name
                break
        if target_name: return {target_name: results[target_name]}
        return {}

    return results

def _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name):
    raw_base   = (dump_name + base_name) if is_xxmi else base_name
    clean_base = re.sub(r'[\\/:*?"<>|]', '_', raw_base).replace(' ', '_').replace('.', '_')
    clean_sk   = re.sub(r'[\\/:*?"<>|]', '_', sk_name).replace(' ', '_').replace('.', '_')
    return f"{clean_base}_{clean_sk}.buf"

# ---------------------------------------------------------------------------
# CLASSIFICATION & PRE-BAKE HELPERS
# ---------------------------------------------------------------------------

def has_active_modifiers(obj):
    for m in obj.modifiers:
        if m.show_viewport and m.type != 'ARMATURE':
            return True
    return False

def _scan_sk_owners(comp_objects, all_keys):
    """Классифицирует объекты по способу их деформации."""
    result = {}
    
    for sk_name in all_keys:
        direct_raw, direct_bake, via_target = [], [], []
        
        for obj in comp_objects:
            has_direct_sk = False
            
            if obj.data and obj.data.shape_keys:
                sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
                ba_blk = obj.data.shape_keys.reference_key
                if sk_blk and ba_blk and sk_blk.data and ba_blk.data:
                    sk_co = np.array([kp.co for kp in sk_blk.data], dtype=np.float32)
                    ba_co = np.array([kp.co for kp in ba_blk.data], dtype=np.float32)
                    if np.any(np.abs(sk_co - ba_co) > 1e-7):
                        has_direct_sk = True

            is_via_target = False
            for mod in obj.modifiers:
                if (mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'}
                        and mod.show_viewport and mod.target
                        and mod.target.data and mod.target.data.shape_keys
                        and sk_name in mod.target.data.shape_keys.key_blocks):
                    is_via_target = True
                    break

            if has_direct_sk:
                if has_active_modifiers(obj):
                    direct_bake.append(obj)
                else:
                    direct_raw.append(obj)
            elif is_via_target:
                via_target.append(obj)

        if direct_raw or direct_bake or via_target:
            result[sk_name] = {'direct_raw': direct_raw, 'direct_bake': direct_bake, 'via_target': via_target}
            
    return result

# ---------------------------------------------------------------------------
# EXACT MATCH PATH (Fast Path + KD-Tree)
# ---------------------------------------------------------------------------

def _process_exact_matches(sk_owner_map, ready_map, comp_cache, original_bytes,
                           stride, buf_v_count, output_dir, base_name, dump_name, is_xxmi):
    """
    Извлекает дельты из полностью подготовленных объектов (ready_map) и 
    наносит их на буфер через v_map или KD-Tree.
    Объекты, которые не удалось перенести (ошибки, нет кэша, диссонанс вершин), 
    возвращаются как failed_objects для передачи в Slow Path.
    """
    import mathutils as mu
    stride_f32 = stride // 4
    cache_objects = {entry['name']: entry for entry in comp_cache.get('objects', [])} if comp_cache else {}

    fast_path_slots_per_sk = {}
    stats = {'vmap_matched': 0, 'kd_matched': 0, 'objects': 0}
    failed_objects = {sk: {'direct': [], 'via_target': []} for sk in sk_owner_map.keys()}

    for sk_name, owners in sk_owner_map.items():
        buf_f32 = np.frombuffer(bytes(original_bytes), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
        sk_fast_slots = np.zeros(buf_v_count, dtype=bool)
        
        objs_to_process = []
        for obj in owners['direct_raw']: 
            objs_to_process.append((obj, obj))
            
        for obj in owners['direct_bake'] + owners['via_target']:
            baked_obj = ready_map.get(obj)
            if baked_obj and baked_obj.data and baked_obj.data.shape_keys and sk_name in baked_obj.data.shape_keys.key_blocks:
                objs_to_process.append((obj, baked_obj))
            else:
                # Объект не прошел Pre-Bake или шейпкей не перенесся
                if obj in owners['via_target']: failed_objects[sk_name]['via_target'].append(obj)
                else: failed_objects[sk_name]['direct'].append(obj)

        matched_for_sk = 0

        for orig_obj, target_obj in objs_to_process:
            sk_blk = target_obj.data.shape_keys.key_blocks.get(sk_name)
            ba_blk = target_obj.data.shape_keys.reference_key
            if not sk_blk or not ba_blk: 
                continue

            entry = cache_objects.get(orig_obj.name)
            vb_off = entry.get('vb_offset', 0) if entry else 0
            vb_cnt = entry.get('vb_count', buf_v_count) if entry else buf_v_count
            v_map  = entry.get('vertex_map') if entry else None
            m_idx  = entry.get('mat_idx', 0) if entry else 0

            mat = mu.Matrix.Identity(4)
            if m_idx == 1:
                mat = orig_obj.matrix_world
            elif m_idx == 2:
                root_obj_name = comp_cache.get('root_obj')
                root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else None
                mat = (root_obj.matrix_world.inverted() @ orig_obj.matrix_world if root_obj else mu.Matrix.Identity(4))

            v_count = len(target_obj.data.vertices)
            sk_co = np.empty(v_count * 3, dtype=np.float32)
            ba_co = np.empty(v_count * 3, dtype=np.float32)
            sk_blk.data.foreach_get('co', sk_co)
            ba_blk.data.foreach_get('co', ba_co)
            sk_co = sk_co.reshape(-1, 3)
            ba_co = ba_co.reshape(-1, 3)

            mat_rot = np.array(mat.to_3x3(), dtype=np.float32)
            deltas_all = ((sk_co - ba_co) @ mat_rot.T).astype(np.float32)
            if not is_xxmi:
                deltas_all[:, 0] *= -1

            if vb_off + vb_cnt > buf_v_count:
                print(f"    [ERROR] {orig_obj.name}: Buffer bounds exceeded. Forwarding to Slow Path.")
                if orig_obj in owners['via_target']: failed_objects[sk_name]['via_target'].append(orig_obj)
                else: failed_objects[sk_name]['direct'].append(orig_obj)
                continue

            obj_slice = buf_f32[vb_off: vb_off + vb_cnt, :3]
            matched_count = 0

            # Попытка 1: Идеальный маппинг по v_map
            if v_map and len(v_map) == vb_cnt and max(v_map) < v_count:
                v_map_np = np.array(v_map, dtype=np.int32)
                buf_f32[vb_off: vb_off + vb_cnt, :3] = (obj_slice + deltas_all[v_map_np]).astype(np.float32)
                matched_count = vb_cnt
                print(f"    [EXACT/VMAP] {orig_obj.name}: {matched_count} slots matched.")
                stats['vmap_matched'] += 1
            
            # Попытка 2: Пространственный маппинг по базису (KD-Tree)
            else:
                mwt = np.array(mat.translation, dtype=np.float32)
                ba_world = ba_co @ mat_rot.T + mwt
                
                kd = mu.kdtree.KDTree(v_count)
                for i, co in enumerate(ba_world):
                    kd.insert(mu.Vector(co), i)
                kd.balance()

                DIST_THRESHOLD = 0.005
                for idx in range(vb_cnt):
                    buf_idx = vb_off + idx
                    buf_pos = mu.Vector(buf_f32[buf_idx, :3])
                    
                    search_pos = buf_pos.copy()
                    if not is_xxmi:
                        search_pos.x *= -1
                        
                    _, best_idx, dist = kd.find(search_pos)
                    
                    if dist <= DIST_THRESHOLD:
                        d = deltas_all[best_idx]
                        if np.linalg.norm(d) > 1e-7:
                            buf_f32[buf_idx, 0] += d[0]
                            buf_f32[buf_idx, 1] += d[1]
                            buf_f32[buf_idx, 2] += d[2]
                        matched_count += 1

                if matched_count > 0:
                    print(f"    [EXACT/KD] {orig_obj.name}: {matched_count} slots matched exactly.")
                    stats['kd_matched'] += 1
                else:
                    print(f"    [WARN] {orig_obj.name}: 0 matches in KD-Tree. Forwarding to Slow Path.")

            if matched_count > 0:
                sk_fast_slots[vb_off: vb_off + vb_cnt] = True
                matched_for_sk += matched_count
                stats['objects'] += 1
            else:
                if orig_obj in owners['via_target']: failed_objects[sk_name]['via_target'].append(orig_obj)
                else: failed_objects[sk_name]['direct'].append(orig_obj)

        if matched_for_sk > 0:
            out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
            with open(os.path.join(output_dir, out_name), 'wb') as f:
                f.write(buf_f32.tobytes())
            print(f"    -> [DONE] {out_name} ({matched_for_sk} verts via Exact Match)")

        fast_path_slots_per_sk[sk_name] = sk_fast_slots

    return fast_path_slots_per_sk, stats, failed_objects

# ---------------------------------------------------------------------------
# BARYCENTRIC DELTA INTERPOLATION (Slow Path)
# ---------------------------------------------------------------------------

def _barycentric_coords(p, a, b, c):
    v0 = b - a
    v1 = c - a
    v2 = p - a
    d00 = np.dot(v0, v0)
    d01 = np.dot(v0, v1)
    d11 = np.dot(v1, v1)
    d20 = np.dot(v2, v0)
    d21 = np.dot(v2, v1)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12: return 1.0/3, 1.0/3, 1.0/3
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    return u, v, w

def _bary_delta_batch_bvh(buf_verts_np, owner_data, target_data):
    base_coords = owner_data['coords']
    deltas      = target_data - base_coords
    tri_verts   = owner_data['tri_verts']
    bvh         = owner_data['bvh']

    out = np.zeros_like(buf_verts_np)

    if bvh is not None:
        for i, bv in enumerate(buf_verts_np):
            mv = Vector(bv)
            loc, norm, face_idx, dist = bvh.find_nearest(mv)
            if face_idx is None:
                dists_sq = ((base_coords - bv) ** 2).sum(axis=1) + 1e-10
                w = 1.0 / dists_sq
                w /= w.sum()
                out[i] = (w[:, None] * deltas).sum(axis=0)
                continue
            ia, ib, ic = tri_verts[face_idx]
            a = base_coords[ia]; b = base_coords[ib]; c = base_coords[ic]
            wu, wv, ww = _barycentric_coords(np.array(bv), a, b, c)
            total = abs(wu) + abs(wv) + abs(ww)
            if total < 1e-9:
                wu, wv, ww = 1.0/3, 1.0/3, 1.0/3
            else:
                wu, wv, ww = wu/total, wv/total, ww/total
            out[i] = wu * deltas[ia] + wv * deltas[ib] + ww * deltas[ic]
    else:
        for i, bv in enumerate(buf_verts_np):
            dists_sq = ((base_coords - bv) ** 2).sum(axis=1) + 1e-10
            w = 1.0 / dists_sq
            w /= w.sum()
            out[i] = (w[:, None] * deltas).sum(axis=0)

    return out

# ---------------------------------------------------------------------------
# SLOW PATH — Универсальный Fallback
# ---------------------------------------------------------------------------

def _build_owner_data(obj, depsgraph, mat):
    eval_obj = obj.evaluated_get(depsgraph)
    b_eval   = eval_obj.to_mesh()

    mw3 = np.array(mat.to_3x3(), dtype=np.float64)
    mwt = np.array(mat.translation, dtype=np.float64)
    n_verts = len(b_eval.vertices)
    raw_co  = np.empty(n_verts * 3, dtype=np.float32)
    b_eval.vertices.foreach_get('co', raw_co)
    local_co = raw_co.reshape(-1, 3).astype(np.float64)
    coords = local_co @ mw3.T + mwt

    polys  = [list(p.vertices) for p in b_eval.polygons]

    b_eval.calc_loop_triangles()
    num_tris = len(b_eval.loop_triangles)
    if num_tris > 0:
        tri_flat = np.empty(num_tris * 3, dtype=np.int32)
        b_eval.loop_triangles.foreach_get("vertices", tri_flat)
        tri_verts = tri_flat.reshape((num_tris, 3))
        tri_list = tri_verts.tolist()
    else:
        tri_verts = np.zeros((0, 3), dtype=np.int32)
        tri_list = []

    bvh = BVHTree.FromPolygons([Vector(c) for c in coords], tri_list) if tri_list else None
    eval_obj.to_mesh_clear()

    return {'coords': coords, 'tri_verts': tri_verts, 'polys': polys, 'bvh': bvh, 'mat': mat}

def _assign_owners_bulk_bvh(buf_xyz, base_cache, limit):
    N = len(buf_xyz)
    owner_map = np.zeros(N, dtype=np.int64)
    dist_map  = np.full(N, np.inf, dtype=np.float64)

    for obj, data in base_cache.items():
        bvh = data['bvh']
        if bvh is None: continue
        for i, bv in enumerate(buf_xyz):
            _, _, _, dist = bvh.find_nearest(Vector(bv))
            if dist is not None and dist < dist_map[i] - 1e-5:
                dist_map[i]  = dist
                owner_map[i] = id(obj)

    owner_map[dist_map > limit] = 0
    return owner_map, dist_map

def _run_slow_path(context, sk_owner_map_slow, comp_cache, original_bytes,
                   stride, buf_v_count, output_dir, base_name, dump_name,
                   is_xxmi, limit, t_start, fast_path_slots=None):

    stride_f32 = stride // 4
    raw_np     = np.frombuffer(original_bytes, dtype=np.uint8)
    float_view = raw_np.reshape(buf_v_count, stride).view(np.float32).reshape(buf_v_count, stride // 4)
    buf_xyz    = float_view[:, :3].astype(np.float64)

    active_objects_set = set()
    for owners in sk_owner_map_slow.values():
        active_objects_set.update(owners['direct'])
        active_objects_set.update(owners['via_target'])
    active_objects = list(active_objects_set)
    if not active_objects: return 0

    linked_targets = get_linked_targets(active_objects)
    all_involved   = active_objects + list(set(linked_targets))
    depsgraph      = context.evaluated_depsgraph_get()

    sk_snapshot = {}
    for obj in all_involved:
        if obj.data and obj.data.shape_keys:
            sk_snapshot[obj] = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}

    set_armature_visibility(all_involved, False)

    try:
        for a_obj in all_involved:
            if a_obj.data and a_obj.data.shape_keys:
                for sk in a_obj.data.shape_keys.key_blocks:
                    sk.value = 0.0
        context.view_layer.update()
        depsgraph.update()

        base_cache = {}
        for obj in active_objects:
            import mathutils as mu
            m_idx = 0
            if comp_cache:
                for entry in comp_cache.get('objects', []):
                    if entry['name'] == obj.name:
                        m_idx = entry.get('mat_idx', 0)
                        break
            if m_idx == 1:
                mat = obj.matrix_world
            elif m_idx == 2:
                root_obj_name = comp_cache.get('root_obj')
                root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else active_objects[0]
                mat = root_obj.matrix_world.inverted() @ obj.matrix_world
            elif not is_xxmi:
                mat = obj.matrix_world
            else:
                mat = mu.Matrix.Identity(4)

            base_cache[obj] = _build_owner_data(obj, depsgraph, mat)

        search_buf_xyz = buf_xyz.copy()
        if not is_xxmi: search_buf_xyz[:, 0] *= -1

        owner_map, dist_map = _assign_owners_bulk_bvh(search_buf_xyz, base_cache, limit)
        stats = 0

        for sk_name, owners in sk_owner_map_slow.items():
            sk_direct = owners.get('direct', [])
            sk_via_target = owners.get('via_target', [])
            if not sk_direct and not sk_via_target: continue

            fp_slots = fast_path_slots.get(sk_name) if fast_path_slots else None
            if fp_slots is not None and fp_slots.any():
                effective_owner_map = owner_map.copy()
                effective_owner_map[fp_slots] = 0
            else:
                effective_owner_map = owner_map

            sk_weight = 0.05
            for obj in all_involved:
                if obj.data and obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = sk_weight if sk.name == sk_name else 0.0
            context.view_layer.update()
            depsgraph.update()

            target_cache = {}
            for obj in sk_direct + sk_via_target:
                if obj not in base_cache: continue
                eval_obj = obj.evaluated_get(depsgraph)
                t_eval   = eval_obj.to_mesh()
                mat      = base_cache[obj]['mat']
                mw3 = np.array(mat.to_3x3(), dtype=np.float64)
                mwt = np.array(mat.translation, dtype=np.float64)
                n_tv = len(t_eval.vertices)
                raw_t = np.empty(n_tv * 3, dtype=np.float32)
                t_eval.vertices.foreach_get('co', raw_t)
                t_coords = raw_t.reshape(-1, 3).astype(np.float64) @ mw3.T + mwt
                eval_obj.to_mesh_clear()
                
                if len(t_coords) == len(base_cache[obj]['coords']):
                    t_coords = base_cache[obj]['coords'] + (t_coords - base_cache[obj]['coords']) / sk_weight
                    target_cache[obj] = t_coords

            if not target_cache: continue

            out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
            out_path = os.path.join(output_dir, out_name)

            if os.path.exists(out_path):
                with open(out_path, 'rb') as f:
                    buf_f32 = np.frombuffer(f.read(), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
            else:
                buf_f32 = np.frombuffer(bytes(original_bytes), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()

            matched_count = 0
            for obj, t_coords in target_cache.items():
                mask = (effective_owner_map == id(obj))
                if not mask.any(): continue

                buf_sub = search_buf_xyz[mask]
                deltas  = _bary_delta_batch_bvh(buf_sub, base_cache[obj], t_coords)
                nonzero = np.linalg.norm(deltas, axis=1) > 1e-7
                if not nonzero.any(): continue

                indices = np.where(mask)[0][nonzero]
                valid_deltas = deltas[nonzero].copy()

                if not is_xxmi: valid_deltas[:, 0] *= -1

                new_xyz = (buf_xyz[indices] + valid_deltas).astype(np.float32)

                buf_f32[indices, 0] = new_xyz[:, 0]
                buf_f32[indices, 1] = new_xyz[:, 1]
                buf_f32[indices, 2] = new_xyz[:, 2]
                matched_count += len(indices)

            if matched_count > 0:
                with open(out_path, 'wb') as f:
                    f.write(buf_f32.tobytes())
                print(f"    -> [DONE] {out_name} ({matched_count} verts via Slow Path [Barycentric])")
                stats += 1

    finally:
        for obj, states in sk_snapshot.items():
            if obj.data and obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks:
                    if sk.name in states:
                        sk.value = states[sk.name]
        set_armature_visibility(all_involved, True)

    return stats

# ---------------------------------------------------------------------------
# CORE BAKE — оркестратор
# ---------------------------------------------------------------------------

def bake_component_shapes(context, base_name, comp_objects, mod_root, limit,
                           single_shape_name=None, full_export_mode=False):
    t_start   = time.time()
    vb0_path  = None
    dump_name = (os.path.basename(os.path.normpath(bpy.path.abspath(context.scene.xxmi.dump_path)))
                 if hasattr(context.scene, "xxmi") else "")

    game    = context.scene.rzm.game.name
    is_xxmi = game in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}

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

    if not vb0_path:
        print(f"  [ERROR] Position buffer not found for {base_name}")
        return False

    output_dir = os.path.join(mod_root, "SK")
    os.makedirs(output_dir, exist_ok=True)

    with open(vb0_path, "rb") as f:
        original_bytes = f.read()
    original_data = bytearray(original_bytes)

    stride = 40 if is_xxmi else 16 if game in {'ArknightsEndfield', 'WutheringWaves'} else 32

    rzm      = context.scene.rzm
    all_keys = ({single_shape_name} if single_shape_name
                else {c.shape_name for c in rzm.shape_configs if not c.disable_export})
    if not all_keys:
        return True

    sk_owner_map = _scan_sk_owners(comp_objects, all_keys)

    # Создаем заглушки-буферы
    for sk_name in all_keys:
        out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
        with open(os.path.join(output_dir, out_name), "wb") as f:
            f.write(original_bytes)

    if not sk_owner_map:
        return True

    try:
        from .export_cache import component_cache
        comp_cache = component_cache(base_name)
    except Exception:
        comp_cache = None

    buf_v_count = len(original_data) // stride
    if comp_cache:
        stride = comp_cache.get('stride', stride)
        buf_v_count = len(original_data) // stride

    # ── 1. ФАЗА ПОДГОТОВКИ (Pre-Processing) ────────────────────────────────
    ready_map = {}
    temp_objects = []
    
    orig_active = context.view_layer.objects.active
    orig_selected = context.selected_objects.copy()

    try:
        for obj in comp_objects:
            needs_sd = False
            sd_target = None
            sd_mod = None
            keys_to_transfer = []

            for mod in obj.modifiers:
                if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                    tgt = mod.target
                    if tgt.data and tgt.data.shape_keys:
                        for sk_name in all_keys:
                            if sk_name in tgt.data.shape_keys.key_blocks:
                                if not obj.data or not obj.data.shape_keys or sk_name not in obj.data.shape_keys.key_blocks:
                                    keys_to_transfer.append(sk_name)
                    if keys_to_transfer:
                        needs_sd = True
                        sd_target = tgt
                        sd_mod = mod
                    break

            needs_mod_bake = False
            for mod in obj.modifiers:
                if mod.show_viewport and mod.type != 'ARMATURE':
                    if needs_sd and mod == sd_mod:
                        continue
                    needs_mod_bake = True
                    break

            has_direct_keys = False
            if obj.data and obj.data.shape_keys:
                for sk_name in all_keys:
                    if sk_name in obj.data.shape_keys.key_blocks:
                        has_direct_keys = True
                        break

            if not has_direct_keys and not needs_sd:
                continue

            if not needs_sd and not needs_mod_bake:
                ready_map[obj] = obj
                continue

            # Создаем временный объект
            bpy.ops.object.select_all(action='DESELECT')
            temp_obj = obj.copy()
            temp_obj.data = obj.data.copy()
            context.collection.objects.link(temp_obj)
            temp_obj.select_set(True)
            context.view_layer.objects.active = temp_obj
            temp_objects.append(temp_obj)

            set_armature_visibility([temp_obj], False)
            bake_success = True

            # Этап A: Surface Deform Baking
            if needs_sd:
                try:
                    from .rzm_surface_baker import transfer_surface_shape_keys
                    print(f"  [SURFACE BAKE] Transferring {len(keys_to_transfer)} keys from {sd_target.name} to {obj.name}")
                    transfer_surface_shape_keys(temp_obj, sd_target, keys_to_transfer)
                    
                    mod_to_remove = temp_obj.modifiers.get(sd_mod.name)
                    if mod_to_remove:
                        temp_obj.modifiers.remove(mod_to_remove)
                except Exception as e:
                    print(f"  [ERROR] Surface bake failed for {obj.name}: {e}")
                    bake_success = False

            # Этап B: Запекание модификаторов
            if bake_success and (needs_mod_bake or (needs_sd and has_active_modifiers(temp_obj))):
                print(f"  [MOD BAKE] Baking modifiers for {obj.name} via Gret standalone...")
                try:
                    bpy.ops.rz.shape_key_apply_modifiers()
                    new_active = context.view_layer.objects.active
                    if new_active not in temp_objects:
                        temp_objects.append(new_active)
                    temp_obj = new_active
                except Exception as e:
                    print(f"  [ERROR] Mod bake failed for {obj.name}: {e}")
                    bake_success = False

            set_armature_visibility([temp_obj], True)
            
            if bake_success:
                ready_map[obj] = temp_obj

        # ── 2. EXACT MATCH PATH (Выгрузка) ─────────────────────────────────────
        fast_path_slots, stats_exact, failed_exact = _process_exact_matches(
            sk_owner_map, ready_map, comp_cache,
            original_bytes, stride, buf_v_count,
            output_dir, base_name, dump_name, is_xxmi
        )

        # ── 3. SLOW PATH (Fallback) ────────────────────────────────────────────
        # Собираем все объекты, которые провалили Exact Match (ошибки, нет v_map, и т.д.)
        sk_owner_map_slow = {sk: owners for sk, owners in failed_exact.items() if owners['direct'] or owners['via_target']}
        stats_slow = 0

        if sk_owner_map_slow:
            print(f"  [SLOW PATH] Spatial Barycentric Fallback")
            stats_slow = _run_slow_path(
                context, sk_owner_map_slow, comp_cache,
                original_bytes, stride, buf_v_count,
                output_dir, base_name, dump_name, is_xxmi, limit, t_start,
                fast_path_slots=fast_path_slots
            )

        # ── SUMMARY ──
        print(f"\n  [SUMMARY] {base_name} component finished in {time.time() - t_start:.3f}s")
        print(f"    - Exact Match (v_map):   {stats_exact['vmap_matched']} objects")
        print(f"    - Exact Match (KD-Tree): {stats_exact['kd_matched']} objects")
        print(f"    - Slow Path (Fallback):  {stats_slow} objects")
            
    finally:
        # УДАЛЕНИЕ ВРЕМЕННЫХ ОБЪЕКТОВ
        bpy.ops.object.select_all(action='DESELECT')
        for t_obj in temp_objects:
            if t_obj and t_obj.name in bpy.data.objects:
                bpy.data.objects.remove(t_obj, do_unlink=True)
                
        # Восстанавливаем выделение
        for o in orig_selected:
            if o.name in bpy.data.objects: o.select_set(True)
        if orig_active and orig_active.name in bpy.data.objects:
            context.view_layer.objects.active = orig_active

    return True

# ---------------------------------------------------------------------------
# OPERATORS
# ---------------------------------------------------------------------------

class RZM_OT_PuppetMasterBake(bpy.types.Operator):
    bl_idname     = "rzm.puppet_master_bake"
    bl_label      = "Bake Puppet Master Shapes"
    bl_description = "Bake shape keys using strictly RZMenu Shape Configs"
    full_export_mode: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root): return {'CANCELLED'}
        addons        = context.scene.rzm.addons
        per_component = False if self.full_export_mode else addons.puppet_master_per_component
        limit         = addons.puppet_master_limit
        components    = get_components_to_process(context, per_component)
        if not components: return {'CANCELLED'}
        for base_name, objs in components.items():
            bake_component_shapes(context, base_name, objs, mod_root, limit,
                                   full_export_mode=self.full_export_mode)
        return {'FINISHED'}


class RZM_OT_PuppetMasterBakeSingle(bpy.types.Operator):
    bl_idname     = "rzm.puppet_master_bake_single"
    bl_label      = "Bake Selected Shape Key"
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
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)