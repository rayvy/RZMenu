# RZMenu/qt_editor/widgets/inspector.py
from PySide6 import QtWidgets, QtCore, QtGui
from .base import RZDraggableNumber, RZSmartSlider
from .. import actions
from ..context import RZContextManager

# ... (RZColorButton оставляем без изменений) ...
class RZColorButton(QtWidgets.QPushButton):
    colorChanged = QtCore.Signal(list)
    def __init__(self, text="Click to set"):
        super().__init__(text)
        self._color = [1.0, 1.0, 1.0, 1.0]
        self.clicked.connect(self._pick_color)
        self.update_style()
    def set_color(self, rgba):
        if not rgba or len(rgba) < 3: rgba = [1.0, 1.0, 1.0, 1.0]
        if len(rgba) == 3: rgba = list(rgba) + [1.0]
        self._color = rgba
        self.update_style()
    def update_style(self):
        r, g, b, _ = [int(c * 255) for c in self._color]
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        contrast = "black" if luminance > 128 else "white"
        self.setStyleSheet(f"background-color: rgb({r},{g},{b}); color: {contrast}; border: 1px solid #555;")
    def _pick_color(self):
        current_qcolor = QtGui.QColor()
        current_qcolor.setRgbF(*self._color)
        dialog = QtWidgets.QColorDialog(current_qcolor, self)
        dialog.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, True)
        if dialog.exec():
            c = dialog.selectedColor()
            new_rgba = [c.redF(), c.greenF(), c.blueF(), c.alphaF()]
            self.set_color(new_rgba)
            self.colorChanged.emit(new_rgba)


