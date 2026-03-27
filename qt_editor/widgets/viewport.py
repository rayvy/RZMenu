# RZMenu/qt_editor/widgets/viewport.py
"""
Viewport Panel - Visual canvas for element manipulation.
Autonomous panel that subscribes to core.SIGNALS for data updates.
"""
import os
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6
from .. import core
from ..core.signals import SIGNALS
from ..core import blender_bridge
from ..systems.layout import GridSolver
from ..systems.smart_snap import SmartSnapSystem
from ..utils.image_cache import ImageCache
from ..context import RZContextManager
from ..context.states import RZInteractionState
from .lib.theme import get_current_theme
from .panel_base import RZEditorPanel
from ..core.logic import FormulaEvaluator
from .lib.animations import SpringAnimation, LiquidFillEffect

HANDLE_SIZE = 8

class RZFontManager:
    """
    Centralized cache for font metrics to prevent expensive re-instantiation.
    """
    _instance = None

    def __init__(self):
        self._metrics_cache = {} # font_family -> RZFontAtlasMetrics

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_metrics_for_family(self, font_family):
        if font_family not in self._metrics_cache:
            self._metrics_cache[font_family] = RZFontAtlasMetrics(font_family)
        return self._metrics_cache[font_family]

class RZFontAtlasMetrics:
    """
    Emulates the atlas metrics used in the shader.
    The constants here align with the user's font generation script:
    FONT_SIZE = 128, ATLAS_BASE_CELL_SIZE = 16, ATLAS_SCALE = 8 -> 128
    """
    def __init__(self, font_family):
        self.font = QtGui.QFont(font_family)
        # We need the metrics for the base font size used in the atlas
        self.font.setPixelSize(128)
        self.f_metrics = QtGui.QFontMetricsF(self.font)
        self.cell_size = 128.0
        self._glyph_cache = {}

    def get(self, char):
        if char not in self._glyph_cache:
            rect = self.f_metrics.boundingRect(char)
            # offX / offY in PIL/Shader terms are left/top of bbox relative to baseline
            # QFontMetricsF.leftBearing gives us the X offset
            self._glyph_cache[char] = type('GlyphMetrics', (), {
                'advance': self.f_metrics.horizontalAdvance(char),
                'offX': rect.left(),
                'offY': rect.top(),
                'glyphW': rect.width(),
                'glyphH': rect.height()
            })
        return self._glyph_cache[char]

