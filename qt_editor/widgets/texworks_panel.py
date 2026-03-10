# RZMenu/qt_editor/widgets/texworks_panel.py
from PySide6 import QtWidgets, QtCore, QtGui
import bpy
from functools import partial

from .panel_base import RZEditorPanel
from .lib.widgets import RZPushButton, RZLabel, RZLineEdit, RZComboBox, RZSpinBox, RZDoubleSpinBox, RZCheckBox, RZGroupBox, RZScrollArea
from .lib.theme import get_current_theme
from ..core.signals import SIGNALS
from ..context import RZContextManager

# --- UTILS & NAVIGATION ---

class RZTexWorksAnchorBar(QtWidgets.QWidget):
    """Sliding navigation bar for TexWorks."""
    clicked = QtCore.Signal(str)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setFixedHeight(35)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 0)
        self.layout.setSpacing(15)
        
        self.buttons = {}
        for label, tab_id in items:
            btn = QtWidgets.QPushButton(label)
            btn.setObjectName("AnchorButton")
            btn.setFlat(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, n=tab_id: self.clicked.emit(n))
            self.layout.addWidget(btn)
            self.buttons[tab_id] = btn
            
        self.layout.addStretch()
        self.underline = QtWidgets.QWidget(self)
        self.underline.setFixedHeight(2)
        self.underline.hide()
        
        self._anim = QtCore.QPropertyAnimation(self.underline, b"geometry")
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutQuint)
        self.active_tab = None

    def set_active(self, tab_id):
        if self.active_tab == tab_id: return
        self.active_tab = tab_id
        btn = self.buttons.get(tab_id)
        if not btn: return
        self.underline.show()
        t = get_current_theme()
        self.underline.setStyleSheet(f"background-color: {t.get('accent', '#5298D4')}; border-radius: 1px;")
        target_rect = btn.geometry()
        target_rect.setY(self.height() - 3)
        target_rect.setHeight(2)
        self._anim.stop()
        self._anim.setEndValue(target_rect)
        self._anim.start()
        for name, b in self.buttons.items():
            is_active = (name == tab_id)
            col = t.get('text_bright', '#FFF') if is_active else t.get('text_dim', '#888')
            b.setStyleSheet(f"color: {col}; font-weight: {'bold' if is_active else 'normal'}; border: none; background: transparent;")

class RZTexWorksItem(QtWidgets.QWidget):
    """Standardized list row for TexWorks."""
    def __init__(self, index, parent_list, parent=None):
        super().__init__(parent)
        self.index = index
        self.parent_list = parent_list
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 8)
        self.main_layout.setSpacing(4)
        
        # Border/Card styling
        self.setObjectName("TexWorksItem")
        t = get_current_theme()
        self.setStyleSheet(f"#TexWorksItem {{ border: 1px solid {t.get('border', '#3E4451')}; border-radius: 6px; background: {t.get('bg_header', '#2C313A')}; }}")

        self.header_layout = QtWidgets.QHBoxLayout()
        self.header_layout.setSpacing(6)
        self.main_layout.addLayout(self.header_layout)

        self.btn_del = RZPushButton("✕")
        self.btn_del.setFixedWidth(24)
        self.btn_del.clicked.connect(self._on_delete)
        self.header_layout.addWidget(self.btn_del)

    def _on_delete(self):
        self.parent_list.remove_item(self.index)

class RZTexWorksListEditor(QtWidgets.QWidget):
    """Generic list manager with reconciliation."""
    def __init__(self, add_label="+ Add", parent=None):
        super().__init__(parent)
        self._block = False
        self.layout_main = QtWidgets.QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)
        self.layout_main.setSpacing(6)
        
        self.layout_items = QtWidgets.QVBoxLayout()
        self.layout_items.setSpacing(6)
        self.layout_main.addLayout(self.layout_items)
        
        self.btn_add = RZPushButton(add_label)
        self.btn_add.clicked.connect(self.add_item)
        self.layout_main.addWidget(self.btn_add)

    def sync_widgets(self, data_list, widget_factory, update_func=None):
        self._block = True
        current_count = self.layout_items.count()
        new_count = len(data_list)
        if new_count > current_count:
            for i in range(current_count, new_count):
                w = widget_factory(i, data_list[i])
                if w: self.layout_items.addWidget(w)
        elif new_count < current_count:
            for i in range(current_count - 1, new_count - 1, -1):
                item = self.layout_items.takeAt(i)
                if item.widget(): item.widget().deleteLater()
        for i in range(len(data_list)):
            item = self.layout_items.itemAt(i)
            if not item: continue
            w = item.widget()
            if not w or not hasattr(w, 'index'): continue
            w.index = i
            if update_func: update_func(w, data_list[i])
        self._block = False