class RZMInspectorPanel(QtWidgets.QWidget):
    property_changed = QtCore.Signal(str, object, object) 

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
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
        self.table_raw.setHorizontalHeaderLabels(["Key", "Value"])
        self.table_raw.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table_raw.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table_raw.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) 
        layout_raw.addWidget(self.table_raw)
        self.tabs.addTab(self.tab_raw, "Raw Data")
        
        self.has_data = False
        self._block_signals = False
        
        # Получаем доступ к ActionManager через родительское окно (dirty but works)
        # Лучше было бы передавать его, но пока через self.window()
        self.act_man = None

    def _get_action_manager(self):
        if not self.act_man:
            # Ищем родительское окно RZMEditorWindow
            curr = self.parent()
            while curr:
                if hasattr(curr, "action_manager"):
                    self.act_man = curr.action_manager
                    break
                curr = curr.parent()
        return self.act_man

    def _init_properties_ui(self):
        # === GROUP: IDENTITY ===
        grp_ident = QtWidgets.QGroupBox("Identity")
        form_ident = QtWidgets.QFormLayout(grp_ident)
        
        self.lbl_id = QtWidgets.QLabel("ID: None")
        form_ident.addRow("ID:", self.lbl_id)
        
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.editingFinished.connect(lambda: self.emit_change('element_name', self.name_edit.text()))
        form_ident.addRow("Name:", self.name_edit)
        
        self.cb_class = QtWidgets.QComboBox()
        self.cb_class.addItems(["CONTAINER", "GRID_CONTAINER", "BUTTON", "TEXT", "SLIDER", "ANCHOR"])
        self.cb_class.setEnabled(True) 
        self.cb_class.currentTextChanged.connect(lambda t: self.emit_change('class_type', t))
        form_ident.addRow("Class:", self.cb_class)
        self.layout_props.addWidget(grp_ident)
        
        # === GROUP: ALIGNMENT (NEW) ===
        self.grp_align = QtWidgets.QGroupBox("Alignment")
        layout_align = QtWidgets.QHBoxLayout(self.grp_align)
        layout_align.setSpacing(2)
        
        # Unicode icons: ⇠ (Left), ⇢ (Right), ⇡ (Top), ⇣ (Bottom), ⌖ (Center)
        # But standard chars like |←, →|, etc usually clearer
        btns = [
            ("⇤", "LEFT", "Align Left"),
            ("⇥", "RIGHT", "Align Right"),
            ("⤒", "TOP", "Align Top"),
            ("⤓", "BOTTOM", "Align Bottom"),
            ("⌖X", "CENTER_X", "Align Center X"),
            ("⌖Y", "CENTER_Y", "Align Center Y")
        ]
        
        for txt, mode, tooltip in btns:
            b = QtWidgets.QPushButton(txt)
            b.setFixedWidth(30)
            b.setToolTip(tooltip)
            # Замыкание
            b.clicked.connect(lambda checked=False, m=mode: self._on_align_click(m))
            layout_align.addWidget(b)
            
        self.layout_props.addWidget(self.grp_align)

        # === GROUP: TRANSFORM ===
        self.grp_trans = QtWidgets.QGroupBox("Transform")
        layout_trans = QtWidgets.QVBoxLayout(self.grp_trans)
        
        self.sl_x = RZSmartSlider(label_text="X", is_int=True)
        self.sl_x.value_changed.connect(lambda v: self.emit_change('pos_x', int(v)))
        layout_trans.addWidget(self.sl_x)
        self.sl_y = RZSmartSlider(label_text="Y", is_int=True)
        self.sl_y.value_changed.connect(lambda v: self.emit_change('pos_y', int(v)))
        layout_trans.addWidget(self.sl_y)
        self.sl_w = RZSmartSlider(label_text="W", is_int=True)
        self.sl_w.value_changed.connect(lambda v: self.emit_change('width', int(v)))
        layout_trans.addWidget(self.sl_w)
        self.sl_h = RZSmartSlider(label_text="H", is_int=True)
        self.sl_h.value_changed.connect(lambda v: self.emit_change('height', int(v)))
        layout_trans.addWidget(self.sl_h)
        self.layout_props.addWidget(self.grp_trans)

        # === GROUP: GRID (EXTENDED) ===
        self.grp_grid = QtWidgets.QGroupBox("Grid Settings")
        layout_grid = QtWidgets.QVBoxLayout(self.grp_grid)
        
        # Cell Size
        h_cell = QtWidgets.QHBoxLayout()
        h_cell.addWidget(QtWidgets.QLabel("Cell Size:"))
        self.sl_cell = RZSmartSlider(label_text="", is_int=True)
        self.sl_cell.value_changed.connect(lambda v: self.emit_change('grid_cell_size', int(v)))
        h_cell.addWidget(self.sl_cell)
        layout_grid.addLayout(h_cell)
        
        # Rows / Cols
        h_rc = QtWidgets.QHBoxLayout()
        self.sl_rows = RZSmartSlider(label_text="R", is_int=True)
        self.sl_rows.value_changed.connect(lambda v: self.emit_change('grid_rows', int(v)))
        self.sl_cols = RZSmartSlider(label_text="C", is_int=True)
        self.sl_cols.value_changed.connect(lambda v: self.emit_change('grid_cols', int(v)))
        h_rc.addWidget(self.sl_rows)
        h_rc.addWidget(self.sl_cols)
        layout_grid.addLayout(h_rc)

        # Padding / Gap
        h_pg = QtWidgets.QHBoxLayout()
        self.sl_pad = RZSmartSlider(label_text="P", is_int=True)
        self.sl_pad.value_changed.connect(lambda v: self.emit_change('grid_padding', int(v)))
        self.sl_gap = RZSmartSlider(label_text="G", is_int=True)
        self.sl_gap.value_changed.connect(lambda v: self.emit_change('grid_gap', int(v)))
        h_pg.addWidget(self.sl_pad)
        h_pg.addWidget(self.sl_gap)
        layout_grid.addLayout(h_pg)

        self.layout_props.addWidget(self.grp_grid)
        
        # === GROUP: STYLE ===
        grp_style = QtWidgets.QGroupBox("Style")
        layout_style = QtWidgets.QVBoxLayout(grp_style)
        self.btn_color = RZColorButton()
        self.btn_color.colorChanged.connect(lambda c: self.emit_change('color', c))
        layout_style.addWidget(QtWidgets.QLabel("Color:"))
        layout_style.addWidget(self.btn_color)
        self.layout_props.addWidget(grp_style)
        
        # === GROUP: EDITOR ===
        grp_edit = QtWidgets.QGroupBox("Editor Flags")
        layout_edit = QtWidgets.QVBoxLayout(grp_edit)
        self.chk_hide = QtWidgets.QCheckBox("Is Hidden")
        self.chk_hide.toggled.connect(lambda v: self.emit_change('is_hidden', v))
        layout_edit.addWidget(self.chk_hide)
        self.chk_lock = QtWidgets.QCheckBox("Lock Transform")
        self.chk_lock.toggled.connect(lambda v: self.emit_change('is_locked', v))
        layout_edit.addWidget(self.chk_lock)
        self.layout_props.addWidget(grp_edit)

    def _on_align_click(self, mode):
        man = self._get_action_manager()
        if man:
            man.run("rzm.align", mode=mode)

    def emit_change(self, key, val, sub=None):
        if self.has_data and not self._block_signals:
            self.property_changed.emit(key, val, sub)

    def update_ui(self, props):
        self._block_signals = True
        
        if props and props.get('exists'):
            self.has_data = True
            self.tab_props.setEnabled(True)
            self.tab_raw.setEnabled(True)
            
            is_locked = props.get('is_locked', False)
            self.grp_trans.setEnabled(not is_locked)
            
            # --- Identity ---
            self.lbl_id.setText(f"ID: {props.get('id')}")
            self.name_edit.setText(props.get('name', ''))
            class_type = props.get('class_type', 'CONTAINER')
            self.cb_class.setCurrentText(class_type)
            
            # --- Alignment ---
            # Доступно только если выделено > 1 элемента
            self.grp_align.setVisible(props.get('is_multi', False))

            # --- Dynamic Visibility for Grid ---
            is_grid = (class_type == "GRID_CONTAINER")
            self.grp_grid.setVisible(is_grid)
            if is_grid:
                self.sl_cell.set_value_from_backend(props.get('grid_cell_size', 20))
                self.sl_rows.set_value_from_backend(props.get('grid_rows', 2))
                self.sl_cols.set_value_from_backend(props.get('grid_cols', 2))
                self.sl_pad.set_value_from_backend(props.get('grid_padding', 5))
                self.sl_gap.set_value_from_backend(props.get('grid_gap', 5))

            # --- Transform ---
            self.sl_x.set_value_from_backend(props.get('pos_x', 0))
            self.sl_y.set_value_from_backend(props.get('pos_y', 0))
            self.sl_w.set_value_from_backend(props.get('width', 100))
            self.sl_h.set_value_from_backend(props.get('height', 100))
            
            # --- Style ---
            color = props.get('color', [1.0, 1.0, 1.0, 1.0])
            self.btn_color.set_color(color)
            
            # --- Flags ---
            self.chk_hide.setChecked(props.get('is_hidden', False))
            self.chk_lock.setChecked(is_locked)
            
            # --- Raw Data Tab ---
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

    def enterEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(),
            (0.0, 0.0),
            area="INSPECTOR"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(),
            (0.0, 0.0),
            area="NONE"
        )
        super().leaveEvent(event)