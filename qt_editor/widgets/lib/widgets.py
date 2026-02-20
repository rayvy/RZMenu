# RZMenu/qt_editor/widgets/lib/widgets.py
from PySide6 import QtWidgets, QtCore, QtGui
from ...context import RZContextManager
from .theme import get_current_theme

# --- RZColorButton ---
class RZColorButton(QtWidgets.QPushButton):
    colorChanged = QtCore.Signal(list)

    def __init__(self, text=""):
        super().__init__(text)
        self._qcolor = QtGui.QColor(255, 255, 255)
        self.clicked.connect(self._pick_color)
        self.update_style()

    def set_color(self, color_data):
        if not color_data: return
        if isinstance(color_data, str):
            self._qcolor.setNamedColor(color_data)
            if not self._qcolor.isValid(): self._qcolor = QtGui.QColor(color_data)
        elif isinstance(color_data, (list, tuple)):
            if len(color_data) >= 3:
                r, g, b = color_data[0], color_data[1], color_data[2]
                a = color_data[3] if len(color_data) > 3 else 1.0
                self._qcolor.setRgbF(r, g, b, a)
        if not self._qcolor.isValid(): self._qcolor = QtGui.QColor(255, 0, 255)
        self.update_style()

    def update_style(self):
        if not self._qcolor.isValid(): return
        r, g, b, a = self._qcolor.red(), self._qcolor.green(), self._qcolor.blue(), self._qcolor.alpha()
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        theme = get_current_theme()
        text_bright = theme.get('text_bright', '#FFFFFF')
        text_main = theme.get('text_main', '#000000')
        border_col = theme.get('border_input', '#444')
        contrast_color = text_main if luminance > 128 else text_bright
        bg_style = f"rgba({r},{g},{b},{a})"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_style};
                color: {contrast_color};
                border: 1px solid {border_col};
                border-radius: 3px;
                padding: 4px 8px;
            }}
        """)

    def _pick_color(self):
        dialog = QtWidgets.QColorDialog(self._qcolor, self)
        dialog.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, True)
        if dialog.exec():
            c = dialog.selectedColor()
            self._qcolor = c
            self.update_style()
            self.colorChanged.emit([c.redF(), c.greenF(), c.blueF(), c.alphaF()])

# --- Advanced Color Panel ---
class RZAdvancedColorPanel(QtWidgets.QWidget):
    """
    Advanced Color Panel: HEX, HSV, Alpha and Palette controls.
    Designed for inline use in the Inspector.
    """
    colorChanged = QtCore.Signal(list) # [r, g, b, a] floats

    # --- Внутренний класс: Цветовой круг (Hue/Saturation) ---
    class ColorWheel(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumSize(100, 100)
            self.h = 0.0
            self.s = 0.0
            self._dragging = False
            self.setCursor(QtCore.Qt.CrossCursor)

        def set_hs(self, h, s):
            self.h = h
            self.s = s
            self.update()

        def mousePressEvent(self, event):
            self._update_from_mouse(event.pos())
            self._dragging = True

        def mouseMoveEvent(self, event):
            if self._dragging:
                self._update_from_mouse(event.pos())

        def mouseReleaseEvent(self, event):
            self._dragging = False

        def _update_from_mouse(self, pos):
            # Вычисляем центр и радиус
            center = QtCore.QPointF(self.width() / 2, self.height() / 2)
            dx = pos.x() - center.x()
            dy = pos.y() - center.y()
            
            # Угол -> Hue
            import math
            angle = math.atan2(dy, dx)
            hue = math.degrees(angle)
            if hue < 0: hue += 360
            # Корректировка, чтобы 0 был справа или сверху (зависит от QConicalGradient)
            # В Qt 0 градусов - это 3 часа. В HSV обычно 0 - красный.
            # QConicalGradient начинает с 3 часов против часовой стрелки? Проверим отрисовку.
            # Оставим стандартную математику, подгоним отрисовку под нее.
            
            # Дистанция -> Saturation
            dist = math.sqrt(dx*dx + dy*dy)
            radius = min(self.width(), self.height()) / 2
            sat = min(1.0, dist / radius) if radius > 0 else 0

            self.h = hue
            self.s = sat * 255.0 # храним как 0-255 для совместимости с QColor
            self.update()
            
            # Вызов коллбэка родителя (так как это вложенный класс)
            if self.parent():
                self.parent()._on_wheel_interact(self.h, self.s)

        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)

            rect = self.rect()
            radius = min(rect.width(), rect.height()) / 2 - 2
            center = QtCore.QPointF(rect.width() / 2, rect.height() / 2)

            # 1. Рисуем Hue (Конический градиент)
            conical = QtGui.QConicalGradient(center, 0)
            # Цвета радуги
            conical.setColorAt(0.0, QtGui.QColor.fromHsvF(0.0, 1, 1))
            conical.setColorAt(1.0/6, QtGui.QColor.fromHsvF(1.0/6, 1, 1))
            conical.setColorAt(2.0/6, QtGui.QColor.fromHsvF(2.0/6, 1, 1))
            conical.setColorAt(3.0/6, QtGui.QColor.fromHsvF(0.5, 1, 1))
            conical.setColorAt(4.0/6, QtGui.QColor.fromHsvF(4.0/6, 1, 1))
            conical.setColorAt(5.0/6, QtGui.QColor.fromHsvF(5.0/6, 1, 1))
            conical.setColorAt(1.0, QtGui.QColor.fromHsvF(1.0, 1, 1))
            
            painter.setBrush(QtGui.QBrush(conical))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(center, radius, radius)

            # 2. Рисуем Saturation (Радиальный градиент от белого к прозрачному)
            radial = QtGui.QRadialGradient(center, radius)
            radial.setColorAt(0.0, QtGui.QColor(255, 255, 255, 255))
            radial.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
            painter.setBrush(QtGui.QBrush(radial))
            painter.drawEllipse(center, radius, radius)

            # 3. Маркер текущего цвета
            import math
            # Преобразуем H/S обратно в координаты
            angle_rad = math.radians(self.h)
            sat_factor = self.s / 255.0
            dist = sat_factor * radius
            
            marker_x = center.x() + math.cos(angle_rad) * dist
            marker_y = center.y() + math.sin(angle_rad) * dist
            
            # Кружок маркера (черно-белая обводка для контраста)
            painter.setPen(QtGui.QPen(QtCore.Qt.black, 2))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(QtCore.QPointF(marker_x, marker_y), 5, 5)
            painter.setPen(QtGui.QPen(QtCore.Qt.white, 1))
            painter.drawEllipse(QtCore.QPointF(marker_x, marker_y), 5, 5)


    # --- Внутренний класс: Вертикальный слайдер яркости (Value) ---
    class ValueBar(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedWidth(24)
            self.setMinimumHeight(100)
            self.v = 255
            self.current_hue = 0
            self.current_sat = 255
            self._dragging = False
            self.setCursor(QtCore.Qt.ArrowCursor)

        def set_hsv(self, h, s, v):
            self.current_hue = h
            self.current_sat = s
            self.v = v
            self.update()

        def mousePressEvent(self, event):
            self._update_from_mouse(event.y())
            self._dragging = True

        def mouseMoveEvent(self, event):
            if self._dragging:
                self._update_from_mouse(event.y())

        def mouseReleaseEvent(self, event):
            self._dragging = False

        def _update_from_mouse(self, y):
            # Сверху 255 (Value=100), снизу 0
            h = self.height()
            val = 1.0 - (y / float(h))
            val = max(0.0, min(1.0, val))
            self.v = val * 255.0
            self.update()
            
            if self.parent():
                self.parent()._on_val_bar_interact(self.v)

        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            rect = self.rect()

            # Градиент от черного (внизу) к цвету (вверху)
            base_color = QtGui.QColor.fromHsv(int(self.current_hue), int(self.current_sat), 255)
            
            linear = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            linear.setColorAt(0.0, base_color)
            linear.setColorAt(1.0, QtCore.Qt.black)
            
            painter.fillRect(rect, linear)
            
            # Индикатор уровня
            y_pos = (1.0 - (self.v / 255.0)) * rect.height()
            painter.setPen(QtGui.QPen(QtCore.Qt.white, 1))
            # Стрелочки или просто линия
            painter.drawLine(0, int(y_pos), rect.width(), int(y_pos))
            # Небольшая рамка для контраста
            painter.setPen(QtGui.QPen(QtCore.Qt.black, 1))
            painter.drawLine(0, int(y_pos)-1, rect.width(), int(y_pos)-1)
            painter.drawLine(0, int(y_pos)+1, rect.width(), int(y_pos)+1)


    def __init__(self, parent=None):
        super().__init__(parent)
        from .base import RZSmartSlider
        self._block_signals = False
        self._qcolor = QtGui.QColor(255, 255, 255)
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Preview & HEX
        h_top = QtWidgets.QHBoxLayout()
        self.preview = QtWidgets.QFrame()
        self.preview.setFixedSize(24, 24)
        self.preview.setFrameShape(QtWidgets.QFrame.StyledPanel)
        h_top.addWidget(self.preview)

        self.edit_hex = RZLineEdit()
        self.edit_hex.setPlaceholderText("#FFFFFF")
        self.edit_hex.editingFinished.connect(self._on_hex_edited)
        h_top.addWidget(self.edit_hex)
        main_layout.addLayout(h_top)

        # --- NEW: Color Wheel Area ---
        h_wheel_layout = QtWidgets.QHBoxLayout()
        h_wheel_layout.setSpacing(6)
        
        # Инстанцируем вложенные классы
        self.wheel = self.ColorWheel(self)
        self.val_bar = self.ValueBar(self)
        
        h_wheel_layout.addWidget(self.wheel, 1) # wheel растягивается
        h_wheel_layout.addWidget(self.val_bar, 0) # слайдер фиксированный
        
        main_layout.addLayout(h_wheel_layout)
        # -----------------------------

        # 2. HSV Sliders
        self.sl_h = RZSmartSlider(label_text="H", is_int=True)
        self.sl_h.spin.setRange(0, 360)
        self.sl_h.value_changed.connect(self._on_hsv_slider_changed)
        main_layout.addWidget(self.sl_h)

        self.sl_s = RZSmartSlider(label_text="S", is_int=True)
        self.sl_s.spin.setRange(0, 100)
        self.sl_s.value_changed.connect(self._on_hsv_slider_changed)
        main_layout.addWidget(self.sl_s)

        self.sl_v = RZSmartSlider(label_text="V", is_int=True)
        self.sl_v.spin.setRange(0, 100)
        self.sl_v.value_changed.connect(self._on_hsv_slider_changed)
        main_layout.addWidget(self.sl_v)

        # 3. Alpha Slider
        self.sl_a = RZSmartSlider(label_text="A", is_int=False)
        self.sl_a.spin.setRange(0.0, 1.0)
        self.sl_a.spin.setSingleStep(0.1)
        self.sl_a.value_changed.connect(self._on_alpha_changed)
        main_layout.addWidget(self.sl_a)

        # 4. Palette (12 colors)
        self.palette_layout = QtWidgets.QGridLayout()
        self.palette_layout.setSpacing(4)
        colors = [
            "#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#00FFFF", "#0000FF",
            "#8B00FF", "#FF00FF", "#FFFFFF", "#AAAAAA", "#555555", "#000000"
        ]
        for i, hex_code in enumerate(colors):
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(18, 18)
            btn.setStyleSheet(f"background-color: {hex_code}; border: 1px solid #444; border-radius: 2px;")
            btn.clicked.connect(lambda _, h=hex_code: self._set_hex(h))
            self.palette_layout.addWidget(btn, i // 6, i % 6)
        main_layout.addLayout(self.palette_layout)

        self.update_style()

    # --- Новые методы-хендлеры для графических элементов ---
    def _on_wheel_interact(self, h, s):
        if self._block_signals: return
        # Обновляем цвет на основе нового H и S, сохраняя старый V и Alpha
        curr_v = self._qcolor.value()
        curr_a = self._qcolor.alpha()
        new_color = QtGui.QColor.fromHsvF(h / 360.0, s / 255.0, curr_v / 255.0, curr_a / 255.0) # hsvF is 0-1
        
        self._qcolor = new_color
        self._update_all_widgets()
        self._emit_color()

    def _on_val_bar_interact(self, v):
        if self._block_signals: return
        # Обновляем только V
        h, s, _, a = self._qcolor.getHsv()
        if h < 0: h = 0
        new_color = QtGui.QColor.fromHsv(h, s, int(v), a)
        
        self._qcolor = new_color
        self._update_all_widgets()
        self._emit_color()
    # -------------------------------------------------------

    def set_color(self, color_data):
        """color_data: [r, g, b, a] floats or string"""
        if self._block_signals: return
        self._block_signals = True
        
        if not color_data: return
        if isinstance(color_data, str):
            self._qcolor.setNamedColor(color_data)
        elif isinstance(color_data, (list, tuple)):
            r, g, b = color_data[0], color_data[1], color_data[2]
            a = color_data[3] if len(color_data) > 3 else 1.0
            self._qcolor.setRgbF(r, g, b, a)
        
        self._update_all_widgets()
        self._block_signals = False

    def _update_all_widgets(self):
        # Update HEX
        self.edit_hex.setText(self._qcolor.name(QtGui.QColor.HexArgb).upper())
        
        # Get HSV data
        h, s, v, _ = self._qcolor.getHsv()
        if h < 0: h = 0 # Undefined hue for black/white

        # Update HSV Sliders
        self.sl_h.set_value(h, emit_signal=False)
        self.sl_s.set_value(int(s / 255.0 * 100), emit_signal=False)
        self.sl_v.set_value(int(v / 255.0 * 100), emit_signal=False)
        
        # Update Alpha
        self.sl_a.set_value(self._qcolor.alphaF(), emit_signal=False)
        
        # Update Preview
        self.preview.setStyleSheet(f"background-color: {self._qcolor.name(QtGui.QColor.HexArgb)}; border-radius: 3px;")

        # --- Update Visual Pickers ---
        # Обновляем круг и бар, не вызывая сигналов (они просто перерисуются)
        self.wheel.set_hs(float(h), float(s))
        self.val_bar.set_hsv(h, s, v)

    def _on_hex_edited(self):
        if self._block_signals: return
        hex_text = self.edit_hex.text().strip()
        if not hex_text.startswith("#"): hex_text = "#" + hex_text
        c = QtGui.QColor(hex_text)
        if c.isValid():
            self._qcolor = c
            self._update_all_widgets()
            self._emit_color()

    def _set_hex(self, hex_code):
        self.edit_hex.setText(hex_code)
        self._on_hex_edited()

    def _on_hsv_slider_changed(self, _):
        if self._block_signals: return
        h = int(self.sl_h.get_value())
        s = int(self.sl_s.get_value() / 100.0 * 255)
        v = int(self.sl_v.get_value() / 100.0 * 255)
        new_color = QtGui.QColor.fromHsv(h, s, v, self._qcolor.alpha())
        self._qcolor = new_color
        self._update_all_widgets()
        self._emit_color()

    def _on_alpha_changed(self, val):
        if self._block_signals: return
        self._qcolor.setAlphaF(val)
        self._update_all_widgets()
        self._emit_color()

    def _emit_color(self):
        c = self._qcolor
        self.colorChanged.emit([c.redF(), c.greenF(), c.blueF(), c.alphaF()])

    def apply_theme(self):
        """Update styles for internal widgets that don't have their own apply_theme."""
        theme = get_current_theme()
        border_col = theme.get('border_input', '#444')
        self.preview.setFrameShape(QtWidgets.QFrame.StyledPanel)
        # Preview style depends on current color, handled in _update_all_widgets
        self._update_all_widgets()

    def update_style(self):
        self.apply_theme()

