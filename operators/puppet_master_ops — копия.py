# RZMenu/operators/puppet_master_ops.py
# Puppet Master v12.0 — Final Rebuild
# 1. Returned to BVH-based matching for robust topology handling (fixes "does not even try to bake")
# 2. Implemented MATRIX_WORLD projection (fixes coordinates collapsing to 0,0,0 due to local-space mismatch)
# 3. neighbor contamination strictly forbidden (if closest object has no shape key, vertex is ignored)
# 4. Limit parameter hard-locked internally to 5mm to prevent absurd jumps
# 5. Correctly stores and restores all shape key states

import bpy
import struct
import os
import re
from bpy.props import IntProperty
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def set_armature_visibility(objects, visible):
    for obj in objects:
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                mod.show_viewport = visible

def get_stride_for_game(context):
    game = context.scene.rzm.game.name
    if game in ('ZenlessZoneZero', 'HonkaiStarRail'): return 40
    if game in ('ArknightsEndfield', 'WutheringWaves'): return 16
    return 32

def is_surface_deform_bound(mod):
    if mod.type != 'SURFACE_DEFORM': return False
    return getattr(mod, 'is_bound', False)

def save_shape_key_state(objects):
    state = {}
    for obj in objects:
        if obj.data and obj.data.shape_keys:
            state[obj] = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}
    return state

def restore_shape_key_state(state):
    for obj, values in state.items():
        if obj.data and obj.data.shape_keys:
            for sk in obj.data.shape_keys.key_blocks:
                if sk.name in values:
                    sk.value = values[sk.name]

def get_disabled_sk_names(context):
    return {cfg.shape_name for cfg in context.scene.rzm.shape_configs if cfg.disable_export}

def get_active_sk_filter(context):
    rzm = context.scene.rzm
    if not rzm.addons.puppet_master_per_component:
        return None
    idx = context.scene.rzm_active_shape_config_index
    if 0 <= idx < len(rzm.shape_configs):
        return rzm.shape_configs[idx].shape_name
    return None


# ─── BUFFER INFO HELPERS ───────────────────────────────────────────────────────

def get_vb0_path(mod_root, comp_id):
    return os.path.join(mod_root, "Meshes", f"Component{comp_id}_VB0.buf")

def get_buf_vertex_count(path, stride):
    return os.path.getsize(path) // stride if os.path.exists(path) else 0

def get_object_vertex_range_in_buf(obj, buf_v_count, stride, vb0_path):
    bl_count = len(obj.data.vertices) if obj and obj.data else 0
    if not os.path.exists(vb0_path) or buf_v_count == 0 or not bl_count:
        return None, None, bl_count

    v_world = obj.matrix_world @ obj.data.vertices[0].co
    obj_first_pos = (v_world.x, v_world.y, v_world.z)

    with open(vb0_path, 'rb') as f:
        raw = f.read()

    best_idx = None
    best_dist = float('inf')
    for i in range(buf_v_count):
        bx, by, bz = struct.unpack_from('<3f', raw, i * stride)
        dx, dy, dz = bx - obj_first_pos[0], by - obj_first_pos[1], bz - obj_first_pos[2]
        d = dx*dx + dy*dy + dz*dz
        if d < best_dist:
            best_dist = d
            best_idx = i

    if best_idx is not None:
        return best_idx, min(best_idx + bl_count, buf_v_count), bl_count
    return None, None, bl_count


# ─── CORE BAKING LOGIC ────────────────────────────────────────────────────────

