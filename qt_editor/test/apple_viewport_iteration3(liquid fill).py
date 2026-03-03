import sys
import os
import math
from PySide6 import QtWidgets, QtCore, QtGui

# --- КОНСТАНТЫ СТИЛЯ ---
APPLE_BLUE = QtGui.QColor(0, 122, 255)
APPLE_BG = QtGui.QColor(245, 245, 247)
SHADOW_COLOR = QtGui.QColor(0, 0, 0, 40)

# --- ГЕНЕРАТОР КАРТИНОК (Чтобы работало без файлов) ---
def get_pixmap(name):
    # 1. Пробуем найти файл рядом со скриптом
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, name)
    if os.path.exists(path):
        return QtGui.QPixmap(path)
    
    # 2. Если нет — генерируем красивую заглушку
    pix = QtGui.QPixmap(300, 300)
    pix.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pix)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    
    # Скругленный квадрат
    path = QtGui.QPainterPath()
    path.addRoundedRect(10, 10, 280, 280, 40, 40)
    
    # Цвет от имени
    hue = (hash(name) % 360)
    color1 = QtGui.QColor.fromHsl(hue, 200, 240)
    color2 = QtGui.QColor.fromHsl((hue + 40) % 360, 220, 210)
    
    grad = QtGui.QLinearGradient(0, 0, 300, 300)
    grad.setColorAt(0, color1)
    grad.setColorAt(1, color2)
    
    painter.setBrush(QtGui.QBrush(grad))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawPath(path)
    
    # Текст
    painter.setPen(QtGui.QColor(255, 255, 255, 200))
    font = painter.font()
    font.setPointSize(40)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pix.rect(), QtCore.Qt.AlignCenter, name.replace(".png", ""))
    painter.end()
    return pix

# --- ФИЗИКА ВЕРШИН ---
class PhysicsPoint:
    def __init__(self, x, y):
        self.target = QtCore.QPointF(x, y) # Куда хочет вернуться
        self.pos = QtCore.QPointF(x, y)    # Где сейчас
        self.velocity = QtCore.QPointF(0, 0)
        # Настройки "картона" (жесткий, быстро успокаивается)
        self.stiffness = 0.25 
        self.damping = 0.65   

    def update(self):
        # F = -kx
        dx = self.target.x() - self.pos.x()
        dy = self.target.y() - self.pos.y()
        
        self.velocity.setX(self.velocity.x() * self.damping + dx * self.stiffness)
        self.velocity.setY(self.velocity.y() * self.damping + dy * self.stiffness)
        
        self.pos.setX(self.pos.x() + self.velocity.x())
        self.pos.setY(self.pos.y() + self.velocity.y())
        
        # True если еще движется
        return (abs(dx) > 0.1 or abs(dy) > 0.1 or 
                abs(self.velocity.x()) > 0.1 or abs(self.velocity.y()) > 0.1)

# --- ПРИЕМНИК (SMART NODE) ---
class SmartNode(QtWidgets.QGraphicsObject):
    def __init__(self, x, y, w, h):
        super().__init__()
        self._w = w
        self._h = h
        self.setPos(x, y)
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemClipsChildrenToShape, True)

        # Внутренний контейнер для картинки
        self._image_item = QtWidgets.QGraphicsPixmapItem(self)
        self._image_item.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self._image_item.setOpacity(0.0) # Скрыт
        
        # Переменная анимации (0.0 -> 1.0)
        self._fill_factor = 0.0 
        
        # Тень
        self._shadow = QtWidgets.QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(20)
        self._shadow.setColor(SHADOW_COLOR)
        self._shadow.setOffset(0, 8)
        self.setGraphicsEffect(self._shadow)
        
        # Аниматор
        self._anim = QtCore.QVariantAnimation()
        self._anim.setDuration(250)
        self._anim.valueChanged.connect(self._on_anim_val)

    def boundingRect(self):
        return QtCore.QRectF(-5, -5, self._w + 10, self._h + 10)
    
    def shape(self):
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, self._w, self._h, 24, 24)
        return path

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        path = self.shape()
        
        # Фон
        painter.setBrush(QtGui.QColor(255, 255, 255))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawPath(path)
        
        # Обводка
        if self._fill_factor > 0.01:
            # Синяя подсветка при наведении
            pen = QtGui.QPen(APPLE_BLUE, 3 * self._fill_factor)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawPath(path)
        else:
            # Обычная рамка
            painter.setPen(QtGui.QPen(QtGui.QColor(220, 220, 230), 1.5))
            painter.drawPath(path)

    def preview_pixmap(self, pixmap, active):
        """Включает/выключает превью заливки."""
        if active:
            # Центрируем картинку (Aspect Fill)
            self._image_item.setPixmap(pixmap)
            scale = max(self._w / pixmap.width(), self._h / pixmap.height())
            self._image_item.setScale(scale)
            dx = (self._w - pixmap.width()*scale) / 2
            dy = (self._h - pixmap.height()*scale) / 2
            self._image_item.setPos(dx, dy)
            
            # Анимация ВХОДА
            self._anim.stop()
            self._anim.setStartValue(self._fill_factor)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            self._anim.start()
        else:
            # Анимация ВЫХОДА
            self._anim.stop()
            self._anim.setStartValue(self._fill_factor)
            self._anim.setEndValue(0.0)
            self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            self._anim.start()

    def _on_anim_val(self, val):
        self._fill_factor = val
        self._image_item.setOpacity(val)
        
        # Эффект зума: картинка "всплывает" (1.1 -> 1.0)
        zoom = 1.15 - (0.15 * val)
        # Центр трансформации для скейла изображения сложно менять на лету у PixmapItem,
        # поэтому упростим: просто Opacity и рамка. Это уже выглядит круто.
        
        self.update() # Перерисовка рамки

    def commit(self):
        """Оставляет картинку навсегда."""
        self._fill_factor = 0.0 # Рамка гаснет
        self._image_item.setOpacity(1.0) # Картинка остается
        self.update()


