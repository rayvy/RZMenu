# RZMenu/qt_editor/widgets/styles_manager.py
import bpy
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.theme import get_current_theme
from .lib.widgets import RZPanelWidget, RZColorButton
from ..core import signals, props, read

from .panel_base import RZEditorPanel

class RZMStylesPanel(RZEditorPanel):
    """
    Panel for managing global RZMenu Styles (rzm.styles).
    """
    PANEL_ID = "STYLES"
    PANEL_NAME = "Style Manager"
    PANEL_ICON = "palette"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RZMStylesPanel")
        
        # Main Layout: Sidebar (List) + Content (Editor)
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)
        
        # --- SIDEBAR ---
        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setFixedWidth(200)
        self.side_layout = QtWidgets.QVBoxLayout(self.sidebar)
        self.side_layout.setContentsMargins(0, 0, 0, 0)
        self.side_layout.setSpacing(4)
        
        # Search
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search styles...")
        self.search_bar.textChanged.connect(self.refresh_list)
        self.side_layout.addWidget(self.search_bar)
        
        # List
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.currentRowChanged.connect(self.on_selection_changed)
        self.side_layout.addWidget(self.list_widget)
        
        # Buttons
        self.btn_layout = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("+ Add")
        self.btn_remove = QtWidgets.QPushButton("- Remove")
        self.btn_add.clicked.connect(self.add_style)
        self.btn_remove.clicked.connect(self.remove_style)
        self.btn_layout.addWidget(self.btn_add)
        self.btn_layout.addWidget(self.btn_remove)
        self.side_layout.addLayout(self.btn_layout)
        
        self.main_layout.addWidget(self.sidebar)
        
        # --- CONTENT (EDITOR) ---
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.editor_widget = QtWidgets.QWidget()
        self.editor_layout = QtWidgets.QVBoxLayout(self.editor_widget)
        self.editor_layout.setContentsMargins(8, 8, 8, 8)
        self.editor_layout.setSpacing(12)
        
        self.setup_editor_ui()
        
        self.scroll_area.setWidget(self.editor_widget)
        self.main_layout.addWidget(self.scroll_area, stretch=1)
        
        # Internal State
        self._block_signals = False
        self.current_style_id = -1
        
        self.apply_theme()

    def setup_editor_ui(self):
        # 1. Header (Name)
        self.group_header = QtWidgets.QGroupBox("General")
        header_layout = QtWidgets.QFormLayout(self.group_header)
        self.inp_name = QtWidgets.QLineEdit()
        self.inp_name.editingFinished.connect(lambda: self.sync_prop("name", self.inp_name.text()))
        header_layout.addRow("Style Name:", self.inp_name)
        self.editor_layout.addWidget(self.group_header)
        
        # 2. Shadow
        self.group_shadow = self.create_effect_group("Drop Shadow", "use_shadow")
        shadow_layout = self.group_shadow.layout()
        
        self.inp_shadow_offset = self.create_vec2_row(shadow_layout, "Offset X/Y:", "shadow_offset")
        self.inp_shadow_blur = self.create_float_row(shadow_layout, "Blur:", "shadow_blur")
        self.inp_shadow_color = self.create_color_row(shadow_layout, "Color:", "shadow_color")
        self.editor_layout.addWidget(self.group_shadow)
        
        # 3. Glow
        self.group_glow = self.create_effect_group("Outer Glow", "use_glow")
        glow_layout = self.group_glow.layout()
        self.inp_glow_radius = self.create_float_row(glow_layout, "Radius:", "glow_radius")
        self.inp_glow_intensity = self.create_float_row(glow_layout, "Intensity:", "glow_intensity")
        self.inp_glow_color = self.create_color_row(glow_layout, "Color:", "glow_color")
        self.editor_layout.addWidget(self.group_glow)
        
        # 4. Outline
        self.group_outline = self.create_effect_group("Outline", "use_outline")
        outline_layout = self.group_outline.layout()
        self.inp_outline_thickness = self.create_float_row(outline_layout, "Thickness:", "outline_thickness")
        self.inp_outline_color = self.create_color_row(outline_layout, "Color:", "outline_color")
        self.editor_layout.addWidget(self.group_outline)
        
        # 5. Gradient
        self.group_gradient = self.create_effect_group("Gradient Overlay", "use_gradient")
        grad_layout = self.group_gradient.layout()
        self.inp_grad_color_1 = self.create_color_row(grad_layout, "Color 1:", "grad_color_1")
        self.inp_grad_color_2 = self.create_color_row(grad_layout, "Color 2:", "grad_color_2")
        self.inp_grad_angle = self.create_float_row(grad_layout, "Angle (Deg):", "grad_angle", min=-360, max=360)
        self.editor_layout.addWidget(self.group_gradient)
        
        # 6. Blur
        self.group_blur = self.create_effect_group("Blur", "use_blur")
        blur_layout = self.group_blur.layout()
        self.inp_blur_strength = self.create_float_row(blur_layout, "Strength:", "blur_strength", max=20)
        self.inp_blur_mask = self.create_bool_row(blur_layout, "Blur Mask Mode:", "use_blur_mask")
        self.editor_layout.addWidget(self.group_blur)

        # 7. Post FX (Grayscale, Chromatic)
        self.group_post = QtWidgets.QGroupBox("Post Effects")
        post_layout = QtWidgets.QFormLayout(self.group_post)
        self.inp_use_grayscale = self.create_bool_row(post_layout, "Enable Grayscale:", "use_grayscale")
        self.inp_grayscale_amount = self.create_float_row(post_layout, "Grayscale Amount:", "grayscale_amount", max=1.0)
        self.inp_use_chromatic = self.create_bool_row(post_layout, "Enable Chromatic:", "use_chromatic")
        self.inp_chromatic_offset = self.create_float_row(post_layout, "Chromatic Offset:", "chromatic_offset", max=20)
        self.editor_layout.addWidget(self.group_post)

        # 8. Animations
        self.group_anim = QtWidgets.QGroupBox("Animations")
        anim_layout = QtWidgets.QFormLayout(self.group_anim)
        self.inp_anim_hover_resize = self.create_bool_row(anim_layout, "Hover Resize:", "anim_hover_resize")
        self.inp_hover_scale = self.create_float_row(anim_layout, "Scale Factor:", "hover_scale_factor", min=0.5, max=2.0)
        
        self.inp_anim_hover_sheen = self.create_bool_row(anim_layout, "Hover Sheen:", "anim_hover_sheen")
        self.inp_sheen_speed = self.create_float_row(anim_layout, "Sheen Speed:", "sheen_speed")
        self.inp_sheen_width = self.create_float_row(anim_layout, "Sheen Width:", "sheen_width", max=1.0)
        self.inp_sheen_color = self.create_color_row(anim_layout, "Sheen Color:", "sheen_color")
        
        self.inp_anim_rotate = self.create_bool_row(anim_layout, "Constant Rotation:", "anim_rotate")
        self.inp_rotate_speed = self.create_float_row(anim_layout, "Rotate Speed:", "rotate_speed", min=-100, max=100)
        self.editor_layout.addWidget(self.group_anim)

        self.editor_layout.addStretch()

    # --- UI HELPER METHODS ---
    
    def create_effect_group(self, title, bool_prop):
        group = QtWidgets.QGroupBox(title)
        group.setCheckable(True)
        group.toggled.connect(lambda checked: self.sync_prop(bool_prop, checked))
        layout = QtWidgets.QFormLayout(group)
        return group

    def create_float_row(self, layout, label, prop, min=0, max=100, step=0.1):
        sb = QtWidgets.QDoubleSpinBox()
        sb.setRange(min, max)
        sb.setSingleStep(step)
        sb.valueChanged.connect(lambda v: self.sync_prop(prop, v))
        layout.addRow(label, sb)
        return sb

    def create_bool_row(self, layout, label, prop):
        cb = QtWidgets.QCheckBox()
        cb.toggled.connect(lambda v: self.sync_prop(prop, v))
        layout.addRow(label, cb)
        return cb

    def create_vec2_row(self, layout, label, prop):
        container = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        x = QtWidgets.QDoubleSpinBox()
        y = QtWidgets.QDoubleSpinBox()
        for w in [x, y]:
            w.setRange(-100, 100)
            w.setSingleStep(0.5)
        
        x.valueChanged.connect(lambda v: self.sync_prop(prop, v, sub_index=0))
        y.valueChanged.connect(lambda v: self.sync_prop(prop, v, sub_index=1))
        
        h.addWidget(QtWidgets.QLabel("X:"))
        h.addWidget(x)
        h.addWidget(QtWidgets.QLabel("Y:"))
        h.addWidget(y)
        layout.addRow(label, container)
        return (x, y)

    def create_color_row(self, layout, label, prop):
        btn = RZColorButton()
        btn.setFixedSize(60, 20)
        btn.colorChanged.connect(lambda color: self.sync_prop(prop, color))
        layout.addRow(label, btn)
        return btn

    # --- LOGIC ---

    def refresh(self):
        """Update the list from Blender data."""
        self._block_signals = True
        try:
            prev_id = self.current_style_id
            self.list_widget.clear()
            
            styles = read.get_all_styles()
            search = self.search_bar.text().lower()
            
            target_row = -1
            for style in styles:
                if search and search not in style['name'].lower():
                    continue
                
                item = QtWidgets.QListWidgetItem(style['name'])
                item.setData(QtCore.Qt.UserRole, style['id'])
                self.list_widget.addItem(item)
                
                if style['id'] == prev_id:
                    target_row = self.list_widget.count() - 1
            
            if target_row != -1:
                self.list_widget.setCurrentRow(target_row)
            elif self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(0)
            else:
                self.current_style_id = -1
                self.editor_widget.setEnabled(False)
        finally:
            self._block_signals = False
        
        self.update_editor()

    def refresh_list(self):
        self.refresh()

    def on_selection_changed(self):
        if self._block_signals: return
        item = self.list_widget.currentItem()
        if item:
            self.current_style_id = item.data(QtCore.Qt.UserRole)
            self.editor_widget.setEnabled(True)
        else:
            self.current_style_id = -1
            self.editor_widget.setEnabled(False)
        self.update_editor()

    def update_editor(self):
        """Fill editor fields from Blender data."""
        if self.current_style_id == -1: return
        
        data = read.get_style_properties(self.current_style_id)
        if not data: return
        
        self._block_signals = True
        try:
            self.inp_name.setText(data['name'])
            
            # Shadow
            self.group_shadow.setChecked(data['use_shadow'])
            self.inp_shadow_offset[0].setValue(data['shadow_offset'][0])
            self.inp_shadow_offset[1].setValue(data['shadow_offset'][1])
            self.inp_shadow_blur.setValue(data['shadow_blur'])
            self.inp_shadow_color.set_color(data['shadow_color'])
            
            # Glow
            self.group_glow.setChecked(data['use_glow'])
            self.inp_glow_radius.setValue(data['glow_radius'])
            self.inp_glow_intensity.setValue(data['glow_intensity'])
            self.inp_glow_color.set_color(data['glow_color'])
            
            # Outline
            self.group_outline.setChecked(data['use_outline'])
            self.inp_outline_thickness.setValue(data['outline_thickness'])
            self.inp_outline_color.set_color(data['outline_color'])
            
            # Gradient
            self.group_gradient.setChecked(data['use_gradient'])
            self.inp_grad_color_1.set_color(data['grad_color_1'])
            self.inp_grad_color_2.set_color(data['grad_color_2'])
            self.inp_grad_angle.setValue(data['grad_angle'])
            
            # Blur
            self.group_blur.setChecked(data['use_blur'])
            self.inp_blur_strength.setValue(data['blur_strength'])
            self.inp_blur_mask.setChecked(data['use_blur_mask'])

            # Post
            self.inp_use_grayscale.setChecked(data['use_grayscale'])
            self.inp_grayscale_amount.setValue(data['grayscale_amount'])
            self.inp_use_chromatic.setChecked(data['use_chromatic'])
            self.inp_chromatic_offset.setValue(data['chromatic_offset'])

            # Anim
            self.inp_anim_hover_resize.setChecked(data['anim_hover_resize'])
            self.inp_hover_scale.setValue(data['hover_scale_factor'])
            self.inp_anim_hover_sheen.setChecked(data['anim_hover_sheen'])
            self.inp_sheen_speed.setValue(data['sheen_speed'])
            self.inp_sheen_width.setValue(data['sheen_width'])
            self.inp_sheen_color.set_color(data['sheen_color'])
            self.inp_anim_rotate.setChecked(data['anim_rotate'])
            self.inp_rotate_speed.setValue(data['rotate_speed'])

        finally:
            self._block_signals = False

    def sync_prop(self, prop, value, sub_index=None):
        if self._block_signals or self.current_style_id == -1: return
        props.update_global_style_property(self.current_style_id, prop, value, sub_index)

    def add_style(self):
        new_id = props.add_global_style()
        self.current_style_id = new_id
        self.refresh()

    def remove_style(self):
        if self.current_style_id == -1: return
        if QtWidgets.QMessageBox.question(self, "Delete Style", "Are you sure you want to delete this style?") == QtWidgets.QMessageBox.Yes:
            props.remove_global_style(self.current_style_id)
            self.current_style_id = -1
            self.refresh()

    def apply_theme(self):
        t = get_current_theme()
        
        # Guard against calls from super().__init__ before UI is fully built
        if not hasattr(self, 'sidebar'):
            return

        # sidebar styling
        self.sidebar.setStyleSheet(f"background-color: {t['bg_panel']}; border-right: 1px solid {t['border_main']};")
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {t['bg_input']};
                border: 1px solid {t['border_input']};
                color: {t['text_main']};
            }}
            QListWidget::item:selected {{
                background-color: {t['accent']};
                color: white;
            }}
        """)
        
        # Style GroupBoxes to look premium
        group_style = f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {t['border_main']};
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {t['bg_panel']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
                color: {t['accent']};
            }}
        """
        if hasattr(self, 'editor_widget'):
            self.editor_widget.setStyleSheet(group_style)
        
        if hasattr(self, 'btn_add') and hasattr(self, 'btn_remove'):
            for btn in [self.btn_add, self.btn_remove]:
                btn.setStyleSheet(f"background-color: {t['bg_header']}; border: 1px solid {t['border_main']}; padding: 4px;")

    def refresh_data(self):
        self.refresh()

    def _connect_signals(self):
        try:
            signals.SIGNALS.styles_changed.connect(self.refresh)
        except (RuntimeError, TypeError): pass

    def _disconnect_signals(self):
        try:
            signals.SIGNALS.styles_changed.disconnect(self.refresh)
        except (RuntimeError, TypeError): pass

    def focus_style(self, style_id):
        """Find and select the style in the list."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(QtCore.Qt.UserRole) == style_id:
                self.list_widget.setCurrentRow(i)
                self.list_widget.scrollToItem(item)
                break
