# RZMenu/operators/puppet_master_ops.py
#
# Hybrid Pipeline v6 (Order of Operations Fix + Slow Path Fallback)
#   
#   Фаза 1: ПОДГОТОВКА (Pre-Processing)
#     - Объекты сортируются: доноры обрабатываются первыми.
#     - Шаг А: Отключение SurfaceDeform (чтобы не исказить генерацию топологии).
#     - Шаг Б: Запекание модификаторов (rz.shape_key_apply_modifiers).
#     - Шаг В: Перенос недостающих шейпкеев с УЖЕ ЗАПЕЧЕННОГО донора на 
#       уже запеченный объект через rzm_surface_baker.
#       
#   Фаза 2: EXACT MATCH (Выгрузка)
#     - Дельты наносятся на буфер через топологический v_map.
#     - Если v_map нет — точный перенос через KD-Tree по координатам Базиса.
#
#   Фаза 3: SLOW PATH (Fallback)
#     - Спасательный круг. Включается автоматически, если Exact Match 
#       не сработал (сбои, новая игра без кэша и т.д.).
#
import bpy
import os
import re
import json
import time
import struct
import numpy as np
from math import radians
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from . import blendworks_baker
from . import rzm_surface_baker
from ..utils.shape_export_filter import (
    active_shape_configs,
    active_weight_shape_configs,
    object_shape_key_is_exportable,
    prepare_shape_config_export_runtime,
    shape_config_matches_component,
    shape_key_block_is_exportable,
)

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

def get_components_to_process(context, per_component=False):
    """
    Retrieves components to process using the generalized ComponentCollector abstraction.
    """
    from ..utils.component_collector import ComponentCollector
    collector = ComponentCollector(context)
    return collector.get_components(per_component=per_component)


def _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name):
    if is_xxmi:
        raw_base = (dump_name + base_name)
    else:
        raw_base = base_name if base_name else "Main"
        
    clean_base = re.sub(r'[\\/:*?"<>|]', '_', raw_base).replace(' ', '_').replace('.', '_')
    clean_sk   = re.sub(r'[\\/:*?"<>|]', '_', sk_name).replace(' ', '_').replace('.', '_')
    
    return f"{clean_base}_{clean_sk}.buf"

# ---------------------------------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------------------------------

def has_active_modifiers(obj):
    for m in obj.modifiers:
        if not m.show_viewport:
            continue
        if m.type in {'ARMATURE', 'DATA_TRANSFER'}:
            continue
        return True
    return False

def _component_affected_names(base_name, comp_cache, dump_name, is_xxmi):
    names = {str(base_name or "").lower()}
    if dump_name:
        names.add(f"{dump_name}{base_name}".lower())

    if comp_cache:
        comp_name = comp_cache.get('name') or comp_cache.get('component_name')
        if comp_name:
            names.add(str(comp_name).lower())
        for entry in comp_cache.get('objects', []):
            obj_name = entry.get('name')
            if obj_name:
                names.add(str(obj_name).lower())

    return list(names)

def _component_shape_key_names(active_configs, affected_names, single_shape_name=None):
    if single_shape_name:
        return {
            config.shape_name
            for config in active_configs
            if config.shape_name == single_shape_name
        }

    return {
        config.shape_name
        for config in active_configs
        if shape_config_matches_component(config, affected_names)
    }

def _write_noop_shape_buffers(output_dir, base_name, shape_names, is_xxmi, dump_name, original_bytes):
    written = 0
    for sk_name in sorted(shape_names):
        out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
        with open(os.path.join(output_dir, out_name), "wb") as f:
            f.write(original_bytes)
        written += 1

    if written:
        print(f"  [NO-OP] Wrote {written} full-size base shape buffer(s) for {base_name}.")

def _validate_shape_buffer_sizes(output_dir, base_name, shape_names, is_xxmi, dump_name, expected_size):
    for sk_name in sorted(shape_names):
        out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
        out_path = os.path.join(output_dir, out_name)
        if not os.path.exists(out_path):
            print(f"  [ERROR] Missing shape buffer after bake: {out_name}")
            continue
        actual_size = os.path.getsize(out_path)
        if actual_size != expected_size:
            print(
                f"  [ERROR] Shape buffer size mismatch: {out_name} "
                f"size={actual_size}, expected={expected_size}"
            )

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
                if shape_key_block_is_exportable(sk_blk) and ba_blk and sk_blk.data and ba_blk.data:
                    sk_co = np.array([kp.co for kp in sk_blk.data], dtype=np.float32)
                    ba_co = np.array([kp.co for kp in ba_blk.data], dtype=np.float32)
                    if np.any(np.abs(sk_co - ba_co) > 1e-7):
                        has_direct_sk = True

            is_via_target = False
            for mod in obj.modifiers:
                if not (mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'}
                        and mod.show_viewport and mod.target
                        and mod.target.data and mod.target.data.shape_keys):
                    continue
                target_key = mod.target.data.shape_keys.key_blocks.get(sk_name)
                if shape_key_block_is_exportable(target_key):
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

