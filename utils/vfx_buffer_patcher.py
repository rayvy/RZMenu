# RZMenu/utils/vfx_buffer_patcher.py
import bpy
import os
import struct
import random
import math
import numpy as np
from mathutils import Vector, Matrix, Euler

# Set to True to export giant triangles directly in the buffer coordinates for visual verification
TEST_TRIANGLE_EXPORT = False


def swap_yz(vec):
    return Vector((vec.x, vec.z, vec.y))

def rotate_x_minus_90_around_origin(vec, origin):
    delta = vec - origin
    rotated_delta = Vector((delta.x, delta.z, -delta.y))
    return origin + rotated_delta

def remap_curve_point_to_buffer(local_pos, local_origin, profile):
    if profile == "ZENLESS_ZONE_ZERO":
        return swap_yz(local_pos)
    if profile == "GENSHIN_IMPACT":
        remapped_pos = swap_yz(local_pos)
        remapped_origin = swap_yz(local_origin)
        return rotate_x_minus_90_around_origin(remapped_pos, remapped_origin)
    return local_pos

def resolve_coordinate_remap_profile(context, requested_profile):
    profile = requested_profile or "AUTO"
    if profile != "AUTO":
        return profile
    
    rzm = getattr(context.scene, "rzm", None)
    game = rzm.game.selection if rzm and hasattr(rzm, "game") else ""
    if game in ("ZenlessZoneZero", "HonkaiStarRail"):
        return "ZENLESS_ZONE_ZERO"
    if game == "GenshinImpact":
        return "GENSHIN_IMPACT"
    return "NONE"

def get_curve_prop(obj, name, default):
    attr = f"rzm_curve_vfx_{name}"
    if hasattr(obj, attr):
        return getattr(obj, attr)
    return default

def pre_collect_vfx_vertex_counts(context):
    """
    Scans the scene for Curve VFX objects, computes their vertex counts,
    and populates context.scene.rzm.vfx_vertex_counts BEFORE rendering J2 template.
    """
    rzm = getattr(context.scene, "rzm", None)
    if not rzm:
        return
        
    try:
        rzm.vfx_vertex_counts.clear()
    except Exception as e:
        print(f"[RZM-VFX] Failed to clear vfx_vertex_counts: {e}")
        return

    # Find all curves in the scene with VFX enabled (either via native property or custom property)
    vfx_curves = [
        obj for obj in context.scene.objects 
        if obj.type == 'CURVE' and (getattr(obj, "rzm_curve_vfx_enabled", False) or obj.get("RZM.CURVE_VFX"))
    ]
    if not vfx_curves:
        return

    print(f"[RZM-VFX] Pre-collecting vertex counts for {len(vfx_curves)} Curve VFX objects.")

    mod_name = getattr(rzm.export_settings, "mod_name", "") or ""
    
    curves_by_comp = {}
    for curve_obj in vfx_curves:
        comp_name, target_mesh, part_name = find_associated_mesh_and_component(context, curve_obj)
        if not target_mesh or not comp_name:
            continue
            
        if comp_name not in curves_by_comp:
            curves_by_comp[comp_name] = []
        curves_by_comp[comp_name].append(curve_obj)

    for comp_name, curve_list in curves_by_comp.items():
        total_new_verts = 0
        for curve_obj in curve_list:
            particle_count = get_curve_prop(curve_obj, "particle_count", 1)
            mesh_fx_type = str(get_curve_prop(curve_obj, "mesh_fx_type", "0"))
            if mesh_fx_type == "1":
                v_per_particle = 4
            elif mesh_fx_type == "2":
                v_per_particle = 6
            else:
                v_per_particle = 3
            total_new_verts += particle_count * v_per_particle
            
        comp_fullname = f"{mod_name}{comp_name}"
        # Avoid duplicates
        item = None
        for x in rzm.vfx_vertex_counts:
            if x.component_name == comp_fullname:
                item = x
                break
        if item is None:
            item = rzm.vfx_vertex_counts.add()
            item.component_name = comp_fullname
            item.vertex_count = 0
        item.vertex_count += total_new_verts
        print(f"[RZM-VFX] Pre-collected {total_new_verts} VFX vertices for component '{comp_fullname}' (total={item.vertex_count})")

