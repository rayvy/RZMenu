import bpy
import numpy as np
import bmesh

def get_selected_median_color(context):
    """
    Вычисляет медианное значение цвета и альфы для выделенных вершин (в Edit Mode)
    или для всей модели (в Object Mode).
    """
    obj = context.active_object
    if not obj or obj.type != 'MESH' or not obj.data:
        return None
        
    mesh = obj.data
    target_name = context.scene.rzm_st_paint_target
    layer = mesh.vertex_colors.get(target_name)
    if not layer:
        return None
        
    n_loops = len(mesh.loops)
    if n_loops == 0:
        return None
        
    try:
        # Быстро получаем все цвета вершинных углов
        colors = np.empty(n_loops * 4, dtype=np.float32)
        layer.data.foreach_get('color', colors)
        colors = colors.reshape(-1, 4)
        
        if obj.mode == 'EDIT':
            # В Edit Mode определяем только выделенные вершины
            bm = bmesh.from_edit_mesh(mesh)
            selected_verts = {v.index for v in bm.verts if v.select}
            if not selected_verts:
                return None
                
            loop_verts = np.empty(n_loops, dtype=np.int32)
            mesh.loops.foreach_get('vertex_index', loop_verts)
            
            mask = np.isin(loop_verts, list(selected_verts))
            selected_colors = colors[mask]
            if len(selected_colors) == 0:
                return None
            
            median_rgba = np.median(selected_colors, axis=0)
            return tuple(float(x) for x in median_rgba)
        else:
            # В Object Mode возвращаем медиану по всему объекту
            median_rgba = np.median(colors, axis=0)
            return tuple(float(x) for x in median_rgba)
    except Exception:
        pass
        
    return None

class RZM_ST_OT_PaintColor(bpy.types.Operator):
    bl_idname = "rzm_st.paint_color"
    bl_label = "Paint Selected Color"
    bl_description = "Покрасить выделенные вершины или весь меш"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        target_color = list(scene.rzm_st_paint_color)
        target_name = scene.rzm_st_paint_target
        
        objects = [o for o in context.selected_objects if o.type == 'MESH' and o.data]
        if not objects:
            self.report({'WARNING'}, "Нет выделенных мешей")
            return {'CANCELLED'}
            
        painted_count = 0
        
        for obj in objects:
            mesh = obj.data
            original_mode = obj.mode
            
            # 1. Получаем список выделенных вершин если мы в Edit Mode
            selected_vert_indices = set()
            if original_mode == 'EDIT':
                # Переключаемся временно в OBJECT для безопасного применения данных
                bm = bmesh.from_edit_mesh(mesh)
                selected_vert_indices = {v.index for v in bm.verts if v.select}
                bpy.ops.object.mode_set(mode='OBJECT')
            
            # 2. Гарантируем наличие слоя цвета
            layer = mesh.vertex_colors.get(target_name)
            if not layer:
                try:
                    layer = mesh.vertex_colors.new(name=target_name, do_init=True)
                except Exception as e:
                    self.report({'ERROR'}, f"Не удалось создать слой '{target_name}': {e}")
                    if original_mode == 'EDIT':
                        bpy.ops.object.mode_set(mode='EDIT')
                    continue
            
            n_loops = len(mesh.loops)
            if n_loops == 0:
                if original_mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='EDIT')
                continue
                
            try:
                # 3. Красим по NumPy маске
                if selected_vert_indices:
                    # Читаем текущие цвета
                    colors = np.empty(n_loops * 4, dtype=np.float32)
                    layer.data.foreach_get('color', colors)
                    colors = colors.reshape(-1, 4)
                    
                    # Получаем индексы вершин для углов
                    loop_verts = np.empty(n_loops, dtype=np.int32)
                    mesh.loops.foreach_get('vertex_index', loop_verts)
                    
                    # Создаем маску
                    mask = np.isin(loop_verts, list(selected_vert_indices))
                    colors[mask] = target_color
                    
                    layer.data.foreach_set('color', colors.flatten())
                else:
                    # Заливаем весь объект целиком
                    colors = np.tile(target_color, n_loops)
                    layer.data.foreach_set('color', colors)
                    
                painted_count += 1
            except Exception as e:
                self.report({'ERROR'}, f"Ошибка покраски {obj.name}: {e}")
                
            # Восстанавливаем режим
            if original_mode == 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
                
        self.report({'INFO'}, f"Окрашено объектов: {painted_count} в слой '{target_name}'")
        return {'FINISHED'}

class RZM_ST_OT_ClearColor(bpy.types.Operator):
    bl_idname = "rzm_st.clear_color"
    bl_label = "Remove Color Layer"
    bl_description = "Удалить выбранный атрибут цвета с выделенных объектов"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_name = context.scene.rzm_st_paint_target
        objects = [o for o in context.selected_objects if o.type == 'MESH' and o.data]
        if not objects:
            self.report({'WARNING'}, "Нет выделенных мешей")
            return {'CANCELLED'}
            
        cleared_count = 0
        for obj in objects:
            layer = obj.data.vertex_colors.get(target_name)
            if layer:
                obj.data.vertex_colors.remove(layer)
                cleared_count += 1
                
        self.report({'INFO'}, f"Удален слой '{target_name}' с {cleared_count} объектов")
        return {'FINISHED'}

class RZM_ST_OT_LoadPreset(bpy.types.Operator):
    bl_idname = "rzm_st.load_preset"
    bl_label = "Load Preset Color"
    bl_description = "Загрузить цвет пресета в пикер"
    bl_options = {'INTERNAL'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        prefs = context.preferences.addons.get('RZMenu')
        if prefs:
            palette = prefs.preferences.rzm_st_palette
            if 0 <= self.index < len(palette):
                context.scene.rzm_st_paint_color = palette[self.index].color
                context.preferences.addons['RZMenu'].preferences.rzm_st_palette_index = self.index
        return {'FINISHED'}

class RZM_ST_OT_SavePreset(bpy.types.Operator):
    bl_idname = "rzm_st.save_preset"
    bl_label = "Save Preset Color"
    bl_description = "Сохранить текущий цвет пикера в выбранный слот пресета"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        prefs = context.preferences.addons.get('RZMenu')
        if prefs:
            palette = prefs.preferences.rzm_st_palette
            if 0 <= self.index < len(palette):
                palette[self.index].color = context.scene.rzm_st_paint_color
                self.report({'INFO'}, f"Пресет {self.index + 1} перезаписан")
        return {'FINISHED'}

class RZM_ST_OT_SetChannelValue(bpy.types.Operator):
    bl_idname = "rzm_st.set_channel_value"
    bl_label = "Set Color Channel"
    bl_description = "Быстро установить значение для конкретного канала цвета"
    bl_options = {'INTERNAL', 'UNDO'}

    channel: bpy.props.EnumProperty(
        items=[
            ('R', 'Red', ''),
            ('G', 'Green', ''),
            ('B', 'Blue', ''),
            ('A', 'Alpha', ''),
        ]
    )
    value: bpy.props.FloatProperty()

    def execute(self, context):
        col = list(context.scene.rzm_st_paint_color)
        if self.channel == 'R': col[0] = self.value
        elif self.channel == 'G': col[1] = self.value
        elif self.channel == 'B': col[2] = self.value
        elif self.channel == 'A': col[3] = self.value
        context.scene.rzm_st_paint_color = col
        return {'FINISHED'}

classes_to_register = [
    RZM_ST_OT_PaintColor,
    RZM_ST_OT_ClearColor,
    RZM_ST_OT_LoadPreset,
    RZM_ST_OT_SavePreset,
    RZM_ST_OT_SetChannelValue,
]
