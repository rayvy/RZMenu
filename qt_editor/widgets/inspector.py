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
from .lib.widgets import RZGroupBox, RZPushButton, RZLabel, RZLineEdit, RZComboBox, RZColorButton, RZCheckBox, RZSpinBox, RZDoubleSpinBox
from .panel_base import RZEditorPanel
from .. import core
from ..core.signals import SIGNALS
from ..context import RZContextManager
from ...data.constants import FX_COMMANDS

class RZConditionalImageItem(QtWidgets.QWidget):
    """A single row in the conditional image list."""
    def __init__(self, index, data, images, parent=None):
        super().__init__(parent)
        self.index = index
        self.parent_list = parent
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.edit_cond = RZFormulaInput()
        self.edit_cond.setPlaceholderText("Condition...")
        self.edit_cond.setText(data.get('condition', ''))
        self.edit_cond.editingFinished.connect(self._on_cond_changed)
        layout.addWidget(self.edit_cond, 2)
        
        self.cb_img = RZImageComboBox()
        self.cb_img.update_items(images)
        self.cb_img.set_value(data.get('image_id', -1))
        self.cb_img.value_changed.connect(self._on_img_changed)
        layout.addWidget(self.cb_img, 3)
        
        self.btn_del = RZPushButton("✕")
        self.btn_del.setFixedWidth(24)
        self.btn_del.clicked.connect(self._on_delete)
        layout.addWidget(self.btn_del)

    def _on_cond_changed(self):
        self.parent_list.item_changed(self.index, 'condition', self.edit_cond.text())

    def _on_img_changed(self, val):
        self.parent_list.item_changed(self.index, 'image_id', val)

    def _on_delete(self):
        self.parent_list.remove_item(self.index)

    def set_cond_visible(self, visible):
        self.edit_cond.setVisible(visible)

class RZConditionalImageList(QtWidgets.QWidget):
    """A list-like widget to manage ConditionalImage collection."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_main = QtWidgets.QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)
        self.layout_main.setSpacing(2)
        
        self.layout_items = QtWidgets.QVBoxLayout()
        self.layout_items.setSpacing(2)
        self.layout_main.addLayout(self.layout_items)
        
        self.btn_add = RZPushButton("+ Add Image")
        self.btn_add.clicked.connect(self.add_item)
        self.layout_main.addWidget(self.btn_add)
        
        self.items_data = []
        self.image_mode = 'SINGLE'
        self._block = False

    def update_data(self, data_list, available_images, mode):
        self._block = True
        self.items_data = data_list
        self.image_mode = mode
        
        # Clear
        while self.layout_items.count():
            w = self.layout_items.takeAt(0).widget()
            if w: w.deleteLater()
            
        for i, data in enumerate(data_list):
            item_w = RZConditionalImageItem(i, data, available_images, self)
            item_w.set_cond_visible(mode == 'CONDITIONAL_LIST')
            self.layout_items.addWidget(item_w)
        
        self._block = False

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


class RZValueLinkItem(QtWidgets.QWidget):
    """A single row in the value link list."""
    def __init__(self, index, data, is_slider, parent=None):
        super().__init__(parent)
        self.index = index
        self.parent_list = parent
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        h1 = QtWidgets.QHBoxLayout()
        h1.setSpacing(5)
        
        self.edit_name = RZFormulaInput()
        self.edit_name.setPlaceholderText("Link ($Var, @Toggle, #Shape)...")
        self.edit_name.setText(data.get('value_name', ''))
        self.edit_name.editingFinished.connect(self._on_name_changed)
        h1.addWidget(self.edit_name, 1)
        
        self.btn_del = RZPushButton("✕")
        self.btn_del.setFixedWidth(24)
        self.btn_del.clicked.connect(self._on_delete)
        h1.addWidget(self.btn_del)
        layout.addLayout(h1)
        
        # Ranges for Sliders
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
        
        layout.addWidget(self.w_ranges)
        # self.w_ranges.setVisible(is_slider)

    def _on_name_changed(self):
        self.parent_list.item_changed(self.index, 'value_name', self.edit_name.text())

    def _on_min_changed(self, val):
        self.parent_list.item_changed(self.index, 'value_min', float(val))

    def _on_max_changed(self, val):
        self.parent_list.item_changed(self.index, 'value_max', float(val))

    def _on_delete(self):
        self.parent_list.remove_item(self.index)

class RZValueLinkList(QtWidgets.QWidget):
    """A list-like widget to manage ValueLink collection."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_main = QtWidgets.QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)
        self.layout_main.setSpacing(2)
        
        self.layout_items = QtWidgets.QVBoxLayout()
        self.layout_items.setSpacing(5)
        self.layout_main.addLayout(self.layout_items)
        
        self.btn_add = RZPushButton("+ Add Link")
        self.btn_add.clicked.connect(self.add_item)
        self.layout_main.addWidget(self.btn_add)
        
        self._block = False

    def update_data(self, data_list, is_slider):
        self._block = True
        
        # Simple reconciliation
        while self.layout_items.count():
            w = self.layout_items.takeAt(0).widget()
            if w: w.deleteLater()
            
        for i, data in enumerate(data_list):
            item_w = RZValueLinkItem(i, data, is_slider, self)
            self.layout_items.addWidget(item_w)
        
        self._block = False

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
            core.props.update_value_link(ctx.selected_ids, index, field, value)


