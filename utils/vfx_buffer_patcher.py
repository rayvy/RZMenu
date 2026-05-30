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
    # No remapping on Python side; we do it in the compute shader on the GPU.
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

def get_mod_output_path(context):
    rzm = getattr(context.scene, "rzm", None)
    if not rzm:
        return ""
    game = rzm.game.selection if hasattr(rzm, "game") else "HonkaiStarRail"
    
    if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail']:
        if hasattr(context.scene, "xxmi"):
            return bpy.path.abspath(context.scene.xxmi.destination_path)
    elif game == 'ArknightsEndfield':
        if hasattr(context.scene, "efmi_tools_settings"):
            return bpy.path.abspath(context.scene.efmi_tools_settings.mod_output_folder)
    elif game == 'WutheringWaves':
        if hasattr(context.scene, "wwmi_tools_settings"):
            return bpy.path.abspath(context.scene.wwmi_tools_settings.mod_output_folder)
    return ""

def update_ini_uv_format(mod_root, comp_name, uv_format_val):
    import re
    for f in os.listdir(mod_root):
        if f.lower().endswith('.ini') and not f.lower().startswith('disabled'):
            ini_path = os.path.join(mod_root, f)
            try:
                with open(ini_path, 'r', encoding='utf-8', errors='ignore') as file_in:
                    content = file_in.read()
                
                blocks = re.split(r'(\[CustomShaderRZM_VFX_UV_[^\]]+\])', content)
                changed = False
                for idx in range(1, len(blocks), 2):
                    block_header = blocks[idx]
                    block_body = blocks[idx+1]
                    
                    if comp_name.lower() in block_header.lower():
                        new_body, count = re.subn(
                            r'(z116\s*=\s*)\d+', 
                            r'\g<1>' + str(int(uv_format_val)), 
                            block_body, 
                            flags=re.IGNORECASE
                        )
                        if count > 0:
                            blocks[idx+1] = new_body
                            changed = True
                            print(f"[RZM-VFX] Updated z116 to {int(uv_format_val)} in block {block_header} of {f}")
                
                if changed:
                    new_content = "".join(blocks)
                    with open(ini_path, 'w', encoding='utf-8') as file_out:
                        file_out.write(new_content)
            except Exception as e:
                print(f"[RZM-VFX] Failed to update UV format in {f}: {e}")

def get_curve_prop(obj, name, default):
    attr = f"rzm_curve_vfx_{name}"
    if hasattr(obj, attr):
        return getattr(obj, attr)
    return default

def distribute_particles(obj):
    """
    Distributes the total particle budget of a curve object among its splines
    proportionally to their volume (length * avg_radius^2).
    """
    total_budget = obj.get("RZM.CURVE_VFX.PARTICLE_COUNT", 1)
    if total_budget < 1:
        total_budget = 1
        
    spline_list = obj.data.splines
    if not spline_list:
        return []
        
    spline_weights = []
    total_weight = 0.0
    
    # 1. Compute spline weights
    for spline in spline_list:
        points = spline.bezier_points if spline.type == 'BEZIER' else spline.points
        
        # Length (approximation from control points)
        length = 0.0
        for i in range(len(points) - 1):
            p0 = points[i].co if spline.type == 'BEZIER' else points[i].co.xyz
            p1 = points[i+1].co if spline.type == 'BEZIER' else points[i+1].co.xyz
            length += (p0 - p1).length
            
        # Average radius
        avg_radius = sum([p.radius for p in points]) / len(points) if len(points) > 0 else 1.0
        
        # Weight = length * cross-sectional area (r^2)
        weight = length * (avg_radius ** 2)
        if weight <= 0.0:
            weight = 1e-5
        spline_weights.append(weight)
        total_weight += weight
        
    # 2. Distribute with normalization remaining
    final_counts = []
    assigned_sum = 0
    
    for w in spline_weights:
        if total_weight > 0.0:
            count = int(round(total_budget * (w / total_weight)))
        else:
            count = 0
        final_counts.append(count)
        assigned_sum += count
        
    # 3. Rounding error fix
    diff = total_budget - assigned_sum
    if diff != 0 and spline_weights:
        max_idx = spline_weights.index(max(spline_weights))
        final_counts[max_idx] += diff
        if final_counts[max_idx] < 0:
            final_counts[max_idx] = 0
            
    return final_counts

