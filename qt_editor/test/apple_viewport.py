import sys
import os
import math
from PySide6 import QtWidgets, QtCore, QtGui, QtMultimedia

# --- КОНФИГУРАЦИЯ ---
ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))

# Цвета
C_BG = QtGui.QColor(245, 245, 247)
C_TEXT_PRI = QtGui.QColor(29, 29, 31)
C_TEXT_SEC = QtGui.QColor(134, 134, 139)
C_ACCENT = QtGui.QColor(0, 122, 255)
C_ACCENT_HOVER = QtGui.QColor(0, 110, 230)

# Шрифты
FONT_TITLE = QtGui.QFont("Segoe UI", 16, QtGui.QFont.Bold)
FONT_DESC = QtGui.QFont("Consolas", 10)
FONT_DESC.setStyleHint(QtGui.QFont.Monospace)

# --- АУДИО ДВИЖОК ---
class SoundEngine:
    """Простой менеджер звуков, чтобы они не собирались мусорщиком."""
    _players = []

    @classmethod
    def play(cls, filename):
        path = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(path):
            print(f"[Audio] File not found: {filename}")
            return

        # QMediaPlayer в PySide6 требует AudioOutput
        player = QtMultimedia.QMediaPlayer()
        audio_output = QtMultimedia.QAudioOutput()
        player.setAudioOutput(audio_output)
        player.setSource(QtCore.QUrl.fromLocalFile(path))
        audio_output.setVolume(0.8)
        
        # Удаляем плеер после окончания, чтобы не текла память
        player.mediaStatusChanged.connect(lambda status: cls._cleanup(player, status))
        
        cls._players.append(player) # Держим ссылку
        player.play()

    @classmethod
    def _cleanup(cls, player, status):
        if status == QtMultimedia.QMediaPlayer.EndOfMedia:
            if player in cls._players:
                cls._players.remove(player)
            player.deleteLater()

# --- БАЗОВЫЙ КЛАСС ЭКСПОНАТА (Museum Exhibit) ---
class MuseumExhibit(QtWidgets.QGraphicsObject):
    """
    Рамка, пьедестал и описание для демонстрации элемента.
    """
    def __init__(self, title, description, width=400, height=500):
        super().__init__()
        self._w = width
        self._h = height
        self._title = title
        self._desc = description.strip()
        
        # Фон пьедестала
        self._bg_brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        self._shadow = QtWidgets.QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(30)
        self._shadow.setColor(QtGui.QColor(0, 0, 0, 20))
        self._shadow.setOffset(0, 10)
        self.setGraphicsEffect(self._shadow)

    def boundingRect(self):
        return QtCore.QRectF(0, 0, self._w, self._h)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Пьедестал
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, self._w, self._h, 24, 24)
        painter.setBrush(self._bg_brush)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawPath(path)
        
        # Заголовок
        painter.setPen(C_TEXT_PRI)
        painter.setFont(FONT_TITLE)
        painter.drawText(QtCore.QRectF(20, 20, self._w-40, 40), QtCore.Qt.AlignLeft, self._title)
        
        # Описание (код/методы)
        painter.setPen(C_TEXT_SEC)
        painter.setFont(FONT_DESC)
        rect_desc = QtCore.QRectF(20, 350, self._w-40, self._h-350)
        painter.drawText(rect_desc, QtCore.Qt.AlignLeft | QtCore.Qt.TextWordWrap, self._desc)
        
        # Разделитель
        painter.setPen(QtGui.QPen(QtGui.QColor(0,0,0, 20), 1))
        painter.drawLine(20, 330, self._w-20, 330)


# ==========================================
# ЭКСПОНАТ 1: Пружинная Кнопка (Spring Physics)
# ==========================================

