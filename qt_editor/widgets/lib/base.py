# RZMenu/qt_editor/widgets/base.py
from PySide6 import QtWidgets, QtCore, QtGui
from .theme import get_current_theme

class RZSmartSlider(QtWidgets.QWidget):
    """
    Умный слайдер: Лейбл (драг) + Спинбокс + Кнопки +/-.
    Заменяет старый RZDraggableNumber, сохраняя совместимость.
    """
    # Сигнал: (новое_значение). Тип float, но если is_int=True, отправляет целое как float
    value_changed = QtCore.Signal(float)

    def __init__(self, value=0.0, is_int=True, parent=None, label_text="Value"):
        super().__init__(parent)
        self.is_int = is_int
        self._value = int(value) if is_int else float(value)
        self._step = 1 if is_int else 0.1
        
        # Layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 1. Draggable Label (Overlay logic handled via event filter or custom widget)
        # Для простоты делаем кастомный QLabel внутри
        self.label = _RZDragLabel(label_text)
        self.label.drag_delta.connect(self._on_label_drag)
        layout.addWidget(self.label)

        # 2. Button [-]
        self.btn_minus = QtWidgets.QPushButton("-")
        self.btn_minus.setFixedSize(16, 20)
        self.btn_minus.clicked.connect(self._decrement)
        layout.addWidget(self.btn_minus)

        # 3. SpinBox
        if self.is_int:
            self.spin = QtWidgets.QSpinBox()
            self.spin.setRange(-999999, 999999)
        else:
            self.spin = QtWidgets.QDoubleSpinBox()
            self.spin.setRange(-999999.0, 999999.0)
            self.spin.setDecimals(2)

        self.spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons) # Скрываем встроенные стрелки, у нас свои
        self.spin.setValue(self._value)
        self.spin.valueChanged.connect(self._on_spin_changed)
        
        # Expanding spinbox
        self.spin.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(self.spin)

        # 4. Button [+]
        self.btn_plus = QtWidgets.QPushButton("+")
        self.btn_plus.setFixedSize(16, 20)
        self.btn_plus.clicked.connect(self._increment)
        layout.addWidget(self.btn_plus)

        # Apply theme after all widgets are created
        self.apply_theme()

    def apply_theme(self):
        """Apply theme colors to all child widgets."""
        t = get_current_theme()

        # Style buttons
        button_style = f"""
            padding: 0px;
            border: none;
            background: {t['bg_header']};
            color: {t['text_main']};
        """
        self.btn_minus.setStyleSheet(button_style)
        self.btn_plus.setStyleSheet(button_style)

        # Style spinbox
        spin_style = f"""
            background: {t['bg_input']};
            color: {t['text_main']};
            border: 1px solid {t['border_input']};
            border-radius: 2px;
        """
        self.spin.setStyleSheet(spin_style)

        # Style label
        self.label.apply_theme()

    def _on_spin_changed(self, val):
        self._value = val
        self.value_changed.emit(float(self._value))

    def _on_label_drag(self, delta_x):
        # Scale sensitivity
        scale = self._step
        change = delta_x * scale
        new_val = self._value + change
        self.set_value(new_val)

    def _increment(self):
        self.set_value(self._value + self._step)

    def _decrement(self):
        self.set_value(self._value - self._step)

    def set_value(self, val):
        if self.is_int:
            val = int(val)
        self.spin.setValue(val) # Signal will be emitted by spinbox

    def get_value(self):
        return self._value
    
    # --- Compatibility Methods for RZDraggableNumber ---
    def set_value_from_backend(self, val):
        self.spin.blockSignals(True)
        self.set_value(val)
        self.spin.blockSignals(False)
        self._value = self.spin.value()

class _RZDragLabel(QtWidgets.QLabel):
    """Helper label that emits drag deltas"""
    drag_delta = QtCore.Signal(int)

    def __init__(self, text=""):
        super().__init__(text)
        self.setCursor(QtCore.Qt.SizeHorCursor)
        self._drag_start_x = 0
        self._dragging = False
        self.apply_theme()

    def apply_theme(self):
        """Apply theme colors to the label."""
        t = get_current_theme()
        self.setStyleSheet(f"color: {t['text_dark']}; padding-right: 4px;")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging = True
            self._drag_start_x = event.globalPos().x()

    def mouseMoveEvent(self, event):
        if self._dragging:
            current_x = event.globalPos().x()
            delta = current_x - self._drag_start_x
            self._drag_start_x = current_x # Reset for relative delta
            self.drag_delta.emit(delta)

    def mouseReleaseEvent(self, event):
        self._dragging = False

# Alias for backward compatibility
# Старый код, ожидающий RZDraggableNumber(value=0, is_int=True), будет работать,
# так как аргументы конструктора RZSmartSlider совпадают.
RZDraggableNumber = RZSmartSlider