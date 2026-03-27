# RZMenu/qt_editor/widgets/lib/widgets.py
from PySide6 import QtWidgets, QtCore, QtGui
from ...context import RZContextManager
from .theme import get_current_theme
from ...utils.debounce import RZDebouncer
from .base import RZVisualInputMixin

# --- RZColorButton ---
class RZColorButton(RZVisualInputMixin, QtWidgets.QPushButton):
    colorChanged = QtCore.Signal(list)

    def __init__(self, text=""):
        super().__init__(text)
        self._init_visuals()
        self._qcolor = QtGui.QColor(255, 255, 255)
        self.clicked.connect(self._pick_color)
        self.update_style()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        painter.end()

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
        contrast_color = text_main if luminance > 128 else text_bright
        
        # Only set color-specific properties, others handled by QSS
        self.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); color: {contrast_color};")

    def _pick_color(self):
        dialog = QtWidgets.QColorDialog(self._qcolor, self)
        dialog.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, True)
        if dialog.exec():
            c = dialog.selectedColor()
            self._qcolor = c
            self.update_style()
            self.colorChanged.emit([c.redF(), c.greenF(), c.blueF(), c.alphaF()])

# --- Advanced Color Panel ---
# --- Advanced Color Components ---
class RZColorWheel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(145, 145)
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
        if hasattr(self.parent(), '_on_release'):
            self.parent()._on_release()

    def _update_from_mouse(self, pos):
        center = QtCore.QPointF(self.width() / 2, self.height() / 2)
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        import math
        angle = math.atan2(dy, dx)
        hue = math.degrees(angle)
        if hue < 0: hue += 360
        dist = math.sqrt(dx*dx + dy*dy)
        radius = min(self.width(), self.height()) / 2
        sat = min(1.0, dist / radius) if radius > 0 else 0
        self.h = hue
        self.s = sat * 255.0
        self.update()
        if hasattr(self.parent(), '_on_wheel_interact'):
            self.parent()._on_wheel_interact(self.h, self.s)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        radius = min(rect.width(), rect.height()) / 2 - 2
        center = QtCore.QPointF(rect.width() / 2, rect.height() / 2)
        conical = QtGui.QConicalGradient(center, 0)
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
        radial = QtGui.QRadialGradient(center, radius)
        radial.setColorAt(0.0, QtGui.QColor(255, 255, 255, 255))
        radial.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
        painter.setBrush(QtGui.QBrush(radial))
        painter.drawEllipse(center, radius, radius)
        import math
        angle_rad = math.radians(self.h)
        sat_factor = self.s / 255.0
        dist = sat_factor * radius
        marker_x = center.x() + math.cos(angle_rad) * dist
        marker_y = center.y() + math.sin(angle_rad) * dist
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 2))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(QtCore.QPointF(marker_x, marker_y), 5, 5)
        painter.setPen(QtGui.QPen(QtCore.Qt.white, 1))
        painter.drawEllipse(QtCore.QPointF(marker_x, marker_y), 5, 5)

class RZValueBar(QtWidgets.QWidget):
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
        if hasattr(self.parent(), '_on_release'):
            self.parent()._on_release()

    def _update_from_mouse(self, y):
        h = self.height()
        val = 1.0 - (y / float(max(1, h)))
        val = max(0.0, min(1.0, val))
        self.v = val * 255.0
        self.update()
        if hasattr(self.parent(), '_on_val_bar_interact'):
            self.parent()._on_val_bar_interact(self.v)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = self.rect()
        base_color = QtGui.QColor.fromHsv(int(self.current_hue), int(self.current_sat), 255)
        linear = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
        linear.setColorAt(0.0, base_color)
        linear.setColorAt(1.0, QtCore.Qt.black)
        painter.fillRect(rect, linear)
        y_pos = (1.0 - (self.v / 255.0)) * rect.height()
        painter.setPen(QtGui.QPen(QtCore.Qt.white, 1))
        painter.drawLine(0, int(y_pos), rect.width(), int(y_pos))
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 1))
        painter.drawLine(0, int(y_pos)-1, rect.width(), int(y_pos)-1)
        painter.drawLine(0, int(y_pos)+1, rect.width(), int(y_pos)+1)

