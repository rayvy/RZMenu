# RZMenu/qt_editor/ui/viewport_items.py

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QObject # <--- Added QObject
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsTextItem

from typing import List
from ..backend.dtos import RZElement

# --- Constants ---
HANDLE_SIZE = 8
MIN_ITEM_SIZE = 10

class RZHandleItem(QObject, QGraphicsRectItem): # <--- FIXED: Inherit from QObject first!
    """A draggable handle for resizing a parent item."""
    
    dragged = Signal(object, QPointF)
    drag_started = Signal()
    drag_finished = Signal()
    
    TOP_LEFT, TOP, TOP_RIGHT, RIGHT, BOTTOM_RIGHT, BOTTOM, BOTTOM_LEFT, LEFT = range(8)

    def __init__(self, handle_type: int, parent: QGraphicsItem):
        # Initialize both bases
        QGraphicsRectItem.__init__(self, 0, 0, HANDLE_SIZE, HANDLE_SIZE, parent)
        QObject.__init__(self) # Init signal machinery
        
        self.handle_type = handle_type
        
        self.setBrush(QtGui.QBrush(Qt.GlobalColor.white))
        self.setPen(QtGui.QPen(Qt.GlobalColor.black, 1))
        self.setZValue(100)
        self.setAcceptHoverEvents(True)

        cursors = {
            self.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor, self.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            self.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor, self.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
            self.TOP: Qt.CursorShape.SizeVerCursor, self.BOTTOM: Qt.CursorShape.SizeVerCursor,
            self.LEFT: Qt.CursorShape.SizeHorCursor, self.RIGHT: Qt.CursorShape.SizeHorCursor,
        }
        self.setCursor(cursors.get(handle_type, Qt.CursorShape.ArrowCursor))

    def hoverEnterEvent(self, event):
        self.setBrush(QtGui.QBrush(QtGui.QColor("#ff8c00")))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QtGui.QBrush(Qt.GlobalColor.white))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        self.drag_started.emit()
        event.accept()

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.scenePos() - event.lastScenePos()
            self.dragged.emit(self, delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        self.drag_finished.emit()
        event.accept()

class RZElementItem(QObject, QGraphicsRectItem): # <--- FIXED: Inherit QObject for signals
    """
    A 'dumb' graphical representation of an RZElement.
    """
    selected = Signal(int, str)
    moved = Signal(int, float, float)
    resized = Signal(int, float, float, float, float)
    interaction_started = Signal(int)
    interaction_finished = Signal(int)

    def __init__(self, dto: RZElement, parent_item: QGraphicsItem = None):
        QGraphicsRectItem.__init__(self, parent_item)
        QObject.__init__(self)
        
        self.uid = dto.id
        self._is_resizing = False
        self._dto_cache: RZElement = dto

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        self._text = QGraphicsTextItem(self)
        self._handles: List[RZHandleItem] = []
        for h_type in range(8):
            handle = RZHandleItem(h_type, self)
            handle.dragged.connect(self._on_handle_drag)
            handle.drag_started.connect(self._on_handle_drag_start)
            handle.drag_finished.connect(self._on_handle_drag_finish)
            self._handles.append(handle)
        
        self.update_from_dto(dto)

    def update_from_dto(self, dto: RZElement):
        self._dto_cache = dto
        
        # Invert Y for Qt
        self.setPos(dto.pos_x, -dto.pos_y)
        self.setRect(0, 0, dto.width, dto.height)
        
        self.setVisible(not dto.is_hidden)
        # Fix locking: if locked, movable is False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not dto.is_locked)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, dto.is_selectable)
        self.setOpacity(0.6 if not dto.is_selectable else 1.0)
        
        self._text.setPlainText(dto.name)
        
        # Only show handles if selected AND NOT LOCKED
        show_handles = self.isSelected() and not dto.is_locked
        self.set_handles_visible(show_handles)
        
        self._update_handles_pos()
        self.update()

    def set_handles_visible(self, visible: bool):
        for handle in self._handles:
            handle.setVisible(visible)

    def _update_handles_pos(self):
        rect = self.rect()
        w, h = rect.width(), rect.height()
        hs_half = HANDLE_SIZE / 2
        
        positions = {
            RZHandleItem.TOP_LEFT: (0 - hs_half, 0 - hs_half), RZHandleItem.TOP: (w / 2 - hs_half, 0 - hs_half),
            RZHandleItem.TOP_RIGHT: (w - hs_half, 0 - hs_half), RZHandleItem.RIGHT: (w - hs_half, h / 2 - hs_half),
            RZHandleItem.BOTTOM_RIGHT: (w - hs_half, h - hs_half), RZHandleItem.BOTTOM: (w / 2 - hs_half, h - hs_half),
            RZHandleItem.BOTTOM_LEFT: (0 - hs_half, h - hs_half), RZHandleItem.LEFT: (0 - hs_half, h / 2 - hs_half),
        }
        for handle in self._handles:
            handle.setPos(*positions[handle.handle_type])

    def _on_handle_drag_start(self):
        self._is_resizing = True
        self.interaction_started.emit(self.uid)

    def _on_handle_drag_finish(self):
        if not self._is_resizing: return
        self._is_resizing = False
        pos, rect = self.pos(), self.rect()
        # Emit Blender coordinates (Y is inverted)
        self.resized.emit(self.uid, pos.x(), -pos.y(), rect.width(), rect.height())
        self.interaction_finished.emit(self.uid)

    def _on_handle_drag(self, handle: RZHandleItem, delta: QPointF):
        rect, pos = self.rect(), self.pos()
        new_rect, new_pos = QRectF(rect), QPointF(pos)

        if handle.handle_type in (RZHandleItem.LEFT, RZHandleItem.TOP_LEFT, RZHandleItem.BOTTOM_LEFT):
            new_width = max(MIN_ITEM_SIZE, rect.width() - delta.x())
            dx = new_width - rect.width()
            new_pos.setX(pos.x() - dx)
            new_rect.setWidth(new_width)
        elif handle.handle_type in (RZHandleItem.RIGHT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_RIGHT):
            new_rect.setWidth(max(MIN_ITEM_SIZE, rect.width() + delta.x()))

        if handle.handle_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
            new_height = max(MIN_ITEM_SIZE, rect.height() - delta.y())
            dy = new_height - rect.height()
            new_pos.setY(pos.y() - dy)
            new_rect.setHeight(new_height)
        elif handle.handle_type in (RZHandleItem.BOTTOM, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT):
            new_rect.setHeight(max(MIN_ITEM_SIZE, rect.height() + delta.y()))

        self.setPos(new_pos)
        self.setRect(new_rect)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        modifier = 'NONE'
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: modifier = 'SHIFT'
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier: modifier = 'CTRL'
        
        self.interaction_started.emit(self.uid)
        self.selected.emit(self.uid, modifier)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        super().mouseReleaseEvent(event)
        if not self._is_resizing:
            self.interaction_finished.emit(self.uid)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.mouseGrabber:
            new_pos = value
            # Emit Blender coordinates
            self.moved.emit(self.uid, new_pos.x(), -new_pos.y())
        return super().itemChange(change, value)
    
    def paint(self, painter: QtGui.QPainter, option, widget):
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dto = self._dto_cache
        
        color_tuple = dto.style.get('color', (0.2, 0.2, 0.2, 0.8))
        # Ensure we have RGBA
        if len(color_tuple) < 3: color_tuple = [0.5, 0.5, 0.5, 1.0]
        elif len(color_tuple) == 3: color_tuple = list(color_tuple) + [1.0]

        r, g, b = [int(c * 255) for c in color_tuple[:3]]
        a = int(color_tuple[3] * 255)
        bg_color = QtGui.QColor(r, g, b, a)

        if dto.is_locked:
             bg_color = bg_color.darker(150)

        painter.fillRect(rect, bg_color)
        
        border_width = 2.0 if self.isSelected() else 1.0
        border_color = QtGui.QColor("#ff8c00") if self.isSelected() else QtGui.QColor(0, 0, 0, 150)
        
        pen = QtGui.QPen(border_color, border_width)
        painter.setPen(pen)
        painter.drawRect(rect)
        
        text_color = QtGui.QColor("white")
        painter.setPen(text_color)
        painter.drawText(rect.adjusted(5, 5, -5, -5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, dto.name)

        if dto.is_locked:
            painter.setPen(QtGui.QColor("red"))
            painter.drawText(rect.adjusted(0, 5, -5, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, "🔒")