# RZMenu/operators/vfx_ops.py
import bpy
import os
import struct
import math
from bpy.types import Operator
from mathutils import Vector, Euler

class RZM_OT_normalize_weight_value(Operator):
    bl_idname = "rzm.normalize_curve_vfx_weight"
    bl_label = "Normalize Weight"
    bl_description = "Normalize the active weight slots so they sum to 1"

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'CURVE':
            self.report({"WARNING"}, "No active curve object")
            return {"CANCELLED"}
            
        indices = list(getattr(obj, "rzm_curve_vfx_weight_indices", (-1, -1, -1, -1)))
        values = list(getattr(obj, "rzm_curve_vfx_weight_values", (0.0, 0.0, 0.0, 0.0)))
        
        active = [i for i, idx in enumerate(indices) if idx != -1 and values[i] > 0.0]
        total = sum(values[i] for i in active)

        if total <= 0.0:
            if "RZM.CURVE_VFX.WEIGHT_INDICES" in obj and "RZM.CURVE_VFX.WEIGHT_VALUES" in obj:
                indices = list(obj.get("RZM.CURVE_VFX.WEIGHT_INDICES", (-1, -1, -1, -1)))
                values = list(obj.get("RZM.CURVE_VFX.WEIGHT_VALUES", (0.0, 0.0, 0.0, 0.0)))
                active = [i for i, idx in enumerate(indices) if idx != -1 and values[i] > 0.0]
                total = sum(values[i] for i in active)
                
        if total <= 0.0:
            self.report({"WARNING"}, "No active weights to normalize")
            return {"CANCELLED"}

        for i in active:
            values[i] = values[i] / total

        if hasattr(obj, "rzm_curve_vfx_weight_values"):
            try:
                obj.rzm_curve_vfx_weight_values = values
            except Exception:
                pass
        obj["RZM.CURVE_VFX.WEIGHT_VALUES"] = values
        
        self.report({"INFO"}, "Weights normalized across active slots")
        return {"FINISHED"}

class RZM_OT_validate_curve_vfx(Operator):
    bl_idname = "rzm.validate_curve_vfx"
    bl_label = "Validate Curve VFX"
    bl_description = "Perform pre-export and post-export checks on Curve VFX objects"

    def execute(self, context):
        from ..utils.vfx_buffer_patcher import (
            find_associated_mesh_and_component,
            evaluate_curve_spline_points,
            resolve_coordinate_remap_profile,
            remap_curve_point_to_buffer,
            get_mod_output_path,
            get_curve_prop
        )
        
        vfx_curves = [
            obj for obj in context.scene.objects 
            if obj.type == 'CURVE' and (getattr(obj, "rzm_curve_vfx_enabled", False) or obj.get("RZM.CURVE_VFX"))
        ]
        
        print("\n[RZM-VFX] ==================================================")
        print("[RZM-VFX] STARTING VFX CURVE VALIDATION")
        print("[RZM-VFX] ==================================================")
        
        if not vfx_curves:
            print("[RZM-VFX] No curve objects with VFX enabled found.")
            print("[RZM-VFX] ==================================================")
            self.report({"WARNING"}, "No VFX curve objects found.")
            return {"CANCELLED"}
            
        print(f"[RZM-VFX] Found {len(vfx_curves)} VFX curve(s) to validate.\n")
        
        mod_output_dir = get_mod_output_path(context)
        print(f"[RZM-VFX] Resolved Mod Output Directory: '{mod_output_dir}'")
        
        for idx, curve_obj in enumerate(vfx_curves):
            print(f"\n[RZM-VFX] --- [CURVE {idx+1}/{len(vfx_curves)}]: \"{curve_obj.name}\" ---")
            
            particle_count = get_curve_prop(curve_obj, "particle_count", 1)
            particle_size_base = get_curve_prop(curve_obj, "particle_size_base", 0.05)
            particle_size_start = get_curve_prop(curve_obj, "particle_size_start", 1.0)
            particle_size_end = get_curve_prop(curve_obj, "particle_size_end", 0.2)
            dispersion_scale = get_curve_prop(curve_obj, "dispersion_scale", 1.0)
            cycle_duration = get_curve_prop(curve_obj, "cycle_duration", 2.0)
            phase_randomness = get_curve_prop(curve_obj, "phase_randomness", 1.0)
            pos_randomness = get_curve_prop(curve_obj, "pos_randomness", 0.0)
            timeline_start = get_curve_prop(curve_obj, "timeline_start_pos", 0.0)
            timeline_mid = get_curve_prop(curve_obj, "timeline_mid_pos", 0.5)
            timeline_end = get_curve_prop(curve_obj, "timeline_end_pos", 1.0)
            mesh_fx_type = str(get_curve_prop(curve_obj, "mesh_fx_type", "0"))
            weight_indices = list(get_curve_prop(curve_obj, "weight_indices", (-1, -1, -1, -1)))
            weight_values = list(get_curve_prop(curve_obj, "weight_values", (0.0, 0.0, 0.0, 0.0)))
            
            # Print settings
            print(f"[RZM-VFX]   * Particle Count: {particle_count}")
            print(f"[RZM-VFX]   * Base Size: {particle_size_base} m")
            print(f"[RZM-VFX]   * Size Scale Start/End: {particle_size_start} -> {particle_size_end}")
            print(f"[RZM-VFX]   * Dispersion Scale: {dispersion_scale}")
            print(f"[RZM-VFX]   * Cycle Duration (sec): {cycle_duration}")
            print(f"[RZM-VFX]   * Phase Randomness: {phase_randomness}")
            print(f"[RZM-VFX]   * Position Randomness: {pos_randomness}")
            print(f"[RZM-VFX]   * Timeline positions: Start={timeline_start}, Mid={timeline_mid}, End={timeline_end}")
            print(f"[RZM-VFX]   * Mesh FX Type: {mesh_fx_type}")
            print(f"[RZM-VFX]   * Weight Indices: {weight_indices}")
            print(f"[RZM-VFX]   * Weight Values: {weight_values}")
            
            # Resolve association
            comp_name, target_mesh, part_name = find_associated_mesh_and_component(context, curve_obj)
            if not target_mesh:
                print(f"[RZM-VFX] [ERROR] Curve \"{curve_obj.name}\" is not in the same collection as any component meshes!")
                continue
                
            print(f"[RZM-VFX]   -> Associated Mesh: \"{target_mesh.name}\"")
            print(f"[RZM-VFX]   -> Component Name: \"{comp_name}\"")
            
            # Sample points
            resampled_points = evaluate_curve_spline_points(context, curve_obj, num_samples=32)
            if not resampled_points or len(resampled_points) < 2:
                print(f"[RZM-VFX] [ERROR] Curve evaluation failed or returned too few points.")
                continue
                
            print(f"[RZM-VFX]   -> Resampled 32 points successfully.")
            
        print("\n[RZM-VFX] ==================================================")
        print("[RZM-VFX] VALIDATION COMPLETED")
        print("[RZM-VFX] ==================================================")
        
        self.report({"INFO"}, "VFX Curve validation completed. See console.")
        return {"FINISHED"}


