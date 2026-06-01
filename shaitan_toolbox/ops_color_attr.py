import bpy
import numpy as np
import bmesh

def _clamp01(value):
    return max(0.0, min(1.0, float(value)))

def format_color_info(color):
    if color is None:
        return "RGBA: -, -, -, - | HEX8: -"

    r, g, b, a = (_clamp01(v) for v in color)
    hex8 = ''.join(f"{round(v * 255):02X}" for v in (r, g, b, a))
    return f"RGBA: {r:.4f}, {g:.4f}, {b:.4f}, {a:.4f} | HEX8: #{hex8}"

def is_color_attr_panel_active(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return False
    return (
        getattr(scene, "rzm_toolbox_mode", None) == 'SHAITAN'
        and getattr(scene, "rzm_st_sub_tab", None) == 'COLOR_ATTR'
    )

def _get_color_layer(mesh, target_name):
    if hasattr(mesh, "color_attributes"):
        layer = mesh.color_attributes.get(target_name)
        if layer is not None:
            return layer
    if hasattr(mesh, "vertex_colors"):
        return mesh.vertex_colors.get(target_name)
    return None

def _get_active_color_layer(mesh):
    if hasattr(mesh, "color_attributes"):
        active = getattr(mesh.color_attributes, "active_color", None)
        if active is not None:
            return active
        active = getattr(mesh.color_attributes, "active", None)
        if active is not None:
            return active
    if hasattr(mesh, "vertex_colors"):
        active = getattr(mesh.vertex_colors, "active", None)
        if active is not None:
            return active
    return None

def _get_sample_color_layer(mesh, target_name):
    return _get_color_layer(mesh, target_name) or _get_active_color_layer(mesh)

def _as_rgba(value):
    if value is None:
        return None
    if len(value) >= 4:
        return tuple(float(value[i]) for i in range(4))
    if len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]), 1.0)
    return None

def _get_bmesh_layer(layer_access, target_name):
    for layer_group_name in ("float_color", "color"):
        layer_group = getattr(layer_access.layers, layer_group_name, None)
        if layer_group is None:
            continue
        layer = layer_group.get(target_name)
        if layer is not None:
            return layer
    return None

def _get_bmesh_color_layer(bm, target_name):
    loop_layer = _get_bmesh_layer(bm.loops, target_name)
    if loop_layer is not None:
        return loop_layer, "LOOP"

    vert_layer = _get_bmesh_layer(bm.verts, target_name)
    if vert_layer is not None:
        return vert_layer, "VERT"

    return None, None

def _get_selected_edit_mode_colors(mesh, target_name):
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()

    layer, domain = _get_bmesh_color_layer(bm, target_name)
    if layer is None:
        return []

    colors = []
    if domain == "LOOP":
        for face in bm.faces:
            for loop in face.loops:
                if loop.vert.select or loop.edge.select or face.select:
                    color = _as_rgba(loop[layer])
                    if color is not None:
                        colors.append(color)
    else:
        for vert in bm.verts:
            if vert.select or any(edge.select for edge in vert.link_edges) or any(face.select for face in vert.link_faces):
                color = _as_rgba(vert[layer])
                if color is not None:
                    colors.append(color)

    return colors

def _new_color_layer(mesh, target_name):
    if hasattr(mesh, "color_attributes"):
        try:
            return mesh.color_attributes.new(name=target_name, type='BYTE_COLOR', domain='CORNER')
        except Exception:
            pass
    if hasattr(mesh, "vertex_colors"):
        return mesh.vertex_colors.new(name=target_name, do_init=True)
    return None

def _remove_color_layer(mesh, layer):
    if hasattr(mesh, "color_attributes") and mesh.color_attributes.get(layer.name) == layer:
        mesh.color_attributes.remove(layer)
        return
    if hasattr(mesh, "vertex_colors") and mesh.vertex_colors.get(layer.name) == layer:
        mesh.vertex_colors.remove(layer)

