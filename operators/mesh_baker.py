import bpy
import numpy as np

# Модификаторы, способные изменять количество вершин или их порядок
TOPOLOGY_MODS = {
    'MIRROR', 'WELD', 'SUBSURF', 'MULTIRES', 'ARRAY', 'BEVEL',
    'BOOLEAN', 'DECIMATE', 'EDGE_SPLIT', 'SOLIDIFY', 'SCREW',
    'SKIN', 'TRIANGULATE', 'REMESH', 'WIREFRAME', 'NODES', 'GEOMETRY_NODES'
}

def has_topology_modifiers(obj):
    """Возвращает True, если у объекта есть активные модификаторы, меняющие топологию."""
    for m in obj.modifiers:
        if m.show_viewport and (m.type in TOPOLOGY_MODS):
            return True
    return False

def bake_shapekeys_with_modifiers(obj, sk_names):
    """
    Gret-style Static Topology Bake:
    Запекает дельты шейпкеев с учетом модификаторов, сохраняя оригинальную топологию.
    Решает проблему Mirror+Merge, "замораживая" топологию из базиса.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()

    # 1. Получаем точный Базис (включая все слияния и генерацию)
    eval_basis = obj.evaluated_get(depsgraph)
    basis_mesh = eval_basis.to_mesh()
    basis_v_count = len(basis_mesh.vertices)
    
    basis_coords = np.empty(basis_v_count * 3, dtype=np.float32)
    basis_mesh.vertices.foreach_get('co', basis_coords)
    basis_coords = basis_coords.reshape(-1, 3)
    
    mw = np.array(obj.matrix_world, dtype=np.float32)
    basis_coords_world = (np.c_[basis_coords, np.ones(basis_v_count)] @ mw.T)[:, :3]
    eval_basis.to_mesh_clear()

    result = {
        'basis_coords': basis_coords_world,
        'deltas': {},
        'vertex_count': basis_v_count,
        'obj_name': obj.name
    }

    # Сохраняем состояния шейпкеев
    sk_snapshot = {sk.name: sk.value for sk in obj.data.shape_keys.key_blocks}

    # 2. Создаем временный объект без слияний (чтобы предотвратить сдвиг топологии при SK=1.0)
    tmp_obj = obj.copy()
    tmp_obj.data = obj.data.copy()
    
    try:
        bpy.context.scene.collection.objects.link(tmp_obj)

        # Отключаем слияния в топологических модификаторах
        for mod in tmp_obj.modifiers:
            if mod.type == 'MIRROR':
                mod.use_mirror_merge = False
                mod.use_clip = False
            elif mod.type == 'WELD':
                mod.show_viewport = False

        # Оцениваем unwelded базис (без слияний)
        eval_tmp_basis = tmp_obj.evaluated_get(depsgraph)
        tmp_basis_mesh = eval_tmp_basis.to_mesh()
        m_v_count = len(tmp_basis_mesh.vertices)
        
        tmp_basis_coords = np.empty(m_v_count * 3, dtype=np.float32)
        tmp_basis_mesh.vertices.foreach_get('co', tmp_basis_coords)
        tmp_basis_coords = tmp_basis_coords.reshape(-1, 3)
        tmp_basis_coords_world = (np.c_[tmp_basis_coords, np.ones(m_v_count)] @ mw.T)[:, :3]
        eval_tmp_basis.to_mesh_clear()

        # Строим weld_map: unwelded_idx -> welded_idx
        from mathutils.kdtree import KDTree
        from mathutils import Vector
        
        kd = KDTree(basis_v_count)
        for i, co in enumerate(basis_coords_world):
            kd.insert(Vector(co), i)
        kd.balance()

        weld_map = np.zeros(m_v_count, dtype=np.int32)
        for i, co in enumerate(tmp_basis_coords_world):
            _, idx, _ = kd.find(Vector(co))
            weld_map[i] = idx

        # 3. Вычисляем дельты для каждого шейпкея
        for sk_name in sk_names:
            if sk_name not in tmp_obj.data.shape_keys.key_blocks:
                continue

            # Изолируем шейпкей (SK = 1.0)
            for sk in tmp_obj.data.shape_keys.key_blocks:
                sk.value = 1.0 if sk.name == sk_name else 0.0

            bpy.context.view_layer.update()
            depsgraph.update()

            eval_tmp_sk = tmp_obj.evaluated_get(depsgraph)
            tmp_sk_mesh = eval_tmp_sk.to_mesh()

            if len(tmp_sk_mesh.vertices) != m_v_count:
                # Если топология изменилась даже без Merge, значит сработал нелинейный GeoNodes
                eval_tmp_sk.to_mesh_clear()
                raise RuntimeError(f"Topology shift in SK {sk_name} despite disabled merges.")

            tmp_sk_coords = np.empty(m_v_count * 3, dtype=np.float32)
            tmp_sk_mesh.vertices.foreach_get('co', tmp_sk_coords)
            tmp_sk_coords = tmp_sk_coords.reshape(-1, 3)
            tmp_sk_coords_world = (np.c_[tmp_sk_coords, np.ones(m_v_count)] @ mw.T)[:, :3]
            eval_tmp_sk.to_mesh_clear()

            # Дельта на unwelded топологии
            unwelded_deltas = tmp_sk_coords_world - tmp_basis_coords_world

            # Сливаем дельты обратно в welded топологию (базис игры)
            welded_deltas = np.zeros((basis_v_count, 3), dtype=np.float32)
            counts = np.zeros(basis_v_count, dtype=np.float32)

            np.add.at(welded_deltas, weld_map, unwelded_deltas)
            np.add.at(counts, weld_map, 1.0)

            # Усредняем значения для слитых вершин
            safe_counts = np.where(counts == 0, 1.0, counts)
            welded_deltas /= safe_counts[:, np.newaxis]

            result['deltas'][sk_name] = welded_deltas

    finally:
        # Очистка памяти
        bpy.data.objects.remove(tmp_obj, do_unlink=True)
        for sk_name, val in sk_snapshot.items():
            if sk_name in obj.data.shape_keys.key_blocks:
                obj.data.shape_keys.key_blocks[sk_name].value = val

    return result