class RZHandleItem(QtWidgets.QGraphicsRectItem):
    TOP_LEFT, TOP, TOP_RIGHT, RIGHT, BOTTOM_RIGHT, BOTTOM, BOTTOM_LEFT, LEFT = range(8)

    def __init__(self, handle_type, target_item):
        super().__init__(0, 0, HANDLE_SIZE, HANDLE_SIZE) # Parent is None (Scene Root)
        self.handle_type = handle_type
        self.target_item = target_item # The item this handle manipulates

        t = get_current_theme()
        self.normal_brush = QtGui.QBrush(QtGui.QColor(t.get('vp_handle', '#FFFFFF')))
        self.hover_brush = QtGui.QBrush(QtGui.QColor(t.get('vp_active', '#FF8C00')))

        self.setBrush(self.normal_brush)
        self.setPen(QtGui.QPen(QtGui.QColor(t.get('vp_handle_border', '#000000')), 1))
        # Rayvich: Fix Blocking - Handles are now Scene Roots with max Z.
        self.setZValue(1e9)

        cursors = {
            self.TOP_LEFT: QtCore.Qt.SizeFDiagCursor, self.BOTTOM_RIGHT: QtCore.Qt.SizeFDiagCursor,
            self.TOP_RIGHT: QtCore.Qt.SizeBDiagCursor, self.BOTTOM_LEFT: QtCore.Qt.SizeBDiagCursor,
            self.TOP: QtCore.Qt.SizeVerCursor, self.BOTTOM: QtCore.Qt.SizeVerCursor,
            self.LEFT: QtCore.Qt.SizeHorCursor, self.RIGHT: QtCore.Qt.SizeHorCursor,
        }
        self.setCursor(cursors.get(handle_type, QtCore.Qt.ArrowCursor))
        self.setAcceptHoverEvents(True)
        self._start_mouse_pos = None

    def hoverEnterEvent(self, event):
        if self.target_item and (getattr(self.target_item, 'is_locked_pos', False) or getattr(self.target_item, 'is_locked_size', False)):
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
        if self.target_item and (getattr(self.target_item, 'is_locked_pos', False) or getattr(self.target_item, 'is_locked_size', False)):
            event.ignore(); return

        self._start_mouse_pos = event.scenePos()

        # Prepare Smart Snap targets (exclude self's target)
        scene = self.scene()
        if scene:
            scene.prepare_smart_snap(exclude_items=[self.target_item])
            scene.interaction_start_signal.emit()

        event.accept()

    def mouseMoveEvent(self, event):
        if self._start_mouse_pos is not None:
            total_delta = event.scenePos() - self._start_mouse_pos
            self.target_item.handle_resize(self.handle_type, total_delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._start_mouse_pos = None
        self.target_item.finalize_resize()

        scene = self.scene()
        if scene:
            scene.clear_smart_snap()
            scene.interaction_end_signal.emit()

        super().mouseReleaseEvent(event)


class RZElementItem(QtWidgets.QGraphicsRectItem):
    # Статическая переменная для хранения семейства шрифта
    _custom_font_family = None

    def __init__(self, uid, w, h, name, elem_type="CONTAINER"):
        super().__init__(0, 0, w, h)
        self.uid = uid
        self.elem_type = elem_type
        self.name = name

        # --- PHASE 2.2: ANIMATION LAYER ---
        self._tilt_spring = SpringAnimation(stiffness=200, damping=20, parent=None)
        self._tilt_spring.value_changed.connect(self._on_tilt_changed)

        self._select_fill = LiquidFillEffect(None)
        self._select_fill.update_requested.connect(self.update)
        self._is_selected_state = False

        self._drag_velocity = QtCore.QPointF(0, 0)
        self._last_drag_pos = None

        self._is_hovered_state = False
        self._is_pressed_state = False
        self.setAcceptHoverEvents(True)

        self._init_data()
        self.create_handles()

    def _init_data(self):
        self.text_content = self.name
        self.text_id = ""  # Поле для хранения text_id
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
        
        self.grid_padding = 0
        self.grid_gap = 0
        self.grid_cell_size = 50
        self.grid_cols = 0
        
        self._initial_rect = None
        self._initial_pos = None
        self._aspect_ratio = 1.0

        self.setFlags(QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption | QtWidgets.QGraphicsItem.ItemIsSelectable | QtWidgets.QGraphicsItem.ItemSendsScenePositionChanges)
        
        # Инициализация шрифта
        self._ensure_font_loaded()
        self._is_drop_target = False

    def _on_tilt_changed(self, angle):
        self.setRotation(angle)
        self.update_handles_pos()
        
    def set_target_tilt(self, angle):
        self._tilt_spring.set_target(angle)

    def set_selection_progress(self, progress):
        self._select_fill.set_progress(progress)

    def hoverEnterEvent(self, event):
        self._is_hovered_state = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered_state = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._is_pressed_state = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_pressed_state = False
        self.update()
        super().mouseReleaseEvent(event)

    def set_drop_highlight(self, active):
        if self._is_drop_target != active:
            self._is_drop_target = active
            self.update()

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemSelectedChange:
            self._is_selected_state = bool(value)
            # Liquid fill removed from default selection per user feedback
            # self.set_selection_progress(1.0 if self._is_selected_state else 0.0)
        if change == QtWidgets.QGraphicsItem.ItemScenePositionHasChanged:
            self.update_handles_pos()
        return super().itemChange(change, value)

    @classmethod
    def _ensure_font_loaded(cls):
        """Загрузка кастомного шрифта bahnscrift.ttf"""
        if cls._custom_font_family is not None:
            return

        # Ищем шрифт в папке qt_editor (на уровень выше от текущего файла widgets/viewport.py)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        editor_dir = os.path.dirname(current_dir)
        font_path = os.path.join(editor_dir, "bahnschrift.ttf")

        if os.path.exists(font_path):
            font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    cls._custom_font_family = families[0]
                    # print(f"[VIEWPORT] Font loaded: {cls._custom_font_family}")
        else:
            print(f"[VIEWPORT] Font not found at: {font_path}")



    def get_inner_origin(self): return self.rect().topLeft()

    def get_anchor_offset(self, w, h, alignment):
        offsets = {
            "TOP_LEFT": (0, 0), "TOP_CENTER": (-w/2, 0), "TOP_RIGHT": (-w, 0),
            "CENTER_LEFT": (0, -h/2), "CENTER": (-w/2, -h/2), "CENTER_RIGHT": (-w, -h/2),
            "BOTTOM_LEFT": (0, -h), "BOTTOM_CENTER": (-w/2, -h), "BOTTOM_RIGHT": (-w, -h),
        }
        return offsets.get(alignment, (0, 0))

    def update_visual_rect(self, w, h):
        dx, dy = self.get_anchor_offset(w, h, self.alignment)
        self.setRect(dx, dy, w, h)
        self.update_handles_pos()

    def create_handles(self):
        if self.handles: return
        scene = self.scene()
        if not scene: return
        
        for h_type in range(8):
            h_item = RZHandleItem(h_type, self) # Parent is None
            scene.addItem(h_item)
            self.handles[h_type] = h_item
            
        self.update_handles_pos()

    def update_handles_pos(self):
        if not self.handles: return
        
        # Calculate Global (Scene) Position for handles
        # because they are now Scene Roots.
        local_r = self.rect()
        # We need points in scene space
        x, y, w, h = local_r.x(), local_r.y(), local_r.width(), local_r.height()
        hs, hh = HANDLE_SIZE, HANDLE_SIZE / 2
        
        # Local offsets for handles
        positions_local = [
            (x - hh, y - hh), (x + w/2 - hh, y - hh), (x + w - hh, y - hh),
            (x + w - hh, y + h/2 - hh), (x + w - hh, y + h - hh), (x + w/2 - hh, y + h - hh),
            (x - hh, y + h - hh), (x - hh, y + h/2 - hh)
        ]
        
        for h_type, local_pos in enumerate(positions_local):
            if h_type in self.handles:
                # Map local point to scene
                scene_pt = self.mapToScene(QtCore.QPointF(*local_pos))
                self.handles[h_type].setPos(scene_pt)

    def set_drop_highlight(self, active):
        if self._is_drop_target != active:
            self._is_drop_target = active
            # Liquid fill is ONLY for drop target highlights now
            self.set_selection_progress(1.0 if active else 0.0)
            self.update()

    def set_handles_visible(self, visible):
        if visible:
             if not self.handles: self.create_handles()
        
        if self.handles:
            for handle in self.handles.values(): 
                handle.setVisible(visible)
            if visible:
                self.update_handles_pos() # Ensure alignment on show

    def cleanup_handles(self):
        """Removes handles from the scene explicitly."""
        scene = self.scene()
        if scene and self.handles:
            for handle in self.handles.values():
                if shiboken6.isValid(handle):
                    scene.removeItem(handle)
        self.handles.clear()

    def finalize_resize(self):
        self._initial_rect = None
        self._initial_pos = None

    def handle_resize(self, h_type, total_delta):
        if self.is_locked_size or self.size_is_formula: return
        
        scene = self.scene()
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        is_ctrl = modifiers & QtCore.Qt.ControlModifier
        is_shift = modifiers & QtCore.Qt.ShiftModifier
        
        if self._initial_rect is None:
            self._initial_rect = self.rect()
            self._initial_pos = self.pos()
            self._aspect_ratio = self._initial_rect.width() / max(self._initial_rect.height(), 1)

        init_ax, init_ay = self._initial_pos.x(), self._initial_pos.y()
        vr = self._initial_rect
        abs_left = init_ax + vr.left()
        abs_right = init_ax + vr.right()
        abs_top = init_ay + vr.top()
        abs_bottom = init_ay + vr.bottom()
        
        dx, dy = total_delta.x(), total_delta.y()
        
        # Apply delta
        if h_type in (RZHandleItem.LEFT, RZHandleItem.TOP_LEFT, RZHandleItem.BOTTOM_LEFT):
            abs_left += dx
        elif h_type in (RZHandleItem.RIGHT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_RIGHT):
            abs_right += dx

        if h_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
            abs_top += dy
        elif h_type in (RZHandleItem.BOTTOM, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT):
            abs_bottom += dy

        # Calculate current dimensions for logic below
        new_w = abs_right - abs_left
        new_h = abs_bottom - abs_top

        # --- Alt Modifier: Aspect Ratio Preservation ---
        if modifiers & QtCore.Qt.AltModifier:
            is_diag = h_type in (RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT)
            if is_diag and self._aspect_ratio > 0:
                # Constrain height based on width and initial aspect ratio
                new_h = new_w / self._aspect_ratio
                # Adjust bottom/top based on handle type to maintain the logic
                if h_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
                    abs_top = abs_bottom - new_h
                else:
                    abs_bottom = abs_top + new_h
            else:
                # For non-diagonal handles, maybe we don't force it? 
                # User usually expects diagonal for aspect ratio.
                pass

        # --- SMART SNAP & GRID SNAP LOGIC ---
        # We need to decide whether to snap specific edges
        snap_sys = scene.snap_sys
        targets = scene.get_smart_snap_targets()
        guides = []
        
        # Helper to process an edge
        def process_edge(value, orientation, do_snap_grid):
            # 1. Try Smart Snap
            smart_val, guide = snap_sys.calculate_edge_snap(value, orientation, targets)
            if smart_val is not None:
                guides.append(guide)
                return smart_val
            # 2. Try Grid Snap
            if do_snap_grid:
                grid = scene.grid_size
                return round(value / grid) * grid
            return value

        do_snap = (scene.snap_enabled or is_ctrl)
        
        # Update X Edges
        if h_type in (RZHandleItem.LEFT, RZHandleItem.TOP_LEFT, RZHandleItem.BOTTOM_LEFT):
            abs_left = process_edge(abs_left, 0, do_snap)
        elif h_type in (RZHandleItem.RIGHT, RZHandleItem.TOP_RIGHT, RZHandleItem.BOTTOM_RIGHT):
            abs_right = process_edge(abs_right, 0, do_snap)
            
        # Update Y Edges
        if h_type in (RZHandleItem.TOP, RZHandleItem.TOP_LEFT, RZHandleItem.TOP_RIGHT):
            abs_top = process_edge(abs_top, 1, do_snap)
        elif h_type in (RZHandleItem.BOTTOM, RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM_RIGHT):
            abs_bottom = process_edge(abs_bottom, 1, do_snap)

        # Update visual guides
        scene.set_smart_guides(guides)

        # --- Apply Min Size ---
        MIN_SIZE = 5
        new_w = abs_right - abs_left
        new_h = abs_bottom - abs_top
        
        if new_w < MIN_SIZE: 
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

        # --- Finalize Geometry ---
        offsets = {
            "TOP_LEFT": (0, 0), "TOP_CENTER": (0.5, 0), "TOP_RIGHT": (1.0, 0),
            "CENTER_LEFT": (0, 0.5), "CENTER": (0.5, 0.5), "CENTER_RIGHT": (1.0, 0.5),
            "BOTTOM_LEFT": (0, 1.0), "BOTTOM_CENTER": (0.5, 1.0), "BOTTOM_RIGHT": (1.0, 1.0),
        }
        rel_x, rel_y = offsets.get(self.alignment, (0, 1.0))
        
        new_anchor_x = abs_left + (new_w * rel_x)
        new_anchor_y = abs_top + (new_h * rel_y)
        
        self.setPos(new_anchor_x, new_anchor_y)
        self.update_visual_rect(new_w, new_h)
        
        bx, by = core.to_qt_coords(new_anchor_x, new_anchor_y)
        scene.element_resized_signal.emit(self.uid, bx, by, int(new_w), int(new_h))

    # Обновили сигнатуру: добавлен аргумент text_id, text_align и order
    def set_data_state(self, locked_pos, locked_size, img_id, is_selectable, text_content, alignment, text_id=None, text_align="LEFT", color=None, grid_props=None, pos_is_formula=False, size_is_formula=False, order=0, image_blending_mode='NONE', flip_x=False, flip_y=False):
        self.is_locked_pos, self.is_locked_size = locked_pos, locked_size
        self.pos_is_formula, self.size_is_formula = pos_is_formula, size_is_formula
        self.flip_x, self.flip_y = flip_x, flip_y
        self.image_id, self.is_selectable = img_id, is_selectable
        self.text_content = text_content if text_content else self.name
        self.text_id = text_id if text_id is not None else "TEST" # Сохраняем text_id
        self.text_align = text_align
        self.order = order  # Сохраняем порядок в массиве для Z-index
        self.alignment = alignment
        self.custom_color = color
        self.image_blending_mode = image_blending_mode
        
        if grid_props:
            self.grid_padding = grid_props.get('padding', 0)
            self.grid_gap = grid_props.get('gap', 0)
            self.grid_cell_size = grid_props.get('cell_size', 50)
            self.grid_cols = grid_props.get('cols', 0)

        # PHANTOM BEHAVIOR: 
        # setEnabled(False) makes item "invisible" to mouse events in the scene.
        self.setEnabled(is_selectable)
        
        # We manually manage opacity to show it's unselectable
        self.setOpacity(0.5 if not is_selectable else 1.0)
        self.update()

    def set_visual_state(self, is_selected, is_active):
        if self.isSelected() != is_selected: self.setSelected(is_selected)
        self.is_active = is_active

        # Base Z-value from array order (higher = drawn later = on top)
        base_z = getattr(self, 'order', 0)

        # State modifiers
        if is_active: z_val = base_z + 1000  # Active on top
        elif is_selected: z_val = base_z + 500  # Selected above normal
        else: z_val = base_z  # Normal elements by order

        self.setZValue(z_val)
        self.set_handles_visible(is_selected and not self.is_locked_size)
        self.update() 
    
    def update_size(self, w, h):
        self.update_visual_rect(w, h)
        self.update() 
    
    def paint(self, painter, option, widget):
        rect = self.rect()
        t = get_current_theme()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # --- PHASE 2.4: MICRO-ANIMATIONS (HOVER/PRESSED) ---
        if self._is_pressed_state:
            # Subtle "pressed" fill
            press_col = QtGui.QColor(t.get('vp_active', '#FF8C00'))
            press_col.setAlpha(40)
            painter.setBrush(press_col)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(rect)
        elif self._is_hovered_state and not self._is_selected_state:
            # Hover glow/highlight
            hover_col = QtGui.QColor(t.get('vp_active', '#FF8C00'))
            hover_col.setAlpha(20)
            painter.setBrush(hover_col)
            painter.setPen(QtGui.QPen(QtGui.QColor(t.get('vp_active', '#FF8C00')), 1.0, QtCore.Qt.DashLine))
            painter.drawRect(rect)

        # --- PHASE 2.2: SELECTION FILL (LIQUID) ---
        if self._is_selected_state:
            select_col = QtGui.QColor(t.get('vp_active', '#FF8C00'))
            select_col.setAlpha(60) # Soft underwater feel
            self._select_fill.draw(painter, QtCore.QRectF(rect), select_col)

        # --- ОТРИСОВКА ТЕКСТА (WYSIWYG v3.3) ---
        # --- ОТРИСОВКА ТЕКСТА (WYSIWYG v3.3 - SHADER MATCH) ---
        if self.elem_type == 'TEXT':
            text = self.text_id if self.text_id else self.name
            if not text: return

            # 1. Init Metrics & Font
            font_family = self._custom_font_family if self._custom_font_family else "Arial"
            metrics = RZFontManager.instance().get_metrics_for_family(font_family)
            chars = list(text)[:32]

            # 2. Scale Calculation (HEIGHT BASED)
            # Shader: scale = (size.y * ScreenRes.y) / cs;
            # Qt: rect.height() is already (size.y * ScreenRes.y) in pixels
            base_scale = rect.height() / metrics.cell_size

            # 3. Calculate Raw Content Width (in 128px space)
            total_w = 0.0
            first_off = 0.0
            if chars:
                first_m = metrics.get(chars[0])
                first_off = first_m.offX
                for i in range(len(chars) - 1):
                    total_w += metrics.get(chars[i]).advance
                last_m = metrics.get(chars[-1])
                # Shader logic for last char width
                total_w += last_m.offX + last_m.glyphW - first_off

            # 4. Squeeze Logic (Auto-Fit)
            # Shader: if (currentTextWidth > inputLimitWidth) squeeze...
            limit_px = rect.width()
            current_px = total_w * base_scale
            squeeze = 1.0
            
            if limit_px > 1.0 and current_px > limit_px:
                squeeze = limit_px / current_px

            # 5. Alignment Shift calculation
            align_map = {"LEFT": 0, "CENTER": 1, "RIGHT": 2}
            align = align_map.get(self.text_align, 0)
            
            shift_128 = 0.0
            if align == 1: # Center
                shift_128 = (first_off * 2.0 + total_w) * 0.5
            elif align == 2: # Right
                shift_128 = first_off + total_w

            # 6. Drawing
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            
            # Color
            text_color = QtGui.QColor(t.get('text_bright', '#FFF'))
            if self.custom_color and len(self.custom_color) >= 3:
                r, g, b = [int(c*255) for c in self.custom_color[:3]]
                text_color = QtGui.QColor(r, g, b)
            painter.setPen(text_color)
            
            # Apply Transform:
            # We translate to the Start Point, then Scale the coordinate system.
            # This allows us to draw using 128px metrics directly and get the "Squished" glyph look correctly.
            
            # X start: rect.left() - (shift converted to pixels)
            # But since we will scale X by (base_scale * squeeze), we apply shift in local space
            
            painter.translate(rect.left(), rect.top())
            painter.scale(base_scale * squeeze, base_scale)
            
            # Font setup (use the large 128px font from metrics)
            painter.setFont(metrics.font)

            cur_x_128 = 0.0
            ref_a = metrics.get('A') # Reference for baseline alignment
            
            # Draw Loop
            for char in chars:
                m = metrics.get(char)
                
                # Y Position Calculation (Shader match)
                # Shader: baseAdj = (ref.offY + ref.glyphH + (128.0/7.5) - (m.offY + m.glyphH))
                # The constant 17.066 comes from 128.0 / 7.5
                base_adj = (ref_a.offY + ref_a.glyphH + 17.0666 - (m.offY + m.glyphH))
                
                # Coordinates in 128px space
                # X: Current cursor - Alignment Shift + Char Offset
                draw_x = cur_x_128 - shift_128 + m.offX
                draw_y = base_adj 
                
                # Draw
                target_rect = QtCore.QRectF(draw_x, draw_y, m.glyphW, m.glyphH)
                painter.drawText(target_rect, QtCore.Qt.AlignCenter | QtCore.Qt.TextDontClip, char)
                
                cur_x_128 += m.advance

            painter.restore()

            # Selection Border (PHASE 2.2: Modern Glow)
            if self.isSelected():
                 painter.setPen(QtGui.QPen(QtGui.QColor(t.get('vp_selection', '#FFF')), 1.5))
                 painter.setBrush(QtCore.Qt.NoBrush)
                 painter.drawRect(rect)
            
            return

        has_image = False
        if self.image_id != -1:
            pix = ImageCache.instance().get_pixmap(self.image_id)
            # print(f"[VIEWPORT] Element {self.name} (ID: {self.uid}), image_id: {self.image_id}")
            # print(f"[VIEWPORT] Rect: {rect}, Size: {rect.width()}x{rect.height()}")
            if pix:
                if not pix.isNull():
                    painter.save()
                    if getattr(self, "flip_x", False) or getattr(self, "flip_y", False):
                        sx = -1 if getattr(self, "flip_x", False) else 1
                        sy = -1 if getattr(self, "flip_y", False) else 1
                        cx = rect.x() + rect.width() / 2.0
                        cy = rect.y() + rect.height() / 2.0
                        painter.translate(cx, cy)
                        painter.scale(sx, sy)
                        painter.translate(-cx, -cy)
                    
                    painter.drawPixmap(rect.toRect(), pix)
                    painter.restore()
                    has_image = True
                else:
                    pass
                    # print(f"[VIEWPORT] Pixmap is null, skipping draw")
            else:
                pass
                # print(f"[VIEWPORT] No pixmap in cache for image_id {self.image_id}")

        if self.custom_color and len(self.custom_color) >= 3:
            r, g, b = [int(c*255) for c in self.custom_color[:3]]
            a = int(self.custom_color[3]*255) if len(self.custom_color) > 3 else 255
            bg_color = QtGui.QColor(r, g, b, a)
        else:
            color_key = f"vp_type_{self.elem_type.lower()}"
            bg_color = QtGui.QColor(t.get(color_key, "rgba(50,50,50,200)"))
        
        if has_image and not self.custom_color: bg_color.setAlpha(30)
        if self.is_locked_pos or self.is_locked_size: bg_color = bg_color.darker(120)
        
        # --- BLENDING RENDERING ---
        if has_image:
            mode = getattr(self, "image_blending_mode", "NONE")
            if mode == "OVERLAY":
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_Overlay)
                painter.fillRect(rect, bg_color)
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            elif mode == "COLOR_HUE":
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_Hue)
                painter.fillRect(rect, bg_color)
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            elif mode == "NONE":
                # Only rgba from texture, skip color fill
                pass
            else:
                # Fallback to normal (legacy behavior)
                painter.fillRect(rect, bg_color)
        else:
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

        painter.setPen(QtGui.QPen(QtGui.QColor(t.get('vp_handle_bg', 'rgba(255, 255, 255, 180)')), 1.0))
        painter.drawLine(-4, 0, 4, 0); painter.drawLine(0, -4, 0, 4)

        text_rect = rect.adjusted(5, 5, -5, -5)
        painter.setPen(QtGui.QColor(t.get('text_bright', '#FFF')))
        
        # Сбрасываем шрифт на дефолтный для отображения имени элемента (не Text)
        painter.setFont(QtGui.QFont())
        # painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.name)
        
        if self.is_locked_pos or self.is_locked_size:
            lock_txt = "🔒" if self.is_locked_pos and self.is_locked_size else "🔒P" if self.is_locked_pos else "🔒S"
            painter.setPen(QtGui.QColor(t.get('vp_locked', '#F00')))
            painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop, lock_txt)

        if self._is_drop_target:
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 255, 0), 3))
            painter.drawRect(rect.adjusted(2, 2, -2, -2))

        if self.pos_is_formula or self.size_is_formula:
            f_rect = QtCore.QRect(rect.x() + rect.width() - 14, rect.y() + rect.height() - 14, 10, 10)
            painter.setPen(QtCore.Qt.NoPen); painter.setBrush(QtGui.QColor(0, 255, 100, 150)); painter.drawEllipse(f_rect)