class RZColorPreview(QtWidgets.QWidget):
    """Lag-free color preview using paintEvent instead of setStyleSheet."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self._color = QtGui.QColor(255, 255, 255)

    def set_color(self, qcolor):
        if self._color != qcolor:
            self._color = QtGui.QColor(qcolor)
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Rounded background/border
        path = QtGui.QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        
        painter.fillPath(path, self._color)
        
        painter.setPen(QtGui.QPen(QtGui.QColor("#444"), 1))
        painter.drawPath(path)

class RZAdvancedColorPanel(QtWidgets.QWidget):
    colorChanged = QtCore.Signal(list)

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
        self.preview = RZColorPreview()
        h_top.addWidget(self.preview)

        self.edit_hex = RZLineEdit()
        self.edit_hex.setPlaceholderText("#FFFFFF")
        self.edit_hex.editingFinished.connect(self._on_hex_edited)
        h_top.addWidget(self.edit_hex)
        main_layout.addLayout(h_top)

        # --- NEW: Color Wheel Area ---
        h_wheel_layout = QtWidgets.QHBoxLayout()
        h_wheel_layout.setSpacing(10)
        
        # Инстанцируем классы выше
        self.wheel = RZColorWheel(self)
        self.val_bar = RZValueBar(self)
        self.val_bar.setFixedWidth(20)
        
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

        # Connect release signals for performance
        self.sl_h.released.connect(self._on_release)
        self.sl_s.released.connect(self._on_release)
        self.sl_v.released.connect(self._on_release)
        self.sl_a.released.connect(self._on_release)

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

        self.apply_theme()

    # --- Новые методы-хендлеры для графических элементов ---
    def _on_wheel_interact(self, h, s):
        if self._block_signals: return
        self._block_signals = True
        
        # Keep current V and Alpha
        curr_v = self._qcolor.valueF()
        curr_a = self._qcolor.alphaF()
        
        # fromHsvF takes 0-1
        self._qcolor = QtGui.QColor.fromHsvF(h / 360.0, s / 255.0, curr_v, curr_a)
        
        # Optimized update
        self.edit_hex.setText(self._qcolor.name(QtGui.QColor.HexArgb).upper())
        self.preview.set_color(self._qcolor)
        self._update_alpha_style()
        
        self.val_bar.set_hsv(h, s, int(curr_v * 255))
        
        self._block_signals = False
        # REAL-TIME UI ONLY: _emit_color moved to _on_release
        # self._emit_color() 

    def _on_val_bar_interact(self, v):
        if self._block_signals: return
        # Обновляем только V
        h, s, _, a = self._qcolor.getHsv()
        if h < 0: h = 0
        new_color = QtGui.QColor.fromHsv(h, s, int(v), a)
        
        self._qcolor = new_color
        self._update_all_widgets()
        # self._emit_color() # Moved to release

    def _on_release(self):
        """Finalize color choice and emit to Blender."""
        if self._block_signals: return
        self._emit_color()
    # -------------------------------------------------------

    def set_color(self, color_data):
        """color_data: [r, g, b, a] floats or string"""
        if self._block_signals: return
        
        if not color_data:
            return

        self._block_signals = True
        try:
            if isinstance(color_data, str):
                self._qcolor.setNamedColor(color_data)
            elif isinstance(color_data, (list, tuple)):
                r, g, b = color_data[0], color_data[1], color_data[2]
                a = color_data[3] if len(color_data) > 3 else 1.0
                self._qcolor.setRgbF(r, g, b, a)
            
            # Use force_update to bypass internal block
            self._update_all_widgets(force=True)
        finally:
            self._block_signals = False

    def _update_all_widgets(self, force=False):
        if self._block_signals and not force: return
        was_blocked = self._block_signals
        self._block_signals = True
        try:
        
            # Update HEX
            self.edit_hex.setText(self._qcolor.name(QtGui.QColor.HexArgb).upper())
        
            # Get HSV data
            h, s, v, _ = self._qcolor.getHsv()
            if h < 0: h = 0 

            # Update HSV Sliders
            self.sl_h.set_value(h, emit_signal=False)
            self.sl_s.set_value(int(s / 255.0 * 100), emit_signal=False)
            self.sl_v.set_value(int(v / 255.0 * 100), emit_signal=False)
        
            # Update Alpha
            self.sl_a.set_value(self._qcolor.alphaF(), emit_signal=False)
            self._update_alpha_style()
        
            # Update Preview
            self.preview.set_color(self._qcolor)
            
            # Update Visual Pickers (Wheel & ValueBar)
            self.wheel.set_hs(float(h), float(s))
            self.val_bar.set_hsv(h, s, v)
        finally:
            self._block_signals = was_blocked

    def _update_alpha_style(self):
        col = self._qcolor
        r, g, b = col.red(), col.green(), col.blue()
        theme = get_current_theme()
        
        # Only update if colors changed to avoid lag
        style_key = f"a_slider_{r}_{g}_{b}"
        if getattr(self, "_last_alpha_style", "") == style_key:
            return
        self._last_alpha_style = style_key
        
        self.sl_a.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 transparent, stop:1 rgb({r},{g},{b}));
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {theme.get('accent', '#5298D4')};
                border-radius: 5px; 
                width: 10px;
                height: 10px;
                margin: -3px 0;
            }}
        """)

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
        self._block_signals = True
        h = self.sl_h.get_value()
        s = self.sl_s.get_value() / 100.0 * 255.0
        v = self.sl_v.get_value() / 100.0 * 255.0
        a = self._qcolor.alphaF()
        self._qcolor.setHsv(int(h), int(s), int(v), int(a * 255))
        
        # UI Sync
        self.preview.set_color(self._qcolor)
        self.edit_hex.setText(self._qcolor.name(QtGui.QColor.HexArgb).upper())
        self.wheel.set_hs(float(h), float(s))
        self.val_bar.set_hsv(h, s, int(v))
        self._update_alpha_style()
        
        self._block_signals = False
        # self._emit_color() # Moved to release

    def _on_alpha_changed(self, val):
        if self._block_signals: return
        self._block_signals = True
        self._qcolor.setAlphaF(val)
        self.preview.set_color(self._qcolor)
        self.edit_hex.setText(self._qcolor.name(QtGui.QColor.HexArgb).upper())
        self._update_alpha_style()
        self._block_signals = False
        # self._emit_color() # Moved to release

    def _emit_color(self):
        c = self._qcolor
        self.colorChanged.emit([c.redF(), c.greenF(), c.blueF(), c.alphaF()])

    def apply_theme(self):
        """Update styles for internal widgets that don't have their own apply_theme."""
        theme = get_current_theme()
        border_col = theme.get('border_input', '#444')
        # Preview style depends on current color, handled in _update_all_widgets
        self._update_all_widgets()

    def update_style(self):
        self.apply_theme()

