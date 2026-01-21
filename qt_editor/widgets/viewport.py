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
from ..core.logic import FormulaEvaluator

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
        
        # State for cumulative drag
        self._start_mouse_pos = None

    def hoverEnterEvent(self, event):
        if self.parentItem() and (getattr(self.parentItem(), 'is_locked_pos', False) or getattr(self.parentItem(), 'is_locked_size', False)):
            return
        self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(self.normal_brush)
        super().hoverLeaveEvent(event)

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.rect().adjusted(-4, -4, 4, 4))
        return path

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRoundedRect(self.rect(), 2, 2)

    def mousePressEvent(self, event):
        if self.parentItem() and (getattr(self.parentItem(), 'is_locked_pos', False) or getattr(self.parentItem(), 'is_locked_size', False)):
            event.ignore()
            return
        
        # Record start position for cumulative math
        self._start_mouse_pos = event.scenePos()
        self.scene().interaction_start_signal.emit()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._start_mouse_pos is not None:
            # Calculate Total Delta from start
            total_delta = event.scenePos() - self._start_mouse_pos
            self.parentItem().handle_resize(self.handle_type, total_delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._start_mouse_pos = None
        self.parentItem().finalize_resize() # Clear initial state
        self.scene().interaction_end_signal.emit()
        super().mouseReleaseEvent(event)


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
        self.pos_is_formula = False
        self.size_is_formula = False
        
        # Grid properties
        self.grid_padding = 0
        self.grid_gap = 0
        self.grid_cell_size = 50
        self.grid_cols = 0
        
        # Interaction state (Cumulative)
        self._initial_rect = None     # (x, y, w, h) visual rect
        self._initial_pos = None      # (x, y) scene pos
        self._aspect_ratio = 1.0

        self.setFlags(
            QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption | 
            QtWidgets.QGraphicsItem.ItemIsSelectable
        )

    def get_inner_origin(self):
        r = self.rect()
        return r.topLeft()

    def get_anchor_offset(self, w, h, alignment):
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

    def finalize_resize(self):
        """Called when mouse is released to clear init state."""
        self._initial_rect = None
        self._initial_pos = None

    def handle_resize(self, h_type, total_delta):
        """
        Handles resize using cumulative delta to prevent snap-deadlock.
        total_delta: distance from the mouse press start position.
        """
        if self.is_locked_size or self.size_is_formula: return
        
        scene = self.scene()
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        is_ctrl = modifiers & QtCore.Qt.ControlModifier
        is_shift = modifiers & QtCore.Qt.ShiftModifier
        
        # 1. Initialize Snapshot on first move
        if self._initial_rect is None:
            self._initial_rect = self.rect()
            self._initial_pos = self.pos() # Scene position (Anchor)
            self._aspect_ratio = self._initial_rect.width() / max(self._initial_rect.height(), 1)

        # 2. Helper to get raw dimensions
        # Current Anchor in Scene coords
        init_ax, init_ay = self._initial_pos.x(), self._initial_pos.y()
        
        # Visual Rect (relative to anchor, e.g., -50, -50 if Center)
        vr = self._initial_rect
        
        # Calculate Absolute edges in Scene Space
        abs_left = init_ax + vr.left()
        abs_right = init_ax + vr.right()
        abs_top = init_ay + vr.top()
        abs_bottom = init_ay + vr.bottom()
        
        # Apply Delta to the moving edges
        dx, dy = total_delta.x(), total_delta.y()
        
        if h_type in (RZHandleItem.LEFT, RZHandleItem.TOP_LEFT, RZHandleItem.BOTTOM_LEFT):
            abs_left += dx
        elif h_type in (RZHandleItem.RIGHT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_RIGHT):
            abs_right += dx

        if h_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
            abs_top += dy
        elif h_type in (RZHandleItem.BOTTOM, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT):
            abs_bottom += dy

        # 3. Apply Snap to the Moving Edges (Absolute Grid Snap)
        grid_size = scene.grid_size if (scene.snap_enabled or is_ctrl) else 1
        
        def snap(val): return round(val / grid_size) * grid_size

        if scene.snap_enabled or is_ctrl:
            if h_type in (RZHandleItem.LEFT, RZHandleItem.TOP_LEFT, RZHandleItem.BOTTOM_LEFT):
                abs_left = snap(abs_left)
            elif h_type in (RZHandleItem.RIGHT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_RIGHT):
                abs_right = snap(abs_right)
            
            if h_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
                abs_top = snap(abs_top)
            elif h_type in (RZHandleItem.BOTTOM, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT):
                abs_bottom = snap(abs_bottom)

        # 4. Recalculate Size (ensure min size)
        MIN_SIZE = 5
        
        # Handle Aspect Ratio Constraint (Shift) - Simplified for Center/Corner
        # Doing aspect ratio properly with absolute snapping is tricky, skipping for now to prioritize snap stability
        
        new_w = abs_right - abs_left
        new_h = abs_bottom - abs_top
        
        # Ensure positive size (flip if inverted)
        # Note: If user drags left handle past right handle, we usually clamp.
        if new_w < MIN_SIZE: 
            # Clamp the moving edge back
            if h_type in (RZHandleItem.LEFT, RZHandleItem.TOP_LEFT, RZHandleItem.BOTTOM_LEFT):
                abs_left = abs_right - MIN_SIZE
            else:
                abs_right = abs_left + MIN_SIZE
            new_w = MIN_SIZE
            
        if new_h < MIN_SIZE:
            if h_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
                abs_top = abs_bottom - MIN_SIZE
            else:
                abs_bottom = abs_top + MIN_SIZE
            new_h = MIN_SIZE

        # 5. Recalculate Scene Position (Anchor) based on Alignment
        # We know the new absolute bounding box (abs_left, abs_top, new_w, new_h)
        # We need to find where the Anchor Point is within this box based on self.alignment
        
        offsets = {
            "TOP_LEFT": (0, 0),
            "TOP_CENTER": (0.5, 0),
            "TOP_RIGHT": (1.0, 0),
            "CENTER_LEFT": (0, 0.5),
            "CENTER": (0.5, 0.5),
            "CENTER_RIGHT": (1.0, 0.5),
            "BOTTOM_LEFT": (0, 1.0),
            "BOTTOM_CENTER": (0.5, 1.0),
            "BOTTOM_RIGHT": (1.0, 1.0),
        }
        rel_x, rel_y = offsets.get(self.alignment, (0, 1.0)) # Default Bottom Left
        
        new_anchor_x = abs_left + (new_w * rel_x)
        new_anchor_y = abs_top + (new_h * rel_y)
        
        # 6. Update Visuals
        # Move the item to the new anchor position
        self.setPos(new_anchor_x, new_anchor_y)
        
        # Update the visual rect (which draws relative to 0,0 based on anchor)
        self.update_visual_rect(new_w, new_h)
        
        # 7. Emit Signal to Core (Convert back to Blender Coords)
        bx, by = core.to_qt_coords(new_anchor_x, new_anchor_y)
        scene.element_resized_signal.emit(self.uid, bx, by, int(new_w), int(new_h))

    def set_data_state(self, locked_pos, locked_size, img_id, is_selectable, text_content, alignment, color=None, grid_props=None, pos_is_formula=False, size_is_formula=False):
        self.is_locked_pos, self.is_locked_size = locked_pos, locked_size
        self.pos_is_formula, self.size_is_formula = pos_is_formula, size_is_formula
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

        # Formula Indicator
        if self.pos_is_formula or self.size_is_formula:
            f_rect = QtCore.QRect(rect.x() + rect.width() - 14, rect.y() + rect.height() - 14, 10, 10)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(0, 255, 100, 150))
            painter.drawEllipse(f_rect)

