# RZMenu/qt_editor/core/wm.py

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut
import traceback

class WindowManager(QObject): # Наследуемся от QObject для сигналов
    # Сигнал: (operator_id, operator_label)
    operator_executed = Signal(str, str)
    
    _operators = {} 
    _keymap = {}    
    _shortcuts = [] 

    def __init__(self, context):
        super().__init__()
        self.context = context

    @classmethod
    def register_operator(cls, op_cls):
        if not op_cls.bl_idname:
            print(f"Error: Operator {op_cls} missing bl_idname")
            return
        cls._operators[op_cls.bl_idname] = op_cls

    def run(self, idname):
        """Запуск оператора по ID."""
        if idname not in self._operators:
            print(f"WM Error: Operator '{idname}' not found.")
            return

        op_cls = self._operators[idname]
        
        # Check Poll
        if not op_cls.poll(self.context):
            # print(f"WM Info: Poll failed for '{idname}'") # Можно раскомментировать для дебага
            return

        # Execute
        try:
            op = op_cls()
            print(f"WM: Executing '{idname}'")
            res = op.execute(self.context)
            
            if 'FINISHED' in res:
                # Уведомляем систему, что оператор выполнен успешно
                self.operator_executed.emit(idname, op_cls.bl_label)
                
        except Exception as e:
            print(f"WM Crash executing '{idname}': {e}")
            traceback.print_exc()

    def load_keymap(self):
        """Загружает дефолтную карту клавиш."""
        self._keymap = {
            "Delete": "element.delete",
            "Ctrl+D": "element.duplicate",
            "Ctrl+C": "element.copy",
            "Ctrl+V": "element.paste",
            "R": "wm.refresh_data",      # <-- NEW: Refresh на R
            "H": "element.hide",         # <-- NEW: Hide на H
            "Alt+H": "element.unhide_all" # <-- NEW: Unhide All на Alt+H
        }
        self._apply_keymap()

    def get_keymap_data(self):
        """Возвращает список (Key, OperatorID) для UI настроек."""
        return self._keymap.items()

    def _apply_keymap(self):
        # ... (код создания шорткатов остается прежним)
        for sc in self._shortcuts:
            sc.setParent(None)
        self._shortcuts.clear()

        window = self.context.window
        for key_str, op_id in self._keymap.items():
            seq = QKeySequence(key_str)
            sc = QShortcut(seq, window)
            sc.activated.connect(lambda o=op_id: self.run(o))
            self._shortcuts.append(sc)