def _object_has_direct_shape_key(obj, shape_name):
    if not obj or not getattr(obj, "data", None) or not getattr(obj.data, "shape_keys", None):
        return False
    return obj.data.shape_keys.key_blocks.get(shape_name) is not None

def should_mirror_mesh(context, game_name):
    """
    Determines if X-axis mirroring should be applied.
    For Arknights Endfield, respects efmi_tools_settings.mirror_mesh.
    For others, uses RZMenu addon settings.
    """
    if game_name == 'ArknightsEndfield' and hasattr(context.scene, "efmi_tools_settings"):
        return context.scene.efmi_tools_settings.mirror_mesh
    
    rzm = context.scene.rzm
    return rzm.addons.mirror_mesh

def should_invert_shape_key_x(context):
    rzm = context.scene.rzm
    return getattr(rzm.addons, "shape_key_invert_x", False)

def _find_xxmi_anchor(context, mod_name, comp_name, classifications):
    """
    Dynamically finds the unique visible anchor object for an XXMI component.
    Uses naming prefix: CharName + ComponentName + SubComponentName.
    Returns: (Matrix, bool_flip)
    """
    import mathutils as mu
    
    def is_truly_visible(obj):
        return obj.visible_get() and not obj.hide_viewport

    # Build search prefixes
    # If no classifications provided, we'll try a few common ones or just the comp_name
    search_prefixes = []
    if classifications:
        for sub_comp in classifications:
            search_prefixes.append(f"{mod_name}{comp_name}{sub_comp}".lower())
    else:
        # Fallback: try common sub-components if it's the main component
        base_prefix = f"{mod_name}{comp_name}".lower()
        search_prefixes.append(base_prefix)
        # XXMI often uses Body/Head/Dress/Extra/Accessories/Bang/Eyes
        for common in ["Body", "Head", "Dress", "Extra", "Accessories", "Bang", "Eyes", "Face"]:
            search_prefixes.append(f"{base_prefix}{common}".lower())
    
    # We prioritize the first prefix that yields a visible anchor
    for prefix in search_prefixes:
        found_visible = []
        for obj in bpy.data.objects:
            if obj.name.lower().startswith(prefix):
                if is_truly_visible(obj):
                    found_visible.append(obj)
        
        if found_visible:
            anchor = found_visible[0]
            # Matrix inversion 'extinguishes' the Blender-side transformation
            orient_mat = anchor.matrix_world.inverted()
            flip_mesh = bool(anchor.get("3DMigoto:FlipMesh", 0))
            
            if len(found_visible) > 1:
                print(f"  [RZM] [WARNING] Multiple visible anchors for prefix '{prefix}'. Using {anchor.name}.")
            
            print(f"  [RZM] [ANCHOR] Found anchor '{anchor.name}' for prefix '{prefix}'.")
            return orient_mat, flip_mesh

    return mu.Matrix.Identity(4), False

def _resolve_component_transform(context, is_xxmi, game_name, mod_name, comp_name, classifications):
    """
    Determines the final orientation matrix and mirror toggle for a component.
    """
    import mathutils as mu
    
    if is_xxmi:
        # Dynamic Anchor Path
        orient_mat, mirror_enabled = _find_xxmi_anchor(context, mod_name, comp_name, classifications)
        if orient_mat != mu.Matrix.Identity(4):
            print(f"  [RZM] [ANCHOR] Applied dynamic transformation from scene anchor.")
        else:
            # Fallback for XXMI if no anchor found (Legacy behavior or Identity)
            mirror_enabled = should_mirror_mesh(context, game_name)
            # You could add legacy Genshin/HSR fallbacks here if desired
            pass
        return orient_mat, mirror_enabled
    
    # EFMI / Legacy Path
    mirror_enabled = should_mirror_mesh(context, game_name)
    return mu.Matrix.Identity(4), mirror_enabled

# ---------------------------------------------------------------------------
# EXACT MATCH PATH (Fast Path + KD-Tree)
# ---------------------------------------------------------------------------