def pre_collect_vfx_vertex_counts(context):
    """
    Scans the scene for Curve VFX objects, computes their vertex counts,
    and populates context.scene.rzm.vfx_vertex_counts BEFORE rendering J2 template.
    Also calculates and stores spline particle distributions on Curve objects.
    """
    rzm = getattr(context.scene, "rzm", None)
    if not rzm:
        return
        
    try:
        rzm.vfx_vertex_counts.clear()
    except Exception as e:
        print(f"[RZM-VFX] Failed to clear vfx_vertex_counts: {e}")
        return

    # Find all curves in the scene with VFX enabled
    vfx_curves = [
        obj for obj in context.scene.objects 
        if obj.type == 'CURVE' and (getattr(obj, "rzm_curve_vfx_enabled", False) or obj.get("RZM.CURVE_VFX"))
    ]
    if not vfx_curves:
        return

    print(f"[RZM-VFX] Pre-collecting vertex counts for {len(vfx_curves)} Curve VFX objects.")

    # Distribute particles among splines and store them
    for curve_obj in vfx_curves:
        try:
            splines_particles = distribute_particles(curve_obj)
            curve_obj["RZM.CURVE_VFX.SPLINES_PARTICLES"] = splines_particles
            print(f"[RZM-VFX] Distributed particles for '{curve_obj.name}': {splines_particles}")
        except Exception as e:
            print(f"[RZM-VFX] Failed to distribute particles for curve '{curve_obj.name}': {e}")

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
            # Re-read spline particle counts
            splines_particles = curve_obj.get("RZM.CURVE_VFX.SPLINES_PARTICLES", [])
            particle_count = sum(splines_particles) if splines_particles else get_curve_prop(curve_obj, "particle_count", 1)
            
            mesh_fx_type = str(get_curve_prop(curve_obj, "mesh_fx_type", "0"))
            if mesh_fx_type == "1":    # Quad
                v_per_particle = 4
            elif mesh_fx_type == "2": # Circle (hexagon fan)
                v_per_particle = 7
            else:                     # Triangle (type 0) or Custom Mesh stub (type 3)
                v_per_particle = 3
            total_new_verts += particle_count * v_per_particle
            
        comp_fullname = f"{mod_name}{comp_name}"
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

    # Extract mod name dynamically for prefix cleanup
    mod_name = ""
    try:
        from ..operators.export_cache import get_cache
        cache = get_cache()
        if cache:
            mod_name = cache.get('mod_name', '')
    except Exception:
        pass
    if not mod_name:
        rzm = getattr(context.scene, "rzm", None)
        if rzm and hasattr(rzm, "export_settings"):
            mod_name = getattr(rzm.export_settings, "mod_name", "") or ""

    candidates = []

    for col in collections:
        for obj in col.objects:
            if obj.type == 'MESH':
                for comp_name, meshes in comp_map.items():
                    if obj in meshes:
                        # Rank candidates to choose the actual character mesh / anchor over helpers
                        score = 0
                        obj_name_lower = obj.name.lower()
                        comp_name_lower = comp_name.lower()
                        mod_name_lower = mod_name.lower() if mod_name else ""

                        # Heavy penalty for helper/setup meshes that aren't parts of the character
                        helper_keywords = [
                            'setup', 'color_setup', 'outline', 'shadow', 'helper',
                            'ignore', 'hidden', 'dummy', 'temp', 'anchor',
                            '_extra', '_ref', '_base', 'extra_', 'ref_',
                        ]
                        for kw in helper_keywords:
                            if kw in obj_name_lower:
                                score -= 100

                        # Deduce part_name and part_suffix (e.g. 'B')
                        part_name = obj.name
                        part_suffix = ""
                        rzm = getattr(context.scene, "rzm", None)
                        if rzm and hasattr(rzm, "component_manager"):
                            # Helper functions for prefix and component cleaning
                            def strip_prefix(val, pref):
                                if not val or not pref:
                                    return val
                                if val.lower().startswith(pref.lower()):
                                    return val[len(pref):]
                                return val

                            def clean_comp(name):
                                if not name: return ""
                                clean = name.strip()
                                if mod_name:
                                    clean = strip_prefix(clean, mod_name).strip()
                                return clean.lower()

                            target_clean = clean_comp(comp_name)
                            for comp in rzm.component_manager.components:
                                if clean_comp(comp.name) == target_clean:
                                    # Found the matching component!
                                    for part in comp.parts:
                                        # Deduce part suffix
                                        p_suf = part.name
                                        if comp_name:
                                            p_suf = strip_prefix(p_suf, comp_name)
                                        if comp.name:
                                            p_suf = strip_prefix(p_suf, comp.name)
                                        p_suf = p_suf.strip()
                                        
                                        # If there's only one part, it must be this one!
                                        if len(comp.parts) == 1:
                                            part_name = p_suf
                                            part_suffix = p_suf
                                            break
                                            
                                        # Otherwise, match via collections
                                        matched = False
                                        for c in obj.users_collection:
                                            c_lower = c.name.lower()
                                            if (comp_name.lower() + p_suf.lower()) in c_lower:
                                                matched = True
                                                break
                                            if (comp.name.lower() + p_suf.lower()) in c_lower:
                                                matched = True
                                                break
                                            if c_lower.endswith(p_suf.lower()):
                                                matched = True
                                                break
                                        if matched:
                                            part_name = p_suf
                                            part_suffix = p_suf
                                            break
                                    break

                        # Target name patterns from User's specification:
                        # CharacterName (mod_name) + ComponentName (comp_name) + PartName (part_suffix)
                        part_suf_lower = part_suffix.lower() if part_suffix else ""
                        
                        # Pattern 1: mod_name + comp_name + part_suffix (e.g. promeiahairb)
                        if mod_name_lower and comp_name_lower:
                            p1 = mod_name_lower + comp_name_lower + part_suf_lower
                            if p1 in obj_name_lower:
                                score += 1000

                        # Pattern 2: comp_name + part_suffix (e.g. hairb)
                        if comp_name_lower:
                            p2 = comp_name_lower + part_suf_lower
                            if p2 in obj_name_lower:
                                score += 500

                        # Pattern 3: mod_name + comp_name (e.g. promeiahair)
                        if mod_name_lower and comp_name_lower:
                            p3 = mod_name_lower + comp_name_lower
                            if p3 in obj_name_lower:
                                score += 200

                        # Pattern 4: comp_name (e.g. hair)
                        if comp_name_lower:
                            p4 = comp_name_lower
                            if p4 in obj_name_lower:
                                score += 100

                        # Pattern 5: if the object name ends with '-keepempty' (indicating it is the export anchor)
                        if obj_name_lower.endswith('-keepempty'):
                            score += 2000

                        # Reward meshes with vertex groups (indicating they are rigged meshes)
                        if hasattr(obj, "vertex_groups") and len(obj.vertex_groups) > 0:
                            score += 50

                        candidates.append((score, comp_name, obj, part_name))

    if candidates:
        # Sort by score descending, then by name length ascending (prefer shorter name if tie)
        candidates.sort(key=lambda x: (x[0], -len(x[2].name)), reverse=True)
        best_score, best_comp, best_obj, best_part = candidates[0]
        print(f"[RZM-VFX] Curve '{curve_obj.name}' association candidates:")
        for score, comp_name, obj, part_name in candidates:
            print(f"  - Mesh '{obj.name}' -> Score: {score} (Component: {comp_name}, Part: {part_name})")

        # PRECISION GUARD: Reject matches that are clearly helper/setup objects
        # A negative score means ONLY helper-keyword objects were found (no real character mesh)
        if best_score < 0:
            print(f"[RZM-VFX] [ERROR] Curve '{curve_obj.name}': Best candidate '{best_obj.name}' "
                  f"has negative score ({best_score}). This is a setup/helper mesh, not a character mesh. "
                  f"Skipping — place the curve in the same collection as the actual character mesh.")
            return None, None, None

        print(f"[RZM-VFX] Selected '{best_obj.name}' as best match (score={best_score}).")
        return best_comp, best_obj, best_part

    return None, None, None


def evaluate_curve_spline_points(context, curve_obj, spline_idx, num_samples=32):
    depsgraph = context.evaluated_depsgraph_get()
    
    if not curve_obj.data.splines or spline_idx >= len(curve_obj.data.splines):
        return []
        
    orig_spline = curve_obj.data.splines[spline_idx]
    if orig_spline.type == 'BEZIER':
        ctrl_points = [p.co.copy() for p in orig_spline.bezier_points]
        ctrl_radii = [p.radius for p in orig_spline.bezier_points]
    else:
        ctrl_points = [p.co.xyz.copy() for p in orig_spline.points]
        ctrl_radii = [p.radius for p in orig_spline.points]
        
    ctrl_dists = [0.0]
    curr_len = 0.0
    for i in range(1, len(ctrl_points)):
        dist = (ctrl_points[i] - ctrl_points[i-1]).length
        curr_len += dist
        ctrl_dists.append(curr_len)
        
    # Temporary copy of curve to evaluate center line of ONLY this spline without bevel
    original_data = curve_obj.data
    temp_data = original_data.copy()
    
    # Keep only the target spline
    for s_i in reversed(range(len(temp_data.splines))):
        if s_i != spline_idx:
            temp_data.splines.remove(temp_data.splines[s_i])
            
    temp_data.bevel_depth = 0.0
    temp_data.extrude = 0.0
    temp_data.bevel_object = None
    
    temp_obj = bpy.data.objects.new("temp_curve_eval", temp_data)
    context.scene.collection.objects.link(temp_obj)
    
    # Clear shape keys to prevent corruption on spline removal
    if temp_obj.data.shape_keys:
        temp_obj.shape_key_clear()
        
    # Match world matrix
    temp_obj.matrix_world = curve_obj.matrix_world.copy()
    context.view_layer.update()
    
    try:
        eval_obj = temp_obj.evaluated_get(depsgraph)
        temp_mesh = eval_obj.to_mesh()
    except Exception as e:
        print(f"[RZM-VFX] Error converting curve spline {spline_idx} to mesh: {e}")
        context.scene.collection.objects.unlink(temp_obj)
        bpy.data.objects.remove(temp_obj)
        bpy.data.curves.remove(temp_data)
        return []
        
    if not temp_mesh or not temp_mesh.vertices:
        if temp_mesh:
            eval_obj.to_mesh_clear()
        context.scene.collection.objects.unlink(temp_obj)
        bpy.data.objects.remove(temp_obj)
        bpy.data.curves.remove(temp_data)
        return []
        
    verts = [v.co.copy() for v in temp_mesh.vertices]
    eval_obj.to_mesh_clear()
    
    # Clean up temporary objects
    context.scene.collection.objects.unlink(temp_obj)
    bpy.data.objects.remove(temp_obj)
    bpy.data.curves.remove(temp_data)
    
    if len(verts) < 2:
        return []
        
    distances = [0.0]
    total_len = 0.0
    for i in range(1, len(verts)):
        dist = (verts[i] - verts[i-1]).length
        total_len += dist
        distances.append(total_len)
        
    if total_len == 0.0:
        r_val = ctrl_radii[0] if ctrl_radii else 1.0
        return [(verts[0], r_val) for _ in range(num_samples)]
        
    resampled_data = []
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
        
        # Interpolate radius based on factor
        if curr_len > 0.0 and len(ctrl_radii) >= 2:
            target_ctrl_dist = factor * curr_len
            c_idx = 0
            while c_idx < len(ctrl_dists) - 2 and ctrl_dists[c_idx+1] < target_ctrl_dist:
                c_idx += 1
            cd0 = ctrl_dists[c_idx]
            cd1 = ctrl_dists[c_idx+1]
            ct = (target_ctrl_dist - cd0) / (cd1 - cd0) if cd1 > cd0 else 0.0
            r_val = ctrl_radii[c_idx] + ct * (ctrl_radii[c_idx+1] - ctrl_radii[c_idx])
        else:
            r_val = ctrl_radii[0] if ctrl_radii else 1.0
            
        resampled_data.append((pt, r_val))
        
    return resampled_data

