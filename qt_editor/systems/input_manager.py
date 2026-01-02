# RZMenu/qt_editor/systems/input_manager.py
import bpy
from PySide6 import QtCore, QtGui, QtWidgets
from . import operators
from ..conf import get_config
from ..utils import logger
from ..context import RZContextManager

class RZInputController(QtCore.QObject):
    context_changed = QtCore.Signal(str)       
    operator_executed = QtCore.Signal(str)     
    
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.config = get_config()
        self._last_context = ""
        
        self._ctx_timer = QtCore.QTimer()
        self._ctx_timer.timeout.connect(self._check_hover_context)
        self._ctx_timer.start(100)
        
        self.window.installEventFilter(self)
    
    def _check_hover_context(self):
        if not self.window.isActiveWindow(): return

        ctx = self._get_hover_context()
        if ctx != self._last_context:
            self._last_context = ctx
            self.context_changed.emit(ctx)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if self._handle_keypress(event):
                return True
        return super().eventFilter(obj, event)

    def _handle_keypress(self, event):
        focused_widget = QtWidgets.QApplication.focusWidget()
        # Если печатаем текст в поле ввода — горячие клавиши не должны работать
        if isinstance(focused_widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            return False

        key_sequence = self._get_key_sequence(event)
        if not key_sequence: 
            return False

        # --- DEBUG PRINT: Раскомментируй строку ниже, если клавиши не работают ---
        # print(f"RZM Input: Detected '{key_sequence}' in context '{self._get_hover_context()}'")
        # -------------------------------------------------------------------------

        context_name = self._get_hover_context()
        op_data = self._lookup_keymap(context_name, key_sequence)
        
        if op_data:
            return self._execute_operator(op_data)
            
        return False

    def _get_key_sequence(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        # Игнорируем нажатия только модификаторов (просто Ctrl, просто Shift)
        if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
            return None

        sequence_str = []
        if modifiers & QtCore.Qt.ControlModifier: sequence_str.append("Ctrl")
        if modifiers & QtCore.Qt.ShiftModifier:   sequence_str.append("Shift")
        if modifiers & QtCore.Qt.AltModifier:     sequence_str.append("Alt")
        
        # Получаем имя клавиши
        # ВАЖНО: Qt иногда возвращает имена по-разному (Del vs Delete), обрабатываем это в lookup
        key_name = QtGui.QKeySequence(key).toString()
        sequence_str.append(key_name)
        
        return "+".join(sequence_str)

    def _get_hover_context(self):
        pos = QtGui.QCursor.pos()
        widget = QtWidgets.QApplication.widgetAt(pos)
        
        if not widget:
            return "GLOBAL"

        curr = widget
        while curr:
            ctx = curr.property("RZ_CONTEXT")
            if ctx:
                return ctx
            curr = curr.parentWidget()
            if curr == self.window:
                break
                
        return "GLOBAL"

    def _lookup_keymap(self, context, key_seq):
        # 1. Проверяем пользовательский конфиг (conf/defaults.py или saved config)
        keymaps = self.config.get("keymaps", {})
        if context in keymaps and key_seq in keymaps[context]:
            return keymaps[context][key_seq]
        if "GLOBAL" in keymaps and key_seq in keymaps["GLOBAL"]:
            return keymaps["GLOBAL"][key_seq]
            
        # 2. Хардкодные дефолты (ЕСЛИ НЕ НАЙДЕНО В КОНФИГЕ)
        defaults = {
            # --- Visibility / Locking ---
            "H": "rzm.toggle_hide",
            "Alt+H": "rzm.unhide_all",           # <--- Исправление 1: Alt+H
            "L": {"op": "rzm.toggle_lock", "args": {"type": "POS"}},
            "Shift+L": {"op": "rzm.toggle_lock", "args": {"type": "SIZE"}},
            "Alt+L": "rzm.toggle_selectable",
            
            # --- Clipboard / Duplication ---
            "Ctrl+C": "rzm.copy",                # <--- Исправление 2: Copy
            "Ctrl+V": "rzm.paste",               # <--- Исправление 3: Paste
            "Ctrl+D": "rzm.duplicate",           # <--- Исправление 4: Duplicate
            "Shift+D": "rzm.duplicate",          # Blender-style duplicate
            
            # --- Deletion ---
            "Del": "rzm.delete",                 # <--- Исправление 5: Delete (Обычно Qt пишет "Del")
            "Delete": "rzm.delete",              # На всякий случай
            "Backspace": "rzm.delete",           # Для маков или удобства
            
            # --- Navigation / Undo ---
            "Ctrl+Z": "rzm.undo",
            "Ctrl+Shift+Z": "rzm.redo",
            "Home": "rzm.view_reset"
        }
        
        if key_seq in defaults:
            return defaults[key_seq]

        return None

    def _execute_operator(self, op_data):
        op_id = None
        op_kwargs = {}
        
        if isinstance(op_data, str):
            op_id = op_data
        elif isinstance(op_data, dict):
            op_id = op_data.get("op")
            op_kwargs = op_data.get("args", {})
            
        if not op_id: return False
        
        op_class = operators.get_operator_class(op_id)
        if not op_class:
            # logger.warn(f"Keymap points to unknown operator: {op_id}")
            return False
            
        # Create Snapshot from Manager
        ctx = RZContextManager.get_instance().get_snapshot()
        # "Грязный" хак для UI операторов (Zoom, etc), им нужно окно Qt
        # В идеале это должно передаваться чище, но пока так работает
        if hasattr(ctx, 'window'): # Если snapshot не поддерживает атрибут, не падаем
             pass 
             
        op_inst = op_class()
        
        # Проверяем poll (можно ли выполнить оператор сейчас)
        if op_inst.poll(ctx):
            try:
                self.operator_executed.emit(op_inst.label or op_id)
                
                # Копируем аргументы, чтобы не менять исходный словарь
                runtime_kwargs = op_kwargs.copy()
                runtime_kwargs['window'] = self.window
                
                op_inst.execute(ctx, **runtime_kwargs)
                return True 
            except Exception as e:
                logger.error(f"Execution failed for {op_id}: {e}")
                import traceback
                traceback.print_exc()
                
        return False