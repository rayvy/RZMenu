# RZMenu/qt_editor/context.py
import bpy

def get_stable_context():
    if bpy.context.area and bpy.context.area.type == 'VIEW_3D':
        return bpy.context.copy()
    
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if not region and area.regions: region = area.regions[0]
                return {
                    'window': window, 'screen': screen, 'area': area, 
                    'region': region, 'scene': window.scene, 'workspace': window.workspace
                }
    return {}

def exec_in_context(op_func, **kwargs):
    ctx = get_stable_context()
    if not ctx: return {'CANCELLED'}
    try:
        if hasattr(bpy.context, "temp_override"):
            with bpy.context.temp_override(**ctx): return op_func(**kwargs)
        else:
            return op_func(ctx, **kwargs)
    except Exception as e:
        print(f"RZM Context Error: {e}")
        return {'CANCELLED'}

def refresh_viewports():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()

def safe_undo_push(message):
    exec_in_context(bpy.ops.ed.undo_push, message=message)
    refresh_viewports()