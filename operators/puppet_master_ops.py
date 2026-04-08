# RZMenu/operators/puppet_master_ops.py
# VERSION: 14.1 (NUMPY VECTORIZED BAKE)
import bpy
import struct
import os
import re
import json
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
def _build_spatial_index(coords_np, polys):
    """
    Build a face-centroid KD-tree for fast nearest-face lookup.
    Returns (kd_tree, face_centroids_np) or None if scipy absent.
    """
    try:
        from scipy.spatial import KDTree
    except ImportError:
        return None, None

    centroids = np.array([
        coords_np[np.array(face)].mean(axis=0) for face in polys
    ], dtype=np.float32)
    return KDTree(centroids), centroids


def _idw_delta_batch(buf_verts_np, owner_data, target_data):
    """
    Vectorised IDW interpolation.
    
    buf_verts_np  : (N, 3) – all buffer vertices that belong to this owner
    owner_data    : dict with 'coords' (np), 'polys', 'kd', 'centroids', 'bvh'
    target_data   : (M, 3) numpy array of deformed positions

    Returns (N, 3) deltas.
    """
    base_coords = owner_data['coords']   # (M, 3)
    polys       = owner_data['polys']
    kd          = owner_data['kd']
    bvh         = owner_data['bvh']

    # 1. Get nearest face for every buffer vertex
    if kd is not None:
        # Fast Scipy path
        _, face_ids = kd.query(buf_verts_np, workers=-1)
    else:
        # Robust BVH fallback
        face_ids = []
        for bv in buf_verts_np:
            _, _, face_idx, _ = bvh.find_nearest(Vector(bv))
            face_ids.append(face_idx if face_idx is not None else 0)
        face_ids = np.array(face_ids, dtype=np.int32)

    deltas_np = target_data - base_coords               # (M, 3) delta per mesh vertex

    # 2. Compute IDW weight for every buffer vertex from its nearest face's corners
    out = np.zeros_like(buf_verts_np)
    for n, (bv, fi) in enumerate(zip(buf_verts_np, face_ids)):
        face_v_idx = np.array(polys[fi])
        bv_face    = base_coords[face_v_idx]            # (K, 3)
        diff       = bv_face - bv                        # (K, 3)
        sq_dist    = (diff * diff).sum(axis=1) + 1e-10  # (K,)
        w          = 1.0 / sq_dist                       # (K,)
        out[n]     = (w[:, None] * deltas_np[face_v_idx]).sum(axis=0) / w.sum()
    return out   # (N, 3)


