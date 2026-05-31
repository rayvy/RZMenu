# RZMenu/utils/overlay_pdiddy.py
import bpy
from bpy_extras import view3d_utils
import blf
import mathutils

COMPARISON_DRAW_HANDLE = None
CENTROID_CACHE = {}

def is_mask_group(name: str) -> bool:
    return name.strip().casefold().startswith("mask")

def draw_vg_stats_prepend(self, context):
    addon_name = __package__.split(".")[0] if "." in __package__ else __package__
    prefs = context.preferences.addons.get(addon_name)
    if prefs and hasattr(prefs.preferences, "show_vg_stats") and not prefs.preferences.show_vg_stats:
        return

    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return
    
    vgs = obj.vertex_groups
    total = len(vgs)
    mask = sum(1 for vg in vgs if is_mask_group(vg.name))
    clear = total - mask
    
    layout = self.layout
    row = layout.row(align=True)
    row.alignment = 'CENTER'
    row.scale_y = 0.85
    
    box_tot = row.box()
    box_tot.label(text=f"Total: {total}", icon='GROUP_VERTEX')
    
    box_clr = row.box()
    box_clr.label(text=f"Clear: {clear}", icon='VERTEXSEL')
    
    box_msk = row.box()
    box_msk.label(text=f"Mask: {mask}", icon='MOD_MASK')
    
    layout.separator(factor=0.3)

def get_cached_vg_centroids(obj):
    if not obj or obj.type != 'MESH':
        return {}
        
    # Check cache based on object name, vertex count, and transform matrix to track translation/rotation
    matrix_world = obj.matrix_world.copy()
    key = (obj.name, len(obj.data.vertices), tuple(matrix_world[0]), tuple(matrix_world[1]), tuple(matrix_world[2]), tuple(matrix_world[3]))
    if key in CENTROID_CACHE:
        return CENTROID_CACHE[key]
        
    vgs = obj.vertex_groups
    centroids = {}
    if not vgs:
        return centroids
        
    # Sum world coordinates for each group
    group_sums = {vg.index: mathutils.Vector((0.0, 0.0, 0.0)) for vg in vgs}
    group_counts = {vg.index: 0 for vg in vgs}
    
    for v in obj.data.vertices:
        co = matrix_world @ v.co
        for g in v.groups:
            idx = g.group
            if idx in group_sums:
                group_sums[idx] += co
                group_counts[idx] += 1
                
    for vg in vgs:
        idx = vg.index
        count = group_counts[idx]
        if count > 0:
            centroids[vg.name] = group_sums[idx] / count
        else:
            # Fallback to local centroid converted to world space
            local_center = sum((mathutils.Vector(corner) for corner in obj.bound_box), mathutils.Vector()) / 8
            centroids[vg.name] = matrix_world @ local_center
            
    CENTROID_CACHE[key] = centroids
    return centroids

def draw_comparison_overlay_pixel():
    context = bpy.context
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    
    compare_mode = getattr(scene, "rzm_st_vg_compare_mode", 'OFF')
    if compare_mode == 'OFF':
        return
        
    if context.region is None or context.region_data is None:
        return
        
    # Get selected mesh objects
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if len(selected_meshes) != 2:
        return
        
    obj_a, obj_b = selected_meshes[0], selected_meshes[1]
    
    try:
        vgs_a = {vg.name for vg in obj_a.vertex_groups}
        vgs_b = {vg.name for vg in obj_b.vertex_groups}
        
        # Calculate lists to draw for each
        if compare_mode == 'IDENTICAL':
            draw_names_a = sorted(list(vgs_a.intersection(vgs_b)))
            draw_names_b = draw_names_a
            color_a = (0.2, 0.8, 0.2, 1.0) # Green for identical
            color_b = (0.2, 0.8, 0.2, 1.0)
        elif compare_mode == 'DIFFERENT':
            draw_names_a = sorted(list(vgs_a - vgs_b))
            draw_names_b = sorted(list(vgs_b - vgs_a))
            color_a = (0.9, 0.3, 0.3, 1.0) # Red for unique
            color_b = (0.9, 0.3, 0.3, 1.0)
        else:
            return
            
        centroids_a = get_cached_vg_centroids(obj_a)
        centroids_b = get_cached_vg_centroids(obj_b)
        
        font_id = 0
        blf.size(font_id, 12)
        
        # Helper to draw labels on screen at their 3D locations
        def draw_labels(obj, names, centroids, color):
            for name in names:
                centroid = centroids.get(name)
                if centroid:
                    screen = view3d_utils.location_3d_to_region_2d(context.region, context.region_data, centroid)
                    if screen:
                        # Draw a small shadow / outline for readability
                        blf.position(font_id, int(screen.x) + 1, int(screen.y) - 1, 0)
                        blf.color(font_id, 0.0, 0.0, 0.0, 0.8)
                        blf.draw(font_id, name)
                        
                        blf.position(font_id, int(screen.x), int(screen.y), 0)
                        blf.color(font_id, color[0], color[1], color[2], color[3])
                        blf.draw(font_id, name)
                        
        draw_labels(obj_a, draw_names_a, centroids_a, color_a)
        draw_labels(obj_b, draw_names_b, centroids_b, color_b)
        
    except Exception as e:
        print(f"overlay_pdiddy draw error: {e}")

def register():
    global COMPARISON_DRAW_HANDLE
    # 1. Prepend to default VG panel
    bpy.types.DATA_PT_vertex_groups.prepend(draw_vg_stats_prepend)
    # 2. Add viewport draw handler
    if COMPARISON_DRAW_HANDLE is None:
        COMPARISON_DRAW_HANDLE = bpy.types.SpaceView3D.draw_handler_add(
            draw_comparison_overlay_pixel, (), "WINDOW", "POST_PIXEL"
        )

def unregister():
    global COMPARISON_DRAW_HANDLE
    # 1. Remove from default VG panel
    try:
        bpy.types.DATA_PT_vertex_groups.remove(draw_vg_stats_prepend)
    except Exception:
        pass
    # 2. Remove viewport draw handler
    if COMPARISON_DRAW_HANDLE is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(COMPARISON_DRAW_HANDLE, "WINDOW")
        except Exception:
            pass
        COMPARISON_DRAW_HANDLE = None
    # 3. Clear cache
    CENTROID_CACHE.clear()
