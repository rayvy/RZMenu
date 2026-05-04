# RZMenu/operators/puppet_master_ops.py
#
# Hybrid Pipeline — три уровня экспорта:
#   1. FAST PATH   — прямой топологический маппинг из кэша (EFMI/XXMI).
#                    Идеально для простых мешей без генеративных модификаторов.
#   2. BAKED PATH  — для объектов с Mirror/Subdiv/Array и т.п.:
#                    Вычисляет координаты через Depsgraph, избегая физического
#                    применения модификаторов и бага с Mirror+Subdiv. Ищет точные 
#                    соответствия через KD-Tree.
#   3. SLOW PATH   — пространственная интерполяция для объектов без кэша или
#                    для via_target (Surface Deform). Используется BVH + барицентрика.
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

# ---------------------------------------------------------------------------
# GENERATIVE MODIFIER DETECTION
# ---------------------------------------------------------------------------

GENERATIVE_MODS = {
    'ARRAY', 'BEVEL', 'BOOLEAN', 'BUILD', 'DECIMATE', 'EDGE_SPLIT',
    'GEOMETRY_NODES', 'MASK', 'MESH_TO_VOLUME', 'MIRROR', 'MULTIRES',
    'REMESH', 'SCREW', 'SKIN', 'SOLIDIFY', 'SUBSURF', 'TRIANGULATE',
    'VOLUME_TO_MESH', 'WELD', 'WIREFRAME', 'CLOTH', 'COLLISION',
    'DYNAMIC_PAINT', 'EXPLODE', 'FLUID', 'OCEAN',
    'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SOFT_BODY',
}

def _get_active_generative_mods(obj):
    """Возвращает список имён активных генеративных модификаторов объекта."""
    return [m.name for m in obj.modifiers
            if m.show_viewport and m.type in GENERATIVE_MODS]

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
        direct, via_target = [], []
        for obj in comp_objects:
            if obj.data and obj.data.shape_keys:
                sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
                if sk_blk is not None:
                    ba_blk = obj.data.shape_keys.reference_key
                    if sk_blk.data and ba_blk.data:
                        sk_co = np.array([kp.co for kp in sk_blk.data], dtype=np.float32)
                        ba_co = np.array([kp.co for kp in ba_blk.data], dtype=np.float32)
                        if np.any(np.abs(sk_co - ba_co) > 1e-7):
                            direct.append(obj)
                            continue
            # Проверяем Surface Deform / Shrinkwrap
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

# ---------------------------------------------------------------------------
# FAST PATH — прямой маппинг из кэша
# ---------------------------------------------------------------------------

