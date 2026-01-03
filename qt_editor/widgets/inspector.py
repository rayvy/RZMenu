# RZMenu/qt_editor/widgets/inspector.py
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.base import RZDraggableNumber, RZSmartSlider
from .lib.theme import get_current_theme
from .lib.widgets import RZPanelWidget, RZGroupBox, RZPushButton, RZLabel, RZLineEdit, RZComboBox, RZColorButton
from .. import actions
from ..context import RZContextManager

class RZMInspectorPanel(RZPanelWidget):
    property_changed = QtCore.Signal(str, object, object) 

    def __init__(self):
        super().__init__()
        self.setObjectName("RZMInspectorPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        
        # --- TAB 1: Properties ---
        self.tab_props = QtWidgets.QWidget()
        self.layout_props = QtWidgets.QVBoxLayout(self.tab_props)
        self.tabs.addTab(self.tab_props, "Properties")
        
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
        self.act_man = None

    def _get_action_manager(self):
        if not self.act_man:
            curr = self.parent()
            while curr:
                if hasattr(curr, "action_manager"):
                    self.act_man = curr.action_manager
                    break
                curr = curr.parent()
        return self.act_man

    def _init_properties_ui(self):
        # === GROUP: IDENTITY ===
        grp_ident = RZGroupBox("Identity")
        form_ident = QtWidgets.QFormLayout(grp_ident)
        
        self.lbl_id = RZLabel("ID: None")
        form_ident.addRow("ID:", self.lbl_id)

        self.name_edit = RZLineEdit()
        self.name_edit.editingFinished.connect(lambda: self.emit_change('element_name', self.name_edit.text()))
        form_ident.addRow("Name:", self.name_edit)
        
        self.cb_class = RZComboBox()
        self.cb_class.addItems(["CONTAINER", "GRID_CONTAINER", "BUTTON", "TEXT", "SLIDER", "ANCHOR"])
        self.cb_class.currentTextChanged.connect(lambda t: self.emit_change('class_type', t))
        form_ident.addRow("Class:", self.cb_class)
        self.layout_props.addWidget(grp_ident)
        
        # === GROUP: ANCHOR & ALIGNMENT ===
        self.grp_anchor = RZGroupBox("Anchor & Alignment")
        layout_anchor = QtWidgets.QFormLayout(self.grp_anchor)
        
        self.cb_anchor = RZComboBox()
        self.cb_anchor.addItems([
            "BOTTOM_LEFT", "BOTTOM_CENTER", "BOTTOM_RIGHT", 
            "CENTER_LEFT", "CENTER", "CENTER_RIGHT", 
            "TOP_LEFT", "TOP_CENTER", "TOP_RIGHT"
        ])
        self.cb_anchor.currentTextChanged.connect(lambda t: self.emit_change('alignment', t))
        layout_anchor.addRow("Anchor:", self.cb_anchor)
        
        self.cb_text_align = RZComboBox()
        self.cb_text_align.addItems(["LEFT", "CENTER", "RIGHT"])
        self.cb_text_align.currentTextChanged.connect(lambda t: self.emit_change('text_align', t))
        self.row_text_align = layout_anchor.addRow("Text Align:", self.cb_text_align)
        
        self.layout_props.addWidget(self.grp_anchor)

        # === GROUP: TRANSFORM ===
        self.grp_trans = RZGroupBox("Transform")
        layout_trans = QtWidgets.QVBoxLayout(self.grp_trans)
        self.sl_x = RZSmartSlider(label_text="X", is_int=True)
        self.sl_x.value_changed.connect(lambda v: self.emit_change('pos_x', int(v)))
        self.sl_x.math_requested.connect(lambda op: self.emit_math('pos_x', op))
        layout_trans.addWidget(self.sl_x)
        
        self.sl_y = RZSmartSlider(label_text="Y", is_int=True)
        self.sl_y.value_changed.connect(lambda v: self.emit_change('pos_y', int(v)))
        self.sl_y.math_requested.connect(lambda op: self.emit_math('pos_y', op))
        layout_trans.addWidget(self.sl_y)
        
        self.sl_w = RZSmartSlider(label_text="W", is_int=True)
        self.sl_w.value_changed.connect(lambda v: self.emit_change('width', int(v)))
        self.sl_w.math_requested.connect(lambda op: self.emit_math('width', op))
        layout_trans.addWidget(self.sl_w)
        
        self.sl_h = RZSmartSlider(label_text="H", is_int=True)
        self.sl_h.value_changed.connect(lambda v: self.emit_change('height', int(v)))
        self.sl_h.math_requested.connect(lambda op: self.emit_math('height', op))
        layout_trans.addWidget(self.sl_h)
        self.layout_props.addWidget(self.grp_trans)

        # === GROUP: GRID ===
        self.grp_grid = RZGroupBox("Grid Settings")
        layout_grid = QtWidgets.QVBoxLayout(self.grp_grid)
        h_cell = QtWidgets.QHBoxLayout()
        h_cell.addWidget(RZLabel("Cell Size:"))
        self.sl_cell = RZSmartSlider(label_text="", is_int=True)
        self.sl_cell.value_changed.connect(lambda v: self.emit_change('grid_cell_size', int(v)))
        self.sl_cell.math_requested.connect(lambda op: self.emit_math('grid_cell_size', op))
        h_cell.addWidget(self.sl_cell)
        layout_grid.addLayout(h_cell)
        
        h_rc = QtWidgets.QHBoxLayout()
        self.sl_rows = RZSmartSlider(label_text="R", is_int=True)
        self.sl_rows.value_changed.connect(lambda v: self.emit_change('grid_rows', int(v)))
        self.sl_rows.math_requested.connect(lambda op: self.emit_math('grid_rows', op))
        self.sl_cols = RZSmartSlider(label_text="C", is_int=True)
        self.sl_cols.value_changed.connect(lambda v: self.emit_change('grid_cols', int(v)))
        self.sl_cols.math_requested.connect(lambda op: self.emit_math('grid_cols', op))
        h_rc.addWidget(self.sl_rows)
        h_rc.addWidget(self.sl_cols)
        layout_grid.addLayout(h_rc)
        
        h_pg = QtWidgets.QHBoxLayout()
        self.sl_pad = RZSmartSlider(label_text="P", is_int=True)
        self.sl_pad.value_changed.connect(lambda v: self.emit_change('grid_padding', int(v)))
        self.sl_pad.math_requested.connect(lambda op: self.emit_math('grid_padding', op))
        self.sl_gap = RZSmartSlider(label_text="G", is_int=True)
        self.sl_gap.value_changed.connect(lambda v: self.emit_change('grid_gap', int(v)))
        self.sl_gap.math_requested.connect(lambda op: self.emit_math('grid_gap', op))
        h_pg.addWidget(self.sl_pad)
        h_pg.addWidget(self.sl_gap)
        layout_grid.addLayout(h_pg)
        self.layout_props.addWidget(self.grp_grid)

        
        # === GROUP: STYLE ===
        grp_style = RZGroupBox("Style")
        layout_style = QtWidgets.QVBoxLayout(grp_style)
        self.btn_color = RZColorButton()
        self.btn_color.colorChanged.connect(lambda c: self.emit_change('color', c))
        layout_style.addWidget(RZLabel("Color:"))
        layout_style.addWidget(self.btn_color)
        self.layout_props.addWidget(grp_style)
        
        # === GROUP: EDITOR ===
        grp_edit = RZGroupBox("Editor Flags")
        layout_edit = QtWidgets.QVBoxLayout(grp_edit)
        self.chk_hide = QtWidgets.QCheckBox("Is Hidden")
        self.chk_hide.toggled.connect(lambda v: self.emit_change('is_hidden', v))
        layout_edit.addWidget(self.chk_hide)
        
        h_locks = QtWidgets.QHBoxLayout()
        self.chk_lock_pos = QtWidgets.QCheckBox("Lock Pos")
        self.chk_lock_pos.toggled.connect(lambda v: self.emit_change('is_locked_pos', v))
        self.chk_lock_size = QtWidgets.QCheckBox("Lock Size")
        self.chk_lock_size.toggled.connect(lambda v: self.emit_change('is_locked_size', v))
        h_locks.addWidget(self.chk_lock_pos)
        h_locks.addWidget(self.chk_lock_size)
        layout_edit.addLayout(h_locks)
        
        self.layout_props.addWidget(grp_edit)

    def emit_change(self, key, val, sub=None):
        if self.has_data and not self._block_signals:
            # Filter out UI placeholders
            if val == "Mixed": return
            self.property_changed.emit(key, val, sub)

    def emit_math(self, key, op_str):
        """Triggers a relative math operation via core."""
        ctx = RZContextManager.get_instance().get_snapshot()
        if not ctx.selected_ids: return
        import core
        core.perform_math_operation(list(ctx.selected_ids), key, op_str)

    def update_ui(self, props):
        self._block_signals = True
        
        if props and props.get('exists'):
            self.has_data = True
            self.tab_props.setEnabled(True)
            self.tab_raw.setEnabled(True)
            
            is_locked_pos = props.get('is_locked_pos', False)
            is_locked_size = props.get('is_locked_size', False)
            
            self.sl_x.setEnabled(is_locked_pos is not True)
            self.sl_y.setEnabled(is_locked_pos is not True)
            self.sl_w.setEnabled(is_locked_size is not True)
            self.sl_h.setEnabled(is_locked_size is not True)
            
            self.lbl_id.setText(f"ID: {props.get('id')}" if not props.get('is_multi') else "Multiple Selection")
            self.name_edit.setText(props.get('name', ''))
            
            class_type = props.get('class_type') # Might be None if mixed
            if class_type:
                self.cb_class.setCurrentText(class_type)
            else:
                if self.cb_class.findText("Mixed") == -1: self.cb_class.addItem("Mixed")
                self.cb_class.setCurrentText("Mixed")
            
            # Update Anchor/Alignment
            alignment = props.get('alignment')
            if alignment:
                self.cb_anchor.setCurrentText(alignment)
            else:
                if self.cb_anchor.findText("Mixed") == -1: self.cb_anchor.addItem("Mixed")
                self.cb_anchor.setCurrentText("Mixed")
            
            # Show text align only for text-capable elements
            has_text = class_type in ["TEXT", "BUTTON"] or class_type is None
            self.cb_text_align.setVisible(has_text)
            label = self.grp_anchor.layout().labelForField(self.cb_text_align)
            if label: label.setVisible(has_text)
            
            if has_text:
                t_align = props.get('text_align')
                if t_align:
                    self.cb_text_align.setCurrentText(t_align)
                else:
                    if self.cb_text_align.findText("Mixed") == -1: self.cb_text_align.addItem("Mixed")
                    self.cb_text_align.setCurrentText("Mixed")

            is_grid = (class_type == "GRID_CONTAINER")
            self.grp_grid.setVisible(is_grid)
            if is_grid:
                self.sl_cell.set_value_from_backend(props.get('grid_cell_size'))
                self.sl_rows.set_value_from_backend(props.get('grid_rows'))
                self.sl_cols.set_value_from_backend(props.get('grid_cols'))
                self.sl_pad.set_value_from_backend(props.get('grid_padding'))
                self.sl_gap.set_value_from_backend(props.get('grid_gap'))

            self.sl_x.set_value_from_backend(props.get('pos_x'))
            self.sl_y.set_value_from_backend(props.get('pos_y'))
            self.sl_w.set_value_from_backend(props.get('width'))
            self.sl_h.set_value_from_backend(props.get('height'))
            
            # Color is complex, for now we just show active or default
            self.btn_color.set_color(props.get('color', [1.0, 1.0, 1.0, 1.0]))
            
            # Checkboxes
            self.chk_hide.setChecked(props.get('is_hidden') is True)
            self.chk_lock_pos.setChecked(is_locked_pos is True)
            self.chk_lock_size.setChecked(is_locked_size is True)
            
            self.table_raw.setRowCount(0)
            sorted_keys = sorted(props.keys())
            self.table_raw.setRowCount(len(sorted_keys))
            for r, key in enumerate(sorted_keys):
                val = str(props[key])
                self.table_raw.setItem(r, 0, QtWidgets.QTableWidgetItem(key))
                self.table_raw.setItem(r, 1, QtWidgets.QTableWidgetItem(val))

        else:
            self.has_data = False
            self.tab_props.setEnabled(False)
            self.tab_raw.setEnabled(False)
            self.lbl_id.setText("No Selection")
            self.name_edit.clear()
            self.table_raw.setRowCount(0)

        self._block_signals = False

    def update_theme_styles(self):
        """Force manual theme update for widgets that cache colors."""
        from .lib.base import RZSmartSlider

        # 1. Generic update: Find ALL children that have an 'apply_theme' method
        # This covers RZGroupBox, RZLabel, RZComboBox, RZPushButton, RZLineEdit, etc.
        for widget in self.findChildren(QtWidgets.QWidget):
            if hasattr(widget, 'apply_theme') and callable(widget.apply_theme):
                widget.apply_theme()

        # 2. Update Sliders specifically (they are complex widgets)
        for sl in self.findChildren(RZSmartSlider):
            sl.apply_theme()

        # 3. Update Color Button
        if hasattr(self, 'btn_color'):
            self.btn_color.update_style()

    def enterEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(), (0.0, 0.0), area="INSPECTOR"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(), (0.0, 0.0), area="NONE"
        )
        super().leaveEvent(event)