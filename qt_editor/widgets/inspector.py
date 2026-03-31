# RZMenu/qt_editor/widgets/inspector.py
"""
Inspector Panel - Property editor for selected elements.
Autonomous panel that subscribes to core.SIGNALS for data updates.
Updated to support Formulas, Conditional Visibility, and Class Specifics.
"""
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.base import RZDraggableNumber, RZSmartSlider
from .lib.inputs import RZImageComboBox, RZFormulaInput, RZCodeTextEdit
from .lib.theme import get_current_theme
from .lib.widgets import RZGroupBox, RZPushButton, RZLabel, RZLineEdit, RZComboBox, RZColorButton, RZCheckBox, RZSpinBox, RZDoubleSpinBox, RZAdvancedColorPanel, RZScrollArea
from .panel_base import RZEditorPanel
from .. import core
from ..core.signals import SIGNALS
from ..context import RZContextManager
from ...data.constants import FX_COMMANDS
import bpy
import os

class RZFontSlotComboBox(RZComboBox):
    """
    ComboBox for selecting font slots (0-3).
    Displays slot number and the name of the font assigned to it.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        
    def refresh_slots(self):
        self.blockSignals(True)
        self.clear()
        
        fonts = []
        if bpy.context and hasattr(bpy.context.scene, "rzm"):
            fonts = bpy.context.scene.rzm.fonts
            
        from ...utils.font_utils import find_by_path
        for i in range(4):
            label = "Empty"
            if i < len(fonts):
                slot = fonts[i]
                if slot.font_source in ('DEFAULT', 'ARIAL', 'CONSOLAS', 'SEGOE'):
                    label = "Windows Arial"
                elif slot.custom_path:
                    result = find_by_path(slot.custom_path)
                    if result:
                        family, style, _ = result
                        label = family if style == "Regular" else f"{family} - {style}"
                    else:
                        label = os.path.basename(slot.custom_path) or "Custom"
                else:
                    label = "Not Set"
            
            self.addItem(f"Slot {i+1}: {label}", i)
        
        self.blockSignals(False)

class RZInspectorAnchorBar(QtWidgets.QWidget):
    """
    Sticky navigation bar for the monolithic Inspector.
    Features a sliding accent line and bi-directional sync with the scroll area.
    """
    clicked = QtCore.Signal(str) # Emits group name

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setFixedHeight(35)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 0)
        self.layout.setSpacing(15)
        
        self.buttons = {}
        self.items = items # List of (label, group_name)
        
        for label, grp_name in items:
            btn = QtWidgets.QPushButton(label)
            btn.setObjectName("AnchorButton")
            btn.setFlat(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, n=grp_name: self.clicked.emit(n))
            self.layout.addWidget(btn)
            self.buttons[grp_name] = btn
            
        self.layout.addStretch()
        
        # Sliding Underline
        self.underline = QtWidgets.QWidget(self)
        self.underline.setFixedHeight(2)
        self.underline.setObjectName("AnchorUnderline")
        self.underline.hide() # Shown on first activation
        
        self._anim = QtCore.QPropertyAnimation(self.underline, b"geometry")
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutQuint)
        
        self.active_grp = None

    def set_active(self, grp_name):
        if self.active_grp == grp_name: return
        self.active_grp = grp_name
        
        btn = self.buttons.get(grp_name)
        if not btn: return
        
        # --- PHASE 2.6: ROLLING TABS ---
        # Ensure the active tab is visible (scroll to it)
        parent_scroll = self.parentWidget()
        if isinstance(parent_scroll, QtWidgets.QScrollArea):
             parent_scroll.ensureWidgetVisible(btn, 10, 10)

        # Animate underline to button geometry
        self.underline.show()
        t = get_current_theme()
        self.underline.setStyleSheet(f"background-color: {t.get('accent', '#007AFF')}; border-radius: 1px;")
        
        target_rect = btn.geometry()
        target_rect.setY(self.height() - 3)
        target_rect.setHeight(2)
        
        self._anim.stop()
        self._anim.setEndValue(target_rect)
        self._anim.start()
        
        # Style buttons
        for name, b in self.buttons.items():
            is_active = (name == grp_name)
            col = t.get('text_bright', '#FFF') if is_active else t.get('text_dim', '#888')
            b.setStyleSheet(f"color: {col}; font-weight: {'bold' if is_active else 'normal'}; border: none; background: transparent;")

    def wheelEvent(self, event):
        event.ignore()

    def wheelEvent(self, event):
        event.ignore()

    def leaveEvent(self, event):
        super().leaveEvent(event)

    def paintEvent(self, event):
        # Optional: Draw separator at bottom
        painter = QtGui.QPainter(self)
        t = get_current_theme()
        painter.setPen(QtGui.QColor(t.get('border', '#333')))
        painter.drawLine(0, self.height()-1, self.width(), self.height()-1)

class RZInspectorItem(QtWidgets.QWidget):
    """
    Standardized base for list row items in the Inspector.
    Provides a fluid layout with content area and actions (delete button).
    """
    def __init__(self, index, parent_list, parent=None):
        super().__init__(parent)
        self.index = index
        self.parent_list = parent_list
        
        # Outer layout for potential future animations/shadows
        self.outer_layout = QtWidgets.QVBoxLayout(self)
        self.outer_layout.setContentsMargins(1, 1, 1, 1)
        self.outer_layout.setSpacing(0)
        
        self.main_widget = QtWidgets.QWidget()
        self.layout_main = QtWidgets.QHBoxLayout(self.main_widget)
        self.layout_main.setContentsMargins(4, 2, 4, 2)
        self.layout_main.setSpacing(6)
        self.outer_layout.addWidget(self.main_widget)
        
        # Content container
        self.content_layout = QtWidgets.QHBoxLayout()
        self.content_layout.setSpacing(6)
        self.layout_main.addLayout(self.content_layout, 1)
        
        # Actions container
        self.actions_layout = QtWidgets.QHBoxLayout()
        self.actions_layout.setSpacing(3)
        self.layout_main.addLayout(self.actions_layout)
        
        # Standard Delete Button
        self.btn_del = RZPushButton("✕")
        self.btn_del.setFixedWidth(24)
        self.btn_del.clicked.connect(self._on_delete)
        self.actions_layout.addWidget(self.btn_del)

    def _on_delete(self):
        if self.parent_list:
            self.parent_list.remove_item(self.index)
            
    def add_widget(self, widget, stretch=0):
        self.content_layout.addWidget(widget, stretch)
        
    def add_action(self, widget):
        self.actions_layout.insertWidget(self.actions_layout.count() - 1, widget)

class RZListEditor(QtWidgets.QWidget):
    """
    Generic base for list-like editors in the Inspector.
    Handles layout, 'Add' button, and reconciliation logic.
    """
    def __init__(self, add_label="+ Add Item", parent=None):
        super().__init__(parent)
        self._block = False
        
        self.layout_main = QtWidgets.QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)
        self.layout_main.setSpacing(2)
        
        self.layout_items = QtWidgets.QVBoxLayout()
        self.layout_items.setSpacing(2)
        self.layout_main.addLayout(self.layout_items)
        
        self.btn_add = RZPushButton(add_label)
        self.btn_add.clicked.connect(self.add_item)
        self.layout_main.addWidget(self.btn_add)

    def clear_items(self):
        while self.layout_items.count():
            item = self.layout_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def sync_widgets(self, data_list, widget_factory, update_func=None):
        """
        Synchronizes UI widgets with the data list without full recreation.
        If update_func is provided, it's called for existing widgets to refresh their data.
        """
        self._block = True
        
        # 1. Reconciliation: Ensure we have the same number of widgets
        current_count = self.layout_items.count()
        new_count = len(data_list)
        
        # Add missing widgets
        if new_count > current_count:
            for i in range(current_count, new_count):
                w = widget_factory(i, data_list[i])
                if w: self.layout_items.addWidget(w)
        
        # Remove excess widgets
        elif new_count < current_count:
            for i in range(current_count - 1, new_count - 1, -1):
                item = self.layout_items.takeAt(i)
                if item.widget():
                    item.widget().deleteLater()
                    
        # 2. Update existing widgets
        for i in range(len(data_list)):
            item = self.layout_items.itemAt(i)
            if not item: continue
            w = item.widget()
            if not w: continue
            
            # Update index property if widget has it
            if hasattr(w, 'index'):
                w.index = i
                
            # Perform custom update if func provided
            if update_func:
                update_func(w, data_list[i])
                
        self._block = False

class RZConditionalImageItem(RZInspectorItem):
    """A single row in the conditional image list."""
    def __init__(self, index, data, images, parent=None):
        super().__init__(index, parent, parent=parent)
        
        # Use a vertical layout for content to give fields full width
        self.v_content = QtWidgets.QVBoxLayout()
        self.v_content.setSpacing(2)
        self.content_layout.addLayout(self.v_content)
        
        self.edit_cond = RZFormulaInput()
        self.edit_cond.setPlaceholderText("Condition (e.g. $var == 1)...")
        self.edit_cond.setText(data.get('condition', ''))
        self.edit_cond.editingFinished.connect(self._on_cond_changed)
        self.v_content.addWidget(self.edit_cond)
        
        self.cb_img = RZImageComboBox()
        self.cb_img.update_items(images)
        self.cb_img.set_value(data.get('image_id', -1))
        self.cb_img.value_changed.connect(self._on_img_changed)
        self.v_content.addWidget(self.cb_img)

    def _on_cond_changed(self):
        self.parent_list.item_changed(self.index, 'condition', self.edit_cond.text())

    def _on_img_changed(self, val):
        self.parent_list.item_changed(self.index, 'image_id', val)

    def update_data(self, data, images):
        self.edit_cond.setText(data.get('condition', ''))
        self.cb_img.update_items(images)
        self.cb_img.set_value(data.get('image_id', -1))

    def set_cond_visible(self, visible):
        self.edit_cond.setVisible(visible)

class RZConditionalImageList(RZListEditor):
    """A list-like widget to manage ConditionalImage collection."""
    def __init__(self, parent=None):
        super().__init__("+ Add Image", parent)
        self.image_mode = 'SINGLE'

    def update_data(self, data_list, available_images, mode):
        self.image_mode = mode
        
        def factory(i, data):
            item_w = RZConditionalImageItem(i, data, available_images, self)
            item_w.set_cond_visible(mode == 'CONDITIONAL_LIST')
            return item_w
            
        def updater(w, data):
            w.blockSignals(True)
            w.update_data(data, available_images)
            w.set_cond_visible(mode == 'CONDITIONAL_LIST')
            w.blockSignals(False)
            
        self.sync_widgets(data_list, factory, updater)

    def add_item(self):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.add_conditional_image(ctx.selected_ids)

    def remove_item(self, index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.remove_conditional_image(ctx.selected_ids, index)

    def item_changed(self, index, field, value):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.update_conditional_image(ctx.selected_ids, index, field, value)


class RZConditionalTextItem(RZInspectorItem):
    """A single row in the conditional text list."""
    def __init__(self, index, data, parent=None):
        super().__init__(index, parent, parent=parent)
        
        # Use a vertical layout for content to give fields full width
        self.v_content = QtWidgets.QVBoxLayout()
        self.v_content.setSpacing(2)
        self.content_layout.addLayout(self.v_content)

        self.edit_cond = RZFormulaInput()
        self.edit_cond.setPlaceholderText("Condition (e.g. $var == 1)...")
        self.edit_cond.setText(data.get('condition', ''))
        self.edit_cond.editingFinished.connect(self._on_cond_changed)
        self.v_content.addWidget(self.edit_cond)
        
        self.edit_txt = RZLineEdit()
        self.edit_txt.setPlaceholderText("Text ID...")
        self.edit_txt.setText(data.get('text_id', ''))
        self.edit_txt.editingFinished.connect(self._on_txt_changed)
        self.v_content.addWidget(self.edit_txt)

    def _on_cond_changed(self):
        self.parent_list.item_changed(self.index, 'condition', self.edit_cond.text())

    def _on_txt_changed(self):
        self.parent_list.item_changed(self.index, 'text_id', self.edit_txt.text())

    def update_data(self, data):
        self.edit_cond.setText(data.get('condition', ''))
        self.edit_txt.setText(data.get('text_id', ''))

    def set_cond_visible(self, visible):
        self.edit_cond.setVisible(visible)

class RZConditionalTextList(RZListEditor):
    """A list-like widget to manage ConditionalText collection."""
    def __init__(self, parent=None):
        super().__init__("+ Add Text", parent)
        self.text_mode = 'SINGLE'

    def update_data(self, data_list, mode):
        self.text_mode = mode
        def factory(i, data):
            item_w = RZConditionalTextItem(i, data, self)
            item_w.set_cond_visible(mode == 'CONDITIONAL_LIST')
            return item_w
            
        def updater(w, data):
            w.blockSignals(True)
            w.update_data(data)
            w.set_cond_visible(mode == 'CONDITIONAL_LIST')
            w.blockSignals(False)
            
        self.sync_widgets(data_list, factory, updater)

    def add_item(self):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.add_conditional_text(ctx.selected_ids)

    def remove_item(self, index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.remove_conditional_text(ctx.selected_ids, index)

    def item_changed(self, index, field, value):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.update_conditional_text(ctx.selected_ids, index, field, value)


class RZValueLinkItem(RZInspectorItem):
    """A single row in the value link list."""
    def __init__(self, index, data, is_slider, parent=None):
        super().__init__(index, parent, parent=parent)

        # RZInspectorItem already has horizontal layout_main (row 1: Name + Actions)
        # We just add a second row to self.outer_layout (QVBoxLayout)

        self.edit_name = RZFormulaInput()
        self.edit_name.setPlaceholderText("Link ($Var, @Toggle, #Shape)...")
        self.edit_name.setText(data.get('value_name', ''))
        self.edit_name.editingFinished.connect(self._on_name_changed)
        self.add_widget(self.edit_name, 1)

        # Ranges for Sliders (Second row)
        self.w_ranges = QtWidgets.QWidget()
        l_range = QtWidgets.QHBoxLayout(self.w_ranges)
        l_range.setContentsMargins(10, 0, 0, 0)
        l_range.setSpacing(5)

        l_range.addWidget(RZLabel("Min:"))
        self.spin_min = RZDoubleSpinBox()
        self.spin_min.setRange(-10000, 10000)
        self.spin_min.setDecimals(2)
        self.spin_min.setValue(data.get('value_min', 0.0))
        self.spin_min.valueChanged.connect(self._on_min_changed)
        l_range.addWidget(self.spin_min)

        l_range.addWidget(RZLabel("Max:"))
        self.spin_max = RZDoubleSpinBox()
        self.spin_max.setRange(-10000, 10000)
        self.spin_max.setDecimals(2)
        self.spin_max.setValue(data.get('value_max', 1.0))
        self.spin_max.valueChanged.connect(self._on_max_changed)
        l_range.addWidget(self.spin_max)

        # Simply add to the outer layout which is QVBoxLayout
        self.outer_layout.addWidget(self.w_ranges)
        
        # Sync pattern
        self.update_data(data)

    def update_data(self, data):
        self.edit_name.setText(data.get('value_name', ''))
        self.spin_min.setValue(data.get('value_min', 0.0))
        self.spin_max.setValue(data.get('value_max', 1.0))
        
        pattern = data.get('value_name_pattern')
        if pattern:
            self.edit_name.set_pattern(pattern)
        else:
            self.edit_name.clear_pattern()
            self.edit_name.setText(data.get('value_name', ''))

    def _on_name_changed(self):
        new_val = self.edit_name.text()
        if self.edit_name.get_pattern():
            self.parent_list.item_pattern_changed(self.index, 'value_name', new_val, self.edit_name.get_originals())
        else:
            self.parent_list.item_changed(self.index, 'value_name', new_val)

    def _on_min_changed(self, val):
        self.parent_list.item_changed(self.index, 'value_min', float(val))

    def _on_max_changed(self, val):
        self.parent_list.item_changed(self.index, 'value_max', float(val))

    def _on_delete(self):
        self.parent_list.remove_item(self.index)

class RZValueLinkList(RZListEditor):
    """A list-like widget to manage ValueLink collection."""
    def __init__(self, parent=None):
        super().__init__("+ Add Link", parent)

    def update_data(self, data_list, is_slider):
        def factory(i, data):
            return RZValueLinkItem(i, data, is_slider, self)
            
        def updater(w, data):
            w.blockSignals(True)
            w.update_data(data)
            w.blockSignals(False)
            
        self.sync_widgets(data_list, factory, updater)

    def add_item(self):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.add_value_link(ctx.selected_ids)

    def remove_item(self, index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.remove_value_link(ctx.selected_ids, index)

    def item_changed(self, index, field, value):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            # Safety for literal dots in standard update
            if len(ctx.selected_ids) > 1 and isinstance(value, str) and "..." in value:
                print(f"[VL_LIST] Blocking standard VL update at index {index} because it contains '...'")
                return
            core.props.update_value_link(ctx.selected_ids, index, field, value)

    def item_pattern_changed(self, index, field, new_pattern, originals=None):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.update_value_link_multi_pattern(ctx.selected_ids, index, field, new_pattern, originals)


class RZFXItem(RZInspectorItem):
    """A single row in the FX list."""
    def __init__(self, index, current_val, parent=None):
        super().__init__(index, parent, parent=parent)
        
        self.cb_fx = RZComboBox()
        for internal, display, desc in FX_COMMANDS:
            self.cb_fx.addItem(display, internal)
            last_idx = self.cb_fx.count() - 1
            self.cb_fx.setItemData(last_idx, desc, QtCore.Qt.ToolTipRole)
            
        # Установка текущего значения
        idx = self.cb_fx.findData(current_val)
        if idx >= 0: 
            self.cb_fx.setCurrentIndex(idx)
        
        self.cb_fx.currentIndexChanged.connect(self._on_changed)
        self.add_widget(self.cb_fx, 1)

    def update_data(self, current_val):
        idx = self.cb_fx.findData(current_val)
        if idx >= 0: 
            self.cb_fx.setCurrentIndex(idx)

    def _on_changed(self, idx):
        internal = self.cb_fx.itemData(idx)
        self.parent_list.item_changed(self.index, internal)

class RZFXList(RZListEditor):
    """A list-like widget to manage FX collection."""
    def __init__(self, parent=None):
        super().__init__("+ Add Effect", parent)

    def update_data(self, data_list):
        def factory(i, val):
            return RZFXItem(i, val, self)
            
        def updater(w, val):
            w.blockSignals(True)
            w.update_data(val)
            w.blockSignals(False)
            
        self.sync_widgets(data_list, factory, updater)

    def add_item(self):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.add_fx(ctx.selected_ids)

    def remove_item(self, index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.remove_fx(ctx.selected_ids, index)

    def item_changed(self, index, value):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.update_fx(ctx.selected_ids, index, value)


class RZPresetItem(RZInspectorItem):
    """A single row in the Preset list."""
    def __init__(self, index, preset_id, preset_name="Unknown", parent=None):
        super().__init__(index, parent, parent=parent)
        self.preset_id = preset_id
        
        display_text = f"{preset_name} (ID: {preset_id})"
        self.lbl_id = RZLabel(display_text)
        self.add_widget(self.lbl_id, 1)
        
        # Reordering buttons (prepended to delete button)
        self.btn_up = RZPushButton("▲")
        self.btn_up.setFixedWidth(24)
        self.btn_up.clicked.connect(self._on_move_up)
        self.add_action(self.btn_up)
        
        self.btn_down = RZPushButton("▼")
        self.btn_down.setFixedWidth(24)
        self.btn_down.clicked.connect(self._on_move_down)
        self.add_action(self.btn_down)

    def _on_move_up(self):
        if self.index > 0:
            self.parent_list.reorder_item(self.index, self.index - 1)

    def _on_move_down(self):
        self.parent_list.reorder_item(self.index, self.index + 1)

    def update_data(self, preset_id, preset_name):
        self.preset_id = preset_id
        display_text = f"{preset_name} (ID: {preset_id})"
        self.lbl_id.setText(display_text)

class RZPresetList(RZListEditor):
    """A list-like widget to manage Preset IDs."""
    def __init__(self, parent=None):
        super().__init__("+ Add Preset", parent)
        # Re-arrange btn_add into a QHBoxLayout with a ComboBox
        self.layout_main.removeWidget(self.btn_add)
        h_add = QtWidgets.QHBoxLayout()
        self.cb_add_preset = RZComboBox()
        h_add.addWidget(self.cb_add_preset, 1)
        h_add.addWidget(self.btn_add)
        self.layout_main.addLayout(h_add)

    def update_data(self, preset_list):
        elements = core.read.get_all_elements_list()
        name_map = {e['id']: e['name'] for e in elements}
            
        def factory(i, pid):
            name = name_map.get(pid, "Unknown")
            return RZPresetItem(i, pid, name, self)
            
        def updater(w, pid):
            w.blockSignals(True)
            name = name_map.get(pid, "Unknown")
            w.update_data(pid, name)
            w.blockSignals(False)
            
        self.sync_widgets(preset_list, factory, updater)
        
        # Update dropdown with available preset elements
        self.cb_add_preset.blockSignals(True)
        self.cb_add_preset.clear()
        preset_elements = [e for e in elements if e.get('is_preset', False)]
        for e in preset_elements:
            self.cb_add_preset.addItem(f"{e['name']} (ID: {e['id']})", e['id'])
        self.cb_add_preset.blockSignals(False)

    def add_item(self):
        if self._block: return
        pid = self.cb_add_preset.currentData()
        if pid is None: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.add_preset_id(ctx.selected_ids, pid)

    def reorder_item(self, old_index, new_index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.reorder_preset_id(ctx.selected_ids, old_index, new_index)

    def remove_item(self, index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.remove_preset_id(ctx.selected_ids, index)

class RZUnderlayerPresetList(RZListEditor):
    """A list-like widget to manage Underlayer Preset IDs."""
    def __init__(self, parent=None):
        super().__init__("+ Add Underlayer", parent)
        self.layout_main.removeWidget(self.btn_add)
        h_add = QtWidgets.QHBoxLayout()
        self.cb_add_preset = RZComboBox()
        h_add.addWidget(self.cb_add_preset, 1)
        h_add.addWidget(self.btn_add)
        self.layout_main.addLayout(h_add)

    def update_data(self, preset_list):
        elements = core.read.get_all_elements_list()
        name_map = {e['id']: e['name'] for e in elements}
            
        def factory(i, pid):
            name = name_map.get(pid, "Unknown")
            return RZPresetItem(i, pid, name, self)
            
        def updater(w, pid):
            w.blockSignals(True)
            name = name_map.get(pid, "Unknown")
            w.update_data(pid, name)
            w.blockSignals(False)
            
        self.sync_widgets(preset_list, factory, updater)
        
        # Update dropdown with available preset elements
        self.cb_add_preset.blockSignals(True)
        self.cb_add_preset.clear()
        preset_elements = [e for e in elements if e.get('is_preset', False)]
        for e in preset_elements:
            self.cb_add_preset.addItem(f"{e['name']} (ID: {e['id']})", e['id'])
        self.cb_add_preset.blockSignals(False)

    def add_item(self):
        if self._block: return
        pid = self.cb_add_preset.currentData()
        if pid is None: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.add_underlayer_preset_id(ctx.selected_ids, pid)

    def reorder_item(self, old_index, new_index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.reorder_underlayer_preset_id(ctx.selected_ids, old_index, new_index)

    def remove_item(self, index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            core.props.remove_underlayer_preset_id(ctx.selected_ids, index)


class RZMInspectorPanel(RZEditorPanel):
    """
    Property inspector panel for editing selected element attributes.
    """
    
    PANEL_ID = "INSPECTOR"
    PANEL_NAME = "Inspector"
    PANEL_ICON = "settings"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RZMInspectorPanel")
        self.has_data = False
        self._block_signals = False
        self._is_panel_active = True
        
        # Performance: Throttle refresh to 60fps max or slightly lower
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_refresh_data)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 5, 2, 5)
        layout.setSpacing(5)
        self.setStyleSheet(f"background-color: {get_current_theme().get('bg_panel', '#2C313A')};")
        
        self.anchor_items = [
            ("Identity", "grp_ident"),
            ("Layout", "grp_anchor"),
            ("Style", "grp_style"),
            ("Logic", "grp_logic"),
            ("Events", "grp_events"),
            ("Presets", "grp_presets")
        ]
        
        self.anchor_scroll = QtWidgets.QScrollArea()
        self.anchor_scroll.setWidgetResizable(True)
        self.anchor_scroll.setFixedHeight(38)
        self.anchor_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.anchor_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.anchor_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        self.anchor_bar = RZInspectorAnchorBar(self.anchor_items)
        self.anchor_bar.clicked.connect(self._scroll_to_group)
        self.anchor_scroll.setWidget(self.anchor_bar)
        layout.addWidget(self.anchor_scroll)

        # --- MONOLITHIC SCROLL AREA ---
        self.scroll_area = RZScrollArea()
        self.scroll_area.setObjectName("InspectorScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_sync)
        
        self.scroll_content = QtWidgets.QWidget()
        self.scroll_content.setObjectName("InspectorScrollContent")
        self.scroll_content.setStyleSheet("background-color: transparent;") # Cards will have the color
        self.layout_props = QtWidgets.QVBoxLayout(self.scroll_content)
        self.layout_props.setContentsMargins(8, 15, 8, 15)
        self.layout_props.setSpacing(10)
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)
        
        self._init_properties_ui()
        self.layout_props.addStretch()

        # --- TAB 2: Raw Data ---
        self.tab_raw = QtWidgets.QWidget()
        layout_raw = QtWidgets.QVBoxLayout(self.tab_raw)
        self.table_raw = QtWidgets.QTableWidget(0, 2)
        self.table_raw.setObjectName("InspectorRawTable")
        self.table_raw.setHorizontalHeaderLabels(["Key", "Value"])
        self.table_raw.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table_raw.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table_raw.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) 
        layout_raw.addWidget(self.table_raw)
        # self.tabs.addTab(self.tab_raw, "Raw Data")

    def _scroll_to_group(self, group_name):
        """Scrolls the scroll area to the target group widget."""
        target_widget = getattr(self, group_name, None)
        if target_widget and self.scroll_area:
            # Anchor bar logic
            self.anchor_bar.set_active(group_name)
            
            # Smooth scrolling
            bar = self.scroll_area.verticalScrollBar()
            y = target_widget.geometry().top()
            
            # Use QPropertyAnimation for smooth scroll
            if not hasattr(self, "_scroll_anim"):
                self._scroll_anim = QtCore.QPropertyAnimation(bar, b"value")
                self._scroll_anim.setDuration(400)
                self._scroll_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            
            self._scroll_anim.stop()
            self._scroll_anim.setEndValue(max(0, y - 5))
            self._scroll_anim.start()

    def _on_scroll_sync(self, value):
        """Updates Anchor bar based on current scroll position."""
        if hasattr(self, "_scroll_anim") and self._scroll_anim.state() == QtCore.QPropertyAnimation.Running:
            return

        visible_y = value + 20
        best_match = self.anchor_items[0][1]
        
        for label, grp_name in self.anchor_items:
            w = getattr(self, grp_name, None)
            if w and w.geometry().top() <= visible_y:
                best_match = grp_name
            else:
                break
        
        self.anchor_bar.set_active(best_match)

    def set_row_visible(self, widget, visible):
        """Helper to hide/show both the widget and its label."""
        if hasattr(widget, '_lbl_buddy'):
            widget._lbl_buddy.setVisible(visible)
        else:
            p = widget.parentWidget()
            if p and p.layout() and isinstance(p.layout(), QtWidgets.QFormLayout):
                label = p.layout().labelForField(widget)
                if label: label.setVisible(visible)
        widget.setVisible(visible)

    def _connect_signals(self):
        SIGNALS.selection_changed.connect(self.refresh_data)
        SIGNALS.data_changed.connect(self.refresh_data)
        SIGNALS.transform_changed.connect(self.refresh_data)
    
    def _disconnect_signals(self):
        try:
            SIGNALS.selection_changed.disconnect(self.refresh_data)
            SIGNALS.data_changed.disconnect(self.refresh_data)
            SIGNALS.transform_changed.disconnect(self.refresh_data)
        except: pass

    def refresh_data(self):
        """Request a refresh (throttled)."""
        if not hasattr(self, '_is_panel_active') or not self._is_panel_active: return
        if not self._refresh_timer.isActive():
            self._refresh_timer.start(16) # ~60 FPS update limit

    def _do_refresh_data(self):
        # ЗАЩИТА: Если мышь зажата (идет перетаскивание ползунка), 
        # мы не обновляем UI, чтобы не сбить фокус и не вызывать лаг.
        if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
            # Откладываем обновление
            self._refresh_timer.start(50) 
            return

        ctx = RZContextManager.get_instance().get_snapshot()
        details = core.get_selection_details(ctx.selected_ids, ctx.active_id)
        
        # PERFORMANCE: Only update UI if something actually changed
        if hasattr(self, "_last_details") and self._last_details == details:
            return
            
        # Optimization: track ONLY fields that changed if possible
        # For now, we still call update_ui, but RZListEditor is now optimized.
        self._last_details = details
        
        self._block_signals = True
        try:
            self.update_ui(details)
        except Exception as e:
            print(f"[INSPECTOR] Error in update_ui: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._block_signals = False
    
    def _add_row(self, layout, label, widget, field_name=None, signal=None):
        """Helper to add a property row and optionally connect its change signal."""
        lbl_w = None
        if isinstance(layout, QtWidgets.QFormLayout):
            lbl_w = RZLabel(label) if isinstance(label, str) else label
            layout.addRow(lbl_w, widget)
        else:
            h = QtWidgets.QHBoxLayout()
            if label:
                lbl_w = RZLabel(label) if isinstance(label, str) else label
                h.addWidget(lbl_w)
            h.addWidget(widget)
            # Only add stretch if it's NOT a full-width code editor or list
            if not label and not isinstance(widget, (RZCodeTextEdit, RZListEditor)):
                h.addStretch()
            if hasattr(layout, 'addLayout'):
                layout.addLayout(h)
            elif hasattr(layout, 'addWidget'):
                # Handle layout as a widget or just append to layout
                dummy = QtWidgets.QWidget()
                dummy.setLayout(h)
                layout.addWidget(dummy)
        
        # Store label reference for easy visibility toggling
        if lbl_w:
            widget._lbl_buddy = lbl_w

        if field_name:
            if signal is None:
                if hasattr(widget, 'value_changed'): signal = 'value_changed'
                elif hasattr(widget, 'valueChanged'): signal = 'valueChanged'
                elif hasattr(widget, 'colorChanged'): signal = 'colorChanged'
                elif isinstance(widget, (RZComboBox, RZImageComboBox)): signal = 'currentTextChanged'
                elif isinstance(widget, RZCheckBox): signal = 'toggled'
                else: signal = 'editingFinished'
            
            sig = getattr(widget, signal, None)
            if sig:
                if signal in ['valueChanged', 'value_changed', 'colorChanged']: 
                    sig.connect(lambda v: self._emit_change(field_name, v))
                elif signal == 'currentIndexChanged':
                    sig.connect(lambda i: self._emit_change(field_name, i))
                elif signal == 'currentTextChanged': 
                    sig.connect(lambda t: self._emit_change(field_name, t))
                elif signal == 'toggled': 
                    sig.connect(lambda v: self._emit_change(field_name, v))
                else:
                    def _on_finish():
                        val = None
                        if hasattr(widget, 'text'): val = widget.text()
                        elif hasattr(widget, 'toPlainText'): val = widget.toPlainText()
                        elif hasattr(widget, 'value'): val = widget.value()
                        self._emit_change(field_name, val)
                    sig.connect(_on_finish)
        return widget

    def _init_properties_ui(self):
        sections = [
            ("Identity", self._init_identity_ui),
            ("Visibility", self._init_visibility_ui),
            ("Presets System", self._init_presets_ui),
            ("Anchor & Alignment", self._init_layout_ui),
            ("Transform", self._init_transform_ui),
            ("Grid Settings", self._init_grid_ui),
            ("Appearance", self._init_style_ui),
            ("Text content", self._init_text_ui),
            ("Value Links & FX", self._init_logic_ui),
            ("Interactions", self._init_events_ui),
            ("Special Options", self._init_special_ui),
            ("Editor Flags", self._init_flags_ui),
        ]
        
        for name, func in sections:
            try:
                func()
            except Exception as e:
                print(f"[INSPECTOR] Error initializing section '{name}': {e}")

    def _init_identity_ui(self):
        self.grp_ident = RZGroupBox("Identity")
        layout = QtWidgets.QFormLayout(self.grp_ident)
        layout.setSpacing(6)
        self.spin_id = self._add_row(layout, "ID:", RZSpinBox())
        self.spin_id.setRange(0, 99999)
        self.spin_id.editingFinished.connect(self._on_id_changed)
        
        self.name_edit = self._add_row(layout, "Name:", RZLineEdit(), 'element_name')
        self.edit_tag = self._add_row(layout, "Tag:", RZLineEdit(), 'tag')
        
        self.cb_class = self._add_row(layout, "Class:", RZComboBox(), 'class_type')
        self.cb_class.addItems(["CONTAINER", "GRID_CONTAINER", "BUTTON", "TEXT", "SLIDER", "ANCHOR"])
        
        self.spin_priority = self._add_row(layout, "Priority:", RZSpinBox(), 'priority')
        self.spin_priority.setRange(-100, 100)
        
        self.chk_main_window = self._add_row(layout, "", RZCheckBox("Is Main Window"), 'is_main_window')
        self.chk_disable_export = self._add_row(layout, "", RZCheckBox("Disable Export"), 'disable_export')
        
        self.layout_props.addWidget(self.grp_ident)

    def _init_visibility_ui(self):
        self.grp_vis = RZGroupBox("Visibility")
        layout = QtWidgets.QFormLayout(self.grp_vis)
        layout.setSpacing(6)
        self.cb_vis_mode = self._add_row(layout, "Mode:", RZComboBox(), 'visibility_mode')
        self.cb_vis_mode.addItems(["ALWAYS", "CONDITIONAL", "HIDED"])
        
        self.edit_vis_cond = RZFormulaInput()
        self.edit_vis_cond.setPlaceholderText("$var > 0")
        self._add_row(layout, "Condition:", self.edit_vis_cond, 'visibility_condition')
        
        self.layout_props.addWidget(self.grp_vis)

    def _init_presets_ui(self):
        try:
            self.grp_presets = RZGroupBox("Presets System")
            layout = QtWidgets.QVBoxLayout(self.grp_presets)
            layout.setSpacing(6)
            self.chk_is_preset = self._add_row(layout, "", RZCheckBox("Is Preset Element"), 'is_preset')
            self.chk_preset_hide = self._add_row(layout, "", RZCheckBox("Hide Presets (Overlay)"), 'qt_preset_hide')
            layout.addWidget(RZLabel("Applied Presets:"))
            self.list_presets = RZPresetList()
            layout.addWidget(self.list_presets)
            layout.addWidget(RZLabel("Applied Underlayer Presets:"))
            self.list_underlayers = RZUnderlayerPresetList()
            layout.addWidget(self.list_underlayers)
            self.layout_props.addWidget(self.grp_presets)

        except Exception as e: print(f"[INSPECTOR] Error Presets: {e}")

    def _init_layout_ui(self):
        try:
            self.grp_anchor = RZGroupBox("Anchor & Alignment")
            layout = QtWidgets.QFormLayout(self.grp_anchor)
            layout.setSpacing(6)
            self.cb_anchor = self._add_row(layout, "Anchor:", RZComboBox(), 'alignment')
            self.cb_anchor.addItems(["BOTTOM_LEFT", "BOTTOM_CENTER", "BOTTOM_RIGHT", "CENTER_LEFT", "CENTER", "CENTER_RIGHT", "TOP_LEFT", "TOP_CENTER", "TOP_RIGHT"])
            
            self.cb_text_align = self._add_row(layout, "Text Align:", RZComboBox(), 'text_align')
            self.cb_text_align.addItems(["LEFT", "CENTER", "RIGHT"])
            
            self.layout_props.addWidget(self.grp_anchor)
        except Exception as e: print(f"[INSPECTOR] Error Layout: {e}")

    def _init_transform_ui(self):
        try:
            self.grp_trans = RZGroupBox("Transform")
            layout_trans = QtWidgets.QVBoxLayout(self.grp_trans)
            layout_trans.setSpacing(4)
            layout_trans.setContentsMargins(6, 6, 6, 6)

            # --- POSITION ---
            h_pos_head = QtWidgets.QHBoxLayout()
            h_pos_head.addWidget(RZLabel("Position"))
            h_pos_head.addStretch()
            self.chk_pos_formula = self._add_row(h_pos_head, "", RZCheckBox("Formula"), 'position_is_formula')
            layout_trans.addLayout(h_pos_head)

            self.stack_pos = QtWidgets.QStackedLayout()
            layout_trans.addLayout(self.stack_pos)
            
            self.w_pos_sliders = QtWidgets.QWidget()
            l_pos_sl = QtWidgets.QVBoxLayout(self.w_pos_sliders)
            l_pos_sl.setContentsMargins(0, 0, 0, 0); l_pos_sl.setSpacing(4)
            self.sl_x = self._add_row(l_pos_sl, "X", RZSmartSlider(is_int=True, show_slider=False), 'pos_x', 'value_changed')
            self.sl_y = self._add_row(l_pos_sl, "Y", RZSmartSlider(is_int=True, show_slider=False), 'pos_y', 'value_changed')
            self.sl_x.math_requested.connect(lambda op: self._emit_math('pos_x', op))
            self.sl_y.math_requested.connect(lambda op: self._emit_math('pos_y', op))
            self.stack_pos.addWidget(self.w_pos_sliders)

            self.w_pos_formulas = QtWidgets.QWidget()
            l_pos_f = QtWidgets.QVBoxLayout(self.w_pos_formulas)
            l_pos_f.setContentsMargins(0, 0, 0, 0); l_pos_f.setSpacing(4)
            self.edit_pos_fx = self._add_row(l_pos_f, "X:", RZFormulaInput(), 'position_formula_x')
            self.edit_pos_fy = self._add_row(l_pos_f, "Y:", RZFormulaInput(), 'position_formula_y')
            self.stack_pos.addWidget(self.w_pos_formulas)
            self.chk_pos_formula.toggled.connect(lambda v: self.stack_pos.setCurrentIndex(1 if v else 0))

            # --- SIZE ---
            h_size_head = QtWidgets.QHBoxLayout()
            h_size_head.addWidget(RZLabel("Size"))
            h_size_head.addStretch()
            self.chk_size_formula = self._add_row(h_size_head, "", RZCheckBox("Formula"), 'size_is_formula')
            layout_trans.addLayout(h_size_head)

            self.stack_size = QtWidgets.QStackedLayout()
            layout_trans.addLayout(self.stack_size)

            self.w_size_sliders = QtWidgets.QWidget()
            l_size_sl = QtWidgets.QVBoxLayout(self.w_size_sliders)
            l_size_sl.setContentsMargins(0, 0, 0, 0); l_size_sl.setSpacing(4)
            self.sl_w = self._add_row(l_size_sl, "W", RZSmartSlider(is_int=True, show_slider=False), 'width', 'value_changed')
            self.sl_h = self._add_row(l_size_sl, "H", RZSmartSlider(is_int=True, show_slider=False), 'height', 'value_changed')
            self.sl_w.math_requested.connect(lambda op: self._emit_math('width', op))
            self.sl_h.math_requested.connect(lambda op: self._emit_math('height', op))
            self.stack_size.addWidget(self.w_size_sliders)

            self.w_size_formulas = QtWidgets.QWidget()
            l_size_f = QtWidgets.QVBoxLayout(self.w_size_formulas)
            l_size_f.setContentsMargins(0, 0, 0, 0); l_size_f.setSpacing(4)
            self.edit_size_fx = self._add_row(l_size_f, "W:", RZFormulaInput(), 'size_formula_x')
            self.edit_size_fy = self._add_row(l_size_f, "H:", RZFormulaInput(), 'size_formula_y')
            self.stack_size.addWidget(self.w_size_formulas)
            self.chk_size_formula.toggled.connect(lambda v: self.stack_size.setCurrentIndex(1 if v else 0))

            # --- GLOBAL TRANSFORM ---
            h_tf_head = QtWidgets.QHBoxLayout()
            h_tf_head.addWidget(RZLabel("Global Transform"))
            h_tf_head.addStretch()
            self.chk_trans_formula = self._add_row(h_tf_head, "", RZCheckBox("Formula"), 'transform_is_formula')
            layout_trans.addLayout(h_tf_head)
            self.edit_trans_fx = self._add_row(layout_trans, "", RZCodeTextEdit(), 'transform_formula')
            self.edit_trans_fx.setPlaceholderText("Transform(x, y, w, h)...")
            self.edit_trans_fx.setMinimumHeight(120); self.edit_trans_fx.setMaximumHeight(400)
            self.chk_trans_formula.toggled.connect(self.edit_trans_fx.setVisible)

            self.layout_props.addWidget(self.grp_trans)
        except Exception as e: print(f"[INSPECTOR] Error Transform: {e}")

    def _init_grid_ui(self):
        try:
            self.grp_grid = RZGroupBox("Grid Settings")
            layout = QtWidgets.QVBoxLayout(self.grp_grid)
            layout.setSpacing(6)
            self.sl_cell = self._add_row(layout, "Cell Size", RZSmartSlider(is_int=True), 'grid_cell_size', 'value_changed')
            h_x = QtWidgets.QHBoxLayout()
            self.sl_min_c = self._add_row(h_x, "MinX", RZSmartSlider(is_int=True), None); self.sl_min_c.value_changed.connect(lambda v: self._emit_change('grid_min_cells', int(v), 0))
            self.sl_max_c = self._add_row(h_x, "MaxX", RZSmartSlider(is_int=True), None); self.sl_max_c.value_changed.connect(lambda v: self._emit_change('grid_max_cells', int(v), 0))
            layout.addLayout(h_x)
            h_y = QtWidgets.QHBoxLayout()
            self.sl_min_r = self._add_row(h_y, "MinY", RZSmartSlider(is_int=True), None); self.sl_min_r.value_changed.connect(lambda v: self._emit_change('grid_min_cells', int(v), 1))
            self.sl_max_r = self._add_row(h_y, "MaxY", RZSmartSlider(is_int=True), None); self.sl_max_r.value_changed.connect(lambda v: self._emit_change('grid_max_cells', int(v), 1))
            layout.addLayout(h_y)
            self.cb_grid_wrap = self._add_row(layout, "Wrap:", RZComboBox(), 'grid_wrap_mode')
            self.cb_grid_wrap.addItems(["SCROLL", "PAGINATE"])
            self.layout_props.addWidget(self.grp_grid)
        except Exception as e: print(f"[INSPECTOR] Error Grid: {e}")

    def _init_style_ui(self):
        try:
            self.grp_style = RZGroupBox("Appearance")
            layout = QtWidgets.QVBoxLayout(self.grp_style)
            layout.setSpacing(6)
            
            h_col = QtWidgets.QHBoxLayout(); h_col.addWidget(RZLabel("Color:")); h_col.addStretch()
            self.chk_color_formula = self._add_row(h_col, "", RZCheckBox("Formula"), 'color_is_formula')
            layout.addLayout(h_col)
            
            self.stack_color = QtWidgets.QStackedLayout()
            self.btn_color = self._add_row(None, None, RZAdvancedColorPanel(), 'color', 'colorChanged')
            self.stack_color.addWidget(self.btn_color)
            
            self.w_color_formulas = QtWidgets.QWidget(); l_col_f = QtWidgets.QVBoxLayout(self.w_color_formulas); l_col_f.setContentsMargins(0, 0, 0, 0); l_col_f.setSpacing(2)
            for chan in ['r','g','b','a']:
                edit = self._add_row(l_col_f, f"{chan.upper()}:", RZFormulaInput(), f'color_formula_{chan}')
                edit.setFixedHeight(30) # Compressed per user request
                setattr(self, f"edit_col_{chan}", edit)
            self.stack_color.addWidget(self.w_color_formulas)
            layout.addLayout(self.stack_color)
            self.chk_color_formula.toggled.connect(lambda v: self.stack_color.setCurrentIndex(1 if v else 0))
            
            self.cb_img_mode = self._add_row(layout, "Image Mode:", RZComboBox(), 'image_mode')
            self.cb_img_mode.addItems(["SINGLE", "CONDITIONAL_LIST", "INDEX_LIST"])
            
            self.cb_blend_mode = self._add_row(layout, "Blend Mode:", RZComboBox(), 'image_blending_mode')
            self.cb_blend_mode.addItems(["NONE", "OVERLAY", "COLOR"])
            
            self.cb_image = self._add_row(layout, "Image:", RZImageComboBox(), 'image_id', 'value_changed')
            self.cb_hover_image = self._add_row(layout, "Hover Image:", RZImageComboBox(), 'hover_image_id', 'value_changed')
            
            h_flip = QtWidgets.QHBoxLayout()
            self.chk_flip_x = self._add_row(h_flip, "", RZCheckBox("Flip X"), 'flip_x')
            self.chk_flip_y = self._add_row(h_flip, "", RZCheckBox("Flip Y"), 'flip_y')
            layout.addLayout(h_flip)
            
            self.grp_tile = RZGroupBox("Tile Settings")
            f_tile = QtWidgets.QFormLayout(self.grp_tile); f_tile.setSpacing(6)
            self.tile_uv_x = self._add_row(f_tile, "UV X:", RZSpinBox(), 'tile_uv_x')
            self.tile_uv_y = self._add_row(f_tile, "UV Y:", RZSpinBox(), 'tile_uv_y')
            layout.addWidget(self.grp_tile)
            
            self.list_images = RZConditionalImageList()
            layout.addWidget(self.list_images)
            self.layout_props.addWidget(self.grp_style)
        except Exception as e: print(f"[INSPECTOR] Error Style: {e}")

    def _init_text_ui(self):
        try:
            self.grp_text = RZGroupBox("Text content")
            layout = QtWidgets.QVBoxLayout(self.grp_text)
            layout.setSpacing(6)
            
            self.cb_font_slot = self._add_row(layout, "Font Slot:", RZFontSlotComboBox(), 'font_slot', 'currentIndexChanged')
            
            self.cb_text_mode = self._add_row(layout, "Text Mode:", RZComboBox(), 'text_mode')
            self.cb_text_mode.addItems(["SINGLE", "CONDITIONAL_LIST", "INDEX_LIST"])
            
            self.list_texts = RZConditionalTextList()
            layout.addWidget(self.list_texts)
            
            self.w_legacy_text = QtWidgets.QWidget(); f_txt = QtWidgets.QFormLayout(self.w_legacy_text); f_txt.setContentsMargins(0, 0, 0, 0); f_txt.setSpacing(5)
            self.edit_txt_id = self._add_row(f_txt, "Text ID:", RZLineEdit(), 'text_id')
            self.edit_hov_txt = self._add_row(f_txt, "Hover ID:", RZLineEdit(), 'hover_text_id')
            layout.addWidget(self.w_legacy_text)
            self.layout_props.addWidget(self.grp_text)
        except Exception as e: print(f"[INSPECTOR] Error Text: {e}")

    def _init_logic_ui(self):
        try:
            self.grp_logic = RZGroupBox("Value Links & FX")
            layout = QtWidgets.QVBoxLayout(self.grp_logic)
            layout.setSpacing(6)
            self.chk_vl_formula = self._add_row(layout, "", RZCheckBox("Formula Mode"), 'value_link_is_formula')
            self.list_links = RZValueLinkList()
            layout.addWidget(self.list_links)
            self.edit_vl_formula = self._add_row(layout, "", RZCodeTextEdit(), 'value_link_formula')
            self.edit_vl_formula.setPlaceholderText("Link Formula..."); self.edit_vl_formula.setMinimumHeight(140)
            self.list_fx = RZFXList()
            layout.addWidget(self.list_fx)
            self.layout_props.addWidget(self.grp_logic)
        except Exception as e: print(f"[INSPECTOR] Error Logic: {e}")

    def _init_events_ui(self):
        try:
            self.grp_events = RZGroupBox("Interactions")
            layout = QtWidgets.QVBoxLayout(self.grp_events)
            layout.setSpacing(6)
            h_hov = QtWidgets.QHBoxLayout(); h_hov.addWidget(RZLabel("Hover Event")); h_hov.addStretch()
            self.chk_hover_event = self._add_row(h_hov, "", RZCheckBox("Enable"), 'hover_event_enabled')
            layout.addLayout(h_hov)
            self.edit_hover_fx = self._add_row(layout, "", RZCodeTextEdit(), 'hover_event_formula')
            self.edit_hover_fx.setPlaceholderText("On hover..."); self.edit_hover_fx.setMinimumHeight(120)
            self.chk_hover_event.toggled.connect(self.edit_hover_fx.setVisible)
            
            h_clk = QtWidgets.QHBoxLayout(); h_clk.addWidget(RZLabel("Click Event")); h_clk.addStretch()
            self.chk_click_event = self._add_row(h_clk, "", RZCheckBox("Enable"), 'click_event_enabled')
            layout.addLayout(h_clk)
            self.edit_click_fx = self._add_row(layout, "", RZCodeTextEdit(), 'click_event_formula')
            self.edit_click_fx.setPlaceholderText("On click..."); self.edit_click_fx.setMinimumHeight(120)
            self.chk_click_event.toggled.connect(self.edit_click_fx.setVisible)
            
            self.layout_props.addWidget(self.grp_events)
        except Exception as e: print(f"[INSPECTOR] Error Events: {e}")

    def _init_special_ui(self):
        try:
            self.grp_special = RZGroupBox("Special Options")
            layout = QtWidgets.QVBoxLayout(self.grp_special)
            self.chk_no_nums = self._add_row(layout, "", RZCheckBox("Disable Button Nums"), 'disable_button_nums')
            self.chk_no_popup = self._add_row(layout, "", RZCheckBox("Disable Button Popup"), 'disable_button_popup')
            
            self.chk_no_slider_nums = self._add_row(layout, "", RZCheckBox("Disable Slider Nums"), 'disable_slider_nums')
            self.chk_no_slider_blur = self._add_row(layout, "", RZCheckBox("Disable Slider Blur"), 'disable_slider_blur')
            self.chk_force_std = self._add_row(layout, "", RZCheckBox("Force Standard Render"), 'disable_slider_prebuild_render')
            
            self.layout_props.addWidget(self.grp_special)
        except Exception as e: print(f"[INSPECTOR] Error Special UI: {e}")

    def _init_flags_ui(self):
        try:
            self.grp_flags = RZGroupBox("Editor Flags")
            layout = QtWidgets.QVBoxLayout(self.grp_flags)
            self.chk_hide = self._add_row(layout, "", RZCheckBox("Is Hidden"), 'qt_hide')
            self.chk_locked = self._add_row(layout, "", RZCheckBox("Lock Transform"), 'qt_locked_ui')
            self.chk_tab = self._add_row(layout, "", RZCheckBox("Is Page (Isolation Root)"), 'is_tab_container')
            self.btn_page_color = self._add_row(layout, "Page Tab Color:", RZColorButton(), 'page_color', 'colorChanged')
            self.chk_tab.toggled.connect(self.btn_page_color.setVisible)
            self.layout_props.addWidget(self.grp_flags)
        except Exception as e: print(f"[INSPECTOR] Error Flags: {e}")

    def _emit_change(self, key, val, sub=None):
        """Handle property changes - directly update core."""
        if self.has_data and not self._block_signals:
            if val == "Mixed": return
            ctx = RZContextManager.get_instance().get_snapshot()
            if not ctx.selected_ids: return

            # SPECIAL: Unified Lock UI -> Dual Properties
            if key == 'qt_locked_ui':
                core.update_property_multi(ctx.selected_ids, 'qt_lock_pos', val)
                core.update_property_multi(ctx.selected_ids, 'qt_lock_size', val)
                return

            # Check for pattern mode (multi-renaming)
            is_pattern_edit = False
            if key == 'element_name' and self.name_edit.get_pattern():
                is_pattern_edit = True
                originals = self.name_edit.get_originals()
                print(f"[INSPECTOR] Pattern edit for 'element_name'. Originals ({len(originals)}): {originals}")
                core.props.update_property_multi_pattern(ctx.selected_ids, key, val, sub, originals)
            elif key == 'text_id' and self.edit_txt_id.get_pattern():
                is_pattern_edit = True
                originals = self.edit_txt_id.get_originals()
                print(f"[INSPECTOR] Pattern edit for 'text_id'. Originals ({len(originals)}): {originals}")
                core.props.update_property_multi_pattern(ctx.selected_ids, key, val, sub, originals)
            elif key == 'hover_text_id' and self.edit_hov_txt.get_pattern():
                is_pattern_edit = True
                originals = self.edit_hov_txt.get_originals()
                print(f"[INSPECTOR] Pattern edit for 'hover_text_id'. Originals ({len(originals)}): {originals}")
                core.props.update_property_multi_pattern(ctx.selected_ids, key, val, sub, originals)
            
            if is_pattern_edit:
                return

            # Safety: don't allow writing literal "..." in standard mode if multi-selected
            if len(ctx.selected_ids) > 1 and isinstance(val, str) and "..." in val:
                print(f"[INSPECTOR] Blocking standard update for '{key}' because it contains '...' but no pattern mode active.")
                return

            print(f"[INSPECTOR] Standard update for '{key}': {val}")
            if is_pattern_edit:
                return

            # Safety: don't allow writing literal "..." in standard mode if multi-selected
            if len(ctx.selected_ids) > 1 and isinstance(val, str) and "..." in val:
                print(f"[INSPECTOR] Blocking standard update for '{key}' because it contains '...' but no pattern mode active.")
                return

            print(f"[INSPECTOR] Standard update for '{key}': {val} (type: {type(val)})")
            core.update_property_multi(ctx.selected_ids, key, val, sub)

    def _on_id_changed(self):
        if self._block_signals: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if len(ctx.selected_ids) != 1: return
        
        old_id = ctx.active_id
        new_id = int(self.spin_id.value())
        if old_id == new_id: return
        
        # Use specialized ID updater
        core.props.update_element_id(old_id, new_id)

    def _emit_math(self, key, op_str):
        ctx = RZContextManager.get_instance().get_snapshot()
        if not ctx.selected_ids: return
        core.perform_math_operation(list(ctx.selected_ids), key, op_str)

    def update_ui(self, props):
        """Refreshes all UI widgets with data from the props dictionary."""
        # Note: self._block_signals is handled in _do_refresh_data
        
        if props and props.get('exists'):
            # DEBUG: Trace where 0 0 0 0 comes from
            print(f"[INSPECTOR] update_ui: pos_x={props.get('pos_x')}, pos_y={props.get('pos_y')}, w={props.get('width')}, h={props.get('height')}")
            
            self.has_data = True
            self.scroll_content.setEnabled(True)
            self.tab_raw.setEnabled(True)
            
            # --- Identity ---
            is_single = not props.get('is_multi')
            if hasattr(self, 'spin_id'):
                self.spin_id.setEnabled(is_single)
                if is_single:
                    self.spin_id.setValue(props.get('id', 0))
                else:
                    self.spin_id.setSpecialValueText("Multiple")
                    self.spin_id.setValue(0)
            
            # Pattern mode for Name
            name_pattern = props.get('name_pattern')
            if hasattr(self, 'name_edit'):
                if name_pattern:
                    self.name_edit.set_pattern(name_pattern, props.get('original_names'))
                else:
                    self.name_edit.clear_pattern()
                    self.name_edit.set_text_silent(props.get('name', ''))
            
            if hasattr(self, 'edit_tag'): self.edit_tag.set_text_silent(props.get('tag', ''))
            if hasattr(self, 'spin_priority'): self.spin_priority.setValue(props.get('priority', 0))
            if hasattr(self, 'chk_main_window'): self.chk_main_window.setChecked(props.get('is_main_window') is True)
            if hasattr(self, 'chk_disable_export'): self.chk_disable_export.setChecked(props.get('disable_export') is True)

            class_type = props.get('class_type')
            if hasattr(self, 'cb_class'):
                if class_type: self.cb_class.setCurrentText(class_type)
                else: self.cb_class.setCurrentText("Mixed")

            # --- Presets ---
            if hasattr(self, 'chk_is_preset'): self.chk_is_preset.setChecked(props.get('is_preset') is True)
            if hasattr(self, 'chk_preset_hide'): self.chk_preset_hide.setChecked(props.get('qt_preset_hide') is True)
            if hasattr(self, 'list_presets'): self.list_presets.update_data(props.get('preset_ids', []))
            if hasattr(self, 'list_underlayers'): self.list_underlayers.update_data(props.get('underlayer_preset_ids', []))


            # --- Visibility ---
            vis_mode = props.get('visibility_mode', 'ALWAYS')
            if hasattr(self, 'cb_vis_mode'): self.cb_vis_mode.setCurrentText(vis_mode)
            is_cond = (vis_mode == 'CONDITIONAL')
            if hasattr(self, 'edit_vis_cond'):
                self.set_row_visible(self.edit_vis_cond, is_cond)
                self.edit_vis_cond.set_text_silent(props.get('visibility_condition', ''))

            # --- Anchor ---
            if hasattr(self, 'cb_anchor'): self.cb_anchor.setCurrentText(props.get('alignment') or "Mixed")
            
            has_text = class_type in ["TEXT", "BUTTON"] or class_type is None
            if hasattr(self, 'cb_text_align'):
                self.set_row_visible(self.cb_text_align, has_text)
                self.cb_text_align.setCurrentText(props.get('text_align') or "Mixed")

            # --- Transform (Formula Switching) ---
            pos_is_form = props.get('position_is_formula') is True
            if hasattr(self, 'chk_pos_formula'): self.chk_pos_formula.setChecked(pos_is_form)
            if hasattr(self, 'stack_pos'): self.stack_pos.setCurrentIndex(1 if pos_is_form else 0)
            
            if pos_is_form:
                if hasattr(self, 'edit_pos_fx'): self.edit_pos_fx.set_text_silent(props.get('position_formula_x', ''))
                if hasattr(self, 'edit_pos_fy'): self.edit_pos_fy.set_text_silent(props.get('position_formula_y', ''))
            else:
                if hasattr(self, 'sl_x'): self.sl_x.set_value_from_backend(props.get('pos_x'))
                if hasattr(self, 'sl_y'): self.sl_y.set_value_from_backend(props.get('pos_y'))

            size_is_form = props.get('size_is_formula') is True
            if hasattr(self, 'chk_size_formula'): self.chk_size_formula.setChecked(size_is_form)
            if hasattr(self, 'stack_size'): self.stack_size.setCurrentIndex(1 if size_is_form else 0)
            
            if size_is_form:
                if hasattr(self, 'edit_size_fx'): self.edit_size_fx.set_text_silent(props.get('size_formula_x', ''))
                if hasattr(self, 'edit_size_fy'): self.edit_size_fy.set_text_silent(props.get('size_formula_y', ''))
            else:
                if hasattr(self, 'sl_w'): self.sl_w.set_value_from_backend(props.get('width'))
                if hasattr(self, 'sl_h'): self.sl_h.set_value_from_backend(props.get('height'))
            
            # Locking Logic
            is_locked_pos = props.get('is_locked_pos', False)
            is_locked_size = props.get('is_locked_size', False)
            is_grid_child = props.get('is_grid_child', False)
            
            # Formulas ignore the 'locked' flag per user request, allowing logic editing 
            # while protecting against accidental viewport drags.
            can_edit_pos_formula = True 
            can_edit_pos_manual = (is_locked_pos is not True) and (not is_grid_child)
            can_edit_size = (is_locked_size is not True)
            
            if hasattr(self, 'sl_x'): self.sl_x.setEnabled(can_edit_pos_manual)
            if hasattr(self, 'sl_y'): self.sl_y.setEnabled(can_edit_pos_manual)
            if hasattr(self, 'edit_pos_fx'): self.edit_pos_fx.setEnabled(can_edit_pos_formula)
            if hasattr(self, 'edit_pos_fy'): self.edit_pos_fy.setEnabled(can_edit_pos_formula)
            
            if hasattr(self, 'sl_w') and hasattr(self, 'sl_h'):
                self.sl_w.setEnabled(can_edit_size)
                self.sl_h.setEnabled(can_edit_size)

            # --- Transform Formula ---
            trans_is_form = props.get('transform_is_formula') is True
            if hasattr(self, 'chk_trans_formula'):
                self.chk_trans_formula.setChecked(trans_is_form)
            
            if hasattr(self, 'edit_trans_fx'):
                self.edit_trans_fx.set_text_silent(props.get('transform_formula', ''))
                self.edit_trans_fx.setVisible(trans_is_form)

            # --- Appearance ---
            if hasattr(self, 'cb_class'):
                self.cb_class.setCurrentText(class_type or 'CONTAINER')
            
            # --- Grid Container ---
            is_grid = (class_type == "GRID_CONTAINER")
            if hasattr(self, 'grp_grid'): self.grp_grid.setVisible(is_grid)
            if hasattr(self, 'grp_tile'): self.grp_tile.setVisible(is_grid)
            
            if is_grid:
                if hasattr(self, 'sl_cell'): self.sl_cell.set_value_from_backend(props.get('grid_cell_size'))
                if hasattr(self, 'sl_min_c'): self.sl_min_c.set_value_from_backend(props.get('grid_min_cells_x'))
                if hasattr(self, 'sl_min_r'): self.sl_min_r.set_value_from_backend(props.get('grid_min_cells_y'))
                if hasattr(self, 'sl_max_c'): self.sl_max_c.set_value_from_backend(props.get('grid_max_cells_x'))
                if hasattr(self, 'sl_max_r'): self.sl_max_r.set_value_from_backend(props.get('grid_max_cells_y'))
                if hasattr(self, 'cb_grid_wrap'): self.cb_grid_wrap.setCurrentText(props.get('grid_wrap_mode', 'SCROLL'))
                if hasattr(self, 'tile_uv_x'): self.tile_uv_x.setValue(props.get('tile_uv_x', 0))
                if hasattr(self, 'tile_uv_y'): self.tile_uv_y.setValue(props.get('tile_uv_y', 0))

            # --- Color ---
            col_is_form = props.get('color_is_formula') is True
            if hasattr(self, 'chk_color_formula'): self.chk_color_formula.setChecked(col_is_form)
            if hasattr(self, 'stack_color'): self.stack_color.setCurrentIndex(1 if col_is_form else 0)
            
            if col_is_form:
                if hasattr(self, 'edit_col_r'): self.edit_col_r.set_text_silent(props.get('color_formula_r', ''))
                if hasattr(self, 'edit_col_g'): self.edit_col_g.set_text_silent(props.get('color_formula_g', ''))
                if hasattr(self, 'edit_col_b'): self.edit_col_b.set_text_silent(props.get('color_formula_b', ''))
                if hasattr(self, 'edit_col_a'): self.edit_col_a.set_text_silent(props.get('color_formula_a', ''))
            else:
                if hasattr(self, 'btn_color'): self.btn_color.set_color(props.get('color'))
            
            # --- Image ---
            img_mode = props.get('image_mode', 'SINGLE')
            if hasattr(self, 'cb_img_mode'): self.cb_img_mode.setCurrentText(img_mode)
            if hasattr(self, 'cb_blend_mode'): self.cb_blend_mode.setCurrentText(props.get('image_blending_mode', 'NONE'))
            
            is_img_single = (img_mode == 'SINGLE')
            if hasattr(self, 'cb_image'): self.set_row_visible(self.cb_image, is_img_single)
            if hasattr(self, 'cb_hover_image'): self.set_row_visible(self.cb_hover_image, is_img_single)
            if hasattr(self, 'list_images'): self.list_images.setVisible(not is_img_single)
            
            if hasattr(self, 'chk_flip_x'): self.chk_flip_x.setChecked(props.get('flip_x') is True)
            if hasattr(self, 'chk_flip_y'): self.chk_flip_y.setChecked(props.get('flip_y') is True)
            
            all_images = core.read.get_available_images()
            if is_img_single:
                if hasattr(self, 'cb_image'):
                    self.cb_image.update_items(all_images)
                    self.cb_image.set_value(props.get('image_id', -1))
                if hasattr(self, 'cb_hover_image'):
                    self.cb_hover_image.update_items(all_images)
                    self.cb_hover_image.set_value(props.get('hover_image_id', -1))
            else:
                if hasattr(self, 'list_images'):
                    self.list_images.update_data(props.get('conditional_images', []), all_images, img_mode)
            
            # --- Text ---
            if hasattr(self, 'cb_font_slot'):
                self.cb_font_slot.refresh_slots()
                idx = props.get('font_slot', 0)
                self.cb_font_slot.setCurrentIndex(idx)
                
            txt_mode = props.get('text_mode', 'SINGLE')
            if hasattr(self, 'cb_text_mode'): self.cb_text_mode.setCurrentText(txt_mode)
            is_txt_single = (txt_mode == 'SINGLE')
            
            if hasattr(self, 'w_legacy_text'): self.w_legacy_text.setVisible(is_txt_single)
            if hasattr(self, 'list_texts'): self.list_texts.setVisible(not is_txt_single)
            
            if is_txt_single:
                txt_pat = props.get('text_id_pattern')
                if hasattr(self, 'edit_txt_id'):
                    if txt_pat: self.edit_txt_id.set_pattern(txt_pat, props.get('original_text_ids'))
                    else:
                        self.edit_txt_id.clear_pattern()
                        self.edit_txt_id.set_text_silent(props.get('text_id', ''))
                        
                hov_pat = props.get('hover_text_id_pattern')
                if hasattr(self, 'edit_hov_txt'):
                    if hov_pat: self.edit_hov_txt.set_pattern(hov_pat, props.get('original_hover_text_ids'))
                    else:
                        self.edit_hov_txt.clear_pattern()
                        self.edit_hov_txt.set_text_silent(props.get('hover_text_id', ''))
            else:
                if hasattr(self, 'list_texts'): self.list_texts.update_data(props.get('conditional_texts', []), txt_mode)

            # --- Logic ---
            vl_is_form = props.get('value_link_is_formula') is True
            if hasattr(self, 'chk_vl_formula'): self.chk_vl_formula.setChecked(vl_is_form)
            if hasattr(self, 'list_links'): self.list_links.update_data(props.get('value_links', []), class_type == 'SLIDER')
            if hasattr(self, 'edit_vl_formula'):
                self.edit_vl_formula.set_text_silent(props.get('value_link_formula', ''))
                self.edit_vl_formula.setVisible(vl_is_form)
            
            # --- Events ---
            if hasattr(self, 'chk_hover_event'): self.chk_hover_event.setChecked(props.get('hover_event_enabled') is True)
            if hasattr(self, 'edit_hover_fx'):
                self.edit_hover_fx.set_text_silent(props.get('hover_event_formula', ''))
                self.edit_hover_fx.setVisible(hasattr(self, 'chk_hover_event') and self.chk_hover_event.isChecked())
            
            if hasattr(self, 'chk_click_event'): self.chk_click_event.setChecked(props.get('click_event_enabled') is True)
            if hasattr(self, 'edit_click_fx'):
                self.edit_click_fx.set_text_silent(props.get('click_event_formula', ''))
                self.edit_click_fx.setVisible(hasattr(self, 'chk_click_event') and self.chk_click_event.isChecked())
            
            if hasattr(self, 'list_fx'): self.list_fx.update_data(props.get('fx', []))

            # --- Special Options (Button/Slider) ---
            is_btn = (class_type == "BUTTON")
            is_slider = (class_type == "SLIDER")
            if hasattr(self, 'grp_special'): self.grp_special.setVisible(is_btn or is_slider)
            
            if hasattr(self, 'chk_no_nums'): self.set_row_visible(self.chk_no_nums, is_btn)
            if hasattr(self, 'chk_no_popup'): self.set_row_visible(self.chk_no_popup, is_btn)
            
            if hasattr(self, 'chk_no_slider_nums'): self.set_row_visible(self.chk_no_slider_nums, is_slider)
            if hasattr(self, 'chk_no_slider_blur'): self.set_row_visible(self.chk_no_slider_blur, is_slider)
            if hasattr(self, 'chk_force_std'): self.set_row_visible(self.chk_force_std, is_slider)

            if is_btn:
                if hasattr(self, 'chk_no_nums'): self.chk_no_nums.setChecked(props.get('disable_button_nums') is True)
                if hasattr(self, 'chk_no_popup'): self.chk_no_popup.setChecked(props.get('disable_button_popup') is True)
            
            if is_slider:
                if hasattr(self, 'chk_no_slider_nums'): self.chk_no_slider_nums.setChecked(props.get('disable_slider_nums') is True)
                if hasattr(self, 'chk_no_slider_blur'): self.chk_no_slider_blur.setChecked(props.get('disable_slider_blur') is True)
                if hasattr(self, 'chk_force_std'): self.chk_force_std.setChecked(props.get('disable_slider_prebuild_render') is True)

            # --- Flags ---
            if hasattr(self, 'chk_hide'): self.chk_hide.setChecked(props.get('qt_hide') is True or props.get('is_hidden') is True)
            if hasattr(self, 'chk_locked'): self.chk_locked.setChecked(props.get('qt_locked_ui') is True or props.get('is_locked_pos') is True or props.get('is_locked_size') is True)
            if hasattr(self, 'chk_tab'): 
                self.chk_tab.setChecked(props.get('is_tab_container') is True)
                self.set_row_visible(self.chk_tab, True) # Visible for all as per user request
            
            if hasattr(self, 'btn_page_color'):
                self.btn_page_color.set_color(props.get('page_color'))
                self.set_row_visible(self.btn_page_color, props.get('is_tab_container') is True)
            
            # --- Raw Data Table ---
            if hasattr(self, 'table_raw'):
                self.table_raw.setRowCount(0)
                sorted_keys = sorted(props.keys())
                self.table_raw.setRowCount(len(sorted_keys))
                for r, key in enumerate(sorted_keys):
                    val = str(props[key])
                    self.table_raw.setItem(r, 0, QtWidgets.QTableWidgetItem(key))
                    self.table_raw.setItem(r, 1, QtWidgets.QTableWidgetItem(val))

        else:
            self.has_data = False
            if hasattr(self, 'scroll_content'): self.scroll_content.setEnabled(False)
            if hasattr(self, 'table_raw'): self.table_raw.setRowCount(0)
            if hasattr(self, 'anchor_scroll'): self.anchor_scroll.setEnabled(False)
            if hasattr(self, 'name_edit'): self.name_edit.clear()

        self._block_signals = False

    def update_theme_styles(self):
        from .lib.base import RZSmartSlider
        for widget in self.findChildren(QtWidgets.QWidget):
            if hasattr(widget, 'apply_theme') and callable(widget.apply_theme):
                widget.apply_theme()
        for sl in self.findChildren(RZSmartSlider):
            sl.apply_theme()
        if hasattr(self, 'btn_color'):
            self.btn_color.update_style()

    def enterEvent(self, event):
        RZContextManager.get_instance().update_input(QtGui.QCursor.pos(), (0.0, 0.0), area="INSPECTOR")
        super().enterEvent(event)

    def leaveEvent(self, event):
        RZContextManager.get_instance().update_input(QtGui.QCursor.pos(), (0.0, 0.0), area="NONE")
        super().leaveEvent(event)