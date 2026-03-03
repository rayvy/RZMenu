import sys
import math
from PySide6 import QtWidgets, QtCore, QtGui

# --- КОНСТАНТЫ СТИЛЯ ---
APPLE_BLUE = QtGui.QColor(0, 122, 255)
APPLE_BG = QtGui.QColor(245, 245, 247)
ITEM_GRADIENT_1 = QtGui.QColor(255, 255, 255, 255)
ITEM_GRADIENT_2 = QtGui.QColor(240, 240, 250, 255)
SHADOW_COLOR = QtGui.QColor(0, 0, 0, 60)

class AppleNode(QtWidgets.QGraphicsObject):
    """
    Элемент с физикой. Исправлена ошибка с анимациями.
    """
    def __init__(self, x, y, w, h):
        super().__init__()
        self._width = w
        self._height = h
        self.setPos(x, y)
        
        # Нативные флаги Qt для перемещения (дают максимальную скорость)
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemIsMovable |
            QtWidgets.QGraphicsItem.ItemIsSelectable |
            QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        
        # Внутренние переменные свойств
        self._anim_scale = 1.0
        self._shadow_blur = 15.0
        self._shadow_offset = 5.0
        
        # Эффект тени
        self._shadow = QtWidgets.QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(self._shadow_blur)
        self._shadow.setOffset(0, self._shadow_offset)
        self._shadow.setColor(SHADOW_COLOR)
        self.setGraphicsEffect(self._shadow)
        
        # --- ИНИЦИАЛИЗАЦИЯ АНИМАЦИЙ (ОДИН РАЗ) ---
        self._anim_group = QtCore.QParallelAnimationGroup(self)
        
        # Анимация масштаба
        self._a_scale = QtCore.QPropertyAnimation(self, b"anim_scale", self)
        self._a_scale.setDuration(300)
        
        # Анимация размытия тени
        self._a_blur = QtCore.QPropertyAnimation(self, b"anim_shadow_blur", self)
        self._a_blur.setDuration(300)
        
        # Анимация смещения тени
        self._a_offset = QtCore.QPropertyAnimation(self, b"anim_shadow_offset", self)
        self._a_offset.setDuration(300)
        
        # Добавляем в группу один раз и навсегда
        self._anim_group.addAnimation(self._a_scale)
        self._anim_group.addAnimation(self._a_blur)
        self._anim_group.addAnimation(self._a_offset)

    # --- PROPERTIES (Свойства для Qt Animation System) ---

    def get_anim_scale(self): return self._anim_scale
    def set_anim_scale(self, s):
        self._anim_scale = s
        # Важно: меняем точку трансформации в центр перед скейлом
        self.setTransformOriginPoint(self._width/2, self._height/2)
        self.setScale(s)
    anim_scale = QtCore.Property(float, get_anim_scale, set_anim_scale)

    def get_shadow_blur(self): return self._shadow_blur
    def set_shadow_blur(self, b):
        self._shadow_blur = b
        self._shadow.setBlurRadius(b)
    anim_shadow_blur = QtCore.Property(float, get_shadow_blur, set_shadow_blur)

    def get_shadow_offset(self): return self._shadow_offset
    def set_shadow_offset(self, o):
        self._shadow_offset = o
        self._shadow.setYOffset(o)
    anim_shadow_offset = QtCore.Property(float, get_shadow_offset, set_shadow_offset)

    # --- ОТРИСОВКА ---

    def boundingRect(self):
        return QtCore.QRectF(-2, -2, self._width + 4, self._height + 4)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, self._width, self._height, 16, 16)

        grad = QtGui.QLinearGradient(0, 0, 0, self._height)
        grad.setColorAt(0, ITEM_GRADIENT_1)
        grad.setColorAt(1, ITEM_GRADIENT_2)

        painter.setBrush(QtGui.QBrush(grad))
        
        if self.isSelected():
            painter.setPen(QtGui.QPen(APPLE_BLUE, 2))
        else:
            painter.setPen(QtGui.QPen(QtGui.QColor(200, 200, 200), 1))
            
        painter.drawPath(path)

    # --- СОБЫТИЯ И МАГИЯ ---

    def run_animation(self, t_scale, t_blur, t_offset, easing=QtCore.QEasingCurve.OutBack):
        """Перезапускаем анимацию с новыми целями, не пересоздавая объекты."""
        self._anim_group.stop()
        
        # Обновляем конечные значения
        self._a_scale.setEndValue(t_scale)
        self._a_scale.setEasingCurve(easing)
        
        self._a_blur.setEndValue(t_blur)
        self._a_blur.setEasingCurve(QtCore.QEasingCurve.OutQuad) # Тень линейнее
        
        self._a_offset.setEndValue(t_offset)
        self._a_offset.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        
        self._anim_group.start()

    def hoverEnterEvent(self, event):
        if not (self.flags() & QtWidgets.QGraphicsItem.ItemIsMovable): return
        self.setCursor(QtCore.Qt.PointingHandCursor)
        # Всплытие при наведении
        self.run_animation(1.02, 25, 8, QtCore.QEasingCurve.OutBack)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(QtCore.Qt.ArrowCursor)
        # Возврат в покой
        self.run_animation(1.0, 15, 5, QtCore.QEasingCurve.OutBack)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # 1. Поднимаем выше всех
        self.setZValue(100)
        # 2. Сильное увеличение (взяли в руку)
        self.run_animation(1.1, 50, 20, QtCore.QEasingCurve.OutBack)
        # 3. ВАЖНО: Передаем событие дальше, чтобы сработал встроенный ItemIsMovable
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # 1. Возвращаем слой (или оставляем чуть выше, если надо)
        self.setZValue(0)
        # 2. Эффект броска обратно (немного оставляем увеличенным, т.к. курсор еще на нем)
        self.run_animation(1.02, 25, 8, QtCore.QEasingCurve.OutBack)
        
        # 3. Завершаем перемещение
        super().mouseReleaseEvent(event)


