# RZMenu/qt_editor/widgets/base.py
from PySide6 import QtWidgets, QtCore, QtGui
from .theme import get_current_theme

class RZSmartSlider(QtWidgets.QWidget):
    """
    Smart Slider: Label (drag) + Spinbox + +/- Buttons.
    Supports math operations (+=, -=, *=, /=) and mixed selection states.
    """
    value_changed = QtCore.Signal(float)
    math_requested = QtCore.Signal(str) # Emits e.g., "+=10"

    def __init__(self, value=0.0, is_int=True, parent=None, label_text="Value", show_slider=True):
        super().__init__(parent)
        self.is_int = is_int
        self.show_slider = show_slider
        self._value = int(value) if is_int else float(value)
        self._step = 1 if is_int else 0.1
        self._is_mixed = False
        
        # Layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 1. Draggable Label
        self.label = _RZDragLabel(label_text)
        self.label.drag_delta.connect(self._on_label_drag)
        layout.addWidget(self.label)

        # 2. Button [-]
        self.btn_minus = QtWidgets.QPushButton("-")
        self.btn_minus.setFixedSize(16, 20)
        self.btn_minus.clicked.connect(self._decrement)
        layout.addWidget(self.btn_minus)

        # 3. SpinBox (Customized for Math & Mixed)
        if self.is_int:
            self.spin = _RZSmartSpinBox(self)
            self.spin.setRange(-999999, 999999)
        else:
            self.spin = _RZSmartDoubleSpinBox(self)
            self.spin.setRange(-999999.0, 999999.0)
            self.spin.setDecimals(2)

        self.spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.spin.setValue(self._value)
        self.spin.valueChanged.connect(self._on_spin_changed)
        
        # 3.5 REAL SLIDER (Requested for Alpha and visual improvement)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimumWidth(40)
        if self.is_int:
            self.slider.setRange(0, 100) # Default range, can be adjusted
        else:
            self.slider.setRange(0, 100)
        
        self._sync_slider_to_value()
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider, 1) # Give it stretch
        
        if not self.show_slider:
            self.slider.hide()

        # Setup Math/Mixed handling on the internal LineEdit
        self.spin.lineEdit().installEventFilter(self)
        self.spin.lineEdit().returnPressed.connect(self._handle_manual_entry)
        
        self.spin.setFixedWidth(50) # Keep spinbox compact now that we have a slider
        layout.addWidget(self.spin)

        # 4. Button [+]
        self.btn_plus = QtWidgets.QPushButton("+")
        self.btn_plus.setFixedSize(16, 20)
        self.btn_plus.clicked.connect(self._increment)
        layout.addWidget(self.btn_plus)

        self.apply_theme()

    def eventFilter(self, obj, event):
        if obj == self.spin.lineEdit():
            if event.type() == QtCore.QEvent.FocusIn:
                if self._is_mixed:
                    self.spin.lineEdit().clear()
            elif event.type() == QtCore.QEvent.FocusOut:
                self._handle_manual_entry()
        return super().eventFilter(obj, event)

    def _handle_manual_entry(self):
        text = self.spin.lineEdit().text().strip()
        if not text:
            if self._is_mixed:
                self.spin.lineEdit().setText("--")
            return

        # Check for math operators
        if any(text.startswith(op) for op in ["+=", "-=", "*=", "/="]):
            self.math_requested.emit(text)
            return

        # Regular numeric entry handled by spinbox default logic 
        # (Spinbox will auto-parse it on focus out or returnPressed)

    def apply_theme(self):
        """Apply theme colors to all child widgets."""
        t = get_current_theme()
        
        # Base colors
        bg_btn = t.get('bg_header', '#3A404A')
        bg_input = t.get('bg_input', '#252930')
        border = t.get('border_input', '#4A505A')
        text = t.get('text_main', '#E0E2E4')
        accent = t.get('accent', '#5298D4')

        button_style = f"""
            QPushButton {{
                padding: 0px; border: none; border-radius: 2px;
                background: {bg_btn}; color: {text};
            }}
            QPushButton:hover {{ background: {accent}; }}
        """
        self.btn_minus.setStyleSheet(button_style)
        self.btn_plus.setStyleSheet(button_style)

        spin_style = f"""
            QAbstractSpinBox {{
                background: {bg_input}; color: {text};
                border: 1px solid {border}; border-radius: 2px;
            }}
            QAbstractSpinBox:focus {{ border: 1px solid {accent}; }}
        """
        self.spin.setStyleSheet(spin_style)
        
        slider_style = f"""
            QSlider::groove:horizontal {{
                height: 4px; background: {bg_btn}; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {accent}; border-radius: 5px; width: 10px; height: 10px; margin: -3px 0;
            }}
        """
        self.slider.setStyleSheet(slider_style)
        self.label.apply_theme()

    def _on_spin_changed(self, val):
        if self._is_mixed:
            self._is_mixed = False
            self.spin.lineEdit().setStyleSheet("") # Reset style
        self._value = val
        self.value_changed.emit(float(self._value))

    def _on_label_drag(self, delta_x):
        if self._is_mixed: return # Don't drag mixed values yet
        scale = self._step
        change = delta_x * scale
        self.set_value(self._value + change)

    def _increment(self):
        if self._is_mixed: return
        self.set_value(self._value + self._step)

    def _decrement(self):
        if self._is_mixed: return
        self.set_value(self._value - self._step)

    def set_value(self, val, emit_signal=True):
        self._is_mixed = False
        if self.is_int: val = int(val)
        self.spin.blockSignals(True)
        self.spin.setValue(val)
        self.spin.blockSignals(False)
        self._value = val
        self._sync_slider_to_value()
        if emit_signal:
            self.value_changed.emit(float(self._value))

    def _sync_slider_to_value(self):
        self.slider.blockSignals(True)
        if self.is_int:
            self.slider.setValue(int(self._value))
        else:
            self.slider.setValue(int(self._value * 100))
        self.slider.blockSignals(False)

    def _on_slider_changed(self, val):
        if self.is_int:
            self.set_value(val)
        else:
            self.set_value(val / 100.0)

    def set_value_from_backend(self, val):
        """Special handler for data sync, supports None for mixed values."""
        if self.spin.hasFocus():
            return
            
        self.spin.blockSignals(True)
        if val is None:
            self._is_mixed = True
            self.spin.lineEdit().setText("--")
            self.spin.lineEdit().setStyleSheet("color: #888; font-style: italic;")
        else:
            self._is_mixed = False
            self.set_value(val, emit_signal=False)
            self.spin.lineEdit().setStyleSheet("")
        self.spin.blockSignals(False)

    def get_value(self):
        return None if self._is_mixed else self._value

# --- Helper Internal Classes ---

class _RZSmartSpinBox(QtWidgets.QSpinBox):
    def validate(self, text, pos):
        if text == "--" or any(text.startswith(op) for op in ["+=", "-=", "*=", "/="]):
            return QtGui.QValidator.Acceptable, text, pos
        return super().validate(text, pos)

    def wheelEvent(self, event):
        event.ignore()

class _RZSmartDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def validate(self, text, pos):
        if text == "--" or any(text.startswith(op) for op in ["+=", "-=", "*=", "/="]):
            return QtGui.QValidator.Acceptable, text, pos
        return super().validate(text, pos)

    def wheelEvent(self, event):
        event.ignore()


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