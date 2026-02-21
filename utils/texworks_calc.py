# RZMenu/utils/texworks_calc.py
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

def get_bmesh_islands(bm, selected_faces):
    """
    Разбивает список граней на связные группы (островки).
    Возвращает список списков граней.
    """
    faces_todo = set(selected_faces)
    islands = []

    while faces_todo:
        seed = faces_todo.pop()
        island = {seed}
        stack = [seed]
        
        while stack:
            f = stack.pop()
            # Ищем соседей через ребра
            for edge in f.edges:
                for linked_face in edge.link_faces:
                    if linked_face in faces_todo:
                        island.add(linked_face)
                        faces_todo.remove(linked_face)
                        stack.append(linked_face)
        
        islands.append(list(island))
    
    return islands

def measure_island_stats(bm, faces, uv_layer):
    """
    Возвращает словарь с метриками островка:
    - 3D Площадь (для пропорций)
    - Центр UV (для сортировки лево-право)
    """
    total_area = 0.0
    uv_centers = []
    
    for f in faces:
        total_area += f.calc_area()
        for loop in f.loops:
            uv = loop[uv_layer].uv
            uv_centers.append(uv)
            
    # Средний UV центр
    if uv_centers:
        avg_u = sum(uv.x for uv in uv_centers) / len(uv_centers)
        avg_v = sum(uv.y for uv in uv_centers) / len(uv_centers)
    else:
        avg_u, avg_v = 0.0, 0.0
        
    return {
        'faces': faces,
        'area': total_area,
        'center_u': avg_u
    }

def calculate_seamless_split_config(obj, res_x, res_y, padding):
    """
    Специализированный расчет для Split Decals.
    Гарантирует равномерную плотность текселей между двумя кусками.
    """
    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
    else:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        
    uv_layer = bm.loops.layers.uv.verify()
    selected_faces = [f for f in bm.faces if f.select]
    
    if not selected_faces:
        if obj.mode != 'EDIT': bm.free()
        return None

    # 1. Находим островки
    islands_faces = get_bmesh_islands(bm, selected_faces)
    
    if len(islands_faces) != 2:
        print(f"Algorithm expects exactly 2 islands, found {len(islands_faces)}")
        if obj.mode != 'EDIT': bm.free()
        return None

    # 2. Анализируем каждый островок
    island_data = []
    for faces in islands_faces:
        stats = measure_island_stats(bm, faces, uv_layer)
        
        # Временная эмуляция выбора для вызова базового калькулятора
        for f in bm.faces: f.select = False
        for f in faces: f.select = True
        
        # Считаем "Сырой" конфиг (как он есть сейчас по UV)
        raw_rect, raw_lattice = calculate_slot_config(obj, res_x, res_y, padding)
        
        stats['rect'] = list(raw_rect) # Convert to list to modify
        stats['lattice'] = raw_lattice
        island_data.append(stats)

    # Восстанавливаем выделение
    for f in selected_faces: f.select = True

    # 3. Сортируем: Pass 0 (слева), Pass 1 (справа)
    island_data.sort(key=lambda x: x['center_u'])
    
    pass0 = island_data[0]
    pass1 = island_data[1]

    # 4. МАТЕМАТИКА БЕСШОВНОСТИ (DENSITY NORMALIZATION)
    total_area_3d = pass0['area'] + pass1['area']
    if total_area_3d <= 0.00001: return None 

    ratio0 = pass0['area'] / total_area_3d
    ratio1 = pass1['area'] / total_area_3d

    total_pixel_width = pass0['rect'][2] + pass1['rect'][2]
    
    new_w0 = int(round(total_pixel_width * ratio0))
    new_w1 = int(round(total_pixel_width * ratio1))
    
    pass0['rect'][2] = new_w0
    pass1['rect'][2] = new_w1
    
    if obj.mode != 'EDIT':
        bm.free()

    return (
        {'rect': tuple(pass0['rect']), 'lattice': pass0['lattice'], 'ratio': ratio0},
        {'rect': tuple(pass1['rect']), 'lattice': pass1['lattice'], 'ratio': ratio1}
    )
