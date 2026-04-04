# RZMenu/qt_editor/widgets/variables_manager.py
import bpy
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.theme import get_current_theme
from .lib.widgets import RZPanelWidget, RZColorButton
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

class RZDraggableVariableList(QtWidgets.QListWidget):
    def __init__(self, prefix="", parent=None):
        super().__init__(parent)
        self.prefix = prefix
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()
        text = item.text()
        
        # Rayvich: logic to prefix without duplication
        if self.prefix:
            clean_name = text.lstrip(self.prefix)
            text = self.prefix + clean_name
            
        mime_data.setText(text)
        # Add custom MIME type for internal RZMenu use
        mime_data.setData("application/x-rzm-variable", text.encode('utf-8'))
        
        drag.setMimeData(mime_data)
        drag.exec_(supportedActions)


class BaseListTab(QtWidgets.QWidget):
    def __init__(self, prefix=""):
        super().__init__()
        self.prefix = prefix
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # List
        self.list_widget = RZDraggableVariableList(prefix=self.prefix)
        self.list_widget.currentItemChanged.connect(self.on_selection_changed)
        self.list_widget.itemChanged.connect(self.on_item_changed)
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
        
    def on_item_changed(self, item):
        pass # To be overridden

    def _get_current_orig_idx(self):
        """Returns the orig_idx (Blender index) of the currently selected item, or None."""
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return item.data(QtCore.Qt.UserRole)

    def sync_list_items(self, enumerated_data, name_func, force_export_func=None):
        """
        Synchronizes the list widget with enumerated_data: List[Tuple[int, object]].
        Preserves selection by orig_idx (Blender index) across re-sorts.
        force_export_func: optional callable(item_data) -> bool for gold highlight.
        """
        # Remember which Blender index was selected before the sync
        prev_orig_idx = self._get_current_orig_idx()

        self.list_widget.blockSignals(True)
        try:
            # 1. Adjust count
            while self.list_widget.count() < len(enumerated_data):
                self.list_widget.addItem("")
            while self.list_widget.count() > len(enumerated_data):
                self.list_widget.takeItem(self.list_widget.count() - 1)

            # 2. Update text, color, and UserRole data
            gold_color = QtGui.QColor("#FFD700")
            normal_color = self.list_widget.palette().color(self.list_widget.foregroundRole())

            for i, (orig_idx, item_data) in enumerate(enumerated_data):
                item_widget = self.list_widget.item(i)
                new_name = name_func(item_data)
                item_widget.setFlags(
                    QtCore.Qt.ItemIsEditable |
                    QtCore.Qt.ItemIsEnabled |
                    QtCore.Qt.ItemIsSelectable
                )
                item_widget.setData(QtCore.Qt.UserRole, orig_idx)
                if item_widget.text() != new_name:
                    item_widget.setText(new_name)

                # Gold color for force_export items instead of ★ in text
                if force_export_func is not None:
                    if force_export_func(item_data):
                        item_widget.setForeground(gold_color)
                        font = item_widget.font()
                        font.setBold(True)
                        item_widget.setFont(font)
                    else:
                        item_widget.setForeground(normal_color)
                        font = item_widget.font()
                        font.setBold(False)
                        item_widget.setFont(font)
        finally:
            self.list_widget.blockSignals(False)

        # 3. Restore selection by orig_idx (survives re-sort)
        if prev_orig_idx is not None:
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(QtCore.Qt.UserRole) == prev_orig_idx:
                    if self.list_widget.currentRow() != i:
                        self.list_widget.setCurrentRow(i)
                    break

