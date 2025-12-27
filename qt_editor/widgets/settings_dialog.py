# RZMenu/qt_editor/widgets/settings_dialog.py

from PySide6 import QtWidgets, QtCore, QtGui

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, wm, parent=None):
        super().__init__(parent)
        self.wm = wm
        self.setWindowTitle("Preferences")
        self.resize(600, 400)
        self.setModal(True) # Блокирует основное окно

        layout = QtWidgets.QVBoxLayout(self)
        
        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.create_keymap_tab(), "Keymap")
        self.tabs.addTab(self.create_appearance_tab(), "Appearance")
        
        layout.addWidget(self.tabs)
        
        # Bottom Buttons
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def create_keymap_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        table = QtWidgets.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Key Combination", "Operator ID"])
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        
        # Заполняем данными из WM
        keymap_data = self.wm.get_keymap_data()
        table.setRowCount(len(keymap_data))
        
        for i, (key, op_id) in enumerate(keymap_data):
            item_key = QtWidgets.QTableWidgetItem(key)
            item_op = QtWidgets.QTableWidgetItem(op_id)
            
            # Read-only for now
            item_key.setFlags(item_key.flags() ^ QtCore.Qt.ItemIsEditable)
            item_op.setFlags(item_op.flags() ^ QtCore.Qt.ItemIsEditable)
            
            table.setItem(i, 0, item_key)
            table.setItem(i, 1, item_op)
            
        layout.addWidget(table)
        layout.addWidget(QtWidgets.QLabel("Key binding editing coming soon...", alignment=QtCore.Qt.AlignCenter))
        return widget

    def create_appearance_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        label = QtWidgets.QLabel("Appearance Settings Placeholder")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("color: #888; font-size: 14px; font-weight: bold;")
        
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        return widget