# --- New RZCheckBox ---
class RZCheckBox(QtWidgets.QCheckBox):
    def __init__(self, text="", parent=None, checked=False):
        super().__init__(text, parent)
        self.setChecked(checked)
        self.apply_theme()
        
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QCheckBox {{
                color: {theme.get('text_main', '#E0E2E4')};
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 2px;
                border: 1px solid {theme.get('border_input', '#4A505A')};
                background-color: {theme.get('bg_input', '#252930')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {theme.get('accent', '#5298D4')};
                border: 1px solid {theme.get('accent', '#5298D4')};
                image: url(:/icons/check.png); /* Fallback or procedural check */
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {theme.get('accent_hover', '#6AACDE')};
            }}
        """)

# --- Existing Widgets ---

class RZContextAwareWidget(QtWidgets.QWidget):
    def __init__(self, area_name, parent=None):
        super().__init__(parent)
        self.area_name = area_name
        self.setObjectName(f"RZContextWidget_{area_name}")
    def enterEvent(self, event):
        RZContextManager.get_instance().update_input(QtGui.QCursor.pos(), (0, 0), area=self.area_name)
        super().enterEvent(event)
    def leaveEvent(self, event):
        RZContextManager.get_instance().update_input(QtGui.QCursor.pos(), (0, 0), area="NONE")
        super().leaveEvent(event)

class RZStyledWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self): pass

class RZPanelWidget(RZStyledWidget):
    def __init__(self, object_name="", parent=None):
        super().__init__(parent)
        if object_name: self.setObjectName(object_name)
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            {self.objectName()} {{
                background-color: {theme.get('bg_panel', '#2C313A')};
                border: 1px solid {theme.get('border_main', '#3A404A')};
                border-radius: 4px;
            }}
        """)

