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

    def on_selection_changed(self, current, previous):
        self.update_properties()

    def sync_list_items(self, data_list, name_func):
        """
        Synchronizes the list widget with data_list.
        Preserves selection if possible.
        """
        current_row = self.list_widget.currentRow()
        
        # 1. Adjust count
        while self.list_widget.count() < len(data_list):
            self.list_widget.addItem("")
        while self.list_widget.count() > len(data_list):
            self.list_widget.takeItem(self.list_widget.count() - 1)
            
        # 2. Update Names
        for i, item_data in enumerate(data_list):
            item_widget = self.list_widget.item(i)
            new_name = name_func(item_data)
            if item_widget.text() != new_name:
                item_widget.setText(new_name)
                
        # 3. Restore Selection (if valid and not already set)
        if current_row >= 0 and current_row < self.list_widget.count():
            if self.list_widget.currentRow() != current_row:
                self.list_widget.setCurrentRow(current_row)

class ValuesTab(BaseListTab):
    def __init__(self):
        super().__init__()
        
        # Props
        self.inp_name = QtWidgets.QLineEdit()
        self.inp_name.editingFinished.connect(self.synch_name)
        
        self.inp_type = QtWidgets.QComboBox()
        self.inp_type.addItems(["INT", "FLOAT", "VECTOR"])
        self.inp_type.currentTextChanged.connect(self.synch_type)
        
        self.inp_val_int = QtWidgets.QSpinBox()
        self.inp_val_int.setRange(-999999, 999999)
        self.inp_val_int.valueChanged.connect(self.synch_val_int)
        
        self.inp_val_float = QtWidgets.QDoubleSpinBox()
        self.inp_val_float.setRange(-999999.0, 999999.0)
        self.inp_val_float.valueChanged.connect(self.synch_val_float)

        # Vector UI
        self.inp_val_vector_widget = QtWidgets.QWidget()
        self.vec_layout = QtWidgets.QHBoxLayout(self.inp_val_vector_widget)
        self.vec_layout.setContentsMargins(0, 0, 0, 0)
        self.inp_vecs = []
        for i in range(4):
            sb = QtWidgets.QDoubleSpinBox()
            sb.setRange(-999999.0, 999999.0)
            sb.valueChanged.connect(lambda v, idx=i: self.synch_val_vector(idx, v))
            self.vec_layout.addWidget(sb)
            self.inp_vecs.append(sb)
        
        self.props_layout.addRow("Name:", self.inp_name)
        self.props_layout.addRow("Type:", self.inp_type)
        self.props_layout.addRow("Int Value:", self.inp_val_int)
        self.props_layout.addRow("Float Value:", self.inp_val_float)
        self.props_layout.addRow("Vector:", self.inp_val_vector_widget)

    def refresh(self):
        if not bpy.context: return
        self.sync_list_items(bpy.context.scene.rzm.rzm_values, lambda x: x.value_name)
        
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
            # Selection restoration handled by sync roughly, but we might want to select row-1
            # sync keeps "current_row", but if we deleted it, we want current_row (which is now next item) or prev?
            # QListWidget auto-handles deletion selection often, but we are managing it.
            # Let's leave it to QListWidget default behavior if possible, or explicit:
            new_count = self.list_widget.count()
            if new_count > 0:
                self.list_widget.setCurrentRow(min(row, new_count-1))

    def update_properties(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(bpy.context.scene.rzm.rzm_values):
            self.props_group.setEnabled(False)
            return
            
        self.props_group.setEnabled(True)
        val = bpy.context.scene.rzm.rzm_values[row]
        
        self.is_updating_ui = True
        
        if self.inp_name.text() != val.value_name:
            self.inp_name.setText(val.value_name)
            
        if self.inp_type.currentText() != val.value_type:
            self.inp_type.setCurrentText(val.value_type)
            
        if self.inp_val_int.value() != val.int_value:
            self.inp_val_int.setValue(val.int_value)
            
        if self.inp_val_float.value() != val.float_value:
            self.inp_val_float.setValue(val.float_value)

        for i in range(4):
            if abs(self.inp_vecs[i].value() - val.vector_value[i]) > 0.0001:
                self.inp_vecs[i].setValue(val.vector_value[i])
        
        # Visibility
        self.inp_val_int.setVisible(val.value_type == 'INT')
        self.inp_val_float.setVisible(val.value_type == 'FLOAT')
        self.inp_val_vector_widget.setVisible(val.value_type == 'VECTOR')
        
        self.is_updating_ui = False

    def synch_name(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_value(index=row, prop_name="value_name", val_str=self.inp_name.text())
        
        # Local visual update to feel responsive (revert if needed on refresh)
        self.list_widget.item(row).setText(self.inp_name.text())

    def synch_type(self, txt):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_value(index=row, prop_name="value_type", val_str=txt)
        self.update_properties() # To toggle visibility

    def synch_val_int(self, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_value(index=row, prop_name="int_value", val_str=str(v))

    def synch_val_float(self, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_value(index=row, prop_name="float_value", val_str=str(v))

    def synch_val_vector(self, idx, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        # Prop name format for indexed update: vector_value[idx]
        bpy.ops.rzm.update_value(index=row, prop_name=f"vector_value[{idx}]", val_str=str(v))

class TogglesTab(BaseListTab):
    def __init__(self):
        super().__init__()
        
        self.inp_name = QtWidgets.QLineEdit()
        self.inp_name.editingFinished.connect(self.synch_name)
        
        self.inp_len = QtWidgets.QSpinBox()
        self.inp_len.setRange(1, 32)
        self.inp_len.valueChanged.connect(self.synch_len)

        self.inp_start_idx = QtWidgets.QSpinBox()
        self.inp_start_idx.setRange(0, 999)
        self.inp_start_idx.valueChanged.connect(self.synch_start_idx)
        
        self.props_layout.addRow("Name:", self.inp_name)
        self.props_layout.addRow("Length:", self.inp_len)
        self.props_layout.addRow("Start Index:", self.inp_start_idx)

    def refresh(self):
        if not bpy.context: return
        self.sync_list_items(bpy.context.scene.rzm.toggle_definitions, lambda x: x.toggle_name)

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
            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(min(row, self.list_widget.count()-1))

    def update_properties(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(bpy.context.scene.rzm.toggle_definitions):
            self.props_group.setEnabled(False)
            return

        self.props_group.setEnabled(True)
        t = bpy.context.scene.rzm.toggle_definitions[row]
        
        self.is_updating_ui = True
        if self.inp_name.text() != t.toggle_name:
            self.inp_name.setText(t.toggle_name)
        if self.inp_len.value() != t.toggle_length:
            self.inp_len.setValue(t.toggle_length)
        if self.inp_start_idx.value() != t.toggle_start_index:
            self.inp_start_idx.setValue(t.toggle_start_index)
        self.is_updating_ui = False

    def synch_name(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_project_toggle(index=row, prop_name="toggle_name", val_str=self.inp_name.text())
        self.list_widget.item(row).setText(self.inp_name.text())

    def synch_len(self, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_project_toggle(index=row, prop_name="toggle_length", val_str=str(v))

    def synch_start_idx(self, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_project_toggle(index=row, prop_name="toggle_start_index", val_str=str(v))

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
        
        self.chk_disable_export = QtWidgets.QCheckBox("Disable Export")
        self.chk_disable_export.toggled.connect(self.synch_disable_export)
        
        self.props_layout.addRow("Name:", self.inp_name)
        self.props_layout.addRow("Type:", self.inp_type)
        self.props_layout.addRow("Anim Condition:", self.inp_cond)
        self.props_layout.addRow("", self.chk_disable_export)
        
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
        if not bpy.context: return
        self.sync_list_items(bpy.context.scene.rzm.shapes, lambda x: x.shape_name)

    def add_item(self):
        bpy.ops.rzm.add_shape()
        self.refresh()
        self.list_widget.setCurrentRow(self.list_widget.count()-1)

    def remove_item(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            bpy.ops.rzm.remove_shape()
            self.refresh()
            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(min(row, self.list_widget.count()-1))

    def update_properties(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(bpy.context.scene.rzm.shapes):
            self.props_group.setEnabled(False)
            self.list_keys.clear() # No shape selected
            return

        self.props_group.setEnabled(True)
        shape = bpy.context.scene.rzm.shapes[row]
        
        self.is_updating_ui = True
        if self.inp_name.text() != shape.shape_name:
            self.inp_name.setText(shape.shape_name)
        if self.inp_type.currentText() != shape.shape_type:
            self.inp_type.setCurrentText(shape.shape_type)
        if self.inp_cond.text() != shape.anim_condition:
            self.inp_cond.setText(shape.anim_condition)
        if self.chk_disable_export.isChecked() != shape.disable_export:
            self.chk_disable_export.setChecked(shape.disable_export)
        self.is_updating_ui = False
        
        self.refresh_keys_list(shape)

    def synch_name(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_shape(shape_index=row, prop_name="shape_name", val_str=self.inp_name.text())
        self.list_widget.item(row).setText(self.inp_name.text())

    def synch_type(self, t):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_shape(shape_index=row, prop_name="shape_type", val_str=t)

    def synch_cond(self):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        _val = self.inp_cond.text()
        bpy.ops.rzm.update_shape(shape_index=row, prop_name="anim_condition", val_str=_val)

    def synch_disable_export(self, v):
        if self.is_updating_ui: return
        row = self.list_widget.currentRow()
        bpy.ops.rzm.update_shape(shape_index=row, prop_name="disable_export", val_str=str(v))

    # --- Shape Keys Logic
    def refresh_keys_list(self, shape):
        # Sync Logic inline for list_keys
        k_list = shape.shape_keys
        current_row = self.list_keys.currentRow()
        
        while self.list_keys.count() < len(k_list):
            self.list_keys.addItem("")
        while self.list_keys.count() > len(k_list):
            self.list_keys.takeItem(self.list_keys.count() - 1)
            
        for i, k in enumerate(k_list):
            item = self.list_keys.item(i)
            txt = f"Key {k.key_name}"
            if item.text() != txt:
                item.setText(txt)
                
        if current_row >= 0 and current_row < self.list_keys.count():
             if self.list_keys.currentRow() != current_row:
                 self.list_keys.setCurrentRow(current_row)

    def add_key(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        # Shape index is 'row'
        bpy.ops.rzm.add_shape_key(shape_index=row)
        
        # Refresh needs fetching shape again
        shape = bpy.context.scene.rzm.shapes[row]
        self.refresh_keys_list(shape)
        self.list_keys.setCurrentRow(len(shape.shape_keys)-1)

    def remove_key(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        k_idx = self.list_keys.currentRow()
        if k_idx >= 0:
            bpy.ops.rzm.remove_shape_key(shape_index=row, key_index=k_idx)
            
            shape = bpy.context.scene.rzm.shapes[row]
            self.refresh_keys_list(shape)
            if self.list_keys.count() > 0:
                self.list_keys.setCurrentRow(min(k_idx, self.list_keys.count()-1))

    def on_key_selected(self):
        row = self.list_widget.currentRow()
        k_idx = self.list_keys.currentRow()
        if row < 0 or k_idx < 0:
            # Disable key props
            # TODO: Disable widgets?
            return
            
        shape = bpy.context.scene.rzm.shapes[row]
        if k_idx >= len(shape.shape_keys): return
        key = shape.shape_keys[k_idx]
        
        self.is_updating_key_ui = True
        
        if self.inp_k_frame.value() != key.key_name:
            self.inp_k_frame.setValue(key.key_name)
            
        if self.inp_k_mode.currentText() != key.mode:
            self.inp_k_mode.setCurrentText(key.mode)
            
        # Float comparison with tolerance? Or just direct
        if abs(self.inp_k_mul.value() - key.multiplier) > 0.001:
            self.inp_k_mul.setValue(key.multiplier)
            
        self.is_updating_key_ui = False

    def synch_k_frame(self, v):
        if self.is_updating_key_ui: return
        row = self.list_widget.currentRow()
        k_idx = self.list_keys.currentRow()
        bpy.ops.rzm.update_shape_key(shape_index=row, key_index=k_idx, prop_name="key_name", val_str=str(v))
        
        # Update list Item text too
        self.list_keys.item(k_idx).setText(f"Key {v}")

    def synch_k_mode(self, v):
        if self.is_updating_key_ui: return
        row = self.list_widget.currentRow()
        k_idx = self.list_keys.currentRow()
        bpy.ops.rzm.update_shape_key(shape_index=row, key_index=k_idx, prop_name="mode", val_str=str(v))

    def synch_k_mul(self, v):
        if self.is_updating_key_ui: return
        row = self.list_widget.currentRow()
        k_idx = self.list_keys.currentRow()
        bpy.ops.rzm.update_shape_key(shape_index=row, key_index=k_idx, prop_name="multiplier", val_str=str(v))