def bake_shape_key_for_component(
    context, comp_id, comp_objects, mod_root, sk_name, disabled_names, depsgraph
):
    """
    Robust BVH-based bake for a single shape key within a component.
    """
    if sk_name in disabled_names:
        return False

    stride = get_stride_for_game(context)
    vb0_path = get_vb0_path(mod_root, comp_id)

    if not os.path.exists(vb0_path):
        return False

    with open(vb0_path, 'rb') as f:
        original_data = bytearray(f.read())
    buf_v_count = len(original_data) // stride

    # 1. Determine active vs inactive objects
    active_objs = set()
    targets_needed = set()

    for obj in comp_objects:
        has_direct = obj.data and obj.data.shape_keys and sk_name in obj.data.shape_keys.key_blocks
        if has_direct:
            active_objs.add(obj)
            continue
        
        for mod in obj.modifiers:
            if not mod.show_viewport: continue
            if mod.type == 'SURFACE_DEFORM':
                if not is_surface_deform_bound(mod):
                    print(f"  [!] {obj.name} has unbound SurfaceDeform. Ignored.")
                    continue
                if mod.target and mod.target.data and mod.target.data.shape_keys:
                    if sk_name in mod.target.data.shape_keys.key_blocks:
                        active_objs.add(obj)
                        targets_needed.add(mod.target)
                        break
            elif mod.type == 'SHRINKWRAP':
                if mod.target and mod.target.data and mod.target.data.shape_keys:
                    if sk_name in mod.target.data.shape_keys.key_blocks:
                        active_objs.add(obj)
                        targets_needed.add(mod.target)
                        break

    if not active_objs:
        return False

    # 2. State Snapshot & Prep
    all_involved = list(set(comp_objects).union(targets_needed))
    set_armature_visibility(all_involved, False)

    mirror_states = {}
    for obj in all_involved:
        mirror_states[obj] = []
        for mod in obj.modifiers:
            if mod.type == 'MIRROR' and mod.show_viewport:
                mirror_states[obj].append((mod, mod.use_mirror_merge, mod.use_clip))
                mod.use_mirror_merge, mod.use_clip = False, False

    sk_snapshot = save_shape_key_state(all_involved)
    current_buf = bytearray(original_data)
    matched_count = 0

    try:
        # --- CACHE BASIS (0.0) ---
        for obj in all_involved:
            if obj.data and obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks: sk.value = 0.0
        bpy.context.view_layer.update()

        base_bvh_cache = {}
        base_coords = {}
        for obj in comp_objects:
            ev = obj.evaluated_get(depsgraph)
            em = ev.to_mesh()
            wm = obj.matrix_world
            coords = [wm @ v.co for v in em.vertices]
            polys = [list(p.vertices) for p in em.polygons]
            base_coords[obj] = coords
            base_bvh_cache[obj] = BVHTree.FromPolygons(coords, polys) if coords else None
            ev.to_mesh_clear()

        # --- CACHE TARGET (1.0) ---
        for obj in all_involved:
            if obj.data and obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks:
                    sk.value = 1.0 if sk.name == sk_name else 0.0
        bpy.context.view_layer.update()

        target_coords = {}
        for obj in active_objs:
            ev = obj.evaluated_get(depsgraph)
            em = ev.to_mesh()
            wm = obj.matrix_world
            t_coords = [wm @ v.co for v in em.vertices]
            if len(t_coords) == len(base_coords[obj]):
                target_coords[obj] = t_coords
            ev.to_mesh_clear()

        # --- INJECT ---
        SEARCH_LIMIT = 0.005 # 5mm tolerance

        for i in range(buf_v_count):
            off = i * stride
            orig_v = Vector(struct.unpack_from('<3f', original_data, off))

            best_obj = None
            best_dist = float('inf')
            best_face = None

            # Find the EXACT closest owner object in the ENTIRE component
            for obj, bvh in base_bvh_cache.items():
                if not bvh: continue
                loc, normal, face_idx, dist = bvh.find_nearest(orig_v)
                if face_idx is not None and dist < best_dist:
                    best_dist = dist
                    best_obj = obj
                    best_face = face_idx

            # Rule 1: Must be within 5mm. If not, this vertex doesn't belong to Blender geometry.
            if best_obj_dist_fail := (best_dist > SEARCH_LIMIT):
                continue

            # Rule 2: If the closest object is NOT affected by the shape key, DO NOTHING!
            # This completely solves neighboring objects getting deformed.
            if best_obj not in active_objs or best_obj not in target_coords:
                continue

            # Calculate precise sub-face interpolation (Barycentric-like via weighted sum)
            face_verts = [v for p in best_obj.data.polygons if p.index == best_face for v in p.vertices]
            b_points = base_coords[best_obj]
            t_points = target_coords[best_obj]

            blended_delta = Vector((0,0,0))
            total_w = 0.0
            
            for vi in face_verts:
                # distance to face vertices
                v_dist = (b_points[vi] - orig_v).length
                # heavily weight the nearest vertex
                w = 1.0 / (v_dist**2 + 1e-8)
                delta_v = t_points[vi] - b_points[vi]
                blended_delta += delta_v * w
                total_w += w

            if total_w > 0:
                final_delta = blended_delta / total_w
                if final_delta.length > 1e-6: # Only write if there's an actual change
                    struct.pack_into('<3f', current_buf, off, *(orig_v + final_delta))
                    matched_count += 1

    finally:
        restore_shape_key_state(sk_snapshot)
        set_armature_visibility(all_involved, True)
        for obj, mods in mirror_states.items():
            for mod, merge, clip in mods:
                mod.use_mirror_merge, mod.use_clip = merge, clip
        bpy.context.view_layer.update()

    if matched_count > 0:
        out_dir = os.path.join(mod_root, "SK")
        os.makedirs(out_dir, exist_ok=True)
        clean_name = sk_name.replace(" ", "_")
        with open(os.path.join(out_dir, f"Component{comp_id}_VB0_{clean_name}.buf"), 'wb') as f:
            f.write(current_buf)
        print(f"  [✓] Baked '{sk_name}' for Comp {comp_id} (Deformed {matched_count} vertices)")
        return True
    return False


