# RZMenu/qt_editor/__init__.py
import bpy
import sys

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

class RZM_OT_LaunchQTEditor(bpy.types.Operator):
    """Launch the RZMenu Qt Editor (Brute Force Mode)"""
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
        
        # 1. Инициализация
        app = QtWidgets.QApplication.instance()
        if not app:
            app = QtWidgets.QApplication(sys.argv)
        
        # 2. Создание окна
        if _editor_instance is None:
            _editor_instance = window.RZMEditorWindow()
        
        # 3. Показ
        _editor_instance.show()
        _editor_instance.activateWindow()
        
        # Исправление ошибки с атрибутом Qt
        win_state = _editor_instance.windowState()
        if win_state & QtCore.Qt.WindowMinimized:
             _editor_instance.setWindowState(win_state & ~QtCore.Qt.WindowMinimized)
        
        # 4. Таймер
        if not bpy.app.timers.is_registered(auto_refresh_ui):
            bpy.app.timers.register(auto_refresh_ui, first_interval=0.1)
            
        return {'FINISHED'}

def auto_refresh_ui():
    """HEARTBEAT: Обновляет UI каждые 0.1 сек"""
    global _editor_instance
    if _editor_instance is None or not _editor_instance.isVisible():
        return 1.0 
    
    try:
        if hasattr(_editor_instance, "brute_force_refresh"):
            _editor_instance.brute_force_refresh()
    except Exception as e:
        print(f"RZM Qt Heartbeat Error: {e}")
        return None 
        
    return 0.1

classes = [RZM_OT_LaunchQTEditor]

def register():
    for cls in classes: bpy.utils.register_class(cls)

def unregister():
    if bpy.app.timers.is_registered(auto_refresh_ui):
        bpy.app.timers.unregister(auto_refresh_ui)
    for cls in classes: bpy.utils.unregister_class(cls)