# RZMenu/qt_editor/__init__.py
import bpy
from .core.launcher import IntegrationManager

try:
    from PySide6 import QtWidgets, QtCore
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    from . import window
else:
    window = None

class RZM_OT_LaunchQTEditor(bpy.types.Operator):
    bl_idname = "rzm.launch_qt_editor"
    bl_label = "Launch RZM Editor"
    
    @classmethod
    def poll(cls, context): return PYSIDE_AVAILABLE

    def execute(self, context):
        IntegrationManager.launch(context)
        return {'FINISHED'}

classes = [RZM_OT_LaunchQTEditor]

def register():
    for cls in classes: bpy.utils.register_class(cls)

def unregister():
    IntegrationManager.stop()
    for cls in classes: bpy.utils.unregister_class(cls)