# --- TABS: RESOURCES ---

class TexWorksResourceItem(RZTexWorksItem):
    def __init__(self, index, data, parent_list, parent=None):
        super().__init__(index, parent_list, parent)
        self.edit_name = RZLineEdit(); self.edit_name.setPlaceholderText("Name")
        self.edit_name.editingFinished.connect(self._on_changed)
        self.header_layout.addWidget(self.edit_name, 1)

        self.cb_type = RZComboBox(); self.cb_type.addItems(["EMPTY", "ON_DISK", "VIRTUAL"])
        self.cb_type.currentTextChanged.connect(self._on_changed)
        self.header_layout.addWidget(self.cb_type)

        self.w_details = QtWidgets.QWidget(); self.l_details = QtWidgets.QFormLayout(self.w_details)
        self.l_details.setContentsMargins(30, 0, 10, 0); self.main_layout.addWidget(self.w_details)
        self.edit_path = RZLineEdit(); self.edit_path.editingFinished.connect(self._on_changed)
        self.l_details.addRow("Path:", self.edit_path)
        self.w_res = QtWidgets.QWidget(); lr = QtWidgets.QHBoxLayout(self.w_res); lr.setContentsMargins(0,0,0,0)
        self.sp_x = RZSpinBox(); self.sp_y = RZSpinBox(); [s.setRange(1, 16384) for s in [self.sp_x, self.sp_y]]
        [s.valueChanged.connect(self._on_changed) for s in [self.sp_x, self.sp_y]]
        lr.addWidget(self.sp_x); lr.addWidget(RZLabel("x")); lr.addWidget(self.sp_y); self.l_details.addRow("Res:", self.w_res)
        self.cb_fmt = RZComboBox(); self.cb_fmt.addItems(['DXGI_FORMAT_R8G8B8A8_UNORM_SRGB', 'DXGI_FORMAT_R8G8B8A8_UNORM', 'DXGI_FORMAT_BC7_UNORM'])
        self.cb_fmt.currentTextChanged.connect(self._on_changed); self.l_details.addRow("Format:", self.cb_fmt)
        self.update_data(data)

    def _on_changed(self, *args):
        if self.parent_list._block: return
        props = {"name": self.edit_name.text(), "type": self.cb_type.currentText(), "path": self.edit_path.text(), "resolution[0]": str(self.sp_x.value()), "resolution[1]": str(self.sp_y.value()), "format": self.cb_fmt.currentText()}
        for k, v in props.items(): self.parent_list.item_changed(self.index, k, v)

    def update_data(self, data):
        self.edit_name.setText(data.name); self.cb_type.setCurrentText(data.type); self.edit_path.setText(data.path); self.sp_x.setValue(data.resolution[0]); self.sp_y.setValue(data.resolution[1]); self.cb_fmt.setCurrentText(data.format)
        self.edit_path.setVisible(data.type == 'ON_DISK'); self.w_res.setVisible(data.type == 'VIRTUAL'); self.cb_fmt.setVisible(data.type == 'VIRTUAL'); self.w_details.setVisible(data.type != 'EMPTY')

class TexWorksResourcesTab(RZTexWorksListEditor):
    def update_ui(self):
        if bpy.context.scene: self.sync_widgets(bpy.context.scene.rzm.tw_resources, lambda i, d: TexWorksResourceItem(i, d, self), lambda w, d: w.update_data(d))
    def add_item(self): bpy.ops.rzm.add_tw_resource(); self.update_ui()
    def remove_item(self, index): bpy.ops.rzm.remove_tw_resource(index=index); self.update_ui()
    def item_changed(self, index, prop, val): bpy.ops.rzm.update_tw_item(collection_name="resources", index=index, prop_name=prop, value_str=val)

# --- TABS: OVERRIDES ---

