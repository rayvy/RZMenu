import bpy
import numpy as np

def get_active_item(context):
    """Gets the active item from the preset list."""
    idx = context.scene.rzm_st_texcoord_list_index
    lst = context.scene.rzm_st_texcoord_list
    if 0 <= idx < len(lst):
        return lst[idx]
    return None

def ensure_uvmap_exists(obj):
    """
    Ensures the mesh has a 'UVMap' layer and that it is first (or active).
    Returns True on success.
    """
    mesh = obj.data
    if not mesh.uv_layers:
        try:
            mesh.uv_layers.new(name="UVMap")
        except:
            return False
            
    if "UVMap" in mesh.uv_layers:
        mesh.uv_layers["UVMap"].active_render = True
        return True
    
    target = mesh.uv_layers.active if mesh.uv_layers.active else mesh.uv_layers[0]
    target.name = "UVMap"
    target.active_render = True
    return True

def standardize_uvmap(obj):
    mesh = obj.data
    if not mesh or obj.type != 'MESH':
        return False, "not a mesh"

    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
        mesh.update()
        return True, "created UVMap"

    uvmap = mesh.uv_layers.get("UVMap")
    if uvmap is None:
        uvmap = mesh.uv_layers[0]
        uvmap.name = "UVMap"
        action = "renamed first layer to UVMap"
    else:
        action = "kept UVMap"

    for layer in list(mesh.uv_layers):
        if layer.name != "UVMap":
            mesh.uv_layers.remove(layer)

    uvmap = mesh.uv_layers.get("UVMap")
    if uvmap:
        mesh.uv_layers.active = uvmap
        uvmap.active_render = True

    mesh.update()
    return True, action

