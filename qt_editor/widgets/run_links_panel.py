# RZMenu/qt_editor/widgets/run_links_panel.py
"""
Qt Editor panel for RunLinks (named CommandLists) and Keybinds.

Layout:
  ┌─ RunLinks ─────────────────────────────────────────────────────┐
  │  [List of RunLinks]  ID | Name                                  │
  │  [+ Add] [- Remove] [Import .ini]                               │
  │  ┌─ Properties ──────────────────────────────────────────────┐  │
  │  │ ID: <read-only badge>                                      │  │
  │  │ Name: [______________________]                             │  │
  │  │ Description: [_______________]                             │  │
  │  │ Body:                                                      │  │
  │  │ ┌────────────────────────────────────────────────────┐    │  │
  │  │ │  $var = 0,1,2,3                                     │    │  │
  │  │ │  $other = 1,0,1,0                                   │    │  │
  │  │ └────────────────────────────────────────────────────┘    │  │
  │  └───────────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────────┘
  ┌─ Keybinds ─────────────────────────────────────────────────────┐
  │  [List of Keybinds]  Name | Key | Type                          │
  │  [+ Add] [- Remove] [Import .ini]                               │
  │  ┌─ Properties ──────────────────────────────────────────────┐  │
  │  │ Name / Key / Back / Type / Condition / Run Link ID         │  │
  │  │ [▼ Advanced]  delay / transition / wrap / smart            │  │
  │  └───────────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────────┘
"""

import bpy
from PySide6 import QtWidgets, QtCore, QtGui
from .panel_base import RZEditorPanel
from .lib.theme import get_current_theme
from ..core.signals import SIGNALS


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _styled_label(text: str, bold: bool = False, italic: bool = False) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    font = lbl.font()
    font.setBold(bold)
    font.setItalic(italic)
    lbl.setFont(font)
    return lbl


def _id_badge(id_val: int) -> QtWidgets.QLabel:
    """Small pill-shaped label showing the integer ID."""
    t = get_current_theme()
    badge = QtWidgets.QLabel(f"#{id_val}" if id_val >= 0 else "#?")
    badge.setAlignment(QtCore.Qt.AlignCenter)
    badge.setFixedSize(36, 20)
    badge.setStyleSheet(
        f"background:{t.get('accent','#3a7dc9')}; color:#fff; "
        f"border-radius:4px; font-size:11px; font-weight:bold;"
    )
    return badge


# ─── RunLinks Section ──────────────────────────────────────────────────────────

