import sys
import os
import bpy
from PySide6 import QtWidgets, QtCore
from .. import window
from . import signals

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
    @bpy.app.handlers.persistent
    def on_depsgraph_update(cls, scene, depsgraph=None):
        """
        Реакция на внешние изменения (Undo/Redo или манипуляции в Blender UI).
        """
        # Если изменение вызвано нашим же Qt кодом (signals.IS_UPDATING_FROM_QT), игнорируем,
        # так как сигналы внутри core уже обновили UI мгновенно.
        if signals.IS_UPDATING_FROM_QT:
            return

        # Если изменение внешнее - просим окно перечитать данные
        if cls._window and cls._window.isVisible():
            cls._window.sync_from_blender()

    @classmethod
    @bpy.app.handlers.persistent
    def on_undo_redo(cls, scene):
        """
        Force update on Undo/Redo.
        """
        if cls._window and cls._window.isVisible():
            # Use a small timer to ensure Blender state is fully restored
            # and we are not in the middle of a context-restricted area.
            # We call full_refresh directly to bypass any interaction checks if necessary.
            QtCore.QTimer.singleShot(0, lambda: cls._window.full_refresh() if cls._window else None)

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
            
        if cls.on_undo_redo not in bpy.app.handlers.undo_post:
            bpy.app.handlers.undo_post.append(cls.on_undo_redo)
        if cls.on_undo_redo not in bpy.app.handlers.redo_post:
            bpy.app.handlers.redo_post.append(cls.on_undo_redo)

        cls._window.sync_from_blender()

    @classmethod
    def stop(cls):
        if bpy.app.timers.is_registered(cls.process_qt_events):
            bpy.app.timers.unregister(cls.process_qt_events)
        
        if cls.on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(cls.on_depsgraph_update)
            
        if cls.on_undo_redo in bpy.app.handlers.undo_post:
            bpy.app.handlers.undo_post.remove(cls.on_undo_redo)
        if cls.on_undo_redo in bpy.app.handlers.redo_post:
            bpy.app.handlers.redo_post.remove(cls.on_undo_redo)