# --- RZScrollArea (Smooth Scroll) ---
class SquishyScrollBar(QtWidgets.QScrollBar):
    """Кастомный скроллбар, который умеет визуально 'сжиматься'"""
    def __init__(self, parent=None):
        super().__init__(QtCore.Qt.Vertical, parent)
        self._squish_margin_top = 0
        self._squish_margin_bottom = 0

    def set_squish(self, offset):
        # offset > 0 значит тянем вниз (сжимается низ)
        # offset < 0 значит тянем вверх (сжимается верх)
        if offset > 0:
            self._squish_margin_bottom = offset
            self._squish_margin_top = 0
        elif offset < 0:
            self._squish_margin_top = abs(offset)
            self._squish_margin_bottom = 0
        else:
            self._squish_margin_top = 0
            self._squish_margin_bottom = 0
        self.update() # Перерисовываем скроллбар

    def paintEvent(self, event):
        # Отрисовываем стандартный скроллбар
        super().paintEvent(event)
        
        # Поверх стандартного поведения делаем визуальный хак:
        # Если есть squish, мы закрашиваем концы ползунка цветом фона, 
        # создавая иллюзию его сжатия.
        if self._squish_margin_top > 0 or self._squish_margin_bottom > 0:
            painter = QtGui.QPainter(self)
            opt = QtWidgets.QStyleOptionSlider()
            self.initStyleOption(opt)
            
            # Получаем геометрию самого ползунка (handle)
            handle_rect = self.style().subControlRect(
                QtWidgets.QStyle.CC_ScrollBar, opt, 
                QtWidgets.QStyle.SC_ScrollBarSlider, self
            )
            
            # Цвет фона скроллбара (чтобы "откусить" часть ползунка)
            # Замените на цвет вашего интерфейса, если он отличается
            bg_color = self.palette().color(QtGui.QPalette.Window)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(bg_color)
            
            # Отрезаем низ
            if self._squish_margin_bottom > 0:
                cut_rect = QtCore.QRect(
                    handle_rect.left(), 
                    handle_rect.bottom() - int(self._squish_margin_bottom) + 1,
                    handle_rect.width(), 
                    int(self._squish_margin_bottom)
                )
                painter.drawRect(cut_rect)
                
            # Отрезаем верх
            if self._squish_margin_top > 0:
                cut_rect = QtCore.QRect(
                    handle_rect.left(), 
                    handle_rect.top(),
                    handle_rect.width(), 
                    int(self._squish_margin_top)
                )
                painter.drawRect(cut_rect)


