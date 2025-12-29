# RZMenu/qt_editor/actions.py
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt
import bpy
from . import core

class RZContext:
    """Контейнер контекста, передаваемый в действия."""
    def __init__(self, window):
        self.window = window
        self.selected_ids = window.selected_ids  # Set[int]
        self.active_id = window.active_id        # int
        self.scene_name = core.get_scene_info().get("scene_name", "Unknown")

class RZActionDefinition:
    """Описание действия: Логика + UI данные"""
    def __init__(self, uid, name, func, shortcut=None):
        self.uid = uid
        self.name = name
        self.func = func
        self.shortcut = shortcut

# --- ФУНКЦИИ ДЕЙСТВИЙ (Pure Logic) ---

def action_refresh(ctx: RZContext):
    """Принудительное обновление UI"""
    ctx.window.brute_force_refresh()

def action_delete(ctx: RZContext):
    """Удаление выбранных элементов"""
    if not ctx.selected_ids:
        return
    
    # 1. Вызов Core
    core.delete_elements(ctx.selected_ids)
    
    # 2. Сброс выделения в UI
    ctx.window.clear_selection()
    
    # 3. Обновление
    ctx.window.brute_force_refresh()

def action_undo(ctx: RZContext):
    """Blender Native Undo"""
    try:
        bpy.ops.ed.undo()
    except Exception as e:
        print(f"Undo Failed: {e}")
    ctx.window.brute_force_refresh()

def action_redo(ctx: RZContext):
    """Blender Native Redo"""
    try:
        bpy.ops.ed.redo()
    except:
        pass
    ctx.window.brute_force_refresh()

def action_select_all(ctx: RZContext):
    """Выбрать все (пример)"""
    all_data = core.get_all_elements_list()
    all_ids = {item['id'] for item in all_data}
    ctx.window.set_selection_multi(all_ids, active_id=-1)


# --- РЕЕСТР ДЕЙСТВИЙ ---
# Здесь мы мапим UID -> Логика -> Хоткей
ACTIONS_REGISTRY = [
    RZActionDefinition("REFRESH", "Force Refresh", action_refresh, "F5"),
    RZActionDefinition("DELETE", "Delete Selected", action_delete, "Delete"),
    RZActionDefinition("UNDO", "Undo", action_undo, "Ctrl+Z"),
    RZActionDefinition("REDO", "Redo", action_redo, "Ctrl+Shift+Z"),
    RZActionDefinition("SELECT_ALL", "Select All", action_select_all, "Ctrl+A"),
]


class RZActionManager:
    def __init__(self, window):
        self.window = window
        self.q_actions = {} # uid -> QAction
        self.setup_actions()

    def setup_actions(self):
        """Создает QAction для каждого определения и вешает на окно"""
        for definition in ACTIONS_REGISTRY:
            # Создаем QAction
            q_act = QAction(definition.name, self.window)
            
            if definition.shortcut:
                q_act.setShortcut(QKeySequence(definition.shortcut))
                
            # Важный момент: замыкание для передачи контекста
            # Используем lambda с capture variable, чтобы не потерять func
            func_ref = definition.func
            q_act.triggered.connect(lambda checked=False, f=func_ref: self.execute_action(f))
            
            # Добавляем к окну (для работы шорткатов)
            self.window.addAction(q_act)
            self.q_actions[definition.uid] = q_act

    def execute_action(self, func):
        """Единая точка входа для выполнения команд"""
        # 1. Собираем контекст на момент нажатия
        ctx = RZContext(self.window)
        
        # 2. Выполняем функцию
        try:
            func(ctx)
        except Exception as e:
            print(f"RZ Action Error: {e}")
            import traceback
            traceback.print_exc()

    def get_action(self, uid):
        return self.q_actions.get(uid)