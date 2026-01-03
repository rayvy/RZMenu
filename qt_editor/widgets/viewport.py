# RZMenu/qt_editor/widgets/viewport.py
"""
Viewport Panel - Visual canvas for element manipulation.
Autonomous panel that subscribes to core.SIGNALS for data updates.
"""
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6
from .. import core
from ..core.signals import SIGNALS
from ..systems.layout import GridSolver
from ..utils.image_cache import ImageCache
from ..context import RZContextManager
from ..context.states import RZInteractionState
from .lib.theme import get_current_theme
from .panel_base import RZEditorPanel

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
        if self.parentItem() and (getattr(self.parentItem(), 'is_locked_pos', False) or getattr(self.parentItem(), 'is_locked_size', False)):
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
        if self.parentItem() and (getattr(self.parentItem(), 'is_locked_pos', False) or getattr(self.parentItem(), 'is_locked_size', False)):
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
        self.is_locked_pos = False
        self.is_locked_size = False
        self.image_id = -1
        self.is_selectable = True
        self.custom_color = None 
        self.handles = {} 
        self.alignment = "BOTTOM_LEFT"
        self._is_layout_controlled = False
        
        # Grid properties
        self.grid_padding = 0
        self.grid_gap = 0
        self.grid_cell_size = 50
        self.grid_cols = 0
        
        # Interaction state
        self._initial_rect = None
        self._aspect_ratio = 1.0

        self.setFlags(
            QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption | 
            QtWidgets.QGraphicsItem.ItemIsSelectable
        )

    def get_inner_origin(self):
        """Returns the top-left coordinate of the content area relative to (0,0) origin."""
        r = self.rect()
        return r.topLeft()

    def get_anchor_offset(self, w, h, alignment):
        """Calculates the visual offset based on the anchor point."""
        offsets = {
            "TOP_LEFT": (0, 0),
            "TOP_CENTER": (-w / 2, 0),
            "TOP_RIGHT": (-w, 0),
            "CENTER_LEFT": (0, -h / 2),
            "CENTER": (-w / 2, -h / 2),
            "CENTER_RIGHT": (-w, -h / 2),
            "BOTTOM_LEFT": (0, -h),
            "BOTTOM_CENTER": (-w / 2, -h),
            "BOTTOM_RIGHT": (-w, -h),
        }
        return offsets.get(alignment, (0, 0))

    def update_visual_rect(self, w, h):
        """Updates the internal rect based on anchor."""
        dx, dy = self.get_anchor_offset(w, h, self.alignment)
        self.setRect(dx, dy, w, h)
        self.update_handles_pos()

    def create_handles(self):
        if self.handles: return
        for h_type in range(8):
            self.handles[h_type] = RZHandleItem(h_type, self)
        self.update_handles_pos()

    def update_handles_pos(self):
        if not self.handles: return
        r = self.rect()
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        hs, hh = HANDLE_SIZE, HANDLE_SIZE / 2
        
        positions = [
            (x - hh, y - hh), (x + w / 2 - hh, y - hh), (x + w - hh, y - hh),
            (x + w - hh, y + h / 2 - hh), (x + w - hh, y + h - hh), (x + w / 2 - hh, y + h - hh),
            (x - hh, y + h - hh), (x - hh, y + h / 2 - hh)
        ]
        for h_type, pos in enumerate(positions):
            if h_type in self.handles:
                self.handles[h_type].setPos(*pos)

    def set_handles_visible(self, visible):
        if not self.handles and visible: self.create_handles()
        for handle in self.handles.values(): handle.setVisible(visible)

    def handle_resize(self, h_type, delta):
        if self.is_locked_size: return
        
        scene = self.scene()
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        is_ctrl = modifiers & QtCore.Qt.ControlModifier
        is_shift = modifiers & QtCore.Qt.ShiftModifier
        
        if self._initial_rect is None:
            self._initial_rect = self.rect()
            self._aspect_ratio = self._initial_rect.width() / max(self._initial_rect.height(), 1)

        r = self.rect()
        pos = self.pos()
        nx, ny = pos.x(), pos.y()
        nw, nh = r.width(), r.height()
        dx, dy = delta.x(), delta.y()
        
        MIN_SIZE = 5
        grid_size = scene.grid_size if (scene.snap_enabled or is_ctrl) else 1
        
        # Resizing logic is now more complex because of anchor.
        # For simplicity, we calculate new width/height first.
        if h_type in (RZHandleItem.LEFT, RZHandleItem.TOP_LEFT, RZHandleItem.BOTTOM_LEFT):
            nw -= dx
        elif h_type in (RZHandleItem.RIGHT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_RIGHT):
            nw += dx

        if h_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
            nh -= dy
        elif h_type in (RZHandleItem.BOTTOM, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT):
            nh += dy

        # Apply constraints
        if is_shift:
            if h_type in (RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT):
                nh = nw / self._aspect_ratio
            elif h_type in (RZHandleItem.LEFT, RZHandleItem.RIGHT):
                nh = nw / self._aspect_ratio
            elif h_type in (RZHandleItem.TOP, RZHandleItem.BOTTOM):
                nw = nh * self._aspect_ratio

        if scene.snap_enabled or is_ctrl:
            nw = max(grid_size, round(nw / grid_size) * grid_size)
            nh = max(grid_size, round(nh / grid_size) * grid_size)

        nw = max(MIN_SIZE, nw)
        nh = max(MIN_SIZE, nh)

        # In Blender, resizing doesn't move the 'position' (which is the anchor point).
        # Our UI reflects this: we just update size.
        self.update_visual_rect(nw, nh)
        scene.element_resized_signal.emit(self.uid, int(nx), int(-ny), int(nw), int(nh))

    def set_data_state(self, locked_pos, locked_size, img_id, is_selectable, text_content, alignment, color=None, grid_props=None):
        self.is_locked_pos, self.is_locked_size = locked_pos, locked_size
        self.image_id, self.is_selectable = img_id, is_selectable
        self.text_content = text_content if text_content else self.name
        self.alignment = alignment
        self.custom_color = color
        
        if grid_props:
            self.grid_padding = grid_props.get('padding', 0)
            self.grid_gap = grid_props.get('gap', 0)
            self.grid_cell_size = grid_props.get('cell_size', 50)
            self.grid_cols = grid_props.get('cols', 0)

        self.setOpacity(0.5 if not is_selectable else 1.0)
        self.update()

    def set_visual_state(self, is_selected, is_active):
        if self.isSelected() != is_selected: self.setSelected(is_selected)
        self.is_active = is_active
        z_val = 1
        if is_active: z_val = 20
        elif is_selected: z_val = 10
        self.setZValue(z_val)
        # Handles visible if selected and not size-locked
        self.set_handles_visible(is_selected and not self.is_locked_size)
        self.update() 
    
    def update_size(self, w, h):
        self.update_visual_rect(w, h)
        self.update() 
    
    def paint(self, painter, option, widget):
        rect = self.rect()
        t = get_current_theme()
        
        # Visual visual for anchor/origin
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
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
        if self.is_locked_pos or self.is_locked_size: bg_color = bg_color.darker(120)
        painter.fillRect(rect, bg_color)
        
        border_width, border_color_str = 1.0, t.get('vp_handle_border', '#000')
        if self.is_active:
            border_color_str = t.get('vp_active', '#FF8C00')
            border_width = 2.0
        elif self.isSelected():
            border_color_str = t.get('vp_selection', '#FFF')
        elif self.is_locked_pos or self.is_locked_size:
            border_color_str = t.get('vp_locked', '#F00')
        
        pen = QtGui.QPen(QtGui.QColor(border_color_str), border_width)
        if self.elem_type == "GRID_CONTAINER": pen.setStyle(QtCore.Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(rect)

        # Draw Marker at Origin (Local 0,0)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 180), 1.0))
        painter.drawLine(-4, 0, 4, 0)
        painter.drawLine(0, -4, 0, 4)

        text_rect = rect.adjusted(5, 5, -5, -5)
        painter.setPen(QtGui.QColor(t.get('text_bright', '#FFF')))
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.name)
        
        if self.is_locked_pos or self.is_locked_size:
            lock_txt = "🔒" if self.is_locked_pos and self.is_locked_size else "🔒P" if self.is_locked_pos else "🔒S"
            painter.setPen(QtGui.QColor(t.get('vp_locked', '#F00')))
            painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop, lock_txt)

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
        self._drag_origin = None # Fixed origin for smart axis lock
        self._items_map = {} 
        self.setSceneRect(-10000, -10000, 20000, 20000)
        
        # Grid settings
        self.grid_size = 20
        self.snap_enabled = False
        
        # Accumulators for sub-pixel precision in Blender deltas
        self._accum_x = 0.0
        self._accum_y = 0.0
        self._axis_lock = None # 'X' or 'Y'

    def _apply_snap(self, value, step):
        return round(value / step) * step

    def drawBackground(self, painter, rect):
        """Infinite Grid Drawing."""
        t = get_current_theme()
        bg_color = QtGui.QColor(t.get('vp_bg', '#1E1E1E'))
        painter.fillRect(rect, bg_color)

        grid_color = QtGui.QColor(t.get('vp_grid_color', 'rgba(255, 255, 255, 30)'))
        
        left, right = int(rect.left()), int(rect.right())
        top, bottom = int(rect.top()), int(rect.bottom())

        # Determine grid steps
        step = self.grid_size
        major_step = step * 5
        
        # Draw Secondary Grid
        painter.setPen(QtGui.QPen(grid_color, 0.5))
        first_x = left - (left % step)
        first_y = top - (top % step)

        for x in range(first_x, right + step, step):
            if x % major_step != 0: painter.drawLine(x, top, x, bottom)
        for y in range(first_y, bottom + step, step):
            if y % major_step != 0: painter.drawLine(left, y, right, y)

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
        
        # Draw Axis
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 80), 1.5))
        if left <= 0 <= right: painter.drawLine(0, top, 0, bottom)
        if top <= 0 <= bottom: painter.drawLine(left, 0, right, 0)

    def _init_background(self):
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
            
            # Only start dragging if the clicked item is not position-locked and not layout-controlled
            if not item.is_locked_pos and not getattr(item, "_is_layout_controlled", False):
                self._is_dragging_items = True
                self._drag_start_pos = event.scenePos()
                self._drag_origin = event.scenePos()
                self._accum_x = 0.0
                self._accum_y = 0.0
                self._axis_lock = None
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
            
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            is_shift = modifiers & QtCore.Qt.ShiftModifier
            is_ctrl = modifiers & QtCore.Qt.ControlModifier

            selected_items = [i for i in self.selectedItems() if isinstance(i, RZElementItem)]
            # Filter items that are position-locked or layout-controlled
            movable_items = [item for item in selected_items if not item.is_locked_pos and not getattr(item, "_is_layout_controlled", False)]
            if not movable_items:
                return

            # Dynamic Smart Axis Lock (Shift)
            if is_shift and self._drag_origin:
                total_move = current_pos - self._drag_origin
                if abs(total_move.x()) > abs(total_move.y()):
                    current_pos.setY(self._drag_origin.y())
                else:
                    current_pos.setX(self._drag_origin.x())

            qt_delta = current_pos - self._drag_start_pos
            dx, dy = qt_delta.x(), qt_delta.y()

            # Snapping
            if self.snap_enabled or is_ctrl:
                dx = self._apply_snap(dx, self.grid_size)
                dy = self._apply_snap(dy, self.grid_size)

            if dx == 0 and dy == 0: return

            # Use accumulators to handle floating point deltas from Qt
            self._accum_x += dx
            self._accum_y += dy
            
            # Only signal core if we have at least 1px of movement in Blender space (int)
            blender_dx = int(self._accum_x)
            blender_dy = int(self._accum_y)
            
            if blender_dx != 0 or blender_dy != 0:
                # Subtract the integer part we are sending to core from the accumulators
                self._accum_x -= blender_dx
                self._accum_y -= blender_dy
                
                # Signal to core (inverted Y for Blender)
                self.item_moved_signal.emit(float(blender_dx), float(-blender_dy))

            # Visual movement (smooth in Qt)
            for item in movable_items:
                item.moveBy(dx, dy)
            
            self._drag_start_pos += QtCore.QPointF(dx, dy)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging_items:
            self._is_dragging_items, self._drag_start_pos = False, None
            self._axis_lock = None
            self.interaction_end_signal.emit()
            for item in self.items():
                if isinstance(item, RZElementItem): item._initial_rect = None
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
            
            grid_props = {
                'padding': data.get('grid_padding', 0),
                'gap': data.get('grid_gap', 0),
                'cell_size': data.get('grid_cell_size', 50),
                'cols': data.get('grid_cols', 0)
            }
            
            item.set_data_state(data.get('is_locked_pos', False), data.get('is_locked_size', False), 
                                data.get('image_id', -1), data.get('is_selectable', True), 
                                data.get('text_content', ''), data.get('alignment', 'BOTTOM_LEFT'), 
                                data.get('color', None), grid_props=grid_props)
            item.setVisible(not data.get('is_hidden', False))
            item.set_visual_state(uid in selected_ids, uid == active_id)
            item._is_layout_controlled = False # Reset for layout pass

        for data in elements_data:
            uid, pid = data['id'], data.get('parent_id', -1)
            if uid in self._items_map and pid != -1 and pid in self._items_map:
                item, parent_item = self._items_map[uid], self._items_map[pid]
                if item.parentItem() != parent_item: item.setParentItem(parent_item)
            elif uid in self._items_map and self._items_map[uid].parentItem() is not None:
                self._items_map[uid].setParentItem(None)
        
        # Pass 5: Layout Calculation
        for item in self._items_map.values():
            if item.elem_type == "GRID_CONTAINER":
                children = [c for c in item.childItems() if isinstance(c, RZElementItem)]
                if not children: continue
                
                # Sort by Blender order if possible, here we just use what we have
                container_data = {
                    'width': item.rect().width(),
                    'grid_padding': item.grid_padding,
                    'grid_gap': item.grid_gap,
                    'grid_cell_size': item.grid_cell_size,
                    'grid_cols': item.grid_cols
                }
                
                children_sizes = [(c.rect().width(), c.rect().height()) for c in children]
                offsets = GridSolver.calculate_layout(container_data, len(children), children_sizes)
                
                inner_origin = item.get_inner_origin()
                for i, child in enumerate(children):
                    if i >= len(offsets): break
                    
                    target_tl_x = inner_origin.x() + offsets[i][0]
                    target_tl_y = inner_origin.y() + offsets[i][1]
                    
                    # Adjust for child's anchor
                    off_x, off_y = child.get_anchor_offset(child.rect().width(), child.rect().height(), child.alignment)
                    child.setPos(target_tl_x - off_x, target_tl_y - off_y)
                    
                    child._is_layout_controlled = True

        self.update()