class RZScrollArea(QtWidgets.QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        # Устанавливаем наш кастомный скроллбар
        self.setVerticalScrollBar(SquishyScrollBar(self))
        self.verticalScrollBar().setSingleStep(20)
        
        self._target_y = 0
        self._current_y = 0
        
        # Таймер
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_physics)
        self._timer.setInterval(10) # 100 FPS
        
        # Анимация сжатия (Squish)
        self._squish_offset = 0
        self._squish_anim = QtCore.QVariantAnimation(self)
        self._squish_anim.setDuration(250) # Сделали чуть быстрее для динамики
        self._squish_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad) # Более естественный отскок
        self._squish_anim.valueChanged.connect(self._set_squish)

    def _set_squish(self, val):
        self._squish_offset = val
        if self.widget():
            # 1. Двигаем сам контент
            offset = int(self._squish_offset)
            self.widget().move(0, -self.verticalScrollBar().value() + offset)
            
            # 2. Передаем значение в скроллбар, чтобы он визуально сжался
            self.verticalScrollBar().set_squish(offset)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        bar = self.verticalScrollBar()
        
        if not self._timer.isActive():
            self._current_y = float(bar.value())
            self._target_y = self._current_y
            
        # Умножаем delta на коэффициент, чтобы скролл был более длинным за один "щелчок" колеса
        scroll_multiplier = 1.5 
        self._target_y -= (delta * scroll_multiplier)
        
        # Проверка границ для эффекта Squish
        squish_max_distance = 120 # Максимальная сила сжатия
        
        if self._target_y < -squish_max_distance:
            self._target_y = -squish_max_distance
            self._trigger_squish(50) # Сжимаем вверх
        elif self._target_y > bar.maximum() + squish_max_distance:
            self._target_y = bar.maximum() + squish_max_distance
            self._trigger_squish(-50) # Сжимаем вниз
            
        self._timer.start()
        event.accept()

    def _trigger_squish(self, amount):
        if self._squish_anim.state() == QtCore.QVariantAnimation.Running:
            return
        self._squish_anim.setStartValue(amount)
        self._squish_anim.setEndValue(0)
        self._squish_anim.start()

    def _update_physics(self):
        bar = self.verticalScrollBar()
        diff = self._target_y - self._current_y
        
        if abs(diff) < 0.5:
            self._current_y = self._target_y
            bar.setValue(int(self._current_y))
            self._timer.stop()
            return
            
        # ИСПРАВЛЕННАЯ ФИЗИКА:
        # Множитель 0.35 дает быструю, но плавную интерполяцию. 
        # Убрана странная константа +2.0, добавлена минимальная скорость (min_speed).
        step = diff * 0.35 
        
        # Гарантируем, что ползунок не будет бесконечно медленно ползти в конце
        if step > 0 and step < 1.0: step = 1.0
        elif step < 0 and step > -1.0: step = -1.0
            
        self._current_y += step
        
        # Защита от переполнения
        clamped_y = max(0, min(int(self._current_y), bar.maximum()))
        bar.setValue(clamped_y)
        
        # Обновляем позицию виджета во время скролла
        if self.widget() and not self._squish_anim.state() == QtCore.QVariantAnimation.Running:
             self.widget().move(0, -clamped_y)

