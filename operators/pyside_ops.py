# rz_gui_constructor/operators/pyside_ops.py
import bpy
import os
import sys

# --- НАСТРОЙКА СРЕДЫ (ДУБЛИРУЕМ ДЛЯ НАДЕЖНОСТИ) ---
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_API"] = "pyside6"

# Попытка импорта PySide (проверка наличия)
try:
    from PySide6 import QtWidgets
    pyside_ok = True
except ImportError:
    pyside_ok = False
    QtWidgets = None

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ (ХРАНИЛИЩЕ ОКОН И МОДУЛЕЙ) ---
# Важно объявить их здесь, чтобы избежать NameError
qt_app = None

# Окна (чтобы сборщик мусора их не удалил)
viewer_window = None
inspector_window = None
qt_editor_window = None

# Ссылки на классы/функции (для ленивого импорта)
RZMViewerWindow_class = None
RZMInspectorWindow_class = None
launch_qt_editor_func = None  # <--- ВОТ ЭТОЙ ПЕРЕМЕННОЙ НЕ ХВАТАЛО

# --------------------------------------------------------

class RZM_OT_LaunchViewer(bpy.types.Operator):
    bl_idname = "rzm.launch_viewer"
    bl_label = "Open Viewer"
    
    @classmethod
    def poll(cls, context):
        return pyside_ok

    def execute(self, context):
        global qt_app, viewer_window, RZMViewerWindow_class

        # 1. Ленивый импорт модуля
        if RZMViewerWindow_class is None:
            try:
                from ..ui.viewer import RZMViewerWindow
                RZMViewerWindow_class = RZMViewerWindow
            except ImportError as e:
                self.report({'ERROR'}, f"Viewer Import Error: {e}")
                return {'CANCELLED'}

        # 2. Создаем или получаем приложение
        qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        # 3. Создаем окно
        # Если окно уже открыто - просто обновляем данные
        if viewer_window and viewer_window.isVisible():
            viewer_window.load_from_blender()
            viewer_window.activateWindow()
        else:
            # Иначе создаем новое
            viewer_window = RZMViewerWindow_class(context)
            viewer_window.show()

        return {'FINISHED'}

class RZM_OT_LaunchInspector(bpy.types.Operator):
    bl_idname = "rzm.launch_inspector"
    bl_label = "Open Inspector"
    
    @classmethod
    def poll(cls, context):
        return pyside_ok

    def execute(self, context):
        global qt_app, inspector_window, RZMInspectorWindow_class

        # 1. Ленивый импорт
        if RZMInspectorWindow_class is None:
            try:
                from ..ui.inspector import RZMInspectorWindow
                RZMInspectorWindow_class = RZMInspectorWindow
            except ImportError as e:
                self.report({'ERROR'}, f"Inspector Import Error: {e}")
                return {'CANCELLED'}

        # 2. App
        qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        # 3. Окно
        if inspector_window and inspector_window.isVisible():
            inspector_window.load_from_blender()
            inspector_window.activateWindow()
        else:
            inspector_window = RZMInspectorWindow_class(context)
            inspector_window.show()

        return {'FINISHED'}

class RZM_OT_LaunchQTEditor(bpy.types.Operator):
    """Launch the comprehensive QT Editor."""
    bl_idname = "rzm.launch_qt_editor"
    bl_label = "Launch QT Editor"
    bl_description = "Launch the comprehensive QT-based UI Editor"

    @classmethod
    def poll(cls, context):
        return pyside_ok

    def execute(self, context):
        # Объявляем, что мы используем глобальные переменные
        global qt_app, qt_editor_window, launch_qt_editor_func 
        
        # Еще раз страхуемся от DPI
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        
        # 1. Ленивый импорт функции запуска
        if launch_qt_editor_func is None:
            try:
                # Импортируем функцию launch_editor из файла qt_editor/__init__.py
                from ..qt_editor import launch_editor
                launch_qt_editor_func = launch_editor
            except ImportError as e:
                self.report({'ERROR'}, f"Editor Import Error: {e}")
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

        # 2. Запускаем через импортированную функцию
        # Функция сама внутри разбирается с QApplication
        try:
            new_window = launch_qt_editor_func(context)
            
            if new_window:
                qt_editor_window = new_window
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Editor returned None (check console)")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Crash launching Editor: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

classes_to_register = [
    RZM_OT_LaunchViewer,
    RZM_OT_LaunchInspector,
    RZM_OT_LaunchQTEditor,
]