def _process_exact_matches(context, sk_owner_map, ready_map, comp_cache, original_bytes,
                           stride, buf_v_count, output_dir, base_name, dump_name, is_xxmi, game_name,
                           orient_mat=None, mirror_enabled=None):
    import mathutils as mu
    stride_f32 = stride // 4
    cache_objects = {entry['name']: entry for entry in comp_cache.get('objects', [])} if comp_cache else {}

    fast_path_slots_per_sk = {}
    stats = {'vmap_matched': 0, 'kd_matched': 0, 'objects': 0}
    failed_objects = {sk: {'direct': [], 'via_target': []} for sk in sk_owner_map.keys()}

    orient_mat = orient_mat if orient_mat is not None else mu.Matrix.Identity(4)
    mirror_enabled = mirror_enabled if mirror_enabled is not None else False
    invert_x_enabled = should_invert_shape_key_x(context)

    for sk_name, owners in sk_owner_map.items():
        buf_f32 = np.frombuffer(bytes(original_bytes), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
        sk_fast_slots = np.zeros(buf_v_count, dtype=bool)
        
        objs_to_process = []
        for obj in owners['direct_raw']: 
            objs_to_process.append((obj, obj))
            
        for obj in owners['direct_bake'] + owners['via_target']:
            ready_obj = ready_map.get(obj)
            if ready_obj and ready_obj.data and ready_obj.data.shape_keys and sk_name in ready_obj.data.shape_keys.key_blocks:
                objs_to_process.append((obj, ready_obj))
            else:
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

            if m_idx in (1, -1):
                mat = orig_obj.matrix_world
            elif m_idx == 2:
                root_obj_name = comp_cache.get('root_obj')
                root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else None
                mat = (root_obj.matrix_world.inverted() @ orig_obj.matrix_world if root_obj else mu.Matrix.Identity(4))
            else:
                mat = mu.Matrix.Identity(4)

            mat = orient_mat @ mat

            v_count = len(target_obj.data.vertices)
            sk_co = np.empty(v_count * 3, dtype=np.float32)
            ba_co = np.empty(v_count * 3, dtype=np.float32)
            sk_blk.data.foreach_get('co', sk_co)
            ba_blk.data.foreach_get('co', ba_co)
            sk_co = sk_co.reshape(-1, 3)
            ba_co = ba_co.reshape(-1, 3)

            mat_rot = np.array(mat.to_3x3(), dtype=np.float32)
            deltas_all = ((sk_co - ba_co) @ mat_rot.T).astype(np.float32)
            
            if mirror_enabled:
                # Mirror Path (Deltas must be standard space for standard buffer)
                deltas_all[:, 0] *= -1

            if invert_x_enabled:
                deltas_all[:, 0] *= -1

            if vb_off + vb_cnt > buf_v_count:
                print(f"    [ERROR] {orig_obj.name}: Buffer bounds exceeded. Forwarding to Slow Path.")
                if orig_obj in owners['via_target']: failed_objects[sk_name]['via_target'].append(orig_obj)
                else: failed_objects[sk_name]['direct'].append(orig_obj)
                continue

            obj_slice = buf_f32[vb_off: vb_off + vb_cnt, :3]
            matched_count = 0

            # 1: Идеальный маппинг по v_map
            if v_map and len(v_map) == vb_cnt and max(v_map) < v_count:
                v_map_np = np.array(v_map, dtype=np.int32)
                buf_f32[vb_off: vb_off + vb_cnt, :3] = (obj_slice + deltas_all[v_map_np]).astype(np.float32)
                matched_count = vb_cnt
                print(f"    [EXACT/VMAP] {orig_obj.name}: {matched_count} slots matched.")
                stats['vmap_matched'] += 1
            
            # 2: Пространственный маппинг (KD-Tree)
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
                    if mirror_enabled:
                        # If mirroring is requested, buffer is standard but search tree is mirrored
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
# BARYCENTRIC DELTA INTERPOLATION (Slow Path Fallback)
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
                   is_xxmi, limit, t_start, game_name, fast_path_slots=None,
                   orient_mat=None, mirror_enabled=None):

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
        orient_mat = orient_mat if orient_mat is not None else mu.Matrix.Identity(4)
        mirror_enabled = mirror_enabled if mirror_enabled is not None else False
        invert_x_enabled = should_invert_shape_key_x(context)

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
            if m_idx in (1, -1):
                mat = obj.matrix_world
            elif m_idx == 2:
                root_obj_name = comp_cache.get('root_obj')
                root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else active_objects[0]
                mat = root_obj.matrix_world.inverted() @ obj.matrix_world
            else:
                mat = mu.Matrix.Identity(4)

            # [Orientation Patch] Apply integrated game orientation (Rotation or Mirror)
            mat = orient_mat @ mat

            base_cache[obj] = _build_owner_data(obj, depsgraph, mat)

        search_buf_xyz = buf_xyz.copy()
        if mirror_enabled:
            # Mirror the search coords to match the search tree (BVH)
            search_buf_xyz[:, 0] *= -1
        
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

                if mirror_enabled:
                    # Flip back to standard space for standard buffer
                    valid_deltas[:, 0] *= -1

                if invert_x_enabled:
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
# BLENDWORKS: Weight Morphing (Phase 1)
# ---------------------------------------------------------------------------