class RunLinksSection(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._setup_ui()

    def _setup_ui(self):
        t = get_current_theme()
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # Header
        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(_styled_label("Run Links", bold=True))
        hdr.addStretch()
        btn_import = QtWidgets.QPushButton("Import .ini")
        btn_import.setFixedHeight(22)
        btn_import.setToolTip("Import RunLinks from a 3DMigoto .ini file")
        btn_import.clicked.connect(self._import_ini)
        hdr.addWidget(btn_import)
        root.addLayout(hdr)

        # List
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setFixedHeight(120)
        self.list_widget.currentItemChanged.connect(self._on_selection)
        root.addWidget(self.list_widget)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_add    = QtWidgets.QPushButton("+ Add")
        self.btn_remove = QtWidgets.QPushButton("— Remove")
        self.btn_add.clicked.connect(self._add)
        self.btn_remove.clicked.connect(self._remove)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Properties box
        self.props_box = QtWidgets.QGroupBox("Run Link Properties")
        props_layout = QtWidgets.QVBoxLayout(self.props_box)
        props_layout.setContentsMargins(6, 6, 6, 6)
        props_layout.setSpacing(4)

        # ID row (read-only)
        id_row = QtWidgets.QHBoxLayout()
        id_row.addWidget(QtWidgets.QLabel("ID:"))
        self.lbl_id = _id_badge(-1)
        id_row.addWidget(self.lbl_id)
        id_row.addStretch()
        props_layout.addLayout(id_row)

        # Name
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        self.inp_name = QtWidgets.QLineEdit()
        self.inp_name.setPlaceholderText("CommandList name (e.g. MyAction)")
        self.inp_name.editingFinished.connect(self._sync_name)
        form.addRow("Name:", self.inp_name)

        self.inp_desc = QtWidgets.QLineEdit()
        self.inp_desc.setPlaceholderText("Short description (optional)")
        self.inp_desc.editingFinished.connect(self._sync_desc)
        form.addRow("Description:", self.inp_desc)
        props_layout.addLayout(form)

        # Body — multiline QPlainTextEdit
        props_layout.addWidget(QtWidgets.QLabel("Body (CommandList lines):"))
        self.inp_body = QtWidgets.QPlainTextEdit()
        self.inp_body.setPlaceholderText(
            "$var = 0,1,2,3\n$other = 1,0,1,0\n; This will generate body as-is"
        )
        self.inp_body.setMinimumHeight(100)
        font = QtGui.QFont("Consolas", 10)
        self.inp_body.setFont(font)
        self.inp_body.textChanged.connect(self._sync_body)
        props_layout.addWidget(self.inp_body)

        self.props_box.hide()
        root.addWidget(self.props_box)

    # ── Данные ────────────────────────────────────────────────────────────────

    def refresh(self):
        if not bpy.context:
            return
        self._updating = True
        try:
            run_links = list(enumerate(bpy.context.scene.rzm.run_links))
            prev = self._get_current_idx()

            while self.list_widget.count() < len(run_links):
                self.list_widget.addItem("")
            while self.list_widget.count() > len(run_links):
                self.list_widget.takeItem(self.list_widget.count() - 1)

            t = get_current_theme()
            for i, (orig_idx, rl) in enumerate(run_links):
                item = self.list_widget.item(i)
                item.setData(QtCore.Qt.UserRole, orig_idx)
                label = f"#{rl.id if rl.id >= 0 else '?'}  {rl.name}"
                if item.text() != label:
                    item.setText(label)
                item.setFlags(
                    QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                )

            # Restore selection
            if prev is not None:
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).data(QtCore.Qt.UserRole) == prev:
                        self.list_widget.setCurrentRow(i)
                        break
        finally:
            self._updating = False

    def _get_current_idx(self):
        item = self.list_widget.currentItem()
        return item.data(QtCore.Qt.UserRole) if item else None

    def _on_selection(self, current, _prev):
        if current is None:
            self.props_box.hide()
            return
        orig_idx = current.data(QtCore.Qt.UserRole)
        self._update_props(orig_idx)

    def _update_props(self, orig_idx: int):
        rl = bpy.context.scene.rzm.run_links[orig_idx]
        self._updating = True
        try:
            # Update ID badge
            self.lbl_id.setText(f"#{rl.id}" if rl.id >= 0 else "#?")
            if self.inp_name.text() != rl.name:
                self.inp_name.setText(rl.name)
            if self.inp_desc.text() != rl.description:
                self.inp_desc.setText(rl.description)
            # Body — use setPlainText only if changed to avoid cursor jump
            body_text = rl.body
            if self.inp_body.toPlainText() != body_text:
                self.inp_body.setPlainText(body_text)
        finally:
            self._updating = False
        self.props_box.show()

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _sync_name(self):
        if self._updating:
            return
        idx = self._get_current_idx()
        if idx is None:
            return
        bpy.context.scene.rzm.run_links[idx].name = self.inp_name.text()
        self.refresh()

    def _sync_desc(self):
        if self._updating:
            return
        idx = self._get_current_idx()
        if idx is None:
            return
        bpy.context.scene.rzm.run_links[idx].description = self.inp_desc.text()

    def _sync_body(self):
        if self._updating:
            return
        idx = self._get_current_idx()
        if idx is None:
            return
        bpy.context.scene.rzm.run_links[idx].body = self.inp_body.toPlainText()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add(self):
        rzm = bpy.context.scene.rzm
        # Assign next ID
        next_id = max((rl.id for rl in rzm.run_links if rl.id >= 0), default=0) + 1
        nrl = rzm.run_links.add()
        nrl.id   = next_id
        nrl.name = f"NewAction_{next_id}"
        self.refresh()
        # Select new item
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def _remove(self):
        idx = self._get_current_idx()
        if idx is None:
            return
        bpy.context.scene.rzm.run_links.remove(idx)
        self.refresh()

    def _import_ini(self):
        bpy.ops.rzm.import_ini('INVOKE_DEFAULT')


