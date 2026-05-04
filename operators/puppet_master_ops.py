# RZMenu/operators/puppet_master_ops.py
#
# Hybrid Pipeline — три уровня экспорта:
#   1. FAST PATH       — прямой топологический маппинг из кэша (EFMI/XXMI).
#                        Только для объектов БЕЗ топологических модификаторов.
#   2. TOPOLOGY BAKE   — для объектов с Mirror/Subdiv/Array и т.п.:
#                        Запекает топологию из базиса и применяет статично.
#                        Идеально совпадает с буфером, не боится Mirror+Merge.
#   3. SLOW PATH       — пространственная интерполяция для объектов без кэша или
#                        для via_target (Surface Deform). Используется BVH + барицентрика.
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
from .mesh_baker import has_topology_modifiers, bake_shapekeys_with_modifiers

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

# ---------------------------------------------------------------------------
# FILENAMING
# ---------------------------------------------------------------------------

def _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name):
    raw_base   = (dump_name + base_name) if is_xxmi else base_name
    clean_base = re.sub(r'[\\/:*?"<>|]', '_', raw_base).replace(' ', '_').replace('.', '_')
    clean_sk   = re.sub(r'[\\/:*?"<>|]', '_', sk_name).replace(' ', '_').replace('.', '_')
    return f"{clean_base}_{clean_sk}.buf"

# ---------------------------------------------------------------------------
# SK OWNER SCAN
# ---------------------------------------------------------------------------

def _scan_sk_owners(comp_objects, all_keys):
    """Классифицирует объекты по способу их деформации для каждого шейпкея."""
    result = {}
    for sk_name in all_keys:
        direct, needs_bake, via_target = [], [], []
        
        for obj in comp_objects:
            has_direct_sk = False
            
            # Проверяем прямые шейпкеи
            if obj.data and obj.data.shape_keys:
                sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
                ba_blk = obj.data.shape_keys.reference_key
                if sk_blk and ba_blk and sk_blk.data and ba_blk.data:
                    sk_co = np.array([kp.co for kp in sk_blk.data], dtype=np.float32)
                    ba_co = np.array([kp.co for kp in ba_blk.data], dtype=np.float32)
                    if np.any(np.abs(sk_co - ba_co) > 1e-7):
                        has_direct_sk = True

            # Проверяем Surface Deform / Shrinkwrap
            is_via_target = False
            for mod in obj.modifiers:
                if (mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'}
                        and mod.show_viewport and mod.target
                        and mod.target.data and mod.target.data.shape_keys
                        and sk_name in mod.target.data.shape_keys.key_blocks):
                    is_via_target = True
                    break

            if has_direct_sk:
                if has_topology_modifiers(obj):
                    needs_bake.append(obj)
                else:
                    direct.append(obj)
            elif is_via_target:
                via_target.append(obj)

        if direct or needs_bake or via_target:
            result[sk_name] = {'direct': direct, 'needs_bake': needs_bake, 'via_target': via_target}
            
    return result

# ---------------------------------------------------------------------------
# FAST PATH — прямой маппинг из кэша (Только ORIG mode)
# ---------------------------------------------------------------------------