def _pack_efmi_vb2(obj, output_path, donor_obj, buf_xyz):
    """
    Orchestrates EFMI VB2 weight buffer packing using blendworks_baker.
    """
    print(f"      [VB2 PACKER] -> Packing weights for {obj.name} from {donor_obj.name}...")
    
    packed_data = blendworks_baker.pack_efmi_weights(obj, donor_obj, buf_xyz)
    
    if packed_data is not None:
        with open(output_path, "wb") as f:
            f.write(packed_data.tobytes())
        print(f"      [VB2 PACKER] -> Done: {os.path.basename(output_path)}")
        return True
    else:
        print(f"      [ERROR] VB2 Packer returned empty data for {obj.name}")
        return False

def _bake_weights_layer(context, base_name, comp_objects, mod_root, all_keys, original_bytes, stride, is_xxmi, dump_name="", comp_cache=None):
    if is_xxmi:
        print('Oups, this is XXMI game, currently weight SK export is not supported for XXMI games')
        return
    
    rzm = context.scene.rzm
    weight_keys = [c for c in active_weight_shape_configs(rzm) if c.shape_name in all_keys]
    
    if not weight_keys:
        return

    buf_v_count = len(original_bytes) // stride
    raw_np = np.frombuffer(original_bytes, dtype=np.uint8)
    float_view = raw_np.reshape(buf_v_count, stride).view(np.float32).reshape(buf_v_count, stride // 4)
    buf_xyz_base = float_view[:, :3].copy()
    
    if not is_xxmi:
        buf_xyz_base[:, 0] *= -1

    print(f"\n  [BLENDWORKS] Processing {len(weight_keys)} weight morph layers...")
    
    output_dir = os.path.join(mod_root, "SK")
    os.makedirs(output_dir, exist_ok=True)

    cache_objects = {entry['name']: entry for entry in comp_cache.get('objects', [])} if comp_cache else {}

    for config in weight_keys:
        sk_name = config.shape_name
        parent_name = config.parent_shape
        print(f"    [*] Layer: {sk_name}" + (f" (Parent: {parent_name})" if parent_name else ""))
        
        master_packed = np.zeros((buf_v_count, 12), dtype=np.uint8)
        
        parent_packed = None
        if parent_name:
            safe_parent_name = "_".join(parent_name.lstrip('$@#~').split())
            parent_path = os.path.join(output_dir, f"{base_name}_VB2_{safe_parent_name}.buf")
            if os.path.exists(parent_path):
                parent_packed = np.fromfile(parent_path, dtype=np.uint8).reshape(-1, 12)
                print(f"      [INFO] Loaded parent weights for subtraction: {safe_parent_name}")
        
        patterns_vb2 = [f"{base_name}Weights.buf", f"{base_name}_VB2.buf", f"{base_name}_VB2_LOD.buf"]
        base_vb2_path = None
        for sub in ["", "Meshes", "Buffers"]:
            for p in patterns_vb2:
                tp = os.path.join(mod_root, sub, p) if sub else os.path.join(mod_root, p)
                if os.path.exists(tp):
                    base_vb2_path = tp
                    break
            if base_vb2_path: break
        
        if base_vb2_path:
            with open(base_vb2_path, "rb") as f:
                master_packed = np.frombuffer(f.read(), dtype=np.uint8).reshape(buf_v_count, 12).copy()
        else:
            print(f"      [WARN] Base VB2 not found. Initializing with zeros.")

        # Resolve cumulative chain for this shape key
        def get_chain(cfg, all_cfgs, chain):
            chain.add(cfg.shape_name)
            if cfg.parent_shape:
                p = next((c for c in all_cfgs if c.shape_name == cfg.parent_shape), None)
                if p and p.shape_name not in chain:
                    get_chain(p, all_cfgs, chain)
        
        active_chain = set()
        get_chain(config, rzm.shape_configs, active_chain)

        layer_has_data = False

        for obj in comp_objects:
            dt_mod = None
            for m in obj.modifiers:
                if m.type == 'DATA_TRANSFER' and m.show_viewport:
                    has_vgroups = any(v in m.data_types_verts for v in {'VGROUP_WEIGHTS', 'VGROUP'})
                    if m.use_vert_data and has_vgroups:
                        dt_mod = m
                        break
            
            if not (dt_mod and dt_mod.object):
                if dt_mod:
                    print(f"      [WARN] Object '{obj.name}' has DataTransfer but no Source Object selected.")
                continue

            donor = dt_mod.object
            if _object_has_direct_shape_key(obj, sk_name):
                if not object_shape_key_is_exportable(obj, sk_name, include_modifier_targets=False):
                    continue
            elif not object_shape_key_is_exportable(donor, sk_name, include_modifier_targets=False):
                continue

            entry = cache_objects.get(obj.name)
            vb_off = entry.get('vb_offset', 0) if entry else 0
            vb_cnt = entry.get('vb_count', 0) if entry else 0
            if vb_cnt == 0:
                vb_cnt = buf_v_count
            v_map = entry.get('vertex_map') if entry else None

            # ── КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ──────────────────────────────────────
            # Сохраняем состояние и активируем ВСЮ цепочку на OBJ + DONOR
            sk_states_obj   = {}
            sk_states_donor = {}

            if obj.data and obj.data.shape_keys:
                for blk in obj.data.shape_keys.key_blocks:
                    sk_states_obj[blk.name] = blk.value
                    blk.value = 1.0 if blk.name in active_chain else 0.0

            if donor.data and donor.data.shape_keys:
                for blk in donor.data.shape_keys.key_blocks:
                    sk_states_donor[blk.name] = blk.value
                    blk.value = 1.0 if blk.name in active_chain else 0.0

            context.view_layer.update()
            depsgraph = context.evaluated_depsgraph_get()
            depsgraph.update()

            # Evaluate деформированного меша объекта для получения реальных координат
            eval_obj = obj.evaluated_get(depsgraph)
            eval_mesh = eval_obj.to_mesh()

            import mathutils as mu
            m_idx = entry.get('mat_idx', 0) if entry else 0
            if m_idx == 1:
                mat = obj.matrix_world
            elif m_idx == 2:
                root_obj_name = comp_cache.get('root_obj') if comp_cache else None
                root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else None
                mat = (root_obj.matrix_world.inverted() @ obj.matrix_world if root_obj else mu.Matrix.Identity(4))
            else:
                mat = obj.matrix_world if not is_xxmi else mu.Matrix.Identity(4)

            mw3 = np.array(mat.to_3x3(), dtype=np.float32)
            mwt = np.array(mat.translation, dtype=np.float32)

            n_eval = len(eval_mesh.vertices)
            raw_eval = np.empty(n_eval * 3, dtype=np.float32)
            eval_mesh.vertices.foreach_get('co', raw_eval)
            eval_co = raw_eval.reshape(-1, 3) @ mw3.T + mwt

            eval_obj.to_mesh_clear()

            # Строим v_map из deformed координат → буферные слоты
            if v_map and len(v_map) == vb_cnt:
                # Используем v_map: для каждого буферного слота берём координату из eval_co[v_map[i]]
                v_map_np = np.array(v_map, dtype=np.int32)
                valid_mask = v_map_np < n_eval
                obj_buf_xyz = np.zeros((vb_cnt, 3), dtype=np.float32)
                obj_buf_xyz[valid_mask] = eval_co[v_map_np[valid_mask]]
                print(f"      [INFO] {obj.name}: Using v_map for deformed coordinates ({vb_cnt} slots).")
            else:
                # Пространственный поиск: для каждого буферного слота ищем ближайший eval-вертекс
                kd = mu.kdtree.KDTree(n_eval)
                for i, co in enumerate(eval_co):
                    kd.insert(mu.Vector(co), i)
                kd.balance()

                obj_buf_xyz = np.empty((vb_cnt, 3), dtype=np.float32)
                for idx in range(vb_cnt):
                    buf_idx = vb_off + idx
                    buf_pos = mu.Vector(buf_xyz_base[buf_idx])
                    # Для EFMI инвертируем X при поиске
                    if not is_xxmi:
                        search_pos = mu.Vector((-buf_pos.x, buf_pos.y, buf_pos.z))
                    else:
                        search_pos = buf_pos
                    co, best_idx, dist = kd.find(search_pos)
                    obj_buf_xyz[idx] = eval_co[best_idx]
                print(f"      [INFO] {obj.name}: Used KD-Tree to map deformed positions ({vb_cnt} slots).")

            # Сэмплинг весов по деформированным координатам
            packed_slice = blendworks_baker.pack_efmi_weights(obj, donor, obj_buf_xyz)

            # Восстанавливаем состояние shape keys
            if sk_states_obj and obj.data and obj.data.shape_keys:
                for name, val in sk_states_obj.items():
                    if name in obj.data.shape_keys.key_blocks:
                        obj.data.shape_keys.key_blocks[name].value = val
            if sk_states_donor and donor.data and donor.data.shape_keys:
                for name, val in sk_states_donor.items():
                    if name in donor.data.shape_keys.key_blocks:
                        donor.data.shape_keys.key_blocks[name].value = val
            context.view_layer.update()
            # ── КОНЕЦ ИСПРАВЛЕНИЯ ─────────────────────────────────────────

            if packed_slice is not None:
                w_slice = packed_slice[:, :8].view(np.uint16).reshape(-1, 4)
                avg_w = np.mean(w_slice, axis=0) / 655.35
                print(f"      [DEBUG] {obj.name} Weights: {avg_w[0]:.1f}%, {avg_w[1]:.1f}%, {avg_w[2]:.1f}%, {avg_w[3]:.1f}%")
                master_packed[vb_off : vb_off + vb_cnt] = packed_slice
                layer_has_data = True

        if layer_has_data:
            safe_sk_name = "_".join(sk_name.lstrip('$@#~').split())
            out_name = f"{base_name}_VB2_{safe_sk_name}.buf"
            out_path = os.path.join(output_dir, out_name)

            if parent_packed is not None and len(parent_packed) == len(master_packed):
                curr_w = master_packed[:, :8].view(np.uint16).reshape(-1, 4).astype(np.int32)
                prev_w = parent_packed[:, :8].view(np.uint16).reshape(-1, 4).astype(np.int32)
                curr_idx = master_packed[:, 8:]
                prev_idx = parent_packed[:, 8:]
                if np.array_equal(curr_idx, prev_idx):
                    master_packed[:, :8].view(np.uint16).reshape(-1, 4)[:] = np.clip(curr_w - prev_w, 0, 65535).astype(np.uint16)
            
            with open(out_path, "wb") as f:
                f.write(master_packed.tobytes())
            print(f"      [VB2 PACKER] -> Done: {out_name}")


# ---------------------------------------------------------------------------
# CORE BAKE — оркестратор
# ---------------------------------------------------------------------------

def bake_component_shapes(context, base_name, comp_objects, mod_root, limit,
                           single_shape_name=None, full_export_mode=False,
                           orient_mat=None, mirror_enabled=None):
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

    # [NEW] Hash-based fallback: look for the hash in mod.ini ifpretty name failed
    if not vb0_path:
        ini_path = os.path.join(mod_root, "mod.ini")
        if os.path.exists(ini_path):
            with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Look for ComponentX section and VB0 hash
                match_sec = re.search(rf"\[\s*Resource{base_name}VB0\s*\]", content, re.I)
                if match_sec:
                    match_hash = re.search(r"filename\s*=\s*([a-fA-F0-9]+)\.buf", content[match_sec.end():match_sec.end()+200], re.I)
                    if match_hash:
                        hash_name = f"{match_hash.group(1)}.buf"
                        for sub in subfolders:
                            test_path = os.path.join(mod_root, sub, hash_name) if sub else os.path.join(mod_root, hash_name)
                            if os.path.exists(test_path):
                                vb0_path = test_path
                                print(f"    [INFO] Found {base_name} VB0 via hash: {hash_name}")
                                break

    try:
        from .export_cache import component_cache
        comp_cache = component_cache(base_name)
    except Exception:
        comp_cache = None

    rzm      = context.scene.rzm
    prepare_shape_config_export_runtime(rzm)
    active_configs = active_shape_configs(rzm)
    affected_names = _component_affected_names(base_name, comp_cache, dump_name, is_xxmi)
    all_keys = _component_shape_key_names(
        active_configs,
        affected_names,
        single_shape_name=single_shape_name,
    )

    if not all_keys:
        return True

    # Now if we REALLY need a buffer but don't have it, then error
    if not vb0_path:
        print(f"  [ERROR] Position buffer not found for {base_name}. Skipping component.")
        return False

    output_dir = os.path.join(mod_root, "SK")
    os.makedirs(output_dir, exist_ok=True)

    with open(vb0_path, "rb") as f:
        original_bytes = f.read()
    original_data = bytearray(original_bytes)

    stride = 40 if is_xxmi else 16 if game in {'ArknightsEndfield', 'WutheringWaves'} else 32

    # Создаем заглушки-буферы
    _write_noop_shape_buffers(output_dir, base_name, all_keys, is_xxmi, dump_name, original_bytes)

    sk_owner_map = _scan_sk_owners(comp_objects, all_keys)

    # [NEW] Check for weight morphs too
    weight_keys = [c for c in active_weight_shape_configs(rzm) if c.shape_name in all_keys]

    if not sk_owner_map and not weight_keys:
        _validate_shape_buffer_sizes(
            output_dir,
            base_name,
            all_keys,
            is_xxmi,
            dump_name,
            len(original_bytes),
        )
        return True

    buf_v_count = len(original_data) // stride
    if comp_cache:
        stride = comp_cache.get('stride', stride)
        buf_v_count = len(original_data) // stride

    if not sk_owner_map:
        _bake_weights_layer(
            context,
            base_name,
            comp_objects,
            mod_root,
            all_keys,
            original_bytes,
            stride,
            is_xxmi,
            dump_name=dump_name,
            comp_cache=comp_cache,
        )
        _validate_shape_buffer_sizes(
            output_dir,
            base_name,
            all_keys,
            is_xxmi,
            dump_name,
            len(original_bytes),
        )
        return True

    # ── 1. ФАЗА ПОДГОТОВКИ (Pre-Processing) ────────────────────────────────
    ready_map = {}
    temp_objects = []
    
    orig_active = context.view_layer.objects.active
    orig_selected = context.selected_objects.copy()

    try:
        # Умная сортировка: объекты-доноры (цели для SurfaceDeform) обрабатываются ПЕРВЫМИ,
        # чтобы перенос шейпкеев происходил с уже запеченных плотных мешей (как при ручной работе).
        def get_sd_target(o):
            for m in o.modifiers:
                if m.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and m.show_viewport and m.target:
                    return m.target
            return None
            
        comp_objects_sorted = sorted(list(comp_objects), key=lambda o: 1 if get_sd_target(o) else 0)

        for obj in comp_objects_sorted:
            needs_sd = False
            sd_target = None
            sd_mod = None
            keys_to_transfer = []

            for mod in obj.modifiers:
                if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                    tgt = mod.target
                    if tgt.data and tgt.data.shape_keys:
                        for sk_name in all_keys:
                            target_key = tgt.data.shape_keys.key_blocks.get(sk_name)
                            if shape_key_block_is_exportable(target_key):
                                if not obj.data or not obj.data.shape_keys or sk_name not in obj.data.shape_keys.key_blocks:
                                    keys_to_transfer.append(sk_name)
                    if keys_to_transfer:
                        needs_sd = True
                        sd_target = tgt
                        sd_mod = mod
                    break

            needs_mod_bake = has_active_modifiers(obj)

            has_direct_keys = False
            if obj.data and obj.data.shape_keys:
                for sk_name in all_keys:
                    if object_shape_key_is_exportable(obj, sk_name, include_modifier_targets=False):
                        has_direct_keys = True
                        break

            if not has_direct_keys and not needs_sd:
                continue

            if not needs_sd and not needs_mod_bake:
                ready_map[obj] = obj
                continue

            # --- Создаем временный объект ---
            bpy.ops.object.select_all(action='DESELECT')
            temp_obj = obj.copy()
            temp_obj.data = obj.data.copy()
            context.collection.objects.link(temp_obj)
            temp_obj.select_set(True)
            context.view_layer.objects.active = temp_obj
            temp_objects.append(temp_obj)

            set_armature_visibility([temp_obj], False)
            bake_success = True

            # ЭТАП 2: Запекание модификаторов (Двойной Try-Except)
            if needs_mod_bake:
                print(f"  [MOD BAKE] Attempt A: Baking modifiers for {obj.name}...")
                try:
                    # Попытка А: Запекаем всё (включая Surface Deform, если он есть)
                    bpy.ops.rz.shape_key_apply_modifiers()
                except Exception:
                    # Фоллбек (Попытка Б): Если А упала, пробуем удалить SD и запечь остальное
                    if needs_sd and temp_obj.modifiers.get(sd_mod.name):
                        print(f"  [MOD BAKE] Attempt A failed, trying Attempt B (removing Surface Deform)...")
                        temp_obj.modifiers.remove(temp_obj.modifiers.get(sd_mod.name))
                        try:
                            bpy.ops.rz.shape_key_apply_modifiers()
                        except Exception as e2:
                            print(f"  [ERROR] Mod bake failed (Attempt B) for {obj.name}: {e2}")
                            bake_success = False
                    else:
                        print(f"  [ERROR] Mod bake failed (Attempt A) for {obj.name}")
                        bake_success = False

                # Обновляем ссылку на temp_obj, так как оператор мог заменить объект
                temp_obj = context.view_layer.objects.active
                if temp_obj not in temp_objects:
                    temp_objects.append(temp_obj)

            # ЭТАП 3: Перенос Shape Keys (Берем донора из ready_map, чтобы использовать его хай-поли версию)
            if bake_success and needs_sd:
                try:
                    actual_donor = ready_map.get(sd_target, sd_target)
                    from .rzm_surface_baker import transfer_surface_shape_keys
                    print(f"  [SURFACE BAKE] Transferring {len(keys_to_transfer)} keys from {actual_donor.name} to {obj.name}")
                    transfer_surface_shape_keys(temp_obj, actual_donor, keys_to_transfer)
                except Exception as e:
                    print(f"  [ERROR] Surface bake failed for {obj.name}: {e}")
                    bake_success = False

            set_armature_visibility([temp_obj], True)
            
            if bake_success:
                ready_map[obj] = temp_obj

        # ── 2. EXACT MATCH PATH (Выгрузка) ─────────────────────────────────────
        fast_path_slots, stats_exact, failed_exact = _process_exact_matches(
            context, sk_owner_map, ready_map, comp_cache,
            original_bytes, stride, buf_v_count,
            output_dir, base_name, dump_name, is_xxmi, game_name=game,
            orient_mat=orient_mat, mirror_enabled=mirror_enabled
        )

        # ── 3. SLOW PATH (Fallback) ────────────────────────────────────────────
        sk_owner_map_slow = {sk: owners for sk, owners in failed_exact.items() if owners['direct'] or owners['via_target']}
        stats_slow = 0

        if sk_owner_map_slow:
            print(f"  [SLOW PATH] Spatial Barycentric Fallback")
            stats_slow = _run_slow_path(
                context, sk_owner_map_slow, comp_cache,
                original_bytes, stride, buf_v_count,
                output_dir, base_name, dump_name, is_xxmi, limit, t_start,
                game_name=game, fast_path_slots=fast_path_slots,
                orient_mat=orient_mat, mirror_enabled=mirror_enabled
            )

        # ── 4. BLENDWORKS (Weights) ────────────────────────────────────────────
        # [NEW] Проверка и запуск слоя весов
        _bake_weights_layer(context, base_name, comp_objects, mod_root, all_keys, original_bytes, stride, is_xxmi, dump_name=dump_name, comp_cache=comp_cache)
        _validate_shape_buffer_sizes(output_dir, base_name, all_keys, is_xxmi, dump_name, len(original_bytes))

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
        
        from .export_cache import get_cache
        cache = get_cache() or {}
        game  = context.scene.rzm.game.name
        is_xxmi = game in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}

        # Resolve Mod Name for XXMI anchor search
        mod_name = ""
        if is_xxmi:
            dump_path_prop = context.scene.xxmi.dump_path if hasattr(context.scene, "xxmi") else ""
            if dump_path_prop:
                dp = os.path.normpath(bpy.path.abspath(dump_path_prop))
                mod_dir = os.path.dirname(dp) if dp.lower().endswith("hash.json") else dp
                mod_name = os.path.basename(mod_dir)

        for base_name, objs in components.items():
            # Get component metadata for classifications
            comp_cache = cache.get('components', {}).get(base_name, {})
            classifications = []
            if is_xxmi and comp_cache:
                obj_names = [o.get('name') for o in comp_cache.get('objects', [])]
                pass

            # [REWORK] Resolve dynamic orientation and mirror per component
            orient_mat, mirror_enabled = _resolve_component_transform(
                context, is_xxmi, game, mod_name, base_name, classifications
            )

            bake_component_shapes(context, base_name, objs, mod_root, limit,
                                   full_export_mode=self.full_export_mode,
                                   orient_mat=orient_mat, mirror_enabled=mirror_enabled)
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
        
        from .export_cache import get_cache
        cache = get_cache() or {}
        game  = context.scene.rzm.game.name
        is_xxmi = game in {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}

        # Resolve Mod Name for XXMI anchor search
        mod_name = ""
        if is_xxmi:
            dump_path_prop = context.scene.xxmi.dump_path if hasattr(context.scene, "xxmi") else ""
            if dump_path_prop:
                dp = os.path.normpath(bpy.path.abspath(dump_path_prop))
                mod_dir = os.path.dirname(dp) if dp.lower().endswith("hash.json") else dp
                mod_name = os.path.basename(mod_dir)

        for base_name, objs in components.items():
            # Get component metadata for classifications
            comp_cache = cache.get('components', {}).get(base_name, {})
            classifications = []
            if is_xxmi and comp_cache:
                # obj_names = [o.get('name') for o in comp_cache.get('objects', [])]
                pass

            # [REWORK] Resolve dynamic orientation and mirror per component
            orient_mat, mirror_enabled = _resolve_component_transform(
                context, is_xxmi, game, mod_name, base_name, classifications
            )

            bake_component_shapes(context, base_name, objs, mod_root, limit,
                                   single_shape_name=target_shape,
                                   orient_mat=orient_mat, mirror_enabled=mirror_enabled)
        return {'FINISHED'}

classes_to_register = [RZM_OT_PuppetMasterBake, RZM_OT_PuppetMasterBakeSingle]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