def _bake_with_direct_offsets(sk_owner_map, comp_cache, original_bytes,
                               stride, buf_v_count, output_dir,
                               base_name, dump_name, is_xxmi):
    """
    Universal Fast Path: extracts shape key deltas and applies them via the
    topology-bridge cache map.

    Two delta-extraction modes, chosen per-object automatically:

    ── ORIG mode (fastest) ───────────────────────────────────────────────────
    Used when max(v_map) < orig_v_count, i.e. v_map indices all fall within
    the original (pre-modifier) mesh.  Reads shape key data directly from
    obj.data.shape_keys — zero depsgraph calls, near-instant.

    ── EVAL mode (universal) ─────────────────────────────────────────────────
    Used when max(v_map) >= orig_v_count, i.e. a modifier (Mirror+Merge,
    Subdiv, GeoNodes, any third-party addon...) generated extra geometry.
    Sets SK value to 1.0, evaluates mesh via depsgraph, computes delta in
    eval space.  Works for ANY modifier stack — no special-casing needed.
    Two depsgraph evaluations per (object × shape_key) pair.

    Routing:
      vertex_map present  → Fast Path (orig or eval)
      vertex_map None     → Baked Path (KD spatial, caller handles)
      Surface Deform      → Slow Path (caller handles)
    """
    import mathutils
    stride_f32    = stride // 4
    cache_objects = {entry['name']: entry for entry in comp_cache.get('objects', [])}
    depsgraph     = bpy.context.evaluated_depsgraph_get()

    fallback_objs_per_sk: dict = {}
    fast_path_slots_per_sk: dict = {}  # {sk_name: bool[buf_v_count]} slots written by Fast Path

    for sk_name in list(sk_owner_map.keys()):
        buf_f32       = np.frombuffer(bytes(original_bytes), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
        matched_count = 0
        fallback_this = []
        map_type      = "Relative"
        sk_fast_slots = np.zeros(buf_v_count, dtype=bool)  # track which slots Fast Path writes

        for obj in sk_owner_map[sk_name]['direct']:
            entry = cache_objects.get(obj.name)
            if entry is None:
                fallback_this.append(obj)
                continue

            if not (obj.data and obj.data.shape_keys):
                continue
            sk_blk = obj.data.shape_keys.key_blocks.get(sk_name)
            ba_blk = obj.data.shape_keys.reference_key
            if not sk_blk or not ba_blk:
                continue

            is_absolute  = entry.get('is_absolute', False)
            vb_off   = 0 if is_absolute else entry['vb_offset']
            vb_cnt   = entry['vb_count']
            v_map    = entry.get('vertex_map')
            m_idx    = entry.get('mat_idx', 0)
            map_type = "Absolute" if is_absolute else "Relative"

            # No topology map → Baked Path
            if v_map is None or len(v_map) != vb_cnt:
                map_len = len(v_map) if v_map else 0
                print(f"    [WARN] {obj.name}: no valid map (map={map_len}, buf={vb_cnt}) → Baked Path.")
                fallback_this.append(obj)
                continue

            orig_v_count = len(obj.data.vertices)
            eval_v_count = entry.get('eval_v_count', orig_v_count)
            has_real_id  = entry.get('has_real_id', True)

            # ── Matrix (coordinate space) ──────────────────────────────────
            mat = mathutils.Matrix.Identity(4)
            if m_idx == 1:
                mat = obj.matrix_world
            elif m_idx == 2:
                root_obj_name = comp_cache.get('root_obj')
                root_obj = bpy.data.objects.get(root_obj_name) if root_obj_name else None
                mat = (root_obj.matrix_world.inverted() @ obj.matrix_world
                       if root_obj else mathutils.Matrix.Identity(4))

            v_map_np = np.array(v_map, dtype=np.int32)

            # ── Route: ORIG vs EVAL ────────────────────────────────────────
            # ORIG: .id is real OR eval_v == orig_v (plain/applied mesh).
            #       v_map[i] is within orig SK data range → read directly.
            # EVAL: .id is synthetic AND modifier expanded the mesh (Mirror, Subdiv).
            #       v_map[i] are eval indices; depsgraph eval at SK=0 and SK=1.
            #       KDTree uses EVAL positions → no left/right ambiguity.
            use_eval_path = (not has_real_id and eval_v_count > orig_v_count)

            if not use_eval_path:
                # ── ORIG mode ─────────────────────────────────────────────
                sk_co = np.empty(orig_v_count * 3, dtype=np.float32)
                ba_co = np.empty(orig_v_count * 3, dtype=np.float32)
                sk_blk.data.foreach_get('co', sk_co)
                ba_blk.data.foreach_get('co', ba_co)
                sk_co = sk_co.reshape(-1, 3)
                ba_co = ba_co.reshape(-1, 3)
                mat_rot    = np.array(mat.to_3x3(), dtype=np.float32)
                deltas_all = ((sk_co - ba_co) @ mat_rot.T).astype(np.float32)
                if not is_xxmi:
                    deltas_all[:, 0] *= -1
                mode_label = "orig"

            else:
                # ── EVAL mode — position KDTree ────────────────────────────
                sk_snapshot = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}
                try:
                    mat_w   = obj.matrix_world
                    mw3     = np.array(mat_w.to_3x3(), dtype=np.float32)
                    mwt     = np.array(mat_w.translation, dtype=np.float32)

                    # Basis eval
                    for sk in obj.data.shape_keys.key_blocks: sk.value = 0.0
                    bpy.context.view_layer.update(); depsgraph.update()
                    em_base = obj.evaluated_get(depsgraph).to_mesh()
                    bv = len(em_base.vertices)
                    ba_loc = np.empty(bv * 3, dtype=np.float32)
                    em_base.vertices.foreach_get('co', ba_loc)
                    ba_loc = ba_loc.reshape(-1, 3)
                    
                    has_id_base = 'id' in em_base.attributes
                    if has_id_base:
                        ba_ids = np.empty(bv, dtype=np.int32)
                        em_base.attributes['id'].data.foreach_get('value', ba_ids)
                        
                    obj.evaluated_get(depsgraph).to_mesh_clear()
                    ba_world = ba_loc @ mw3.T + mwt

                    # SK=1 eval (use microscopic weight to prevent topology destruction by modifiers)
                    sk_weight = 0.001
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = sk_weight if sk.name == sk_name else 0.0
                    bpy.context.view_layer.update(); depsgraph.update()
                    em_sk = obj.evaluated_get(depsgraph).to_mesh()
                    sv = len(em_sk.vertices)
                    sk_loc = np.empty(sv * 3, dtype=np.float32)
                    em_sk.vertices.foreach_get('co', sk_loc)
                    sk_loc = sk_loc.reshape(-1, 3)
                    
                    has_id_sk = 'id' in em_sk.attributes
                    if has_id_sk:
                        sk_ids = np.empty(sv, dtype=np.int32)
                        em_sk.attributes['id'].data.foreach_get('value', sk_ids)
                        
                    obj.evaluated_get(depsgraph).to_mesh_clear()
                    sk_world = sk_loc @ mw3.T + mwt

                    # Delta per eval vertex.
                    # If vertex counts match, Blender's eval mesh order is exactly stable.
                    # We MUST use direct subtraction. KDTree can pick wrong neighbors for large deltas!
                    if sv == bv:
                        mode_label = "eval_direct"
                        deltas_eval = ((sk_world - ba_world) / sk_weight).astype(np.float32)
                    else:
                        mode_label = "eval_kd"
                        print(f"    [WARN] {obj.name}: Topology shifted (sv={sv} != bv={bv}), matching by ID...")
                        deltas_eval = np.zeros((bv, 3), dtype=np.float32)
                        
                        has_id = has_id_base and has_id_sk
                        if has_id:
                            sk_id_map = {}
                            for ki in range(sv):
                                vid = sk_ids[ki]
                                if vid not in sk_id_map: sk_id_map[vid] = []
                                sk_id_map[vid].append((ki, sk_world[ki]))
                                
                            for bi in range(bv):
                                vid = ba_ids[bi]
                                b_pos = ba_world[bi]
                                candidates = sk_id_map.get(vid, [])
                                
                                if not candidates: continue
                                
                                if len(candidates) == 1:
                                    best_ki = candidates[0][0]
                                else:
                                    # Safe proximity: only compares among identical orig vertices (Left vs Right)
                                    best_dist = float('inf')
                                    best_ki = candidates[0][0]
                                    for ki, k_pos in candidates:
                                        dist = np.sum((k_pos - b_pos)**2)
                                        if dist < best_dist:
                                            best_dist = dist
                                            best_ki = ki
                                            
                                deltas_eval[bi] = (sk_world[best_ki] - b_pos) / sk_weight
                        else:
                            import mathutils as _mu
                            kd = _mu.kdtree.KDTree(sv)
                            for ki, kp in enumerate(sk_world): kd.insert(_mu.Vector(kp), ki)
                            kd.balance()
                            for bi in range(bv):
                                _, ki, _ = kd.find(_mu.Vector(ba_world[bi]))
                                deltas_eval[bi] = (sk_world[ki] - ba_world[bi]) / sk_weight

                    # deltas_eval[i] = world-space delta for eval vertex i.
                    # v_map_np[slot] = eval vertex index → indexes deltas_eval.
                    deltas_all = deltas_eval

                    if not is_xxmi:
                        deltas_all[:, 0] *= -1

                finally:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = sk_snapshot.get(sk.name, 0.0)
                    bpy.context.view_layer.update(); depsgraph.update()

            # ── Guard 1: buffer bounds ─────────────────────────────────────
            # vb_off+vb_cnt can exceed buf_v_count when export_cache accumulates
            # actual_vb_count (topological dedup) instead of EFMI's internal counts.
            if vb_off + vb_cnt > buf_v_count:
                print(f"    [ERROR] {obj.name}: offset OOB "
                      f"(vb_off={vb_off}+vb_cnt={vb_cnt}={vb_off+vb_cnt} > buf={buf_v_count}) "
                      f"→ Baked Path.")
                fallback_this.append(obj)
                continue

            # ── Guard 2: v_map index bounds ────────────────────────────────
            max_idx = int(v_map_np.max()) if len(v_map_np) > 0 else 0
            if max_idx >= len(deltas_all):
                print(f"    [ERROR] {obj.name}: v_map max index {max_idx} >= "
                      f"deltas size {len(deltas_all)} → Baked Path.")
                fallback_this.append(obj)
                continue

            # ── Apply: buf[vb_off + i] += deltas[v_map[i]] ────────────────
            obj_slice = buf_f32[vb_off: vb_off + vb_cnt, :3]
            buf_f32[vb_off: vb_off + vb_cnt, :3] = (obj_slice + deltas_all[v_map_np]).astype(np.float32)
            obj_matched = vb_cnt
            sk_fast_slots[vb_off: vb_off + vb_cnt] = True  # mark these slots as done

            matched_count += obj_matched
            print(f"    [FAST/{mode_label.upper()}] {obj.name}: {obj_matched} slots for '{sk_name}'.")

        out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
        if matched_count > 0:
            with open(os.path.join(output_dir, out_name), 'wb') as f:
                f.write(buf_f32.tobytes())
            print(f"    -> [DONE] {out_name} ({matched_count} verts via Fast Path [{map_type}])")

        fallback_objs_per_sk[sk_name] = fallback_this
        fast_path_slots_per_sk[sk_name] = sk_fast_slots

    return fallback_objs_per_sk, fast_path_slots_per_sk


