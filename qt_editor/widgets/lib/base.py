# RZMenu/qt_editor/widgets/base.py
from PySide6 import QtWidgets, QtCore, QtGui
import logging

logger = logging.getLogger(__name__)

from .theme import get_current_theme

class RZVisualInputMixin:
    """
    Mixin to provide consistent hover animations, focused accents,
    and optional resizing logic to input widgets (QLineEdit & QPlainTextEdit).
    """
    def _init_visuals(self):
        # Feature Toggles
        self._draw_border_enabled = True
        self._draw_glow_enabled = True
        self._is_active = False # Pressed state
        
        # 1. Focus Animation (Subtle blue glow)
        self._focus_progress = 0.0
        self._focus_anim = QtCore.QPropertyAnimation(self, b"focus_progress")
        self._focus_anim.setDuration(200)
        self._focus_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        # 2. Press Animation (Apple-like Pulse/Shrink)
        self._press_progress = 0.0
        self._press_anim = QtCore.QPropertyAnimation(self, b"press_progress")
        self._press_anim.setDuration(120)
        self._press_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)

        # 3. Hover Animation (Fluid and Snappy)
        self._hover_progress = 0.0
        self._hover_anim = QtCore.QPropertyAnimation(self, b"hover_progress")
        self._hover_anim.setDuration(220)
        self._hover_anim.setEasingCurve(QtCore.QEasingCurve.OutQuint)
        
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

    @QtCore.Property(float)
    def focus_progress(self):
        return self._focus_progress

    @focus_progress.setter
    def focus_progress(self, val):
        self._focus_progress = val
        self.update()

    @QtCore.Property(float)
    def press_progress(self):
        return self._press_progress

    @press_progress.setter
    def press_progress(self, val):
        self._press_progress = val
        self.update()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self._focus_anim.stop()
        self._focus_anim.setEndValue(1.0)
        self._focus_anim.start()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._focus_anim.stop()
        self._focus_anim.setEndValue(0.0)
        self._focus_anim.start()
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._is_active = True
            self._press_anim.stop()
            self._press_anim.setEndValue(1.0)
            self._press_anim.start()
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_active = False
        self._press_anim.stop()
        self._press_anim.setEndValue(0.0)
        self._press_anim.start()
        self.update()
        super().mouseReleaseEvent(event)

    def _draw_visual_border(self, painter):
        if not self.isVisible() or not self._draw_border_enabled: return
        r = self.rect() 
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        theme = get_current_theme()
        base_border_color = QtGui.QColor(theme.get('border_input', '#4A505A'))
        accent_color = QtGui.QColor(theme.get('accent', '#5298D4'))
        
        # 1. Draw Subtle Focus/Hover background glow (inner fill)
        if self._focus_progress > 0.01 or self._hover_progress > 0.01:
            glow_alpha = int((self._focus_progress * 15) + (self._hover_progress * 10))
            if glow_alpha > 0:
                glow_bg = QtGui.QColor(accent_color)
                glow_bg.setAlpha(glow_alpha)
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(glow_bg)
                painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 3, 3)

        # 2. Base Border
        border_col = base_border_color
        if self._focus_progress > 0.01:
            # Transition border color to accent on focus
            border_col = QtGui.QColor(
                int(base_border_color.red() + (accent_color.red() - base_border_color.red()) * self._focus_progress),
                int(base_border_color.green() + (accent_color.green() - base_border_color.green()) * self._focus_progress),
                int(base_border_color.blue() + (accent_color.blue() - base_border_color.blue()) * self._focus_progress)
            )

        pen = QtGui.QPen(border_col, 1.0)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)

        # 3. Outer Focus Accent (Glow Ring)
        if (self._draw_glow_enabled and self._focus_progress > 0.01) or self._press_progress > 0.01:
            focus_alpha = int(self._focus_progress * 100)
            if self._is_active: 
                focus_alpha = 180 

            glow_color = QtGui.QColor(accent_color)
            glow_color.setAlpha(focus_alpha)
            
            # Press pulse effect
            press_expand = self._press_progress * 1.2
            
            pen = QtGui.QPen(glow_color, 1.2 + press_expand)
            painter.setPen(pen)
            
            # Apple-style focus ring is slightly outside the border
            glow_rect = r.adjusted(-0.5 - press_expand, -0.5 - press_expand, 0.5 + press_expand, 0.5 + press_expand)
            painter.drawRoundedRect(glow_rect, 4, 4)

    def _draw_resizer_dots(self, painter):
        """Optional resizer visual for multi-line editors."""
        if not self._is_resizable: return
        
        r = self.rect()
        cx = r.center().x()
        by = r.bottom() - 4
        
        theme = get_current_theme()
        col = QtGui.QColor(theme.get('border_input', '#4A505A'))
        if self._hover_progress > 0.5:
            col = QtGui.QColor(theme.get('accent', '#5298D4'))
            
        painter.setPen(QtGui.QPen(col, 1.5))
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