class TexWorksOverrideItem(RZTexWorksItem):
    def __init__(self, index, data, parent_list, parent=None):
        super().__init__(index, parent_list, parent)
        self.edit_name = RZLineEdit(); self.edit_name.setText(data.name); self.edit_name.editingFinished.connect(self._on_changed); self.header_layout.addWidget(self.edit_name, 1)
        self.edit_hash = RZLineEdit(); self.edit_hash.setPlaceholderText("Hash"); self.edit_hash.setText(data.hash); self.edit_hash.editingFinished.connect(self._on_changed); self.header_layout.addWidget(self.edit_hash, 1)
        self.edit_res = RZLineEdit(); self.edit_res.setPlaceholderText("Resource"); self.edit_res.setText(data.resource_name); self.edit_res.editingFinished.connect(self._on_changed); self.header_layout.addWidget(self.edit_res, 1)
    def _on_changed(self):
        if self.parent_list._block: return
        for k, v in {"name": self.edit_name.text(), "hash": self.edit_hash.text(), "resource_name": self.edit_res.text()}.items(): self.parent_list.item_changed(self.index, k, v)
    def update_data(self, data): self.edit_name.setText(data.name); self.edit_hash.setText(data.hash); self.edit_res.setText(data.resource_name)

class TexWorksOverridesTab(RZTexWorksListEditor):
    def update_ui(self):
        if bpy.context.scene: self.sync_widgets(bpy.context.scene.rzm.tw_overrides, lambda i, d: TexWorksOverrideItem(i, d, self), lambda w, d: w.update_data(d))
    def add_item(self): bpy.ops.rzm.add_tw_override(); self.update_ui()
    def remove_item(self, index): bpy.ops.rzm.remove_tw_override(index=index); self.update_ui()
    def item_changed(self, index, prop, val): bpy.ops.rzm.update_tw_item(collection_name="overrides", index=index, prop_name=prop, value_str=val)

# --- TABS: MATERIALS ---

class TexWorksMaterialItem(RZTexWorksItem):
    def __init__(self, index, data, parent_list, parent=None):
        super().__init__(index, parent_list, parent)
        self.edit_name = RZLineEdit(); self.edit_name.setText(data.name); self.edit_name.editingFinished.connect(self._on_changed); self.header_layout.addWidget(self.edit_name, 1)
        self.cb_blend = RZComboBox(); self.cb_blend.addItems(["LERP", "ADD", "MULTIPLY", "OVERLAY"]); self.cb_blend.currentTextChanged.connect(self._on_changed); self.header_layout.addWidget(self.cb_blend)
        self.w_params = QtWidgets.QWidget(); lp = QtWidgets.QHBoxLayout(self.w_params); lp.setContentsMargins(30,0,0,0); self.spins = []
        for i in range(4): s = RZDoubleSpinBox(); s.setRange(-100, 100); s.setFixedWidth(60); s.valueChanged.connect(self._on_changed); lp.addWidget(s); self.spins.append(s)
        self.main_layout.addWidget(self.w_params); self.update_data(data)
    def _on_changed(self, *args):
        if self.parent_list._block: return
        self.parent_list.item_changed(self.index, "name", self.edit_name.text()); self.parent_list.item_changed(self.index, "diffuse_blend_mode", self.cb_blend.currentText())
        for i, s in enumerate(self.spins): self.parent_list.item_changed(self.index, f"parameters[{i}]", str(s.value()))
    def update_data(self, data): self.edit_name.setText(data.name); self.cb_blend.setCurrentText(data.diffuse_blend_mode); [self.spins[i].setValue(data.parameters[i]) for i in range(4)]

class TexWorksMaterialsTab(RZTexWorksListEditor):
    def update_ui(self):
        if bpy.context.scene: self.sync_widgets(bpy.context.scene.rzm.tw_materials, lambda i, d: TexWorksMaterialItem(i, d, self), lambda w, d: w.update_data(d))
    def add_item(self): bpy.ops.rzm.add_tw_material(); self.update_ui()
    def remove_item(self, index): bpy.ops.rzm.remove_tw_material(index=index); self.update_ui()
    def item_changed(self, index, prop, val): bpy.ops.rzm.update_tw_item(collection_name="materials", index=index, prop_name=prop, value_str=val)

# --- TABS: MAIN BLOCKS HIERARCHY ---