# ---------------------------------------------------------------------------
# BAKED PATH — вычисление дельт через Depsgraph (Mirror + Subdiv safe)
# ---------------------------------------------------------------------------

def _bake_path_for_generative_objects(
        context, sk_owner_map_bake, comp_cache,
        original_bytes, stride, buf_v_count,
        output_dir, base_name, dump_name, is_xxmi):
    """
    Baked Path (Spatial Fallback) — поиск соответствий через KD-Tree.
    Используется для объектов с модификаторами или если нет топологического кэша.
    """
    import mathutils as mu
    
    stride_f32 = stride // 4
    remaining_for_slow = {}
    depsgraph = context.evaluated_depsgraph_get()

    # Cache lookup for boundaries
    cache_objects = {e['name']: e for e in comp_cache.get('objects', [])} if comp_cache else {}

    # Собираем все уникальные объекты, чтобы отключить у них арматуру
    all_bake_objs = set(obj for owners in sk_owner_map_bake.values() for obj in owners if obj)
    set_armature_visibility(all_bake_objs, False)

    try:
        for obj_name_key in set(obj.name for obj in all_bake_objs):
            obj = bpy.data.objects.get(obj_name_key)
            if not obj or not obj.data or not obj.data.shape_keys: continue

            gen_mods = _get_active_generative_mods(obj)
            
            # Даже если нет генеративных модов, мы используем этот путь как точный пространственный поиск
            # для объектов без кэша (вместо Slow Path).
            if gen_mods:
                print(f"  [BAKED] Processing {obj.name} via Depsgraph (Mods: {', '.join(gen_mods[:3])})")
            else:
                print(f"  [BAKED] Processing {obj.name} via Spatial Vertex Match (No mods, No cache)")

            # Сохраняем исходное состояние шейпкеев
            sk_snapshot = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}

            # 1. Получаем БАЗОВЫЙ сгенерированный меш (все shape keys = 0.0)
            for sk in obj.data.shape_keys.key_blocks:
                sk.value = 0.0
            context.view_layer.update()
            depsgraph.update()

            eval_base = obj.evaluated_get(depsgraph)
            mesh_base = eval_base.to_mesh()
            base_v_count = len(mesh_base.vertices)
            mat_world = obj.matrix_world

            # Конвертируем вершины в World Space
            base_coords_world = np.array([mat_world @ v.co for v in mesh_base.vertices], dtype=np.float32)
            eval_base.to_mesh_clear()

            # Строим KD-Tree для точного поиска
            baked_kd = mu.kdtree.KDTree(base_v_count)
            for i, co in enumerate(base_coords_world):
                baked_kd.insert(Vector(co), i)
            baked_kd.balance()

            # 2. Обрабатываем каждый шейпкей, который принадлежит этому объекту
            for sk_name, owners in sk_owner_map_bake.items():
                if obj not in owners: continue

                if sk_name not in obj.data.shape_keys.key_blocks:
                    remaining_for_slow.setdefault(sk_name, []).append(obj)
                    continue

                # Включаем ТОЛЬКО текущий шейпкей (use microscopic weight to prevent topology destruction)
                sk_weight = 0.001
                for sk in obj.data.shape_keys.key_blocks:
                    sk.value = sk_weight if sk.name == sk_name else 0.0
                context.view_layer.update()
                depsgraph.update()

                eval_sk = obj.evaluated_get(depsgraph)
                mesh_sk = eval_sk.to_mesh()

                # Если топология изменилась (Mirror Merge break), уходим в Slow Path.
                if len(mesh_sk.vertices) != base_v_count:
                    print(f"    [WARN] Topology shifted on {obj.name} for SK '{sk_name}' (Merge break). Fallback -> Slow Path.")
                    eval_sk.to_mesh_clear()
                    remaining_for_slow.setdefault(sk_name, []).append(obj)
                    continue

                sk_coords_world = np.array([mat_world @ v.co for v in mesh_sk.vertices], dtype=np.float32)
                eval_sk.to_mesh_clear()

                # Вычисляем дельты
                deltas_world = (sk_coords_world - base_coords_world) / sk_weight

                # Запись в буфер
                out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
                out_path = os.path.join(output_dir, out_name)
                
                if os.path.exists(out_path):
                    with open(out_path, 'rb') as f:
                        buf_f32 = np.frombuffer(f.read(), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()
                else:
                    buf_f32 = np.frombuffer(bytes(original_bytes), dtype=np.float32).reshape(buf_v_count, stride_f32).copy()

                buf_xyz = buf_f32[:, :3].copy()
                
                # --- PER-OBJECT ISOLATION (LIMITER) ---
                entry = cache_objects.get(obj.name)
                vb_off = entry.get('vb_offset', 0) if entry else 0
                vb_cnt = entry.get('vb_count', buf_v_count) if entry else buf_v_count
                
                matched_count = 0
                DIST_THRESHOLD = 0.02

                for buf_idx in range(vb_off, vb_off + vb_cnt):
                    buf_pos = Vector(buf_xyz[buf_idx])
                    _, baked_v_idx, dist = baked_kd.find(buf_pos)
                    if dist > DIST_THRESHOLD: continue
                    
                    d = deltas_world[baked_v_idx]
                    if np.linalg.norm(d) < 1e-7: continue
                    
                    buf_f32[buf_idx, 0] += d[0]
                    buf_f32[buf_idx, 1] += d[1]
                    buf_f32[buf_idx, 2] += d[2]
                    matched_count += 1

                if matched_count > 0:
                    with open(out_path, 'wb') as f:
                        f.write(buf_f32.tobytes())
                    print(f"    [BAKED] {obj.name}: {matched_count} verts matched for '{sk_name}'")
                else:
                    print(f"    [WARN] {obj.name}: 0 matched verts for '{sk_name}' via Baked Path. Fallback -> Slow Path.")
                    remaining_for_slow.setdefault(sk_name, []).append(obj)

            # Восстанавливаем оригинальные значения шейпкеев
            for sk in obj.data.shape_keys.key_blocks:
                if sk.name in sk_snapshot:
                    sk.value = sk_snapshot[sk.name]
            context.view_layer.update()
            depsgraph.update()

    finally:
        set_armature_visibility(all_bake_objs, True)

    return remaining_for_slow

# ---------------------------------------------------------------------------
# BARYCENTRIC DELTA INTERPOLATION (Slow Path)
# ---------------------------------------------------------------------------

def _barycentric_coords(p, a, b, c):
    """Барицентрические координаты точки p в треугольнике (a, b, c)."""
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
        return 1.0/3, 1.0/3, 1.0/3  # вырожденный треугольник
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    return u, v, w

def _bary_delta_batch_bvh(buf_verts_np, owner_data, target_data):
    """
    Барицентрическая интерполяция дельт через BVH.
    Для каждой вершины буфера:
      1. Ищем ближайший треугольник в меше владельца.
      2. Вычисляем барицентрические координаты.
      3. Интерполируем дельту по этим весам.
    Значительно точнее IDW на центроидах: нет «шума» и «спайков».
    """
    base_coords = owner_data['coords']   # (N, 3) float64
    deltas      = target_data - base_coords  # (N, 3)
    tri_verts   = owner_data['tri_verts']    # (T, 3) int32
    bvh         = owner_data['bvh']

    out = np.zeros_like(buf_verts_np)

    if bvh is not None:
        for i, bv in enumerate(buf_verts_np):
            mv = Vector(bv)
            loc, norm, face_idx, dist = bvh.find_nearest(mv)
            if face_idx is None:
                # Резервный IDW по 3 ближайшим вершинам
                dists_sq = ((base_coords - bv) ** 2).sum(axis=1) + 1e-10
                w = 1.0 / dists_sq
                w /= w.sum()
                out[i] = (w[:, None] * deltas).sum(axis=0)
                continue
            ia, ib, ic = tri_verts[face_idx]
            a = base_coords[ia]; b = base_coords[ib]; c = base_coords[ic]
            wu, wv, ww = _barycentric_coords(np.array(bv), a, b, c)
            # Клэмпируем веса: если точка за пределами треугольника — просто IDW
            total = abs(wu) + abs(wv) + abs(ww)
            if total < 1e-9:
                wu, wv, ww = 1.0/3, 1.0/3, 1.0/3
            else:
                wu, wv, ww = wu/total, wv/total, ww/total
            out[i] = wu * deltas[ia] + wv * deltas[ib] + ww * deltas[ic]
    else:
        # Без BVH — IDW по вершинам (резервный вариант)
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
    """Строит структуру данных объекта для Slow Path (BVH + координаты).
    
    mat — матрица преобразования координат (обычно obj.matrix_world для EFMI,
    так как EFMI применяет transform_apply → буфер в мировых координатах).
    """
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

    # Строим BVH из треугольников для точного поиска
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
    """Назначаем каждой вершине буфера ближайший объект через BVH."""
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
    """Slow Path: пространственный поиск + барицентрическая интерполяция."""

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

    # Snapshot шейпкеев
    sk_snapshot = {}
    for obj in all_involved:
        if obj.data and obj.data.shape_keys:
            sk_snapshot[obj] = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}

    set_armature_visibility(all_involved, False)

    # Для Mirror: НЕ отключаем Merge/Clip — объект уже in Slow Path только если
    # у него нет кэша, значит буфер содержит полный (зеркальный) меш.
    # Отключение Merge/Clip здесь только навредит (половина вершин пропадёт).
    # Мы НЕ трогаем mirror_states в Slow Path.

    try:
        # Сбрасываем все шейпкеи в 0
        for a_obj in all_involved:
            if a_obj.data and a_obj.data.shape_keys:
                for sk in a_obj.data.shape_keys.key_blocks:
                    sk.value = 0.0
        context.view_layer.update()
        depsgraph.update()

        # Строим базовый кэш объектов
        # EFMI применяет transform_apply → позиции буфера в мировых координатах.
        # Для корректного BVH-матчинга используем matrix_world для всех EFMI объектов.
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
                # EFMI: transform_apply bakes world transform → buf positions == world space.
                mat = obj.matrix_world
            else:
                mat = mu.Matrix.Identity(4)

            base_cache[obj] = _build_owner_data(obj, depsgraph, mat)

        # Назначаем владельцев вершинам буфера
        owner_map, dist_map = _assign_owners_bulk_bvh(buf_xyz, base_cache, limit)

        for sk_name, owners in sk_owner_map_slow.items():
            sk_direct     = owners['direct']
            sk_via_target = owners['via_target']

            # Build a per-sk owner_map that excludes slots already written by Fast Path.
            # This prevents Slow Path from overwriting correct Fast Path deltas with
            # approximated barycentric ones.
            fp_slots = fast_path_slots.get(sk_name) if fast_path_slots else None
            if fp_slots is not None and fp_slots.any():
                effective_owner_map = owner_map.copy()
                effective_owner_map[fp_slots] = 0  # 0 = unowned → Slow Path skips these
                n_protected = int(fp_slots.sum())
                print(f"    [SLOW] '{sk_name}': protecting {n_protected} Fast Path slots from overwrite")
            else:
                effective_owner_map = owner_map

            # Активируем шейпкей.
            # sk_weight=0.05: достаточно большой для точной линейной экстраполяции
            # через Surface Deform, достаточно маленький чтобы не ломать Mirror+Merge
            # (вершины не успевают пересечь X=0 при таком малом весе).
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
                    # Экстраполируем к полному весу 1.0
                    t_coords = base_cache[obj]['coords'] + (t_coords - base_cache[obj]['coords']) / sk_weight
                    target_cache[obj] = t_coords

            if not target_cache:
                print(f"    [WARN] Skipping SK '{sk_name}': Topology shifted on all owners. Try removing 'Merge' from Mirror.")
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

                buf_sub = buf_xyz[mask]
                deltas  = _bary_delta_batch_bvh(buf_sub, base_cache[obj], t_coords)
                nonzero = np.linalg.norm(deltas, axis=1) > 1e-7
                if not nonzero.any(): continue

                indices      = np.where(mask)[0][nonzero]
                valid_deltas = deltas[nonzero].copy()

                # EFMI хранит позиции в мировом пространстве с инвертированной осью X
                # (аналогично Fast Path: if not is_xxmi: deltas[:, 0] *= -1)
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
        # Восстанавливаем шейпкеи
        for obj, states in sk_snapshot.items():
            if obj.data and obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks:
                    if sk.name in states:
                        sk.value = states[sk.name]
        set_armature_visibility(all_involved, True)
        print(f"  [TIME] Slow Path finished in {time.time() - t_start:.3f}s")

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

    # Создаём заглушки-буферы для всех шейпкеев (игра не упадёт)
    for sk_name in all_keys:
        out_name = _get_shape_buffer_name(base_name, sk_name, is_xxmi, dump_name)
        with open(os.path.join(output_dir, out_name), "wb") as f:
            f.write(original_bytes)

    if not sk_owner_map:
        print(f"  [PRE-SCAN] No real shape keys found — skipping component (placeholders saved)")
        return True

    # Читаем кэш
    try:
        from .export_cache import component_cache
        comp_cache = component_cache(base_name)
    except Exception:
        comp_cache = None

    buf_v_count = len(original_data) // stride

    # ── FAST PATH ──────────────────────────────────────────────────────────
    sk_owner_map_after_fast = {}   # шейпкеи, которые нуждаются в Baked или Slow Path

    if comp_cache is not None:
        print(f"  [CACHE] HIT — starting Fast Path")
        stride = comp_cache.get('stride', stride)
        buf_v_count = len(original_data) // stride

        fallback_map, fast_path_slots_per_sk = _bake_with_direct_offsets(
            sk_owner_map, comp_cache, original_bytes,
            stride, buf_v_count, output_dir, base_name, dump_name, is_xxmi
        )

        for sk_name, owners in sk_owner_map.items():
            fb  = fallback_map.get(sk_name, [])
            via = owners.get('via_target', [])
            if fb or via:
                sk_owner_map_after_fast[sk_name] = {
                    'direct':     fb,
                    'via_target': via,
                }
    else:
        print(f"  [CACHE] MISS — skipping Fast Path")
        sk_owner_map_after_fast = sk_owner_map
        fast_path_slots_per_sk = {}

    if not sk_owner_map_after_fast:
        print(f"  [TIME] Bake finished in {time.time() - t_start:.3f}s (Fast Path only)")
        return True

    # ── BAKED PATH (Spatial Fallback) ──────────────────────────────────────
    # Все 'direct' объекты, которые не прошли через Fast Path, пробуем запечь через KD-Tree.
    sk_owner_map_bake   = {}
    sk_owner_map_slow   = {}

    for sk_name, owners in sk_owner_map_after_fast.items():
        bake_direct = []
        # Теперь ВСЕ прямые владельцы шейпкеев идут в Baked Path (пространственный поиск),
        # так как это точнее и быстрее, чем барицентрический Slow Path.
        for obj in owners.get('direct', []):
            if obj.data and obj.data.shape_keys:
                bake_direct.append(obj)
            else:
                sk_owner_map_slow.setdefault(sk_name, {'direct': [], 'via_target': []})['direct'].append(obj)

        if bake_direct:
            sk_owner_map_bake[sk_name] = bake_direct

        # via_target → ВСЕГДА Slow Path (Surface Deform требует интерполяции по треугольникам)
        slow_via = owners.get('via_target', [])
        if slow_via:
            if sk_name not in sk_owner_map_slow:
                sk_owner_map_slow[sk_name] = {'direct': [], 'via_target': []}
            sk_owner_map_slow[sk_name]['via_target'].extend(slow_via)

    if sk_owner_map_bake:
        print(f"  [BAKED PATH] Processing {sum(len(v) for v in sk_owner_map_bake.values())} objects via Spatial Match")
        remaining = _bake_path_for_generative_objects(
            context, sk_owner_map_bake, comp_cache,
            original_bytes, stride, buf_v_count,
            output_dir, base_name, dump_name, is_xxmi
        )
        # Объекты, которые не удалось запечь (из-за смены топологии или дистанции) → в Slow Path
        for sk_name, objs in remaining.items():
            if sk_name not in sk_owner_map_slow:
                sk_owner_map_slow[sk_name] = {'direct': [], 'via_target': []}
            sk_owner_map_slow[sk_name]['direct'].extend(objs)

    # ── SLOW PATH (Barycentric) ────────────────────────────────────────────
    if sk_owner_map_slow:
        # Финальная проверка: объекты без шейпкеев И без Surface Deform не нужны
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
    print(f"    - Fast Path (Direct Map): {sum(1 for sk_name, sk_data in sk_owner_map.items() for o in sk_data['direct'] if o not in sk_owner_map_after_fast.get(sk_name, {}).get('direct', []))} objects")
    print(f"    - Baked Path (Spatial Match): {sum(len(v) for v in sk_owner_map_bake.values())} objects")
    print(f"    - Slow Path (Barycentric): {sum(len(v['direct']) + len(v['via_target']) for v in sk_owner_map_slow.values())} objects")
    
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