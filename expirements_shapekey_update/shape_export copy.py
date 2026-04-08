bl_info = {
    "name": "Rayvich Auto Injector v10.1",
    "author": "Rayvich & AI",
    "version": (10, 1),
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

def set_armature_visibility(objects, visible):
    """Отключает скелеты для чистой деформации"""
    for obj in objects:
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                mod.show_viewport = visible

def get_linked_targets(comp_objects):
    """Ищет объекты-кукловоды (Body), к которым привязана одежда"""
    targets = set()
    for obj in comp_objects:
        for mod in obj.modifiers:
            if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                targets.add(mod.target)
    return list(targets)

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

    stride = props.stride
    limit = props.distance_limit
    buf_v_count = len(original_data) // stride

    linked_targets = get_linked_targets(comp_objects)
    all_involved = comp_objects + linked_targets
    
    # Собираем все уникальные шейп-кеи (нативные + кукловодов)
    all_keys = set()
    for o in all_involved:
        if o.data.shape_keys:
            all_keys.update([sk.name for sk in o.data.shape_keys.key_blocks if sk != o.data.shape_keys.key_blocks[0]])

    print("\n" + "█"*10 + f" COMPONENT {comp_id} PUPPET MASTER v10.1 " + "█"*10)
    print(f"🔗 Кукловоды: {[t.name for t in linked_targets]}")
    
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    depsgraph = context.evaluated_depsgraph_get()
    
    # 1. Отключаем скелеты и защищаем Mirror (Merge/Clip)
    set_armature_visibility(all_involved, False)
    mirror_states = {}
    for obj in comp_objects:
        mirror_states[obj] = []
        for mod in obj.modifiers:
            if mod.type == 'MIRROR' and mod.show_viewport:
                mirror_states[obj].append((mod, mod.use_mirror_merge, mod.use_clip))
                mod.use_mirror_merge = False
                mod.use_clip = False

    try:
        # 2. Кэшируем БАЗОВОЕ СОСТОЯНИЕ (Basis) для всех объектов
        for obj in all_involved:
            if obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks: sk.value = 0.0
        bpy.context.view_layer.update()

        base_cache = {} # obj -> {coords, polys, bvh}
        for obj in comp_objects:
            b_obj_eval = obj.evaluated_get(depsgraph)
            b_eval = b_obj_eval.to_mesh()
            
            b_coords = [v.co.copy() for v in b_eval.vertices]
            p_indices = [list(p.vertices) for p in b_eval.polygons]
            bvh = BVHTree.FromPolygons(b_coords, p_indices) if b_coords else None
            
            base_cache[obj] = {
                'coords': b_coords,
                'polys': p_indices,
                'bvh': bvh
            }
            
            # --- ПРАВИЛЬНАЯ ОЧИСТКА ПАМЯТИ ---
            b_obj_eval.to_mesh_clear()

        # 3. Главный цикл по шейп-кеям
        for sk_name in all_keys:
            current_buf = bytearray(original_data)
            print(f"\n🚀 КЛЮЧ: [{sk_name}]")
            
            # Определяем, какие объекты будут деформироваться (Изоляция статики)
            active_objs = []
            for obj in comp_objects:
                is_active = False
                # А) Есть нативный ключ
                if obj.data.shape_keys and sk_name in obj.data.shape_keys.key_blocks:
                    is_active = True
                else:
                    # Б) Есть кукловод с этим ключом
                    for mod in obj.modifiers:
                        if mod.type in {'SURFACE_DEFORM', 'SHRINKWRAP'} and mod.show_viewport and mod.target:
                            t = mod.target
                            if t.data.shape_keys and sk_name in t.data.shape_keys.key_blocks:
                                is_active = True
                                break
                if is_active:
                    active_objs.append(obj)

            if not active_objs:
                print("  ⏭️ Нет активных объектов/кукловодов для этого ключа. Пропуск.")
                continue

            # Активируем нужный ключ на всех объектах
            for obj in all_involved:
                if obj.data.shape_keys:
                    for sk in obj.data.shape_keys.key_blocks:
                        sk.value = 1.0 if sk.name == sk_name else 0.0
            bpy.context.view_layer.update()

            # Кэшируем ЦЕЛЕВОЕ СОСТОЯНИЕ только для активных
            target_cache = {}
            for obj in active_objs:
                t_obj_eval = obj.evaluated_get(depsgraph)
                t_eval = t_obj_eval.to_mesh()
                
                t_coords = [v.co.copy() for v in t_eval.vertices]
                
                # --- ПРАВИЛЬНАЯ ОЧИСТКА ПАМЯТИ ---
                t_obj_eval.to_mesh_clear()
                
                if len(t_coords) == len(base_cache[obj]['coords']):
                    target_cache[obj] = t_coords
                else:
                    print(f"  ⚠️ {obj.name}: Топология сломана ({len(base_cache[obj]['coords'])} != {len(t_coords)}).")

            # 4. ИНЪЕКЦИЯ БУФЕРА (С жесткой привязкой к владельцу)
            matched_total = 0
            for i in range(buf_v_count):
                off = i * stride
                orig_v = Vector(struct.unpack_from("<3f", original_data, off))
                
                # Ищем "Владельца" этой вершины (строго среди Base BVH)
                owner_obj = None
                best_dist = float('inf')
                best_face = None
                
                for obj, data in base_cache.items():
                    if not data['bvh']: continue
                    loc, normal, face_idx, dist = data['bvh'].find_nearest(orig_v)
                    if face_idx is not None and dist < best_dist:
                        best_dist = dist
                        owner_obj = obj
                        best_face = face_idx

                # Если владелец найден и он АКТИВЕН для этого ключа -> применяем дельту
                if owner_obj and best_dist <= limit:
                    if owner_obj in target_cache:
                        face_verts = base_cache[owner_obj]['polys'][best_face]
                        b_coords = base_cache[owner_obj]['coords']
                        t_coords = target_cache[owner_obj]
                        
                        total_w = 0.0
                        blended_delta = Vector((0,0,0))
                        
                        # BVH Интерполяция внутри конкретного полигона владельца
                        for v_idx in face_verts:
                            v_dist = (b_coords[v_idx] - orig_v).length
                            weight = 1.0 / (v_dist**2 + 1e-10)
                            blended_delta += (t_coords[v_idx] - b_coords[v_idx]) * weight
                            total_w += weight
                        
                        final_delta = blended_delta / total_w
                        
                        if final_delta.length > 1e-7:
                            new_pos = orig_v + final_delta
                            struct.pack_into("<3f", current_buf, off, *new_pos)
                            matched_total += 1
                    # Если owner_obj НЕ в target_cache, он Static -> дельта = 0, пропускаем.

            print(f"  ✅ Запечено вершин: {matched_total}")
            if matched_total > 0:
                with open(os.path.join(output_dir, f"Component{comp_id}_VB0_{sk_name}.buf"), "wb") as f: f.write(current_buf)

    finally:
        # Восстанавливаем всё как было
        set_armature_visibility(all_involved, True)
        for obj in all_involved:
            if obj.data.shape_keys:
                for sk in obj.data.shape_keys.key_blocks: sk.value = 0.0
        
        for obj, mods in mirror_states.items():
            for mod, merge, clip in mods:
                mod.use_mirror_merge = merge
                mod.use_clip = clip

    return "FINISHED"

class VIEW3D_PT_rayvich_auto(bpy.types.Panel):
    bl_label = "Rayvich Auto Injector v10.1"
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
        layout.operator("rayvich.run_auto_injection", text="ЗАПЕЧЬ PUPPET MASTER", icon='ARMATURE_DATA')

class OT_RunAutoInjection(bpy.types.Operator):
    bl_idname = "rayvich.run_auto_injection"
    bl_label = "Run"
    def execute(self, context):
        res = run_auto_injection(context)
        if res == "FINISHED": self.report({'INFO'}, "Успех! Объекты изолированы, модификаторы запечены.")
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