# ─── Keybinds Section ─────────────────────────────────────────────────────────

class KeybindsSection(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._setup_ui()

    def _setup_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # Header
        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(_styled_label("Keybinds", bold=True))
        hdr.addStretch()
        root.addLayout(hdr)

        # List
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setFixedHeight(130)
        self.list_widget.currentItemChanged.connect(self._on_selection)
        root.addWidget(self.list_widget)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_add    = QtWidgets.QPushButton("+ Add")
        self.btn_remove = QtWidgets.QPushButton("— Remove")
        btn_import      = QtWidgets.QPushButton("Import .ini")
        self.btn_add.clicked.connect(self._add)
        self.btn_remove.clicked.connect(self._remove)
        btn_import.clicked.connect(lambda: bpy.ops.rzm.import_ini('INVOKE_DEFAULT'))
        btn_import.setFixedHeight(22)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()
        btn_row.addWidget(btn_import)
        root.addLayout(btn_row)

        # Properties
        self.props_box = QtWidgets.QGroupBox("Keybind Properties")
        pl = QtWidgets.QVBoxLayout(self.props_box)
        pl.setContentsMargins(6, 6, 6, 6)
        pl.setSpacing(4)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)

        self.inp_name  = QtWidgets.QLineEdit()
        self.inp_key   = QtWidgets.QLineEdit()
        self.inp_back  = QtWidgets.QLineEdit()
        self.inp_type  = QtWidgets.QComboBox()
        self.inp_type.addItems(['cycle', 'toggle', 'hold', 'down', 'up'])
        self.inp_only_menu = QtWidgets.QCheckBox("Require $active == 1")
        self.inp_cond  = QtWidgets.QLineEdit()
        self.inp_run   = QtWidgets.QComboBox()
        self.inp_run.setEditable(True)
        self.inp_run.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.inp_run.setPlaceholderText("(none / type RunLink name)")

        self.inp_name.editingFinished.connect(lambda: self._sync('name', self.inp_name.text()))
        self.inp_key.editingFinished.connect(lambda: self._sync('key', self.inp_key.text()))
        self.inp_back.editingFinished.connect(lambda: self._sync('back', self.inp_back.text()))
        self.inp_type.currentTextChanged.connect(lambda t: self._sync('type', t))
        self.inp_only_menu.toggled.connect(lambda v: self._sync('only_menu_active', str(v)))
        self.inp_cond.editingFinished.connect(lambda: self._sync('condition', self.inp_cond.text()))
        self.inp_run.currentTextChanged.connect(lambda t: self._sync('run_id', t))

        form.addRow("Name:", self.inp_name)
        form.addRow("Key:", self.inp_key)
        form.addRow("Back:", self.inp_back)
        form.addRow("Type:", self.inp_type)
        form.addRow("Condition:", self.inp_only_menu)
        form.addRow("Custom Cond:", self.inp_cond)
        form.addRow("Run Link:", self.inp_run)
        pl.addLayout(form)

        # Advanced (collapsible)
        adv_btn = QtWidgets.QToolButton()
        adv_btn.setText("▶  Advanced (3DMigoto)")
        adv_btn.setCheckable(True)
        adv_btn.setChecked(False)
        adv_btn.setStyleSheet("border:none; font-weight:bold;")
        adv_btn.setArrowType(QtCore.Qt.RightArrow)
        pl.addWidget(adv_btn)

        self.adv_widget = QtWidgets.QWidget()
        adv_form = QtWidgets.QFormLayout(self.adv_widget)
        adv_form.setLabelAlignment(QtCore.Qt.AlignRight)

        self.inp_delay    = QtWidgets.QSpinBox()
        self.inp_delay.setRange(0, 9999)
        self.inp_r_delay  = QtWidgets.QSpinBox()
        self.inp_r_delay.setRange(0, 9999)
        self.inp_wrap     = QtWidgets.QCheckBox()
        self.inp_smart    = QtWidgets.QCheckBox()
        self.inp_trans    = QtWidgets.QSpinBox()
        self.inp_trans.setRange(0, 9999)
        self.inp_trans_t  = QtWidgets.QLineEdit()

        self.inp_delay.valueChanged.connect(lambda v: self._sync('delay', str(v)))
        self.inp_r_delay.valueChanged.connect(lambda v: self._sync('release_delay', str(v)))
        self.inp_wrap.toggled.connect(lambda v: self._sync('wrap', str(v)))
        self.inp_smart.toggled.connect(lambda v: self._sync('smart', str(v)))
        self.inp_trans.valueChanged.connect(lambda v: self._sync('transition', str(v)))
        self.inp_trans_t.editingFinished.connect(lambda: self._sync('transition_type', self.inp_trans_t.text()))

        adv_form.addRow("Delay (ms):", self.inp_delay)
        adv_form.addRow("Release Delay:", self.inp_r_delay)
        adv_form.addRow("Wrap:", self.inp_wrap)
        adv_form.addRow("Smart:", self.inp_smart)
        adv_form.addRow("Transition:", self.inp_trans)
        adv_form.addRow("Trans. Type:", self.inp_trans_t)

        self.adv_widget.setVisible(False)
        pl.addWidget(self.adv_widget)

        def _toggle_adv(checked):
            self.adv_widget.setVisible(checked)
            adv_btn.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)

        adv_btn.toggled.connect(_toggle_adv)

        self.props_box.hide()
        root.addWidget(self.props_box)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        if not bpy.context:
            return
        self._updating = True
        try:
            keybinds = list(enumerate(bpy.context.scene.rzm.keybinds))
            prev = self._get_current_idx()

            while self.list_widget.count() < len(keybinds):
                self.list_widget.addItem("")
            while self.list_widget.count() > len(keybinds):
                self.list_widget.takeItem(self.list_widget.count() - 1)

            for i, (orig_idx, kb) in enumerate(keybinds):
                item = self.list_widget.item(i)
                item.setData(QtCore.Qt.UserRole, orig_idx)
                label = f"{kb.name}  [{kb.key[:16] if kb.key else '—'}]  {kb.type}"
                if item.text() != label:
                    item.setText(label)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)

            if prev is not None:
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).data(QtCore.Qt.UserRole) == prev:
                        self.list_widget.setCurrentRow(i)
                        break

            # Refresh RunLink dropdown
            self._refresh_run_link_combo()
        finally:
            self._updating = False

    def _refresh_run_link_combo(self):
        """Populate Run Link combo with names of all existing RunLinks."""
        self.inp_run.blockSignals(True)
        current_text = self.inp_run.currentText()
        self.inp_run.clear()
        self.inp_run.addItem("")  # empty = no RunLink
        rzm = bpy.context.scene.rzm
        for rl in rzm.run_links:
            self.inp_run.addItem(f"#{rl.id}  {rl.name}", userData=rl.name)
        # Try to restore
        idx = self.inp_run.findText(current_text)
        if idx >= 0:
            self.inp_run.setCurrentIndex(idx)
        self.inp_run.blockSignals(False)

    def _get_current_idx(self):
        item = self.list_widget.currentItem()
        return item.data(QtCore.Qt.UserRole) if item else None

    def _on_selection(self, current, _prev):
        if current is None:
            self.props_box.hide()
            return
        orig_idx = current.data(QtCore.Qt.UserRole)
        self._update_props(orig_idx)

    def _update_props(self, orig_idx: int):
        kb = bpy.context.scene.rzm.keybinds[orig_idx]
        self._updating = True
        try:
            self.inp_name.setText(kb.name)
            self.inp_key.setText(kb.key)
            self.inp_back.setText(kb.back)
            idx_t = self.inp_type.findText(kb.type)
            if idx_t >= 0:
                self.inp_type.setCurrentIndex(idx_t)
            self.inp_only_menu.setChecked(kb.only_menu_active)
            self.inp_cond.setText(kb.condition)

            # Run link
            self._refresh_run_link_combo()
            # Find matching item by run_id name
            found = False
            for i in range(self.inp_run.count()):
                if self.inp_run.itemData(i) == kb.run_id or self.inp_run.itemText(i).endswith(kb.run_id):
                    self.inp_run.setCurrentIndex(i)
                    found = True
                    break
            if not found:
                self.inp_run.setCurrentText(kb.run_id)

            # Advanced
            self.inp_delay.setValue(getattr(kb, 'delay', 0))
            self.inp_r_delay.setValue(getattr(kb, 'release_delay', 0))
            self.inp_wrap.setChecked(getattr(kb, 'wrap', False))
            self.inp_smart.setChecked(getattr(kb, 'smart', False))
            self.inp_trans.setValue(getattr(kb, 'transition', 0))
            self.inp_trans_t.setText(getattr(kb, 'transition_type', ''))
        finally:
            self._updating = False
        self.props_box.show()

    def _sync(self, prop: str, val: str):
        if self._updating:
            return
        idx = self._get_current_idx()
        if idx is None:
            return
        kb = bpy.context.scene.rzm.keybinds[idx]
        try:
            attr = getattr(kb, prop)
        except AttributeError:
            return
        if isinstance(attr, bool):
            setattr(kb, prop, val.lower() in ('true', '1'))
        elif isinstance(attr, int):
            try:
                setattr(kb, prop, int(float(val)))
            except ValueError:
                pass
        else:
            setattr(kb, prop, val)
        if prop == 'name':
            self.refresh()

    def _add(self):
        rzm = bpy.context.scene.rzm
        nk = rzm.keybinds.add()
        nk.name = "NewKeybind"
        nk.type = "cycle"
        self.refresh()
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def _remove(self):
        idx = self._get_current_idx()
        if idx is None:
            return
        bpy.context.scene.rzm.keybinds.remove(idx)
        self.refresh()


