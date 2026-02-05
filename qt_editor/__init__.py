# RZMenu/qt_editor/__init__.py
import bpy

# --- 1. Сначала проверяем библиотеку ---
try:
    from PySide6 import QtWidgets, QtCore
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

# --- 2. Импортируем зависимые модули ТОЛЬКО если библиотека есть ---
if PYSIDE_AVAILABLE:
    # Перенесли импорт Launcher сюда, так как он зависит от PySide
    from .core.launcher import IntegrationManager
    from . import window
else:
    IntegrationManager = None
    window = None

# --- 3. Оператор запуска ---
class RZM_OT_LaunchQTEditor(bpy.types.Operator):
    bl_idname = "rzm.launch_qt_editor"
    bl_label = "Launch RZM Editor"
    
    @classmethod
    def poll(cls, context): 
        # Кнопка будет неактивна, если нет PySide
        return PYSIDE_AVAILABLE

    def execute(self, context):
        if not PYSIDE_AVAILABLE:
            self.report({'ERROR'}, "PySide6 library is missing!")
            return {'CANCELLED'}
        
        IntegrationManager.launch(context)
        return {'FINISHED'}

classes = [RZM_OT_LaunchQTEditor]

def register():
    for cls in classes: 
        bpy.utils.register_class(cls)

def unregister():
    if PYSIDE_AVAILABLE and IntegrationManager:
        IntegrationManager.stop()
    for cls in classes: 
        bpy.utils.unregister_class(cls)