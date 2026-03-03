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

# --- 4. Тестовые операторы (Apple Magic / Новая архитектура) ---
class RZM_OT_LaunchAppleDemo(bpy.types.Operator):
    """Launch the Apple-style UX demonstration window."""
    bl_idname = "rzm.launch_apple_demo"
    bl_label = "Apple UX Demo"
    
    def execute(self, context):
        if not PYSIDE_AVAILABLE:
            self.report({'ERROR'}, "PySide6 missing!")
            return {'CANCELLED'}
        
        from . import test
        test.run_apple_demo()
        return {'FINISHED'}

class RZM_OT_LaunchGfxEditorTest(bpy.types.Operator):
    bl_idname = "rzm.launch_gfx_test"
    bl_label = "Gfx Editor (Wait)"
    def execute(self, context):
        self.report({'INFO'}, "Graphics Editor is planned for March-May.")
        return {'FINISHED'}

class RZM_OT_Launch3DPreviewTest(bpy.types.Operator):
    bl_idname = "rzm.launch_3d_test"
    bl_label = "3D Preview (Wait)"
    def execute(self, context):
        self.report({'INFO'}, "3D Preview is planned for Oct-Dec.")
        return {'FINISHED'}

classes = [
    RZM_OT_LaunchQTEditor,
    RZM_OT_LaunchAppleDemo,
    RZM_OT_LaunchGfxEditorTest,
    RZM_OT_Launch3DPreviewTest
]

def register():
    for cls in classes: 
        bpy.utils.register_class(cls)

def unregister():
    if PYSIDE_AVAILABLE and IntegrationManager:
        IntegrationManager.stop()
    for cls in classes: 
        bpy.utils.unregister_class(cls)