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
    
    # ... (Keep existing _check_hover_context, eventFilter, _handle_keypress, _get_key_sequence, _get_hover_context, _lookup_keymap methods) ...

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
        if isinstance(focused_widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            return False

        key_sequence = self._get_key_sequence(event)
        if not key_sequence: 
            return False

        context_name = self._get_hover_context()
        op_data = self._lookup_keymap(context_name, key_sequence)
        
        if op_data:
            return self._execute_operator(op_data)
            
        return False

    def _get_key_sequence(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
            return None

        sequence_str = []
        if modifiers & QtCore.Qt.ControlModifier: sequence_str.append("Ctrl")
        if modifiers & QtCore.Qt.ShiftModifier:   sequence_str.append("Shift")
        if modifiers & QtCore.Qt.AltModifier:     sequence_str.append("Alt")
        
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
        keymaps = self.config.get("keymaps", {})
        if context in keymaps and key_seq in keymaps[context]:
            return keymaps[context][key_seq]
        if "GLOBAL" in keymaps and key_seq in keymaps["GLOBAL"]:
            return keymaps["GLOBAL"][key_seq]
            
        defaults = {
            "H": "rzm.toggle_hide",
            "L": {"op": "rzm.toggle_lock", "args": {"type": "POS"}},
            "Shift+L": {"op": "rzm.toggle_lock", "args": {"type": "SIZE"}},
            "Alt+L": "rzm.toggle_selectable"
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
            logger.warn(f"Keymap points to unknown operator: {op_id}")
            return False
            
        # Create Snapshot from Manager
        ctx = RZContextManager.get_instance().get_snapshot()
        op_inst = op_class()
        
        if op_inst.poll(ctx):
            try:
                self.operator_executed.emit(op_inst.label or op_id)
                # Inject window
                op_kwargs['window'] = self.window
                op_inst.execute(ctx, **op_kwargs)
                return True 
            except Exception as e:
                logger.error(f"Execution failed for {op_id}: {e}")
                
        return False