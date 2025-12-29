# RZMenu/qt_editor/widgets/base.py
from PySide6 import QtWidgets, QtCore, QtGui

class RZDraggableNumber(QtWidgets.QWidget):
    """
    Гибрид Label и SpinBox.
    - Клик: Ввод текста.
    - Драг (зажать и тянуть): Изменение значения.
    """
    # Сигнал отправляет (имя_свойства, новое_значение, индекс_вектора)
    value_changed = QtCore.Signal(float)

    def __init__(self, value=0.0, is_int=True):
        super().__init__()
        self.is_int = is_int
        self.current_value = value
        self.drag_start_x = 0
        self.drag_start_value = 0
        self.is_dragging = False

        # UI Layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # Поле ввода (скрываем рамки, чтобы выглядело как лейбл)
        self.input = QtWidgets.QLineEdit(str(value))
        self.input.setStyleSheet("background: transparent; border: none; color: white;")
        self.input.editingFinished.connect(self.finish_edit)
        
        # Курсор "Resize" при наведении
        self.setCursor(QtCore.Qt.SizeHorCursor)
        
        layout.addWidget(self.input)
        
        # Стили
        self.setStyleSheet("background-color: #333; border-radius: 3px;")
        self.setFixedWidth(80) # Фиксированная ширина как в Блендере

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.is_dragging = True
            self.drag_start_x = event.globalPos().x()
            self.drag_start_value = self.current_value
            self.input.clearFocus() # Убираем фокус ввода текста

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            delta = event.globalPos().x() - self.drag_start_x
            # Чувствительность (Shift = медленнее)
            scale = 0.1 if (event.modifiers() & QtCore.Qt.ShiftModifier) else 1.0
            
            new_val = self.drag_start_value + (delta * scale)
            if self.is_int: new_val = int(new_val)
            
            self.update_internal(new_val)
            self.value_changed.emit(new_val)

    def mouseReleaseEvent(self, event):
        self.is_dragging = False

    def finish_edit(self):
        """Когда нажали Enter в поле ввода"""
        try:
            val = float(self.input.text())
            if self.is_int: val = int(val)
            self.update_internal(val)
            self.value_changed.emit(val)
        except ValueError:
            self.update_internal(self.current_value) # Вернуть как было

    def update_internal(self, val):
        self.current_value = val
        self.input.setText(str(val))

    def set_value_from_backend(self, val):
        """Вызывается извне для синхронизации"""
        if not self.input.hasFocus() and not self.is_dragging:
            self.update_internal(val)