# RZMenu/qt_editor/widgets/localization_manager.py
import bpy
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.theme import get_current_theme
from .lib.widgets import RZPanelWidget
from ..core import signals, props, read
from .panel_base import RZEditorPanel

class RZMLocalizationPanel(RZEditorPanel):
    """
    Panel for managing all localized strings in the project.
    Provides two views:
    1. Element Mapping: Assign keys to UI elements.
    2. Project Database: Manage translations for all project languages.
    """
    PANEL_ID = "LOCALIZATION"
    PANEL_NAME = "Localization Manager"
    PANEL_ICON = "translate"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RZMLocalizationPanel")
        
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(6)
        
        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # --- TAB 1: ELEMENT MAPPING ---
        self.tab_mapping = QtWidgets.QWidget()
        self.mapping_layout = QtWidgets.QVBoxLayout(self.tab_mapping)
        self.mapping_layout.setContentsMargins(4, 4, 4, 4)
        
        # Toolbar for Mapping
        self.toolbar_map = QtWidgets.QHBoxLayout()
        self.search_map = QtWidgets.QLineEdit()
        self.search_map.setPlaceholderText("Filter elements...")
        self.search_map.textChanged.connect(self.refresh_mapping)
        self.toolbar_map.addWidget(self.search_map)
        
        self.btn_auto_prefix = QtWidgets.QPushButton("Auto Prefix")
        self.btn_auto_prefix.clicked.connect(self.auto_prefix_keys)
        self.toolbar_map.addWidget(self.btn_auto_prefix)
        
        self.mapping_layout.addLayout(self.toolbar_map)
        
        self.table_map = QtWidgets.QTableWidget(0, 5)
        self.table_map.setHorizontalHeaderLabels(["ID", "Element Name", "Type", "Text Content", "Loc Key"])
        self.table_map.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.table_map.itemChanged.connect(self.on_mapping_item_changed)
        self.mapping_layout.addWidget(self.table_map)
        
        self.tabs.addTab(self.tab_mapping, "Element Mapping")
        
        # --- TAB 2: PROJECT DATABASE ---
        self.tab_db = QtWidgets.QWidget()
        self.db_layout = QtWidgets.QVBoxLayout(self.tab_db)
        self.db_layout.setContentsMargins(4, 4, 4, 4)
        
        # Toolbar for DB
        self.toolbar_db = QtWidgets.QHBoxLayout()
        
        self.btn_add_key = QtWidgets.QPushButton("Add Key")
        self.btn_add_key.clicked.connect(self.add_key_to_db)
        self.toolbar_db.addWidget(self.btn_add_key)
        
        self.btn_remove_key = QtWidgets.QPushButton("Remove Selected")
        self.btn_remove_key.clicked.connect(self.remove_key_from_db)
        self.toolbar_db.addWidget(self.btn_remove_key)
        
        self.toolbar_db.addStretch()
        
        self.btn_sync = QtWidgets.QPushButton("Sync from Project")
        self.btn_sync.setToolTip("Harvest all loc_keys used in elements and add them to the database")
        self.btn_sync.clicked.connect(self.sync_keys)
        self.toolbar_db.addWidget(self.btn_sync)
        
        self.db_layout.addLayout(self.toolbar_db)
        
        self.table_db = QtWidgets.QTableWidget(0, 2)
        self.table_db.setHorizontalHeaderLabels(["Loc Key", "Translations"])
        self.table_db.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table_db.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table_db.itemChanged.connect(self.on_db_item_changed)
        self.db_layout.addWidget(self.table_db)
        
        self.tabs.addTab(self.tab_db, "Project Localization DB")
        
        self._block_signals = False
        self.apply_theme()
        
    def refresh(self):
        self.refresh_mapping()
        self.refresh_db()

    def refresh_mapping(self):
        self._block_signals = True
        self.table_map.setRowCount(0)
        data = read.get_all_localized_texts()
        search = self.search_map.text().lower()
        
        filtered = [e for e in data if not search or search in e['name'].lower() or search in e['text'].lower() or search in e['loc_key'].lower()]
        
        self.table_map.setRowCount(len(filtered))
        for row, entry in enumerate(filtered):
            id_item = QtWidgets.QTableWidgetItem(str(entry['element_id']))
            id_item.setFlags(id_item.flags() & ~QtCore.Qt.ItemIsEditable)
            id_item.setData(QtCore.Qt.UserRole, entry)
            self.table_map.setItem(row, 0, id_item)
            
            self.table_map.setItem(row, 1, QtWidgets.QTableWidgetItem(entry['name']))
            self.table_map.setItem(row, 2, QtWidgets.QTableWidgetItem(entry['type']))
            self.table_map.setItem(row, 3, QtWidgets.QTableWidgetItem(entry['text']))
            
            key_text = entry['loc_key'] if entry['loc_key'] else "[No Key]"
            key_item = QtWidgets.QTableWidgetItem(key_text)
            if not entry['loc_key']: key_item.setForeground(QtGui.QBrush(QtGui.QColor("#888")))
            self.table_map.setItem(row, 4, key_item)
            
        self._block_signals = False

    def on_mapping_item_changed(self, item):
        if self._block_signals or item.column() != 4: return
        entry = self.table_map.item(item.row(), 0).data(QtCore.Qt.UserRole)
        new_key = item.text().strip()
        if new_key == "[No Key]": new_key = ""
        
        if entry['type'] in ['SINGLE', 'HOVER']:
            props.update_property_multi([entry['element_id']], entry['prop_name'], new_key)
        else:
            props.update_conditional_text([entry['element_id']], entry['prop_index'], entry['sub_prop'], new_key)
        self.refresh_mapping()

    def refresh_db(self):
        self._block_signals = True
        self.table_db.setRowCount(0)
        rzm = bpy.context.scene.rzm
        db = rzm.loc_database
        langs = rzm.languages
        
        # Columns: Key, then one column per language
        self.table_db.setColumnCount(1 + len(langs))
        headers = ["Loc Key"] + [l.name for l in langs]
        self.table_db.setHorizontalHeaderLabels(headers)
        
        self.table_db.setRowCount(len(db))
        for row, key_entry in enumerate(db):
            key_item = QtWidgets.QTableWidgetItem(key_entry.name)
            key_item.setData(QtCore.Qt.UserRole, key_entry.name) # Store original name
            self.table_db.setItem(row, 0, key_item)
            
            # Map translations for each language
            trans_dict = {t.lang_id: t.text for t in key_entry.translations}
            for col, lang in enumerate(langs, 1):
                text = trans_dict.get(lang.lang_id, "")
                t_item = QtWidgets.QTableWidgetItem(text)
                t_item.setData(QtCore.Qt.UserRole, (key_entry.name, lang.lang_id))
                self.table_db.setItem(row, col, t_item)
                
        self._block_signals = False

    def on_db_item_changed(self, item):
        if self._block_signals: return
        self._block_signals = True
        
        rzm = bpy.context.scene.rzm
        row = item.row()
        col = item.column()
        new_val = item.text().strip()
        
        if col == 0: # Rename Key
            old_name = item.data(QtCore.Qt.UserRole)
            if old_name != new_val:
                key_entry = next((k for k in rzm.loc_database if k.name == old_name), None)
                if key_entry: key_entry.name = new_val
        else: # Update Translation
            key_name, lang_id = item.data(QtCore.Qt.UserRole)
            key_entry = next((k for k in rzm.loc_database if k.name == key_name), None)
            if key_entry:
                trans = next((t for t in key_entry.translations if t.lang_id == lang_id), None)
                if not trans:
                    trans = key_entry.translations.add()
                    trans.lang_id = lang_id
                trans.text = new_val
                
        self._block_signals = False
        # self.refresh_db() # Don't refresh immediately to avoid losing focus if editing sequentially

    def add_key_to_db(self):
        new_key, ok = QtWidgets.QInputDialog.getText(self, "Add Key", "Unique Key Name (e.g. L_MY_LABEL):")
        if ok and new_key:
            db = bpy.context.scene.rzm.loc_database
            if any(k.name == new_key for k in db):
                QtWidgets.QMessageBox.warning(self, "Error", "Key already exists!")
                return
            entry = db.add()
            entry.name = new_key
            self.refresh_db()

    def remove_key_from_db(self):
        idx = self.table_db.currentRow()
        if idx < 0: return
        key_name = self.table_db.item(idx, 0).text()
        if QtWidgets.QMessageBox.question(self, "Remove Key", f"Delete key '{key_name}' and all its translations?") == QtWidgets.QMessageBox.Yes:
            db = bpy.context.scene.rzm.loc_database
            for i, k in enumerate(db):
                if k.name == key_name:
                    db.remove(i)
                    break
            self.refresh_db()

    def sync_keys(self):
        """Harvest keys used in elements and add missing ones to the database."""
        data = read.get_all_localized_texts()
        db = bpy.context.scene.rzm.loc_database
        existing_keys = {k.name for k in db}
        new_count = 0
        for entry in data:
            k = entry['loc_key']
            if k and k not in existing_keys:
                new_key = db.add()
                new_key.name = k
                existing_keys.add(k)
                new_count += 1
        if new_count > 0:
            QtWidgets.QMessageBox.information(self, "Sync Complete", f"Added {new_count} new keys from project elements.")
            self.refresh_db()

    def auto_prefix_keys(self):
        self._block_signals = True
        for row in range(self.table_map.rowCount()):
            id_item = self.table_map.item(row, 0)
            entry = id_item.data(QtCore.Qt.UserRole)
            if entry['loc_key']: continue
            new_key = f"L_{entry['name'].upper().replace(' ', '_')}_{entry['type'].split(' ')[0]}"
            if entry['type'] in ['SINGLE', 'HOVER']:
                props.update_property_multi([entry['element_id']], entry['prop_name'], new_key)
            else:
                props.update_conditional_text([entry['element_id']], entry['prop_index'], entry['sub_prop'], new_key)
        self._block_signals = False
        self.refresh_mapping()

    def apply_theme(self):
        if not hasattr(self, 'table_map'): return
        t = get_current_theme()
        style = f"""
            QWidget {{ background-color: {t['bg_panel']}; color: {t['text_main']}; }}
            QTableWidget {{ background-color: {t['bg_input']}; gridline-color: {t['border_main']}; color: {t['text_main']}; }}
            QHeaderView::section {{ background-color: {t['bg_header']}; color: {t['text_main']}; border: 1px solid {t['border_main']}; padding: 4px; }}
            QTabWidget::pane {{ border: 1px solid {t['border_main']}; }}
            QTabBar::tab {{ background: {t['bg_header']}; border: 1px solid {t['border_main']}; padding: 6px 12px; }}
            QTabBar::tab:selected {{ background: {t['accent']}; color: white; }}
        """
        self.setStyleSheet(style)

    def _connect_signals(self): signals.SIGNALS.data_changed.connect(self.refresh)
    def _disconnect_signals(self):
        try: signals.SIGNALS.data_changed.disconnect(self.refresh)
        except: pass
