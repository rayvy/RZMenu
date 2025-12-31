import sys
import os
import bpy
from PySide6 import QtWidgets, QtCore
from .. import window

try:
    from PySide6 import QtWidgets, QtCore
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

class IntegrationManager:
    _app = None
    _window = None
    
    @classmethod
    def get_app(cls):
        app = QtWidgets.QApplication.instance()
        if not app:
            os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
            app = QtWidgets.QApplication(sys.argv)
        return app

    @staticmethod
    def process_qt_events():
        """Оставляет Qt живым внутри Blender"""
        app = QtWidgets.QApplication.instance()
        if app: app.processEvents()
        
        if IntegrationManager._window and not IntegrationManager._window.isVisible():
             IntegrationManager.stop()
             return None 
        return 0.01

    @classmethod
    def on_depsgraph_update(cls, scene, depsgraph):
        """
        Реакция на внешние изменения (Undo/Redo или манипуляции в Blender UI).
        """
        # Если изменение вызвано нашим же Qt кодом (core.IS_UPDATING_FROM_QT), игнорируем,
        # так как сигналы внутри core уже обновили UI мгновенно.
        if core.IS_UPDATING_FROM_QT:
            return

        # Если изменение внешнее - просим окно перечитать данные
        if cls._window and cls._window.isVisible():
            cls._window.sync_from_blender()

    @classmethod
    def launch(cls, context):
        if not PYSIDE_AVAILABLE:
            print("PySide6 missing.")
            return {'CANCELLED'}

        cls._app = cls.get_app()
        if cls._window is None:
            cls._window = window.RZMEditorWindow()
        
        cls._window.show()
        cls._window.activateWindow()
        
        win_state = cls._window.windowState()
        if win_state & QtCore.Qt.WindowMinimized:
             cls._window.setWindowState(win_state & ~QtCore.Qt.WindowMinimized)

        if not bpy.app.timers.is_registered(cls.process_qt_events):
            bpy.app.timers.register(cls.process_qt_events, persistent=True)
            
        if cls.on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(cls.on_depsgraph_update)
            
        cls._window.sync_from_blender()

    @classmethod
    def stop(cls):
        if bpy.app.timers.is_registered(cls.process_qt_events):
            bpy.app.timers.unregister(cls.process_qt_events)
        
        if cls.on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(cls.on_depsgraph_update)