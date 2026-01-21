# RZMenu/qt_editor/widgets/elem_config.py
from PySide6 import QtWidgets, QtCore, QtGui
from ..conf import get_config, save_config
from .lib.theme import get_current_theme
from .lib.widgets import RZGroupBox, RZLabel, RZColorButton, RZComboBox
from .lib.base import RZSmartSlider

class RZElementDefaultsPanel(QtWidgets.QWidget):
    """
    Панель для настройки дефолтных параметров создаваемых элементов.
    Позволяет менять размер, цвет, выравнивание по умолчанию.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.current_elem_type = None
        
        # Main Layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # --- Left Side: Type List ---
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.type_list = QtWidgets.QListWidget()
        self.type_list.setFixedWidth(150)
        self.type_list.itemClicked.connect(self._on_type_selected)
        left_layout.addWidget(RZLabel("Element Type:"))
        left_layout.addWidget(self.type_list)
        
        # --- Right Side: Property Editor ---
        self.prop_scroll = QtWidgets.QScrollArea()
        self.prop_scroll.setWidgetResizable(True)
        self.prop_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.prop_container = QtWidgets.QWidget()
        self.prop_layout = QtWidgets.QVBoxLayout(self.prop_container)
        self.prop_layout.setAlignment(QtCore.Qt.AlignTop)
        self.prop_scroll.setWidget(self.prop_container)
        
        # --- Buttons ---
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Save Defaults")
        self.btn_save.clicked.connect(self._save_changes)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.prop_scroll)
        right_layout.addLayout(btn_layout)
        
        layout.addWidget(left_container)
        layout.addLayout(right_layout)
        
        self._populate_types()
        self.apply_theme()

    def apply_theme(self):
        theme = get_current_theme()
        bg_input = theme.get('bg_input', '#222')
        text_main = theme.get('text_main', '#EEE')
        selection = theme.get('selection', '#444')
        
        self.type_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {bg_input};
                color: {text_main};
                border: 1px solid {theme.get('border_main', '#444')};
                border-radius: 4px;
            }}
            QListWidget::item {{ padding: 5px; }}
            QListWidget::item:selected {{ background-color: {selection}; }}
        """)

    def _populate_types(self):
        self.type_list.clear()
        defaults = self.config.get("element_defaults", {})
        for elem_type in sorted(defaults.keys()):
            item = QtWidgets.QListWidgetItem(elem_type)
            self.type_list.addItem(item)
        
        if self.type_list.count() > 0:
            self.type_list.setCurrentRow(0)
            self._on_type_selected(self.type_list.item(0))

    def _on_type_selected(self, item):
        if not item: return
        self.current_elem_type = item.text()
        self._build_editor(self.current_elem_type)

    def _build_editor(self, elem_type):
        # Clear previous widgets
        while self.prop_layout.count():
            item = self.prop_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        
        defaults = self.config.get("element_defaults", {}).get(elem_type, {})
        if not defaults:
            self.prop_layout.addWidget(RZLabel("No configurable properties."))
            return

        grp = RZGroupBox(f"{elem_type} Properties")
        form = QtWidgets.QFormLayout(grp)
        form.setLabelAlignment(QtCore.Qt.AlignLeft)
        
        # Sort keys to put generic ones first usually looks better
        sorted_keys = sorted(defaults.keys(), key=lambda k: (k != 'width', k != 'height', k))

        for key in sorted_keys:
            val = defaults[key]
            widget = None
            
            label_text = key.replace("_", " ").title() + ":"

            # --- COLOR ---
            if key == "color" and isinstance(val, list) and len(val) >= 3:
                widget = RZColorButton()
                widget.set_color(val)
                # Store closure to capture current key
                widget.colorChanged.connect(lambda c, k=key: self._update_config_value(k, c))
            
            # --- TEXT ALIGN ---
            elif key == "text_align":
                widget = RZComboBox()
                widget.addItems(["LEFT", "CENTER", "RIGHT"])
                widget.setCurrentText(val)
                widget.currentTextChanged.connect(lambda t, k=key: self._update_config_value(k, t))
            
            # --- NUMBERS (Width, Height, Padding, etc) ---
            elif isinstance(val, (int, float)):
                widget = QtWidgets.QSpinBox() if isinstance(val, int) else QtWidgets.QDoubleSpinBox()
                widget.setRange(0, 9999)
                widget.setValue(val)
                widget.setFixedWidth(100)
                widget.valueChanged.connect(lambda v, k=key: self._update_config_value(k, v))
                
            # --- STRINGS (Text ID, etc) ---
            elif isinstance(val, str):
                widget = QtWidgets.QLineEdit(val)
                widget.textChanged.connect(lambda t, k=key: self._update_config_value(k, t))

            if widget:
                form.addRow(RZLabel(label_text), widget)
        
        self.prop_layout.addWidget(grp)
        self.prop_layout.addStretch()

    def _update_config_value(self, key, value):
        if not self.current_elem_type: return
        
        # Color conversion handling (from QColor list/tuple back to format in json if needed)
        # RZColorButton emits list [r, g, b, a] which is compatible with our defaults.
        
        self.config["element_defaults"][self.current_elem_type][key] = value

    def _save_changes(self):
        save_config()
        self.btn_save.setText("Saved!")
        QtCore.QTimer.singleShot(1000, lambda: self.btn_save.setText("Save Defaults"))