class AppleButton(QtWidgets.QGraphicsObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptHoverEvents(True)
        self._rect = QtCore.QRectF(-80, -25, 160, 50)
        self._scale = 1.0
        
        # Анимация скейла
        self._anim = QtCore.QPropertyAnimation(self, b"scale_prop", self)
        self._anim.setDuration(400)

    def boundingRect(self): return self._rect.adjusted(-10,-10,10,10)
    
    # Property для анимации
    def get_scale(self): return self._scale
    def set_scale(self, s):
        self._scale = s
        self.setScale(s)
    scale_prop = QtCore.Property(float, get_scale, set_scale)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Градиент iOS
        grad = QtGui.QLinearGradient(0, -25, 0, 25)
        grad.setColorAt(0, C_ACCENT)
        grad.setColorAt(1, C_ACCENT_HOVER)
        
        path = QtGui.QPainterPath()
        path.addRoundedRect(self._rect, 25, 25)
        
        painter.setBrush(grad)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawPath(path)
        
        painter.setPen(QtCore.Qt.white)
        painter.setFont(QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold))
        painter.drawText(self._rect, QtCore.Qt.AlignCenter, "Click Me")

    def mousePressEvent(self, event):
        SoundEngine.play("effect_click.mp3")
        self._anim.stop()
        self._anim.setEndValue(0.9) # Сжатие
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        self._anim.start()

    def mouseReleaseEvent(self, event):
        self._anim.stop()
        self._anim.setEndValue(1.0)
        # QEasingCurve.OutBack - это и есть магия пружины (overshoot)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutBack) 
        self._anim.start()

    def hoverEnterEvent(self, event):
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._anim.setEndValue(1.05) # Легкое увеличение
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        self._anim.start()
        
    def hoverLeaveEvent(self, event):
        self.setCursor(QtCore.Qt.ArrowCursor)
        self._anim.setEndValue(1.0)
        self._anim.start()


# ==========================================
# ЭКСПОНАТ 2: Магнитный Слайдер (Haptics)
# ==========================================

class MagneticSlider(QtWidgets.QGraphicsObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._width = 200
        self._val = 0.0 # 0.0 to 1.0
        self._dragging = False
        
        # Магнитные точки (ticks)
        self.ticks = [0.0, 0.5, 1.0] 

    def boundingRect(self): return QtCore.QRectF(-10, -20, self._width+20, 40)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Трек
        painter.setBrush(QtGui.QColor(220, 220, 220))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(0, -4, self._width, 8, 4, 4)
        
        # Заполненная часть
        fill_w = self._width * self._val
        painter.setBrush(C_ACCENT)
        painter.drawRoundedRect(0, -4, fill_w, 8, 4, 4)
        
        # Ручка (Handle) with shadow
        handle_x = fill_w
        
        # Тень ручки
        painter.setBrush(QtGui.QColor(0,0,0, 30))
        painter.drawEllipse(QtCore.QPointF(handle_x, 2), 14, 14)
        
        # Сама ручка
        painter.setBrush(QtCore.Qt.white)
        painter.drawEllipse(QtCore.QPointF(handle_x, 0), 14, 14)
        
        # Магнитные точки визуально
        painter.setBrush(QtGui.QColor(0,0,0, 50))
        for t in self.ticks:
            cx = t * self._width
            painter.drawEllipse(QtCore.QPointF(cx, 0), 2, 2)

    def mousePressEvent(self, event):
        self._dragging = True
        self.update_val(event.pos().x())

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.update_val(event.pos().x())

    def mouseReleaseEvent(self, event):
        self._dragging = False
        # Финальный "Чпоньк" если отпустили на магните
        SoundEngine.play("effect_zatuhanya.mp3") 

    def update_val(self, x_pos):
        raw_val = max(0.0, min(1.0, x_pos / self._width))
        
        # Магнитная логика
        snapped = False
        for tick in self.ticks:
            if abs(raw_val - tick) < 0.05: # Зона магнита 5%
                if abs(self._val - tick) > 0.001: # Если только что примагнитились
                     # Можно добавить микро-анимацию ручки тут
                     pass
                raw_val = tick
                snapped = True
                break
        
        self._val = raw_val
        self.update()


# ==========================================
# ЭКСПОНАТ 3: Жидкая Бумага (Liquid Morph)
# ==========================================
# (Упрощенная версия того кода для музея)

class LiquidPaperEx(QtWidgets.QGraphicsObject):
    def __init__(self, img_name, parent=None):
        super().__init__(parent)
        path = os.path.join(ASSETS_DIR, img_name)
        if os.path.exists(path):
            self.pixmap = QtGui.QPixmap(path)
        else:
            self.pixmap = QtGui.QPixmap(100, 100)
            self.pixmap.fill(C_ACCENT)
            
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable | QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        
        self._scale = 1.0
        self._shadow_blur = 10
        self._shadow_offset = 3

        # Тень
        self._shadow = QtWidgets.QGraphicsDropShadowEffect()
        self._shadow.setColor(QtGui.QColor(0,0,0,60))
        self._shadow.setBlurRadius(10)
        self._shadow.setOffset(0, 3)
        self.setGraphicsEffect(self._shadow)
        
        # Аниматор
        self._anim = QtCore.QPropertyAnimation(self, b"geometry_prop", self)
        self._anim.setDuration(300)

    def boundingRect(self): return QtCore.QRectF(0, 0, 100, 100)
    
    # Свойство для анимации сразу скейла и тени
    def get_geom(self): return self._scale
    def set_geom(self, s):
        self._scale = s
        self.setScale(s)
        # Тень меняется вместе со скейлом (иллюзия высоты)
        self._shadow.setBlurRadius(10 + (s-1.0)*100) 
        self._shadow.setOffset(0, 3 + (s-1.0)*20)
    geometry_prop = QtCore.Property(float, get_geom, set_geom)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, 100, 100, 10, 10)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, 100, 100, self.pixmap)
        
        # Глянец
        grad = QtGui.QLinearGradient(0, 0, 0, 100)
        grad.setColorAt(0, QtGui.QColor(255, 255, 255, 50))
        grad.setColorAt(1, QtGui.QColor(255, 255, 255, 0))
        painter.fillPath(path, grad)

    def mousePressEvent(self, event):
        self._anim.stop()
        self._anim.setEndValue(1.15)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutBack)
        self._anim.start()
        self.setZValue(100)
        self.setCursor(QtCore.Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        SoundEngine.play("effect_zatuhanya.mp3") # Звук "броска"
        self._anim.stop()
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutBounce) # Отскок при падении
        self._anim.start()
        self.setZValue(0)
        self.setCursor(QtCore.Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)
        
    def hoverEnterEvent(self, event):
        self.setCursor(QtCore.Qt.OpenHandCursor)
        super().hoverEnterEvent(event)

