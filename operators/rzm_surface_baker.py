# RZMenu/operators/rzm_surface_baker.py
import bpy
import bmesh
import mathutils
import numpy as np

def transfer_surface_shape_keys(target_obj, source_obj, sk_names):
    """
    Продвинутое запекание шейпкеев с сохранением формы (Tangent-Space Bind).
    Используется как подготовительный этап перед экспортом.
    
    target_obj: Объект, который получает шейпкеи (например, одежда)
    source_obj: Объект-донор (например, тело)
    sk_names:   Список имен шейпкеев для переноса
    """
    if not target_obj or not source_obj or not sk_names:
        return
        
    if not source_obj.data.shape_keys or not source_obj.data.shape_keys.key_blocks:
        return

    # Хардкод параметров (как в оригинальном UI)
    blend_form = 0.8
    use_smooth = False
    use_anticlip = False

    src_blocks = source_obj.data.shape_keys.key_blocks
    src_basis = src_blocks[0]
    size_src = len(source_obj.data.vertices)
    
    if size_src == 0:
        return

    # 1. Готовим Базис Источника
    src_basis_co = np.zeros(size_src * 3, dtype=np.float32)
    src_basis.data.foreach_get("co", src_basis_co)
    src_basis_co.shape = (size_src, 3)

    M_src = np.array(source_obj.matrix_world, dtype=np.float32)
    src_hom = np.ones((size_src, 4), dtype=np.float32)
    src_hom[:, :3] = src_basis_co
    src_world = (M_src @ src_hom.T).T[:, :3]

    # Строим BVH из Источника
    bm = bmesh.new()
    bm.from_mesh(source_obj.data)
    bm.transform(source_obj.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bvh = mathutils.bvhtree.BVHTree.FromBMesh(bm)

    # 2. Готовим Цель (Target)
    if not target_obj.data.shape_keys:
        target_obj.shape_key_add(name="Basis", from_mix=False)
        
    tgt_blocks = target_obj.data.shape_keys.key_blocks
    tgt_basis = tgt_blocks[0]
    size_tgt = len(target_obj.data.vertices)
    
    if size_tgt == 0:
        bm.free()
        return

    tgt_basis_co = np.zeros(size_tgt * 3, dtype=np.float32)
    tgt_basis.data.foreach_get("co", tgt_basis_co)
    tgt_basis_co.shape = (size_tgt, 3)

    M_tgt = np.array(target_obj.matrix_world, dtype=np.float32)
    tgt_hom = np.ones((size_tgt, 4), dtype=np.float32)
    tgt_hom[:, :3] = tgt_basis_co
    tgt_world = (M_tgt @ tgt_hom.T).T[:, :3]

    # Массивы привязок
    v0_idx = np.zeros(size_tgt, dtype=np.int32)
    v1_idx = np.zeros(size_tgt, dtype=np.int32)
    v2_idx = np.zeros(size_tgt, dtype=np.int32)
    w0 = np.zeros((size_tgt, 1), dtype=np.float32)
    w1 = np.zeros((size_tgt, 1), dtype=np.float32)
    w2 = np.zeros((size_tgt, 1), dtype=np.float32)

    # Ищем пересечения
    for i in range(size_tgt):
        loc, normal, face_idx, dist = bvh.find_nearest(tgt_world[i])
        if face_idx is not None:
            face = bm.faces[face_idx]
            vert0, vert1, vert2 = face.verts
            v0_idx[i] = vert0.index
            v1_idx[i] = vert1.index
            v2_idx[i] = vert2.index
            
            area_total = mathutils.geometry.area_tri(vert0.co, vert1.co, vert2.co)
            if area_total > 1e-8:
                a0 = mathutils.geometry.area_tri(loc, vert1.co, vert2.co) / area_total
                a1 = mathutils.geometry.area_tri(vert0.co, loc, vert2.co) / area_total
                a2 = mathutils.geometry.area_tri(vert0.co, vert1.co, loc) / area_total
                total_w = a0 + a1 + a2
                w0[i, 0], w1[i, 0], w2[i, 0] = a0/total_w, a1/total_w, a2/total_w
            else:
                w0[i, 0], w1[i, 0], w2[i, 0] = 1.0, 0.0, 0.0
        else:
            w0[i, 0], w1[i, 0], w2[i, 0] = 1.0, 0.0, 0.0

    # PRE-CALCULATE TANGENT SPACE BIND
    v0_orig = src_world[v0_idx]
    v1_orig = src_world[v1_idx]
    v2_orig = src_world[v2_idx]
    loc_orig = w0*v0_orig + w1*v1_orig + w2*v2_orig

    # Local Frame (Orig)
    T_orig = v1_orig - v0_orig
    norm_T = np.linalg.norm(T_orig, axis=1, keepdims=True)
    norm_T[norm_T < 1e-8] = 1.0
    T_orig /= norm_T

    N_orig_unnorm = np.cross(v1_orig - v0_orig, v2_orig - v0_orig)
    norm_N = np.linalg.norm(N_orig_unnorm, axis=1, keepdims=True)
    norm_N[norm_N < 1e-8] = 1.0
    N_orig = N_orig_unnorm / norm_N

    B_orig = np.cross(N_orig, T_orig)
    norm_B = np.linalg.norm(B_orig, axis=1, keepdims=True)
    norm_B[norm_B < 1e-8] = 1.0
    B_orig /= norm_B

    # Offset Projection
    offset_orig = tgt_world - loc_orig
    dx = np.sum(offset_orig * T_orig, axis=1, keepdims=True)
    dy = np.sum(offset_orig * B_orig, axis=1, keepdims=True)
    dz = np.sum(offset_orig * N_orig, axis=1, keepdims=True)

    M_tgt_inv_3x3 = np.array(target_obj.matrix_world.inverted_safe().to_3x3(), dtype=np.float32)

    # 3. Перенос выбранных шейпкеев
    for sk_name in sk_names:
        if sk_name not in src_blocks:
            continue
        src_sk = src_blocks[sk_name]
        
        # Если шейпкей уже существует на Target - не трогаем его (пользовательское правило)
        if sk_name in tgt_blocks:
            continue
            
        tgt_sk = target_obj.shape_key_add(name=sk_name, from_mix=False)
            
        src_sk_co = np.zeros(size_src * 3, dtype=np.float32)
        src_sk.data.foreach_get("co", src_sk_co)
        src_sk_co.shape = (size_src, 3)
        
        src_sk_hom = np.ones((size_src, 4), dtype=np.float32)
        src_sk_hom[:, :3] = src_sk_co
        src_sk_world = (M_src @ src_sk_hom.T).T[:, :3]
        
        # APPLY TANGENT SPACE BIND
        v0_def = src_sk_world[v0_idx]
        v1_def = src_sk_world[v1_idx]
        v2_def = src_sk_world[v2_idx]
        loc_def = w0*v0_def + w1*v1_def + w2*v2_def

        T_def = v1_def - v0_def
        norm_T_def = np.linalg.norm(T_def, axis=1, keepdims=True)
        norm_T_def[norm_T_def < 1e-8] = 1.0
        T_def /= norm_T_def

        N_def_unnorm = np.cross(v1_def - v0_def, v2_def - v0_def)
        norm_N_def = np.linalg.norm(N_def_unnorm, axis=1, keepdims=True)
        norm_N_def[norm_N_def < 1e-8] = 1.0
        N_def = N_def_unnorm / norm_N_def

        B_def = np.cross(N_def, T_def)
        norm_B_def = np.linalg.norm(B_def, axis=1, keepdims=True)
        norm_B_def[norm_B_def < 1e-8] = 1.0
        B_def /= norm_B_def

        # Линейное и Жесткое смещение
        tgt_def_linear = loc_def + offset_orig
        tgt_def_rigid = loc_def + dx * T_def + dy * B_def + dz * N_def

        # Бленд
        tgt_raw_world = tgt_def_linear * (1.0 - blend_form) + tgt_def_rigid * blend_form
        
        # Финал
        final_disp_world = tgt_raw_world - tgt_world
        tgt_disp_local = (M_tgt_inv_3x3 @ final_disp_world.T).T
        tgt_sk_co = tgt_basis_co + tgt_disp_local
        
        tgt_sk.data.foreach_set("co", tgt_sk_co.ravel())
        tgt_sk.value = 0.0

    target_obj.data.update()
    bm.free()