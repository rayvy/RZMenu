# RZMenu/qt_editor/widgets/inspector.py
from PySide6 import QtWidgets, QtCore, QtGui
from .base import RZDraggableNumber, RZSmartSlider # RZDraggableNumber is alias to RZSmartSlider

class RZColorButton(QtWidgets.QPushButton):
    colorChanged = QtCore.Signal(list)

    def __init__(self, text="Click to set"):
        super().__init__(text)
        self._color = [1.0, 1.0, 1.0, 1.0]
        self.clicked.connect(self._pick_color)
        self.update_style()

    def set_color(self, rgba):
        self._color = rgba
        self.update_style()

    def update_style(self):
        r, g, b, _ = [int(c * 255) for c in self._color]
        contrast = "black" if (r+g+b) > 380 else "white"
        self.setStyleSheet(f"background-color: rgb({r},{g},{b}); color: {contrast}; border: 1px solid #555;")

    def _pick_color(self):
        # Mock color dialog
        import random
        new_c = [random.random(), random.random(), random.random(), 1.0]
        self.set_color(new_c)
        self.colorChanged.emit(new_c)

class RZMInspectorPanel(QtWidgets.QWidget):
    property_changed = QtCore.Signal(str, object, object) # key, val, sub_index

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
        self.table_raw.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        layout_raw.addWidget(self.table_raw)
        self.tabs.addTab(self.tab_raw, "Raw Data")
        
        self.has_data = False
        self._block_signals = False

    def _init_properties_ui(self):
        # Using QToolBox-like approach with Groups or actual QToolBox. 
        # Using specific Groups as requested.
        
        # === GROUP: IDENTITY ===
        grp_ident = QtWidgets.QGroupBox("Identity")
        form_ident = QtWidgets.QFormLayout(grp_ident)
        
        self.lbl_id = QtWidgets.QLabel("ID: None")
        form_ident.addRow("ID:", self.lbl_id)
        
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.editingFinished.connect(lambda: self.emit_change('name', self.name_edit.text()))
        form_ident.addRow("Name:", self.name_edit)
        
        self.cb_class = QtWidgets.QComboBox()
        self.cb_class.addItems(["CONTAINER", "BUTTON", "TEXT", "SLIDER", "ANCHOR"])
        self.cb_class.currentTextChanged.connect(lambda t: self.emit_change('class_type', t))
        form_ident.addRow("Class:", self.cb_class)
        
        self.layout_props.addWidget(grp_ident)
        
        # === GROUP: TRANSFORM ===
        grp_trans = QtWidgets.QGroupBox("Transform")
        layout_trans = QtWidgets.QVBoxLayout(grp_trans)
        
        # X / Y
        self.sl_x = RZSmartSlider(label_text="X", is_int=True)
        self.sl_x.value_changed.connect(lambda v: self.emit_change('pos_x', int(v)))
        layout_trans.addWidget(self.sl_x)
        
        self.sl_y = RZSmartSlider(label_text="Y", is_int=True)
        self.sl_y.value_changed.connect(lambda v: self.emit_change('pos_y', int(v)))
        layout_trans.addWidget(self.sl_y)
        
        # W / H
        self.sl_w = RZSmartSlider(label_text="W", is_int=True)
        self.sl_w.value_changed.connect(lambda v: self.emit_change('width', int(v)))
        layout_trans.addWidget(self.sl_w)
        
        self.sl_h = RZSmartSlider(label_text="H", is_int=True)
        self.sl_h.value_changed.connect(lambda v: self.emit_change('height', int(v)))
        layout_trans.addWidget(self.sl_h)
        
        self.chk_formula = QtWidgets.QCheckBox("Use Formula")
        # Placeholder logic
        layout_trans.addWidget(self.chk_formula)
        
        self.layout_props.addWidget(grp_trans)
        
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

    def emit_change(self, key, val, sub=None):
        if self.has_data and not self._block_signals:
            self.property_changed.emit(key, val, sub)

    def update_ui(self, props):
        self._block_signals = True
        
        if props and props.get('exists'):
            self.has_data = True
            self.tab_props.setEnabled(True)
            self.tab_raw.setEnabled(True)
            
            # Identity
            self.lbl_id.setText(f"ID: {props.get('id')}")
            self.name_edit.setText(props.get('name', ''))
            self.cb_class.setCurrentText(props.get('class_type', 'CONTAINER'))
            
            # Transform
            self.sl_x.set_value_from_backend(props.get('pos_x', 0))
            self.sl_y.set_value_from_backend(props.get('pos_y', 0))
            self.sl_w.set_value_from_backend(props.get('width', 100))
            self.sl_h.set_value_from_backend(props.get('height', 100))
            
            # Style
            color = props.get('color', [1,1,1,1])
            self.btn_color.set_color(color)
            
            # Flags
            self.chk_hide.setChecked(props.get('is_hidden', False))
            self.chk_lock.setChecked(props.get('is_locked', False))
            
            # Update Raw Data Table (Simple dump)
            self.table_raw.setRowCount(len(props))
            for r, (k, v) in enumerate(props.items()):
                self.table_raw.setItem(r, 0, QtWidgets.QTableWidgetItem(str(k)))
                self.table_raw.setItem(r, 1, QtWidgets.QTableWidgetItem(str(v)))

        else:
            self.has_data = False
            self.tab_props.setEnabled(False)
            self.tab_raw.setEnabled(False)
            self.lbl_id.setText("No Selection")
            self.name_edit.clear()

        self._block_signals = False