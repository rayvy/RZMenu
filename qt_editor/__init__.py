# RZMenu/qt_editor/__init__.py
import bpy
import sys
import os
from bpy.app.handlers import persistent

try:
    from PySide6 import QtWidgets, QtCore
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    from . import window
else:
    window = None

_editor_instance = None

# --- HANDLERS (СЛУШАТЕЛИ) ---

@persistent
def rzm_undo_redo_handler(scene):
    """Вызывается Blender'ом после Undo/Redo"""
    global _editor_instance
    if _editor_instance and PYSIDE_AVAILABLE:
        try:
            if _editor_instance.isVisible():
                _editor_instance.brute_force_refresh()
        except RuntimeError:
            pass 

class RZM_OT_LaunchQTEditor(bpy.types.Operator):
    """Launch the RZMenu Qt Editor"""
    bl_idname = "rzm.launch_qt_editor"
    bl_label = "Launch RZM Editor"
    
    @classmethod
    def poll(cls, context):
        return PYSIDE_AVAILABLE

    def execute(self, context):
        global _editor_instance
        
        if not PYSIDE_AVAILABLE:
            self.report({'ERROR'}, "PySide6 not installed")
            return {'CANCELLED'}
        
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        
        app = QtWidgets.QApplication.instance()
        if not app:
            app = QtWidgets.QApplication(sys.argv)
        
        if _editor_instance is None:
            try:
                _editor_instance = window.RZMEditorWindow()
            except Exception as e:
                self.report({'ERROR'}, f"Failed to open window: {e}")
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}
        
        _editor_instance.show()
        _editor_instance.activateWindow()
        
        win_state = _editor_instance.windowState()
        if win_state & QtCore.Qt.WindowMinimized:
             _editor_instance.setWindowState(win_state & ~QtCore.Qt.WindowMinimized)
        
        if not bpy.app.timers.is_registered(auto_refresh_ui):
            bpy.app.timers.register(auto_refresh_ui, first_interval=0.1)
            
        return {'FINISHED'}

def auto_refresh_ui():
    """Таймер для проверки жизни окна"""
    global _editor_instance
    if _editor_instance is None:
        return None  
    try:
        if not _editor_instance.isVisible():
             return 1.0 
    except RuntimeError:
        _editor_instance = None
        return None
    return 0.1

classes = [RZM_OT_LaunchQTEditor]

def register():
    for cls in classes: bpy.utils.register_class(cls)
    
    # --- FIX INIT LAGS: PREVENT DUPLICATION ---
    if rzm_undo_redo_handler in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(rzm_undo_redo_handler)
    if rzm_undo_redo_handler in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(rzm_undo_redo_handler)
        
    bpy.app.handlers.undo_post.append(rzm_undo_redo_handler)
    bpy.app.handlers.redo_post.append(rzm_undo_redo_handler)

def unregister():
    if rzm_undo_redo_handler in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(rzm_undo_redo_handler)
    if rzm_undo_redo_handler in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(rzm_undo_redo_handler)
        
    if bpy.app.timers.is_registered(auto_refresh_ui):
        bpy.app.timers.unregister(auto_refresh_ui)
    for cls in classes: bpy.utils.unregister_class(cls)