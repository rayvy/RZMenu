bl_info = {
    "name": "Rayvich Auto Injector v8.0",
    "author": "Rayvich & AI",
    "version": (8, 0),
    "blender": (3, 0, 0),
    "category": "Import-Export",
}

import bpy
import struct
import os
import re
from mathutils import Vector
from mathutils.bvhtree import BVHTree

class RayvichAutoProperties(bpy.types.PropertyGroup):
    mod_root: bpy.props.StringProperty(name="Папка мода", subtype='DIR_PATH')
    stride: bpy.props.IntProperty(name="Stride", default=16)
    distance_limit: bpy.props.FloatProperty(name="Limit (Матчинг)", default=0.01, precision=6)
    
    algorithm: bpy.props.EnumProperty(
        name="Алгоритм",
        items=[
            ('MATH_SYMMETRY', "3. Math Symmetry BVH (Обход движка)", "Математически генерирует отзеркаленную сетку в Python. 100% защита от Merge-коллапса."),
            ('UNMERGED_EVAL', "2. Unmerged Evaluated BVH (Твой метод)", "Отключает Merge/Clip перед снятием слепков через Depsgraph."),
            ('CLASSIC_BVH', "1. Classic BVH (Vanilla)", "Для обычных сеток без генеративных модификаторов."),
        ],
        default='MATH_SYMMETRY'
    )

def set_armature_visibility(comp_objects, visible):
    for obj in comp_objects:
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                mod.show_viewport = visible

def process_classic_bvh(comp_objects, original_data, stride, limit, output_dir, comp_id, key_map):
    """АЛГОРИТМ 1: Vanilla BVH (Сырая сетка)"""
    buf_v_count = len(original_data) // stride
    for sk_name in key_map.keys():
        current_buf = bytearray(original_data)
        print(f"\n🚀 [CLASSIC BVH] КЛЮЧ: [{sk_name}]")
        
        surface_data = []
        for obj in comp_objects:
            if not obj.data.shape_keys: continue
            b_coords = [v.co.copy() for v in obj.data.shape_keys.key_blocks[0].data]
            p_indices = [list(p.vertices) for p in obj.data.polygons]
            bvh = BVHTree.FromPolygons(b_coords, p_indices)
            
            target_sk = obj.data.shape_keys.key_blocks.get(sk_name)
            t_coords = [v.co.copy() for v in target_sk.data] if target_sk else b_coords
            surface_data.append({'bvh': bvh, 'p_indices': p_indices, 'b_coords': b_coords, 't_coords': t_coords})

        matched = 0
        for i in range(buf_v_count):
            off = i * stride
            orig_v = Vector(struct.unpack_from("<3f", original_data, off))
            
            best_dist, best_hit = float('inf'), None
            for s_data in surface_data:
                loc, normal, face_idx, dist = s_data['bvh'].find_nearest(orig_v)
                if face_idx is not None and dist < best_dist:
                    best_dist, best_hit = dist, (s_data, face_idx)
            
            if best_hit and best_dist <= limit:
                s_data, face_idx = best_hit
                face_verts = s_data['p_indices'][face_idx]
                total_w, blended_delta = 0.0, Vector((0,0,0))
                for v_idx in face_verts:
                    v_dist = (s_data['b_coords'][v_idx] - orig_v).length
                    weight = 1.0 / (v_dist**2 + 1e-10)
                    blended_delta += (s_data['t_coords'][v_idx] - s_data['b_coords'][v_idx]) * weight
                    total_w += weight
                
                final_delta = blended_delta / total_w
                if final_delta.length > 1e-7:
                    struct.pack_into("<3f", current_buf, off, *(orig_v + final_delta))
                    matched += 1
                    
        print(f"  ✅ Запечено: {matched} вершин.")
        with open(os.path.join(output_dir, f"Component{comp_id}_VB0_{sk_name}.buf"), "wb") as f: f.write(current_buf)