class RZViewportScene(QtWidgets.QGraphicsScene):
    item_moved_signal = QtCore.Signal(float, float) 
    element_resized_signal = QtCore.Signal(int, int, int, int, int)
    selection_changed_signal = QtCore.Signal(object, object)
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._is_user_interaction = False
        self._is_dragging_items = False
        self._drag_start_pos = None
        self.is_alt_mode = False
        self._items_map = {} 
        self.setSceneRect(-10000, -10000, 20000, 20000)
        
        # Grid settings
        self.grid_size = 20
        self.snap_enabled = False
        
        # Accumulators
        self._accum_x = 0.0
        self._accum_y = 0.0
        
        # --- CYCLIC SELECTION STATE ---
        self._cycle_stack = []      # Список ID элементов под курсором для перебора
        self._cycle_index = 0       # Текущий индекс в стеке
        self._last_click_pos = None # Позиция последнего клика для проверки сдвига

    def _apply_snap(self, value, step):
        if step <= 0: return value
        return round(value / step) * step

    def drawBackground(self, painter, rect):
        """Infinite Grid Drawing."""
        t = get_current_theme()
        bg_color = QtGui.QColor(t.get('vp_bg', '#1E1E1E'))
        painter.fillRect(rect, bg_color)

        grid_color = QtGui.QColor(t.get('vp_grid_color', 'rgba(255, 255, 255, 30)'))
        
        left, right = int(rect.left()), int(rect.right())
        top, bottom = int(rect.top()), int(rect.bottom())

        step = self.grid_size
        major_step = step * 5
        
        painter.setPen(QtGui.QPen(grid_color, 0.5))
        first_x = left - (left % step)
        first_y = top - (top % step)

        for x in range(first_x, right + step, step):
            if x % major_step != 0: painter.drawLine(x, top, x, bottom)
        for y in range(first_y, bottom + step, step):
            if y % major_step != 0: painter.drawLine(left, y, right, y)

        major_color = grid_color.lighter(150)
        major_color.setAlpha(min(grid_color.alpha() * 2, 255))
        painter.setPen(QtGui.QPen(major_color, 1.0))
        
        first_major_x = left - (left % major_step)
        first_major_y = top - (top % major_step)
        for x in range(first_major_x, right + major_step, major_step):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_major_y, bottom + major_step, major_step):
            painter.drawLine(left, y, right, y)
        
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

        # 1. Handle Gizmo Interaction
        item = self.itemAt(event.scenePos(), QtGui.QTransform())
        if isinstance(item, RZHandleItem):
            self.interaction_start_signal.emit()
            super().mousePressEvent(event)
            return

        # 2. Element Selection Logic
        modifier_str = 'CTRL' if event.modifiers() & QtCore.Qt.ControlModifier else 'SHIFT' if event.modifiers() & QtCore.Qt.ShiftModifier else None
        
        # Check if we clicked in the same spot (allow 5px jitter)
        is_same_spot = False
        if self._last_click_pos:
            dist = (event.scenePos() - self._last_click_pos).manhattanLength()
            if dist < 5.0:
                is_same_spot = True
        
        # Get raw items under cursor
        raw_items = self.items(event.scenePos())
        # Strict filter: Must be RZElementItem AND selectable
        valid_items = [i for i in raw_items if isinstance(i, RZElementItem) and i.is_selectable]
        
        if valid_items:
            event.accept() # Stop propagation to prevent rubberband
            
            target_uid = -1
            
            # --- ROBUST CYCLIC LOGIC ---
            if is_same_spot and self._cycle_stack:
                # REPEAT CLICK: Use the FROZEN stack from previous click.
                # This ignores Z-index changes caused by selection highlighting.
                self._cycle_index = (self._cycle_index + 1) % len(self._cycle_stack)
                target_uid = self._cycle_stack[self._cycle_index]
            else:
                # NEW CLICK: Build a new stack
                self._cycle_stack = [i.uid for i in valid_items]
                self._cycle_index = 0
                target_uid = self._cycle_stack[0]
                self._last_click_pos = event.scenePos()

            # Emit Selection
            self.selection_changed_signal.emit(target_uid, modifier_str)
            
            # --- INIT DRAG ---
            # Find the item object corresponding to target_uid to check locks
            target_item = self._items_map.get(target_uid)
            
            if target_item and not target_item.is_locked_pos and not getattr(target_item, "_is_layout_controlled", False) and not target_item.pos_is_formula:
                self._is_dragging_items = True
                self._drag_start_pos = event.scenePos()
                self._accum_x = 0.0
                self._accum_y = 0.0
                
                # Store INITIAL positions for Absolute Snapping
                # We need to snapshot where EVERY selected item is right now
                selected_items = [i for i in self.selectedItems() if isinstance(i, RZElementItem)]
                # If target wasn't selected yet (Qt delay), include it manually
                if target_item not in selected_items:
                    selected_items.append(target_item)
                    
                self._initial_item_positions = {it: it.pos() for it in selected_items}
                
                self.interaction_start_signal.emit()
        else:
            # Clicked on empty space or unselectable items
            if modifier_str is None:
                self.selection_changed_signal.emit(-1, None)
            
            # Reset Cycle State
            self._cycle_stack = []
            self._last_click_pos = None
            
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_alt_mode:
             super().mouseMoveEvent(event); return

        if self._is_dragging_items and self._drag_start_pos and hasattr(self, '_initial_item_positions'):
            current_pos = event.scenePos()
            
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            is_ctrl = modifiers & QtCore.Qt.ControlModifier # Snap
            is_shift = modifiers & QtCore.Qt.ShiftModifier  # Axis Lock

            # Identify movable items (filter locked ones from the cached snapshot)
            movable_items = []
            for item in self._initial_item_positions:
                if not item.is_locked_pos and not getattr(item, "_is_layout_controlled", False) and not item.pos_is_formula:
                    movable_items.append(item)
            
            if not movable_items: return

            # Calculate raw offset from START of drag
            total_dx = current_pos.x() - self._drag_start_pos.x()
            total_dy = current_pos.y() - self._drag_start_pos.y()

            # --- 1. AXIS LOCK ---
            if is_shift:
                if abs(total_dx) > abs(total_dy): total_dy = 0
                else: total_dx = 0

            # --- 2. ABSOLUTE SNAPPING ---
            # We snap the LEADER (first item) to the grid, 
            # and move everyone else by the same delta.
            leader = movable_items[0]
            start_pos = self._initial_item_positions[leader]
            
            # Where would the leader be without snap?
            target_x = start_pos.x() + total_dx
            target_y = start_pos.y() + total_dy
            
            if self.snap_enabled or is_ctrl:
                # Snap the absolute target coordinate
                final_x = self._apply_snap(target_x, self.grid_size)
                final_y = self._apply_snap(target_y, self.grid_size)
            else:
                final_x = target_x
                final_y = target_y
            
            # Calculate the effective delta needed to reach this position from CURRENT visual pos
            # Actually, simpler: Calculate absolute new pos for everyone based on Leader's delta
            
            # Leader's total required shift from start
            leader_shift_x = final_x - start_pos.x()
            leader_shift_y = final_y - start_pos.y()
            
            # --- 3. BLENDER SYNC (ACCUMULATOR) ---
            # We need to send incremental deltas to Blender core
            # Calculate shift from LAST PROCESSED frame
            if not hasattr(self, '_last_processed_shift'):
                self._last_processed_shift = QtCore.QPointF(0, 0)
            
            step_dx = leader_shift_x - self._last_processed_shift.x()
            step_dy = leader_shift_y - self._last_processed_shift.y()
            
            if step_dx == 0 and step_dy == 0: return

            self._accum_x += step_dx
            self._accum_y += step_dy
            
            blender_dx = int(self._accum_x)
            blender_dy = int(self._accum_y)
            
            if blender_dx != 0 or blender_dy != 0:
                self._accum_x -= blender_dx
                self._accum_y -= blender_dy
                
                # Signal Core
                bdx, bdy = core.to_blender_delta(blender_dx, blender_dy)
                self.item_moved_signal.emit(float(bdx), float(bdy))
                
                # Update processed tracker by the amount we actually sent
                self._last_processed_shift += QtCore.QPointF(blender_dx, blender_dy)

            # --- 4. VISUAL UPDATE ---
            # Move all items relative to their INITIAL start position
            # This prevents floating point drift over time
            for item in movable_items:
                item_start = self._initial_item_positions[item]
                new_pos_x = item_start.x() + leader_shift_x
                new_pos_y = item_start.y() + leader_shift_y
                item.setPos(new_pos_x, new_pos_y)

        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging_items:
            self._is_dragging_items = False
            self._drag_start_pos = None
            if hasattr(self, '_initial_item_positions'): del self._initial_item_positions
            if hasattr(self, '_last_processed_shift'): del self._last_processed_shift
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
        
        # 1. Sync items pool
        self._sync_items_pool(elements_data)
        
        # 2. Resolve layouts
        resolved_layout = FormulaEvaluator.resolve_layout(elements_data)
        
        # 3. Update items
        self._update_items_state(elements_data, resolved_layout, selected_ids, active_id)
        
        # 4. Hierarchy
        self._rebuild_hierarchy(elements_data)
        
        # 5. Positioning
        self._resolve_positioning(elements_data, resolved_layout)
        
        # 6. Grid Layouts
        self._refresh_layout_engines()
        
        self.update()

    def _sync_items_pool(self, elements_data):
        incoming_ids = {d['id'] for d in elements_data}
        current_ids = set(self._items_map.keys())
        cache = ImageCache.instance()

        for data in elements_data:
            if data.get('image_id', -1) != -1: 
                cache.pre_cache_image(data['image_id'])

        for uid in (current_ids - incoming_ids):
            if uid in self._items_map and shiboken6.isValid(self._items_map[uid]):
                self.removeItem(self._items_map[uid])
            if uid in self._items_map: 
                del self._items_map[uid]

    def _update_items_state(self, elements_data, resolved_layout, selected_ids, active_id):
        for data in elements_data:
            uid = data['id']
            layout = resolved_layout.get(uid, {})
            rw = layout.get('w', data['width'])
            rh = layout.get('h', data['height'])

            item = self._items_map.get(uid)
            if not item or not shiboken6.isValid(item):
                item = RZElementItem(uid, rw, rh, data['name'], data.get('class_type', 'CONTAINER'))
                self.addItem(item)
                self._items_map[uid] = item
            else:
                item.name = data['name']
                item.elem_type = data.get('class_type', 'CONTAINER')

            item.update_size(rw, rh)
            
            grid_props = {
                'padding': data.get('grid_padding', 0),
                'gap': data.get('grid_gap', 0),
                'cell_size': data.get('grid_cell_size', 50),
                'cols': data.get('grid_cols', 0)
            }
            
            item.set_data_state(
                data.get('is_locked_pos', False), data.get('is_locked_size', False), 
                data.get('image_id', -1), data.get('is_selectable', True), 
                data.get('text_content', ''), data.get('alignment', 'BOTTOM_LEFT'), 
                data.get('color', None), grid_props=grid_props,
                pos_is_formula=data.get('pos_is_formula', False),
                size_is_formula=data.get('size_is_formula', False)
            )
            item.setVisible(not data.get('is_hidden', False))
            item.set_visual_state(uid in selected_ids, uid == active_id)
            item._is_layout_controlled = False 

    def _rebuild_hierarchy(self, elements_data):
        for data in elements_data:
            uid, pid = data['id'], data.get('parent_id', -1)
            if uid in self._items_map and pid != -1 and pid in self._items_map:
                item, parent_item = self._items_map[uid], self._items_map[pid]
                if item.parentItem() != parent_item: 
                    item.setParentItem(parent_item)
            elif uid in self._items_map and self._items_map[uid].parentItem() is not None:
                self._items_map[uid].setParentItem(None)

    def _resolve_positioning(self, elements_data, resolved_layout):
        for data in elements_data:
            uid = data['id']
            item = self._items_map[uid]
            
            layout = resolved_layout.get(uid, {})
            rx = layout.get('x', data['pos_x'])
            ry = layout.get('y', data['pos_y'])
            
            qx, qy = core.to_qt_coords(rx, ry)
            
            parent = item.parentItem()
            if parent and isinstance(parent, RZElementItem):
                p_layout = resolved_layout.get(parent.uid, {})
                px = p_layout.get('x', 0)
                py = p_layout.get('y', 0)
                pqx, pqy = core.to_qt_coords(px, py)
                item.setPos(qx - pqx, qy - pqy)
            else:
                item.setPos(qx, qy)

    def _refresh_layout_engines(self):
        for item in self._items_map.values():
            if item.elem_type == "GRID_CONTAINER":
                children = [c for c in item.childItems() if isinstance(c, RZElementItem)]
                if not children: continue
                
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
        bx, by = core.to_qt_coords(scene_pos.x(), scene_pos.y())
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
                bx, by = core.to_qt_coords(scene_pos.x(), scene_pos.y())
                
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
        from .utils import find_action_manager
        return find_action_manager(self)

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
        bx, by = core.to_qt_coords(scene_pos.x(), scene_pos.y())
        RZContextManager.get_instance().update_input(global_pos, (bx, by), area="VIEWPORT")
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