# RZMenu/qt_editor/widgets/variables_manager.py
import bpy
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.theme import get_current_theme
from .lib.widgets import RZPanelWidget
from ..core.signals import SIGNALS

class RZVariablesManager(QtWidgets.QWidget):
    """
    Widget to manage Global Values, Toggles, and Shapes.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Tabs for different types
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)
        
        self.tab_values = ValuesTab()
        self.tab_toggles = TogglesTab()
        self.tab_shapes = ShapesTab()
        
        self.tabs.addTab(self.tab_values, "Values ($)")
        self.tabs.addTab(self.tab_toggles, "Toggles (@)")
        self.tabs.addTab(self.tab_shapes, "Shapes (#)")
        
        # Style tabs
        self.apply_theme()
        
    def apply_theme(self):
        t = get_current_theme()
        self.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {t['border_main']};
                background-color: {t['bg_panel']};
            }}
            QTabBar::tab {{
                background-color: {t['bg_header']};
                color: {t['text_main']};
                padding: 6px 12px;
                border: 1px solid {t['border_main']};
                border-bottom: none;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {t['bg_panel']};
                border-bottom: 1px solid {t['bg_panel']}; /* Blend with pane */
            }}
        """)
        self.tab_values.apply_theme()
        self.tab_toggles.apply_theme()
        self.tab_shapes.apply_theme()

    def on_activate(self):
        self.tab_values.refresh()
        self.tab_toggles.refresh()
        self.tab_shapes.refresh()


class BaseListTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # List
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_selection_changed)
        self.layout.addWidget(self.list_widget)
        
        # Controls (Add/Remove)
        self.btn_layout = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add")
        self.btn_remove = QtWidgets.QPushButton("Remove")
        
        self.btn_add.clicked.connect(self.add_item)
        self.btn_remove.clicked.connect(self.remove_item)
        
        self.btn_layout.addWidget(self.btn_add)
        self.btn_layout.addWidget(self.btn_remove)
        self.layout.addLayout(self.btn_layout)
        
        # Properties Area
        self.props_group = QtWidgets.QGroupBox("Properties")
        self.props_layout = QtWidgets.QFormLayout(self.props_group)
        self.layout.addWidget(self.props_group)
        
        self.is_updating_ui = False

    def apply_theme(self):
        t = get_current_theme()
        self.list_widget.setStyleSheet(f"""
            background-color: {t['bg_input']};
            color: {t['text_main']};
            border: 1px solid {t['border_input']};
        """)
        for w in [self.btn_add, self.btn_remove]:
             w.setStyleSheet(f"background-color: {t['bg_header']}; color: {t['text_main']}; border: 1px solid {t['border_main']}; padding: 4px;")

    def refresh(self):
        pass # Implement in subclass
        
    def on_selection_changed(self, current, previous):
        self.update_properties()
    
    def update_properties(self):
        pass
    
    def add_item(self):
        pass
        
    def remove_item(self):
        pass