class MagicView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(
            QtGui.QPainter.Antialiasing | 
            QtGui.QPainter.SmoothPixmapTransform | 
            QtGui.QPainter.TextAntialiasing
        )
        
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setBackgroundBrush(QtGui.QBrush(APPLE_BG))
        
        self._is_panning = False
        self._last_pan_pos = QtCore.QPoint()

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        # Сетка
        grid_size = 50
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        
        lines = []
        for x in range(left, int(rect.right()), grid_size):
            lines.append(QtCore.QLineF(x, rect.top(), x, rect.bottom()))
        for y in range(top, int(rect.bottom()), grid_size):
            lines.append(QtCore.QLineF(rect.left(), y, rect.right(), y))
            
        painter.setPen(QtGui.QPen(QtGui.QColor(220, 220, 230), 1))
        painter.drawLines(lines)

    def wheelEvent(self, event):
        zoom_in = 1.1
        zoom_out = 1 / zoom_in
        if event.angleDelta().y() > 0:
            self.scale(zoom_in, zoom_in)
        else:
            self.scale(zoom_out, zoom_out)

    def mousePressEvent(self, event):
        # ИСПРАВЛЕНО: Убрана проверка SpaceModifier, которая крашила скрипт.
        # Теперь панорамирование только на Среднюю кнопку мыши (колесо).
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = True
            self._last_pan_pos = event.position().toPoint()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
        else:
            # Для Левой кнопки событие уходит в стандартную обработку (Scene -> Item)
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.position().toPoint() - self._last_pan_pos
            self._last_pan_pos = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_panning:
            self._is_panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class AppleMagicWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RZMenu: Apple UX Magic Demo (Fixed)")
        self.resize(1000, 700)
        
        self.scene = QtWidgets.QGraphicsScene(-2000, -2000, 4000, 4000)
        self.view = MagicView()
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)
        
        self.populate_demo()

    def populate_demo(self):
        # Обычные AppleNode
        for i in range(2):
            for j in range(2):
                node = AppleNode(i * 220, j * 160, 180, 120)
                self.scene.addItem(node)

        # --- ЛЕТАЮЩАЯ БУМАЖКА (Новая магия) ---
        # Добавляем справа
        paper = FlyingPaper(500, 50, 200, 250)
        self.scene.addItem(paper)
        
        # Еще одна поменьше
        paper2 = FlyingPaper(550, 350, 150, 150)
        self.scene.addItem(paper2)