# ─── Combined Panel ───────────────────────────────────────────────────────────

class RZRunLinksManager(QtWidgets.QWidget):
    """
    Main widget shown in the Qt Editor Run Links panel.
    Two collapsible sections: RunLinks and Keybinds.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = QtWidgets.QVBoxLayout(self)
        self._root.setContentsMargins(4, 4, 4, 4)
        self._root.setSpacing(8)

        self._run_section = RunLinksSection()
        self._kb_section  = KeybindsSection()

        # Thin separators between sections
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)

        self._root.addWidget(self._run_section)
        self._root.addWidget(sep)
        self._root.addWidget(self._kb_section)
        self._root.addStretch()

        self.apply_theme()

    def apply_theme(self):
        t = get_current_theme()
        self.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {t['border_main']};
                border-radius: 4px;
                margin-top: 8px;
                padding: 4px;
                color: {t['text_main']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                color: {t.get('accent', '#5298D4')};
                font-weight: bold;
            }}
            QListWidget {{
                background: {t['bg_input']};
                color: {t['text_main']};
                border: 1px solid {t['border_input']};
                border-radius: 3px;
            }}
            QListWidget::item:selected {{
                background: {t.get('accent', '#1a6ea8')};
                color: #fff;
            }}
            QPushButton {{
                background: {t['bg_header']};
                color: {t['text_main']};
                border: 1px solid {t['border_main']};
                border-radius: 3px;
                padding: 3px 8px;
                min-height: 22px;
            }}
            QPushButton:hover {{ background: {t.get('accent', '#1e5c99')}; color: #fff; }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background: {t['bg_input']};
                color: {t['text_main']};
                border: 1px solid {t['border_input']};
                border-radius: 3px;
                padding: 2px 4px;
            }}
            QPlainTextEdit {{
                background: {t['bg_input']};
                color: {t['text_main']};
                border: 1px solid {t['border_input']};
                border-radius: 3px;
                font-family: Consolas, monospace;
            }}
            QLabel {{ color: {t['text_main']}; }}
        """)

    def on_activate(self):
        self._run_section.refresh()
        self._kb_section.refresh()