class RZViewportView(QtWidgets.QGraphicsView):
    """
    The actual QGraphicsView for rendering the viewport scene.
    This is the internal view component, wrapped by RZViewportPanel.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RZViewportView")
        self.rz_scene = RZViewportScene()
        self.setScene(self.rz_scene)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        
        self.setAcceptDrops(True)
        
        self._is_panning = False
        self._pan_start_pos = QtCore.QPoint()
        self.parent_window = None 
        
        # Overlay UI
        self.setup_overlay_ui()
        
        self.rz_scene.interaction_start_signal.connect(self._on_interaction_start)
        self.rz_scene.interaction_end_signal.connect(self._on_interaction_end)

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        key = event.key()
        
        # Shift + A: Add Menu
        if key == QtCore.Qt.Key_A and (modifiers & QtCore.Qt.ShiftModifier):
            # Map global cursor to scene
            scene_pos = self.mapToScene(self.mapFromGlobal(QtGui.QCursor.pos()))
            self.open_add_menu(scene_pos)
            event.accept()
            return

        # Ctrl + A: Select All
        elif key == QtCore.Qt.Key_A and (modifiers & QtCore.Qt.ControlModifier):
            items = [i for i in self.scene().items() if isinstance(i, RZElementItem) and i.is_selectable]
            ids = [i.uid for i in items]
            if ids:
                self.rz_scene.selection_changed_signal.emit(ids, None)
            event.accept()
            return
            
        super().keyPressEvent(event)

    def open_add_menu(self, scene_pos):
        """Opens menu to add new elements at the specified scene position."""
        menu = QtWidgets.QMenu(self)
        menu.addSection("Add Element")
        
        types = [
            ("Container", "CONTAINER"),
            ("Grid Container", "GRID_CONTAINER"),
            ("Button", "BUTTON"),
            ("Text", "TEXT"),
            ("Slider", "SLIDER"),
            ("Anchor", "ANCHOR")
        ]
        
        for label, class_type in types:
            action = menu.addAction(label)
            # Use funky closure for the lambda
            action.triggered.connect(lambda _, ct=class_type, sp=scene_pos: self._create_at_pos(ct, sp))
            
        menu.exec(QtGui.QCursor.pos())

    def _create_at_pos(self, class_type, scene_pos):
        # Convert scene Y to Blender Y (inverted)
        bx = scene_pos.x()
        by = -scene_pos.y()
        from .. import core
        core.create_element(class_type, bx, by)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-rzmenu-image-id"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-rzmenu-image-id"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-rzmenu-image-id"):
            data = event.mimeData().data("application/x-rzmenu-image-id")
            try:
                image_id = int(data.data().decode('utf-8'))
                
                # Get drop position in scene
                scene_pos = self.mapToScene(event.position().toPoint())
                
                # Convert to Blender coords (Y is flipped in our UI)
                bx = scene_pos.x()
                by = -scene_pos.y()
                
                from .. import core
                core.create_element_with_image(image_id, bx, by)
                
                event.acceptProposedAction()
            except (ValueError, TypeError):
                event.ignore()
        else:
            super().dropEvent(event)

    def setup_overlay_ui(self):
        self.overlay_container = QtWidgets.QFrame(self)
        self.overlay_container.setObjectName("ViewportOverlay")
        self.overlay_container.setStyleSheet("""
            #ViewportOverlay {
                background-color: rgba(30, 30, 30, 180);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 4px;
            }
            QPushButton { background: transparent; border: none; padding: 4px; color: #BBB; }
            QPushButton:hover { color: #FFF; background: rgba(255,255,255,20); }
        """)
        
        layout = QtWidgets.QHBoxLayout(self.overlay_container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)
        
        self.btn_settings = QtWidgets.QPushButton("⚙")
        self.btn_settings.setToolTip("Viewport Settings")
        self.btn_settings.clicked.connect(self.show_settings_menu)
        layout.addWidget(self.btn_settings)
        
        self.overlay_container.adjustSize()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position overlay at top right
        margin = 10
        self.overlay_container.move(self.width() - self.overlay_container.width() - margin, margin)

    def show_settings_menu(self):
        menu = QtWidgets.QMenu(self)
        
        # Snap Toggle
        act_snap = menu.addAction("Snap Enabled")
        act_snap.setCheckable(True)
        act_snap.setChecked(self.rz_scene.snap_enabled)
        def toggle_snap(checked):
            self.rz_scene.snap_enabled = checked
            self.viewport().update()
        act_snap.triggered.connect(toggle_snap)
        
        menu.addSeparator()
        
        # Grid Size options
        menu.addSection("Grid Size")
        for size in [10, 25, 50, 100, 200]:
            act = menu.addAction(f"{size} px")
            act.setCheckable(True)
            act.setChecked(self.rz_scene.grid_size == size)
            
            # Using lambda with explicit argument capture to avoid loop-scope and signal-argument issues
            def set_grid_size(val):
                self.rz_scene.grid_size = val
                self.rz_scene.update()
                self.viewport().update()
                
            act.triggered.connect(lambda _, s=size: set_grid_size(s))
            
        menu.exec(QtGui.QCursor.pos())

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

    def _find_action_manager(self):
        """Find action_manager by traversing up to the main window."""
        # First try explicit parent_window
        if self.parent_window and hasattr(self.parent_window, "action_manager"):
            return self.parent_window.action_manager
        
        # Traverse up widget hierarchy
        widget = self
        while widget:
            parent = widget.parent()
            if parent is None:
                if hasattr(widget, 'action_manager'):
                    return widget.action_manager
                break
            if hasattr(parent, 'action_manager'):
                return parent.action_manager
            widget = parent
        
        # Fallback: try window()
        try:
            win = self.window()
            if win and hasattr(win, 'action_manager'):
                return win.action_manager
        except:
            pass
        
        return None

    def contextMenuEvent(self, event):
        am = self._find_action_manager()
        if not am:
            return
        
        menu = QtWidgets.QMenu(self)
        def add_op(op_id):
            if op_id in am.q_actions: 
                menu.addAction(am.q_actions[op_id])
        
        hit_element = hasattr(self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform()), 'uid')

        if hit_element:
            menu.addSection("Element"); add_op("rzm.toggle_hide"); add_op("rzm.toggle_lock"); add_op("rzm.toggle_selectable")
            menu.addSeparator(); add_op("rzm.delete")
        else:
            scene_pos = self.mapToScene(event.pos())
            add_menu = menu.addMenu("Add")
            types = [("Container", "CONTAINER"), ("Grid Container", "GRID_CONTAINER"), ("Button", "BUTTON"), ("Text", "TEXT"), ("Slider", "SLIDER"), ("Anchor", "ANCHOR")]
            for label, ct in types:
                act = add_menu.addAction(label)
                act.triggered.connect(lambda _, c=ct, p=scene_pos: self._create_at_pos(c, p))
            
            menu.addSeparator()
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


class RZViewportPanel(RZEditorPanel):
    """
    Container panel for the viewport, following the RZEditorPanel architecture.
    Wraps RZViewportView and exposes its scene for external access.
    
    AUTONOMOUS: Subscribes to SIGNALS.structure_changed, SIGNALS.transform_changed,
    SIGNALS.selection_changed to update itself without window.py intervention.
    """
    
    # Panel Registry Metadata
    PANEL_ID = "VIEWPORT"
    PANEL_NAME = "Viewport"
    PANEL_ICON = "globe"
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RZViewportPanel")
        
        # Create the internal view
        self.view = RZViewportView(self)
        
        # Set up layout - viewport fills the entire panel
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view)
        
        # Connect scene signals to internal handlers
        self.view.rz_scene.item_moved_signal.connect(self._on_item_moved)
        self.view.rz_scene.element_resized_signal.connect(self._on_element_resized)
        self.view.rz_scene.interaction_start_signal.connect(self._on_interaction_start)
        self.view.rz_scene.interaction_end_signal.connect(self._on_interaction_end)
        self.view.rz_scene.selection_changed_signal.connect(self._on_selection_changed)
    
    def _connect_signals(self):
        """Connect to core signals for autonomous updates."""
        SIGNALS.structure_changed.connect(self.refresh_data)
        SIGNALS.transform_changed.connect(self.refresh_data)
        SIGNALS.selection_changed.connect(self._on_global_selection_changed)
        SIGNALS.data_changed.connect(self.refresh_data)
    
    def _disconnect_signals(self):
        """Disconnect from core signals to prevent calls to deleted objects."""
        try:
            SIGNALS.structure_changed.disconnect(self.refresh_data)
        except (RuntimeError, TypeError):
            pass
        try:
            SIGNALS.transform_changed.disconnect(self.refresh_data)
        except (RuntimeError, TypeError):
            pass
        try:
            SIGNALS.selection_changed.disconnect(self._on_global_selection_changed)
        except (RuntimeError, TypeError):
            pass
        try:
            SIGNALS.data_changed.disconnect(self.refresh_data)
        except (RuntimeError, TypeError):
            pass
    
    def refresh_data(self):
        """Fetch and display current viewport data from core."""
        if not self._is_panel_active:
            return
        # Don't refresh during user interaction
        if self.view.rz_scene._is_user_interaction:
            return
        data = core.get_viewport_data()
        ctx = RZContextManager.get_instance().get_snapshot()
        self.view.rz_scene.update_scene(data, ctx.selected_ids, ctx.active_id)
    
    def _on_global_selection_changed(self):
        """Update selection visuals when global selection changes."""
        if not self._is_panel_active:
            return
        ctx = RZContextManager.get_instance().get_snapshot()
        if hasattr(self.view.rz_scene, 'update_selection_visuals'):
            self.view.rz_scene.update_selection_visuals(ctx.selected_ids, ctx.active_id)
    
    def _on_item_moved(self, delta_x, delta_y):
        """Handle element movement from viewport."""
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.move_elements_delta(ctx.selected_ids, delta_x, delta_y, silent=True)
    
    def _on_element_resized(self, uid, x, y, w, h):
        """Handle element resize from viewport."""
        core.resize_element(uid, x, y, w, h, silent=True)
    
    def _on_interaction_start(self):
        """Mark interaction as active."""
        self.view.rz_scene._is_user_interaction = True
    
    def _on_interaction_end(self):
        """Commit changes and broadcast updates to all panels."""
        core.commit_history("RZM Transformation")
        self.view.rz_scene._is_user_interaction = False
        
        # Emit global signals so ALL panels update (including other viewports/outliners)
        SIGNALS.structure_changed.emit()
        SIGNALS.transform_changed.emit()
    
    def _on_selection_changed(self, target_data, modifiers):
        """Handle selection changes from viewport interaction."""
        ctx = RZContextManager.get_instance().get_snapshot()
        current_selection = set(ctx.selected_ids)
        new_selection = current_selection.copy()
        new_active = -1
        
        if isinstance(target_data, list):
            # Box selection
            items_ids = set(target_data)
            if modifiers == 'SHIFT':
                new_selection.update(items_ids)
            elif modifiers == 'CTRL':
                new_selection.difference_update(items_ids)
            else:
                new_selection = items_ids
            if items_ids:
                new_active = list(items_ids)[0]
            elif new_selection:
                new_active = next(iter(new_selection))
        else:
            # Single item click
            clicked_id = target_data
            if clicked_id == -1:
                if modifiers not in ['SHIFT', 'CTRL']:
                    new_selection.clear()
                new_active = -1
            else:
                if modifiers == 'SHIFT':
                    if clicked_id in new_selection:
                        new_selection.remove(clicked_id)
                        new_active = -1 if not new_selection else next(iter(new_selection))
                    else:
                        new_selection.add(clicked_id)
                        new_active = clicked_id
                elif modifiers == 'CTRL':
                    if clicked_id in new_selection:
                        new_selection.remove(clicked_id)
                else:
                    new_selection = {clicked_id}
                    new_active = clicked_id
        
        RZContextManager.get_instance().set_selection(new_selection, new_active)
    
    @property
    def rz_scene(self) -> RZViewportScene:
        """Convenience property to access the scene directly."""
        return self.view.rz_scene
    
    @property
    def parent_window(self):
        """Get the parent window reference from the view."""
        return self.view.parent_window
    
    @parent_window.setter
    def parent_window(self, value):
        """Set the parent window reference on the view."""
        self.view.parent_window = value
    
    def set_alt_mode(self, active: bool):
        """Proxy method to set alt mode on the view."""
        self.view.set_alt_mode(active)
    
    def update_theme_styles(self):
        """Update viewport theme."""
        if hasattr(self.view, 'rz_scene'):
            self.view.rz_scene._init_background()
            self.view.rz_scene.update()