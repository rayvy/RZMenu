# RZMenu/qt_editor/widgets/inspector.py
from PySide6 import QtWidgets, QtCore
from .base import RZDraggableNumber

class RZMInspectorPanel(QtWidgets.QWidget):
    property_changed = QtCore.Signal(str, object, object)

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QFormLayout(self)
        
        # Хедер
        self.lbl_info = QtWidgets.QLabel("No Selection")
        self.lbl_info.setStyleSheet("font-weight: bold; color: #888;")
        layout.addRow(self.lbl_info)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.editingFinished.connect(lambda: self.emit_change('element_name', self.name_edit.text()))
        layout.addRow("Name:", self.name_edit)
        
        # Position
        self.pos_x = RZDraggableNumber(is_int=True)
        self.pos_y = RZDraggableNumber(is_int=True)
        self.pos_x.value_changed.connect(lambda v: self.emit_change('position', int(v), 0))
        self.pos_y.value_changed.connect(lambda v: self.emit_change('position', int(v), 1))
        
        row_pos = QtWidgets.QHBoxLayout()
        row_pos.addWidget(QtWidgets.QLabel("X:"))
        row_pos.addWidget(self.pos_x)
        row_pos.addWidget(QtWidgets.QLabel("Y:"))
        row_pos.addWidget(self.pos_y)
        layout.addRow("Position:", row_pos)

        # State storage
        self.has_data = False

    def emit_change(self, key, val, idx=None):
        if self.has_data:
            self.property_changed.emit(key, val, idx)

    def update_ui(self, props):
        if props and props['exists']:
            self.has_data = True
            self.setEnabled(True)
            
            # Заголовок
            count = len(props['selected_ids'])
            if props['is_multi']:
                self.lbl_info.setText(f"Multi-Edit ({count} items)")
                self.name_edit.setPlaceholderText("Mixed Names...")
            else:
                self.lbl_info.setText(f"Element ID: {props['id']}")
            
            # Данные (берем от активного)
            if not self.name_edit.hasFocus():
                 self.name_edit.setText(props['name'])
            
            self.pos_x.set_value_from_backend(props['pos_x'])
            self.pos_y.set_value_from_backend(props['pos_y'])
        else:
            self.has_data = False
            self.setEnabled(False)
            self.lbl_info.setText("No Selection")
            self.name_edit.clear()