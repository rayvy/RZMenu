# RZMenu/qt_editor/systems/input_manager.py
import bpy
from PySide6 import QtCore, QtGui, QtWidgets
from . import operators
from ..conf import get_config
from ..utils import logger

class RZInputController(QtCore.QObject):
    """
    Перехватывает события клавиатуры на уровне окна.
    Определяет контекст (над какой панелью мышь).
    Ищет соответствие в Keymap и запускает оператор.
    """
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.config = get_config()
        
        # Устанавливаем себя как фильтр событий для всего окна
        self.window.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Главный цикл обработки событий"""
        if event.type() == QtCore.QEvent.KeyPress:
            if self._handle_keypress(event):
                return True # Событие обработано нами, не передавать дальше
                
        return super().eventFilter(obj, event)

    def _handle_keypress(self, event):
        # 1. Пропускаем, если фокус в поле ввода текста (Inspector)
        focused_widget = QtWidgets.QApplication.focusWidget()
        if isinstance(focused_widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            # Но! Если нажали Enter или Esc, возможно мы хотим завершить ввод
            # Пока оставим Qt обрабатывать текст
            return False

        # 2. Определяем нажатую комбинацию (строка "Ctrl+Z")
        key_sequence = self._get_key_sequence(event)
        if not key_sequence: 
            return False

        # 3. Определяем контекст под мышью
        context_name = self._get_hover_context()
        # logger.debug(f"Input: {key_sequence} | Context: {context_name}")

        # 4. Ищем оператор в конфиге (Сначала Локальный, потом Глобальный)
        op_data = self._lookup_keymap(context_name, key_sequence)
        
        if op_data:
            return self._execute_operator(op_data)
            
        return False

    def _get_key_sequence(self, event):
        """Превращает Qt Key Event в строку 'Ctrl+Shift+Z'"""
        key = event.key()
        modifiers = event.modifiers()
        
        # Игнорируем нажатие самих модификаторов (просто Ctrl без буквы)
        if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
            return None

        # Собираем строку
        sequence_str = []
        if modifiers & QtCore.Qt.ControlModifier: sequence_str.append("Ctrl")
        if modifiers & QtCore.Qt.ShiftModifier:   sequence_str.append("Shift")
        if modifiers & QtCore.Qt.AltModifier:     sequence_str.append("Alt")
        
        # Добавляем саму клавишу
        # Используем QKeySequence для получения понятного имени (Key_Left -> "Left")
        key_name = QtGui.QKeySequence(key).toString()
        sequence_str.append(key_name)
        
        return "+".join(sequence_str)

    def _get_hover_context(self):
        """Определяет, над какой панелью находится курсор мыши"""
        # Глобальная позиция мыши
        pos = QtGui.QCursor.pos()
        # Виджет под мышью внутри нашего окна
        widget = QtWidgets.QApplication.widgetAt(pos)
        
        if not widget:
            return "GLOBAL"

        # Поднимаемся вверх по иерархии виджетов, пока не найдем свойство RZ_CONTEXT
        curr = widget
        while curr:
            ctx = curr.property("RZ_CONTEXT")
            if ctx:
                return ctx
            curr = curr.parentWidget()
            
            # Защита: не выйти за пределы нашего окна
            if curr == self.window:
                break
                
        return "GLOBAL"

    def _lookup_keymap(self, context, key_seq):
        """
        Ищет 'Ctrl+Z' сначала в keymaps[context], затем в keymaps['GLOBAL']
        Возвращает ID оператора или словарь данных.
        """
        keymaps = self.config.get("keymaps", {})
        
        # 1. Локальный поиск
        if context in keymaps:
            if key_seq in keymaps[context]:
                return keymaps[context][key_seq]
        
        # 2. Глобальный поиск (Fallback)
        if "GLOBAL" in keymaps:
            if key_seq in keymaps["GLOBAL"]:
                return keymaps["GLOBAL"][key_seq]
                
        return None

    def _execute_operator(self, op_data):
        """Запуск оператора по ID"""
        op_id = None
        op_kwargs = {}
        
        # op_data может быть строкой "rzm.undo" или словарем {"op":..., "args":...}
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
            
        # Создаем контекст и запускаем
        ctx = operators.RZContext(self.window)
        op_inst = op_class()
        
        if op_inst.poll(ctx):
            try:
                op_inst.execute(ctx, **op_kwargs)
                return True # Успех, событие поглощено
            except Exception as e:
                logger.error(f"Execution failed for {op_id}: {e}")
                
        return False # Poll failed, событие не поглощено (может сработать что-то другое)