class RZFXItem(QtWidgets.QWidget):
    """A single row in the FX list."""
    
    # Теперь мы не хардкодим список здесь, 
    # а используем импортированный FX_COMMANDS

    def __init__(self, index, current_val, parent=None):
        super().__init__(parent)
        self.index = index
        self.parent_list = parent
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.cb_fx = RZComboBox()
        
        # Читаем данные из файла констант
        # Обратите внимание: распаковываем 3 значения (internal, display, desc)
        for internal, display, desc in FX_COMMANDS:
            self.cb_fx.addItem(display, internal)
            
            # БОНУС: Раз уж у нас есть описание (desc), 
            # добавим его как всплывающую подсказку для каждого пункта
            last_idx = self.cb_fx.count() - 1
            self.cb_fx.setItemData(last_idx, desc, QtCore.Qt.ToolTipRole)
            
        # Установка текущего значения
        idx = self.cb_fx.findData(current_val)
        if idx >= 0: 
            self.cb_fx.setCurrentIndex(idx)
        
        self.cb_fx.currentIndexChanged.connect(self._on_changed)
        layout.addWidget(self.cb_fx, 1)
        
        self.btn_del = RZPushButton("✕")
        self.btn_del.setFixedWidth(24)
        self.btn_del.clicked.connect(self._on_delete)
        layout.addWidget(self.btn_del)

    def _on_changed(self, idx):
        internal = self.cb_fx.itemData(idx)
        self.parent_list.item_changed(self.index, internal)

    def _on_delete(self):
        self.parent_list.remove_item(self.index)