def process_unmerged_eval(comp_objects, original_data, stride, limit, output_dir, comp_id, key_map, depsgraph):
    """АЛГОРИТМ 2: Unmerged Evaluated BVH"""
    buf_v_count = len(original_data) // stride
    for sk_name in key_map.keys():
        current_buf = bytearray(original_data)
        print(f"\n🚀 [UNMERGED EVAL] КЛЮЧ: [{sk_name}]")
        
        # 1. Отключаем Merge на лету
        mirror_states = {}
        for obj in comp_objects:
            mirror_states[obj] = []
            for mod in obj.modifiers:
                if mod.type == 'MIRROR' and mod.show_viewport:
                    mirror_states[obj].append((mod, mod.use_mirror_merge, mod.use_clip))
                    mod.use_mirror_merge = False
                    mod.use_clip = False

        surface_data = []
        for obj in comp_objects:
            if not obj.data.shape_keys: continue
            
            for sk in obj.data.shape_keys.key_blocks: sk.value = 0.0
            bpy.context.view_layer.update()
            b_obj_eval = obj.evaluated_get(depsgraph)
            b_mesh = b_obj_eval.to_mesh()
            b_coords = [v.co.copy() for v in b_mesh.vertices]
            p_indices = [list(p.vertices) for p in b_mesh.polygons]
            b_poly_count = len(p_indices)
            bvh = BVHTree.FromPolygons(b_coords, p_indices)
            b_obj_eval.to_mesh_clear()
            
            target_sk = obj.data.shape_keys.key_blocks.get(sk_name)
            if target_sk: target_sk.value = 1.0
            bpy.context.view_layer.update()
            t_obj_eval = obj.evaluated_get(depsgraph)
            t_mesh = t_obj_eval.to_mesh()
            t_coords = [v.co.copy() for v in t_mesh.vertices]
            t_poly_count = len(t_mesh.polygons)
            t_obj_eval.to_mesh_clear()
            
            if len(b_coords) == len(t_coords) and b_poly_count == t_poly_count:
                surface_data.append({'bvh': bvh, 'p_indices': p_indices, 'b_coords': b_coords, 't_coords': t_coords})
            else:
                print(f"  ⚠️ {obj.name}: Пропущен (Сломана топология V:{len(b_coords)}->{len(t_coords)})")

        # 2. Возвращаем Merge
        for obj, mods in mirror_states.items():
            for mod, merge, clip in mods:
                mod.use_mirror_merge = merge
                mod.use_clip = clip

        matched = 0
        for i in range(buf_v_count):
            off = i * stride
            orig_v = Vector(struct.unpack_from("<3f", original_data, off))
            
            best_dist, best_hit = float('inf'), None
            for s_data in surface_data:
                loc, normal, face_idx, dist = s_data['bvh'].find_nearest(orig_v)
                if face_idx is not None and dist < best_dist:
                    best_dist, best_hit = dist, (s_data, face_idx)
            
            if best_hit and best_dist <= limit:
                s_data, face_idx = best_hit
                face_verts = s_data['p_indices'][face_idx]
                total_w, blended_delta = 0.0, Vector((0,0,0))
                for v_idx in face_verts:
                    v_dist = (s_data['b_coords'][v_idx] - orig_v).length
                    weight = 1.0 / (v_dist**2 + 1e-10)
                    blended_delta += (s_data['t_coords'][v_idx] - s_data['b_coords'][v_idx]) * weight
                    total_w += weight
                
                final_delta = blended_delta / total_w
                if final_delta.length > 1e-7:
                    struct.pack_into("<3f", current_buf, off, *(orig_v + final_delta))
                    matched += 1
                    
        print(f"  ✅ Запечено: {matched} вершин.")
        with open(os.path.join(output_dir, f"Component{comp_id}_VB0_{sk_name}.buf"), "wb") as f: f.write(current_buf)

def process_math_symmetry(comp_objects, original_data, stride, limit, output_dir, comp_id, key_map):
    """АЛГОРИТМ 3: Math Symmetry (Виртуальная генерация в Python)"""
    buf_v_count = len(original_data) // stride
    for sk_name in key_map.keys():
        current_buf = bytearray(original_data)
        print(f"\n🚀 [MATH SYMMETRY] КЛЮЧ: [{sk_name}]")
        
        surface_data = []
        for obj in comp_objects:
            if not obj.data.shape_keys: continue
            
            b_coords_raw = [v.co.copy() for v in obj.data.shape_keys.key_blocks[0].data]
            p_indices_raw = [list(p.vertices) for p in obj.data.polygons]
            
            target_sk = obj.data.shape_keys.key_blocks.get(sk_name)
            t_coords_raw = [v.co.copy() for v in target_sk.data] if target_sk else [v.co.copy() for v in b_coords_raw]
            
            # Проверка оси X в модификаторе Mirror
            has_mirror_x = any(m.type == 'MIRROR' and m.show_viewport and m.use_axis[0] for m in obj.modifiers)
            
            b_coords = b_coords_raw.copy()
            t_coords = t_coords_raw.copy()
            p_indices = p_indices_raw.copy()
            
            if has_mirror_x:
                offset = len(b_coords_raw)
                # Математически дублируем координаты (отражение по X)
                b_coords.extend([Vector((-v.x, v.y, v.z)) for v in b_coords_raw])
                t_coords.extend([Vector((-v.x, v.y, v.z)) for v in t_coords_raw])
                # Переворачиваем индексы полигонов для правильных нормалей BVH
                p_indices.extend([[v + offset for v in reversed(p)] for p in p_indices_raw])
            
            bvh = BVHTree.FromPolygons(b_coords, p_indices)
            surface_data.append({'bvh': bvh, 'p_indices': p_indices, 'b_coords': b_coords, 't_coords': t_coords})

        matched = 0
        for i in range(buf_v_count):
            off = i * stride
            orig_v = Vector(struct.unpack_from("<3f", original_data, off))
            
            best_dist, best_hit = float('inf'), None
            for s_data in surface_data:
                loc, normal, face_idx, dist = s_data['bvh'].find_nearest(orig_v)
                if face_idx is not None and dist < best_dist:
                    best_dist, best_hit = dist, (s_data, face_idx)
            
            if best_hit and best_dist <= limit:
                s_data, face_idx = best_hit
                face_verts = s_data['p_indices'][face_idx]
                total_w, blended_delta = 0.0, Vector((0,0,0))
                for v_idx in face_verts:
                    v_dist = (s_data['b_coords'][v_idx] - orig_v).length
                    weight = 1.0 / (v_dist**2 + 1e-10)
                    blended_delta += (s_data['t_coords'][v_idx] - s_data['b_coords'][v_idx]) * weight
                    total_w += weight
                
                final_delta = blended_delta / total_w
                if final_delta.length > 1e-7:
                    struct.pack_into("<3f", current_buf, off, *(orig_v + final_delta))
                    matched += 1
                    
        print(f"  ✅ Запечено: {matched} вершин.")
        with open(os.path.join(output_dir, f"Component{comp_id}_VB0_{sk_name}.buf"), "wb") as f: f.write(current_buf)