class ValuesTab(BaseListTab):
    def __init__(self):
        super().__init__(prefix="$")
        
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
            
        self.inp_val_color = RZColorButton()
        self.inp_val_color.setFixedSize(24, 24)
        self.inp_val_color.colorChanged.connect(self.synch_color_picker)
        self.vec_layout.addWidget(self.inp_val_color)
        
        self.props_layout.addRow("Name:", self.inp_name)
        self.props_layout.addRow("Type:", self.inp_type)
        self.props_layout.addRow("Int Value:", self.inp_val_int)
        self.props_layout.addRow("Float Value:", self.inp_val_float)
        self.props_layout.addRow("Vector:", self.inp_val_vector_widget)

        self.chk_force_export = QtWidgets.QToolButton()
        self.chk_force_export.setCheckable(True)
        self.chk_force_export.setText("★")
        self.chk_force_export.setToolTip("Force Export: Always include this variable in templates/partial exports")
        self.chk_force_export.setFixedSize(24, 24)
        self.chk_force_export.clicked.connect(self.synch_force_export)
        self.props_layout.addRow("Force Export:", self.chk_force_export)

        # Tier assignment — chip buttons for each configured tier
        self.tiers_group = QtWidgets.QGroupBox("Mod Producer Tiers")
        self.tiers_layout = QtWidgets.QHBoxLayout(self.tiers_group)
        self.tiers_layout.setContentsMargins(4, 4, 4, 4)
        self.tiers_layout.setSpacing(4)
        self._tier_buttons = {}  # tier_id -> QPushButton
        self.props_layout.addRow(self.tiers_group)

    def refresh(self):
        if not bpy.context: return
        data = list(enumerate(bpy.context.scene.rzm.rzm_values))
        data.sort(key=lambda x: x[1].force_export, reverse=True)
        self.sync_list_items(
            data,
            name_func=lambda x: x.value_name,
            force_export_func=lambda x: x.force_export
        )

    def update_properties(self):
        if self.is_updating_ui: return
        self.is_updating_ui = True
        
        item = self.list_widget.currentItem()
        if not item:
            self.props_group.hide()
            self.is_updating_ui = False
            return
            
        orig_idx = item.data(QtCore.Qt.UserRole)
        val = bpy.context.scene.rzm.rzm_values[orig_idx]
        self.props_group.show()
        
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
        self.inp_val_color.set_color(list(val.vector_value))
        
        # Visibility (Smart hide for Form Layout)
        def set_row_visible(widget, visible):
            label = self.props_layout.labelForField(widget)
            if label: label.setVisible(visible)
            widget.setVisible(visible)

        set_row_visible(self.inp_val_int, val.value_type == 'INT')
        set_row_visible(self.inp_val_float, val.value_type == 'FLOAT')
        set_row_visible(self.inp_val_vector_widget, val.value_type == 'VECTOR')
        
        self.chk_force_export.blockSignals(True)
        self.chk_force_export.setChecked(val.force_export)
        self._update_star_style(self.chk_force_export)
        self.chk_force_export.blockSignals(False)

        self._update_tier_chips(orig_idx, val)

        self.is_updating_ui = False

    def _update_star_style(self, btn):
        t = get_current_theme()
        if btn.isChecked():
            # Glowing gold star
            btn.setStyleSheet(f"""
                color: #FFD700; 
                background: rgba(255, 215, 0, 40); 
                border: 2px solid #FFD700; 
                border-radius: 4px; 
                font-size: 18px;
                font-weight: bold;
            """)
            btn.setStyleSheet(f"""
                color: {t.get('text_dark', '#666')}; 
                background: transparent; 
                border: 1px solid {t['border_main']}; 
                border-radius: 4px; 
                font-size: 16px;
            """)

    def _get_available_tiers(self):
        """Returns list of (tier_id, color_tuple) from AddonPreferences."""
        try:
            if not bpy.context: return []
            for name, addon in bpy.context.preferences.addons.items():
                if 'RZMenu' in name or 'rzm' in name.lower():
                    return [(t.tier_id, tuple(t.tier_color)) for t in addon.preferences.tier_definitions]
        except Exception:
            pass
        return []

    def _update_tier_chips(self, value_index, val):
        """Rebuild tier chip buttons for the selected value."""
        available = self._get_available_tiers()
        active_ids = {t.tier_id for t in val.export_tiers}
        existing = set(self._tier_buttons.keys())
        available_ids = {tid for tid, _ in available}

        # Remove obsolete chips
        for tid in (existing - available_ids):
            btn = self._tier_buttons.pop(tid)
            self.tiers_layout.removeWidget(btn)
            btn.deleteLater()

        # Add or update chips
        for tier_id, _ in available:
            if tier_id not in self._tier_buttons:
                btn = QtWidgets.QPushButton(tier_id)
                btn.setCheckable(True)
                btn.setFixedHeight(22)
                btn.setCursor(QtWidgets.QSizePolicy.Policy.Expanding)
                btn.clicked.connect(
                    lambda checked, tid=tier_id, vidx=value_index: self._on_tier_clicked(vidx, tid, checked)
                )
                self.tiers_layout.addWidget(btn)
                self._tier_buttons[tier_id] = btn

        if not any(isinstance(self.tiers_layout.itemAt(i), QtWidgets.QSpacerItem)
                   for i in range(self.tiers_layout.count())):
            self.tiers_layout.addStretch()

        t = get_current_theme()
        for tier_id, btn in self._tier_buttons.items():
            is_active = tier_id in active_ids
            btn.blockSignals(True)
            btn.setChecked(is_active)
            btn.blockSignals(False)
            # Reconnect with updated value_index
            try:
                btn.clicked.disconnect()
            except Exception:
                pass
            btn.clicked.connect(
                lambda checked, tid=tier_id, vidx=value_index: self._on_tier_clicked(vidx, tid, checked)
            )
            if is_active:
                btn.setStyleSheet(
                    "QPushButton { background: #1a6ea8; color: #fff; border: 1px solid #3b9de0; "
                    "border-radius: 3px; padding: 1px 8px; font-size: 11px; font-weight: bold; }"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {t.get('text_dark', '#888')}; "
                    f"border: 1px solid {t.get('border_main', '#555')}; "
                    "border-radius: 3px; padding: 1px 8px; font-size: 11px; }"
                )

    def _on_tier_clicked(self, value_index, tier_id, checked):
        if self.is_updating_ui: return
        if checked:
            bpy.ops.rzm.add_value_tier(value_index=value_index, tier_id=tier_id)
        else:
            bpy.ops.rzm.remove_value_tier(value_index=value_index, tier_id=tier_id)

    def synch_force_export(self, checked):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_value(index=orig_idx, prop_name="force_export", val_str=str(checked))
        self._update_star_style(self.chk_force_export)
        self.refresh() # Re-sort after change

    def synch_name(self):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_value(index=orig_idx, prop_name="value_name", val_str=self.inp_name.text())
        self.refresh()

    def on_item_changed(self, item):
        if self.is_updating_ui: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        if orig_idx is not None:
            bpy.ops.rzm.update_value(index=orig_idx, prop_name="value_name", val_str=item.text())
            self.inp_name.setText(item.text())

    def synch_type(self, txt):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_value(index=orig_idx, prop_name="value_type", val_str=txt)
        self.update_properties() # To toggle visibility

    def synch_val_int(self, v):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_value(index=orig_idx, prop_name="int_value", val_str=str(v))

    def synch_val_float(self, v):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_value(index=orig_idx, prop_name="float_value", val_str=str(v))

    def synch_val_vector(self, idx, v):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        # Prop name format for indexed update: vector_value[idx]
        bpy.ops.rzm.update_value(index=orig_idx, prop_name=f"vector_value[{idx}]", val_str=str(v))
        
        # Update color button without triggering its signals
        self.inp_val_color.blockSignals(True)
        self.inp_val_color.set_color([self.inp_vecs[i].value() for i in range(4)])
        self.inp_val_color.blockSignals(False)

    def synch_color_picker(self, color_data):
        if self.is_updating_ui: return
        # Setting values will trigger synch_val_vector
        for i in range(4):
            if i < len(color_data):
                self.inp_vecs[i].setValue(color_data[i])

    def add_item(self):
        bpy.ops.rzm.add_value()
        self.refresh()

    def remove_item(self):
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.context.scene.rzm_active_value_index = orig_idx
        bpy.ops.rzm.remove_value()
        self.refresh()