# --- New RZCheckBox ---
class RZCheckBox(RZVisualInputMixin, QtWidgets.QCheckBox):
    def __init__(self, text="", parent=None, checked=False):
        super().__init__(text, parent)
        self._init_visuals()
        self._draw_border_enabled = False # Checkbox only wants indicator styling
        self.setChecked(checked)
        self.apply_theme()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        # For checkbox, we draw a smaller glow around the indicator if possible, 
        # or just the standard border if it's a full-width widget.
        self._draw_visual_border(painter)
        painter.end()
        
    def apply_theme(self):
        pass

# --- Existing Widgets ---

from .base import RZBaseWidget

class RZContextAwareWidget(RZBaseWidget):
    def __init__(self, area_name, parent=None):
        super().__init__(parent, area_name)
        self.setObjectName(f"RZContextWidget_{area_name}")

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
        pass

class RZGroupBox(QtWidgets.QGroupBox):
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.apply_theme()
    def apply_theme(self):
        pass

class RZPushButton(RZVisualInputMixin, QtWidgets.QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._init_visuals()
        self.apply_theme()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        painter.end()
    def apply_theme(self):
        pass

class RZLabel(QtWidgets.QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.apply_theme()
    def apply_theme(self):
        pass

class RZSpinBox(RZVisualInputMixin, QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_visuals()
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.apply_theme()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        painter.end()
    def apply_theme(self):
        pass
    def wheelEvent(self, event):
        event.ignore()

    def validate(self, input_text, pos):
        # Allow digits, arithmetic operators, parentheses, and spaces for formulas
        import re
        if re.fullmatch(r"[0-9.+\-*/() ]*", input_text):
            return (QtGui.QValidator.State.Intermediate, input_text, pos)
        return (QtGui.QValidator.State.Invalid, input_text, pos)

    def valueFromText(self, text):
        try:
            from ...utils.evaluation import safe_eval
            # If the user types a calculation, evaluate it
            val = safe_eval(text)
            if isinstance(val, (int, float)):
                return int(round(val))
        except Exception:
            # On calculation error (like 1/0), stay at current value
            return self.value()
        return super().valueFromText(text)

class RZDoubleSpinBox(RZVisualInputMixin, QtWidgets.QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_visuals()
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.apply_theme()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        painter.end()

    def apply_theme(self):
        pass
    def wheelEvent(self, event):
        event.ignore()

    def validate(self, input_text, pos):
        # Allow digits, arithmetic operators, parentheses, and spaces for formulas
        import re
        if re.fullmatch(r"[0-9.+\-*/() ]*", input_text):
            return (QtGui.QValidator.State.Intermediate, input_text, pos)
        return (QtGui.QValidator.State.Invalid, input_text, pos)

    def valueFromText(self, text):
        try:
            from ...utils.evaluation import safe_eval
            # If the user types a calculation, evaluate it
            val = safe_eval(text)
            if isinstance(val, (int, float)):
                return float(val)
        except Exception:
            # On calculation error (like 1/0), stay at current value
            return self.value()
        return super().valueFromText(text)

class RZStaggeredDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.progress = 0.0 # 0 to 1
        self.stagger_delay = 0.02 # dynamic
        self.item_fade_speed = 0.5 # relative to progress multiplier

    def paint(self, painter, option, index):
        row = index.row()
        # Increased timing multiplier (5.0) and faster fade to ensure ALL items animate
        current_time = self.progress * 5.0 
        start_time = row * self.stagger_delay
        local_progress = max(0.0, min(1.0, (current_time - start_time) / (self.item_fade_speed * 0.5)))
        
        if local_progress <= 0: return 
        painter.save()
        painter.setOpacity(local_progress)
        # Pronounced fall-down and horizontal slide-in
        offset_y = (1.0 - local_progress) * 15 # Increased from 10
        offset_x = (1.0 - local_progress) * 8  # Increased from 4
        painter.translate(offset_x, offset_y)
        super().paint(painter, option, index)
        painter.restore()

class RZComboBox(RZVisualInputMixin, QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_visuals()
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.apply_theme()
        
        self._delegate = RZStaggeredDelegate(self)
        self.setItemDelegate(self._delegate)
        
        self._popup_anim = QtCore.QPropertyAnimation(self, b"popup_progress")
        self._popup_anim.setDuration(400) 
        self._popup_anim.setEasingCurve(QtCore.QEasingCurve.Linear)

    @QtCore.Property(float)
    def popup_progress(self):
        return self._delegate.progress
        
    @popup_progress.setter
    def popup_progress(self, val):
        self._delegate.progress = val
        # Rayvich: FIXED "gray emptiness" bug for standard ComboBoxes too
        if self.view() and self.view().viewport():
            self.view().viewport().update()
        self.view().window().setWindowOpacity(min(1.0, val * 4))

    def showPopup(self):
        count = self.count()
        # Adaptive timings
        total_duration = 200 # 0.2s
        if count > 0:
            # We want the animation to be dense but legible
            # stagger_delay is in 'virtual time' (0 to 4)
            # Last item should start at some point and finish quickly
            self._delegate.stagger_delay = 4.0 / max(1, count + 2)
            self._delegate.item_fade_speed = 1.0 # 1/4 of total time
        
        self._popup_anim.stop()
        self._popup_anim.setDuration(total_duration)
        self._popup_anim.setStartValue(0.0)
        self._popup_anim.setEndValue(1.0)
        super().showPopup()
        self._popup_anim.start()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        painter.end()

    def apply_theme(self):
        pass
    def wheelEvent(self, event):
        event.ignore()

class RZLineEdit(RZVisualInputMixin, QtWidgets.QLineEdit):
    editingFinished = QtCore.Signal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_visuals()
        self.apply_theme()
        self._pattern = ""
        self._originals = []

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        painter.end()

    def wheelEvent(self, event):
        event.ignore()

    def apply_theme(self):
        pass

    def set_text_silent(self, text):
        """Update text without emitting signals and only if not focused."""
        if self.hasFocus():
            return
        if self.text() == text:
            return
            
        self.blockSignals(True)
        self.setText(str(text))
        self.blockSignals(False)

    def set_pattern(self, pattern, originals=None):
        self._pattern = pattern
        self._originals = originals or []
        # Use silent update for pattern too
        self.set_text_silent(pattern)
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