def run_auto_injection(context):
    props = context.scene.rayvich_auto_props
    active_obj = context.active_object
    if not active_obj: return "❌ Выдели объект компонента!"

    match = re.search(r"Component\s*(\d+)", active_obj.name, re.IGNORECASE)
    if not match: return "❌ Нет 'Component N' в имени!"
    comp_id = match.group(1)

    comp_objects = [o for o in bpy.data.objects if o.type == 'MESH' and f"Component {comp_id}" in o.name]
    root = bpy.path.abspath(props.mod_root)
    vb0_path = os.path.join(root, "Meshes", f"Component{comp_id}_VB0.buf")
    output_dir = os.path.join(root, "Blend")

    if not os.path.exists(vb0_path): return f"❌ Файл не найден: {vb0_path}"
    with open(vb0_path, "rb") as f:
        original_data = bytearray(f.read())

    key_map = {} 
    for o in comp_objects:
        if o.data.shape_keys and o.data.shape_keys.key_blocks:
            for sk in o.data.shape_keys.key_blocks:
                if sk == o.data.shape_keys.key_blocks[0]: continue
                key_map.setdefault(sk.name, []).append(o.name)

    print("\n" + "█"*10 + f" COMPONENT {comp_id} THE MIRROR ARCHITECT v8.0 " + "█"*10)
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    depsgraph = context.evaluated_depsgraph_get()
    set_armature_visibility(comp_objects, False)

    try:
        if props.algorithm == 'UNMERGED_EVAL':
            process_unmerged_eval(comp_objects, original_data, props.stride, props.distance_limit, output_dir, comp_id, key_map, depsgraph)
        elif props.algorithm == 'MATH_SYMMETRY':
            process_math_symmetry(comp_objects, original_data, props.stride, props.distance_limit, output_dir, comp_id, key_map)
        elif props.algorithm == 'CLASSIC_BVH':
            process_classic_bvh(comp_objects, original_data, props.stride, props.distance_limit, output_dir, comp_id, key_map)
    finally:
        set_armature_visibility(comp_objects, True)

    return "FINISHED"

# --- UI Регистрация ---
class VIEW3D_PT_rayvich_auto(bpy.types.Panel):
    bl_label = "Rayvich Auto Injector v8.0"
    bl_idname = "VIEW3D_PT_rayvich_auto"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Rayvich'
    def draw(self, context):
        layout = self.layout
        props = context.scene.rayvich_auto_props
        layout.prop(props, "mod_root")
        layout.prop(props, "stride")
        layout.prop(props, "distance_limit")
        layout.separator()
        layout.prop(props, "algorithm", expand=True)
        layout.separator()
        layout.operator("rayvich.run_auto_injection", text="ЗАПЕЧЬ", icon='PLAY')

class OT_RunAutoInjection(bpy.types.Operator):
    bl_idname = "rayvich.run_auto_injection"
    bl_label = "Run"
    def execute(self, context):
        res = run_auto_injection(context)
        if res == "FINISHED": self.report({'INFO'}, "Успех! Зеркала побеждены.")
        else: self.report({'ERROR'}, res)
        return {'FINISHED'}

def register():
    bpy.utils.register_class(RayvichAutoProperties)
    bpy.utils.register_class(VIEW3D_PT_rayvich_auto)
    bpy.utils.register_class(OT_RunAutoInjection)
    bpy.types.Scene.rayvich_auto_props = bpy.props.PointerProperty(type=RayvichAutoProperties)

def unregister():
    bpy.utils.unregister_class(RayvichAutoProperties)
    bpy.utils.unregister_class(VIEW3D_PT_rayvich_auto)
    bpy.utils.unregister_class(OT_RunAutoInjection)
    del bpy.types.Scene.rayvich_auto_props

if __name__ == "__main__": register()