def find_associated_mesh_and_component(context, curve_obj):
    collections = curve_obj.users_collection
    if not collections:
        return None, None, None
        
    comp_map = {}
    try:
        from .component_collector import ComponentCollector
        collector = ComponentCollector(context)
        comp_map = collector.get_components()
    except Exception as e:
        print(f"[RZM-VFX] ComponentCollector import failed: {e}")
        comp_map = {}
        
    if not comp_map:
        rzm = getattr(context.scene, "rzm", None)
        if rzm and hasattr(rzm, "component_manager"):
            cm = rzm.component_manager
            for comp in cm.components:
                comp_map[comp.name] = [obj for obj in context.scene.objects if obj.type == 'MESH' and comp.name.lower() in obj.name.lower()]
                
    for col in collections:
        for obj in col.objects:
            if obj.type == 'MESH':
                for comp_name, meshes in comp_map.items():
                    if obj in meshes:
                        part_name = obj.name
                        rzm = getattr(context.scene, "rzm", None)
                        if rzm and hasattr(rzm, "component_manager"):
                            for comp in rzm.component_manager.components:
                                if comp.name == comp_name:
                                    for part in comp.parts:
                                        if part.name.lower() in obj.name.lower():
                                            part_name = part.name
                                            break
                        return comp_name, obj, part_name
                        
    return None, None, None

def evaluate_curve_spline_points(context, curve_obj, num_samples=32):
    depsgraph = context.evaluated_depsgraph_get()
    try:
        eval_obj = curve_obj.evaluated_get(depsgraph)
    except Exception as e:
        print(f"[RZM-VFX] Error getting evaluated curve: {e}")
        return []
        
    if not eval_obj.data.splines:
        return []
        
    try:
        temp_mesh = eval_obj.to_mesh()
    except Exception as e:
        print(f"[RZM-VFX] Error converting curve to mesh: {e}")
        return []
        
    if not temp_mesh or not temp_mesh.vertices:
        if temp_mesh:
            eval_obj.to_mesh_clear()
        return []
        
    verts = [v.co.copy() for v in temp_mesh.vertices]
    eval_obj.to_mesh_clear()
    
    if len(verts) < 2:
        return []
        
    distances = [0.0]
    total_len = 0.0
    for i in range(1, len(verts)):
        dist = (verts[i] - verts[i-1]).length
        total_len += dist
        distances.append(total_len)
        
    if total_len == 0.0:
        return [verts[0] for _ in range(num_samples)]
        
    resampled_verts = []
    for j in range(num_samples):
        factor = j / (num_samples - 1)
        target_dist = factor * total_len
        
        idx = 0
        while idx < len(distances) - 2 and distances[idx+1] < target_dist:
            idx += 1
            
        d0 = distances[idx]
        d1 = distances[idx+1]
        t = (target_dist - d0) / (d1 - d0) if d1 > d0 else 0.0
        
        pt = verts[idx] + t * (verts[idx+1] - verts[idx])
        resampled_verts.append(pt)
        
    return resampled_verts

def find_file(directory, filename):
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower() == filename.lower():
                return os.path.join(root, f)
    return None

def strip_prefix_case_insensitive(value, prefix):
    if not value or not prefix:
        return value
    if value.lower().startswith(prefix.lower()):
        return value[len(prefix):]
    return value

def resolve_part_suffix(component_name, part_name, mesh_name="", mod_name=""):
    candidates = []
    if part_name:
        candidates.append(str(part_name))
    if mesh_name:
        candidates.append(str(mesh_name))

    for candidate in candidates:
        value = candidate.strip()
        if not value:
            continue
        value = strip_prefix_case_insensitive(value, mod_name).strip()
        suffix = strip_prefix_case_insensitive(value, component_name).strip()
        if suffix and suffix != value:
            return suffix
        if value and value.lower() != str(component_name).lower():
            return value
    return ""

def float_to_half(f):
    return np.float16(f).view(np.uint16)



def find_stride_from_ini(mod_root, resource_name, default_stride):
    # Search for resource_name in any active .ini file in mod_root
    ini_path = None
    for f in os.listdir(mod_root):
        if f.lower().endswith('.ini') and not f.lower().startswith('disabled'):
            ini_path = os.path.join(mod_root, f)
            break
    if not ini_path:
        return default_stride
        
    try:
        with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        import re
        pattern = rf"\[{resource_name}\].*?stride\s*=\s*(\d+)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return int(match.group(1))
    except Exception as e:
        print(f"[RZM-VFX] Error reading stride from ini for {resource_name}: {e}")
    return default_stride