class RZViewportScene(QtWidgets.QGraphicsScene):
    item_moved_signal = QtCore.Signal(float, float) 
    element_resized_signal = QtCore.Signal(int, int, int, int, int)
    selection_changed_signal = QtCore.Signal(object, object)
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.snap_sys = SmartSnapSystem() # The Brain
        self._cached_targets = []
        self._guide_lines = []
        
        self._is_user_interaction = False
        self._is_dragging_items = False
        self._drag_start_pos = None
        self.is_alt_mode = False
        self._items_map = {} 
        self.setSceneRect(-10000, -10000, 20000, 20000)
        self.grid_size = 20
        self.snap_enabled = False
        self._accum_x = 0.0
        self._accum_y = 0.0
        self._cycle_stack = []
        self._last_click_pos = None
        self._active_id = -1

        # --- PHASE 2.2: DRAG PHYSICS ---
        self._last_drag_pos = None
        self._drag_velocity = QtCore.QPointF(0, 0)
        self._velocity_smooth = 0.7 

    def prepare_smart_snap(self, exclude_items):
        """Called on interaction start to cache possible targets."""
        self._cached_targets = self.snap_sys.get_targets(self, exclude_items)
        self._guide_lines = []

    def get_smart_snap_targets(self): return self._cached_targets
    
    def set_smart_guides(self, guides):
        self._guide_lines = guides
        self.update() # Trigger redraw for foreground

    def clear_smart_snap(self):
        self._cached_targets = []
        self._guide_lines = []
        self.update()

    def drawForeground(self, painter, rect):
        if self._guide_lines:
            pen = QtGui.QPen(QtGui.QColor("#FF00FF"), 1, QtCore.Qt.DashLine)
            painter.setPen(pen)
            for line in self._guide_lines:
                # Draw long lines for visibility
                painter.drawLine(line)

    def _apply_snap(self, value, step):
        if step <= 0: return value
        return round(value / step) * step

    def drawBackground(self, painter, rect):
        t = get_current_theme()
        bg_color = QtGui.QColor(t.get('vp_bg', '#1E1E1E'))
        painter.fillRect(rect, bg_color)
        
        # Performance Layer: Adaptive Level of Detail
        # Avoid drawing thousands of lines when zoomed out.
        current_zoom = painter.transform().m11()
        
        # Don't draw grid at all if zoomed out extremely far
        if current_zoom < 0.05:
            self._draw_axes(painter, rect)
            return

        grid_color = QtGui.QColor(t.get('vp_grid_color', 'rgba(255, 255, 255, 30)'))
        left, right = int(rect.left()), int(rect.right())
        top, bottom = int(rect.top()), int(rect.bottom())
        step = self.grid_size
        major_step = step * 5
        
        # Level 1: Full Grid (Zoom >= 0.6)
        if current_zoom >= 0.6:
            painter.setPen(QtGui.QPen(grid_color, 0.5))
            first_x = left - (left % step); first_y = top - (top % step)
            for x in range(first_x, right + step, step):
                if x % major_step != 0: painter.drawLine(x, top, x, bottom)
            for y in range(first_y, bottom + step, step):
                if y % major_step != 0: painter.drawLine(left, y, right, y)

        # Level 2: Major Grid Only (Zoom >= 0.15)
        if current_zoom >= 0.15:
            major_color = grid_color.lighter(150)
            major_color.setAlpha(min(grid_color.alpha() * 2, 255))
            painter.setPen(QtGui.QPen(major_color, 1.0))
            first_major_x = left - (left % major_step); first_major_y = top - (top % major_step)
            for x in range(first_major_x, right + major_step, major_step): 
                painter.drawLine(x, top, x, bottom)
            for y in range(first_major_y, bottom + major_step, major_step): 
                painter.drawLine(left, y, right, y)
        
        self._draw_axes(painter, rect)

    def _draw_axes(self, painter, rect):
        left, right = rect.left(), rect.right()
        top, bottom = rect.top(), rect.bottom()
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 80), 1.5))
        if left <= 0 <= right: painter.drawLine(0, top, 0, bottom)
        if top <= 0 <= bottom: painter.drawLine(left, 0, right, 0)

    def _init_background(self): self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton: return 
        if self.is_alt_mode:
            super().mousePressEvent(event); return

        # PRIORITY: Search for a handle at the click position.
        # Handles now have Z=10000, but we manually check to be sure.
        clicked_items = self.items(event.scenePos())
        handle_item = next((i for i in clicked_items if isinstance(i, RZHandleItem)), None)
        
        if handle_item:
            # Let the scene handle it normally - because it's on top (Z=10000), 
            # super().mousePressEvent should correctly pick it and start the grabber.
            super().mousePressEvent(event)
            if event.isAccepted():
                self.interaction_start_signal.emit()
                return

        modifier_str = 'CTRL' if event.modifiers() & QtCore.Qt.ControlModifier else 'SHIFT' if event.modifiers() & QtCore.Qt.ShiftModifier else None
        
        is_same_spot = False
        if self._last_click_pos:
            dist = (event.scenePos() - self._last_click_pos).manhattanLength()
            if dist < 5.0: is_same_spot = True
        
        # Rayvich: Possible bugs - Ensure we skip disabled/unselectable items completely
        valid_items = [i for i in clicked_items if isinstance(i, RZElementItem) and i.is_selectable and i.isEnabled()]
        
        if valid_items:
            event.accept()
            target_uid = -1
            if is_same_spot and self._cycle_stack:
                current_idx = -1
                for idx, uid in enumerate(self._cycle_stack):
                    if uid == self._active_id: current_idx = idx; break
                
                next_idx = (current_idx + 1) % len(self._cycle_stack)
                target_uid = self._cycle_stack[next_idx]
            else:
                self._cycle_stack = [i.uid for i in valid_items]
                target_uid = self._cycle_stack[0]
                self._last_click_pos = event.scenePos()

            # Rayvich Multi-Drag Fix: Check if target is already in selection
            ctx = RZContextManager.get_instance().get_snapshot()
            if target_uid in ctx.selected_ids:
                # Keep current selection, but update active ID
                RZContextManager.get_instance().set_selection(ctx.selected_ids, target_uid)
            else:
                # Standard selection behavior
                self.selection_changed_signal.emit(target_uid, modifier_str)
            
            target_item = self._items_map.get(target_uid)
            if target_item and not target_item.is_locked_pos and not getattr(target_item, "_is_layout_controlled", False) and not target_item.pos_is_formula:
                self._is_dragging_items = True
                self._drag_start_pos = event.scenePos()
                self._last_drag_pos = event.scenePos()
                self._drag_velocity = QtCore.QPointF(0, 0)
                self._accum_x = 0.0; self._accum_y = 0.0
                
                # Rayvich: Multi-Drag Fix - Use context manager's selection as source of truth
                ctx = RZContextManager.get_instance().get_snapshot()
                selected_items = [self._items_map[uid] for uid in ctx.selected_ids if uid in self._items_map]
                if target_item and target_item not in selected_items:
                    selected_items.append(target_item)
                
                # PARENTING FIX: Filter selected_items to only move root elements of the selection.
                # Moving a parent already moves the child.
                movable_roots = []
                for it in selected_items:
                    # If any ancestor of 'it' is also in selected_items, then 'it' is NOT a root for this move.
                    has_parent_in_selection = False
                    curr = it.parentItem()
                    while curr:
                        if curr in selected_items:
                            has_parent_in_selection = True; break
                        curr = curr.parentItem()
                    if not has_parent_in_selection:
                        movable_roots.append(it)
                
                self._initial_item_positions = {it: it.pos() for it in movable_roots}
                self._all_movable_in_selection = selected_items # For visual feedback consistency if needed
                
                # CACHE TARGETS FOR MOVE
                self.prepare_smart_snap(exclude_items=selected_items)
                
                self.interaction_start_signal.emit()
        else:
            if modifier_str is None: self.selection_changed_signal.emit(-1, None)
            self._cycle_stack = []
            self._last_click_pos = None
            super().mousePressEvent(event)

    def clear_smart_snap_guides_only(self):
        self._guide_lines = []
        self.update()

    def mouseMoveEvent(self, event):
        if self.is_alt_mode: super().mouseMoveEvent(event); return

        if self._is_dragging_items and self._drag_start_pos and hasattr(self, '_initial_item_positions'):
            current_pos = event.scenePos()
            
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            is_ctrl = modifiers & QtCore.Qt.ControlModifier
            is_alt = modifiers & QtCore.Qt.AltModifier
            is_shift = modifiers & QtCore.Qt.ShiftModifier

            movable_items = []
            for item in self._initial_item_positions:
                # Root protection check already done in mousePressEvent, but we verify active state here
                if not item.is_locked_pos and not getattr(item, "_is_layout_controlled", False) and not item.pos_is_formula:
                    movable_items.append(item)
            if not movable_items: return

            # Рассчитываем смещение мыши
            total_dx = current_pos.x() - self._drag_start_pos.x()
            total_dy = current_pos.y() - self._drag_start_pos.y()

            if is_shift:
                if abs(total_dx) > abs(total_dy): total_dy = 0
                else: total_dx = 0

            # Лидер группы для расчета снаппинга
            leader = movable_items[0]
            start_pos_local = self._initial_item_positions[leader]
            
            # Целевая позиция лидера БЕЗ снаппинга (LOCAL)
            raw_target_local_x = start_pos_local.x() + total_dx
            raw_target_local_y = start_pos_local.y() + total_dy
            
            # --- CONVERT TO GLOBAL FOR SNAPPING ---
            # We need to know where this local point is in Global Space.
            # Only the parent's transform matters.
            parent_item = leader.parentItem()
            if parent_item:
                # Map the local point to scene
                raw_global_pt = parent_item.mapToScene(QtCore.QPointF(raw_target_local_x, raw_target_local_y))
            else:
                raw_global_pt = QtCore.QPointF(raw_target_local_x, raw_target_local_y)
                
            raw_target_global_x = raw_global_pt.x()
            raw_target_global_y = raw_global_pt.y()
            
            # --- ОПРЕДЕЛЕНИЕ РЕЖИМА СНАППИНГА ---
            modes = {
                'grid': False,
                'adhesion': False,
                'alignment': False
            }
            
            if is_ctrl:
                if is_alt:
                    # Ctrl + Alt = Только Alignment (Оси)
                    modes['alignment'] = True
                else:
                    # Ctrl = Grid + Adhesion (Прилипание)
                    modes['grid'] = True
                    modes['adhesion'] = True

            # Формируем гипотетический Rect в новой позиции (GLOBAL)
            # Используем normalized(), чтобы избежать проблем с отрицательными размерами
            lr = leader.rect().normalized()
            hypothetical_rect_global = QtCore.QRectF(
                raw_target_global_x + lr.x(), 
                raw_target_global_y + lr.y(), 
                lr.width(), 
                lr.height()
            )
            
            # --- ВЫЗОВ SOLVER (Global Space) ---
            self.clear_smart_snap_guides_only()
            
            # Если хотя бы один режим включен, считаем
            if any(modes.values()):
                final_global_x, final_global_y, guides = self.snap_sys.solve_snap(
                    hypothetical_rect_global, 
                    self._cached_targets, 
                    self.grid_size, 
                    modes
                )
                self.set_smart_guides(guides)
            else:
                final_global_x, final_global_y = raw_target_global_x, raw_target_global_y

            # --- CONVERT BACK TO LOCAL DELTA ---
            if parent_item:
                final_local_pt = parent_item.mapFromScene(QtCore.QPointF(final_global_x, final_global_y))
            else:
                final_local_pt = QtCore.QPointF(final_global_x, final_global_y)
                
            final_local_x = final_local_pt.x()
            final_local_y = final_local_pt.y()

            # --- ПРИМЕНЕНИЕ ---
            # Рассчитываем итоговую дельту для всей группы (LOCAL SPACE)
            leader_shift_x = final_local_x - start_pos_local.x()
            leader_shift_y = final_local_y - start_pos_local.y()
            
            # Remove incremental Blender updates (Causes Drift/Snap-back)
            # We now commit only on MouseRelease.
            
            # Визуальное обновление
            for item in movable_items:
                item_start = self._initial_item_positions[item]
                new_pos = QtCore.QPointF(item_start.x() + leader_shift_x, item_start.y() + leader_shift_y)
                item.setPos(new_pos)

            # --- PHASE 2.4: REFINED FLYING PAPER PHYSICS ---
            if hasattr(self, '_last_drag_pos') and self._last_drag_pos:
                dist = (current_pos - self._last_drag_pos).manhattanLength()
                vx = current_pos.x() - self._last_drag_pos.x()
                
                # Smooth velocity tracker
                self._drag_velocity.setX(self._drag_velocity.x() * (1.0 - self._velocity_smooth) + vx * self._velocity_smooth)
                
                # Threshold check: only tilt if moving fast enough (5.0 px per frame)
                is_fast = dist > 5.0
                tilt_angle = max(-15.0, min(15.0, self._drag_velocity.x() * 0.5)) if is_fast else 0.0
                
                # Apply tilt and hide handles if tilt is significant
                ctx = RZContextManager.get_instance().get_snapshot()
                handles_visible = abs(tilt_angle) < 5.0
                
                for uid in ctx.selected_ids:
                    it = self._items_map.get(uid)
                    if it and hasattr(it, 'set_target_tilt'):
                        it.set_target_tilt(tilt_angle)
                        # Hide handles during large tilts to prevent Gizmo detachment
                        if hasattr(it, 'set_handles_visible'):
                            it.set_handles_visible(handles_visible and not it.is_locked_size)
            
            self._last_drag_pos = current_pos
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging_items:
            # --- PHASE 2.2: RESET PHYSICS ---
            ctx = RZContextManager.get_instance().get_snapshot()
            for uid in ctx.selected_ids:
                it = self._items_map.get(uid)
                if it and hasattr(it, 'set_target_tilt'):
                    it.set_target_tilt(0.0)

            self._is_dragging_items = False
            self._drag_start_pos = None
            self._last_drag_pos = None
            self._drag_velocity = QtCore.QPointF(0, 0)
            
            # --- COMMIT BATCH UPDATE ---
            if hasattr(self, '_initial_item_positions') and self._initial_item_positions:
                pos_data = {}
                movable_items = []
                # Re-verify items are valid
                for item in self._initial_item_positions:
                    if shiboken6.isValid(item):
                        movable_items.append(item)
                
                # Collect final local positions
                for item in movable_items:
                    # RZMenu usually stores integer positions
                    # item.pos() returns Local coordinates (Qt Space: Y Down)
                    # We MUST convert to Blender Space (Y Up) before saving.
                    qt_pos = item.pos()
                    bx, by = core.to_blender_coords(qt_pos.x(), qt_pos.y())
                    
                    px = int(bx)
                    py = int(by)
                    pos_data[item.uid] = (px, py)
                
                if pos_data:
                    # Pass mode='LOCAL' because we read item.pos() (Local)
                    core.set_multiple_element_positions(pos_data, mode='LOCAL')
            
            if hasattr(self, '_initial_item_positions'): del self._initial_item_positions
            if hasattr(self, '_last_processed_shift'): del self._last_processed_shift
            self.clear_smart_snap()
            self.interaction_end_signal.emit()
            for item in self.items():
                if isinstance(item, RZElementItem): item._initial_rect = None
        elif self._is_user_interaction:
             self.interaction_end_signal.emit()
        super().mouseReleaseEvent(event)

    def update_selection_visuals(self, selected_ids, active_id):
        if self._is_user_interaction: return
        self._active_id = active_id
        for uid, item in self._items_map.items():
            item.set_visual_state(uid in selected_ids, uid == active_id)

    def update_scene(self, elements_data, selected_ids, active_id):
        if self._is_user_interaction: return
        self._active_id = active_id
        self._sync_items_pool(elements_data)
        resolved_layout = FormulaEvaluator.resolve_layout(elements_data)
        self._update_items_state(elements_data, resolved_layout, selected_ids, active_id)
        self._rebuild_hierarchy(elements_data)
        self._resolve_positioning(elements_data, resolved_layout)
        self._refresh_layout_engines()
        self.update()

    def _sync_items_pool(self, elements_data):
        incoming_ids = {d['id'] for d in elements_data}
        current_ids = set(self._items_map.keys())
        cache = ImageCache.instance()
        for data in elements_data:
            if data.get('image_id', -1) != -1: cache.pre_cache_image(data['image_id'])
        for uid in (current_ids - incoming_ids):
            item = self._items_map.get(uid)
            if item and shiboken6.isValid(item):
                if hasattr(item, 'cleanup_handles'):
                    item.cleanup_handles()
                self.removeItem(item)
            if uid in self._items_map: del self._items_map[uid]

        # GHOST GIZMO SAFETY: Cleanup any handles that lost their targets
        all_scene_items = self.items()
        for it in all_scene_items:
            if hasattr(it, 'target_item'):
                t_item = getattr(it, 'target_item', None)
                if not t_item or not shiboken6.isValid(t_item) or t_item.uid not in incoming_ids:
                    self.removeItem(it)

    def _update_items_state(self, elements_data, resolved_layout, selected_ids, active_id):
        for data in elements_data:
            uid = data['id']
            layout = resolved_layout.get(uid, {})
            rw = layout.get('w', data['width'])
            rh = layout.get('h', data['height'])
            item = self._items_map.get(uid)
            if not item or not shiboken6.isValid(item):
                item = RZElementItem(uid, rw, rh, data['name'], data.get('class_type', 'CONTAINER'))
                self.addItem(item); self._items_map[uid] = item
            else:
                item.name = data['name']; item.elem_type = data.get('class_type', 'CONTAINER')
            item.update_size(rw, rh)
            grid_props = {'padding': data.get('grid_padding', 0), 'gap': data.get('grid_gap', 0), 'cell_size': data.get('grid_cell_size', 50), 'cols': data.get('grid_cols', 0)}
            
            # UPDATED: Passing text_id and order to set_data_state
            item.set_data_state(
                data.get('is_locked_pos', False),
                data.get('is_locked_size', False),
                data.get('image_id', -1),
                data.get('is_selectable', True),
                data.get('text_content', ''),
                data.get('alignment', 'BOTTOM_LEFT'),
                text_id=data.get('text_id', ''),
                text_align=data.get('text_align', 'LEFT'),
                color=data.get('color', None),
                grid_props=grid_props,
                pos_is_formula=data.get('pos_is_formula', False),
                size_is_formula=data.get('size_is_formula', False),
                order=data.get('order', 0),
                image_blending_mode=data.get('image_blending_mode', 'NONE'),
                flip_x=data.get('flip_x', False),
                flip_y=data.get('flip_y', False)
            )
            
            item.setVisible(not data.get('is_hidden', False))
            item.set_visual_state(uid in selected_ids, uid == active_id)
            item._is_layout_controlled = False
            if uid == active_id: self._active_id = uid

    def _rebuild_hierarchy(self, elements_data):
        for data in elements_data:
            uid, pid = data['id'], data.get('parent_id', -1)
            if uid in self._items_map and pid != -1 and pid in self._items_map:
                item, parent_item = self._items_map[uid], self._items_map[pid]
                if item.parentItem() != parent_item: item.setParentItem(parent_item)
            elif uid in self._items_map and self._items_map[uid].parentItem() is not None:
                self._items_map[uid].setParentItem(None)

    def _resolve_positioning(self, elements_data, resolved_layout):
        for data in elements_data:
            uid = data['id']
            item = self._items_map[uid]
            layout = resolved_layout.get(uid, {})
            rx = layout.get('x', data['pos_x']); ry = layout.get('y', data['pos_y'])
            qx, qy = core.to_qt_coords(rx, ry)
            # Rayvich: Possible bugs - If parent's global pos in resolved_layout is missing, 
            # we fallback to 0 which causes "teleportation". 
            # Ensure resolved_layout is always complete.
            parent = item.parentItem()
            if parent and isinstance(parent, RZElementItem):
                p_layout = resolved_layout.get(parent.uid, {})
                px = p_layout.get('x', 0); py = p_layout.get('y', 0)
                pqx, pqy = core.to_qt_coords(px, py)
                # Precision check: floats are used now, but sub-pixel mismatch might still occur
                item.setPos(qx - pqx, qy - pqy)
            else: item.setPos(qx, qy)

    def _refresh_layout_engines(self):
        for item in self._items_map.values():
            if item.elem_type == "GRID_CONTAINER":
                children = [c for c in item.childItems() if isinstance(c, RZElementItem)]
                if not children: continue
                container_data = {'width': item.rect().width(), 'grid_padding': item.grid_padding, 'grid_gap': item.grid_gap, 'grid_cell_size': item.grid_cell_size, 'grid_cols': item.grid_cols}
                children_sizes = [(c.rect().width(), c.rect().height()) for c in children]
                offsets = GridSolver.calculate_layout(container_data, len(children), children_sizes)
                inner_origin = item.get_inner_origin()
                for i, child in enumerate(children):
                    if i >= len(offsets): break
                    target_tl_x = inner_origin.x() + offsets[i][0]; target_tl_y = inner_origin.y() + offsets[i][1]
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
        
        is_shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        is_ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        is_alt = bool(modifiers & QtCore.Qt.AltModifier)

        # Shift + A: Add Menu
        if key == QtCore.Qt.Key_A and is_shift and not is_ctrl:
            scene_pos = self.mapToScene(self.mapFromGlobal(QtGui.QCursor.pos()))
            self.open_add_menu(scene_pos)
            event.accept(); return

        # Ctrl + A: Select All
        elif key == QtCore.Qt.Key_A and is_ctrl and not is_shift:
            items = [i for i in self.scene().items() if isinstance(i, RZElementItem) and i.is_selectable]
            ids = [i.uid for i in items]
            if ids: self.rz_scene.selection_changed_signal.emit(ids, None)
            event.accept(); return

        # H / Alt+H: Hide / Unhide
        elif key == QtCore.Qt.Key_H:
            am = self._find_action_manager()
            if am:
                op_id = "rzm.unhide_all" if is_alt else "rzm.toggle_hide"
                if op_id in am.q_actions: am.q_actions[op_id].trigger()
            event.accept(); return
            
        # L: Lock
        elif key == QtCore.Qt.Key_L:
            am = self._find_action_manager()
            if am:
                op_id = "rzm.toggle_lock"
                if op_id in am.q_actions: am.q_actions[op_id].trigger()
            event.accept(); return

        # Delete / Backspace
        elif key in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            am = self._find_action_manager()
            if am and "rzm.delete" in am.q_actions: am.q_actions["rzm.delete"].trigger()
            event.accept(); return
            
        # Clipboard Operations
        if is_ctrl:
            am = self._find_action_manager()
            if not am: return super().keyPressEvent(event)

            # C: Copy
            if key == QtCore.Qt.Key_C:
                if "rzm.copy" in am.q_actions: am.q_actions["rzm.copy"].trigger()
                event.accept(); return
            
            # V / Ctrl+Shift+V: Paste
            elif key == QtCore.Qt.Key_V:
                if is_shift:
                    # Paste in Place (No offset)
                    from ..core import clipboard
                    clipboard.paste_elements(offset=0)
                else:
                    if "rzm.paste" in am.q_actions: am.q_actions["rzm.paste"].trigger()
                event.accept(); return
                
            # D / Ctrl+Shift+D: Duplicate
            elif key == QtCore.Qt.Key_D:
                if is_shift:
                    # Duplicate in Place (No offset)
                    ctx = RZContextManager.get_instance().get_snapshot()
                    if ctx.selected_ids:
                        from ..core import structure
                        structure.duplicate_elements(list(ctx.selected_ids), offset=0)
                else:
                    if "rzm.duplicate" in am.q_actions: am.q_actions["rzm.duplicate"].trigger()
                event.accept(); return

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

    def _get_element_at(self, pos):
        """Find the most appropriate RZElementItem at position, prioritizing nested content items."""
        scene_pos = self.mapToScene(pos)
        items = self.rz_scene.items(scene_pos)
        
        # 1. Look for non-container elements first (Content)
        for q_item in items:
            it = q_item
            while it:
                if isinstance(it, RZElementItem):
                    if it.elem_type not in ["CONTAINER", "GRID_CONTAINER", "ANCHOR"]:
                        return it
                    break # Found an RZElementItem but it's a structural container, check next hit
                it = it.parentItem()
        
        # 2. Fallback to the top-most RZElementItem regardless of type
        for q_item in items:
            it = q_item
            while it:
                if isinstance(it, RZElementItem):
                    return it
                it = it.parentItem()
                    
        return None

    def _create_at_pos(self, class_type, scene_pos):
        bx, by = core.to_blender_coords(scene_pos.x(), scene_pos.y())
        
        # Determine parent: 
        # 1. Start with currently active element (if any)
        ctx = RZContextManager.get_instance().get_snapshot()
        parent_id = ctx.active_id
        
        # 2. If clicking on empty space but in isolation mode, the isolated Page is the parent
        view_pos = self.mapFromScene(scene_pos)
        hovered_item = self._get_element_at(view_pos)
        
        if not hovered_item:
            isolated_id = RZContextManager.get_instance().isolated_tab_id
            if isolated_id != -1:
                parent_id = isolated_id
        else:
            # If clicked ON an item, that item is the parent (Hierarchy-based)
            parent_id = hovered_item.uid
            
        core.create_element(class_type, bx, by, parent_id=parent_id)
        # Emit signal to update all panels
        from ..core.signals import SIGNALS
        SIGNALS.structure_changed.emit()

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        # Проверяем ВСЕ поддерживаемые типы
        if (mime.hasUrls() or 
            mime.hasFormat("application/x-rzmenu-image-id") or 
            mime.hasFormat("application/x-rzmenu-template")): # <--- ВАЖНО
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        mime = event.mimeData()
        if (mime.hasUrls() or 
            mime.hasFormat("application/x-rzmenu-image-id") or 
            mime.hasFormat("application/x-rzmenu-template")): 
            event.acceptProposedAction()
            
            # --- Smart DnD Highlight ---
            item = self._get_element_at(event.pos())
            
            # Update hover_id in context manager
            ctx = RZContextManager.get_instance()
            target_uid = item.uid if item else -1
            ctx.set_hover_id(target_uid)
            
            # Reset previous highlight if target changed
            if hasattr(self, '_last_dnd_item') and self._last_dnd_item != item:
                if self._last_dnd_item and shiboken6.isValid(self._last_dnd_item):
                    if hasattr(self._last_dnd_item, 'set_drop_highlight'):
                        self._last_dnd_item.set_drop_highlight(False)
            
            # Set new highlight
            if item and (mime.hasUrls() or mime.hasFormat("application/x-rzmenu-image-id")):
                item.set_drop_highlight(True)
                self._last_dnd_item = item
            else:
                self._last_dnd_item = None
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        # Clear highlight when leaving viewport
        if hasattr(self, '_last_dnd_item') and self._last_dnd_item:
            if shiboken6.isValid(self._last_dnd_item):
                if hasattr(self._last_dnd_item, 'set_drop_highlight'):
                    self._last_dnd_item.set_drop_highlight(False)
        self._last_dnd_item = None
        RZContextManager.get_instance().set_hover_id(-1)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        try:
            mime = event.mimeData()
            scene_pos = self.mapToScene(event.pos())
            
            bx_qt = scene_pos.x()
            by_qt = scene_pos.y()
            bx_bl, by_bl = core.to_blender_coords(bx_qt, by_qt)
            bx, by = int(bx_bl), int(by_bl)
            
            # Get target item from context
            ctx = RZContextManager.get_instance()
            target_uid = ctx._hover_id
            
            # Clear highlight
            if hasattr(self, '_last_dnd_item') and self._last_dnd_item:
                if shiboken6.isValid(self._last_dnd_item):
                    if hasattr(self._last_dnd_item, 'set_drop_highlight'):
                        self._last_dnd_item.set_drop_highlight(False)
            self._last_dnd_item = None
            ctx.set_hover_id(-1)

            # 1. Внутренний Шаблон (Из Asset Browser)
            if mime.hasFormat("application/x-rzmenu-template"):
                data = mime.data("application/x-rzmenu-template")
                filepath = data.data().decode('utf-8')
                
                print(f"[Viewport] Importing Template from Browser: {filepath}")
                # Импортируем в сцену в точку курсора
                blender_bridge.import_template_direct(filepath, offset=(bx, by))
                
                event.acceptProposedAction()
                return

            # 2. Внутренняя Картинка (Из Asset Browser)
            if mime.hasFormat("application/x-rzmenu-image-id"):
                data = mime.data("application/x-rzmenu-image-id")
                image_id = int(data.data().decode('utf-8'))
                
                if target_uid >= 0:
                    core.update_property_multi([target_uid], "image_id", image_id)
                else:
                    core.create_element_with_image(image_id, bx, by)
                
                event.acceptProposedAction(); return

            # 3. Внешний файл (Из Windows Explorer)
            if mime.hasUrls():
                urls = mime.urls()
                offset_counter = 0
                for url in urls:
                    path = url.toLocalFile()
                    if not path: continue
                    ext = os.path.splitext(path)[1].lower()

                    if ext == '.rzmt':
                        blender_bridge.import_template_direct(path, offset=(bx + offset_counter, by - offset_counter))
                        offset_counter += 20
                    elif ext in ['.png', '.jpg', '.jpeg', '.tga', '.bmp']:
                        img_id, _ = core.import_image_from_path(path)
                        if img_id is not None:
                            if target_uid >= 0 and offset_counter == 0:
                                core.update_property_multi([target_uid], "image_id", img_id)
                            else:
                                core.create_element_with_image(img_id, bx + offset_counter, by - offset_counter)
                            offset_counter += 20
                            
                event.acceptProposedAction(); return

            super().dropEvent(event)

        except Exception as e:
            print(f"[Viewport] Drop Error: {e}")
            import traceback
            traceback.print_exc()


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

        # Alignment Toolbar
        layout.addSpacing(4)
        v_line = QtWidgets.QFrame(); v_line.setFrameShape(QtWidgets.QFrame.VLine); v_line.setStyleSheet("color: rgba(255,255,255,20)"); layout.addWidget(v_line)
        layout.addSpacing(4)

        align_actions = [
            ("⬅", "LEFT", "Align Left"), ("⏐", "CENTER_X", "Align Center X"), ("➡", "RIGHT", "Align Right"),
            ("⬆", "TOP", "Align Top"), ("⎯", "CENTER_Y", "Align Center Y"), ("⬇", "BOTTOM", "Align Bottom")
        ]
        from .. import core
        from .viewport import RZContextManager # Need current selection
        
        def run_align(mode):
            ctx = RZContextManager.get_instance().get_snapshot()
            if ctx.selected_ids:
                core.align_elements(list(ctx.selected_ids), mode)

        for icon, mode, tip in align_actions:
            btn = QtWidgets.QPushButton(icon)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked=False, m=mode: run_align(m))
            layout.addWidget(btn)
        
        self.overlay_container.adjustSize()

        # --- ISOLATION TABS (LEFT OVERLAY) ---
        self.iso_container = QtWidgets.QFrame(self)
        self.iso_container.setObjectName("IsolationOverlay")
        self.iso_container.setStyleSheet("""
            #IsolationOverlay {
                background-color: rgba(30, 30, 30, 180);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 4px;
            }
        """)
        iso_layout = QtWidgets.QHBoxLayout(self.iso_container)
        iso_layout.setContentsMargins(2, 2, 2, 2)
        
        self.iso_tab_bar = QtWidgets.QTabBar()
        self.iso_tab_bar.setDocumentMode(True)
        self.iso_tab_bar.setDrawBase(False)
        self.iso_tab_bar.setStyleSheet("""
            QTabBar::tab {
                background: transparent;
                color: #888;
                padding: 4px 10px;
                border-radius: 3px;
            }
            QTabBar::tab:selected {
                background: rgba(255, 255, 255, 15);
                color: #FFF;
            }
            QTabBar::tab:hover {
                background: rgba(255, 255, 255, 8);
            }
        """)
        self.iso_tab_bar.currentChanged.connect(self._on_iso_tab_changed)
        iso_layout.addWidget(self.iso_tab_bar)
        
        self.iso_container.adjustSize()

    def _on_iso_tab_changed(self, index):
        if not hasattr(self, 'iso_tab_bar'): return
        uid = self.iso_tab_bar.tabData(index)
        if uid is None: uid = -1
        RZContextManager.get_instance().set_isolated_tab_id(uid)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 10
        # Position overlay at top right (Settings/Alignment)
        if hasattr(self, 'overlay_container'):
            self.overlay_container.move(self.width() - self.overlay_container.width() - margin, margin)
        
        # Position isolation at top left
        if hasattr(self, 'iso_container'):
            self.iso_container.move(margin, margin)

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
            # Если элемент выбран, добавляем опцию экспорта
            menu.addSection("Assets")
            
            save_action = menu.addAction("Save as Asset (.rzmt)")
            # Используем замыкание, чтобы не потерять selected_ids
            # Получаем текущие выделенные ID через Context Manager
            ctx = RZContextManager.get_instance().get_snapshot()
            selected_ids = ctx.selected_ids
            
            save_action.triggered.connect(lambda: self.on_save_asset(selected_ids))
            
            menu.addSeparator()
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

    def on_save_asset(self, selected_ids):
        if not selected_ids: return
        
        # 1. Спрашиваем имя файла
        from PySide6.QtWidgets import QFileDialog
        
        # Дефолтная папка (та же, что в браузере)
        # Можно вынести этот путь в конфиг (conf/defaults.py)
        import os
        import bpy
        if bpy.data.is_saved:
            folder = os.path.join(os.path.dirname(bpy.data.filepath), "rzm_assets")
        else:
            folder = os.path.join(os.path.expanduser("~"), "rzm_assets_global")
        if not os.path.exists(folder): os.makedirs(folder)

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Asset", folder, "RZM Templates (*.rzmt)"
        )
        
        if filepath:
            # 2. Экспорт через Bridge
            if blender_bridge.export_template_direct(list(selected_ids), filepath):
                # 3. Обновляем Asset Browser (через Сигналы)
                # Нужно добавить сигнал asset_library_changed или просто дернуть structure_changed
                from ..core.signals import SIGNALS
                SIGNALS.structure_changed.emit() # Это заставит Browser обновиться
                print(f"Asset saved: {filepath}")


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
        SIGNALS.isolation_changed.connect(self.refresh_data)
    
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
        try:
            SIGNALS.isolation_changed.disconnect(self.refresh_data)
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

        # VIEWPORT TAB ISOLATION FILTERING
        active_tab_uid = RZContextManager.get_instance().isolated_tab_id
        
        # Update Viewport Tab Bar (Overlay)
        if hasattr(self.view, 'iso_tab_bar'):
            tab_bar = self.view.iso_tab_bar
            # Block signals during update to avoid recursion
            tab_bar.blockSignals(True)
            
            # Fetch tab containers from all data
            tab_containers = [e for e in data if e.get('is_tab_container')]
            
            # Rebuild tabs (Fixing 'clear' crash by using loop)
            while tab_bar.count() > 0:
                tab_bar.removeTab(0)
            
            # Always add "ALL"
            tab_bar.addTab("ALL")
            tab_bar.setTabData(0, -1)
            
            current_idx = 0
            for i, tc in enumerate(tab_containers):
                tab_bar.addTab(tc['name'])
                tab_bar.setTabData(i + 1, tc['id'])
                
                # Apply Page Color to tab text
                col = tc.get('page_color', [0.5, 0.5, 0.5, 1.0])
                qcol = QtGui.QColor.fromRgbF(col[0], col[1], col[2], 1.0)
                tab_bar.setTabTextColor(i + 1, qcol)
                
                if tc['id'] == active_tab_uid:
                    current_idx = i + 1
            
            tab_bar.setCurrentIndex(current_idx)
            tab_bar.blockSignals(False)
            self.view.iso_container.adjustSize()

        if active_tab_uid != -1:
            descendants = set([active_tab_uid])
            parent_map = {}
            for e in data:
                parent_map.setdefault(e.get('parent_id', -1), []).append(e['id'])
                
            def gather_descendants(pid):
                for child_id in parent_map.get(pid, []):
                    descendants.add(child_id)
                    gather_descendants(child_id)
                    
            gather_descendants(active_tab_uid)
            
            # Remove anything not in descendants
            data = [e for e in data if e['id'] in descendants]

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
                    # If clicked item is already selected, don't clear the rest of the selection
                    # This allows dragging multiple items without holding Shift
                    if clicked_id in new_selection:
                        new_active = clicked_id
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