class RZFXList(QtWidgets.QWidget):
    """A list-like widget to manage FX collection."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_main = QtWidgets.QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)
        self.layout_main.setSpacing(2)
        
        self.layout_items = QtWidgets.QVBoxLayout()
        self.layout_items.setSpacing(2)
        self.layout_main.addLayout(self.layout_items)
        
        self.btn_add = RZPushButton("+ Add Effect")
        self.btn_add.clicked.connect(self.add_item)
        self.layout_main.addWidget(self.btn_add)
        
        self._block = False

    def update_data(self, data_list):
        self._block = True
        while self.layout_items.count():
            w = self.layout_items.takeAt(0).widget()
            if w: w.deleteLater()
            
        for i, val in enumerate(data_list):
            item_w = RZFXItem(i, val, self)
            self.layout_items.addWidget(item_w)
        self._block = False

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


class RZPresetItem(QtWidgets.QWidget):
    """A single row in the Preset list."""
    def __init__(self, index, preset_id, parent=None):
        super().__init__(parent)
        self.index = index
        self.parent_list = parent
        self.preset_id = preset_id
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.lbl_id = RZLabel(f"ID: {preset_id}")
        layout.addWidget(self.lbl_id, 1)
        
        # We could potentially add a name lookup here if available in quick snapshot
        # But for now, just ID is fine.
        
        self.btn_del = RZPushButton("✕")
        self.btn_del.setFixedWidth(24)
        self.btn_del.clicked.connect(self._on_delete)
        layout.addWidget(self.btn_del)

    def _on_delete(self):
        self.parent_list.remove_item(self.index)

class RZPresetList(QtWidgets.QWidget):
    """A list-like widget to manage Preset IDs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_main = QtWidgets.QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)
        self.layout_main.setSpacing(2)
        
        self.layout_items = QtWidgets.QVBoxLayout()
        self.layout_items.setSpacing(2)
        self.layout_main.addLayout(self.layout_items)
        
        h_add = QtWidgets.QHBoxLayout()
        self.spin_id = RZSpinBox()
        self.spin_id.setRange(1, 1000000)
        self.spin_id.setPrefix("ID: ")
        h_add.addWidget(self.spin_id)
        
        self.btn_add = RZPushButton("+ Add Preset")
        self.btn_add.clicked.connect(self.add_item)
        h_add.addWidget(self.btn_add)
        self.layout_main.addLayout(h_add)
        
        self._block = False

    def update_data(self, preset_list):
        # preset_list is expected to be list of IDs or dicts?
        # In read.py we might need to parse the CollectionProperty of presets.
        # Let's assume passed data is list of integer IDs
        self._block = True
        
        while self.layout_items.count():
            w = self.layout_items.takeAt(0).widget()
            if w: w.deleteLater()
            
        for i, pid in enumerate(preset_list):
            item_w = RZPresetItem(i, pid, self)
            self.layout_items.addWidget(item_w)
        
        self._block = False

    def add_item(self):
        if self._block: return
        pid = self.spin_id.value()
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            # We need a dedicated prop function for this
            # Since core.props methods usually generic, we might need a custom one or 
            # use a generic 'add_collection_item' if available.
            # Let's assume we add a specific one in props.py or call wrapper here.
            # WRAPPER:
            import bpy
            if not bpy.context or not bpy.context.scene: return
            
            # This is "EXECUTION" logic which should be in core, but for speed logic here:
            # But wait, we can't access Blender Context safely from Qt thread regarding Undo?
            # RZMenu commands usually go through core/props.py which wraps in Undo.
            # I should add 'add_preset(ids, preset_id)' to props.py? 
            # Or just use the generic logic if possible.
            # For now, let's implement the logic here via call_op_batch-like approach or direct update
            # ACTUALLY: Best to trust core/props.py to have 'add_preset_ref'.
            # I will assume I need to implement it there or use a generic one.
            # Let's use a dynamic one defined here for now using blender_bridge
            
            def op_add_preset(elem, _pid):
                if not hasattr(elem, "presets"): return
                # Check exists
                for p in elem.presets:
                    if p.preset_id == _pid: return
                new_p = elem.presets.add()
                new_p.preset_id = _pid

            core.blender_bridge.execute_on_elements(list(ctx.selected_ids), op_add_preset, pid, undo_name="Add Preset")
            SIGNALS.data_changed.emit()

    def remove_item(self, index):
        if self._block: return
        ctx = RZContextManager.get_instance().get_snapshot()
        if ctx.selected_ids:
            def op_rem_preset(elem, _idx):
                if not hasattr(elem, "presets"): return
                if _idx < len(elem.presets):
                    elem.presets.remove(_idx)
            
            core.blender_bridge.execute_on_elements(list(ctx.selected_ids), op_rem_preset, index, undo_name="Remove Preset")
            SIGNALS.data_changed.emit()


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
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        
        # --- TAB 1: Properties ---
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setObjectName("InspectorScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.scroll_content = QtWidgets.QWidget()
        self.scroll_content.setObjectName("InspectorScrollContent")
        self.layout_props = QtWidgets.QVBoxLayout(self.scroll_content)
        self.layout_props.setContentsMargins(0, 0, 0, 0)
        self.layout_props.setSpacing(5)
        
        self.scroll_area.setWidget(self.scroll_content)
        self.tabs.addTab(self.scroll_area, "Properties")
        
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
        self.tabs.addTab(self.tab_raw, "Raw Data")
        
        self.has_data = False
        self._block_signals = False

    def set_row_visible(self, widget, visible):
        """Helper to hide/show both the widget and its label in a QFormLayout."""
        layout = None
        # Try to find which form layout contains this widget
        p = widget.parentWidget()
        if p and p.layout():
            layout = p.layout()
        
        if isinstance(layout, QtWidgets.QFormLayout):
            label = layout.labelForField(widget)
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
        if not self._is_panel_active: return
        ctx = RZContextManager.get_instance().get_snapshot()
        details = core.get_selection_details(ctx.selected_ids, ctx.active_id)
        self.update_ui(details)

    def _init_properties_ui(self):
        # === GROUP: IDENTITY ===
        grp_ident = RZGroupBox("Identity")
        form_ident = QtWidgets.QFormLayout(grp_ident)
        
        self.lbl_id = RZLabel("ID: None")
        form_ident.addRow("ID:", self.lbl_id)

        self.name_edit = RZLineEdit()
        self.name_edit.editingFinished.connect(lambda: self._emit_change('element_name', self.name_edit.text()))
        form_ident.addRow("Name:", self.name_edit)

        self.edit_tag = RZLineEdit()
        self.edit_tag.editingFinished.connect(lambda: self._emit_change('tag', self.edit_tag.text()))
        form_ident.addRow("Tag:", self.edit_tag)
        
        self.cb_class = RZComboBox()
        self.cb_class.addItems(["CONTAINER", "GRID_CONTAINER", "BUTTON", "TEXT", "SLIDER", "ANCHOR"])
        self.cb_class.currentTextChanged.connect(lambda t: self._emit_change('class_type', t))
        form_ident.addRow("Class:", self.cb_class)

        self.spin_priority = RZSpinBox()
        self.spin_priority.setRange(-100, 100)
        self.spin_priority.valueChanged.connect(lambda v: self._emit_change('priority', int(v)))
        form_ident.addRow("Priority:", self.spin_priority)

        self.chk_main_window = RZCheckBox("Is Main Window")
        self.chk_main_window.toggled.connect(lambda v: self._emit_change('is_main_window', v))
        form_ident.addRow("", self.chk_main_window)
        
        self.layout_props.addWidget(grp_ident)
        
        # === GROUP: PRESETS ===
        self.grp_presets = RZGroupBox("Presets System")
        layout_presets = QtWidgets.QVBoxLayout(self.grp_presets)
        
        self.chk_is_preset = RZCheckBox("Is Preset Element")
        self.chk_is_preset.toggled.connect(lambda v: self._emit_change('is_preset', v))
        layout_presets.addWidget(self.chk_is_preset)
        
        self.chk_preset_hide = RZCheckBox("Hide Presets (Overlay)")
        self.chk_preset_hide.toggled.connect(lambda v: self._emit_change('qt_preset_hide', v))
        layout_presets.addWidget(self.chk_preset_hide)
        
        layout_presets.addWidget(RZLabel("Applied Presets:"))
        self.list_presets = RZPresetList()
        layout_presets.addWidget(self.list_presets)
        
        self.layout_props.addWidget(self.grp_presets)

        # === GROUP: VISIBILITY ===
        self.grp_vis = RZGroupBox("Visibility")
        form_vis = QtWidgets.QFormLayout(self.grp_vis)
        
        self.cb_vis_mode = RZComboBox()
        self.cb_vis_mode.addItems(["ALWAYS", "CONDITIONAL"])
        self.cb_vis_mode.currentTextChanged.connect(lambda t: self._emit_change('visibility_mode', t))
        form_vis.addRow("Mode:", self.cb_vis_mode)

        # Using RZFormulaInput for Condition
        self.edit_vis_cond = RZFormulaInput()
        self.edit_vis_cond.setPlaceholderText("$var > 0")
        self.edit_vis_cond.editingFinished.connect(lambda: self._emit_change('visibility_condition', self.edit_vis_cond.text()))
        self.row_vis_cond = form_vis.addRow("Condition:", self.edit_vis_cond)
        
        self.layout_props.addWidget(self.grp_vis)

        # === GROUP: ANCHOR & ALIGNMENT ===
        self.grp_anchor = RZGroupBox("Anchor & Alignment")
        layout_anchor = QtWidgets.QFormLayout(self.grp_anchor)
        
        self.cb_anchor = RZComboBox()
        self.cb_anchor.addItems([
            "BOTTOM_LEFT", "BOTTOM_CENTER", "BOTTOM_RIGHT", 
            "CENTER_LEFT", "CENTER", "CENTER_RIGHT", 
            "TOP_LEFT", "TOP_CENTER", "TOP_RIGHT"
        ])
        self.cb_anchor.currentTextChanged.connect(lambda t: self._emit_change('alignment', t))
        layout_anchor.addRow("Anchor:", self.cb_anchor)
        
        self.cb_text_align = RZComboBox()
        self.cb_text_align.addItems(["LEFT", "CENTER", "RIGHT"])
        self.cb_text_align.currentTextChanged.connect(lambda t: self._emit_change('text_align', t))
        self.row_text_align = layout_anchor.addRow("Text Align:", self.cb_text_align)
        
        self.layout_props.addWidget(self.grp_anchor)

        # === GROUP: TRANSFORM (Dual Mode) ===
        self.grp_trans = RZGroupBox("Transform")
        layout_trans = QtWidgets.QVBoxLayout(self.grp_trans)
        
        # --- Position Sub-Group ---
        h_pos_head = QtWidgets.QHBoxLayout()
        h_pos_head.addWidget(RZLabel("Position"))
        h_pos_head.addStretch()
        self.chk_pos_formula = RZCheckBox("Formula")
        self.chk_pos_formula.toggled.connect(lambda v: self._emit_change('position_is_formula', v))
        h_pos_head.addWidget(self.chk_pos_formula)
        layout_trans.addLayout(h_pos_head)

        self.stack_pos = QtWidgets.QStackedLayout()
        
        # Mode 0: Sliders
        self.w_pos_sliders = QtWidgets.QWidget()
        l_pos_sl = QtWidgets.QVBoxLayout(self.w_pos_sliders)
        l_pos_sl.setContentsMargins(0,0,0,0)
        self.sl_x = RZSmartSlider(label_text="X", is_int=True)
        self.sl_x.value_changed.connect(lambda v: self._emit_change('pos_x', int(v)))
        self.sl_x.math_requested.connect(lambda op: self._emit_math('pos_x', op))
        l_pos_sl.addWidget(self.sl_x)
        self.sl_y = RZSmartSlider(label_text="Y", is_int=True)
        self.sl_y.value_changed.connect(lambda v: self._emit_change('pos_y', int(v)))
        self.sl_y.math_requested.connect(lambda op: self._emit_math('pos_y', op))
        l_pos_sl.addWidget(self.sl_y)
        self.stack_pos.addWidget(self.w_pos_sliders)

        # Mode 1: Formulas (RZFormulaInput)
        self.w_pos_formulas = QtWidgets.QWidget()
        l_pos_f = QtWidgets.QFormLayout(self.w_pos_formulas)
        l_pos_f.setContentsMargins(0,0,0,0)
        self.edit_pos_fx = RZFormulaInput()
        self.edit_pos_fx.editingFinished.connect(lambda: self._emit_change('position_formula_x', self.edit_pos_fx.text()))
        l_pos_f.addRow("X:", self.edit_pos_fx)
        self.edit_pos_fy = RZFormulaInput()
        self.edit_pos_fy.editingFinished.connect(lambda: self._emit_change('position_formula_y', self.edit_pos_fy.text()))
        l_pos_f.addRow("Y:", self.edit_pos_fy)
        self.stack_pos.addWidget(self.w_pos_formulas)

        layout_trans.addLayout(self.stack_pos)

        # --- Size Sub-Group ---
        h_size_head = QtWidgets.QHBoxLayout()
        h_size_head.addWidget(RZLabel("Size"))
        h_size_head.addStretch()
        self.chk_size_formula = RZCheckBox("Formula")
        self.chk_size_formula.toggled.connect(lambda v: self._emit_change('size_is_formula', v))
        h_size_head.addWidget(self.chk_size_formula)
        layout_trans.addLayout(h_size_head)

        self.stack_size = QtWidgets.QStackedLayout()

        # Mode 0: Sliders
        self.w_size_sliders = QtWidgets.QWidget()
        l_size_sl = QtWidgets.QVBoxLayout(self.w_size_sliders)
        l_size_sl.setContentsMargins(0,0,0,0)
        self.sl_w = RZSmartSlider(label_text="W", is_int=True)
        self.sl_w.value_changed.connect(lambda v: self._emit_change('width', int(v)))
        self.sl_w.math_requested.connect(lambda op: self._emit_math('width', op))
        l_size_sl.addWidget(self.sl_w)
        self.sl_h = RZSmartSlider(label_text="H", is_int=True)
        self.sl_h.value_changed.connect(lambda v: self._emit_change('height', int(v)))
        self.sl_h.math_requested.connect(lambda op: self._emit_math('height', op))
        l_size_sl.addWidget(self.sl_h)
        self.stack_size.addWidget(self.w_size_sliders)

        # Mode 1: Formulas (RZFormulaInput)
        self.w_size_formulas = QtWidgets.QWidget()
        l_size_f = QtWidgets.QFormLayout(self.w_size_formulas)
        l_size_f.setContentsMargins(0,0,0,0)
        self.edit_size_fx = RZFormulaInput()
        self.edit_size_fx.editingFinished.connect(lambda: self._emit_change('size_formula_x', self.edit_size_fx.text()))
        l_size_f.addRow("W:", self.edit_size_fx)
        self.edit_size_fy = RZFormulaInput()
        self.edit_size_fy.editingFinished.connect(lambda: self._emit_change('size_formula_y', self.edit_size_fy.text()))
        l_size_f.addRow("H:", self.edit_size_fy)
        self.stack_size.addWidget(self.w_size_formulas)

        layout_trans.addLayout(self.stack_size)
        self.layout_props.addWidget(self.grp_trans)

        # === GROUP: GRID ===
        self.grp_grid = RZGroupBox("Grid Settings")
        layout_grid = QtWidgets.QVBoxLayout(self.grp_grid)
        
        # Cells
        h_cell = QtWidgets.QHBoxLayout()
        h_cell.addWidget(RZLabel("Cell Size:"))
        self.sl_cell = RZSmartSlider(label_text="", is_int=True)
        self.sl_cell.value_changed.connect(lambda v: self._emit_change('grid_cell_size', int(v)))
        h_cell.addWidget(self.sl_cell)
        layout_grid.addLayout(h_cell)
        
        # Min/Max
        h_grid_mm = QtWidgets.QHBoxLayout()
        self.sl_min_c = RZSmartSlider(label_text="MinX", is_int=True)
        self.sl_min_c.value_changed.connect(lambda v: self._emit_change('grid_min_cells', int(v), 0))
        self.sl_max_c = RZSmartSlider(label_text="MaxX", is_int=True)
        self.sl_max_c.value_changed.connect(lambda v: self._emit_change('grid_max_cells', int(v), 0))
        h_grid_mm.addWidget(self.sl_min_c)
        h_grid_mm.addWidget(self.sl_max_c)
        layout_grid.addLayout(h_grid_mm)
        
        h_grid_mm_y = QtWidgets.QHBoxLayout()
        self.sl_min_r = RZSmartSlider(label_text="MinY", is_int=True)
        self.sl_min_r.value_changed.connect(lambda v: self._emit_change('grid_min_cells', int(v), 1))
        self.sl_max_r = RZSmartSlider(label_text="MaxY", is_int=True)
        self.sl_max_r.value_changed.connect(lambda v: self._emit_change('grid_max_cells', int(v), 1))
        h_grid_mm_y.addWidget(self.sl_min_r)
        h_grid_mm_y.addWidget(self.sl_max_r)
        layout_grid.addLayout(h_grid_mm_y)

        # Wrap Mode
        self.cb_grid_wrap = RZComboBox()
        self.cb_grid_wrap.addItems(["SCROLL", "PAGINATE"])
        self.cb_grid_wrap.currentTextChanged.connect(lambda t: self._emit_change('grid_wrap_mode', t))
        layout_grid.addWidget(self.cb_grid_wrap)

        self.layout_props.addWidget(self.grp_grid)

        # === GROUP: STYLE & CONTENT ===
        grp_style = RZGroupBox("Style & Content")
        layout_style = QtWidgets.QVBoxLayout(grp_style)
        
        # Color
        h_col = QtWidgets.QHBoxLayout()
        h_col.addWidget(RZLabel("Color:"))
        h_col.addStretch()
        self.chk_color_formula = RZCheckBox("Formula")
        self.chk_color_formula.toggled.connect(lambda v: self._emit_change('color_is_formula', v))
        h_col.addWidget(self.chk_color_formula)
        layout_style.addLayout(h_col)

        self.stack_color = QtWidgets.QStackedLayout()
        
        # Mode 0: Color Button
        self.btn_color = RZColorButton()
        self.btn_color.colorChanged.connect(lambda c: self._emit_change('color', c))
        self.stack_color.addWidget(self.btn_color)

        # Mode 1: Four Formula Inputs
        self.w_color_formulas = QtWidgets.QWidget()
        l_col_f = QtWidgets.QHBoxLayout(self.w_color_formulas)
        l_col_f.setContentsMargins(0, 0, 0, 0)
        l_col_f.setSpacing(2)
        
        self.edit_col_r = RZFormulaInput()
        self.edit_col_r.setPlaceholderText("R")
        self.edit_col_r.editingFinished.connect(lambda: self._emit_change('color_formula_r', self.edit_col_r.text()))
        l_col_f.addWidget(self.edit_col_r)
        
        self.edit_col_g = RZFormulaInput()
        self.edit_col_g.setPlaceholderText("G")
        self.edit_col_g.editingFinished.connect(lambda: self._emit_change('color_formula_g', self.edit_col_g.text()))
        l_col_f.addWidget(self.edit_col_g)
        
        self.edit_col_b = RZFormulaInput()
        self.edit_col_b.setPlaceholderText("B")
        self.edit_col_b.editingFinished.connect(lambda: self._emit_change('color_formula_b', self.edit_col_b.text()))
        l_col_f.addWidget(self.edit_col_b)
        
        self.edit_col_a = RZFormulaInput()
        self.edit_col_a.setPlaceholderText("A")
        self.edit_col_a.editingFinished.connect(lambda: self._emit_change('color_formula_a', self.edit_col_a.text()))
        l_col_f.addWidget(self.edit_col_a)
        
        self.stack_color.addWidget(self.w_color_formulas)
        layout_style.addLayout(self.stack_color)
        
        # Image Mode
        self.cb_img_mode = RZComboBox()
        self.cb_img_mode.addItems(["SINGLE", "CONDITIONAL_LIST", "INDEX_LIST"])
        self.cb_img_mode.currentTextChanged.connect(lambda t: self._emit_change('image_mode', t))
        layout_style.addWidget(RZLabel("Image Mode:"))
        layout_style.addWidget(self.cb_img_mode)

        # Image ID
        self.lbl_image = RZLabel("Image:")
        layout_style.addWidget(self.lbl_image)
        self.cb_image = RZImageComboBox()
        self.cb_image.value_changed.connect(lambda v: self._emit_change('image_id', v))
        layout_style.addWidget(self.cb_image)

        # Image List (Conditional / Index)
        self.list_images = RZConditionalImageList()
        layout_style.addWidget(self.list_images)
        
        # Tile Settings
        f_tile = QtWidgets.QFormLayout()
        self.tile_uv_x = RZSpinBox()
        self.tile_uv_x.valueChanged.connect(lambda v: self._emit_change('tile_uv', int(v), 0))
        f_tile.addRow("Tile X:", self.tile_uv_x)
        self.tile_uv_y = RZSpinBox()
        self.tile_uv_y.valueChanged.connect(lambda v: self._emit_change('tile_uv', int(v), 1))
        f_tile.addRow("Tile Y:", self.tile_uv_y)
        layout_style.addLayout(f_tile)
        
        # Texts
        f_txt = QtWidgets.QFormLayout()
        self.edit_txt_id = RZLineEdit()
        self.edit_txt_id.editingFinished.connect(lambda: self._emit_change('text_id', self.edit_txt_id.text()))
        f_txt.addRow("Text ID:", self.edit_txt_id)
        self.edit_hov_txt = RZLineEdit()
        self.edit_hov_txt.editingFinished.connect(lambda: self._emit_change('hover_text_id', self.edit_hov_txt.text()))
        f_txt.addRow("Hover ID:", self.edit_hov_txt)
        layout_style.addLayout(f_txt)

        self.layout_props.addWidget(grp_style)
        
        # === GROUP: LOGIC ===
        self.grp_logic = RZGroupBox("Logic")
        layout_logic = QtWidgets.QVBoxLayout(self.grp_logic)
        
        layout_logic.addWidget(RZLabel("Value Links:"))
        h_vl_formula = QtWidgets.QHBoxLayout()
        self.chk_vl_formula = RZCheckBox("Formula Mode")
        self.chk_vl_formula.toggled.connect(lambda v: self._emit_change('value_link_is_formula', v))
        h_vl_formula.addWidget(self.chk_vl_formula)
        h_vl_formula.addStretch()
        layout_logic.addLayout(h_vl_formula)

        self.stack_vl = QtWidgets.QStackedLayout()
        
        # Mode 0: List of Links
        self.list_links = RZValueLinkList()
        self.stack_vl.addWidget(self.list_links)

        # Mode 1: Raw Formula
        self.edit_vl_formula = RZCodeTextEdit()
        self.edit_vl_formula.setPlaceholderText("Link Formula (e.g. run = CommandList...)")
        self.edit_vl_formula.editingFinished.connect(lambda: self._emit_change('value_link_formula', self.edit_vl_formula.text()))
        self.stack_vl.addWidget(self.edit_vl_formula)
        
        layout_logic.addLayout(self.stack_vl)
        
        layout_logic.addWidget(RZLabel("FX Rules:"))
        self.list_fx = RZFXList()
        layout_logic.addWidget(self.list_fx)
        
        self.layout_props.addWidget(self.grp_logic)
        
        # === GROUP: BUTTON SPECIFICS ===
        self.grp_btn = RZGroupBox("Button Options")
        layout_btn = QtWidgets.QVBoxLayout(self.grp_btn)
        self.chk_no_nums = RZCheckBox("Disable Button Nums")
        self.chk_no_nums.toggled.connect(lambda v: self._emit_change('disable_button_nums', v))
        layout_btn.addWidget(self.chk_no_nums)
        self.chk_no_popup = RZCheckBox("Disable Button Popup")
        self.chk_no_popup.toggled.connect(lambda v: self._emit_change('disable_button_popup', v))
        layout_btn.addWidget(self.chk_no_popup)
        self.layout_props.addWidget(self.grp_btn)

        # === GROUP: EDITOR ===
        grp_edit = RZGroupBox("Editor Flags")
        layout_edit = QtWidgets.QVBoxLayout(grp_edit)
        self.chk_hide = RZCheckBox("Is Hidden")
        self.chk_hide.toggled.connect(lambda v: self._emit_change('qt_hide', v))
        layout_edit.addWidget(self.chk_hide)
        
        h_locks = QtWidgets.QHBoxLayout()
        self.chk_locked = RZCheckBox("Lock Transform")
        self.chk_locked.toggled.connect(lambda v: self._emit_change('qt_locked_ui', v))
        h_locks.addWidget(self.chk_locked)
        h_locks.addStretch()
        layout_edit.addLayout(h_locks)
        
        self.layout_props.addWidget(grp_edit)

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

            # Use mapping to determine if we need int casting
            from ..core.props import PROP_MAP
            mapping = PROP_MAP.get(key)
            if mapping and mapping[1] is not None: # It's a sub-index prop often needing int
                 val = int(float(val))
            elif key in ['grid_cell_size', 'priority', 'grid_min_cells', 'grid_max_cells']:
                 val = int(float(val))
            
            core.update_property_multi(ctx.selected_ids, key, val, sub)

    def _emit_math(self, key, op_str):
        ctx = RZContextManager.get_instance().get_snapshot()
        if not ctx.selected_ids: return
        core.perform_math_operation(list(ctx.selected_ids), key, op_str)

    def update_ui(self, props):
        self._block_signals = True
        
        if props and props.get('exists'):
            self.has_data = True
            self.scroll_content.setEnabled(True)
            self.tab_raw.setEnabled(True)
            
            # --- Identity ---
            self.lbl_id.setText(f"ID: {props.get('id')}" if not props.get('is_multi') else "Multiple Selection")
            self.name_edit.setText(props.get('name', ''))
            self.edit_tag.setText(props.get('tag', ''))
            self.spin_priority.setValue(props.get('priority', 0))
            self.chk_main_window.setChecked(props.get('is_main_window', False))

            class_type = props.get('class_type')
            if class_type: self.cb_class.setCurrentText(class_type)
            else: self.cb_class.setCurrentText("Mixed")

            # --- Presets ---
            self.chk_is_preset.setChecked(props.get('is_preset', False))
            self.chk_preset_hide.setChecked(props.get('qt_preset_hide', False))
            # Extract preset list from props. Note: read.py needs to populate this!
            # Using 'presets' key.
            self.list_presets.update_data(props.get('presets', [])) # Expecting list of IDs

            # --- Visibility ---
            vis_mode = props.get('visibility_mode', 'ALWAYS')
            self.cb_vis_mode.setCurrentText(vis_mode)
            is_cond = (vis_mode == 'CONDITIONAL')
            self.set_row_visible(self.edit_vis_cond, is_cond)
            self.edit_vis_cond.setText(props.get('visibility_condition', ''))

            # --- Anchor ---
            self.cb_anchor.setCurrentText(props.get('alignment') or "Mixed")
            
            has_text = class_type in ["TEXT", "BUTTON"] or class_type is None
            self.set_row_visible(self.cb_text_align, has_text)
            self.cb_text_align.setCurrentText(props.get('text_align') or "Mixed")

            # --- Transform (Formula Switching) ---
            pos_is_form = props.get('position_is_formula', False)
            self.chk_pos_formula.setChecked(pos_is_form)
            self.stack_pos.setCurrentIndex(1 if pos_is_form else 0)
            
            if pos_is_form:
                self.edit_pos_fx.setText(props.get('position_formula_x', ''))
                self.edit_pos_fy.setText(props.get('position_formula_y', ''))
            else:
                self.sl_x.set_value_from_backend(props.get('pos_x'))
                self.sl_y.set_value_from_backend(props.get('pos_y'))

            size_is_form = props.get('size_is_formula', False)
            self.chk_size_formula.setChecked(size_is_form)
            self.stack_size.setCurrentIndex(1 if size_is_form else 0)
            
            if size_is_form:
                self.edit_size_fx.setText(props.get('size_formula_x', ''))
                self.edit_size_fy.setText(props.get('size_formula_y', ''))
            else:
                self.sl_w.set_value_from_backend(props.get('width'))
                self.sl_h.set_value_from_backend(props.get('height'))
            
            # Locking Logic
            is_locked_pos = props.get('is_locked_pos', False)
            is_locked_size = props.get('is_locked_size', False)
            is_grid_child = props.get('is_grid_child', False)
            
            can_edit_pos = (is_locked_pos is not True) and (not is_grid_child)
            can_edit_size = (is_locked_size is not True)
            
            self.sl_x.setEnabled(can_edit_pos)
            self.sl_y.setEnabled(can_edit_pos)
            self.edit_pos_fx.setEnabled(can_edit_pos)
            self.edit_pos_fy.setEnabled(can_edit_pos)
            
            self.sl_w.setEnabled(can_edit_size)
            self.sl_h.setEnabled(can_edit_size)

            # --- Grid Container ---
            is_grid = (class_type == "GRID_CONTAINER")
            self.grp_grid.setVisible(is_grid)
            if is_grid:
                self.sl_cell.set_value_from_backend(props.get('grid_cell_size'))
                self.sl_min_c.set_value_from_backend(props.get('grid_min_cells_x'))
                self.sl_min_r.set_value_from_backend(props.get('grid_min_cells_y'))
                self.sl_max_c.set_value_from_backend(props.get('grid_max_cells_x'))
                self.sl_max_r.set_value_from_backend(props.get('grid_max_cells_y'))
                self.cb_grid_wrap.setCurrentText(props.get('grid_wrap_mode', 'SCROLL'))

            # --- Style ---
            col_is_form = props.get('color_is_formula', False)
            self.chk_color_formula.setChecked(col_is_form)
            self.stack_color.setCurrentIndex(1 if col_is_form else 0)
            
            if col_is_form:
                self.edit_col_r.setText(props.get('color_formula_r', ''))
                self.edit_col_g.setText(props.get('color_formula_g', ''))
                self.edit_col_b.setText(props.get('color_formula_b', ''))
                self.edit_col_a.setText(props.get('color_formula_a', ''))
            else:
                self.btn_color.set_color(props.get('color'))
            
            img_mode = props.get('image_mode', 'SINGLE')
            self.cb_img_mode.setCurrentText(img_mode)
            
            is_single = (img_mode == 'SINGLE')
            self.lbl_image.setVisible(is_single)
            self.cb_image.setVisible(is_single)
            self.list_images.setVisible(not is_single)
            
            all_images = core.read.get_available_images()
            
            if is_single:
                self.cb_image.update_items(all_images)
                self.cb_image.set_value(props.get('image_id', -1))
            else:
                self.list_images.update_data(props.get('conditional_images', []), all_images, img_mode)
            
            # --- Logic ---
            vl_is_form = props.get('value_link_is_formula', False)
            self.chk_vl_formula.setChecked(vl_is_form)
            self.stack_vl.setCurrentIndex(1 if vl_is_form else 0)
            
            if vl_is_form:
                self.edit_vl_formula.setText(props.get('value_link_formula', ''))
            else:
                self.list_links.update_data(props.get('value_links', []), class_type == 'SLIDER')
                
            self.list_fx.update_data(props.get('fx', []))

            self.tile_uv_x.setValue(props.get('tile_uv_x', 0))
            self.tile_uv_y.setValue(props.get('tile_uv_y', 0))
            self.edit_txt_id.setText(props.get('text_id', ''))
            self.edit_hov_txt.setText(props.get('hover_text_id', ''))

            # --- Button Specifics ---
            is_btn = (class_type == "BUTTON")
            self.grp_btn.setVisible(is_btn)
            if is_btn:
                self.chk_no_nums.setChecked(props.get('disable_button_nums', False))
                self.chk_no_popup.setChecked(props.get('disable_button_popup', False))

            # --- Flags ---
            self.chk_hide.setChecked(props.get('is_hidden') is True)
            self.chk_locked.setChecked(is_locked_pos is True or is_locked_size is True)
            
            # --- Raw Data Table ---
            self.table_raw.setRowCount(0)
            sorted_keys = sorted(props.keys())
            self.table_raw.setRowCount(len(sorted_keys))
            for r, key in enumerate(sorted_keys):
                val = str(props[key])
                self.table_raw.setItem(r, 0, QtWidgets.QTableWidgetItem(key))
                self.table_raw.setItem(r, 1, QtWidgets.QTableWidgetItem(val))

        else:
            self.has_data = False
            self.scroll_content.setEnabled(False)
            self.tab_raw.setEnabled(False)
            self.lbl_id.setText("No Selection")
            self.name_edit.clear()

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