def patch_buffers(context, cache):
    """
    Main post-export entry point for curve-based VFX buffer patching.
    Modifies vertex position/blend/texcoord buffers and index buffers.
    """
    print("\n[RZM-VFX] ==================================================")
    print("[RZM-VFX] RUNNING VFX BUFFER PATCHER")
    print("[RZM-VFX] ==================================================")
    mod_root = cache.get('mod_root')
    mod_name = cache.get('mod_name')
    if not mod_root or not os.path.exists(mod_root):
        print(f"[RZM-VFX] [ERROR] Invalid mod root: '{mod_root}'")
        return

    # Find all curves in the scene with VFX enabled (either via native property or custom property)
    vfx_curves = [
        obj for obj in context.scene.objects 
        if obj.type == 'CURVE' and (getattr(obj, "rzm_curve_vfx_enabled", False) or obj.get("RZM.CURVE_VFX"))
    ]
    if not vfx_curves:
        print("[RZM-VFX] No Curve objects with VFX enabled found.")
        print("[RZM-VFX] ==================================================")
        return

    print(f"[RZM-VFX] Found {len(vfx_curves)} Curve VFX objects to export.")

    # 1. Export all curves to curve_data.buf in the 'res' folder
    res_dir = os.path.join(mod_root, "res")
    os.makedirs(res_dir, exist_ok=True)
    curve_buf_path = os.path.join(res_dir, "curve_data.buf")

    # Let's accumulate all curve data points
    all_curve_bytes = bytearray()
    valid_curve_count = 0
    curve_mapping = {} # maps curve object name to index in curve_data.buf

    for idx, curve_obj in enumerate(vfx_curves):
        comp_name, target_mesh, part_name = find_associated_mesh_and_component(context, curve_obj)
        if not target_mesh:
            print(f"[RZM-VFX] [ERROR] Curve '{curve_obj.name}' is invalid: no associated mesh component.")
            continue

        profile_raw = get_curve_prop(curve_obj, "coordinate_remap_profile", "AUTO")
        profile = resolve_coordinate_remap_profile(context, profile_raw)
        
        # Sample points
        resampled_points = evaluate_curve_spline_points(context, curve_obj, num_samples=32)
        if not resampled_points or len(resampled_points) < 2:
            print(f"[RZM-VFX] [ERROR] Curve '{curve_obj.name}' evaluation returned insufficient points.")
            continue

        # Remap to target mesh's local coordinates
        local_pts = []
        for pt in resampled_points:
            wpos = curve_obj.matrix_world @ pt
            lpos = target_mesh.matrix_world.inverted() @ wpos
            local_pts.append(lpos)

        # Apply buffer coordinate remap
        remapped_pts = []
        for lpos in local_pts:
            remap_pt = remap_curve_point_to_buffer(lpos, local_pts[0], profile)
            remapped_pts.append(remap_pt)

        # Pack and write to curve_data.buf: 33 points, 40 bytes each (32 sampled points + 1 metadata point)
        for j in range(32):
            pt = remapped_pts[j]
            # Tangent
            if j < 31:
                tangent = (remapped_pts[j+1] - pt).normalized()
            else:
                tangent = (pt - remapped_pts[j-1]).normalized()
            
            # Normal
            ref = Vector((0.0, 1.0, 0.0)) if abs(tangent.dot(Vector((0.0, 0.0, 1.0)))) > 0.9 else Vector((0.0, 0.0, 1.0))
            normal = (ref - tangent * tangent.dot(ref)).normalized()
            u_val = j / 31.0

            # Pack
            point_data = struct.pack(
                '<fffffffff',
                pt.x, pt.y, pt.z,
                tangent.x, tangent.y, tangent.z,
                normal.x, normal.y, normal.z
            )
            point_data += struct.pack('<f', u_val)
            all_curve_bytes.extend(point_data)

        # 33rd point contains metadata (mesh_fx_type, mesh_fx_size_base, tri_aspect, speed, start_radius, end_radius, curve_right, curve_up)
        meta_fx_type = float(get_curve_prop(curve_obj, "mesh_fx_type", "0"))
        meta_size = float(get_curve_prop(curve_obj, "mesh_fx_size_base", 0.05))
        meta_aspect = float(get_curve_prop(curve_obj, "tri_aspect", 1.0))
        meta_speed = float(get_curve_prop(curve_obj, "speed", 0.5))
        start_radius = float(get_curve_prop(curve_obj, "start_radius", 0.005))
        end_radius = float(get_curve_prop(curve_obj, "end_radius", 0.060))
        curve_right = float(get_curve_prop(curve_obj, "curve_right", -0.1))
        curve_up = float(get_curve_prop(curve_obj, "curve_up", -0.15))
        
        meta_data = struct.pack(
            '<ffffffffff',
            meta_fx_type, meta_size, meta_aspect,  # position.xyz
            meta_speed, start_radius, end_radius,  # tangent.xyz
            curve_right, curve_up, 0.0,            # normal.xyz
            0.0                                    # u
        )
        all_curve_bytes.extend(meta_data)

        curve_mapping[curve_obj.name] = valid_curve_count
        valid_curve_count += 1
        print(f"[RZM-VFX] Curve '{curve_obj.name}' exported at index {valid_curve_count-1} for component '{comp_name}'")

    if valid_curve_count == 0:
        print("[RZM-VFX] [WARNING] No valid curves were exported. Aborting patch.")
        return

    # Write the collected curve_data.buf
    with open(curve_buf_path, 'wb') as f:
        f.write(all_curve_bytes)
    print(f"[RZM-VFX] Wrote {valid_curve_count} curves ({valid_curve_count * 32 * 40} bytes) to '{curve_buf_path}'")

    # 2. Group curves by target component and part
    curves_by_part = {}
    for curve_obj in vfx_curves:
        if curve_obj.name not in curve_mapping:
            continue
        comp_name, target_mesh, part_name = find_associated_mesh_and_component(context, curve_obj)
        if not target_mesh:
            continue
        key = (comp_name, part_name, target_mesh)
        if key not in curves_by_part:
            curves_by_part[key] = []
        curves_by_part[key].append(curve_obj)

    # 3. Patch component buffers per group
    for (comp_name, part_name, target_mesh), curve_list in curves_by_part.items():
        # Calculate total vertices and indices to be appended
        total_new_verts = 0
        total_new_indices = 0
        for curve_obj in curve_list:
            particle_count = get_curve_prop(curve_obj, "particle_count", 1)
            mesh_fx_type = str(get_curve_prop(curve_obj, "mesh_fx_type", "0"))
            if mesh_fx_type == "1":
                v_per_particle, i_per_particle = 4, 6
            elif mesh_fx_type == "2":
                v_per_particle, i_per_particle = 6, 15
            else:
                v_per_particle, i_per_particle = 3, 3
            total_new_verts += particle_count * v_per_particle
            total_new_indices += particle_count * i_per_particle

        # Resolve filenames
        part_suffix = resolve_part_suffix(comp_name, part_name, target_mesh.name, mod_name)
        expected_vb0_name = f"{mod_name}{comp_name}Position.buf"
        expected_vb2_name = f"{mod_name}{comp_name}Blend.buf"
        expected_vb1_name = f"{mod_name}{comp_name}Texcoord.buf"
        expected_ib_name = f"{mod_name}{comp_name}{part_suffix}.ib" if part_suffix else f"{mod_name}{comp_name}.ib"

        vb0_path = find_file(mod_root, expected_vb0_name)
        vb2_path = find_file(mod_root, expected_vb2_name)
        vb1_path = find_file(mod_root, expected_vb1_name)
        ib_path = find_file(mod_root, expected_ib_name)

        if not vb0_path:
            print(f"[RZM-VFX] [ERROR] Position buffer '{expected_vb0_name}' not found. Cannot patch.")
            continue

        # Get original vertex count from cache metadata if available, otherwise fallback
        comp_cache = cache.get('components', {}).get(comp_name, {})
        original_v_count = comp_cache.get('n_verts')
        if original_v_count is None:
            vb0_size = os.path.getsize(vb0_path)
            original_v_count = vb0_size // 40
            
        # Get original index count of the submesh part from the cache
        original_i_count = None
        for obj in comp_cache.get('objects', []):
            obj_name = obj.get('name', '').lower()
            if part_suffix:
                match_part = part_suffix.lower()
                if obj_name.endswith(match_part) or f"{match_part}-" in obj_name or f"_{match_part}" in obj_name:
                    original_i_count = obj.get('ib_count')
                    break
            else:
                original_i_count = obj.get('ib_count')
                break

        # Fallback for original_i_count if not found in cache
        if original_i_count is None or original_i_count == 0:
            if ib_path:
                ib_size_before = os.path.getsize(ib_path)
                stride_i = 4 if ib_size_before % 4 == 0 else 2
                original_i_count = ib_size_before // stride_i
            else:
                original_i_count = 0

        # Determine strides using find_stride_from_ini
        stride_b = 32
        if vb2_path:
            stride_b = find_stride_from_ini(mod_root, f"Resource{mod_name}{comp_name}Blend", 32)
            
        stride_t = 20
        if vb1_path:
            stride_t = find_stride_from_ini(mod_root, f"Resource{mod_name}{comp_name}Texcoord", 20)

        # Truncate all buffers to their clean original sizes first!
        print(f"[RZM-VFX] Cleaning and truncating buffers to original state:")
        print(f"[RZM-VFX]   * Original vertex count: {original_v_count}")
        print(f"[RZM-VFX]   * Original index count: {original_i_count}")
        print(f"[RZM-VFX]   * Strides - Position: 40, Blend: {stride_b}, Texcoord: {stride_t}")
        
        # Position (always stride 40)
        clean_vb0_size = original_v_count * 40
        if os.path.getsize(vb0_path) > clean_vb0_size:
            print(f"[RZM-VFX]   * Truncating VB0 to {clean_vb0_size} bytes")
            with open(vb0_path, 'r+b') as f:
                f.truncate(clean_vb0_size)
                
        # Blend (Weights)
        if vb2_path:
            clean_vb2_size = original_v_count * stride_b
            if os.path.getsize(vb2_path) > clean_vb2_size:
                print(f"[RZM-VFX]   * Truncating VB2 to {clean_vb2_size} bytes")
                with open(vb2_path, 'r+b') as f:
                    f.truncate(clean_vb2_size)
                    
        # Texcoord
        if vb1_path:
            clean_vb1_size = original_v_count * stride_t
            if os.path.getsize(vb1_path) > clean_vb1_size:
                print(f"[RZM-VFX]   * Truncating VB1 to {clean_vb1_size} bytes")
                with open(vb1_path, 'r+b') as f:
                    f.truncate(clean_vb1_size)
                    
        # IB (Indices)
        stride_i = 4
        if ib_path:
            ib_size_before = os.path.getsize(ib_path)
            stride_i = 4 if ib_size_before % 4 == 0 else 2
            fmt = '<I' if stride_i == 4 else '<H'
            clean_ib_size = original_i_count * stride_i
            if os.path.getsize(ib_path) > clean_ib_size:
                print(f"[RZM-VFX]   * Truncating IB to {clean_ib_size} bytes")
                with open(ib_path, 'r+b') as f:
                    f.truncate(clean_ib_size)

        # Open files for appending
        f_vb0 = open(vb0_path, 'ab')
        f_vb2 = open(vb2_path, 'ab') if vb2_path else None
        f_vb1 = open(vb1_path, 'ab') if vb1_path else None
        f_ib = open(ib_path, 'ab') if ib_path else None

        current_v_count = original_v_count

        # Iterate and write each curve's data
        for curve_obj in curve_list:
            curve_idx = curve_mapping[curve_obj.name]
            particle_count = get_curve_prop(curve_obj, "particle_count", 1)
            mesh_fx_type = str(get_curve_prop(curve_obj, "mesh_fx_type", "0"))
            mesh_fx_size_base = get_curve_prop(curve_obj, "mesh_fx_size_base", 0.05)
            tri_aspect = get_curve_prop(curve_obj, "tri_aspect", 1.0)
            weight_indices = list(get_curve_prop(curve_obj, "weight_indices", (-1, -1, -1, -1)))
            weight_values = list(get_curve_prop(curve_obj, "weight_values", (0.0, 0.0, 0.0, 0.0)))

            profile_raw = get_curve_prop(curve_obj, "coordinate_remap_profile", "AUTO")
            profile = resolve_coordinate_remap_profile(context, profile_raw)

            if mesh_fx_type == "1":
                v_per_particle, i_per_particle = 4, 6
            elif mesh_fx_type == "2":
                v_per_particle, i_per_particle = 6, 15
            else:
                v_per_particle, i_per_particle = 3, 3

            # ----------------------------------------------------------------------
            # A. Patch VB0 (Position)
            # ----------------------------------------------------------------------
            for p in range(particle_count):
                phase = random.random()
                speed_scale = random.uniform(0.8, 1.2)
                
                # Random unit direction in 3D
                theta = random.uniform(0, 2.0 * math.pi)
                phi = random.uniform(0, math.pi)
                dir_x = math.sin(phi) * math.cos(theta)
                dir_y = math.cos(phi)
                dir_z = math.sin(phi) * math.sin(theta)

                for v_idx in range(v_per_particle):
                    # Define local offsets based on mesh_fx_type
                    if mesh_fx_type == "1": # Quad
                        quad_verts = [
                            (-0.5 * tri_aspect, -0.5, 0.0),
                            ( 0.5 * tri_aspect, -0.5, 0.0),
                            (-0.5 * tri_aspect,  0.5, 0.0),
                            ( 0.5 * tri_aspect,  0.5, 0.0),
                        ]
                        local_pos = quad_verts[v_idx]
                    elif mesh_fx_type == "2": # Circle (pentagon)
                        if v_idx == 0:
                            local_pos = (0.0, 0.0, 0.0)
                        else:
                            angle = (v_idx - 1) * (2.0 * math.pi / 5.0)
                            local_pos = (math.cos(angle) * tri_aspect, math.sin(angle), 0.0)
                    else: # Triangle
                        tri_verts = [
                            (0.0, 1.0, 0.0),
                            (-0.866 * tri_aspect, -0.5, 0.0),
                            ( 0.866 * tri_aspect, -0.5, 0.0),
                        ]
                        local_pos = tri_verts[v_idx]

                    pos_x = local_pos[0] * mesh_fx_size_base
                    pos_y = local_pos[1] * mesh_fx_size_base
                    pos_z = local_pos[2] * mesh_fx_size_base

                    # Pack into 40-byte stride VB0
                    v_data = struct.pack(
                        '<ffffffffff',
                        pos_x, pos_y, pos_z,
                        phase, speed_scale, float(curve_idx),
                        dir_x, dir_y, dir_z, float(v_idx)
                    )
                    f_vb0.write(v_data)

            # ----------------------------------------------------------------------
            # B. Patch VB2 (Blend)
            # ----------------------------------------------------------------------
            if f_vb2:
                for p in range(particle_count):
                    for v_idx in range(v_per_particle):
                        buf = bytearray(stride_b)
                        clean_idx = [int(idx) if idx != -1 else 0 for idx in weight_indices]
                        clean_w = [float(w) for w in weight_values]

                        # Pack based on stride
                        if stride_b == 32:
                            struct.pack_into('<ffffIIII', buf, 0, clean_w[0], clean_w[1], clean_w[2], clean_w[3], clean_idx[0], clean_idx[1], clean_idx[2], clean_idx[3])
                        elif stride_b == 24:
                            struct.pack_into('<ffffBBBBxxxx', buf, 0, clean_w[0], clean_w[1], clean_w[2], clean_w[3], clean_idx[0], clean_idx[1], clean_idx[2], clean_idx[3])
                        elif stride_b == 20:
                            struct.pack_into('<ffffBBBB', buf, 0, clean_w[0], clean_w[1], clean_w[2], clean_w[3], clean_idx[0], clean_idx[1], clean_idx[2], clean_idx[3])
                        elif stride_b == 16:
                            h0 = float_to_half(clean_w[0])
                            h1 = float_to_half(clean_w[1])
                            h2 = float_to_half(clean_w[2])
                            h3 = float_to_half(clean_w[3])
                            struct.pack_into('<HHHHBBBBxxxx', buf, 0, h0, h1, h2, h3, clean_idx[0], clean_idx[1], clean_idx[2], clean_idx[3])
                        else:
                            if stride_b >= 16:
                                struct.pack_into('<ffff', buf, 0, clean_w[0], clean_w[1], clean_w[2], clean_w[3])
                            if stride_b >= 20:
                                struct.pack_into('<B', buf, 16, clean_idx[0])
                        f_vb2.write(buf)

            # ----------------------------------------------------------------------
            # C. Patch VB1 (Texcoord)
            # ----------------------------------------------------------------------
            if f_vb1:
                for p in range(particle_count):
                    for v_idx in range(v_per_particle):
                        buf = bytearray(stride_t)
                        if mesh_fx_type == "1": # Quad
                            uvs = [(0.0, 1.0), (1.0, 1.0), (0.0, 0.0), (1.0, 0.0)]
                            u, v = uvs[v_idx]
                        elif mesh_fx_type == "2": # Circle (pentagon)
                            if v_idx == 0:
                                u, v = 0.5, 0.5
                            else:
                                angle = (v_idx - 1) * (2.0 * math.pi / 5.0)
                                u, v = 0.5 + 0.5 * math.cos(angle), 0.5 + 0.5 * math.sin(angle)
                        else: # Triangle
                            uvs = [(0.5, 1.0), (0.0, 0.0), (1.0, 0.0)]
                            u, v = uvs[v_idx]

                        if stride_t >= 8:
                            struct.pack_into('<ff', buf, 0, u, v)
                        if stride_t >= 16:
                            struct.pack_into('<ff', buf, 8, u, v)
                        if stride_t >= 24:
                            if stride_t == 24:
                                struct.pack_into('<BBBB', buf, 16, 255, 255, 255, 255)
                            else:
                                struct.pack_into('<ffff', buf, 16, 1.0, 1.0, 1.0, 1.0)
                        f_vb1.write(buf)

            # ----------------------------------------------------------------------
            # D. Patch IB (Indices)
            # ----------------------------------------------------------------------
            if f_ib:
                for p in range(particle_count):
                    v_start = current_v_count + p * v_per_particle
                    if mesh_fx_type == "1": # Quad
                        idx_list = [v_start, v_start + 1, v_start + 2, v_start + 2, v_start + 1, v_start + 3]
                    elif mesh_fx_type == "2": # Circle (pentagon)
                        idx_list = [
                            v_start, v_start + 1, v_start + 2,
                            v_start, v_start + 2, v_start + 3,
                            v_start, v_start + 3, v_start + 4,
                            v_start, v_start + 4, v_start + 5,
                            v_start, v_start + 5, v_start + 1,
                        ]
                    else: # Triangle
                        idx_list = [v_start, v_start + 1, v_start + 2]
                    
                    for idx_val in idx_list:
                        f_ib.write(struct.pack(fmt, idx_val))

            # Move current_v_count forward for the next curve in this part
            current_v_count += particle_count * v_per_particle

        # Close all files
        f_vb0.close()
        if f_vb2: f_vb2.close()
        if f_vb1: f_vb1.close()
        
        if f_ib:
            f_ib.close()
            
            # Print patching summaries
            print(f"[RZM-VFX]   -> VB0 patched: appended {total_new_verts} verts. Path: '{os.path.basename(vb0_path)}'")
            if vb2_path:
                print(f"[RZM-VFX]   -> VB2 (Weights) patched: appended {total_new_verts} vertices. Stride={stride_b}. Path: '{os.path.basename(vb2_path)}'")
            if vb1_path:
                print(f"[RZM-VFX]   -> VB1 (Texcoord) patched: appended {total_new_verts} vertices. Stride={stride_t}. Path: '{os.path.basename(vb1_path)}'")
            print(f"[RZM-VFX]   -> IB (Indices) patched: appended {total_new_indices} indices. Format={'R32_UINT' if stride_i==4 else 'R16_UINT'}. Path: '{os.path.basename(ib_path)}'")
            print(f"[RZM-VFX]      * INI Draw Override Setup:")
            print(f"[RZM-VFX]      * DrawIndexed = {total_new_indices}, {original_i_count}, 0")
        else:
            print(f"[RZM-VFX]   -> [ERROR] IB file '{expected_ib_name}' not found. Cannot patch indices.")

    print("\n[RZM-VFX] ==================================================")
    print("[RZM-VFX] BUFFER PATCHING COMPLETED")
    print("[RZM-VFX] ==================================================")
