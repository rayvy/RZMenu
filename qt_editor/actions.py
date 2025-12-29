# RZMenu/qt_editor/actions.py
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtCore import Qt, QObject
import bpy
from . import core

class RZContext:
    """Обертка для передачи состояния в операторы"""
    def __init__(self, window):
        self.window = window
        self.selected_ids = window.selected_ids
        self.active_id = window.active_id
        self.scene = getattr(window.panel_viewport, 'rz_scene', None) # Доступ к сцене для viewport операций

# --- BASE OPERATOR ---

class RZOperator:
    """Базовый класс для всех действий"""
    id = ""          # Уникальный ID (напр. "rzm.delete")
    label = ""       # Текст для UI
    icon = None      # Имя иконки (если нужно)
    shortcut = None  # Хоткей по умолчанию
    tooltip = ""

    def poll(self, context: RZContext) -> bool:
        """Проверка: можно ли сейчас выполнить действие?"""
        return True

    def execute(self, context: RZContext, **kwargs):
        """Основная логика"""
        raise NotImplementedError

# --- CONCRETE ACTIONS ---

class RZ_OT_Undo(RZOperator):
    id = "rzm.undo"
    label = "Undo"
    shortcut = "Ctrl+Z"
    
    def execute(self, context, **kwargs):
        # ИСПОЛЬЗУЕМ ОБЕРТКУ С КОНТЕКСТОМ
        print("RZM: Executing Undo via Wrapper")
        core.exec_in_context(bpy.ops.ed.undo)
        # UI обновится через Handler или таймер, но для надежности:
        context.window.brute_force_refresh()

class RZ_OT_Redo(RZOperator):
    id = "rzm.redo"
    label = "Redo"
    shortcut = "Ctrl+Shift+Z"
    
    def execute(self, context, **kwargs):
        print("RZM: Executing Redo via Wrapper")
        try:
            core.exec_in_context(bpy.ops.ed.redo)
        except:
            pass
        context.window.brute_force_refresh()

class RZ_OT_Delete(RZOperator):
    id = "rzm.delete"
    label = "Delete Selected"
    shortcut = "Delete"
    tooltip = "Remove selected elements from the scene"

    def poll(self, context):
        return bool(context.selected_ids)

    def execute(self, context, **kwargs):
        core.delete_elements(context.selected_ids)
        context.window.clear_selection()
        context.window.brute_force_refresh()

class RZ_OT_Refresh(RZOperator):
    id = "rzm.refresh"
    label = "Force Refresh"
    shortcut = "F5"
    
    def execute(self, context, **kwargs):
        context.window.brute_force_refresh()

class RZ_OT_SelectAll(RZOperator):
    id = "rzm.select_all"
    label = "Select All"
    shortcut = "Ctrl+A"
    
    def execute(self, context, **kwargs):
        all_data = core.get_all_elements_list()
        all_ids = {item['id'] for item in all_data}
        context.window.set_selection_multi(all_ids, active_id=-1)

class RZ_OT_Nudge(RZOperator):
    """Пример параметрического оператора для стрелок клавиатуры"""
    id = "rzm.nudge"
    label = "Nudge Element"
    # Хоткеи задаются динамически при регистрации, т.к. их несколько
    
    def poll(self, context):
        return bool(context.selected_ids)

    def execute(self, context, **kwargs):
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        core.move_elements_delta(context.selected_ids, x, y)
        core.commit_history("Nudge") # Важно сохранить историю
        context.window.refresh_viewport(force=True)
        context.window.refresh_inspector(force=True)

# --- REGISTRY & MANAGER ---

# Список классов операторов
CLASSES = [
    RZ_OT_Delete,
    RZ_OT_Refresh,
    RZ_OT_Undo,
    RZ_OT_Redo,
    RZ_OT_SelectAll,
    RZ_OT_Nudge
]

class RZActionManager(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.operators = {} 
        self.q_actions = {}
        
        self._register_operators()
        self._init_qactions()

    def _register_operators(self):
        for cls in CLASSES:
            self.operators[cls.id] = cls()

    def _init_qactions(self):
        for op_id, op in self.operators.items():
            if not op.shortcut: continue
            
            # Для стандартных (Undo/Delete/Refresh)
            q_act = QAction(op.label, self.window)
            q_act.setShortcut(QKeySequence(op.shortcut))
            q_act.triggered.connect(lambda checked=False, oid=op_id: self.run(oid))
            
            self.window.addAction(q_act)
            self.q_actions[op_id] = q_act
            
        self._register_nudge_shortcuts()

    def _register_nudge_shortcuts(self):
        arrows = [
            (Qt.Key_Left,  -10, 0), (Qt.Key_Right, 10, 0),
            (Qt.Key_Up,    0, -10), (Qt.Key_Down,  0, 10),
        ]
        for key, dx, dy in arrows:
            q_act = QAction(self.window)
            q_act.setShortcut(QKeySequence(key))
            q_act.triggered.connect(lambda _, x=dx, y=dy: self.run("rzm.nudge", x=x, y=y))
            self.window.addAction(q_act)

    def run(self, op_id, **kwargs):
        op = self.operators.get(op_id)
        if not op: return
        ctx = RZContext(self.window)
        if not op.poll(ctx): return
        
        try:
            op.execute(ctx, **kwargs)
            self.update_ui_state()
        except Exception as e:
            print(f"Op Error {op_id}: {e}")
            import traceback
            traceback.print_exc()

    def update_ui_state(self):
        ctx = RZContext(self.window)
        for op_id, q_act in self.q_actions.items():
            op = self.operators.get(op_id)
            if op: q_act.setEnabled(op.poll(ctx))
    
    def connect_button(self, btn, op_id, **kwargs):
        op = self.operators.get(op_id)
        if not op: return
        btn.clicked.connect(lambda: self.run(op_id, **kwargs))
        if op.shortcut:
            btn.setToolTip(f"{op.label} ({op.shortcut})")