def get_selected_average_color(context, require_active_panel=True):
    """
    Returns the average RGBA color for selected vertices in Edit Mode,
    or the average RGBA color for the whole active mesh in Object Mode.
    """
    if require_active_panel and not is_color_attr_panel_active(context):
        return None

    obj = context.active_object
    if not obj or obj.type != 'MESH' or not obj.data:
        return None
        
    mesh = obj.data
    target_name = context.scene.rzm_st_paint_target
    layer = _get_sample_color_layer(mesh, target_name)
    if not layer:
        return None

    if obj.mode == 'EDIT':
        selected_colors = _get_selected_edit_mode_colors(mesh, layer.name)
        if not selected_colors:
            return None
        average_rgba = np.mean(np.asarray(selected_colors, dtype=np.float32), axis=0)
        return tuple(float(x) for x in average_rgba)
        
    n_loops = len(mesh.loops)
    if n_loops == 0:
        return None
        
    try:
        # Быстро получаем все цвета вершинных углов
        colors = np.empty(n_loops * 4, dtype=np.float32)
        layer.data.foreach_get('color', colors)
        colors = colors.reshape(-1, 4)
        
        average_rgba = np.mean(colors, axis=0)
        return tuple(float(x) for x in average_rgba)
    except Exception:
        pass
        
    return None

def get_selected_median_color(context):
    return get_selected_average_color(context)

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
        layer = _get_color_layer(mesh, target_name)
        if not layer:
            try:
                layer = _new_color_layer(mesh, target_name)
                if not layer:
                    raise RuntimeError("color attributes are not available")
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
    bl_description = "Paint the selected vertices or the entire mesh with the active picker color"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        target_color = list(scene.rzm_st_paint_color)
        target_name = scene.rzm_st_paint_target
        
        count = paint_mesh_with_color(context, target_color, target_name)
        if count > 0:
            self.report({'INFO'}, f"Painted {count} objects into layer '{target_name}'")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No selected meshes to paint")
            return {'CANCELLED'}

class RZM_ST_OT_SampleColor(bpy.types.Operator):
    bl_idname = "rzm_st.sample_color"
    bl_label = "Copy Selected Color"
    bl_description = "Copy the selected vertex color average, including alpha, into the active picker color"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        color = get_selected_average_color(context)
        if color is None:
            self.report({'WARNING'}, "No color data found on the active target layer")
            return {'CANCELLED'}

        context.scene.rzm_st_paint_color = tuple(_clamp01(v) for v in color)
        self.report({'INFO'}, f"Copied selected color: {format_color_info(color)}")
        return {'FINISHED'}

class RZM_ST_OT_PaintPresetColor(bpy.types.Operator):
    bl_idname = "rzm_st.paint_preset_color"
    bl_label = "Paint Preset Color"
    bl_description = "Paint the current selection directly with this preset color"
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
                self.report({'INFO'}, f"Painted with preset {self.index + 1} into layer '{target_name}'")
                return {'FINISHED'}
                
        return {'CANCELLED'}

class RZM_ST_OT_ClearColor(bpy.types.Operator):
    bl_idname = "rzm_st.clear_color"
    bl_label = "Remove Color Layer"
    bl_description = "Remove the selected color attribute from the selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_name = context.scene.rzm_st_paint_target
        objects = [o for o in context.selected_objects if o.type == 'MESH' and o.data]
        if not objects:
            self.report({'WARNING'}, "No selected meshes")
            return {'CANCELLED'}
            
        cleared_count = 0
        for obj in objects:
            layer = _get_color_layer(obj.data, target_name)
            if layer:
                _remove_color_layer(obj.data, layer)
                cleared_count += 1
                
        self.report({'INFO'}, f"Removed layer '{target_name}' from {cleared_count} objects")
        return {'FINISHED'}

classes_to_register = [
    RZM_ST_OT_PaintColor,
    RZM_ST_OT_SampleColor,
    RZM_ST_OT_PaintPresetColor,
    RZM_ST_OT_ClearColor,
]
