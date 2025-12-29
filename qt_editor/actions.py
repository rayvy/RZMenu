# RZMenu/qt_editor/actions.py
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt
import bpy
from . import core

class RZActionManager:
    def __init__(self, window):
        self.window = window
        self.actions = {}
        
        # Инициализация всех действий
        self.setup_actions()

    def setup_actions(self):
        # --- 1. REFRESH (Обновление) ---
        # Логика: Вызвать brute_force_refresh у окна
        act_refresh = QAction("Force Refresh", self.window)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self.window.brute_force_refresh)
        # Добавляем в глобальный список окна (чтобы хоткей работал везде)
        self.window.addAction(act_refresh)
        self.actions['refresh'] = act_refresh

        # --- 2. DELETE (Удаление) ---
        # Логика: Удалить выбранный ID через core, потом обновить UI
        act_delete = QAction("Delete Element", self.window)
        act_delete.setShortcut(QKeySequence("Delete"))
        act_delete.triggered.connect(self.on_delete_triggered)
        self.window.addAction(act_delete)
        self.actions['delete'] = act_delete

        # --- 3. UNDO / REDO (Blender Native) ---
        # Логика: Вызвать оператор Блендера
        act_undo = QAction("Undo", self.window)
        act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        act_undo.triggered.connect(lambda: self.run_blender_operator(bpy.ops.ed.undo))
        self.window.addAction(act_undo)
        self.actions['undo'] = act_undo

        act_redo = QAction("Redo", self.window)
        # Shift+Ctrl+Z
        act_redo.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        act_redo.triggered.connect(lambda: self.run_blender_operator(bpy.ops.ed.redo))
        self.window.addAction(act_redo)
        self.actions['redo'] = act_redo

    # --- ЛОГИКА ДЕЙСТВИЙ ---

    def on_delete_triggered(self):
        # Получаем ID из окна
        target_id = self.window.selected_id
        if target_id == -1:
            return

        # Удаляем через Core (Бэкенд)
        # (Предполагаем, что ты добавишь delete_element в core.py)
        if hasattr(core, 'delete_element'):
            core.delete_element(target_id)
        else:
            print("RZM Error: core.delete_element not implemented yet")

        # Форсируем обновление UI
        self.window.brute_force_refresh()

    def run_blender_operator(self, operator_func):
        """Безопасный запуск оператора Блендера (для Undo/Redo)"""
        # Трюк с переопределением контекста, чтобы Блендер не ругался,
        # что мы жмем кнопки не в 3D View
        try:
            # Ищем любое окно
            for win in bpy.context.window_manager.windows:
                screen = win.screen
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        with bpy.context.temp_override(window=win, area=area):
                            operator_func()
                        return
                        
            # Если не нашли 3D view, пробуем просто так (может сработать глобально)
            operator_func()
            
        except Exception as e:
            print(f"RZM Action Error: {e}")
            
        # После Undo/Redo нужно обновить наш UI!
        self.window.brute_force_refresh()