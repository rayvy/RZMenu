# RZMenu/qt_editor/widgets/keymap_editor.py
from PySide6 import QtWidgets, QtCore, QtGui
from ..conf import get_config, save_config
from ..systems import operators
from .lib.theme import get_current_theme
from .lib.widgets import RZPanelWidget

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
        
        # Хардкод стилей для диалога захвата, чтобы он выделялся
        self.lbl.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.lbl)
        
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.btn_cancel)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
            return

        sequence_str = []
        if modifiers & QtCore.Qt.ControlModifier: sequence_str.append("Ctrl")
        if modifiers & QtCore.Qt.ShiftModifier:   sequence_str.append("Shift")
        if modifiers & QtCore.Qt.AltModifier:     sequence_str.append("Alt")
        
        key_name = QtGui.QKeySequence(key).toString()
        sequence_str.append(key_name)
        
        result = "+".join(sequence_str)
        self.captured_sequence = result
        self.accept()

class RZKeymapPanel(QtWidgets.QWidget):
    """
    Основной виджет редактора кеймапов.
    Теперь наследуется от QWidget, чтобы его можно было вставлять в Preferences.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # --- Tree Widget ---
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Command / Context", "Key Binding", "Operator ID"])
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 150)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.tree)
        
        # --- Help Text ---
        self.info_lbl = QtWidgets.QLabel("Double-click on an item to rebind.")
        theme = get_current_theme()
        self.info_lbl.setStyleSheet(f"color: {theme.get('text_disabled', '#888')}; margin-top: 5px;")
        layout.addWidget(self.info_lbl)
        
        # --- Buttons (Save logic moved mostly to parent, but kept here for standalone usage) ---
        self.btn_box = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Save Changes")
        self.btn_save.clicked.connect(self.save_config)
        
        self.btn_box.addStretch()
        self.btn_box.addWidget(self.btn_save)
        layout.addLayout(self.btn_box)
        
        self.populate_tree()

    def populate_tree(self):
        self.tree.clear()
        keymaps = self.config.get("keymaps", {})
        
        theme = get_current_theme()
        bg_header = QtGui.QColor(theme.get('bg_header', '#3A404A'))

        for context_name, mapping in keymaps.items():
            context_item = QtWidgets.QTreeWidgetItem(self.tree)
            context_item.setText(0, context_name)
            context_item.setExpanded(True)
            context_item.setBackground(0, bg_header)
            context_item.setBackground(1, bg_header)
            context_item.setBackground(2, bg_header)
            
            for key_seq, op_data in mapping.items():
                op_id = ""
                label = ""
                
                if isinstance(op_data, str):
                    op_id = op_data
                elif isinstance(op_data, dict):
                    op_id = op_data.get("op", "unknown")
                
                op_cls = operators.get_operator_class(op_id)
                if op_cls:
                    label = op_cls.label
                    if isinstance(op_data, dict) and "args" in op_data:
                        label += f" {op_data['args']}"
                else:
                    label = op_id 
                
                item = QtWidgets.QTreeWidgetItem(context_item)
                item.setText(0, label)
                item.setText(1, key_seq)
                item.setText(2, op_id)
                item.setData(0, QtCore.Qt.UserRole, context_name)
                item.setData(1, QtCore.Qt.UserRole, key_seq)

    def on_item_double_clicked(self, item, column):
        context = item.data(0, QtCore.Qt.UserRole)
        old_key = item.data(1, QtCore.Qt.UserRole)
        
        if not context or not old_key: 
            return 
            
        dialog = KeyCaptureDialog(self)
        if dialog.exec():
            new_key = dialog.captured_sequence
            if new_key and new_key != old_key:
                self.update_binding(context, old_key, new_key, item)

    def update_binding(self, context, old_key, new_key, item):
        keymaps = self.config["keymaps"]
        if context not in keymaps: return
        
        op_data = keymaps[context].pop(old_key)
        keymaps[context][new_key] = op_data
        
        item.setText(1, new_key)
        item.setData(1, QtCore.Qt.UserRole, new_key)
        
        theme = get_current_theme()
        item.setForeground(1, QtGui.QColor(theme.get('warning', '#ffaa00')))

    def save_config(self):
        save_config()
        # Visual feedback could be added here
        self.btn_save.setText("Saved!")
        QtCore.QTimer.singleShot(1000, lambda: self.btn_save.setText("Save Changes"))


class RZKeymapEditor(QtWidgets.QDialog):
    """
    Обертка (Dialog) для RZKeymapPanel для обратной совместимости 
    или использования как отдельное окно.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keymap Editor")
        self.resize(600, 500)
        
        layout = QtWidgets.QVBoxLayout(self)
        self.panel = RZKeymapPanel(self)
        
        # Скрываем кнопку Save панели, так как в диалоге мы обычно хотим "Save & Close" или "Cancel"
        # Но для простоты оставим логику панели, просто добавим кнопку Close
        self.panel.btn_box.setParent(None) # Remove inner buttons layout to replace logic if needed
        # Re-add panel content
        layout.addWidget(self.panel)
        
        btn_box = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Save & Close")
        btn_save.clicked.connect(self.save_and_close)
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def save_and_close(self):
        self.panel.save_config()
        self.accept()