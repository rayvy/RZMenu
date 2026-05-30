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

def paint_mesh_with_color(context, target_color, target_name=None):
    """
    Покрасить выделенные вершины (в Edit Mode) или весь меш (в Object Mode)
    указанным цветом с использованием NumPy.
    """
    if target_name is None:
        target_name = context.scene.rzm_st_paint_target
        
    objects = [o for o in context.selected_objects if o.type == 'MESH' and o.data]
    if not objects:
        return 0
        
    painted_count = 0
    for obj in objects:
        mesh = obj.data
        original_mode = obj.mode
        
        # 1. Получаем список выделенных вершин если мы в Edit Mode
        selected_vert_indices = set()
        if original_mode == 'EDIT':
            bm = bmesh.from_edit_mesh(mesh)
            selected_vert_indices = {v.index for v in bm.verts if v.select}
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # 2. Гарантируем наличие слоя цвета
        layer = mesh.vertex_colors.get(target_name)
        if not layer:
            try:
                layer = mesh.vertex_colors.new(name=target_name, do_init=True)
            except Exception as e:
                print(f"Failed to create color layer {target_name} on {obj.name}: {e}")
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
                colors = np.empty(n_loops * 4, dtype=np.float32)
                layer.data.foreach_get('color', colors)
                colors = colors.reshape(-1, 4)
                
                loop_verts = np.empty(n_loops, dtype=np.int32)
                mesh.loops.foreach_get('vertex_index', loop_verts)
                
                mask = np.isin(loop_verts, list(selected_vert_indices))
                colors[mask] = target_color
                
                layer.data.foreach_set('color', colors.flatten())
            else:
                colors = np.tile(target_color, n_loops)
                layer.data.foreach_set('color', colors)
                
            painted_count += 1
        except Exception as e:
            print(f"Error painting {obj.name}: {e}")
            
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
            
    return painted_count

class RZM_ST_OT_PaintColor(bpy.types.Operator):
    bl_idname = "rzm_st.paint_color"
    bl_label = "Paint Selected Color"
    bl_description = "Покрасить выделенные вершины или весь меш активным цветом пикера"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        target_color = list(scene.rzm_st_paint_color)
        target_name = scene.rzm_st_paint_target
        
        count = paint_mesh_with_color(context, target_color, target_name)
        if count > 0:
            self.report({'INFO'}, f"Окрашено объектов: {count} в слой '{target_name}'")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Нет выделенных мешей для покраски")
            return {'CANCELLED'}

class RZM_ST_OT_PaintPresetColor(bpy.types.Operator):
    bl_idname = "rzm_st.paint_preset_color"
    bl_label = "Paint Preset Color"
    bl_description = "Покрасить выделение цветом этого пресета напрямую"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        prefs = context.preferences.addons.get('RZMenu')
        if not prefs:
            return {'CANCELLED'}
            
        palette = prefs.preferences.rzm_st_palette
        if 0 <= self.index < len(palette):
            target_color = list(palette[self.index].color)
            target_name = context.scene.rzm_st_paint_target
            count = paint_mesh_with_color(context, target_color, target_name)
            if count > 0:
                self.report({'INFO'}, f"Покрашено пресетом {self.index + 1} в слой '{target_name}'")
                return {'FINISHED'}
                
        return {'CANCELLED'}

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

classes_to_register = [
    RZM_ST_OT_PaintColor,
    RZM_ST_OT_PaintPresetColor,
    RZM_ST_OT_ClearColor,
]
