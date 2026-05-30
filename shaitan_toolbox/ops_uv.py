import bpy
import numpy as np

def get_active_item(context):
    """Получает активный элемент из списка пресетов"""
    idx = context.scene.rzm_st_texcoord_list_index
    lst = context.scene.rzm_st_texcoord_list
    if 0 <= idx < len(lst):
        return lst[idx]
    return None

def ensure_uvmap_exists(obj):
    """
    Гарантирует, что у меша есть слой 'UVMap' и он стоит первым (или активным).
    Возвращает True, если успех.
    """
    mesh = obj.data
    if not mesh.uv_layers:
        # Пытаемся создать базовую разметку, если слоев вообще нет
        # (это поведение мы также переиспользуем в xxmi_data_predictor)
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

def apply_uv_math(obj, target_name, grid_x, grid_y, pos_x, pos_y):
    """
    Ядро математики UV Packer.
    pos_x, pos_y: Координаты из UI (0,0 - Верх-Лево).
    """
    mesh = obj.data
    
    # 1. Активируем UVMap как источник
    src_uv = mesh.uv_layers.get("UVMap")
    if not src_uv: return False
    mesh.uv_layers.active = src_uv
    
    # 2. Удаляем целевой слой, если есть (для обновления)
    if target_name in mesh.uv_layers:
        mesh.uv_layers.remove(mesh.uv_layers[target_name])
        
    # 3. Создаем новый слой (копирует данные из active)
    try:
        target_layer = mesh.uv_layers.new(name=target_name)
    except:
        return False
        
    if not target_layer: return False
    
    # 4. Numpy Математика
    layer_len = len(mesh.loops)
    if layer_len == 0: return True

    uvs = np.empty(layer_len * 2, dtype=np.float32)
    target_layer.data.foreach_get("uv", uvs)
    uvs = uvs.reshape(-1, 2)
    
    # Инвертируем Y индекс для математики
    math_pos_y = (grid_y - 1) - pos_y
    
    scale_x = 1.0 / max(1, grid_x)
    scale_y = 1.0 / max(1, grid_y)
    
    offset_x = pos_x * scale_x
    offset_y = math_pos_y * scale_y
    
    # Применяем: Сжать + Сдвинуть
    uvs[:, 0] = uvs[:, 0] * scale_x + offset_x
    uvs[:, 1] = uvs[:, 1] * scale_y + offset_y
    
    target_layer.data.foreach_set("uv", uvs.flatten())
    return True

class RZM_ST_OT_SetGridCell(bpy.types.Operator):
    bl_idname = "rzm_st.set_grid_cell"
    bl_label = "Set Grid Cell"
    bl_description = "Установить позицию (0,0 - Верхний Левый угол)"
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
    bl_label = "Записать и Применить (Активный)"
    bl_description = "Записывает параметры и создает развертку ТОЛЬКО для выделенной строки списка"
    bl_options = {'REGISTER', 'UNDO'}
    
    mode: bpy.props.StringProperty(default="BOTH") # "PARAM", "APPLY", "BOTH"

    def execute(self, context):
        item = get_active_item(context)
        if not item: return {'CANCELLED'}
        
        objects = context.selected_objects
        if not objects: return {'CANCELLED'}
        
        data_array = [item.grid_x, item.grid_y, item.pos_x, item.pos_y]
        
        for obj in objects:
            if obj.type != 'MESH': continue
            
            if not ensure_uvmap_exists(obj): continue
            
            if self.mode in {'PARAM', 'BOTH'}:
                obj["TEXCOORD_POS_SIZE"] = data_array
            
            if self.mode in {'APPLY', 'BOTH'}:
                g_x, g_y, p_x, p_y = item.grid_x, item.grid_y, item.pos_x, item.pos_y
                
                if self.mode == 'APPLY' and "TEXCOORD_POS_SIZE" in obj:
                    try:
                        p = obj["TEXCOORD_POS_SIZE"]
                        g_x, g_y, p_x, p_y = p[0], p[1], p[2], p[3]
                    except:
                        pass
                
                apply_uv_math(obj, item.target_name, g_x, g_y, p_x, p_y)

        self.report({'INFO'}, f"Обработан активный слой: {item.target_name}")
        return {'FINISHED'}

class RZM_ST_OT_ProcessAllLayers(bpy.types.Operator):
    bl_idname = "rzm_st.process_all_layers"
    bl_label = "Записать и Применить (Всё из списка)"
    bl_description = "Проходит по всему списку пресетов и создает слои по очереди для всех объектов"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        presets = context.scene.rzm_st_texcoord_list
        objects = context.selected_objects
        
        if not presets:
            self.report({'WARNING'}, "Список пуст")
            return {'CANCELLED'}
        
        if not objects:
            self.report({'WARNING'}, "Выберите объекты")
            return {'CANCELLED'}
            
        count_obj = 0
        
        for obj in objects:
            if obj.type != 'MESH': continue
            
            if not ensure_uvmap_exists(obj):
                self.report({'WARNING'}, f"Объект {obj.name} не имеет UV")
                continue
                
            count_obj += 1
            
            for item in presets:
                data_array = [item.grid_x, item.grid_y, item.pos_x, item.pos_y]
                obj["TEXCOORD_POS_SIZE"] = data_array
                apply_uv_math(obj, item.target_name, item.grid_x, item.grid_y, item.pos_x, item.pos_y)
                
        self.report({'INFO'}, f"Обработано {count_obj} объектов ({len(presets)} слоев каждый)")
        return {'FINISHED'}

class RZM_ST_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "target_name", text="", emboss=False, icon='TEXTURE')
            layout.label(text=f"[{item.grid_x}x{item.grid_y}] @ ({item.pos_x}, {item.pos_y})")

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

classes_to_register = [
    RZM_ST_OT_SetGridCell,
    RZM_ST_OT_ProcessActiveLayer,
    RZM_ST_OT_ProcessAllLayers,
    RZM_ST_UL_List,
    RZM_ST_OT_TexCoordListAdd,
    RZM_ST_OT_TexCoordListRemove,
]
