# RZMenu/qt_editor/__init__.py
import bpy
import sys
import os # Добавлено

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
        
        # --- FIX DPI ISSUES ---
        # Устанавливаем переменные окружения ДО создания QApplication
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        
        app = QtWidgets.QApplication.instance()
        if not app:
            # Если Blender еще не создал Qt контекст, создаем его
            app = QtWidgets.QApplication(sys.argv)
        
        # 2. Создание окна
        if _editor_instance is None:
            # Защита от повторного открытия при ошибках
            try:
                _editor_instance = window.RZMEditorWindow()
            except Exception as e:
                self.report({'ERROR'}, f"Failed to open window: {e}")
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}
        
        # 3. Показ
        _editor_instance.show()
        _editor_instance.activateWindow()
        
        # Fix minimized state
        win_state = _editor_instance.windowState()
        if win_state & QtCore.Qt.WindowMinimized:
             _editor_instance.setWindowState(win_state & ~QtCore.Qt.WindowMinimized)
        
        # 4. Таймер
        if not bpy.app.timers.is_registered(auto_refresh_ui):
            bpy.app.timers.register(auto_refresh_ui, first_interval=0.1)
            
        return {'FINISHED'}

def auto_refresh_ui():
    """HEARTBEAT"""
    global _editor_instance
    
    # Если окно закрыто или уничтожено - останавливаем таймер
    if _editor_instance is None:
        return None
        
    try:
        if not _editor_instance.isVisible():
             return 1.0 # Редкая проверка, если окно скрыто
             
        if hasattr(_editor_instance, "brute_force_refresh"):
            _editor_instance.brute_force_refresh()
            
    except RuntimeError:
        # C++ объект удален (окно закрыли крестиком)
        _editor_instance = None
        return None
    except Exception as e:
        print(f"RZM Heartbeat Error: {e}")
        return None 
        
    return 0.1

classes = [RZM_OT_LaunchQTEditor]

def register():
    for cls in classes: bpy.utils.register_class(cls)

def unregister():
    if bpy.app.timers.is_registered(auto_refresh_ui):
        bpy.app.timers.unregister(auto_refresh_ui)
    for cls in classes: bpy.utils.unregister_class(cls)