class TexWorksSlotItem(RZTexWorksItem):
    def __init__(self, index, data, parent_list, parent=None):
        super().__init__(index, parent_list, parent)
        self.block_idx = -1; self.comp_idx = -1
        self.cb_active = RZCheckBox("Active"); self.cb_active.toggled.connect(self._on_changed); self.header_layout.insertWidget(1, self.cb_active)
        self.edit_name = RZLineEdit(); self.edit_name.editingFinished.connect(self._on_changed); self.header_layout.addWidget(self.edit_name, 1)
        self.w_trans = QtWidgets.QWidget(); lt = QtWidgets.QHBoxLayout(self.w_trans); lt.setContentsMargins(30,0,0,0); lt.addWidget(RZLabel("Rect:"))
        self.rect_spins = []
        for i in range(4): s = RZSpinBox(); s.setRange(0, 16384); s.setFixedWidth(50); s.valueChanged.connect(self._on_changed); lt.addWidget(s); self.rect_spins.append(s)
        self.main_layout.addWidget(self.w_trans); self.update_data(data, -1, -1)
    def _on_changed(self, *args):
        if self.parent_list._block: return
        p = self.parent_list.item_changed
        p(self.index, "active", str(self.cb_active.isChecked()), self.block_idx, self.comp_idx); p(self.index, "name", self.edit_name.text(), self.block_idx, self.comp_idx)
        for i, s in enumerate(self.rect_spins): p(self.index, f"rect[{i}]", str(s.value()), self.block_idx, self.comp_idx)
    def update_data(self, data, b_idx, c_idx):
        self.block_idx = b_idx; self.comp_idx = c_idx; self.cb_active.setChecked(data.active); self.edit_name.setText(data.name); [s.setValue(data.rect[i]) for i, s in enumerate(self.rect_spins)]

class TexWorksSlotList(RZTexWorksListEditor):
    def __init__(self): super().__init__("+ Slot"); self.block_idx = -1; self.comp_idx = -1
    def update_data(self, slots, b_idx, c_idx): self.block_idx = b_idx; self.comp_idx = c_idx; self.sync_widgets(slots, lambda i, d: TexWorksSlotItem(i, d, self), lambda w, d: w.update_data(d, b_idx, c_idx))
    def add_item(self): bpy.ops.rzm.add_tw_slot(block_index=self.block_idx, comp_index=self.comp_idx); SIGNALS.structure_changed.emit()
    def remove_item(self, index): bpy.ops.rzm.remove_tw_slot(block_index=self.block_idx, comp_index=self.comp_idx, index=index); SIGNALS.structure_changed.emit()
    def item_changed(self, index, prop, val, b_idx, c_idx): bpy.ops.rzm.update_tw_item(collection_name="slots", index=index, prop_name=prop, value_str=val, block_index=b_idx, comp_index=c_idx)

class TexWorksComponentItem(RZTexWorksItem):
    def __init__(self, index, data, parent_list, parent=None):
        super().__init__(index, parent_list, parent); self.block_idx = -1
        self.edit_name = RZLineEdit(); self.edit_name.editingFinished.connect(self._on_changed); self.header_layout.addWidget(self.edit_name, 1)
        self.w_tech = QtWidgets.QWidget(); lf = QtWidgets.QFormLayout(self.w_tech); lf.setContentsMargins(30,0,0,0); self.main_layout.addWidget(self.w_tech)
        self.edit_base = RZLineEdit(); self.edit_base.setPlaceholderText("Base Res"); self.edit_base.editingFinished.connect(self._on_changed); lf.addRow("Base:", self.edit_base)
        self.slot_list = TexWorksSlotList(); self.main_layout.addWidget(self.slot_list); self.update_data(data, -1)
    def _on_changed(self):
        if self.parent_list._block: return
        self.parent_list.item_changed(self.index, "name", self.edit_name.text(), self.block_idx); self.parent_list.item_changed(self.index, "base_resource_name", self.edit_base.text(), self.block_idx)
    def update_data(self, data, b_idx): self.block_idx = b_idx; self.edit_name.setText(data.name); self.edit_base.setText(data.base_resource_name); self.slot_list.update_data(data.slots, b_idx, self.index)