def apply_uv_math(context, obj, target_name, grid_x, grid_y, pos_x, pos_y, packing_mode='SHIFT'):
    """
    Applies the transform or projection for the selected UV layer.
    """
    original_mode = obj.mode
    
    # 1. Если объект в Edit Mode, переключаем в Object Mode для безопасного манипулирования слоями
    if original_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
        
    mesh = obj.data
    
    # 2. Активируем/создаем базовый слой UVMap как источник
    if not ensure_uvmap_exists(obj):
        if obj.mode != original_mode:
            bpy.ops.object.mode_set(mode=original_mode)
        return False
        
    src_uv = mesh.uv_layers.get("UVMap")
    if not src_uv:
        if obj.mode != original_mode:
            bpy.ops.object.mode_set(mode=original_mode)
        return False
    mesh.uv_layers.active = src_uv
    
    # 3. Удаляем целевой слой, если есть (для полного обновления)
    if target_name in mesh.uv_layers:
        mesh.uv_layers.remove(mesh.uv_layers[target_name])
        
    # 4. Создаем новый слой (копирует данные из active, то есть из UVMap)
    try:
        target_layer = mesh.uv_layers.new(name=target_name)
    except Exception as e:
        print(f"Failed to create UV layer {target_name}: {e}")
        if obj.mode != original_mode:
            bpy.ops.object.mode_set(mode=original_mode)
        return False
        
    if not target_layer:
        if obj.mode != original_mode:
            bpy.ops.object.mode_set(mode=original_mode)
        return False
    
    layer_len = len(mesh.loops)
    if layer_len == 0:
        if obj.mode != original_mode:
            bpy.ops.object.mode_set(mode=original_mode)
        return True

    # Убеждаемся, что целевой слой активен
    mesh.uv_layers.active = target_layer

    if packing_mode == 'SHIFT':
        # Сдвиг/масштаб по сетке
        uvs = np.empty(layer_len * 2, dtype=np.float32)
        target_layer.data.foreach_get("uv", uvs)
        uvs = uvs.reshape(-1, 2)
        
        math_pos_y = (grid_y - 1) - pos_y
        scale_x = 1.0 / max(1, grid_x)
        scale_y = 1.0 / max(1, grid_y)
        offset_x = pos_x * scale_x
        offset_y = math_pos_y * scale_y
        
        uvs[:, 0] = uvs[:, 0] * scale_x + offset_x
        uvs[:, 1] = uvs[:, 1] * scale_y + offset_y
        target_layer.data.foreach_set("uv", uvs.flatten())

    elif packing_mode == 'OCTAHEDRAL':
        # Октаэдрическая упаковка нормалей вершин в диапазон [-1, 1]
        try:
            verts_normals = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            mesh.vertices.foreach_get("normal", verts_normals)
            verts_normals = verts_normals.reshape(-1, 3)
            
            loop_verts = np.empty(layer_len, dtype=np.int32)
            mesh.loops.foreach_get("vertex_index", loop_verts)
            
            normals = verts_normals[loop_verts]
            norms = np.linalg.norm(normals, axis=1, keepdims=True)
            norms[norms == 0.0] = 1.0
            normals = normals / norms
            
            x = normals[:, 0]
            y = normals[:, 1]
            z = normals[:, 2]
            
            l1 = np.abs(x) + np.abs(y) + np.abs(z)
            l1[l1 == 0.0] = 1.0
            
            u = x / l1
            v = y / l1
            
            neg_z = z < 0.0
            if np.any(neg_z):
                sign_u = np.where(u >= 0.0, 1.0, -1.0)
                sign_v = np.where(v >= 0.0, 1.0, -1.0)
                u_fold = (1.0 - np.abs(v)) * sign_u
                v_fold = (1.0 - np.abs(u)) * sign_v
                u = np.where(neg_z, u_fold, u)
                v = np.where(neg_z, v_fold, v)
                
            uvs = np.stack([u, v], axis=1)
            target_layer.data.foreach_set("uv", uvs.flatten())
        except Exception as e:
            print(f"Error in Octahedral encoding: {e}")
            if obj.mode != original_mode:
                bpy.ops.object.mode_set(mode=original_mode)
            return False

    elif packing_mode in {'PROJECT', 'PROJECT_INV'}:
        # Переключаемся в Edit Mode для выполнения проекции
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Выделяем все вершины для полной проекции
        bpy.ops.mesh.select_all(action='SELECT')
        
        # Находим VIEW_3D область для безопасного вызова
        area_override = None
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area_override = area
                    break
            if area_override:
                break
                
        try:
            if area_override:
                with context.temp_override(area=area_override):
                    bpy.ops.uv.project_from_view(scale_to_bounds=False)
            else:
                bpy.ops.uv.project_from_view(scale_to_bounds=False)
        except Exception as e:
            print(f"Projection failed: {e}")
            
        # Сразу переключаемся обратно в Object Mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Переполучаем ссылки на меш и слой после изменения режима (инвалидация)
        mesh = obj.data
        target_layer = mesh.uv_layers.get(target_name)
            
        # Если PROJECT_INV, инвертируем Y координату
        if packing_mode == 'PROJECT_INV' and target_layer:
            uvs = np.empty(layer_len * 2, dtype=np.float32)
            target_layer.data.foreach_get("uv", uvs)
            uvs = uvs.reshape(-1, 2)
            uvs[:, 1] = -uvs[:, 1]
            target_layer.data.foreach_set("uv", uvs.flatten())
            
    # Обновляем меш
    obj.data.update()

    # Возвращаем исходный режим
    if obj.mode != original_mode:
        bpy.ops.object.mode_set(mode=original_mode)
            
    return True

class RZM_ST_OT_SetGridCell(bpy.types.Operator):
    bl_idname = "rzm_st.set_grid_cell"
    bl_label = "Set Grid Cell"
    bl_description = "Set the position (0,0 = top-left corner)"
    bl_options = {'INTERNAL'} 

    x: bpy.props.IntProperty()
    y: bpy.props.IntProperty()

    def execute(self, context):
        item = get_active_item(context)
        if item:
            item.pos_x = self.x
            item.pos_y = self.y
        return {'FINISHED'}

