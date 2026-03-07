# RZMenu/qt_editor/widgets/base.py
from PySide6 import QtWidgets, QtCore, QtGui
from .theme import get_current_theme

class RZVisualInputMixin:
    """
    Mixin to provide consistent hover animations, focused accents,
    and optional resizing logic to input widgets (QLineEdit & QPlainTextEdit).
    """
    def _init_visuals(self):
        # Hover Animation
        self._hover_progress = 0.0
        self._hover_anim = QtCore.QPropertyAnimation(self, b"hover_progress")
        self._hover_anim.setDuration(250)
        
        # Resizing flags
        self._is_resizable = False
        self._resizing = False
        self._last_y = 0
        self._min_res_h = 24
        self._max_res_h = 16777215

    @QtCore.Property(float)
    def hover_progress(self):
        return self._hover_progress

    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        self.update()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.setEasingCurve(QtCore.QEasingCurve.InCubic)
        self._hover_anim.start()
        super().leaveEvent(event)

    def _draw_visual_border(self, painter):
        """Standardized drawing for hover and focus borders."""
        if not hasattr(self, 'rect'): return
        
        # Рисуем "тестовый маркер" в правом верхнем углу, если мышь наведена
        if self._hover_progress > 0.01:
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            
            # 1. Цвет маркера — ярко-оранжевый/красный
            marker_color = QtGui.QColor("#FF4500")
            marker_color.setAlpha(int(255 * self._hover_progress))
            painter.setBrush(marker_color)
            painter.setPen(QtCore.Qt.NoPen)
            
            # 2. Рисуем кружок в углу (x, y, width, height)
            # Сдвигаем внутрь на 5 пикселей от правого края
            r = self.rect()
            circle_size = 8 * self._hover_progress
            painter.drawEllipse(r.right() - 15, 5, circle_size, circle_size)
            
            # --- Оставляем и старую логику рамки, но сделаем её ЖИРНОЙ ---
            accent = QtGui.QColor("#FF0000")
            accent.setAlpha(int(160 * self._hover_progress))
            pen = QtGui.QPen(accent, 3.0) # 3 пикселя — это очень жирно
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRoundedRect(r.adjusted(2, 2, -2, -2), 4, 4)

    def _draw_resizer_dots(self, painter):
        """Optional resizer visual for multi-line editors."""
        if not self._is_resizable: return
        
        r = self.rect()
        cx = r.center().x()
        by = r.bottom() - 4
        
        theme = get_current_theme()
        painter.setPen(QtGui.QPen(QtGui.QColor(theme.get('border_input', '#4A505A')), 1.5))
        
        painter.drawPoint(cx - 4, by)
        painter.drawPoint(cx, by)
        painter.drawPoint(cx + 4, by)

    def _handle_visual_mouse_press(self, event):
        if self._is_resizable:
            if event.button() == QtCore.Qt.LeftButton and event.pos().y() > self.height() - 15:
                self._resizing = True
                self._last_y = event.globalPosition().y()
                self.setCursor(QtCore.Qt.SizeVerCursor)
                event.accept()
                return True
        return False

    def _handle_visual_mouse_move(self, event):
        if self._resizing:
            current_y = event.globalPosition().y()
            dy = current_y - self._last_y
            self._last_y = current_y
            
            new_h = max(self._min_res_h, min(self.height() + dy, self._max_res_h))
            self.setMinimumHeight(new_h)
            event.accept()
            return True
            
        if self._is_resizable:
            if event.pos().y() > self.height() - 15:
                self.setCursor(QtCore.Qt.SizeVerCursor)
            else:
                self.setCursor(QtCore.Qt.IBeamCursor if isinstance(self, (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit)) else QtCore.Qt.ArrowCursor)
        return False

    def _handle_visual_mouse_release(self, event):
        if self._resizing:
            self._resizing = False
            self.unsetCursor()
            event.accept()
            return True
        return False

class RZSmartSlider(QtWidgets.QWidget):
    """
    Smart Slider: Label (drag) + Spinbox + +/- Buttons.
    Supports math operations (+=, -=, *=, /=) and mixed selection states.
    """
    value_changed = QtCore.Signal(float)
    math_requested = QtCore.Signal(str) # Emits e.g., "+=10"
    released = QtCore.Signal()          # Emits on mouse release/editing finish

    def __init__(self, value=0.0, is_int=True, parent=None, label_text="Value", show_slider=True):
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Preferred)
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
        self.slider.setFixedHeight(20) # Match spinbox height roughly
        if self.is_int:
            self.slider.setRange(0, 100) 
        else:
            self.slider.setRange(0, 100)
        
        self._sync_slider_to_value()
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        if self.show_slider:
            layout.addWidget(self.slider, 1) # Give it stretch
        
        # REMOVED: self.spin.setFixedWidth(50) - Let it expand as requested!
        self.spin.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Preferred)
        self.spin.setMinimumWidth(80) # Ensure it's never too small
        layout.addWidget(self.spin)
        
        if not self.show_slider:
             # Force the spinbox to take all available space if no slider
             layout.setStretch(layout.indexOf(self.spin), 1)

        # 4. Button [+]
        self.btn_plus = QtWidgets.QPushButton("+")
        self.btn_plus.setFixedSize(16, 20)
        self.btn_plus.clicked.connect(self._increment)
        layout.addWidget(self.btn_plus)

        # Connect release signals
        self.slider.sliderReleased.connect(self.released.emit)
        self.spin.editingFinished.connect(self.released.emit)
        self.label.released.connect(self.released.emit)

        # Better interaction feel
        self.slider.setMouseTracking(True)
        self.slider.installEventFilter(self)

        self.apply_theme()

    def eventFilter(self, obj, event):
        if obj == self.spin.lineEdit():
            if event.type() == QtCore.QEvent.FocusIn:
                if self._is_mixed:
                    self.spin.lineEdit().clear()
            elif event.type() == QtCore.QEvent.FocusOut:
                self._handle_manual_entry()
        
        elif obj == self.slider:
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.MiddleButton:
                    event.ignore()
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    # Click to jump (interpolation feel)
                    opt = QtWidgets.QStyleOptionSlider()
                    self.slider.initStyleOption(opt)
                    sr = self.slider.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderGroove, self.slider)
                    if sr.contains(event.pos()):
                        new_val = QtWidgets.QStyle.sliderValueFromPosition(self.slider.minimum(), self.slider.maximum(), event.pos().x(), sr.width())
                        self.slider.setValue(new_val)
                        # We don't return True here so the standard logic can also kick in for dragging
            elif event.type() == QtCore.QEvent.Wheel:
                # Ignore wheel on slider as requested
                event.ignore()
                return True
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
    released = QtCore.Signal()

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
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self._dragging:
            current_x = event.globalPos().x()
            delta = current_x - self._drag_start_x
            self._drag_start_x = current_x # Reset for relative delta
            self.drag_delta.emit(delta)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self.released.emit()

# Alias for backward compatibility
# Старый код, ожидающий RZDraggableNumber(value=0, is_int=True), будет работать,
# так как аргументы конструктора RZSmartSlider совпадают.
RZDraggableNumber = RZSmartSlider