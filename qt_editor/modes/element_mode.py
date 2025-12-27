from PySide6 import QtWidgets, QtGui, QtCore
from ..rz_bridge import RZBridge
from ..utils.image_cache import ImageCache

class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, data, bridge):
        super().__init__(0, 0, data['w'], data['h'])
        self.setPos(data['x'], data['y'])
        
        self.bridge = bridge
        self.element_id = data['id']
        self.image_id = data.get('image_id', -1)
        self.element_type = data.get('type', 'CONTAINER')
        
        # Настройка флагов
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        
        # 1. ЦВЕТ (Из Blender)
        # data['color'] приходит как (R, G, B, A) float 0-1
        c = data.get('color', (0.5, 0.5, 0.5, 1.0))
        self.base_color = QtGui.QColor.fromRgbF(c[0], c[1], c[2], c[3])
        
        # Текст
        self.text_item = QtWidgets.QGraphicsTextItem(data['name'], self)
        self.text_item.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        # Тень для текста, чтобы читался на любом фоне
        effect = QtWidgets.QGraphicsDropShadowEffect()
        effect.setBlurRadius(4)
        effect.setColor(QtGui.QColor(0,0,0))
        effect.setOffset(1,1)
        self.text_item.setGraphicsEffect(effect)
        self.text_item.setPos(2, 0)
        self.text_item.setZValue(10)

    def paint(self, painter, option, widget):
        # Получаем картинку из кэша (быстро)
        pixmap = ImageCache.instance().get_pixmap(self.image_id)
        rect = self.rect()
        
        # Отрисовка фона
        if pixmap and not pixmap.isNull():
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(rect.toRect(), pixmap)
            
            # Легкая рамка и полупрозрачная заливка цветом (если задан цвет поверх)
            if self.base_color.alpha() > 0:
                painter.setBrush(QtGui.QBrush(self.base_color))
                painter.setOpacity(self.base_color.alphaF() * 0.3) # 30% тинт цвета поверх картинки
                painter.drawRect(rect)
                painter.setOpacity(1.0)
        else:
            # Если картинки нет - просто цветной квадрат
            painter.setBrush(QtGui.QBrush(self.base_color))
            painter.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30), 1))
            painter.drawRect(rect)

        # Отрисовка выделения (оранжевая рамка)
        if self.isSelected():
            painter.setBrush(QtCore.Qt.NoBrush)
            pen = QtGui.QPen(QtGui.QColor("#ffaa00"), 2)
            pen.setJoinStyle(QtCore.Qt.MiterJoin)
            painter.setPen(pen)
            # Рисуем чуть внутри, чтобы не обрезалось
            painter.drawRect(rect.adjusted(1,1,-1,-1))

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            if self.bridge:
                self.bridge.enqueue_update_element(self.element_id, int(value.x()), int(value.y()))
        return super().itemChange(change, value)

class RZViewport(QtWidgets.QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#181818")))
        
    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            zoom_in = event.angleDelta().y() > 0
            scale = 1.15 if zoom_in else 1 / 1.15
            self.scale(scale, scale)
        else:
            super().wheelEvent(event)
    
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        grid_size = 50
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40), 1))
        l = int(rect.left()) - (int(rect.left()) % grid_size)
        t = int(rect.top()) - (int(rect.top()) % grid_size)
        for x in range(l, int(rect.right()), grid_size):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(t, int(rect.bottom()), grid_size):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

class ElementMode(QtWidgets.QWidget):
    element_selected = QtCore.Signal(object)

    def __init__(self, context, bridge):
        super().__init__()
        self.bl_context = context
        self.bridge = bridge 
        self.scene = QtWidgets.QGraphicsScene()
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.view = RZViewport(self.scene)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.view)

    def on_selection_changed(self):
        items = self.scene.selectedItems()
        if len(items) == 1 and isinstance(items[0], RZElementItem):
            self.element_selected.emit(items[0].element_id)
        else:
            self.element_selected.emit(None)

    def rebuild_scene(self):
        # 1. Очистка
        ImageCache.instance().clear()
        self.scene.clear()
        
        if not hasattr(self.bl_context.scene, "rzm"): return
        elements = self.bl_context.scene.rzm.elements
        
        # 2. Сбор данных и PRE-CACHE картинок
        for elem in elements:
            # Определяем ID картинки
            img_id = -1
            if elem.image_mode == 'SINGLE':
                img_id = elem.image_id
            
            # ВАЖНО: Грузим картинку в кэш ПРЯМО СЕЙЧАС (пока мы в безопасном контексте)
            if img_id != -1:
                ImageCache.instance().pre_cache_image(img_id)
            
            # Собираем данные
            data = {
                'id': elem.id,
                'name': elem.element_name,
                'type': elem.elem_class,
                'x': elem.position[0],
                'y': elem.position[1],
                'w': elem.size[0],
                'h': elem.size[1],
                'image_id': img_id,
                # Получаем цвет (tuple 4 float)
                'color': tuple(elem.color) 
            }
            
            # 3. Создание айтема
            item = RZElementItem(data, self.bridge)
            self.scene.addItem(item)