# vfx_debug_script.py
# Open this script in Blender's Text Editor and click "Run Script" (or press Alt+P).
# It will generate a detailed report "rzm_vfx_debug_report.txt" on your Desktop.

import bpy
import os
import math
import struct
from mathutils import Vector

def run_diagnostic():
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    report_path = os.path.join(desktop_path, "rzm_vfx_debug_report.txt")
    
    lines = []
    lines.append("=" * 80)
    lines.append("RZM VFX CURVE COORD & HIERARCHY DIAGNOSTIC REPORT")
    lines.append("=" * 80)
    lines.append(f"Blender Version: {bpy.app.version_string}")
    lines.append(f"Scene Name: {bpy.context.scene.name}")
    lines.append(f"File Path: {bpy.data.filepath}")
    lines.append("")

    # Try to import RZMenu functions
    try:
        from RZMenu.utils.vfx_buffer_patcher import find_associated_mesh_and_component, get_armature_or_root
        from RZMenu.operators.export_cache import get_cache
        lines.append("[SUCCESS] Successfully imported RZMenu functions.")
        cache = get_cache()
        if cache:
            lines.append(f"Mod Name in Cache: {cache.get('mod_name')}")
            lines.append(f"Mod Root in Cache: {cache.get('mod_root')}")
        else:
            lines.append("[WARNING] Export cache is empty.")
    except Exception as e:
        lines.append(f"[ERROR] Failed to import RZMenu functions: {e}")
        # Fallbacks if RZMenu is not loaded
        def get_armature_or_root(obj):
            if not obj: return None
            if hasattr(obj, "modifiers"):
                for mod in obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object:
                        return mod.object
            parent = obj.parent
            last_valid = obj
            while parent:
                if parent.type == 'ARMATURE': return parent
                if parent.type == 'EMPTY' and not parent.parent: return parent
                last_valid = parent
                parent = parent.parent
            return last_valid

        def find_associated_mesh_and_component(context, curve_obj):
            # Simple fallback: look for mesh in same collection
            for col in curve_obj.users_collection:
                for o in col.objects:
                    if o.type == 'MESH':
                        return "UnknownComponent", o, o.name
            return None, None, None

    # Find VFX curves
    vfx_curves = [
        obj for obj in bpy.context.scene.objects 
        if obj.type == 'CURVE' and (getattr(obj, "rzm_curve_vfx_enabled", False) or obj.get("RZM.CURVE_VFX"))
    ]
    
    lines.append(f"Found {len(vfx_curves)} Curve objects with VFX enabled in the scene.")
    lines.append("")

    for curve_obj in vfx_curves:
        lines.append("-" * 60)
        lines.append(f"CURVE OBJECT: '{curve_obj.name}'")
        lines.append("-" * 60)
        lines.append(f"  * Loc: {tuple(round(c, 4) for c in curve_obj.location)}")
        lines.append(f"  * Rot (Euler): {tuple(round(math.degrees(c), 2) for c in curve_obj.rotation_euler)}")
        lines.append(f"  * Scale: {tuple(round(c, 4) for c in curve_obj.scale)}")
        lines.append(f"  * Parent: {curve_obj.parent.name if curve_obj.parent else 'None'}")
        if curve_obj.parent:
            lines.append(f"    - Parent Type: {curve_obj.parent_type}")
            lines.append(f"    - Parent Bone: {curve_obj.parent_bone}")
        lines.append(f"  * Collections: {[c.name for c in curve_obj.users_collection]}")
        
        # Matrix World
        mw = curve_obj.matrix_world
        lines.append("  * Matrix World:")
        for r in range(4):
            row_vals = tuple(round(mw[r][c], 6) for c in range(4))
            lines.append(f"    Row {r}: {row_vals}")

        # Find associated mesh
        comp_name, target_mesh, part_name = find_associated_mesh_and_component(bpy.context, curve_obj)
        lines.append(f"  * Resolved Association:")
        lines.append(f"    - Component: {comp_name}")
        lines.append(f"    - Target Mesh: '{target_mesh.name}'" if target_mesh else "    - Target Mesh: None")
        lines.append(f"    - Part Name: {part_name}")
        
        if not target_mesh:
            lines.append("    [ERROR] No associated target mesh found for this curve.")
            lines.append("")
            continue

        # Target Mesh details
        lines.append(f"  * Target Mesh '{target_mesh.name}' details:")
        lines.append(f"    - Loc: {tuple(round(c, 4) for c in target_mesh.location)}")
        lines.append(f"    - Rot (Euler): {tuple(round(math.degrees(c), 2) for c in target_mesh.rotation_euler)}")
        lines.append(f"    - Scale: {tuple(round(c, 4) for c in target_mesh.scale)}")
        lines.append(f"    - Parent: {target_mesh.parent.name if target_mesh.parent else 'None'}")
        if target_mesh.parent:
            lines.append(f"      * Parent Type: {target_mesh.parent_type}")
            lines.append(f"      * Parent Bone: {target_mesh.parent_bone}")
            
        # Target Mesh Matrix World
        m_mesh = target_mesh.matrix_world
        lines.append("    - Matrix World:")
        for r in range(4):
            row_vals = tuple(round(m_mesh[r][c], 6) for c in range(4))
            lines.append(f"      Row {r}: {row_vals}")

        # Armature details
        arm_obj = get_armature_or_root(target_mesh)
        lines.append(f"    - Resolved Root/Armature: '{arm_obj.name}'" if arm_obj else "    - Resolved Root/Armature: None")
        if arm_obj:
            lines.append(f"      * Root Type: {arm_obj.type}")
            lines.append(f"      * Root Loc: {tuple(round(c, 4) for c in arm_obj.location)}")
            lines.append(f"      * Root Rot (Euler): {tuple(round(math.degrees(c), 2) for c in arm_obj.rotation_euler)}")
            lines.append(f"      * Root Scale: {tuple(round(c, 4) for c in arm_obj.scale)}")
            
            m_arm = arm_obj.matrix_world
            lines.append("      * Root Matrix World:")
            for r in range(4):
                row_vals = tuple(round(m_arm[r][c], 6) for c in range(4))
                lines.append(f"        Row {r}: {row_vals}")

        # Weight Reference Mesh
        weight_ref = curve_obj.rzm_curve_vfx_weight_reference
        lines.append(f"    - Weight Reference Mesh: '{weight_ref.name}'" if weight_ref else "    - Weight Reference Mesh: None")
        if weight_ref:
            m_ref = weight_ref.matrix_world
            lines.append("      * Weight Ref Matrix World:")
            for r in range(4):
                row_vals = tuple(round(m_ref[r][c], 6) for c in range(4))
                lines.append(f"        Row {r}: {row_vals}")

        # Splines and coordinates
        lines.append(f"  * Spline Coordinates Evaluation:")
        for s_idx, spline in enumerate(curve_obj.data.splines):
            lines.append(f"    Spline {s_idx}:")
            # Sample first point of spline
            if spline.type == 'BEZIER':
                pt_co = spline.bezier_points[0].co.xyz.copy()
            else:
                pt_co = spline.points[0].co.xyz.copy()
                
            wpos = curve_obj.matrix_world @ pt_co
            lpos_mesh = target_mesh.matrix_world.inverted() @ wpos
            lpos_arm = arm_obj.matrix_world.inverted() @ wpos if arm_obj else Vector((0,0,0))
            
            lines.append(f"      Point 0 (Local Curve): {tuple(round(c, 6) for c in pt_co)}")
            lines.append(f"      Point 0 (World Space): {tuple(round(c, 6) for c in wpos)}")
            lines.append(f"      Point 0 (Mesh Local Space): {tuple(round(c, 6) for c in lpos_mesh)}")
            lines.append(f"      Point 0 (Armature Local Space): {tuple(round(c, 6) for c in lpos_arm)}")

            # Weight lookup test
            # Let's inspect the target mesh's closest vertex to this Point 0
            if target_mesh.type == 'MESH':
                try:
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    mesh_eval = target_mesh.evaluated_get(depsgraph)
                    mesh_data = mesh_eval.data
                    
                    vg_map = {vg.index: vg.name for vg in target_mesh.vertex_groups}
                    
                    min_dist = float('inf')
                    closest_v = None
                    closest_idx = -1
                    
                    for v_idx, v in enumerate(mesh_data.vertices):
                        v_wpos = target_mesh.matrix_world @ v.co
                        dist = (v_wpos - wpos).length
                        if dist < min_dist:
                            min_dist = dist
                            closest_v = v
                            closest_idx = v_idx
                            
                    if closest_v:
                        lines.append(f"      Closest Vertex on Mesh '{target_mesh.name}':")
                        lines.append(f"        - Vertex Index: {closest_idx}")
                        lines.append(f"        - Distance: {round(min_dist, 6)} meters")
                        lines.append(f"        - Local Pos: {tuple(round(c, 6) for c in closest_v.co)}")
                        lines.append(f"        - World Pos: {tuple(round(c, 6) for c in (target_mesh.matrix_world @ closest_v.co))}")
                        
                        bone_weights = []
                        for g in closest_v.groups:
                            g_name = vg_map.get(g.group, f"Group_{g.group}")
                            bone_weights.append(f"{g_name} (Index {g.group}): {round(g.weight, 4)}")
                        lines.append(f"        - Vertex Bone Weights: {', '.join(bone_weights)}")
                except Exception as ex:
                    lines.append(f"      [ERROR] Could not perform mesh vertex lookup: {ex}")
            lines.append("")
            
    # Write to file
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Report successfully saved to: {report_path}")
        return report_path
    except Exception as e:
        print(f"Failed to write report file: {e}")
        return None

if __name__ == "__main__":
    path = run_diagnostic()
    if path:
        import sys
        if 'bpy' in sys.modules:
            # Show popup in Blender UI
            def draw_popup(self, context):
                self.layout.label(text="RZM VFX Diagnostic Done!")
                self.layout.label(text=f"Report saved to Desktop as: rzm_vfx_debug_report.txt")
            bpy.context.window_manager.popup_menu(draw_popup, title="Diagnostic Complete", icon='INFO')
