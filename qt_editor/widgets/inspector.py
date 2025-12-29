# RZMenu/qt_editor/widgets/inspector.py
from PySide6 import QtWidgets, QtCore
from .base import RZDraggableNumber

class RZMInspectorPanel(QtWidgets.QWidget):
    property_changed = QtCore.Signal(str, object, object)

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QFormLayout(self)
        
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.editingFinished.connect(lambda: self.emit_change('element_name', self.name_edit.text()))
        
        # Кастомные контролы
        self.pos_x = RZDraggableNumber(is_int=True)
        self.pos_y = RZDraggableNumber(is_int=True)
        self.size_w = RZDraggableNumber(is_int=True)
        self.size_h = RZDraggableNumber(is_int=True)
        
        # Подключаем сигналы кастомных виджетов
        self.pos_x.value_changed.connect(lambda v: self.emit_change('position', int(v), 0))
        self.pos_y.value_changed.connect(lambda v: self.emit_change('position', int(v), 1))
        self.size_w.value_changed.connect(lambda v: self.emit_change('size', int(v), 0))
        self.size_h.value_changed.connect(lambda v: self.emit_change('size', int(v), 1))
        
        layout.addRow("Name:", self.name_edit)
        
        # Группировка в ряд для X/Y
        row_pos = QtWidgets.QHBoxLayout()
        row_pos.addWidget(QtWidgets.QLabel("X:"))
        row_pos.addWidget(self.pos_x)
        row_pos.addWidget(QtWidgets.QLabel("Y:"))
        row_pos.addWidget(self.pos_y)
        layout.addRow("Position:", row_pos)
        
        row_size = QtWidgets.QHBoxLayout()
        row_size.addWidget(QtWidgets.QLabel("W:"))
        row_size.addWidget(self.size_w)
        row_size.addWidget(QtWidgets.QLabel("H:"))
        row_size.addWidget(self.size_h)
        layout.addRow("Size:", row_size)
        
        self.active_id = -1

    def emit_change(self, key, val, idx=None):
        if self.active_id != -1:
            self.property_changed.emit(key, val, idx)

    def update_ui(self, props):
        if props and props['exists']:
            self.active_id = props['id']
            self.setEnabled(True)
            if not self.name_edit.hasFocus(): self.name_edit.setText(props['name'])
            
            # Обновляем кастомные контролы
            self.pos_x.set_value_from_backend(props['pos_x'])
            self.pos_y.set_value_from_backend(props['pos_y'])
            self.size_w.set_value_from_backend(props['width'])
            self.size_h.set_value_from_backend(props['height'])
        else:
            self.active_id = -1
            self.setEnabled(False)
            self.name_edit.clear()