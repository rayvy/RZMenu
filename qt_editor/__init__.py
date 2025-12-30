# RZMenu/qt_editor/__init__.py
import bpy
import sys
import os
from . import core

try:
    from PySide6 import QtWidgets, QtCore
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    from . import window
else:
    window = None

# --- INTEGRATION MANAGER ---

class IntegrationManager:
    _app = None
    _window = None
    
    @classmethod
    def get_app(cls):
        # Гарантируем Singleton QApplication
        app = QtWidgets.QApplication.instance()
        if not app:
            os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
            app = QtWidgets.QApplication(sys.argv)
        return app

    @staticmethod
    def process_qt_events():
        """
        Магия плавности. Вызывается Blender'ом каждые ~10мс.
        Обрабатывает клики, наведения и отрисовку Qt.
        """
        app = QtWidgets.QApplication.instance()
        if app:
            app.processEvents()
        
        # Если окно закрыто - останавливаем таймер, чтобы не жрать ресурсы
        if IntegrationManager._window and not IntegrationManager._window.isVisible():
             IntegrationManager.stop()
             return None # Отмена таймера
             
        return 0.01 # Повторить через 10мс

    @classmethod
    def on_depsgraph_update(cls, scene, depsgraph):
        """
        Реакция на изменения в Blender.
        """
        if core.IS_UPDATING_FROM_QT:
            return

        if cls._window and cls._window.isVisible():
            # Вызываем обновление напрямую. 
            # Благодаря "ленивым" проверкам (signature check) в window.py,
            # это не будет тормозить, если данные не изменились.
            cls._window.sync_from_blender()

    @classmethod
    def launch(cls, context):
        if not PYSIDE_AVAILABLE:
            return {'CANCELLED'}

        cls._app = cls.get_app()
        
        # Создаем окно, если нет, или показываем существующее
        if cls._window is None:
            cls._window = window.RZMEditorWindow()
        
        cls._window.show()
        cls._window.activateWindow()
        
        # Разворачиваем, если свернуто
        win_state = cls._window.windowState()
        if win_state & QtCore.Qt.WindowMinimized:
             cls._window.setWindowState(win_state & ~QtCore.Qt.WindowMinimized)

        # 1. Запускаем "Сердцебиение" интерфейса
        if not bpy.app.timers.is_registered(cls.process_qt_events):
            bpy.app.timers.register(cls.process_qt_events, persistent=True)
            
        # 2. Подписываемся на обновления данных
        if cls.on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(cls.on_depsgraph_update)
            
        # Первичное обновление данных
        cls._window.sync_from_blender()

    @classmethod
    def stop(cls):
        # Очистка
        if bpy.app.timers.is_registered(cls.process_qt_events):
            bpy.app.timers.unregister(cls.process_qt_events)
        
        if cls.on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(cls.on_depsgraph_update)
        
        # Не уничтожаем окно полностью, чтобы сохранить его положение/размер,
        # но можно и cls._window = None, если нужно освободить память.

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
    for cls in classes: bpy.utils.register_class(cls)

def unregister():
    IntegrationManager.stop()
    for cls in classes: bpy.utils.unregister_class(cls)