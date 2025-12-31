# RZMenu/qt_editor/__init__.py
import bpy
import sys
import os

# Try to import PySide6
try:
    from PySide6 import QtWidgets, QtCore
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

# NEW: Import the refactored main window
if PYSIDE_AVAILABLE:
    from . import main_window
else:
    main_window = None

# --- INTEGRATION MANAGER ---

class IntegrationManager:
    _app = None
    _window = None
    
    @classmethod
    def get_app(cls):
        """Ensures a singleton QApplication instance exists."""
        app = QtWidgets.QApplication.instance()
        if not app:
            # High-DPI scaling can be enabled here if needed
            # os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
            app = QtWidgets.QApplication(sys.argv)
        return app

    @staticmethod
    def process_qt_events():
        """
        Keeps the Qt event loop running smoothly inside Blender's modal context.
        This is called by a Blender timer.
        """
        app = QtWidgets.QApplication.instance()
        if app:
            app.processEvents()
        
        # If the window has been closed by the user, stop the timer.
        if IntegrationManager._window and not IntegrationManager._window.isVisible():
             IntegrationManager.stop()
             return None # Unregisters the timer
             
        return 0.01 # Repeat every 10ms

    @classmethod
    def launch(cls, context):
        """Launches the editor window."""
        if not PYSIDE_AVAILABLE:
            print("PySide6 is not available. Cannot launch RZMenu Editor.")
            return {'CANCELLED'}

        cls._app = cls.get_app()
        
        # Create a new window instance if it doesn't exist, or just show it.
        if cls._window is None:
            cls._window = main_window.RZMEditorWindow()
        
        cls._window.show()
        cls._window.activateWindow()
        
        # Bring to front if minimized
        if cls._window.windowState() & QtCore.Qt.WindowState.WindowMinimized:
             cls._window.setWindowState(cls._window.windowState() & ~QtCore.Qt.WindowState.WindowMinimized)

        # Register the Qt event loop timer if it's not already running.
        if not bpy.app.timers.is_registered(cls.process_qt_events):
            bpy.app.timers.register(cls.process_qt_events, persistent=True)

    @classmethod
    def stop(cls):
        """Cleans up resources, particularly the Blender timer."""
        if bpy.app.timers.is_registered(cls.process_qt_events):
            bpy.app.timers.unregister(cls.process_qt_events)
        
        # We don't destroy the window, just let it be garbage collected
        # if the reference is lost. This preserves its size and position.
        if cls._window:
            cls._window.close() # Ensure the window's closeEvent is called
            cls._window = None

class RZM_OT_LaunchQTEditor(bpy.types.Operator):
    """Launch the RZMenu Qt Editor"""
    bl_idname = "rzm.launch_qt_editor"
    bl_label = "Launch RZM Editor"
    
    @classmethod
    def poll(cls, context):
        return PYSIDE_AVAILABLE

    def execute(self, context):
        IntegrationManager.launch(context)
        return {'FINISHED'}

classes = [RZM_OT_LaunchQTEditor]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    IntegrationManager.stop()
    for cls in classes:
        bpy.utils.unregister_class(cls)