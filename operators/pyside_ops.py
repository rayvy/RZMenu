# RZMenu/operators/pyside_ops.py
import bpy
from bpy.app.handlers import persistent

# Импортируем наш PoC модуль
try:
    from ..qt_editor import poc_window
    qt_module_found = True
except ImportError:
    qt_module_found = False
    print("RZMenu: qt_editor module not found.")

# --- ОПЕРАТОРЫ ---

class RZM_OT_LaunchViewer(bpy.types.Operator):
    bl_idname = "rzm.launch_viewer"
    bl_label = "Open Viewer (Disabled)"
    @classmethod
    def poll(cls, context): return False
    def execute(self, context): return {'CANCELLED'}

class RZM_OT_LaunchInspector(bpy.types.Operator):
    bl_idname = "rzm.launch_inspector"
    bl_label = "Open Inspector (Disabled)"
    @classmethod
    def poll(cls, context): return False
    def execute(self, context): return {'CANCELLED'}

class RZM_OT_LaunchQTEditor(bpy.types.Operator):
    bl_idname = "rzm.launch_qt_editor"
    bl_label = "Launch PoC Editor"
    
    @classmethod
    def poll(cls, context):
        return qt_module_found

    def execute(self, context):
        if qt_module_found:
            poc_window.show_window()
            return {'FINISHED'}
        return {'CANCELLED'}

# @persistent
# def rzm_qt_updater(scene):
#     """
#     Этот хендлер вызывается Блендером после любого Undo (Ctrl+Z) или Redo (Ctrl+Shift+Z).
#     Мы проверяем, открыто ли наше окно, и если да — просим его обновить данные.
#     """
#     if qt_module_found and hasattr(poc_window, "_qt_window"):
#         win = poc_window._qt_window
#         if win and win.isVisible():
#             if hasattr(win, "sync_with_blender"):
#                 win.sync_with_blender()

@persistent
def rzm_on_undo(scene):
    """Срабатывает после Ctrl+Z"""
    if qt_module_found and hasattr(poc_window, "_qt_window"):
        win = poc_window._qt_window
        if win and win.isVisible():
            win.sync_with_blender(source="Blender UNDO")

@persistent
def rzm_on_redo(scene):
    """Срабатывает после Ctrl+Shift+Z"""
    if qt_module_found and hasattr(poc_window, "_qt_window"):
        win = poc_window._qt_window
        if win and win.isVisible():
            win.sync_with_blender(source="Blender REDO")

# --- REGISTRATION ---

classes_to_register = [
    RZM_OT_LaunchViewer,
    RZM_OT_LaunchInspector,
    RZM_OT_LaunchQTEditor,
]

def register():
    # Хендлеры (раздельные)
    if rzm_on_undo not in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.append(rzm_on_undo)
    
    if rzm_on_redo not in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.append(rzm_on_redo)

def unregister():
    if rzm_on_undo in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(rzm_on_undo)
    
    if rzm_on_redo in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(rzm_on_redo)