class RZM_OT_toggle_curve_bevel(Operator):
    bl_idname = "rzm.toggle_curve_bevel"
    bl_label = "Toggle Bevel Preview"
    bl_description = "Set bevel_depth=0.01 on selected curves for preview; if already 0.01, set to 0.0"

    def execute(self, context):
        targets = [obj for obj in context.selected_objects if obj.type == 'CURVE']
        if not targets:
            self.report({'WARNING'}, "No curve objects selected")
            return {'CANCELLED'}
        for obj in targets:
            if abs(obj.data.bevel_depth - 0.01) < 1e-6:
                obj.data.bevel_depth = 0.0
            else:
                obj.data.bevel_depth = 0.01
        return {'FINISHED'}



class RZM_OT_compute_vfx_uv(Operator):
    bl_idname = "rzm.compute_vfx_uv"
    bl_label = "Compute & Write UV"
    bl_description = (
        "Compute UV offset and scale from canvas size + pixel offset + sprite size, "
        "then write the result to UV Offset / UV Scale"
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'CURVE':
            self.report({'WARNING'}, "No active curve object")
            return {'CANCELLED'}

        tex_w, tex_h = obj.rzm_curve_vfx_texture_size
        off_u, off_v   = obj.rzm_curve_vfx_uv_px_offset
        sz_w,  sz_h    = obj.rzm_curve_vfx_uv_px_size

        tw = max(tex_w, 1)
        th = max(tex_h, 1)

        uv_offset = (off_u / tw, off_v / th)
        uv_scale  = (sz_w  / tw, sz_h  / th)

        obj.rzm_curve_vfx_uv_offset = uv_offset
        obj.rzm_curve_vfx_uv_scale  = uv_scale

        self.report({'INFO'},
            f"UV written → Offset=({uv_offset[0]:.4f}, {uv_offset[1]:.4f})  "
            f"Scale=({uv_scale[0]:.4f}, {uv_scale[1]:.4f})")
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_normalize_weight_value,
    RZM_OT_validate_curve_vfx,
    RZM_OT_toggle_curve_bevel,
    RZM_OT_compute_vfx_uv,
]