# --- БУМАЖКА (ИСТОЧНИК) ---
class DraggablePaper(QtWidgets.QGraphicsObject):
    def __init__(self, x, y, w, h, img_name):
        super().__init__()
        self.setPos(x, y)
        self._w = w
        self._h = h
        self._pixmap = get_pixmap(img_name)
        
        self.setAcceptHoverEvents(True)
        # ВАЖНО: Мы НЕ ставим ItemIsMovable, мы пишем свою логику драга,
        # чтобы иметь полный контроль над физикой вершин.
        
        # Физика вершин
        self.corners = [
            PhysicsPoint(0, 0), PhysicsPoint(w, 0),
            PhysicsPoint(w, h), PhysicsPoint(0, h)
        ]
        
        # Состояние
        self._is_dragging = False
        self._last_scene_pos = QtCore.QPointF()
        self._target_node = None # Над чем мы сейчас висим
        self._absorb_val = 0.0   # 0 - видно, 1 - прозрачная (влилась)
        
        # Таймер анимации (60 FPS)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._update_physics)
        
        # Тень
        self._shadow = QtWidgets.QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(15)
        self._shadow.setColor(SHADOW_COLOR)
        self._shadow.setOffset(0, 4)
        self.setGraphicsEffect(self._shadow)
        
        # Аниматор растворения (Absorb)
        self._anim_absorb = QtCore.QVariantAnimation()
        self._anim_absorb.setDuration(200)
        self._anim_absorb.valueChanged.connect(self._set_absorb)

    def boundingRect(self):
        # Огромный запас для вершин, которые отстают
        return QtCore.QRectF(-100, -100, self._w+200, self._h+200)

    def paint(self, painter, option, widget):
        if self._absorb_val > 0.99: return # Полностью невидима

        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        painter.setOpacity(1.0 - self._absorb_val)
        
        # Строим форму
        poly = QtGui.QPolygonF()
        for p in self.corners: poly.append(p.pos)
            
        path = QtGui.QPainterPath()
        path.addPolygon(poly)
        
        painter.setClipPath(path)
        
        # Рисуем контент (картинку)
        painter.drawPixmap(0, 0, self._w, self._h, self._pixmap)
        
        # Блик (Gloss)
        grad = QtGui.QLinearGradient(0, 0, 0, self._h)
        grad.setColorAt(0, QtGui.QColor(255, 255, 255, 60))
        grad.setColorAt(1, QtGui.QColor(255, 255, 255, 0))
        painter.fillPath(path, QtGui.QBrush(grad))
        
        # Тонкая обводка
        painter.setPen(QtGui.QPen(QtGui.QColor(0,0,0, 30), 1))
        painter.drawPath(path)

    def _update_physics(self):
        moved = False
        for p in self.corners:
            if p.update(): moved = True
        self.update()
        # Выключаем таймер, если все успокоилось и мы не тащим
        if not moved and not self._is_dragging:
            self._timer.stop()

    # --- СОБЫТИЯ МЫШИ (ГЛАВНАЯ МАГИЯ) ---

    def mousePressEvent(self, event):
        # 1. Захват
        self._is_dragging = True
        self._last_scene_pos = event.scenePos()
        self.setZValue(1000) # Поверх всего
        self.setCursor(QtCore.Qt.ClosedHandCursor)
        
        # 2. Визуальный отклик (Подъем)
        self._shadow.setBlurRadius(40)
        self._shadow.setOffset(0, 20)
        self.setScale(1.05)
        
        # 3. Физика становится жестче (мы держим бумагу)
        for p in self.corners: 
            p.stiffness = 0.5
            p.damping = 0.5
            
        self._timer.start()
        event.accept() # ВАЖНО: Не даем вьюпорту украсть событие

    def mouseMoveEvent(self, event):
        if not self._is_dragging: return

        # 1. Считаем дельту в мировых координатах
        current_scene_pos = event.scenePos()
        delta = current_scene_pos - self._last_scene_pos
        self._last_scene_pos = current_scene_pos
        
        # 2. Двигаем сам объект
        self.setPos(self.pos() + delta)
        
        # 3. Эффект инерции (вершины отстают)
        # Смещаем визуальные точки ПРОТИВ движения
        for p in self.corners:
            p.pos -= delta * 0.7 # Коэффициент отставания
            
        # 4. Проверка коллизий (Smart Node)
        # Берем центр объекта в сцене
        center = self.mapToScene(self._w/2, self._h/2)
        items = self.scene().items(center)
        
        found_node = None
        for it in items:
            if isinstance(it, SmartNode):
                found_node = it
                break
        
        # Логика входа/выхода
        if found_node != self._target_node:
            if self._target_node:
                self._target_node.preview_pixmap(None, False)
                self._animate_absorb(False) # Вытащить
            
            if found_node:
                found_node.preview_pixmap(self._pixmap, True)
                self._animate_absorb(True) # Всунуть
            
            self._target_node = found_node
            
        event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        self.setCursor(QtCore.Qt.OpenHandCursor)
        
        # Если отпустили над нодой -> COMMIT
        if self._target_node:
            self._target_node.commit()
            self.scene().removeItem(self) # Удаляем себя
            return
            
        # Иначе -> ВОЗВРАТ НА СТОЛ
        self.setZValue(0)
        self.setScale(1.0)
        self._shadow.setBlurRadius(15)
        self._shadow.setOffset(0, 4)
        
        # Расслабляем физику
        for p in self.corners:
            p.stiffness = 0.25
            p.damping = 0.65
            
        event.accept()

    def hoverEnterEvent(self, event):
        self.setCursor(QtCore.Qt.OpenHandCursor)
        self.setScale(1.02)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.setScale(1.0)
        super().hoverLeaveEvent(event)

    # --- АНИМАЦИЯ ПОГЛОЩЕНИЯ ---
    def _animate_absorb(self, entering):
        self._anim_absorb.stop()
        if entering:
            self._anim_absorb.setStartValue(self._absorb_val)
            self._anim_absorb.setEndValue(1.0)
            self._anim_absorb.setEasingCurve(QtCore.QEasingCurve.InQuad)
        else:
            # Эффект "чпоньк" при вытаскивании
            self._anim_absorb.setStartValue(self._absorb_val)
            self._anim_absorb.setEndValue(0.0)
            self._anim_absorb.setEasingCurve(QtCore.QEasingCurve.OutBack)
        self._anim_absorb.start()

    def _set_absorb(self, val):
        self._absorb_val = val
        # При поглощении бумажка уменьшается в точку
        s = 1.05 * (1.0 - 0.4 * val)
        self.setScale(s)
        self.update()