class ValuesTab(BaseListTab):
    def __init__(self):
        super().__init__()
        
        # Props
        self.inp_name = QtWidgets.QLineEdit()
        self.inp_name.editingFinished.connect(self.synch_name)
        
        self.inp_type = QtWidgets.QComboBox()
        self.inp_type.addItems(["INT", "FLOAT"])
        self.inp_type.currentTextChanged.connect(self.synch_type)
        
        self.inp_val_int = QtWidgets.QSpinBox()
        self.inp_val_int.setRange(-999999, 999999)
        self.inp_val_int.valueChanged.connect(self.synch_val_int)
        
        self.inp_val_float = QtWidgets.QDoubleSpinBox()
        self.inp_val_float.setRange(-999999.0, 999999.0)
        self.inp_val_float.valueChanged.connect(self.synch_val_float)
        
        self.props_layout.addRow("Name:", self.inp_name)
        self.props_layout.addRow("Type:", self.inp_type)
        self.props_layout.addRow("Int Value:", self.inp_val_int)
        self.props_layout.addRow("Float Value:", self.inp_val_float)

    def refresh(self):
        self.list_widget.clear()
        if not bpy.context: return
        for i, val in enumerate(bpy.context.scene.rzm.rzm_values):
            self.list_widget.addItem(val.value_name)
            
        # Restore selection? Simplification: Select last or none
        
    def add_item(self):
        bpy.ops.rzm.add_value()
        self.refresh()
        self.list_widget.setCurrentRow(self.list_widget.count()-1)

    def remove_item(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            bpy.context.scene.rzm_active_value_index = row # Ensure correct active index for operator
            bpy.ops.rzm.remove_value()
            self.refresh()

    def update_properties(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(bpy.context.scene.rzm.rzm_values):
            self.props_group.setEnabled(False)
            return
            
        self.props_group.setEnabled(True)
        val = bpy.context.scene.rzm.rzm_values[row]
        
        self.is_updating_ui = True
        self.inp_name.setText(val.value_name)
        self.inp_type.setCurrentText(val.value_type)
        self.inp_val_int.setValue(val.int_value)
        self.inp_val_float.setValue(val.float_value)
        
        # Visibility
        self.inp_val_int.setVisible(val.value_type == 'INT')
        self.inp_val_float.setVisible(val.value_type == 'FLOAT')
        # Hiding row label is harder in FormLayout, so just hide widget
        
        self.is_updating_ui = False

    def synch_name(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        val = bpy.context.scene.rzm.rzm_values[row]
        val.value_name = self.inp_name.text()
        self.list_widget.item(row).setText(val.value_name)

    def synch_type(self, txt):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        val = bpy.context.scene.rzm.rzm_values[row]
        val.value_type = txt
        self.update_properties() # To toggle visibility

    def synch_val_int(self, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.context.scene.rzm.rzm_values[row].int_value = v

    def synch_val_float(self, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.context.scene.rzm.rzm_values[row].float_value = v

class TogglesTab(BaseListTab):
    def __init__(self):
        super().__init__()
        
        self.inp_name = QtWidgets.QLineEdit()
        self.inp_name.editingFinished.connect(self.synch_name)
        
        self.inp_len = QtWidgets.QSpinBox()
        self.inp_len.setRange(1, 32)
        self.inp_len.valueChanged.connect(self.synch_len)
        
        self.props_layout.addRow("Name:", self.inp_name)
        self.props_layout.addRow("Length:", self.inp_len)

    def refresh(self):
        self.list_widget.clear()
        if not bpy.context: return
        for t in bpy.context.scene.rzm.toggle_definitions:
            self.list_widget.addItem(t.toggle_name)

    def add_item(self):
        bpy.ops.rzm.add_project_toggle()
        self.refresh()
        self.list_widget.setCurrentRow(self.list_widget.count()-1)

    def remove_item(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            bpy.context.scene.rzm_active_toggle_def_index = row
            bpy.ops.rzm.remove_project_toggle()
            self.refresh()

    def update_properties(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(bpy.context.scene.rzm.toggle_definitions):
            self.props_group.setEnabled(False)
            return

        self.props_group.setEnabled(True)
        t = bpy.context.scene.rzm.toggle_definitions[row]
        
        self.is_updating_ui = True
        self.inp_name.setText(t.toggle_name)
        self.inp_len.setValue(t.toggle_length)
        self.is_updating_ui = False

    def synch_name(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        t = bpy.context.scene.rzm.toggle_definitions[row]
        t.toggle_name = self.inp_name.text()
        self.list_widget.item(row).setText(t.toggle_name)

    def synch_len(self, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.context.scene.rzm.toggle_definitions[row].toggle_length = v

class ShapesTab(BaseListTab):
    def __init__(self):
        super().__init__()
        
        # Shape Props
        self.inp_name = QtWidgets.QLineEdit()
        self.inp_name.editingFinished.connect(self.synch_name)
        
        self.inp_type = QtWidgets.QComboBox()
        self.inp_type.addItems(["Linear", "Anim"])
        self.inp_type.currentTextChanged.connect(self.synch_type)
        
        self.inp_cond = QtWidgets.QLineEdit()
        self.inp_cond.editingFinished.connect(self.synch_cond)
        
        self.props_layout.addRow("Name:", self.inp_name)
        self.props_layout.addRow("Type:", self.inp_type)
        self.props_layout.addRow("Anim Condition:", self.inp_cond)
        
        # Nested ShapeKeys List
        self.keys_group = QtWidgets.QGroupBox("Shape Keys")
        self.keys_layout = QtWidgets.QVBoxLayout(self.keys_group)
        self.props_layout.addRow(self.keys_group)
        
        self.list_keys = QtWidgets.QListWidget()
        self.list_keys.setFixedHeight(100)
        self.list_keys.currentItemChanged.connect(self.on_key_selected)
        self.keys_layout.addWidget(self.list_keys)
        
        self.btn_key_layout = QtWidgets.QHBoxLayout()
        self.btn_add_key = QtWidgets.QPushButton("+ Key")
        self.btn_rem_key = QtWidgets.QPushButton("- Key")
        self.btn_add_key.clicked.connect(self.add_key)
        self.btn_rem_key.clicked.connect(self.remove_key)
        self.btn_key_layout.addWidget(self.btn_add_key)
        self.btn_key_layout.addWidget(self.btn_rem_key)
        self.keys_layout.addLayout(self.btn_key_layout)
        
        # Key Props
        self.key_props_layout = QtWidgets.QFormLayout()
        self.keys_layout.addLayout(self.key_props_layout)
        
        self.inp_k_frame = QtWidgets.QSpinBox()
        self.inp_k_frame.setRange(0, 9999)
        self.inp_k_frame.valueChanged.connect(self.synch_k_frame)
        self.key_props_layout.addRow("Keyframe:", self.inp_k_frame)
        
        self.inp_k_mode = QtWidgets.QComboBox()
        self.inp_k_mode.addItems(["SIMPLE", "ADVANCED"])
        self.inp_k_mode.currentTextChanged.connect(self.synch_k_mode)
        self.key_props_layout.addRow("Mode:", self.inp_k_mode)
        
        self.inp_k_mul = QtWidgets.QDoubleSpinBox()
        self.inp_k_mul.setValue(1.0)
        self.inp_k_mul.valueChanged.connect(self.synch_k_mul)
        self.key_props_layout.addRow("Multiplier:", self.inp_k_mul)
        
        self.is_updating_key_ui = False

    def refresh(self):
        self.list_widget.clear()
        if not bpy.context: return
        for s in bpy.context.scene.rzm.shapes:
            self.list_widget.addItem(s.shape_name)

    def add_item(self):
        bpy.ops.rzm.add_shape()
        self.refresh()
        self.list_widget.setCurrentRow(self.list_widget.count()-1)

    def remove_item(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            # Need to manually handle remove logic since operator relies on UI context or we write logic here
            # Operator RZM_OT_RemoveShape uses scene.rzm.shapes.remove(len-1) - that's buggy if we want to remove specific index.
            # Assuming we can just call remove directly for generic list.
            bpy.context.scene.rzm.shapes.remove(row)
            self.refresh()

    def update_properties(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(bpy.context.scene.rzm.shapes):
            self.props_group.setEnabled(False)
            return
            
        self.props_group.setEnabled(True)
        shape = bpy.context.scene.rzm.shapes[row]
        
        self.is_updating_ui = True
        self.inp_name.setText(shape.shape_name)
        self.inp_type.setCurrentText(shape.shape_type)
        self.inp_cond.setText(shape.anim_condition)
        self.is_updating_ui = False
        
        self.refresh_keys_list(shape)

    def synch_name(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        s = bpy.context.scene.rzm.shapes[row]
        s.shape_name = self.inp_name.text()
        self.list_widget.item(row).setText(s.shape_name)

    def synch_type(self, t):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.context.scene.rzm.shapes[row].shape_type = t

    def synch_cond(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.context.scene.rzm.shapes[row].anim_condition = self.inp_cond.text()

    # --- Shape Keys Logic
    def refresh_keys_list(self, shape):
        self.list_keys.clear()
        for k in shape.shape_keys:
            self.list_keys.addItem(f"Key {k.key_name}")

    def add_key(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        shape = bpy.context.scene.rzm.shapes[row]
        shape.shape_keys.add()
        self.refresh_keys_list(shape)
        self.list_keys.setCurrentRow(len(shape.shape_keys)-1)

    def remove_key(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        shape = bpy.context.scene.rzm.shapes[row]
        k_idx = self.list_keys.currentRow()
        if k_idx >= 0:
            shape.shape_keys.remove(k_idx)
            self.refresh_keys_list(shape)

    def on_key_selected(self):
        row = self.list_widget.currentRow()
        k_idx = self.list_keys.currentRow()
        if row < 0 or k_idx < 0:
            # Disable key props
            return
            
        shape = bpy.context.scene.rzm.shapes[row]
        key = shape.shape_keys[k_idx]
        
        self.is_updating_key_ui = True
        self.inp_k_frame.setValue(key.key_name)
        self.inp_k_mode.setCurrentText(key.mode)
        self.inp_k_mul.setValue(key.multiplier)
        self.is_updating_key_ui = False

    def synch_k_frame(self, v):
        if self.is_updating_key_ui: return
        self._get_key().key_name = v
        # Update list item text
        self.list_keys.currentItem().setText(f"Key {v}")

    def synch_k_mode(self, v):
        if self.is_updating_key_ui: return
        self._get_key().mode = v

    def synch_k_mul(self, v):
        if self.is_updating_key_ui: return
        self._get_key().multiplier = v

    def _get_key(self):
        row = self.list_widget.currentRow()
        k_idx = self.list_keys.currentRow()
        return bpy.context.scene.rzm.shapes[row].shape_keys[k_idx]