# ─────────────────────────────────────────────────────────────────────────────
# CORE BAKE
# ─────────────────────────────────────────────────────────────────────────────
def bake_component_shapes(context, base_name, comp_objects, mod_root, limit,
                          single_shape_name=None, full_export_mode=False):
    """Bake shapes with strict whitelisting – v14.1 NumPy accelerated."""
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
    linked_targets  = get_linked_targets(comp_objects)
    all_involved    = comp_objects + list(set(linked_targets))

    if single_shape_name:
        all_keys = {single_shape_name}
    else:
        all_keys = {c.shape_name for c in rzm.shape_configs if not c.disable_export}

    if not all_keys: return True

    print(f"\n[RZM] [BAKE] Group: '{base_name}'")
    _log_buf_path(vb0_path, stride, game)
    print(f"[RZM] [BAKE] Vertices in buffer: {buf_v_count} | Shapes to bake: {len(all_keys)}")

    # ── Read buffer XYZ into numpy once ──────────────────────────────────────
    # Extract only the XYZ floats (first 12 bytes of every stride block)
    raw_np = np.frombuffer(original_bytes, dtype=np.uint8)
    # view as float32, shape (buf_v_count, stride//4)
    float_view = raw_np.reshape(buf_v_count, stride).view(np.float32).reshape(buf_v_count, stride // 4)
    buf_xyz = float_view[:, :3].astype(np.float64)    # (N, 3)  – positions only

    # ── Depsgraph ─────────────────────────────────────────────────────────────
    depsgraph = context.evaluated_depsgraph_get()

    # ── Snapshot current SK values ─────────────────────────────────────────
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
        # ── BASIS cache ───────────────────────────────────────────────────────
        # Reset all shape keys to 0, evaluate mesh once per object
        for a_obj in all_involved:
            if a_obj.data and a_obj.data.shape_keys:
                for sk in a_obj.data.shape_keys.key_blocks: sk.value = 0.0
        context.view_layer.update()
        depsgraph.update()

        base_cache = {}
        for obj in comp_objects:
            b_eval  = obj.evaluated_get(depsgraph).to_mesh()
            coords  = np.array([v.co for v in b_eval.vertices], dtype=np.float64)
            polys   = [list(p.vertices) for p in b_eval.polygons]
            obj.evaluated_get(depsgraph).to_mesh_clear()

            # Build KD on face centroids (scipy) or BVH fallback
            kd, centroids = _build_spatial_index(coords, polys)
            bvh = None if kd is not None else BVHTree.FromPolygons(
                [Vector(c) for c in coords], polys
            )
            base_cache[obj] = {
                'coords':    coords,
                'polys':     polys,
                'kd':        kd,
                'centroids': centroids,
                'bvh':       bvh,
            }

        # Precompute per-object mask: which buf vertices are "owned" by each object.
        # We do ONE BVH/KD query across ALL buf verts here and cache the result.
        # Then for each shape we only re-evaluate objects that actually moved.
        owner_map, dist_map = _assign_owners_bulk(buf_xyz, base_cache, limit)

        # ── Per-shape loop ────────────────────────────────────────────────────
        for sk_name in all_keys:
            print(f"  [SK] Submitting: '{sk_name}'")

            # Activate only the current SK
            for obj in all_involved:
                if obj.data and obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = 1.0 if sk.name == sk_name else 0.0
            context.view_layer.update()
            depsgraph.update()

            # Collect deformed coords for objects that actually have this SK
            target_cache = {}
            for obj in comp_objects:
                is_active = (obj.data.shape_keys and
                             sk_name in obj.data.shape_keys.key_blocks)
                if not is_active:
                    for mod in obj.modifiers:
                        if (mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and
                                mod.show_viewport and mod.target):
                            t = mod.target
                            if (t.data and t.data.shape_keys and
                                    sk_name in t.data.shape_keys.key_blocks):
                                is_active = True
                                break
                if is_active:
                    t_eval  = obj.evaluated_get(depsgraph).to_mesh()
                    t_coords = np.array([v.co for v in t_eval.vertices], dtype=np.float64)
                    obj.evaluated_get(depsgraph).to_mesh_clear()
                    if len(t_coords) == len(base_cache[obj]['coords']):
                        target_cache[obj] = t_coords

            if not target_cache:
                continue

            # ── Vectorised delta application ───────────────────────────────
            current_buf = bytearray(original_data)
            matched_count = 0

            for obj, t_coords in target_cache.items():
                # Indices in buf owned by this object
                mask = (owner_map == id(obj))
                if not mask.any(): continue

                buf_sub = buf_xyz[mask]   # (K, 3) subset

                deltas = _idw_delta_batch(buf_sub, base_cache[obj], t_coords)  # (K, 3)

                # Filter trivially-zero deltas
                nonzero = np.linalg.norm(deltas, axis=1) > 1e-7
                indices = np.where(mask)[0][nonzero]
                valid_deltas = deltas[nonzero]

                for gi, delta in zip(indices, valid_deltas):
                    orig_xyz = buf_xyz[gi]
                    new_xyz  = orig_xyz + delta
                    struct.pack_into("<3f", current_buf, gi * stride,
                                    float(new_xyz[0]), float(new_xyz[1]), float(new_xyz[2]))
                    matched_count += 1

            clean_name = re.sub(r'[\\/:*?"<>|]', '_', sk_name).replace(" ", "_").replace(".", "_")
            out_name   = f"{base_name}_{clean_name}.buf"
            
            if matched_count > 0:
                with open(os.path.join(output_dir, out_name), "wb") as f:
                    f.write(current_buf)
                print(f"    -> [DONE] {out_name} ({matched_count} verts)")
            else:
                print(f"    -> [SKIP] {out_name} (No deltas)")

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
    bl_description = "Bake shape keys using strictly RZMenu Shape Configs (v14.1)"
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