class RZGroupBox(QtWidgets.QGroupBox):
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {theme.get('bg_panel', '#2C313A')};
                border: 1px solid {theme.get('border_main', '#3A404A')};
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                left: 10px;
                background-color: {theme.get('bg_panel', '#2C313A')};
                color: {theme.get('text_dark', '#9DA5B4')};
            }}
        """)

class RZPushButton(QtWidgets.QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get('bg_header', '#3A404A')};
                color: {theme.get('text_main', '#E0E2E4')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {theme.get('accent_hover', '#6AACDE')};
                color: {theme.get('accent_text', '#FFFFFF')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get('accent', '#5298D4')};
            }}
            QPushButton:disabled {{
                color: {theme.get('text_disabled', '#6A717C')};
                background-color: {theme.get('bg_input', '#252930')};
            }}
        """)

class RZLabel(QtWidgets.QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"color: {theme.get('text_main', '#E0E2E4')};")

class RZSpinBox(QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QSpinBox {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QSpinBox:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
        """)
    def wheelEvent(self, event):
        event.ignore()

class RZDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QDoubleSpinBox:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
        """)
    def wheelEvent(self, event):
        event.ignore()

class RZComboBox(QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QComboBox:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
            QComboBox::drop-down {{ border-left: 1px solid {theme.get('border_input', '#4A505A')}; }}
        """)
    def wheelEvent(self, event):
        event.ignore()

class RZLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
        self._pattern = ""
        self._originals = []
        
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QLineEdit:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
        """)

    def set_pattern(self, pattern, originals=None):
        self._pattern = pattern
        self._originals = originals or []
        self.setText(pattern)
        # Visual feedback for pattern mode
        font = self.font()
        font.setItalic(bool(pattern))
        self.setFont(font)

    def get_pattern(self):
        return self._pattern

    def get_originals(self):
        return self._originals

    def clear_pattern(self):
        self._pattern = ""
        self._originals = []
        font = self.font()
        font.setItalic(False)
        self.setFont(font)