# --- НОВЫЙ КЛАСС ФИЗИКИ ---

class PhysicsPoint:
    """
    Точка, которая стремится к target_pos с поведением пружины.
    """
    def __init__(self, x, y):
        self.pos = QtCore.QPointF(x, y)      # Текущая визуальная позиция
        self.target = QtCore.QPointF(x, y)   # Идеальная позиция (в локальных координатах)
        self.velocity = QtCore.QPointF(0, 0)
        
        # Физические константы
        self.stiffness = 0.1  # Сила возврата (чем меньше, тем "сопливее")
        self.damping = 0.75   # Гашение колебаний (0.9 - желе, 0.5 - в масле)
        
    def update(self):
        # Закон Гука: F = -k*x
        force_x = (self.target.x() - self.pos.x()) * self.stiffness
        force_y = (self.target.y() - self.pos.y()) * self.stiffness
        
        self.velocity.setX(self.velocity.x() * self.damping + force_x)
        self.velocity.setY(self.velocity.y() * self.damping + force_y)
        
        self.pos.setX(self.pos.x() + self.velocity.x())
        self.pos.setY(self.pos.y() + self.velocity.y())
        
        # Возвращаем True, если движение еще есть (для оптимизации)
        speed = math.hypot(self.velocity.x(), self.velocity.y())
        dist = math.hypot(self.target.x() - self.pos.x(), self.target.y() - self.pos.y())
        return speed > 0.01 or dist > 0.01