def get_spline_raw_vertex_counts(context, curve_obj):
    counts = []
    for s_idx in range(len(curve_obj.data.splines)):
        # Copy curve data
        temp_data = curve_obj.data.copy()
        # Keep only target spline
        for s_i in reversed(range(len(temp_data.splines))):
            if s_i != s_idx:
                temp_data.splines.remove(temp_data.splines[s_i])
        temp_data.bevel_depth = 0.0
        temp_data.extrude = 0.0
        temp_data.bevel_object = None
        
        temp_obj = bpy.data.objects.new("temp_count", temp_data)
        context.scene.collection.objects.link(temp_obj)
        
        # Clear shape keys to prevent corruption
        if temp_obj.data.shape_keys:
            temp_obj.shape_key_clear()
            
        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()
        try:
            eval_obj = temp_obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            counts.append(len(mesh.vertices))
            eval_obj.to_mesh_clear()
        except Exception as e:
            print(f"[RZM-VFX] Error getting vertex count for spline {s_idx}: {e}")
            counts.append(0)
        finally:
            context.scene.collection.objects.unlink(temp_obj)
            bpy.data.objects.remove(temp_obj)
            bpy.data.curves.remove(temp_data)
    return counts

def evaluate_curve_all_shapes(context, curve_obj, spline_idx, num_samples=32):
    """
    Evaluates spline points for all shape keys of the curve sequentially for a single spline.
    """
    if not curve_obj.data.splines or spline_idx >= len(curve_obj.data.splines):
        return [[] for _ in range(8)]
        
    shape_keys = curve_obj.data.shape_keys
    if not shape_keys or len(shape_keys.key_blocks) <= 1:
        # Static curve spline: evaluate once and duplicate 8 times
        basis_pts = evaluate_curve_spline_points(context, curve_obj, spline_idx, num_samples)
        return [list(basis_pts) for _ in range(8)]

    # Multi-spline shape keys:
    # 1. Get raw vertex counts for each spline to slice the evaluated mesh
    counts = get_spline_raw_vertex_counts(context, curve_obj)
    start_v = sum(counts[:spline_idx])
    end_v = start_v + counts[spline_idx]

    # Create temporary copy of curve data to evaluate (keeping all splines to preserve shape keys layout)
    orig_data = curve_obj.data
    temp_data = orig_data.copy()
    
    temp_data.bevel_depth = 0.0
    temp_data.bevel_object = None
    temp_data.extrude = 0.0
    
    temp_obj = bpy.data.objects.new("temp_curve_eval_shapes", temp_data)
    context.scene.collection.objects.link(temp_obj)
    temp_obj.matrix_world = curve_obj.matrix_world.copy()
    
    shapes_pts = []
    
    try:
        keys = list(temp_obj.data.shape_keys.key_blocks)
        orig_values = [kb.value for kb in keys]
        
        for k_idx in range(min(len(keys), 8)):
            for kb in keys:
                kb.value = 0.0
            if k_idx > 0:
                keys[k_idx].value = 1.0
                
            context.view_layer.update()
            depsgraph = context.evaluated_depsgraph_get()
            eval_obj = temp_obj.evaluated_get(depsgraph)
            
            try:
                temp_mesh = eval_obj.to_mesh()
            except Exception as e:
                print(f"[RZM-VFX] Spline {spline_idx} Shape {k_idx} eval error: {e}")
                shapes_pts.append([])
                continue
                
            verts = [v.co.copy() for v in temp_mesh.vertices[start_v:end_v]]
            eval_obj.to_mesh_clear()
            
            if len(verts) < 2:
                shapes_pts.append([])
                continue
                
            # Control points and radii from the target spline
            spline = temp_obj.data.splines[spline_idx]
            if spline.type == 'BEZIER':
                ctrl_points = [p.co.copy() for p in spline.bezier_points]
                ctrl_radii = [p.radius for p in spline.bezier_points]
            else:
                ctrl_points = [p.co.xyz.copy() for p in spline.points]
                ctrl_radii = [p.radius for p in spline.points]
                
            ctrl_dists = [0.0]
            curr_len = 0.0
            for i in range(1, len(ctrl_points)):
                curr_len += (ctrl_points[i] - ctrl_points[i-1]).length
                ctrl_dists.append(curr_len)
                
            distances = [0.0]
            total_len = 0.0
            for i in range(1, len(verts)):
                total_len += (verts[i] - verts[i-1]).length
                distances.append(total_len)
                
            if total_len == 0.0:
                r_val = ctrl_radii[0] if ctrl_radii else 1.0
                shapes_pts.append([(verts[0], r_val)] * num_samples)
                continue
                
            resampled = []
            for j in range(num_samples):
                factor = j / (num_samples - 1)
                target = factor * total_len
                idx = 0
                while idx < len(distances) - 2 and distances[idx+1] < target:
                    idx += 1
                d0, d1 = distances[idx], distances[idx+1]
                t = (target - d0) / (d1 - d0) if d1 > d0 else 0.0
                pt = verts[idx].lerp(verts[min(idx+1, len(verts)-1)], t)
                
                # Radius from ctrl-points via factor
                if curr_len > 0.0 and len(ctrl_radii) >= 2:
                    target_ctrl_dist = factor * curr_len
                    c_idx = 0
                    while c_idx < len(ctrl_dists) - 2 and ctrl_dists[c_idx+1] < target_ctrl_dist:
                        c_idx += 1
                    cd0, cd1 = ctrl_dists[c_idx], ctrl_dists[c_idx+1]
                    ct = (target_ctrl_dist - cd0) / (cd1 - cd0) if cd1 > cd0 else 0.0
                    r_val = ctrl_radii[c_idx] + ct * (ctrl_radii[c_idx+1] - ctrl_radii[c_idx])
                else:
                    r_val = ctrl_radii[0] if ctrl_radii else 1.0
                resampled.append((pt, r_val))
                
            shapes_pts.append(resampled)
    finally:
        context.scene.collection.objects.unlink(temp_obj)
        bpy.data.objects.remove(temp_obj)
        bpy.data.curves.remove(temp_data)
        
    while len(shapes_pts) < 8:
        last = shapes_pts[-1] if shapes_pts else []
        shapes_pts.append(list(last))
        
    return shapes_pts[:8]