class TogglesTab(BaseListTab):
    def __init__(self):
        super().__init__(prefix="@")
        
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

        self.chk_force_export = QtWidgets.QToolButton()
        self.chk_force_export.setCheckable(True)
        self.chk_force_export.setText("★")
        self.chk_force_export.setToolTip("Force Export: Always include this toggle in templates")
        self.chk_force_export.setFixedSize(24, 24)
        self.chk_force_export.clicked.connect(self.synch_force_export)
        self.props_layout.addRow("Force Export:", self.chk_force_export)

    def refresh(self):
        if not bpy.context: return
        data = list(enumerate(bpy.context.scene.rzm.toggle_definitions))
        data.sort(key=lambda x: x[1].force_export, reverse=True)
        self.sync_list_items(
            data,
            name_func=lambda x: x.toggle_name,
            force_export_func=lambda x: x.force_export
        )

    def update_properties(self):
        if self.is_updating_ui: return
        self.is_updating_ui = True
        
        item = self.list_widget.currentItem()
        if not item:
            self.props_group.hide()
            self.is_updating_ui = False
            return
            
        orig_idx = item.data(QtCore.Qt.UserRole)
        t = bpy.context.scene.rzm.toggle_definitions[orig_idx]
        self.props_group.show()
        
        if self.inp_name.text() != t.toggle_name:
            self.inp_name.setText(t.toggle_name)
        if self.inp_len.value() != t.toggle_length:
            self.inp_len.setValue(t.toggle_length)
        if self.inp_start_idx.value() != t.toggle_start_index:
            self.inp_start_idx.setValue(t.toggle_start_index)
            
        self.chk_force_export.blockSignals(True)
        self.chk_force_export.setChecked(t.force_export)
        self._update_star_style(self.chk_force_export)
        self.chk_force_export.blockSignals(False)

        self.is_updating_ui = False

    def _update_star_style(self, btn):
        t = get_current_theme()
        if btn.isChecked():
            btn.setStyleSheet(f"""
                color: #FFD700; 
                background: rgba(255, 215, 0, 40); 
                border: 2px solid #FFD700; 
                border-radius: 4px; 
                font-size: 18px;
                font-weight: bold;
            """)
        else:
            btn.setStyleSheet(f"""
                color: {t.get('text_dark', '#666')}; 
                background: transparent; 
                border: 1px solid {t['border_main']}; 
                border-radius: 4px; 
                font-size: 16px;
            """)

    def synch_force_export(self, checked):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_project_toggle(index=orig_idx, prop_name="force_export", val_str=str(checked))
        self.refresh()

    def synch_name(self):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_project_toggle(index=orig_idx, prop_name="toggle_name", val_str=self.inp_name.text())
        self.refresh()

    def on_item_changed(self, item):
        if self.is_updating_ui: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        if orig_idx is not None:
            bpy.ops.rzm.update_project_toggle(index=orig_idx, prop_name="toggle_name", val_str=item.text())
            self.inp_name.setText(item.text())

    def synch_len(self, v):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_project_toggle(index=orig_idx, prop_name="toggle_length", val_str=str(v))

    def synch_start_idx(self, v):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_project_toggle(index=orig_idx, prop_name="toggle_start_index", val_str=str(v))

    def add_item(self):
        bpy.ops.rzm.add_project_toggle()
        self.refresh()

    def remove_item(self):
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.context.scene.rzm_active_toggle_def_index = orig_idx
        bpy.ops.rzm.remove_project_toggle()
        self.refresh()