# ==========================================
# ЭКСПОНАТ 4: iOS Toggle Switch (Transition)
# ==========================================

class AppleSwitch(QtWidgets.QGraphicsObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on = False
        self._pos = 0.0 # 0.0 left, 1.0 right
        
        self._anim = QtCore.QPropertyAnimation(self, b"pos_prop", self)
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QtCore.QEasingCurve.InOutQuad)

    def boundingRect(self): return QtCore.QRectF(0, 0, 60, 36)
    
    def get_pos(self): return self._pos
    def set_pos(self, p):
        self._pos = p
        self.update()
    pos_prop = QtCore.Property(float, get_pos, set_pos)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Фон интерполируется от Серого к Зеленому/Синему
        c_off = QtGui.QColor(233, 233, 234)
        c_on = QtGui.QColor(52, 199, 89) # Apple Green
        
        r = self._pos
        curr_bg = QtGui.QColor(
            c_off.red() + (c_on.red()-c_off.red())*r,
            c_off.green() + (c_on.green()-c_off.green())*r,
            c_off.blue() + (c_on.blue()-c_off.blue())*r
        )
        
        painter.setBrush(curr_bg)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(0, 0, 60, 36, 18, 18)
        
        # Круг (Knob)
        # Сдвиг от 2 до 26 (60-34 = 26)
        knob_x = 2 + (24 * self._pos)
        
        # Тень круга
        painter.setBrush(QtGui.QColor(0,0,0, 40))
        painter.drawEllipse(knob_x, 4, 32, 32)
        
        painter.setBrush(QtCore.Qt.white)
        painter.drawEllipse(knob_x, 2, 32, 32)

    def mousePressEvent(self, event):
        self._on = not self._on
        self._anim.stop()
        self._anim.setEndValue(1.0 if self._on else 0.0)
        self._anim.start()
        
        if self._on:
             SoundEngine.play("effect_apply.mp3")
        else:
             SoundEngine.play("effect_click.mp3")


# ==========================================
# MAIN WINDOW & SCENE
# ==========================================

class MuseumScene(QtWidgets.QGraphicsScene):
    def __init__(self):
        super().__init__(0, 0, 1600, 1000)
        self.setBackgroundBrush(C_BG)

class MuseumView(QtWidgets.QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform | QtGui.QPainter.TextAntialiasing)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        # Отключаем скроллбары для чистоты
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def wheelEvent(self, event):
        # Apple Zoom
        factor = 1.05 if event.angleDelta().y() > 0 else 0.95
        self.scale(factor, factor)


class AppleMuseumWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RZMenu: The Museum of Qt Magic")
        self.resize(1400, 900)
        
        self.scene = MuseumScene()
        self.view = MuseumView(self.scene)
        self.setCentralWidget(self.view)
        
        self.setup_exhibits()

    def setup_exhibits(self):
        # Grid layout logic
        col_width = 450
        row_height = 550
        
        # --- EXHIBIT 1: BUTTON ---
        desc_1 = (
            "CLASS: AppleButton(QGraphicsObject)\n"
            "-----------------------------------\n"
            "PARAM: QEasingCurve.OutBack\n"
            "METHOD: QPropertyAnimation(scale)\n"
            "\n"
            "Демонстрирует 'Overshoot' эффект.\n"
            "При нажатии сжимается (OutQuad),\n"
            "при отпускании 'выстреливает' (OutBack).\n"
            "Аудио: effect_click.mp3"
        )
        ex1 = MuseumExhibit("01. Spring Physics", desc_1)
        ex1.setPos(50, 50)
        self.scene.addItem(ex1)
        
        btn = AppleButton(ex1)
        btn.setPos(200, 150) # Центр экспоната


        # --- EXHIBIT 2: LIQUID DRAG ---
        desc_2 = (
            "CLASS: LiquidPaperEx\n"
            "-----------------------------------\n"
            "PARAM: Shadow Blur + Offset + Scale\n"
            "EVENT: mousePress / mouseRelease\n"
            "\n"
            "Симуляция подъема объекта по оси Z.\n"
            "Тень размывается и смещается.\n"
            "Объект увеличивается (Scale > 1.0).\n"
            "Аудио: effect_zatuhanya.mp3"
        )
        ex2 = MuseumExhibit("02. Depth & Elevation", desc_2)
        ex2.setPos(50 + col_width, 50)
        self.scene.addItem(ex2)
        
        paper = LiquidPaperEx("0.png", ex2)
        paper.setPos(150, 100)


        # --- EXHIBIT 3: MAGNETIC SLIDER ---
        desc_3 = (
            "CLASS: MagneticSlider\n"
            "-----------------------------------\n"
            "METHOD: update_val(x_pos)\n"
            "LOGIC: if abs(val - tick) < 0.05\n"
            "\n"
            "Визуальный Haptics.\n"
            "При перетаскивании 'прилипает' к\n"
            "точкам 0.0, 0.5, 1.0.\n"
            "Реализовано чисто математически в коде."
        )
        ex3 = MuseumExhibit("03. Magnetic Snapping", desc_3)
        ex3.setPos(50 + col_width*2, 50)
        self.scene.addItem(ex3)
        
        slider = MagneticSlider(ex3)
        slider.setPos(100, 150)


        # --- EXHIBIT 4: COLOR MORPH ---
        desc_4 = (
            "CLASS: AppleSwitch\n"
            "-----------------------------------\n"
            "PARAM: QColor interpolation\n"
            "METHOD: lerp(color_A, color_B, t)\n"
            "\n"
            "Плавная интерполяция цвета (Lerp).\n"
            "Никаких картинок, всё рисуется кодом.\n"
            "Аудио: effect_apply.mp3 (On)"
        )
        ex4 = MuseumExhibit("04. Color Interpolation", desc_4)
        ex4.setPos(50, 50 + row_height)
        self.scene.addItem(ex4)
        
        switch = AppleSwitch(ex4)
        switch.setPos(170, 130)


        # --- EXHIBIT 5: TEXT & INFO ---
        desc_5 = (
            "QT CAPABILITIES:\n"
            "1. Sub-pixel rendering (Antialiasing)\n"
            "2. Hardware Accelerated Scene\n"
            "3. Audio Engine (QMultimedia)\n"
            "4. Vector Graphics (QPainterPath)\n"
            "\n"
            "Вся эта сцена — один виджет.\n"
            "Работает внутри Blender как родное окно."
        )
        ex5 = MuseumExhibit("05. System Capabilities", desc_5)
        ex5.setPos(50 + col_width, 50 + row_height)
        self.scene.addItem(ex5)
        
        # Просто красивая иконка Qt
        icon = QtWidgets.QGraphicsTextItem("Qt 6", ex5)
        font = QtGui.QFont("Segoe UI", 40, QtGui.QFont.Bold)
        icon.setFont(font)
        icon.setDefaultTextColor(QtGui.QColor(65, 205, 82))
        icon.setPos(140, 100)
        
        # Intro Text
        intro = self.scene.addText("RZMenu: The Apple UX Museum")
        f = QtGui.QFont("Segoe UI", 32, QtGui.QFont.Bold)
        intro.setFont(f)
        intro.setDefaultTextColor(QtGui.QColor(0,0,0, 150))
        intro.setPos(50, -80)


if __name__ == "__main__":
    # Фикс для High DPI
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    app = QtWidgets.QApplication(sys.argv)
    window = AppleMuseumWindow()
    window.show()
    sys.exit(app.exec())