class TexWorksComponentList(RZTexWorksListEditor):
    def __init__(self): super().__init__("+ Component"); self.block_idx = -1
    def update_data(self, comps, b_idx): self.block_idx = b_idx; self.sync_widgets(comps, lambda i, d: TexWorksComponentItem(i, d, self), lambda w, d: w.update_data(d, b_idx))
    def add_item(self): bpy.ops.rzm.add_tw_component(block_index=self.block_idx); SIGNALS.structure_changed.emit()
    def remove_item(self, index): bpy.ops.rzm.remove_tw_component(block_index=self.block_idx, index=index); SIGNALS.structure_changed.emit()
    def item_changed(self, index, prop, val, b_idx): bpy.ops.rzm.update_tw_item(collection_name="components", index=index, prop_name=prop, value_str=val, block_index=b_idx)

class TexWorksBlockItem(RZTexWorksItem):
    def __init__(self, index, data, parent_list, parent=None):
        super().__init__(index, parent_list, parent)
        self.edit_name = RZLineEdit(); self.edit_name.editingFinished.connect(self._on_changed); self.header_layout.addWidget(self.edit_name, 1)
        self.edit_res = RZLineEdit(); self.edit_res.setPlaceholderText("Output Res"); self.edit_res.editingFinished.connect(self._on_changed); self.header_layout.addWidget(self.edit_res, 1)
        self.comp_list = TexWorksComponentList(); self.main_layout.addWidget(self.comp_list); self.update_data(data)
    def _on_changed(self):
        if self.parent_list._block: return
        self.parent_list.item_changed(self.index, "name", self.edit_name.text()); self.parent_list.item_changed(self.index, "resource_name", self.edit_res.text())
    def update_data(self, data): self.edit_name.setText(data.name); self.edit_res.setText(data.resource_name); self.comp_list.update_data(data.components, self.index)

class TexWorksMainTab(RZTexWorksListEditor):
    def __init__(self): super().__init__("+ Add Block")
    def update_ui(self):
        if bpy.context.scene: self.sync_widgets(bpy.context.scene.rzm.tw_blocks, lambda i, d: TexWorksBlockItem(i, d, self), lambda w, d: w.update_data(d))
    def add_item(self): bpy.ops.rzm.add_tw_block(); self.update_ui()
    def remove_item(self, index): bpy.ops.rzm.remove_tw_block(index=index); self.update_ui()
    def item_changed(self, index, prop, val): bpy.ops.rzm.update_tw_item(collection_name="blocks", index=index, prop_name=prop, value_str=val)

# --- MANAGER & PANEL ---

class TexWorksManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.layout.setSpacing(0)
        self.tabs_info = [("Main", "tab_main"), ("Resources", "tab_res"), ("Overrides", "tab_over"), ("Materials", "tab_mat")]
        self.anchor_bar = RZTexWorksAnchorBar(self.tabs_info); self.anchor_bar.clicked.connect(self._on_tab_clicked); self.layout.addWidget(self.anchor_bar)
        self.scroll_area = RZScrollArea(); self.scroll_area.setWidgetResizable(True); self.stack = QtWidgets.QStackedWidget(); self.scroll_area.setWidget(self.stack); self.layout.addWidget(self.scroll_area)
        self.tab_widgets = {"tab_main": TexWorksMainTab(), "tab_res": TexWorksResourcesTab(), "tab_over": TexWorksOverridesTab(), "tab_mat": TexWorksMaterialsTab()}
        for tab_id in ["tab_main", "tab_res", "tab_over", "tab_mat"]: self.stack.addWidget(self.tab_widgets[tab_id])
        self.anchor_bar.set_active("tab_main"); self.stack.setCurrentWidget(self.tab_widgets["tab_main"]); SIGNALS.structure_changed.connect(self.refresh_current)
    def _on_tab_clicked(self, tab_id): self.anchor_bar.set_active(tab_id); self.stack.setCurrentWidget(self.tab_widgets[tab_id]); self.refresh_current()
    def refresh_current(self):
        w = self.stack.currentWidget()
        if hasattr(w, 'update_ui'): w.update_ui()
    def on_activate(self): self.refresh_current()

class RZMTexWorksPanel(RZEditorPanel):
    PANEL_ID = "TEXWORKS"; PANEL_NAME = "TexWorks"; PANEL_ICON = "image"
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.manager = TexWorksManager(); self.layout.addWidget(self.manager)
    def on_activate(self): self.manager.on_activate()
    def update_theme_styles(self): pass
    def enterEvent(self, event): RZContextManager.get_instance().update_input(self.cursor().pos(), (0,0), "TEXWORKS"); super().enterEvent(event)