def sample_curve_at_progress(resampled_data, t):
    """
    Interpolates a position along the 32 sampled curve points.
    t is between 0.0 and 1.0.
    """
    if not resampled_data:
        return Vector((0.0, 0.0, 0.0))
    if len(resampled_data) == 1:
        return resampled_data[0][0]
    t = max(0.0, min(1.0, t))
    t_spline = t * 31.0
    idx0 = int(math.floor(t_spline))
    idx1 = min(idx0 + 1, 31)
    factor = t_spline - idx0
    
    pt0 = resampled_data[idx0][0]
    pt1 = resampled_data[idx1][0]
    return pt0.lerp(pt1, factor)

def get_path_progress(phase, tl_start, tl_mid, tl_end):
    """
    Computes path progress matching vfx_curve_cs.hlsl timeline easing math.
    """
    cycle = phase
    denom = max(tl_end - tl_start, 1e-5)
    active_t = max(0.0, min(1.0, (cycle - tl_start) / denom))
    k = max(0.01, min(0.99, (tl_mid - tl_start) / denom))
    A = (0.5 - k) / (k * k - k)
    B = 1.0 - A
    path_progress = max(0.0, min(1.0, A * active_t * active_t + B * active_t))
    return path_progress

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

def cache_object_matches_part(obj_name, component_name, part_suffix):
    """
    Match cache objects that belong to the same rendered part.
    Handles numbered Blender duplicates such as "HairB.001".
    """
    if not obj_name:
        return False

    name = str(obj_name).lower().strip()
    component = str(component_name).lower().strip()
    suffix = str(part_suffix).lower().strip()
    base_name = f"{component}{suffix}" if suffix else component
    if not suffix:
        return True

    if name == base_name:
        return True
    if name.startswith(base_name + "."):
        return True
    if name.startswith(base_name + "-"):
        return True
    if name.startswith(base_name + "_"):
        return True
    if name.endswith(base_name):
        return True
    if f"{base_name}-" in name or f"_{base_name}" in name:
        return True

    return False

def float_to_half(f):
    return int(np.float16(f).view(np.uint16))



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