class RZM_ST_OT_ProcessActiveLayer(bpy.types.Operator):
    bl_idname = "rzm_st.process_active_layer"
    bl_label = "Process Layers"
    bl_description = "Writes the active layer parameter and/or applies all layers from the list"
    bl_options = {'REGISTER', 'UNDO'}
    
    mode: bpy.props.StringProperty(default="BOTH") # "PARAM", "APPLY", "BOTH"

    def execute(self, context):
        scene = context.scene
        presets = scene.rzm_st_texcoord_list
        active_item = get_active_item(context)
        
        objects = [o for o in context.selected_objects if o.type == 'MESH' and o.data]
        if not objects:
            self.report({'WARNING'}, "No selected meshes")
            return {'CANCELLED'}
            
        # 1. Записать параметр (если PARAM или BOTH)
        if self.mode in {'PARAM', 'BOTH'}:
            if not active_item:
                self.report({'WARNING'}, "No active list item to write the parameter")
                return {'CANCELLED'}
            data_array = [active_item.grid_x, active_item.grid_y, active_item.pos_x, active_item.pos_y]
            for obj in objects:
                obj["TEXCOORD_POS_SIZE"] = data_array
                
        # 2. Применить сдвиг (если APPLY или BOTH) для ВСЕХ слоев из списка
        if self.mode in {'APPLY', 'BOTH'}:
            if not presets:
                self.report({'WARNING'}, "The layer list is empty")
                return {'CANCELLED'}
                
            count_applied = 0
            for obj in objects:
                for item in presets:
                    apply_uv_math(
                        context,
                        obj,
                        item.target_name,
                        item.grid_x,
                        item.grid_y,
                        item.pos_x,
                        item.pos_y,
                        item.packing_mode
                    )
                count_applied += 1
            self.report({'INFO'}, f"Applied all layers ({len(presets)}) to {count_applied} objects")
            
        return {'FINISHED'}

class RZM_ST_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "target_name", text="", emboss=False, icon='TEXTURE')
            # Отображаем режим упаковки и параметры сетки
            if item.packing_mode == 'SHIFT':
                layout.label(text=f"[{item.grid_x}x{item.grid_y}] ({item.pos_x},{item.pos_y})")
            else:
                layout.label(text=f"[{item.packing_mode}]")

class RZM_ST_OT_TexCoordListAdd(bpy.types.Operator):
    bl_idname = "rzm_st.texcoord_list_add"
    bl_label = "Add"
    def execute(self, context):
        item = context.scene.rzm_st_texcoord_list.add()
        count = len(context.scene.rzm_st_texcoord_list)
        if count == 1: item.target_name = "TEXCOORD.xy"
        elif count == 2: item.target_name = "TEXCOORD.zw"
        else: item.target_name = f"TEXCOORD{count-1}.xy"
        
        context.scene.rzm_st_texcoord_list_index = count - 1
        return {'FINISHED'}

class RZM_ST_OT_TexCoordListRemove(bpy.types.Operator):
    bl_idname = "rzm_st.texcoord_list_remove"
    bl_label = "Remove"
    def execute(self, context):
        idx = context.scene.rzm_st_texcoord_list_index
        context.scene.rzm_st_texcoord_list.remove(idx)
        context.scene.rzm_st_texcoord_list_index = min(max(0, idx - 1), len(context.scene.rzm_st_texcoord_list) - 1)
        return {'FINISHED'}

class RZM_ST_OT_StandardizeUVMap(bpy.types.Operator):
    bl_idname = "rzm_st.standardize_uvmap"
    bl_label = "Standardize UVMap"
    bl_description = "Keep or create only one UV layer named UVMap on active/selected mesh objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_meshes = [
            obj for obj in context.selected_objects
            if obj and obj.type == 'MESH' and obj.data
        ]
        active_obj = context.active_object

        if selected_meshes:
            objects = selected_meshes
        elif active_obj and active_obj.type == 'MESH' and active_obj.data:
            objects = [active_obj]
        else:
            self.report({'WARNING'}, "No active or selected mesh objects")
            return {'CANCELLED'}

        processed = 0
        failed = 0
        for obj in objects:
            try:
                ok, action = standardize_uvmap(obj)
                if ok:
                    processed += 1
                    print(f"[Shaitan UV] {obj.name}: {action}")
                else:
                    failed += 1
                    print(f"[Shaitan UV] {obj.name}: skipped ({action})")
            except Exception as e:
                failed += 1
                print(f"[Shaitan UV] {obj.name}: failed: {e}")

        if processed:
            self.report({'INFO'}, f"Standardized UVMap on {processed} object(s), failed {failed}.")
            return {'FINISHED'}

        self.report({'WARNING'}, f"No UVMap standardized, failed {failed}.")
        return {'CANCELLED'}

classes_to_register = [
    RZM_ST_OT_SetGridCell,
    RZM_ST_OT_ProcessActiveLayer,
    RZM_ST_UL_List,
    RZM_ST_OT_TexCoordListAdd,
    RZM_ST_OT_TexCoordListRemove,
    RZM_ST_OT_StandardizeUVMap,
]