class ShapesTab(BaseListTab):
    def __init__(self):
        super().__init__(prefix="#")
        
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
        
        h_export = QtWidgets.QHBoxLayout()
        self.chk_disable_export = QtWidgets.QCheckBox("Disable Export")
        self.chk_disable_export.toggled.connect(self.synch_disable_export)
        h_export.addWidget(self.chk_disable_export)

        self.chk_force_export = QtWidgets.QToolButton()
        self.chk_force_export.setCheckable(True)
        self.chk_force_export.setText("★")
        self.chk_force_export.setToolTip("Force Export: Always include this shape in templates")
        self.chk_force_export.setFixedSize(24, 24)
        self.chk_force_export.clicked.connect(self.synch_force_export)
        h_export.addWidget(self.chk_force_export)
        h_export.addWidget(QtWidgets.QLabel("Force Export"))
        h_export.addStretch()

        self.props_layout.addRow("Export Options:", h_export)
        
        # Tier assignment — chip buttons for each configured tier
        self.tiers_group = QtWidgets.QGroupBox("Mod Producer Tiers")
        self.tiers_layout = QtWidgets.QHBoxLayout(self.tiers_group)
        self.tiers_layout.setContentsMargins(4, 4, 4, 4)
        self.tiers_layout.setSpacing(4)
        self._tier_buttons = {}  # tier_id -> QPushButton
        self.props_layout.addRow(self.tiers_group)
        
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
        data = list(enumerate(bpy.context.scene.rzm.shapes))
        data.sort(key=lambda x: x[1].force_export, reverse=True)
        self.sync_list_items(
            data,
            name_func=lambda x: x.shape_name,
            force_export_func=lambda x: x.force_export
        )

    def update_properties(self):
        if self.is_updating_ui: return
        self.is_updating_ui = True
        
        item = self.list_widget.currentItem()
        if not item:
            self.props_group.hide()
            self.is_updating_ui = False
            return
            
        orig_idx = item.data(QtCore.Qt.UserRole)
        shape = bpy.context.scene.rzm.shapes[orig_idx]
        self.props_group.show()
        
        if self.inp_name.text() != shape.shape_name:
            self.inp_name.setText(shape.shape_name)
        if self.inp_type.currentText() != shape.shape_type:
            self.inp_type.setCurrentText(shape.shape_type)
        if self.inp_cond.text() != shape.anim_condition:
            self.inp_cond.setText(shape.anim_condition)
        if self.chk_disable_export.isChecked() != shape.disable_export:
            self.chk_disable_export.setChecked(shape.disable_export)
            
        self.chk_force_export.blockSignals(True)
        self.chk_force_export.setChecked(shape.force_export)
        self._update_star_style(self.chk_force_export)
        self.chk_force_export.blockSignals(False)
        
        self._update_tier_chips(orig_idx, shape)

        self.refresh_keys_list(shape)
        self.is_updating_ui = False

    def _update_star_style(self, btn):
        t = get_current_theme()
        if btn.isChecked():
            btn.setStyleSheet(f"""
                color: #FFD700; 
                background: rgba(255, 215, 0, 40); 
                border: 2px solid #FFD700; 
                border-radius: 4px; 
                font-size: 18px;
                font-weight: bold;
            """)
        else:
            btn.setStyleSheet(f"""
                color: {t.get('text_dark', '#666')}; 
                background: transparent; 
                border: 1px solid {t['border_main']}; 
                border-radius: 4px; 
                font-size: 16px;
            """)

    def _get_available_tiers(self):
        """Returns list of (tier_id, color_tuple) from AddonPreferences."""
        try:
            if not bpy.context: return []
            for name, addon in bpy.context.preferences.addons.items():
                if 'RZMenu' in name or 'rzm' in name.lower():
                    return [(t.tier_id, tuple(t.tier_color)) for t in addon.preferences.tier_definitions]
        except Exception:
            pass
        return []

    def _update_tier_chips(self, shape_index, shape):
        """Rebuild tier chip buttons for the selected shape."""
        available = self._get_available_tiers()
        active_ids = {t.tier_id for t in shape.export_tiers}
        existing = set(self._tier_buttons.keys())
        available_ids = {tid for tid, _ in available}

        # Remove obsolete chips
        for tid in (existing - available_ids):
            btn = self._tier_buttons.pop(tid)
            self.tiers_layout.removeWidget(btn)
            btn.deleteLater()

        # Add or update chips
        for tier_id, _ in available:
            if tier_id not in self._tier_buttons:
                btn = QtWidgets.QPushButton(tier_id)
                btn.setCheckable(True)
                btn.setFixedHeight(22)
                btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(
                    lambda checked, tid=tier_id, sidx=shape_index: self._on_tier_clicked(sidx, tid, checked)
                )
                self.tiers_layout.addWidget(btn)
                self._tier_buttons[tier_id] = btn

        if not any(isinstance(self.tiers_layout.itemAt(i), QtWidgets.QSpacerItem)
                   for i in range(self.tiers_layout.count())):
            self.tiers_layout.addStretch()

        t = get_current_theme()
        for tier_id, btn in self._tier_buttons.items():
            is_active = tier_id in active_ids
            btn.blockSignals(True)
            btn.setChecked(is_active)
            btn.blockSignals(False)
            # Reconnect with updated shape_index
            try:
                btn.clicked.disconnect()
            except Exception:
                pass
            btn.clicked.connect(
                lambda checked, tid=tier_id, sidx=shape_index: self._on_tier_clicked(sidx, tid, checked)
            )
            if is_active:
                btn.setStyleSheet(
                    "QPushButton { background: #1a6ea8; color: #fff; border: 1px solid #3b9de0; "
                    "border-radius: 3px; padding: 1px 8px; font-size: 11px; font-weight: bold; }"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {t.get('text_dark', '#888')}; "
                    f"border: 1px solid {t.get('border_main', '#555')}; "
                    "border-radius: 3px; padding: 1px 8px; font-size: 11px; }"
                )

    def _on_tier_clicked(self, shape_index, tier_id, checked):
        if self.is_updating_ui: return
        if checked:
            bpy.ops.rzm.add_shape_tier(shape_index=shape_index, tier_id=tier_id)
        else:
            bpy.ops.rzm.remove_shape_tier(shape_index=shape_index, tier_id=tier_id)

    def synch_force_export(self, checked):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_shape(shape_index=orig_idx, prop_name="force_export", val_str=str(checked))
        self._update_star_style(self.chk_force_export)
        self.refresh()

    def synch_name(self):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_shape(shape_index=orig_idx, prop_name="shape_name", val_str=self.inp_name.text())
        self.refresh()

    def on_item_changed(self, item):
        if self.is_updating_ui: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        if orig_idx is not None:
            bpy.ops.rzm.update_shape(shape_index=orig_idx, prop_name="shape_name", val_str=item.text())
            self.inp_name.setText(item.text())

    def synch_type(self, t):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_shape(shape_index=orig_idx, prop_name="shape_type", val_str=t)

    def synch_cond(self):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        _val = self.inp_cond.text()
        bpy.ops.rzm.update_shape(shape_index=orig_idx, prop_name="anim_condition", val_str=_val)

    def synch_disable_export(self, v):
        if self.is_updating_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.update_shape(shape_index=orig_idx, prop_name="disable_export", val_str=str(v))

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

    def add_item(self):
        bpy.ops.rzm.add_shape()
        self.refresh()

    def remove_item(self):
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        # We don't have rzm_active_shape_index in scene, so we use operator parameters if available
        # or rely on active selection logic in operators.
        # Actually RZMenu operators for shapes usually take indices.
        bpy.ops.rzm.remove_shape(shape_index=orig_idx)
        self.refresh()

    def on_key_selected(self):
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        k_idx = self.list_keys.currentRow()
        
        if orig_idx < 0 or k_idx < 0:
            return
            
        shape = bpy.context.scene.rzm.shapes[orig_idx]
        if k_idx >= len(shape.shape_keys): return
        key = shape.shape_keys[k_idx]
        
        self.is_updating_key_ui = True
        if self.inp_k_frame.value() != key.key_name:
            self.inp_k_frame.setValue(key.key_name)
        if self.inp_k_mode.currentText() != key.mode:
            self.inp_k_mode.setCurrentText(key.mode)
        if abs(self.inp_k_mul.value() - key.multiplier) > 0.001:
            self.inp_k_mul.setValue(key.multiplier)
        self.is_updating_key_ui = False

    def synch_k_frame(self, v):
        if self.is_updating_key_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        k_idx = self.list_keys.currentRow()
        bpy.ops.rzm.update_shape_key(shape_index=orig_idx, key_index=k_idx, prop_name="key_name", val_str=str(v))
        self.list_keys.item(k_idx).setText(f"Key {v}")

    def synch_k_mode(self, v):
        if self.is_updating_key_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        k_idx = self.list_keys.currentRow()
        bpy.ops.rzm.update_shape_key(shape_index=orig_idx, key_index=k_idx, prop_name="mode", val_str=str(v))

    def synch_k_mul(self, v):
        if self.is_updating_key_ui: return
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        k_idx = self.list_keys.currentRow()
        bpy.ops.rzm.update_shape_key(shape_index=orig_idx, key_index=k_idx, prop_name="multiplier", val_str=str(v))

    def add_key(self):
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        bpy.ops.rzm.add_shape_key(shape_index=orig_idx)
        shape = bpy.context.scene.rzm.shapes[orig_idx]
        self.refresh_keys_list(shape)
        self.list_keys.setCurrentRow(len(shape.shape_keys)-1)

    def remove_key(self):
        item = self.list_widget.currentItem()
        if not item: return
        orig_idx = item.data(QtCore.Qt.UserRole)
        k_idx = self.list_keys.currentRow()
        if k_idx >= 0:
            bpy.ops.rzm.remove_shape_key(shape_index=orig_idx, key_index=k_idx)
            shape = bpy.context.scene.rzm.shapes[orig_idx]
            self.refresh_keys_list(shape)
            if self.list_keys.count() > 0:
                self.list_keys.setCurrentRow(min(k_idx, self.list_keys.count()-1))

