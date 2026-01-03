# RZMenu/qt_editor/widgets/viewport.py
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6
from .. import core
from ..utils.image_cache import ImageCache
from ..context import RZContextManager
from ..context.states import RZInteractionState
from .lib.theme import get_current_theme

HANDLE_SIZE = 8

class RZHandleItem(QtWidgets.QGraphicsRectItem):
    # Handle types
    TOP_LEFT, TOP, TOP_RIGHT, RIGHT, BOTTOM_RIGHT, BOTTOM, BOTTOM_LEFT, LEFT = range(8)

    def __init__(self, handle_type, parent):
        super().__init__(0, 0, HANDLE_SIZE, HANDLE_SIZE, parent)
        self.handle_type = handle_type
        
        t = get_current_theme()
        self.normal_brush = QtGui.QBrush(QtGui.QColor(t.get('vp_handle', '#FFFFFF')))
        self.hover_brush = QtGui.QBrush(QtGui.QColor(t.get('vp_active', '#FF8C00')))
        
        self.setBrush(self.normal_brush)
        self.setPen(QtGui.QPen(QtGui.QColor(t.get('vp_handle_border', '#000000')), 1))
        self.setZValue(100) 
        
        cursors = {
            self.TOP_LEFT: QtCore.Qt.SizeFDiagCursor, self.BOTTOM_RIGHT: QtCore.Qt.SizeFDiagCursor,
            self.TOP_RIGHT: QtCore.Qt.SizeBDiagCursor, self.BOTTOM_LEFT: QtCore.Qt.SizeBDiagCursor,
            self.TOP: QtCore.Qt.SizeVerCursor, self.BOTTOM: QtCore.Qt.SizeVerCursor,
            self.LEFT: QtCore.Qt.SizeHorCursor, self.RIGHT: QtCore.Qt.SizeHorCursor,
        }
        self.setCursor(cursors.get(handle_type, QtCore.Qt.ArrowCursor))
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        if self.parentItem() and getattr(self.parentItem(), 'is_locked', False):
            return
        self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(self.normal_brush)
        super().hoverLeaveEvent(event)

    def shape(self):
        """Improve hit-testing by providing a larger interaction area."""
        path = QtGui.QPainterPath()
        # Add 4px margin for easier grabbing
        path.addRect(self.rect().adjusted(-4, -4, 4, 4))
        return path

    def paint(self, painter, option, widget):
        """Visual polish: rounded handles with antialiasing."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRoundedRect(self.rect(), 2, 2)

    def mousePressEvent(self, event):
        if self.parentItem() and getattr(self.parentItem(), 'is_locked', False):
            event.ignore()
            return
        event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            delta = event.scenePos() - event.lastScenePos()
            self.parentItem().handle_resize(self.handle_type, delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, uid, w, h, name, elem_type="CONTAINER"):
        super().__init__(0, 0, w, h)
        self.uid = uid
        self.elem_type = elem_type
        self.name = name
        self.text_content = name
        self.is_active = False
        self.is_locked = False
        self.image_id = -1
        self.is_selectable = True
        self.custom_color = None 
        self.handles = {} 
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption | 
            QtWidgets.QGraphicsItem.ItemIsSelectable
        )

    def create_handles(self):
        if self.handles: return
        for h_type in range(8):
            self.handles[h_type] = RZHandleItem(h_type, self)
        self.update_handles_pos()

    def update_handles_pos(self):
        if not self.handles: return
        rect = self.rect()
        w, h = rect.width(), rect.height()
        hs, hh = HANDLE_SIZE, HANDLE_SIZE / 2
        
        positions = [
            (-hh, -hh), (w/2 - hh, -hh), (w - hh, -hh),
            (w - hh, h/2 - hh), (w - hh, h - hh), (w/2 - hh, h - hh),
            (-hh, h - hh), (-hh, h/2 - hh)
        ]
        for h_type, pos in enumerate(positions):
            if h_type in self.handles:
                self.handles[h_type].setPos(*pos)

    def set_handles_visible(self, visible):
        if not self.handles and visible: self.create_handles()
        for handle in self.handles.values(): handle.setVisible(visible)

    def handle_resize(self, h_type, delta):
        if self.is_locked: return
        r, pos, dx, dy = self.rect(), self.pos(), delta.x(), delta.y()
        nx, ny, nw, nh = pos.x(), pos.y(), r.width(), r.height()
        MIN_SIZE = 10
        
        if h_type in (RZHandleItem.LEFT, RZHandleItem.TOP_LEFT, RZHandleItem.BOTTOM_LEFT):
            if nw - dx < MIN_SIZE: dx = nw - MIN_SIZE
            nx += dx; nw -= dx
        elif h_type in (RZHandleItem.RIGHT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_RIGHT):
            if nw + dx < MIN_SIZE: dx = MIN_SIZE - nw
            nw += dx

        if h_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
            if nh - dy < MIN_SIZE: dy = nh - MIN_SIZE
            ny += dy; nh -= dy
        elif h_type in (RZHandleItem.BOTTOM, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT):
            if nh + dy < MIN_SIZE: dy = MIN_SIZE - nh
            nh += dy

        self.setRect(0, 0, nw, nh)
        self.setPos(nx, ny)
        self.update_handles_pos() 
        self.scene().element_resized_signal.emit(self.uid, int(nx), int(-ny), int(nw), int(nh))

    def set_data_state(self, locked, img_id, is_selectable, text_content, color=None):
        self.is_locked, self.image_id, self.is_selectable = locked, img_id, is_selectable
        self.text_content = text_content if text_content else self.name
        self.custom_color = color
        self.setOpacity(0.5 if not is_selectable else 1.0)
        self.update()

    def set_visual_state(self, is_selected, is_active):
        if self.isSelected() != is_selected: self.setSelected(is_selected)
        self.is_active = is_active
        z_val = 1
        if is_active: z_val = 20
        elif is_selected: z_val = 10
        self.setZValue(z_val)
        self.set_handles_visible(is_selected and not self.is_locked)
        self.update() 
    
    def update_size(self, w, h):
        self.setRect(0, 0, w, h)
        self.update_handles_pos()
        self.update() 
    
    def paint(self, painter, option, widget):
        rect = self.rect()
        t = get_current_theme()
        
        if self.elem_type == 'TEXT':
            painter.setPen(QtGui.QColor(t.get('text_bright', '#FFF')))
            painter.drawText(rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.text_content)
            if self.isSelected():
                 painter.setPen(QtGui.QPen(QtGui.QColor(t.get('vp_selection', '#FFF')), 1, QtCore.Qt.DashLine))
                 painter.drawRect(rect)
            return

        has_image = False
        if self.image_id != -1:
            pix = ImageCache.instance().get_pixmap(self.image_id)
            if pix and not pix.isNull():
                painter.drawPixmap(rect.toRect(), pix)
                has_image = True

        if self.custom_color and len(self.custom_color) >= 3:
            r, g, b = [int(c*255) for c in self.custom_color[:3]]
            a = int(self.custom_color[3]*255) if len(self.custom_color) > 3 else 255
            bg_color = QtGui.QColor(r, g, b, a)
        else:
            color_key = f"vp_type_{self.elem_type.lower()}"
            bg_color = QtGui.QColor(t.get(color_key, "rgba(50,50,50,200)"))
        
        if has_image and not self.custom_color: bg_color.setAlpha(30)
        if self.is_locked: bg_color = bg_color.darker(120)
        painter.fillRect(rect, bg_color)
        
        border_width, border_color_str = 1.0, t.get('vp_handle_border', '#000')
        if self.is_active:
            border_color_str = t.get('vp_active', '#FF8C00')
            border_width = 2.0
        elif self.isSelected():
            border_color_str = t.get('vp_selection', '#FFF')
        elif self.is_locked:
            border_color_str = t.get('vp_locked', '#F00')
        pen = QtGui.QPen(QtGui.QColor(border_color_str), border_width)
        if self.elem_type == "GRID_CONTAINER": pen.setStyle(QtCore.Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(rect)

        text_rect = rect.adjusted(5, 5, -5, -5)
        painter.setPen(QtGui.QColor(t.get('text_bright', '#FFF')))
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.name)
        
        if self.is_locked:
            painter.setPen(QtGui.QColor(t.get('vp_locked', '#F00')))
            painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop, "🔒")

class RZViewportScene(QtWidgets.QGraphicsScene):
    item_moved_signal = QtCore.Signal(float, float) 
    element_resized_signal = QtCore.Signal(int, int, int, int, int)
    selection_changed_signal = QtCore.Signal(object, object)
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._is_user_interaction, self._is_dragging_items = False, False
        self._drag_start_pos, self.is_alt_mode = None, False
        self._items_map = {} 
        self.setSceneRect(-10000, -10000, 20000, 20000)
        
        # Accumulators for sub-pixel precision in Blender deltas
        self._accum_x = 0.0
        self._accum_y = 0.0

    def drawBackground(self, painter, rect):
        """Infinite Grid Drawing."""
        t = get_current_theme()
        
        # Fill Background
        bg_color = QtGui.QColor(t.get('vp_bg', '#1E1E1E'))
        painter.fillRect(rect, bg_color)

        # Draw Grid
        grid_color = QtGui.QColor(t.get('vp_grid_color', 'rgba(255, 255, 255, 30)'))
        
        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())

        # Determine grid steps
        grid_step = 100
        major_step = 500
        
        # Draw Secondary Grid
        painter.setPen(QtGui.QPen(grid_color, 0.5))
        
        first_x = left - (left % grid_step)
        first_y = top - (top % grid_step)

        # Draw vertical lines
        for x in range(first_x, right + grid_step, grid_step):
            if x % major_step != 0:
                painter.drawLine(x, top, x, bottom)

        # Draw horizontal lines
        for y in range(first_y, bottom + grid_step, grid_step):
            if y % major_step != 0:
                painter.drawLine(left, y, right, y)

        # Draw Major Grid
        major_color = grid_color.lighter(150)
        major_color.setAlpha(min(grid_color.alpha() * 2, 255))
        painter.setPen(QtGui.QPen(major_color, 1.0))
        
        first_major_x = left - (left % major_step)
        first_major_y = top - (top % major_step)

        for x in range(first_major_x, right + major_step, major_step):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_major_y, bottom + major_step, major_step):
            painter.drawLine(left, y, right, y)
        
        # Draw Axis (Origin)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 80), 1.5))
        if left <= 0 <= right:
            painter.drawLine(0, top, 0, bottom)
        if top <= 0 <= bottom:
            painter.drawLine(left, 0, right, 0)

    def _init_background(self):
        # We now use drawBackground, but keep this for backward compatibility or initial setup
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton: return 
        if self.is_alt_mode:
            super().mousePressEvent(event)
            return

        item = self.itemAt(event.scenePos(), QtGui.QTransform())
        if isinstance(item, RZHandleItem):
            self.interaction_start_signal.emit()
            super().mousePressEvent(event)
            return

        modifier_str = 'CTRL' if event.modifiers() & QtCore.Qt.ControlModifier else 'SHIFT' if event.modifiers() & QtCore.Qt.ShiftModifier else None
        
        if isinstance(item, RZElementItem):
            if not item.is_selectable:
                event.ignore(); return
            self._handle_item_click(item, event, modifier_str)
            
            # Only start dragging if the clicked item is not locked
            if not item.is_locked:
                self._is_dragging_items = True
                self._drag_start_pos = event.scenePos()
                self._accum_x = 0.0
                self._accum_y = 0.0
                self.interaction_start_signal.emit()
            event.accept() 
        else:
            super().mousePressEvent(event)

    def _handle_item_click(self, clicked_item, event, modifier_str):
        items_under = [i for i in self.items(event.scenePos()) if isinstance(i, RZElementItem) and i.is_selectable]
        if not items_under: return
        
        target_uid = clicked_item.uid
        if modifier_str is None and len(items_under) > 1:
            try:
                current_index = [i.isSelected() for i in items_under].index(True)
                target_uid = items_under[(current_index + 1) % len(items_under)].uid
            except ValueError:
                target_uid = items_under[0].uid
        self.selection_changed_signal.emit(target_uid, modifier_str)

    def mouseMoveEvent(self, event):
        if self.is_alt_mode:
             super().mouseMoveEvent(event); return

        if self._is_dragging_items and self._drag_start_pos:
            current_pos = event.scenePos()
            qt_delta = current_pos - self._drag_start_pos
            
            # ARCHITECT FIX: Abort drag if any selected item is locked
            selected_items = [i for i in self.selectedItems() if isinstance(i, RZElementItem)]
            if any(item.is_locked for item in selected_items):
                return

            # Visual movement in Qt (always smooth with floats)
            for item in selected_items:
                item.moveBy(qt_delta.x(), qt_delta.y())

            # PRECISION FIX: Accumulate sub-pixel deltas
            # Manual conversion to avoid dependence on core.maths.int() casts
            dx_bl = float(qt_delta.x())
            dy_bl = float(-qt_delta.y())
            
            self._accum_x += dx_bl
            self._accum_y += dy_bl
            
            # Only emit signal when accumulated delta reaches a whole pixel
            if abs(self._accum_x) >= 1.0 or abs(self._accum_y) >= 1.0:
                emit_x = int(self._accum_x)
                emit_y = int(self._accum_y)
                
                self.item_moved_signal.emit(float(emit_x), float(emit_y))
                
                self._accum_x -= emit_x
                self._accum_y -= emit_y

            self._drag_start_pos = current_pos
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging_items:
            self._is_dragging_items, self._drag_start_pos = False, None
            self.interaction_end_signal.emit()
        elif self._is_user_interaction:
             self.interaction_end_signal.emit()
        super().mouseReleaseEvent(event)

    def update_selection_visuals(self, selected_ids, active_id):
        if self._is_user_interaction: return
        for uid, item in self._items_map.items():
            item.set_visual_state(uid in selected_ids, uid == active_id)

    def update_scene(self, elements_data, selected_ids, active_id):
        if self._is_user_interaction: return
        
        incoming_ids = {d['id'] for d in elements_data}
        current_ids = set(self._items_map.keys())
        cache = ImageCache.instance()

        for data in elements_data:
            if data.get('image_id', -1) != -1: cache.pre_cache_image(data['image_id'])

        for uid in (current_ids - incoming_ids):
            if uid in self._items_map and shiboken6.isValid(self._items_map[uid]):
                self.removeItem(self._items_map[uid])
            if uid in self._items_map: del self._items_map[uid]
        
        for data in elements_data:
            uid = data['id']
            qx, qy = core.to_qt_coords(data['pos_x'], data['pos_y'])
            item = self._items_map.get(uid)
            if not item or not shiboken6.isValid(item):
                item = RZElementItem(uid, data['width'], data['height'], data['name'], data.get('class_type', 'CONTAINER'))
                self.addItem(item)
                self._items_map[uid] = item
            else:
                item.name = data['name']
                item.elem_type = data.get('class_type', 'CONTAINER')

            item.update_size(data['width'], data['height'])
            item.setPos(qx, qy)
            item.set_data_state(data.get('is_locked', False), data.get('image_id', -1), 
                                data.get('is_selectable', True), data.get('text_content', ''), data.get('color', None))
            item.setVisible(not data.get('is_hidden', False))
            item.set_visual_state(uid in selected_ids, uid == active_id)

        for data in elements_data:
            uid, pid = data['id'], data.get('parent_id', -1)
            if uid in self._items_map and pid != -1 and pid in self._items_map:
                item, parent_item = self._items_map[uid], self._items_map[pid]
                if item.parentItem() != parent_item: item.setParentItem(parent_item)
            elif uid in self._items_map and self._items_map[uid].parentItem() is not None:
                self._items_map[uid].setParentItem(None)
        self.update()

class RZViewportPanel(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setObjectName("RZViewportPanel")
        self.rz_scene = RZViewportScene()
        self.setScene(self.rz_scene)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self._is_panning = False
        self._pan_start_pos = QtCore.QPoint()
        self.parent_window = None 
        self.rz_scene.interaction_start_signal.connect(self._on_interaction_start)
        self.rz_scene.interaction_end_signal.connect(self._on_interaction_end)

    def _on_interaction_start(self):
        RZContextManager.get_instance().set_state(RZInteractionState.DRAGGING)

    def _on_interaction_end(self):
        RZContextManager.get_instance().set_state(RZInteractionState.IDLE)

    def set_alt_mode(self, active):
        self.rz_scene.is_alt_mode = active
        t = get_current_theme()
        if active:
            color = t.get('ctx_viewport', '#4772b3')
            self.setStyleSheet(f"border: 2px solid {color};") 
            self.setCursor(QtCore.Qt.PointingHandCursor)
        else:
            self.setStyleSheet("border: none;")
            self.setCursor(QtCore.Qt.ArrowCursor)

    def contextMenuEvent(self, event):
        if not self.parent_window or not hasattr(self.parent_window, "action_manager"): return
        menu = QtWidgets.QMenu(self)
        am = self.parent_window.action_manager
        def add_op(op_id):
            if op_id in am.q_actions: menu.addAction(am.q_actions[op_id])
        
        hit_element = hasattr(self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform()), 'uid')

        if hit_element:
            menu.addSection("Element"); add_op("rzm.toggle_hide"); add_op("rzm.toggle_lock"); add_op("rzm.toggle_selectable")
            menu.addSeparator(); add_op("rzm.delete")
        else:
            menu.addSection("General"); add_op("rzm.select_all"); add_op("rzm.view_reset"); add_op("rzm.unhide_all")
        menu.addSeparator(); add_op("rzm.undo"); add_op("rzm.redo")
        menu.exec(event.globalPos())

    def enterEvent(self, event):
        # Update context with current mouse position on enter
        global_pos = QtGui.QCursor.pos()
        view_pos = self.mapFromGlobal(global_pos)
        scene_pos = self.mapToScene(view_pos)
        RZContextManager.get_instance().update_input(global_pos, (scene_pos.x(), -scene_pos.y()), area="VIEWPORT")
        super().enterEvent(event)

    def leaveEvent(self, event):
        RZContextManager.get_instance().update_input(QtGui.QCursor.pos(), (0,0), area="NONE")
        super().leaveEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        current_scale = self.transform().m11()
        if (factor > 1 and current_scale < 5.0) or (factor < 1 and current_scale > 0.1):
            self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = True; self._pan_start_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            RZContextManager.get_instance().set_state(RZInteractionState.PANNING)
            event.accept(); return
        
        item = self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform())
        if not self.rz_scene.is_alt_mode and not hasattr(item, 'uid') and not hasattr(item, 'handle_type'):
            self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
            RZContextManager.get_instance().set_state(RZInteractionState.BOX_SELECT)
        else:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        screen_pos, scene_pos_qt = event.globalPos(), self.mapToScene(event.pos())
        scene_x, scene_y = scene_pos_qt.x(), -scene_pos_qt.y()
        hover_uid = -1
        for it in self.scene().items(scene_pos_qt):
            if hasattr(it, 'uid'): hover_uid = it.uid; break
        mgr = RZContextManager.get_instance()
        mgr.update_input(screen_pos, (scene_x, scene_y), area="VIEWPORT")
        mgr.set_hover_id(hover_uid)
        
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = False; self.setCursor(QtCore.Qt.ArrowCursor)
            RZContextManager.get_instance().set_state(RZInteractionState.IDLE)
            event.accept(); return
            
        if self.dragMode() == QtWidgets.QGraphicsView.RubberBandDrag:
            ids = [item.uid for item in self.scene().selectedItems() if hasattr(item, 'uid')]
            modifier_str = 'SHIFT' if event.modifiers() & QtCore.Qt.ShiftModifier else None
            if ids or modifier_str is None:
                self.rz_scene.selection_changed_signal.emit(ids or -1, modifier_str)
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self.scene().clearSelection()
            RZContextManager.get_instance().set_state(RZInteractionState.IDLE)
        super().mouseReleaseEvent(event)