def _bake_with_direct_offsets(sk_owner_map_fast, comp_cache, original_bytes,
                               stride, buf_v_count, output_dir,
                               base_name, dump_name, is_xxmi):
    import mathutils
    stride_f32    = stride // 4
    cache_objects = {entry['name']: entry for entry in comp_cache.get('objects', [])}

    fallback_objs_per_sk: dict = {}
    fast_path_slots_per_sk: dict = {}

    for sk_name, owners in sk_owner_map_fast.items():
        buf_f32       = np.frombuffer(bytes(original_bytes), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
        matched_count = 0
        fallback_this = []
        map_type      = "Relative"
        sk_fast_slots = np.zeros(buf_v_count, dtype=bool)

        for obj in owners['direct']:
            entry = cache_objects.get(obj.name)
            if entry is None:
                fallback_this.append(obj)
                continue

            sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
            ba_blk = obj.data.shape_keys.reference_key

            is_absolute = entry.get('is_absolute', False)
            vb_off      = 0 if is_absolute else entry['vb_offset']
            vb_cnt      = entry['vb_count']
            v_map       = entry.get('vertex_map')
            m_idx       = entry.get('mat_idx', 0)
            map_type    = "Absolute" if is_absolute else "Relative"

            if v_map is None or len(v_map) != vb_cnt:
                print(f"    [WARN] {obj.name}: no valid map → Fallback.")
                fallback_this.append(obj)
                continue

            orig_v_count = len(obj.data.vertices)
            v_map_np     = np.array(v_map, dtype=np.int32)
            
            # Проверка границ индексов (на случай если объект попал сюда ошибочно)
            if len(v_map_np) > 0 and v_map_np.max() >= orig_v_count:
                print(f"    [ERROR] {obj.name}: Topology mismatch in Fast Path. Fallback -> Topology Bake.")
                fallback_this.append(obj)
                continue

            mat = mathutils.Matrix.Identity(4)
            if m_idx == 1:
                mat = obj.matrix_world
            elif m_idx == 2:
                root_obj_name = comp_cache.get('root_obj')
                root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else None
                mat = (root_obj.matrix_world.inverted() @ obj.matrix_world
                       if root_obj else mathutils.Matrix.Identity(4))

            # Читаем дельты напрямую (ORIG mode)
            sk_co = np.empty(orig_v_count * 3, dtype=np.float32)
            ba_co = np.empty(orig_v_count * 3, dtype=np.float32)
            sk_blk.data.foreach_get('co', sk_co)
            ba_blk.data.foreach_get('co', ba_co)
            
            sk_co = sk_co.reshape(-1, 3)
            ba_co = ba_co.reshape(-1, 3)
            mat_rot = np.array(mat.to_3x3(), dtype=np.float32)
            
            deltas_all = ((sk_co - ba_co) @ mat_rot.T).astype(np.float32)
            if not is_xxmi:
                deltas_all[:, 0] *= -1

            if vb_off + vb_cnt > buf_v_count:
                print(f"    [ERROR] {obj.name}: offset OOB → Fallback.")
                fallback_this.append(obj)
                continue

            obj_slice = buf_f32[vb_off: vb_off + vb_cnt, :3]
            buf_f32[vb_off: vb_off + vb_cnt, :3] = (obj_slice + deltas_all[v_map_np]).astype(np.float32)
            
            sk_fast_slots[vb_off: vb_off + vb_cnt] = True
            matched_count += vb_cnt
            print(f"    [FAST/ORIG] {obj.name}: {vb_cnt} slots for '{sk_name}'.")

        out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
        if matched_count > 0:
            with open(os.path.join(output_dir, out_name), 'wb') as f:
                f.write(buf_f32.tobytes())
            print(f"    -> [DONE] {out_name} ({matched_count} verts via Fast Path)")

        fallback_objs_per_sk[sk_name] = fallback_this
        fast_path_slots_per_sk[sk_name] = sk_fast_slots

    return fallback_objs_per_sk, fast_path_slots_per_sk


# ---------------------------------------------------------------------------
# TOPOLOGY BAKE PATH — Статическое применение топологических модификаторов
# ---------------------------------------------------------------------------

def _topology_bake_path(context, sk_owner_map_bake, comp_cache,
                        original_bytes, stride, buf_v_count,
                        output_dir, base_name, dump_name, is_xxmi):
    import mathutils as mu
    stride_f32 = stride // 4
    remaining_for_slow = {}
    cache_objects = {e['name']: e for e in comp_cache.get('objects', [])} if comp_cache else {}

    all_bake_objs = set(obj for owners in sk_owner_map_bake.values() for obj in owners if obj)
    set_armature_visibility(all_bake_objs, False)

    try:
        for obj in all_bake_objs:
            relevant_sk_names = [sk for sk, owners in sk_owner_map_bake.items() if obj in owners]
            if not relevant_sk_names: continue
            
            print(f"  [TOPO BAKE] Processing {obj.name} via Static Modifiers Bake")
            
            try:
                baked_data = bake_shapekeys_with_modifiers(obj, relevant_sk_names)
            except Exception as e:
                print(f"    [WARN] Topology bake failed for {obj.name}: {e}. Fallback -> Slow Path.")
                for sk in relevant_sk_names:
                    remaining_for_slow.setdefault(sk, []).append(obj)
                continue

            basis_coords = baked_data['basis_coords']
            kd = mu.kdtree.KDTree(len(basis_coords))
            for i, co in enumerate(basis_coords):
                kd.insert(mu.Vector(co), i)
            kd.balance()

            entry = cache_objects.get(obj.name)
            vb_off = entry.get('vb_offset', 0) if entry else 0
            vb_cnt = entry.get('vb_count', buf_v_count) if entry else buf_v_count
            
            DIST_THRESHOLD = 0.05

            for sk_name in relevant_sk_names:
                delta = baked_data['deltas'].get(sk_name)
                if delta is None:
                    remaining_for_slow.setdefault(sk_name, []).append(obj)
                    continue

                out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
                out_path = os.path.join(output_dir, out_name)

                if os.path.exists(out_path):
                    with open(out_path, 'rb') as f:
                        buf_f32 = np.frombuffer(f.read(), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
                else:
                    buf_f32 = np.frombuffer(bytes(original_bytes), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()

                matched_count = 0
                for buf_idx in range(vb_off, vb_off + vb_cnt):
                    buf_pos = mu.Vector(buf_f32[buf_idx, :3])
                    
                    # Компенсация координаты X для не-XXMI игр
                    search_pos = buf_pos.copy()
                    if not is_xxmi:
                        search_pos.x *= -1
                        
                    _, baked_v_idx, dist = kd.find(search_pos)
                    if dist > DIST_THRESHOLD: continue

                    d = delta[baked_v_idx].copy()
                    if np.linalg.norm(d) < 1e-7: continue
                    
                    if not is_xxmi:
                        d[0] *= -1

                    buf_f32[buf_idx, 0] += d[0]
                    buf_f32[buf_idx, 1] += d[1]
                    buf_f32[buf_idx, 2] += d[2]
                    matched_count += 1

                if matched_count > 0:
                    with open(out_path, 'wb') as f:
                        f.write(buf_f32.tobytes())
                    print(f"    [TOPO BAKE] {obj.name}: {matched_count} verts matched for '{sk_name}'")
                else:
                    print(f"    [WARN] {obj.name}: 0 matched verts for '{sk_name}'. Fallback -> Slow Path.")
                    remaining_for_slow.setdefault(sk_name, []).append(obj)

    finally:
        set_armature_visibility(all_bake_objs, True)

    return remaining_for_slow

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
    if abs(denom) < 1e-12:
        return 1.0/3, 1.0/3, 1.0/3
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
# SLOW PATH — пространственная интерполяция
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

    if tri_list:
        bvh = BVHTree.FromPolygons([Vector(c) for c in coords], tri_list)
    else:
        bvh = None

    eval_obj.to_mesh_clear()

    return {
        'coords':    coords,
        'tri_verts': tri_verts,
        'polys':     polys,
        'bvh':       bvh,
        'mat':       mat,
    }

def _assign_owners_bulk_bvh(buf_xyz, base_cache, limit):
    N        = len(buf_xyz)
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
    if not active_objects: return

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

        # Компенсация X для BVH матчинга в не-XXMI
        search_buf_xyz = buf_xyz.copy()
        if not is_xxmi:
            search_buf_xyz[:, 0] *= -1

        owner_map, dist_map = _assign_owners_bulk_bvh(search_buf_xyz, base_cache, limit)

        for sk_name, owners in sk_owner_map_slow.items():
            sk_direct     = owners['direct']
            sk_via_target = owners['via_target']

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

            if not target_cache:
                continue

            out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
            out_path = os.path.join(output_dir, out_name)

            if os.path.exists(out_path):
                with open(out_path, 'rb') as f:
                    buf_bytes = f.read()
                buf_f32 = np.frombuffer(buf_bytes, dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
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

                indices      = np.where(mask)[0][nonzero]
                valid_deltas = deltas[nonzero].copy()

                if not is_xxmi:
                    valid_deltas[:, 0] *= -1

                new_xyz = (buf_xyz[indices] + valid_deltas).astype(np.float32)

                buf_f32[indices, 0] = new_xyz[:, 0]
                buf_f32[indices, 1] = new_xyz[:, 1]
                buf_f32[indices, 2] = new_xyz[:, 2]
                matched_count += len(indices)

            if matched_count > 0:
                with open(out_path, 'wb') as f:
                    f.write(buf_f32.tobytes())
                print(f"    -> [DONE] {out_name} ({matched_count} verts via Slow Path [Barycentric])")

    finally:
        for obj, states in sk_snapshot.items():
            if obj.data and obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks:
                    if sk.name in states:
                        sk.value = states[sk.name]
        set_armature_visibility(all_involved, True)

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

    # ── FAST PATH ──────────────────────────────────────────────────────────
    sk_owner_map_fast = {}
    for sk_name, owners in sk_owner_map.items():
        if owners['direct']:
            sk_owner_map_fast[sk_name] = {'direct': owners['direct']}

    sk_owner_map_after_fast = {}

    if comp_cache is not None and sk_owner_map_fast:
        stride = comp_cache.get('stride', stride)
        buf_v_count = len(original_data) // stride

        fallback_map, fast_path_slots_per_sk = _bake_with_direct_offsets(
            sk_owner_map_fast, comp_cache, original_bytes,
            stride, buf_v_count, output_dir, base_name, dump_name, is_xxmi
        )

        for sk_name, owners in sk_owner_map.items():
            direct_fb  = fallback_map.get(sk_name, [])
            needs_bake = owners.get('needs_bake', [])
            via_target = owners.get('via_target', [])

            if direct_fb or needs_bake or via_target:
                sk_owner_map_after_fast[sk_name] = {
                    'needs_bake': direct_fb + needs_bake,
                    'via_target': via_target
                }
    else:
        for sk_name, owners in sk_owner_map.items():
            sk_owner_map_after_fast[sk_name] = {
                'needs_bake': owners.get('direct', []) + owners.get('needs_bake', []),
                'via_target': owners.get('via_target', [])
            }
        fast_path_slots_per_sk = {}

    # ── TOPOLOGY BAKE (Static Mods) ────────────────────────────────────────
    sk_owner_map_bake   = {}
    sk_owner_map_slow   = {}

    for sk_name, owners in sk_owner_map_after_fast.items():
        bake_objs = owners.get('needs_bake', [])
        if bake_objs:
            sk_owner_map_bake[sk_name] = bake_objs

        via_objs = owners.get('via_target', [])
        if via_objs:
            sk_owner_map_slow.setdefault(sk_name, {'direct': [], 'via_target': []})['via_target'].extend(via_objs)

    if sk_owner_map_bake:
        print(f"  [TOPOLOGY BAKE] Processing {sum(len(v) for v in sk_owner_map_bake.values())} objects via Static Mesh Bake")
        remaining = _topology_bake_path(
            context, sk_owner_map_bake, comp_cache,
            original_bytes, stride, buf_v_count,
            output_dir, base_name, dump_name, is_xxmi
        )
        for sk_name, objs in remaining.items():
            sk_owner_map_slow.setdefault(sk_name, {'direct': [], 'via_target': []})['direct'].extend(objs)

    # ── SLOW PATH (Barycentric) ────────────────────────────────────────────
    if sk_owner_map_slow:
        sk_owner_map_slow = {
            sk: owners for sk, owners in sk_owner_map_slow.items()
            if owners.get('direct') or owners.get('via_target')
        }

    if sk_owner_map_slow:
        print(f"  [SLOW PATH] Spatial Barycentric for Object Bind (Surface Deform) and Failures")
        _run_slow_path(
            context, sk_owner_map_slow, comp_cache,
            original_bytes, stride, buf_v_count,
            output_dir, base_name, dump_name, is_xxmi, limit, t_start,
            fast_path_slots=fast_path_slots_per_sk
        )

    # ── SUMMARY ──
    print(f"\n  [SUMMARY] {base_name} component finished in {time.time() - t_start:.3f}s")
    
    fast_count = sum(len(owners['direct']) for owners in sk_owner_map_fast.values()) - sum(len(owners.get('needs_bake', [])) for owners in sk_owner_map_after_fast.values() if not sk_owner_map.get('needs_bake'))
    bake_count = sum(len(v) for v in sk_owner_map_bake.values())
    slow_count = sum(len(v['direct']) + len(v['via_target']) for v in sk_owner_map_slow.values())
    
    print(f"    - Fast Path (Direct Map): {max(0, fast_count)} executions")
    print(f"    - Topology Bake (Static Mods): {bake_count} executions")
    print(f"    - Slow Path (Barycentric): {slow_count} executions")
    
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