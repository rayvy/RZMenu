from PySide6 import QtWidgets, QtGui, QtCore

# --- ITEM CLASS ---
class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, data, bridge):
        super().__init__(0, 0, data['w'], data['h'])
        self.setPos(data['x'], data['y'])
        
        self.bridge = bridge
        self.element_id = data['id']
        
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        
        colors = {
            'CONTAINER': QtGui.QColor(60, 60, 60),
            'BUTTON': QtGui.QColor(71, 114, 179),
            'IMAGE': QtGui.QColor(179, 71, 71),
            'TEXT': QtGui.QColor(71, 179, 114)
        }
        self.bg_color = colors.get(data['type'], QtGui.QColor(100, 100, 100))
        self.setBrush(QtGui.QBrush(self.bg_color))
        self.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30), 1))
        
        self.text_item = QtWidgets.QGraphicsTextItem(data['name'], self)
        self.text_item.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        self.text_item.setPos(5, 0)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffaa00"), 2))
            painter.drawRect(self.rect())

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            new_pos = value
            x = int(new_pos.x())
            y = int(new_pos.y())
            if self.bridge:
                self.bridge.enqueue_update_element(self.element_id, x, y)
        return super().itemChange(change, value)

# --- VIEWPORT CLASS ---
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
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        for x in range(left, int(rect.right()), grid_size):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), grid_size):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

# --- MODE CLASS ---
class ElementMode(QtWidgets.QWidget):
    # Signal emitting the ID of the selected element (or None)
    element_selected = QtCore.Signal(object)

    def __init__(self, context, bridge):
        super().__init__()
        self.bl_context = context
        self.bridge = bridge # Receive bridge from MainWindow
        
        self.scene = QtWidgets.QGraphicsScene()
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        
        # Connect Selection Signal from Scene
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        
        self.view = RZViewport(self.scene)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def on_scene_selection_changed(self):
        """Handle QGraphicsScene selection changes."""
        selected_items = self.scene.selectedItems()
        
        if len(selected_items) == 1:
            item = selected_items[0]
            if isinstance(item, RZElementItem):
                self.element_selected.emit(item.element_id)
            else:
                self.element_selected.emit(None)
        else:
            # If 0 items or >1 items (multi-select), clear inspector for now
            self.element_selected.emit(None)

    def rebuild_scene(self):
        self.scene.clear()
        if not hasattr(self.bl_context.scene, "rzm"):
            return

        elements = self.bl_context.scene.rzm.elements
        for elem in elements:
            data = {
                'id': elem.id,
                'name': elem.element_name,
                'type': elem.elem_class,
                'x': elem.position[0],
                'y': elem.position[1],
                'w': elem.size[0],
                'h': elem.size[1]
            }
            # Pass existing bridge to items
            item = RZElementItem(data, self.bridge)
            self.scene.addItem(item)