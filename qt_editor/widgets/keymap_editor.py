# RZMenu/qt_editor/widgets/keymap_editor.py
from PySide6 import QtWidgets, QtCore, QtGui
from ..conf import get_config, save_config
from ..systems import operators
from .lib.theme import get_current_theme

class KeyCaptureDialog(QtWidgets.QDialog):
    """Диалог "Нажмите любую клавишу..." """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Press a Key")
        self.resize(300, 150)
        self.captured_sequence = None
        
        layout = QtWidgets.QVBoxLayout(self)
        self.lbl = QtWidgets.QLabel("Press the key combination...")
        self.lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.lbl)
        
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.btn_cancel)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        # Игнорим одиночные модификаторы
        if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
            return

        # Формируем строку (Ctrl+Shift+A)
        sequence_str = []
        if modifiers & QtCore.Qt.ControlModifier: sequence_str.append("Ctrl")
        if modifiers & QtCore.Qt.ShiftModifier:   sequence_str.append("Shift")
        if modifiers & QtCore.Qt.AltModifier:     sequence_str.append("Alt")
        
        key_name = QtGui.QKeySequence(key).toString()
        sequence_str.append(key_name)
        
        result = "+".join(sequence_str)
        self.captured_sequence = result
        self.accept()

class RZKeymapEditor(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keymap Editor")
        self.resize(600, 500)
        self.config = get_config()
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # --- Tree Widget ---
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Command / Context", "Key Binding", "Operator ID"])
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 150)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.tree)
        
        # --- Help Text ---
        info = QtWidgets.QLabel("Double-click on an item to rebind.")
        theme = get_current_theme()
        info.setStyleSheet(f"color: {theme.get('text_disabled', '#888')};")
        layout.addWidget(info)
        
        # --- Buttons ---
        btn_box = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Save & Close")
        btn_save.clicked.connect(self.save_and_close)
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)
        
        self.populate_tree()

    def populate_tree(self):
        self.tree.clear()
        keymaps = self.config.get("keymaps", {})
        
        # Проходим по контекстам (GLOBAL, VIEWPORT...)
        theme = get_current_theme()
        bg_header = QtGui.QColor(theme.get('bg_header', '#3A404A'))

        for context_name, mapping in keymaps.items():
            context_item = QtWidgets.QTreeWidgetItem(self.tree)
            context_item.setText(0, context_name)
            context_item.setExpanded(True)
            # Визуально выделим контекст
            context_item.setBackground(0, bg_header)
            context_item.setBackground(1, bg_header)
            context_item.setBackground(2, bg_header)
            
            # Проходим по биндингам
            # mapping: { "Ctrl+Z": "rzm.undo", "Left": {"op":...} }
            for key_seq, op_data in mapping.items():
                op_id = ""
                label = ""
                
                if isinstance(op_data, str):
                    op_id = op_data
                elif isinstance(op_data, dict):
                    op_id = op_data.get("op", "unknown")
                
                # Ищем красивое имя оператора
                op_cls = operators.get_operator_class(op_id)
                if op_cls:
                    label = op_cls.label
                    # Если есть аргументы, добавим в лейбл
                    if isinstance(op_data, dict) and "args" in op_data:
                        label += f" {op_data['args']}"
                else:
                    label = op_id # Fallback
                
                item = QtWidgets.QTreeWidgetItem(context_item)
                item.setText(0, label)
                item.setText(1, key_seq)
                item.setText(2, op_id)
                # Сохраним реальные данные в UserRole для логики
                item.setData(0, QtCore.Qt.UserRole, context_name)
                item.setData(1, QtCore.Qt.UserRole, key_seq) # Старый ключ

    def on_item_double_clicked(self, item, column):
        context = item.data(0, QtCore.Qt.UserRole)
        old_key = item.data(1, QtCore.Qt.UserRole)
        
        if not context or not old_key: 
            return # Кликнули по заголовку
            
        # Запускаем "слушателя"
        dialog = KeyCaptureDialog(self)
        if dialog.exec():
            new_key = dialog.captured_sequence
            if new_key and new_key != old_key:
                self.update_binding(context, old_key, new_key, item)

    def update_binding(self, context, old_key, new_key, item):
        keymaps = self.config["keymaps"]
        if context not in keymaps: return
        
        # Получаем данные оператора по старому ключу
        op_data = keymaps[context].pop(old_key)
        
        # Записываем по новому ключу (удаляя старый бинд, если он был на этой кнопке)
        keymaps[context][new_key] = op_data
        
        # Обновляем UI
        item.setText(1, new_key)
        item.setData(1, QtCore.Qt.UserRole, new_key)
        # Подсветка изменения
        theme = get_current_theme()
        item.setForeground(1, QtGui.QColor(theme.get('warning', '#ffaa00')))

    def save_and_close(self):
        # Сохраняем в JSON
        save_config()
        self.accept()