def get_armature_or_root(obj):
    if not obj:
        return None
    if hasattr(obj, "modifiers"):
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                return mod.object
    parent = obj.parent
    last_valid = obj
    while parent:
        if parent.type == 'ARMATURE':
            return parent
        if parent.type == 'EMPTY' and not parent.parent:
            return parent
        last_valid = parent
        parent = parent.parent
    return last_valid

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

    # Build list of virtual curves (one per spline)
    virtual_curves = []
    for curve_obj in vfx_curves:
        comp_name, target_mesh, part_name = find_associated_mesh_and_component(context, curve_obj)
        if not target_mesh:
            print(f"[RZM-VFX] [ERROR] Curve '{curve_obj.name}' is invalid: no associated mesh component.")
            continue
            
        splines_particles = curve_obj.get("RZM.CURVE_VFX.SPLINES_PARTICLES", [])
        num_splines = len(curve_obj.data.splines)
        target_budget = curve_obj.get("RZM.CURVE_VFX.PARTICLE_COUNT", 1)
        if not splines_particles or len(splines_particles) != num_splines or sum(splines_particles) != target_budget:
            splines_particles = distribute_particles(curve_obj)
            curve_obj["RZM.CURVE_VFX.SPLINES_PARTICLES"] = splines_particles
            
        for s_idx in range(num_splines):
            p_count = splines_particles[s_idx]
            virtual_curves.append({
                'obj': curve_obj,
                'spline_idx': s_idx,
                'particle_count': p_count,
                'comp_name': comp_name,
                'target_mesh': target_mesh,
                'part_name': part_name
            })

    # Let's accumulate all curve data points
    all_curve_bytes = bytearray()
    valid_curve_count = 0
    curve_mapping = {} # maps (curve_name, spline_idx) to index in curve_data.buf
    curve_shapes_cache = {} # maps (curve_name, spline_idx) to shapes_resampled

    for idx, v_curve in enumerate(virtual_curves):
        curve_obj = v_curve['obj']
        s_idx = v_curve['spline_idx']
        comp_name = v_curve['comp_name']
        target_mesh = v_curve['target_mesh']

        profile_raw = get_curve_prop(curve_obj, "coordinate_remap_profile", "AUTO")
        profile = resolve_coordinate_remap_profile(context, profile_raw)
        
        # Sample points for all 8 shapes (returns list of 8 lists, each with 32 (pt, radius) tuples)
        shapes_resampled = evaluate_curve_all_shapes(context, curve_obj, s_idx, num_samples=32)
        if not shapes_resampled or any(len(s) < 2 for s in shapes_resampled):
            print(f"[RZM-VFX] [ERROR] Curve '{curve_obj.name}' spline {s_idx} evaluation returned insufficient points.")
            continue
            
        curve_shapes_cache[(curve_obj.name, s_idx)] = shapes_resampled

        # Process each shape
        for k in range(8):
            resampled_data = shapes_resampled[k]
            
            # Remap to target mesh's local coordinates
            local_pts = []
            radii = []
            for pt, r_val in resampled_data:
                wpos = curve_obj.matrix_world @ pt
                lpos = target_mesh.matrix_world.inverted() @ wpos
                local_pts.append(lpos)
                radii.append(r_val)

            # Apply buffer coordinate remap
            remapped_pts = []
            for lpos in local_pts:
                remap_pt = remap_curve_point_to_buffer(lpos, local_pts[0], profile)
                remapped_pts.append(remap_pt)

            # Pack 32 sampled points for this shape: 40 bytes each
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
                
                # Pack local radius into the 10th float (point radius * 0.01 meters baseline)
                r_packed = radii[j] * 0.01

                # Pack
                point_data = struct.pack(
                    '<fffffffff',
                    pt.x, pt.y, pt.z,
                    tangent.x, tangent.y, tangent.z,
                    normal.x, normal.y, normal.z
                )
                point_data += struct.pack('<f', r_packed)
                all_curve_bytes.extend(point_data)

        # Determine number of active shape keys
        num_shapes = 0
        if curve_obj.data.shape_keys and curve_obj.data.shape_keys.key_blocks:
            num_shapes = min(7, len(curve_obj.data.shape_keys.key_blocks) - 1)

        # 257th point contains metadata
        mesh_fx_type = float(get_curve_prop(curve_obj, "mesh_fx_type", "0"))
        packed_fx_type = mesh_fx_type + float(num_shapes) * 10.0
        
        meta_size_base = float(get_curve_prop(curve_obj, "particle_size_base", 0.05))
        meta_size_start = float(get_curve_prop(curve_obj, "particle_size_start", 1.0))
        meta_size_end = float(get_curve_prop(curve_obj, "particle_size_end", 0.2))
        
        # cycle duration (fallback to speed via conversion)
        speed_val = get_curve_prop(curve_obj, "speed", 0.5)
        default_dur = 1.0 / speed_val if speed_val > 0.0 else 2.0
        meta_cycle_dur = float(get_curve_prop(curve_obj, "cycle_duration", default_dur))
        
        meta_dispersion = float(get_curve_prop(curve_obj, "dispersion_scale", 1.0))
        meta_phase_rand = float(get_curve_prop(curve_obj, "phase_randomness", 1.0))
        meta_pos_rand = float(get_curve_prop(curve_obj, "pos_randomness", 0.0))
        meta_size_rand_min = max(0.0, min(2.0, float(get_curve_prop(curve_obj, "size_rand_min", 1.0))))
        meta_size_rand_max = max(0.0, min(2.0, float(get_curve_prop(curve_obj, "size_rand_max", 1.0))))
        meta_tl_start = max(0.0, min(1.0, float(get_curve_prop(curve_obj, "timeline_start_pos", 0.0))))
        meta_tl_mid = max(0.0, min(1.0, float(get_curve_prop(curve_obj, "timeline_mid_pos", 0.5))))
        meta_tl_end = float(get_curve_prop(curve_obj, "timeline_end_pos", 1.0))
        
        # Pack tl_start and tl_mid as: start_int + mid_int * 1000
        int_start = int(round(meta_tl_start * 100.0))
        int_mid = int(round(meta_tl_mid * 100.0))
        packed_tls = float(int_start + int_mid * 1000)
        
        # Pack size_rand_min and size_rand_max as: min_int + max_int * 1000
        int_min = int(round(meta_size_rand_min * 100.0))
        int_max = int(round(meta_size_rand_max * 100.0))
        packed_rand = float(int_min + int_max * 1000)
        
        meta_data = struct.pack(
            '<ffffffffff',
            packed_fx_type + meta_tl_end * 0.1, meta_size_base, meta_size_start,  # position.xyz
            meta_size_end, meta_cycle_dur, meta_dispersion,                      # tangent.xyz
            meta_phase_rand, meta_pos_rand, packed_tls,                          # normal.xyz
            packed_rand                                                          # u
        )
        all_curve_bytes.extend(meta_data)

        curve_mapping[(curve_obj.name, s_idx)] = valid_curve_count
        valid_curve_count += 1
        print(f"[RZM-VFX] Curve '{curve_obj.name}' spline {s_idx} exported at index {valid_curve_count-1} for component '{comp_name}'")

    if valid_curve_count == 0:
        print("[RZM-VFX] [WARNING] No valid curves were exported. Aborting patch.")
        return

    # Write the collected curve_data.buf
    with open(curve_buf_path, 'wb') as f:
        f.write(all_curve_bytes)
    print(f"[RZM-VFX] Wrote {valid_curve_count} curve splines ({valid_curve_count * 257 * 40} bytes) to '{curve_buf_path}'")

    # Write curve_weight_data.buf: 8 shapes × 32 points per curve, stride=32 (4xfloat + 4xuint)
    weight_buf_path = os.path.join(res_dir, "curve_weight_data.buf")
    all_weight_bytes = bytearray()
    
    # Cache KDTree evaluations per reference mesh name to avoid redundant builds
    ref_kd_cache = {}
    
    for v_curve in virtual_curves:
        curve_obj = v_curve['obj']
        s_idx = v_curve['spline_idx']
        if (curve_obj.name, s_idx) not in curve_mapping:
            continue
            
        shapes_resampled = curve_shapes_cache.get((curve_obj.name, s_idx), [])

        weight_indices = list(get_curve_prop(curve_obj, "weight_indices", (-1, -1, -1, -1)))
        weight_values  = list(get_curve_prop(curve_obj, "weight_values", (0.0, 0.0, 0.0, 0.0)))
        fallback_idx = [int(x) if x != -1 else 0 for x in weight_indices]
        fallback_w   = [float(w) for w in weight_values]

        # Build/get KDTree for weight reference
        target_mesh = v_curve['target_mesh']
        ref_mesh = curve_obj.rzm_curve_vfx_weight_reference
        if not ref_mesh or ref_mesh.type != 'MESH':
            ref_mesh = target_mesh
        kd_w = None; vg_map_w = {}; bone_to_id_w = {}; ref_data_w = None
        
        if ref_mesh and ref_mesh.type == 'MESH':
            if ref_mesh.name in ref_kd_cache:
                kd_w, vg_map_w, bone_to_id_w, ref_data_w = ref_kd_cache[ref_mesh.name]
            else:
                try:
                    depsgraph = context.evaluated_depsgraph_get()
                    ref_data_w = ref_mesh.evaluated_get(depsgraph).data
                    vg_map_w   = {vg.index: vg.name for vg in ref_mesh.vertex_groups}
                    for vg in ref_mesh.vertex_groups:
                        bone_to_id_w[vg.name] = vg.index
                    from mathutils.kdtree import KDTree
                    kd_w = KDTree(len(ref_data_w.vertices))
                    for vi, v in enumerate(ref_data_w.vertices):
                        kd_w.insert(ref_mesh.matrix_world @ v.co, vi)
                    kd_w.balance()
                    # Cache it
                    ref_kd_cache[ref_mesh.name] = (kd_w, vg_map_w, bone_to_id_w, ref_data_w)
                except Exception as e:
                    print(f"[RZM-VFX] [WARN] Weight KDTree failed for weight export: {e}")
                    kd_w = None

        def sample_weight_at_world_pos(wpos):
            """Look up top-4 bone weights at a world-space position via KDTree."""
            if not kd_w:
                return fallback_idx, fallback_w
            _, ref_idx, _ = kd_w.find(wpos)
            v = ref_data_w.vertices[ref_idx]
            bone_groups = []
            for g in v.groups:
                if g.weight > 1e-5:
                    gname = vg_map_w.get(g.group)
                    if gname and gname in bone_to_id_w:
                        bone_groups.append((bone_to_id_w[gname], g.weight))
            bone_groups.sort(key=lambda x: x[1], reverse=True)
            bone_groups = bone_groups[:4]
            if bone_groups:
                tw = sum(w for _, w in bone_groups)
                bone_groups = [(idx, w / tw) for idx, w in bone_groups] if tw > 0 else bone_groups
                while len(bone_groups) < 4:
                    bone_groups.append((0, 0.0))
                return [bg[0] for bg in bone_groups], [bg[1] for bg in bone_groups]
            return fallback_idx, fallback_w

        # Write 8 shapes × 32 points
        for shape_idx in range(8):
            shape_pts = shapes_resampled[shape_idx] if shape_idx < len(shapes_resampled) else []
            for pt_idx in range(32):
                t = pt_idx / 31.0
                if shape_pts and len(shape_pts) >= 2:
                    pos_local = sample_curve_at_progress(shape_pts, t)
                    wpos = curve_obj.matrix_world @ pos_local
                    out_idx, out_w = sample_weight_at_world_pos(wpos)
                else:
                    out_idx, out_w = fallback_idx, fallback_w
                all_weight_bytes.extend(struct.pack('<ffffIIII',
                    out_w[0], out_w[1], out_w[2], out_w[3],
                    out_idx[0], out_idx[1], out_idx[2], out_idx[3]))

    with open(weight_buf_path, 'wb') as f:
        f.write(all_weight_bytes)
    print(f"[RZM-VFX] Wrote curve_weight_data.buf ({len(all_weight_bytes)} bytes, 8shapes×32pts per curve spline) to '{weight_buf_path}'")

    has_any_animated_uv = any(getattr(v_curve['obj'], "rzm_curve_vfx_animated_uv", False) for v_curve in virtual_curves)
    if has_any_animated_uv:
        uv_buf_path = os.path.join(res_dir, "curve_uv_data.buf")
        all_uv_bytes = bytearray()
        for v_curve in virtual_curves:
            curve_obj = v_curve['obj']
            s_idx = v_curve['spline_idx']
            if (curve_obj.name, s_idx) not in curve_mapping:
                continue
            if getattr(curve_obj, "rzm_curve_vfx_animated_uv", False):
                dup_start = list(getattr(curve_obj, "rzm_curve_vfx_uv_dup_start", (0.0, 0.0)))
                dup_end = list(getattr(curve_obj, "rzm_curve_vfx_uv_dup_end", (0.0, 0.0)))
            else:
                dup_start = [0.0, 0.0]
                dup_end = [0.0, 0.0]
            all_uv_bytes.extend(struct.pack('<ffff', dup_start[0], dup_start[1], dup_end[0], dup_end[1]))
            
        with open(uv_buf_path, 'wb') as f:
            f.write(all_uv_bytes)
        print(f"[RZM-VFX] Wrote curve_uv_data.buf ({len(all_uv_bytes)} bytes) to '{uv_buf_path}'")

        # Copy compute shader to mod modules directory
        addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src_shader = os.path.join(addon_dir, "basic_pack", "modules", "vfx_uv_cs.hlsl")
        dst_shader_dir = os.path.join(mod_root, "modules")
        if os.path.exists(src_shader):
            os.makedirs(dst_shader_dir, exist_ok=True)
            import shutil
            shutil.copy2(src_shader, os.path.join(dst_shader_dir, "vfx_uv_cs.hlsl"))
            print(f"[RZM-VFX] Copied vfx_uv_cs.hlsl to {dst_shader_dir}")

    # 2. Group curves by target component and part
    curves_by_part = {}
    for v_curve in virtual_curves:
        curve_obj = v_curve['obj']
        s_idx = v_curve['spline_idx']
        if (curve_obj.name, s_idx) not in curve_mapping:
            continue
        comp_name = v_curve['comp_name']
        part_name = v_curve['part_name']
        target_mesh = v_curve['target_mesh']
        key = (comp_name, part_name, target_mesh)
        if key not in curves_by_part:
            curves_by_part[key] = []
        curves_by_part[key].append(v_curve)

    # 3. Patch component buffers per group
    for (comp_name, part_name, target_mesh), v_curve_list in curves_by_part.items():
        # Calculate total vertices and indices to be appended
        total_new_verts = 0
        total_new_indices = 0
        for v_curve in v_curve_list:
            particle_count = v_curve['particle_count']
            mesh_fx_type = str(get_curve_prop(v_curve['obj'], "mesh_fx_type", "0"))
            if mesh_fx_type == "1":    # Quad
                v_per_particle, i_per_particle = 4, 6
            elif mesh_fx_type == "2": # Circle (hexagon: 7 verts, 6 tris = 18 indices)
                v_per_particle, i_per_particle = 7, 18
            else:                     # Triangle (type 0) or Custom Mesh stub (type 3)
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

        # Determine original vertex and index counts.
        comp_cache = cache.get('components', {}).get(comp_name, {})
        
        # 1. Determine original_v_count from Cache
        cache_v_count = comp_cache.get('n_verts')
        if cache_v_count is None:
            # Fallback: assume the file size on disk is the clean size
            file_size_vb0 = os.path.getsize(vb0_path)
            cache_v_count = file_size_vb0 // 40
            
        # Check if the VB0 file on disk was already patched in a previous run.
        # It is considered patched if and only if its size is exactly equal to (cache_v_count + total_new_verts) * 40.
        expected_patched_vb0_size = (cache_v_count + total_new_verts) * 40
        file_size_vb0 = os.path.getsize(vb0_path)
        
        is_vb0_already_patched = (file_size_vb0 == expected_patched_vb0_size and total_new_verts > 0)
        
        if is_vb0_already_patched:
            # Revert the previous patch by truncating back to the clean size
            original_v_count = cache_v_count
            print(f"[RZM-VFX]   * Detected previously patched VB0 ({file_size_vb0} bytes). Truncating to clean size {original_v_count * 40} bytes.")
            with open(vb0_path, 'r+b') as f:
                f.truncate(original_v_count * 40)
        else:
            # Trust the file size on disk as the clean original vertex count!
            original_v_count = file_size_vb0 // 40
            print(f"[RZM-VFX]   * Trusting VB0 size on disk as original size: {file_size_vb0} bytes -> {original_v_count} vertices.")

        # 2. Determine original_i_count from Cache
        cache_i_count = 0
        matched_ib_entries = []
        for obj in comp_cache.get('objects', []):
            ib_count = int(obj.get('ib_count') or 0)
            if ib_count <= 0:
                continue

            obj_name = obj.get('name', '')
            obj_part_suffix = obj.get('part_suffix')
            if obj_part_suffix is not None:
                if str(obj_part_suffix).lower().strip() != str(part_suffix).lower().strip():
                    continue
            else:
                if not cache_object_matches_part(obj_name, comp_name, part_suffix):
                    continue

            cache_i_count += ib_count
            matched_ib_entries.append((obj_name, ib_count))

        if matched_ib_entries:
            if len(matched_ib_entries) > 1:
                match_desc = ", ".join(f"{name}({count})" for name, count in matched_ib_entries)
                print(f"[RZM-VFX]   * IB cache matches for '{comp_name}/{part_name}': {match_desc} -> total {cache_i_count}")
            else:
                match_name, match_count = matched_ib_entries[0]
                print(f"[RZM-VFX]   * IB cache match for '{comp_name}/{part_name}': {match_name}({match_count}) -> total {cache_i_count}")

        if cache_i_count == 0:
            # Fallback: assume the file size on disk is the clean size
            if ib_path:
                ib_size_before = os.path.getsize(ib_path)
                stride_i_temp = 4 if ib_size_before % 4 == 0 else 2
                cache_i_count = ib_size_before // stride_i_temp
            else:
                cache_i_count = 0

        # Check if the IB file on disk was already patched in a previous run.
        # We determine the index stride first
        stride_i = 4
        is_ib_already_patched = False
        if ib_path:
            file_size_ib = os.path.getsize(ib_path)
            # Stride check: if we assume it's patched, the total indices would be cache_i_count + total_new_indices
            if file_size_ib == (cache_i_count + total_new_indices) * 4 and total_new_indices > 0:
                stride_i = 4
                is_ib_already_patched = True
            elif file_size_ib == (cache_i_count + total_new_indices) * 2 and total_new_indices > 0:
                stride_i = 2
                is_ib_already_patched = True
            else:
                stride_i = 4 if file_size_ib % 4 == 0 else 2

            if is_ib_already_patched:
                original_i_count = cache_i_count
                print(f"[RZM-VFX]   * Detected previously patched IB ({file_size_ib} bytes). Truncating to clean size {original_i_count * stride_i} bytes.")
                with open(ib_path, 'r+b') as f:
                    f.truncate(original_i_count * stride_i)
            else:
                # Trust the file size on disk as the clean original index count!
                original_i_count = file_size_ib // stride_i
                print(f"[RZM-VFX]   * Trusting IB size on disk as original size: {file_size_ib} bytes -> {original_i_count} indices.")
        else:
            original_i_count = 0

        # Determine strides using find_stride_from_ini
        stride_b = 32
        if vb2_path:
            stride_b = find_stride_from_ini(mod_root, f"Resource{mod_name}{comp_name}Blend", 32)
            
        stride_t = 20
        if vb1_path:
            stride_t = find_stride_from_ini(mod_root, f"Resource{mod_name}{comp_name}Texcoord", 20)

        # Auto-detect if UV coordinates are stored as float32 or half-float (float16)
        uv_format = 'float'  # Default fallback
        if vb1_path and os.path.exists(vb1_path) and os.path.getsize(vb1_path) >= stride_t:
            try:
                with open(vb1_path, 'rb') as f_detect:
                    for v_idx in range(min(20, original_v_count)):
                        f_detect.seek(v_idx * stride_t)
                        v_data = f_detect.read(stride_t)
                        if len(v_data) >= 8:
                            f_u, f_v = struct.unpack('<ff', v_data[0:8])
                            import numpy as np
                            h_u_raw, h_v_raw = struct.unpack('<HH', v_data[0:4])
                            h_u = float(np.frombuffer(struct.pack('<H', h_u_raw), dtype=np.float16)[0])
                            h_v = float(np.frombuffer(struct.pack('<H', h_v_raw), dtype=np.float16)[0])
                            
                            # If they are not both zero, make a decision
                            if (f_u != 0.0 or f_v != 0.0) or (h_u != 0.0 or h_v != 0.0):
                                float_sensible = (-4.0 <= f_u <= 4.0) and (-4.0 <= f_v <= 4.0) and not (math.isnan(f_u) or math.isnan(f_v))
                                half_sensible = (-4.0 <= h_u <= 4.0) and (-4.0 <= h_v <= 4.0) and not (math.isnan(h_u) or math.isnan(h_v))
                                
                                if float_sensible and half_sensible:
                                    if 0.0 < abs(f_u) < 1e-4 or 0.0 < abs(f_v) < 1e-4:
                                        uv_format = 'half'
                                    else:
                                        uv_format = 'float'
                                elif half_sensible:
                                    uv_format = 'half'
                                else:
                                    uv_format = 'float'
                                break
                print(f"[RZM-VFX]   * UV Format Detection -> Detected: {uv_format}")
                uv_format_val = 1 if uv_format == 'half' else 0
                has_comp_animated_uv = any(getattr(vc['obj'], "rzm_curve_vfx_animated_uv", False) for vc in v_curve_list)
                if has_comp_animated_uv:
                    update_ini_uv_format(mod_root, comp_name, uv_format_val)
            except Exception as e:
                print(f"[RZM-VFX]   * UV Format Detection error: {e}")

        # Truncate and clean up previously patched bytes if detected
        print(f"[RZM-VFX] Cleaning and preparing buffers for patching:")
        print(f"[RZM-VFX]   * Original vertex count: {original_v_count}")
        print(f"[RZM-VFX]   * Original index count: {original_i_count}")
        print(f"[RZM-VFX]   * Strides - Position: 40, Blend: {stride_b}, Texcoord: {stride_t}")
        
        # Position (already truncated in the check phase if is_vb0_already_patched)
        # Blend (Weights)
        if vb2_path and is_vb0_already_patched:
            clean_vb2_size = original_v_count * stride_b
            if os.path.getsize(vb2_path) > clean_vb2_size:
                print(f"[RZM-VFX]   * Truncating VB2 to {clean_vb2_size} bytes")
                with open(vb2_path, 'r+b') as f:
                    f.truncate(clean_vb2_size)
                    
        # Texcoord
        if vb1_path and is_vb0_already_patched:
            clean_vb1_size = original_v_count * stride_t
            if os.path.getsize(vb1_path) > clean_vb1_size:
                print(f"[RZM-VFX]   * Truncating VB1 to {clean_vb1_size} bytes")
                with open(vb1_path, 'r+b') as f:
                    f.truncate(clean_vb1_size)
                    
        # IB (Indices) (already truncated in the check phase if is_ib_already_patched)
        fmt = '<I' if stride_i == 4 else '<H'

        # Open files for appending
        f_vb0 = open(vb0_path, 'ab')
        f_vb2 = open(vb2_path, 'ab') if vb2_path else None
        f_vb1 = open(vb1_path, 'ab') if vb1_path else None
        f_ib = open(ib_path, 'ab') if ib_path else None

        current_v_count = original_v_count

        # Iterate and write each virtual curve's data
        for v_curve in v_curve_list:
            curve_obj = v_curve['obj']
            s_idx = v_curve['spline_idx']
            curve_idx = curve_mapping[(curve_obj.name, s_idx)]
            particle_count = v_curve['particle_count']
            
            mesh_fx_type = str(get_curve_prop(curve_obj, "mesh_fx_type", "0"))
            mesh_fx_size_base = get_curve_prop(curve_obj, "mesh_fx_size_base", 0.05)
            tri_aspect = get_curve_prop(curve_obj, "tri_aspect", 1.0)
            
            weight_indices = list(get_curve_prop(curve_obj, "weight_indices", (-1, -1, -1, -1)))
            weight_values = list(get_curve_prop(curve_obj, "weight_values", (0.0, 0.0, 0.0, 0.0)))
            
            if mesh_fx_type == "1":    # Quad
                v_per_particle, i_per_particle = 4, 6
            elif mesh_fx_type == "2": # Circle (hexagon: 7 verts, 6 tris = 18 indices)
                v_per_particle, i_per_particle = 7, 18
            else:                     # Triangle (type 0) or Custom Mesh stub (type 3)
                v_per_particle, i_per_particle = 3, 3
                
            # Pre-generate particle parameters to share phase offsets between VB0 and VB2 loops
            particles_params = []
            for p in range(particle_count):
                phase = random.random()
                speed_scale = random.uniform(0.8, 1.2)
                # Random unit direction in 3D
                theta = random.uniform(0, 2.0 * math.pi)
                phi = random.uniform(0, math.pi)
                dir_x = math.sin(phi) * math.cos(theta)
                dir_y = math.cos(phi)
                dir_z = math.sin(phi) * math.sin(theta)
                particles_params.append((phase, speed_scale, dir_x, dir_y, dir_z))

            # Build/get KDTree for weight reference
            ref_mesh = curve_obj.rzm_curve_vfx_weight_reference
            if not ref_mesh or ref_mesh.type != 'MESH':
                ref_mesh = target_mesh
            kd = None
            vg_map = {}
            bone_to_id = {}
            ref_mesh_data = None
            if ref_mesh and ref_mesh.type == 'MESH':
                if ref_mesh.name in ref_kd_cache:
                    kd, vg_map, bone_to_id, ref_mesh_data = ref_kd_cache[ref_mesh.name]
                else:
                    try:
                        depsgraph = context.evaluated_depsgraph_get()
                        ref_eval = ref_mesh.evaluated_get(depsgraph)
                        ref_mesh_data = ref_eval.data
                        vg_map = {vg.index: vg.name for vg in ref_mesh.vertex_groups}
                        for vg in ref_mesh.vertex_groups:
                            bone_to_id[vg.name] = vg.index
                                
                        from mathutils.kdtree import KDTree
                        kd = KDTree(len(ref_mesh_data.vertices))
                        for v_idx, v in enumerate(ref_mesh_data.vertices):
                            world_pos = ref_mesh.matrix_world @ v.co
                            kd.insert(world_pos, v_idx)
                        kd.balance()
                        # Cache it
                        ref_kd_cache[ref_mesh.name] = (kd, vg_map, bone_to_id, ref_mesh_data)
                        print(f"[RZM-VFX] Built KDTree for weight reference '{ref_mesh.name}' with {len(ref_mesh_data.vertices)} vertices.")
                    except Exception as e:
                        print(f"[RZM-VFX] Error building KDTree for reference mesh: {e}")
                        kd = None

            # ----------------------------------------------------------------------
            # A. Patch VB0 (Position)
            # ----------------------------------------------------------------------
            for p in range(particle_count):
                phase, speed_scale, dir_x, dir_y, dir_z = particles_params[p]
                
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
                    elif mesh_fx_type == "2": # Circle (hexagon fan: center + 6 outer)
                        if v_idx == 0:
                            local_pos = (0.0, 0.0, 0.0)
                        else:
                            angle = (v_idx - 1) * (2.0 * math.pi / 6.0)
                            local_pos = (math.cos(angle) * tri_aspect, math.sin(angle), 0.0)
                    else: # Triangle (type 0 or Custom Mesh stub type 3)
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
                        '<fffffffff',
                        pos_x, pos_y, pos_z,
                        phase, speed_scale, float(curve_idx),
                        dir_x, dir_y, dir_z
                    )
                    v_data += struct.pack('<f', float(v_idx))
                    f_vb0.write(v_data)

            # ----------------------------------------------------------------------
            # B. Patch VB2 (Blend)
            # ----------------------------------------------------------------------
            if f_vb2:
                tl_start = get_curve_prop(curve_obj, "timeline_start_pos", 0.0)
                tl_mid = get_curve_prop(curve_obj, "timeline_mid_pos", 0.5)
                tl_end = get_curve_prop(curve_obj, "timeline_end_pos", 1.0)
                
                num_shapes = 0
                if curve_obj.data.shape_keys and curve_obj.data.shape_keys.key_blocks:
                    num_shapes = min(7, len(curve_obj.data.shape_keys.key_blocks) - 1)
                
                shapes_resampled = curve_shapes_cache.get((curve_obj.name, s_idx))
                if not shapes_resampled:
                    shapes_resampled = evaluate_curve_all_shapes(context, curve_obj, s_idx, num_samples=32)
                
                for p in range(particle_count):
                    phase, speed_scale, dir_x, dir_y, dir_z = particles_params[p]
                    
                    if kd and shapes_resampled and len(shapes_resampled) > 0:
                        path_progress = get_path_progress(phase, tl_start, tl_mid, tl_end)
                        if num_shapes == 0:
                            pos = sample_curve_at_progress(shapes_resampled[0], path_progress)
                        else:
                            t_scaled = path_progress * num_shapes
                            k0 = int(math.floor(t_scaled))
                            k1 = min(k0 + 1, num_shapes)
                            f = t_scaled - k0
                            pos_k0 = sample_curve_at_progress(shapes_resampled[k0], path_progress)
                            pos_k1 = sample_curve_at_progress(shapes_resampled[k1], path_progress)
                            pos = pos_k0.lerp(pos_k1, f)
                            
                        # Transform to world space
                        wpos = curve_obj.matrix_world @ pos
                        _, ref_idx, _ = kd.find(wpos)
                        v = ref_mesh_data.vertices[ref_idx]
                        
                        # Collect all valid bone groups, sort by weight descending, take top 4
                        bone_groups = []
                        for g in v.groups:
                            if g.weight > 1e-5:
                                group_name = vg_map.get(g.group)
                                if group_name and group_name in bone_to_id:
                                    bone_groups.append((bone_to_id[group_name], g.weight))
                        bone_groups.sort(key=lambda x: x[1], reverse=True)
                        bone_groups = bone_groups[:4]
                        
                        if bone_groups:
                            total_w = sum(w for _, w in bone_groups)
                            if total_w > 0:
                                bone_groups = [(idx, w / total_w) for idx, w in bone_groups]
                            while len(bone_groups) < 4:
                                bone_groups.append((0, 0.0))
                            clean_idx = [bg[0] for bg in bone_groups]
                            clean_w   = [bg[1] for bg in bone_groups]
                        else:
                            clean_idx = [int(idx) if idx != -1 else 0 for idx in weight_indices]
                            clean_w = [float(w) for w in weight_values]
                    else:
                        clean_idx = [int(idx) if idx != -1 else 0 for idx in weight_indices]
                        clean_w = [float(w) for w in weight_values]


                        
                    for v_idx in range(v_per_particle):
                        buf = bytearray(stride_b)
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
                uv_offset = get_curve_prop(curve_obj, "uv_offset", (0.0, 0.0))
                uv_scale = get_curve_prop(curve_obj, "uv_scale", (1.0, 1.0))
                u_min, v_min = uv_offset[0], uv_offset[1]
                u_max, v_max = uv_offset[0] + uv_scale[0], uv_offset[1] + uv_scale[1]
                u_center = (u_min + u_max) * 0.5
                v_center = (v_min + v_max) * 0.5
                u_radius = (u_max - u_min) * 0.5
                v_radius = (v_max - v_min) * 0.5

                for p in range(particle_count):
                    for v_idx in range(v_per_particle):
                        buf = bytearray(stride_t)
                        if mesh_fx_type == "1": # Quad
                            uvs = [
                                (u_min, v_max),
                                (u_max, v_max),
                                (u_min, v_min),
                                (u_max, v_min)
                            ]
                            u, v = uvs[v_idx]
                        elif mesh_fx_type == "2": # Circle (hexagon fan)
                            if v_idx == 0:
                                u, v = u_center, v_center
                            else:
                                angle = (v_idx - 1) * (2.0 * math.pi / 6.0)
                                u = u_center + u_radius * math.cos(angle)
                                v = v_center + v_radius * math.sin(angle)
                        else: # Triangle (type 0 or Custom Mesh stub type 3)
                            uvs = [
                                (u_center, v_max),
                                (u_min, v_min),
                                (u_max, v_min)
                            ]
                            u, v = uvs[v_idx]

                        h_u = float_to_half(u)
                        h_v = float_to_half(v)
                        uv_slot_bytes = 4  # 2×float16
                        num_slots = stride_t // uv_slot_bytes
                        for slot in range(num_slots):
                            struct.pack_into('<HH', buf, slot * uv_slot_bytes, h_u, h_v)
                        leftover_start = num_slots * uv_slot_bytes
                        for byte_i in range(leftover_start, stride_t):
                            buf[byte_i] = 0xFF
                        f_vb1.write(buf)




            # ----------------------------------------------------------------------
            # D. Patch IB (Indices)
            # ----------------------------------------------------------------------
            if f_ib:
                for p in range(particle_count):
                    v_start = current_v_count + p * v_per_particle
                    if mesh_fx_type == "1": # Quad
                        idx_list = [v_start, v_start + 1, v_start + 2, v_start + 2, v_start + 1, v_start + 3]
                    elif mesh_fx_type == "2": # Circle (hexagon fan: 6 tris)
                        idx_list = [
                            v_start, v_start + 1, v_start + 2,
                            v_start, v_start + 2, v_start + 3,
                            v_start, v_start + 3, v_start + 4,
                            v_start, v_start + 4, v_start + 5,
                            v_start, v_start + 5, v_start + 6,
                            v_start, v_start + 6, v_start + 1,
                        ]
                    else: # Triangle (type 0 or Custom Mesh stub type 3)
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