class FlyingPaper(QtWidgets.QGraphicsObject):
    """
    Элемент, имитирующий лист бумаги.
    Деформируется при перетаскивании в зависимости от точки захвата.
    """
    def __init__(self, x, y, w, h):
        super().__init__()
        self.setPos(x, y)
        self._w = w
        self._h = h
        
        self.setAcceptHoverEvents(True)
        # Мы НЕ используем ItemIsMovable, мы пишем свой драг для контроля вершин
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable) 

        # 4 угла: TL, TR, BR, BL
        # Мы храним их как физические точки
        self.corners = [
            PhysicsPoint(0, 0),        # TL
            PhysicsPoint(w, 0),        # TR
            PhysicsPoint(w, h),        # BR
            PhysicsPoint(0, h)         # BL
        ]
        
        # Точка захвата (относительно центра)
        self._drag_anchor = QtCore.QPointF(0, 0)
        self._is_dragging = False
        
        # Таймер физики (60 FPS)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._physics_step)
        
        # Тень
        self._shadow = QtWidgets.QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(20)
        self._shadow.setColor(QtGui.QColor(0, 0, 0, 40))
        self._shadow.setOffset(0, 5)
        self.setGraphicsEffect(self._shadow)

    def boundingRect(self):
        # Границы должны быть с запасом, так как бумажка может выгибаться наружу
        margin = 50
        return QtCore.QRectF(-margin, -margin, self._w + margin*2, self._h + margin*2)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Собираем полигон из текущих позиций физических точек
        poly = QtGui.QPolygonF()
        for p in self.corners:
            poly.append(p.pos)
            
        # Градиент "Бумаги"
        path = QtGui.QPainterPath()
        path.addPolygon(poly)
        
        grad = QtGui.QLinearGradient(0, 0, self._w, self._h)
        grad.setColorAt(0, QtGui.QColor(255, 255, 255))
        grad.setColorAt(1, QtGui.QColor(240, 240, 245))
        
        painter.setBrush(QtGui.QBrush(grad))
        
        if self.isSelected():
            painter.setPen(QtGui.QPen(APPLE_BLUE, 2))
        else:
            painter.setPen(QtGui.QPen(QtGui.QColor(200, 200, 200), 1))
            
        painter.drawPath(path)
        
        # Рисуем "линовку" или текст, чтобы было видно искажение
        painter.setClipPath(path)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 20), 1))
        
        # Интерполяция линий внутри искаженного четырехугольника (упрощенно)
        # Просто рисуем линии между левыми и правыми точками
        steps = 5
        for i in range(1, steps):
            ratio = i / steps
            # Линейная интерполяция между левой гранью и правой гранью
            p_left = self.corners[0].pos * (1-ratio) + self.corners[3].pos * ratio
            p_right = self.corners[1].pos * (1-ratio) + self.corners[2].pos * ratio
            painter.drawLine(p_left, p_right)

    def _physics_step(self):
        any_movement = False
        for p in self.corners:
            if p.update():
                any_movement = True
        
        self.update() # Перерисовка
        
        # Если все успокоилось и мы не тащим - выключаем таймер для экономии CPU
        if not any_movement and not self._is_dragging:
            self._timer.stop()

    def mousePressEvent(self, event):
        self._is_dragging = True
        self.setCursor(QtCore.Qt.ClosedHandCursor)
        self._drag_anchor = event.pos() # Где схватили внутри объекта
        
        # МАГИЯ: Рассчитываем жесткость для каждого угла в зависимости от точки хвата
        max_dist = math.hypot(self._w, self._h)
        
        for p in self.corners:
            # Расстояние от точки хвата до этого угла
            dist = math.hypot(p.target.x() - self._drag_anchor.x(), p.target.y() - self._drag_anchor.y())
            
            # Чем ближе к курсору, тем жестче (stiffness выше)
            # Чем дальше, тем мягче (бумажка отстает)
            ratio = 1.0 - (dist / (max_dist * 1.5))
            ratio = max(0.05, ratio) # Минимум 5% жесткости
            
            p.stiffness = 0.4 * ratio # Базовая жесткость 0.4
            p.damping = 0.6 + (0.2 * ratio) # Ближние точки гасят колебания быстрее
            
        self.setZValue(100) # Наверх
        self._shadow.setBlurRadius(40)
        self._shadow.setOffset(0, 20)
        self._timer.start()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            # Считаем, насколько сдвинулась мышь
            # Внимание: mapToParent нужен, так как мы меняем self.pos()
            new_pos = self.mapToParent(event.pos()) - self._drag_anchor
            
            # Разница (вектор скорости объекта)
            delta = new_pos - self.pos()
            
            # Двигаем сам объект
            self.setPos(new_pos)
            
            # А ТЕПЕРЬ САМОЕ ВАЖНОЕ:
            # Мы сдвинули объект, значит локальные координаты углов "уехали".
            # Чтобы создать эффект инерции, мы должны сдвинуть визуальные точки
            # в ПРОТИВОПОЛОЖНУЮ сторону от движения.
            
            for p in self.corners:
                # Мы "выдергиваем" ковер из под точек.
                # Они остаются на месте в мировых координатах, а объект уехал.
                # Потом пружина их подтянет.
                p.pos.setX(p.pos.x() - delta.x())
                p.pos.setY(p.pos.y() - delta.y())
                
    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        self.setCursor(QtCore.Qt.ArrowCursor)
        
        # Возвращаем нормальную физику (все углы одинаково упругие)
        for p in self.corners:
            p.stiffness = 0.15
            p.damping = 0.8
            
        self.setZValue(0)
        self._shadow.setBlurRadius(20)
        self._shadow.setOffset(0, 5)
        # Таймер не останавливаем, пока не успокоится качание
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        self.setCursor(QtCore.Qt.OpenHandCursor)
        super().hoverEnterEvent(event)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = AppleMagicWindow()
    window.show()
    sys.exit(app.exec())