def collect_components_and_shapes(context, sk_filter=None):
    rzm = context.scene.rzm
    result = {} 
    
    for cfg in rzm.shape_configs:
        if cfg.disable_export: continue
        sk_name = cfg.shape_name
        if sk_filter and sk_name != sk_filter: continue

        for ref in cfg.affected_objects:
            obj = ref.obj or bpy.data.objects.get(ref.obj_name)
            if not obj or obj.type != 'MESH': continue

            m = re.search(r'Component\s*(\d+)', obj.name, re.IGNORECASE)
            comp_id = m.group(1) if m else '0'
            result.setdefault(comp_id, {}).setdefault(sk_name, set()).add(obj)

    # Convert sets to lists
    return {cid: {sk: list(objs) for sk, objs in sk_map.items()} for cid, sk_map in result.items()}


# ─── OPERATOR ─────────────────────────────────────────────────────────────────

class RZM_OT_PuppetMasterBake(bpy.types.Operator):
    bl_idname = "rzm.puppet_master_bake"
    bl_label = "Bake Puppet Master Shapes"
    bl_description = "Bake active shape keys into VB0 buffers"

    def execute(self, context):
        from .export_manager import get_target_path
        mod_root = get_target_path(context)
        if not mod_root or not os.path.exists(mod_root):
            self.report({'ERROR'}, "Invalid export path!")
            return {'CANCELLED'}

        sk_filter = get_active_sk_filter(context)
        disabled = get_disabled_sk_names(context)
        
        work_queue = collect_components_and_shapes(context, sk_filter)
        if not work_queue:
            self.report({'WARNING'}, "No active components to bake.")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
        total_baked, total_skipped = 0, 0

        print("\n" + "=" * 50)
        print(f"  PUPPET MASTER v12.0 BAKE STARTED")
        print(f"  Mode: {'Single SK -> ' + sk_filter if sk_filter else 'ALL Active Shapes'}")
        print("=" * 50)

        for comp_id, sk_map in sorted(work_queue.items()):
            # Fetch ALL objects that belong to this component ID so we can safely test against them
            comp_objs = [
                o for o in bpy.context.view_layer.objects 
                if o.type == 'MESH' and re.search(fr'Component\s*0*{comp_id}\b', o.name, re.IGNORECASE)
            ]
            if not comp_objs:
                continue
                
            for sk_name, active_subset in sk_map.items():
                if bake_shape_key_for_component(context, comp_id, comp_objs, mod_root, sk_name, disabled, depsgraph):
                    total_baked += 1
                else:
                    total_skipped += 1

        print("=" * 50)
        self.report({'INFO'}, f"PM v12 Done. Baked: {total_baked}")
        return {'FINISHED'}


# ─── BUFFER INFO DISPLAY ──────────────────────────────────────────────────────

class RZM_OT_ShowBufferInfo(bpy.types.Operator):
    bl_idname = "rzm.show_buffer_info"
    bl_label = "Buffer Index Info"
    
    config_index: IntProperty()

    def execute(self, context):
        from .export_manager import get_target_path
        rzm = context.scene.rzm
        cfg = rzm.shape_configs[self.config_index]
        mod_root = get_target_path(context)
        stride = get_stride_for_game(context)

        print(f"\n[Buffer Info] Shape: '{cfg.shape_name}'")
        print(f"{'Object':<35} | {'BL Verts':>8} | {'VB Range':>18} | {'SK Size':>8}")
        print("-" * 75)

        for ref in cfg.affected_objects:
            obj = ref.obj or bpy.data.objects.get(ref.obj_name)
            if not obj or not obj.data: continue

            bl_c = len(obj.data.vertices)
            m = re.search(r'Component\s*(\d+)', obj.name, re.IGNORECASE)
            c_id = m.group(1) if m else '0'
            vb0 = get_vb0_path(mod_root, c_id) if mod_root else ""
            b_cnt = get_buf_vertex_count(vb0, stride)

            s, e, _ = get_object_vertex_range_in_buf(obj, b_cnt, stride, vb0)
            rng = f"{s}..{e}" if s is not None else "?..?"
            
            p = os.path.join(mod_root, "SK", f"Component{c_id}_VB0_{cfg.shape_name.replace(' ', '_')}.buf") if mod_root else ""
            sk_sz = os.path.getsize(p) // stride if os.path.exists(p) else 0

            print(f"{obj.name:<35} | {bl_c:>8} | {rng:>18} | {str(sk_sz) if sk_sz else '—':>8}")

        return {'FINISHED'}


classes_to_register = [RZM_OT_PuppetMasterBake, RZM_OT_ShowBufferInfo]

def register():
    for cls in classes_to_register: bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register): bpy.utils.unregister_class(cls)
