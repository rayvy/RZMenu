import bpy
import bmesh
import math
import numpy as np
from mathutils import Vector, kdtree

def calculate_slot_config(obj, res_x, res_y, padding, lattice_strength=1.0):
    """
    Calculates Bounding Box (Top-Left 0,0) and 3x3 Lattice deformation.
    Processes all selected faces as a single unit.
    """
    if not obj or obj.type != 'MESH':
        return None

    # Use bmesh to get UVs from edit mode or object mode
    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
    else:
        bm = bmesh.new()
        bm.from_mesh(obj.data)

    uv_layer = bm.loops.layers.uv.verify()
    
    selected_faces = [f for f in bm.faces if f.select]
    if not selected_faces:
        if obj.mode != 'EDIT':
            bm.free()
        return None

    uv_points = []
    for face in selected_faces:
        for loop in face.loops:
            uv = loop[uv_layer].uv
            uv_points.append(Vector((uv.x, uv.y, 0.0)))

    if not uv_points:
        if obj.mode != 'EDIT':
            bm.free()
        return None

    np_coords = np.array([(v.x, v.y) for v in uv_points], dtype=np.float32)
    min_u, min_v = np.min(np_coords, axis=0)
    max_u, max_v = np.max(np_coords, axis=0)

    # --- CONVERSION TO TOP-LEFT (Y axis flip for TexWorks) ---
    # UV: 0 is bottom, 1 is top.
    # TexWorks: 0 is top, 1 is bottom.
    
    px_min_x = math.floor(min_u * res_x) - padding
    px_max_x = math.ceil(max_u * res_x) + padding
    
    # 1.0 - max_v is the top coordinate in CS
    px_min_y = math.floor((1.0 - max_v) * res_y) - padding
    px_max_y = math.ceil((1.0 - min_v) * res_y) + padding
    
    width = px_max_x - px_min_x
    height = px_max_y - px_min_y
    
    rect = (px_min_x, px_min_y, width, height)

    # --- LATTICE (WARP) ---
    kd = kdtree.KDTree(len(uv_points))
    for i, v in enumerate(uv_points):
        kd.insert(v, i)
    kd.balance()

    mid_u = (min_u + max_u) * 0.5
    mid_v = (min_v + max_v) * 0.5
    
    # Grid targets (Top-Left to Bottom-Right)
    # Row 0: Top (Max V in UV)
    # Row 1: Mid
    # Row 2: Bot (Min V in UV)
    targets = [
        Vector((min_u, max_v, 0)), Vector((mid_u, max_v, 0)), Vector((max_u, max_v, 0)),
        Vector((min_u, mid_v, 0)), Vector((mid_u, mid_v, 0)), Vector((max_u, mid_v, 0)),
        Vector((min_u, min_v, 0)), Vector((mid_u, min_v, 0)), Vector((max_u, min_v, 0))
    ]
    
    lattice_offsets = []
    size_u = max(0.0001, max_u - min_u)
    size_v = max(0.0001, max_v - min_v)

    for target in targets:
        co, index, dist = kd.find(target)
        
        # Horizontal offset
        off_x = (co.x - target.x) / size_u
        # Vertical offset (inverted since CS Y is top-down)
        off_y = (target.y - co.y) / size_v
        
        lattice_offsets.extend([off_x * lattice_strength, off_y * lattice_strength])

    if obj.mode != 'EDIT':
        bm.free()

    return rect, lattice_offsets