class RZBaseWidget(QtWidgets.QWidget):
    """
    Base class for all RZ widgets.
    Automatically handles ContextManager updates for the area it's in.
    """
    def __init__(self, parent=None, area_name="NONE"):
        super().__init__(parent)
        self.area_name = area_name
        
    def enterEvent(self, event):
        from ...context import RZContextManager
        RZContextManager.get_instance().update_input(QtGui.QCursor.pos(), (0, 0), area=self.area_name)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        from ...context import RZContextManager
        RZContextManager.get_instance().update_input(QtGui.QCursor.pos(), (0, 0), area="NONE")
        super().leaveEvent(event)

    def apply_theme(self):
        """Should be overridden if needed, but generic QSS usually handles it."""
        pass

class RZSmartSlider(QtWidgets.QWidget):
    """
    Smart Slider: Label (drag) + Spinbox + +/- Buttons.
    Supports math operations (+=, -=, *=, /=) and mixed selection states.
    """
    value_changed = QtCore.Signal(float)
    math_requested = QtCore.Signal(str) # Emits e.g., "+=10"
    released = QtCore.Signal()          # Emits on mouse release/editing finish

    def setRange(self, min_val, max_val):
        self.spin.setRange(min_val, max_val)
        if self.is_int:
            self.slider.setRange(int(min_val), int(max_val))
        else:
            self.slider.setRange(int(min_val * 100), int(max_val * 100))

    def set_range(self, min_val, max_val):
        self.setRange(min_val, max_val)

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
        self.spin.lineEdit().installEventFilter(self)

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

        # Check for relative math operators (+=, -=, *=, /=)
        if any(text.startswith(op) for op in ["+=", "-=", "*=", "/="]):
            self.math_requested.emit(text)
            return

        # For absolute arithmetic (e.g. 500 - 100), force evaluate it now
        # so the SpinBox value is updated before focus is lost.
        if any(op in text for op in "+-*/%^"):
            val = self.spin.valueFromText(text)
            self.spin.blockSignals(True)
            self.spin.setValue(val)
            self.spin.blockSignals(False)
            self.value_changed.emit(float(val))

    def apply_theme(self):
        """Apply theme colors to all child widgets."""
        t = get_current_theme()
        
        # Base colors
        bg_btn = t.get('bg_header', '#3A404A')
        bg_input = t.get('bg_input', '#252930')
        bg_panel = t.get('bg_panel', '#2C313A')
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
                border: none; border-radius: 2px;
            }}
            QAbstractSpinBox:focus {{ background: {bg_panel}; }}
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
        if self._is_mixed:
            self.math_requested.emit(f"+={self._step}")
            return
        self.set_value(self._value + self._step)

    def _decrement(self):
        if self._is_mixed:
            self.math_requested.emit(f"-={self._step}")
            return
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

class _RZSmartSpinBox(RZVisualInputMixin, QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_visuals()

    def validate(self, text, pos):
        import re
        if text == "--" or re.fullmatch(r"[0-9.,+\-*/()%^= ]*", text):
            return QtGui.QValidator.State.Acceptable, text, pos
        return super().validate(text, pos)

    def valueFromText(self, text):
        if text == "--": return self.value()
        try:
            from ...utils.evaluation import safe_eval
            eval_text = text.replace(',', '.')
            val = safe_eval(eval_text)
            if isinstance(val, (int, float)):
                return int(round(val))
        except Exception:
            pass
        return self.value() # Revert on failure

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        painter.end()

    def wheelEvent(self, event):
        event.ignore()

class _RZSmartDoubleSpinBox(RZVisualInputMixin, QtWidgets.QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_visuals()

    def validate(self, text, pos):
        import re
        if text == "--" or re.fullmatch(r"[0-9.,+\-*/()%^= ]*", text):
            return QtGui.QValidator.State.Acceptable, text, pos
        return super().validate(text, pos)

    def valueFromText(self, text):
        if text == "--": return self.value()
        try:
            from ...utils.evaluation import safe_eval
            eval_text = text.replace(',', '.')
            val = safe_eval(eval_text)
            if isinstance(val, (int, float)):
                return float(val)
        except Exception:
            pass
        return self.value() # Revert on failure

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        painter.end()

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
RZDraggableNumber = RZSmartSlider