# --- VIEWPORT ---
class MagicView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        # ВАЖНО: RubberBandDrag иногда мешает кастомному драгу, если не аккуратно.
        # Но с event.accept() в айтеме проблем быть не должно.
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        
        self.setBackgroundBrush(QtGui.QBrush(APPLE_BG))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def wheelEvent(self, event):
        # Zoom
        factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1
        self.scale(factor, factor)

# --- MAIN ---
class AppleMagicWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RZMenu: Liquid Drag & Drop")
        self.resize(1200, 800)
        
        self.scene = QtWidgets.QGraphicsScene(-2000, -2000, 4000, 4000)
        self.view = MagicView()
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)
        
        self.setup_scene()

    def setup_scene(self):
        # Инструкция
        txt = self.scene.addText("Перетащи картинки в квадраты")
        txt.setScale(3)
        txt.setPos(200, -150)
        txt.setDefaultTextColor(QtGui.QColor(0,0,0, 100))

        # Создаем слоты (Ноды)
        for i in range(3):
            node = SmartNode(i * 350, 50, 280, 280)
            self.scene.addItem(node)

        # Создаем бумажки
        # Даже если файлов нет, оно сгенерит красивые цветные
        names = ["render_01.png", "texture_map.png", "ref_image.png"]
        for i, name in enumerate(names):
            paper = DraggablePaper(i * 320, 450, 200, 200, name)
            self.scene.addItem(paper)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = AppleMagicWindow()
    window.show()
    sys.exit(app.exec())