# RZMenu/qt_editor/rz_main_window.py

from PySide6 import QtWidgets, QtCore, QtGui
from .widgets.inspector import InspectorWidget
from .widgets.hierarchy import HierarchyWidget
from .widgets.settings_dialog import SettingsDialog # Импорт нового диалога
from .rz_bridge import RZBridge
from .rz_data_manager import RZDataManager
from .modes.element_mode import ElementMode
from .core.wm import WindowManager
from .core.context import RZContext
from .ops import element_ops, window_ops

# --- CUSTOM HEADER ---
class RZHeader(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34) # Чуть выше стандартного
        self.setStyleSheet("""
            RZHeader { background-color: #2d2d2d; border-bottom: 1px solid #111; }
            QLabel { color: #ccc; font-weight: bold; padding: 0 10px; }
            QPushButton { 
                background: transparent; border: none; color: #aaa; 
                padding: 4px 10px; border-radius: 3px;
            }
            QPushButton:hover { background-color: #3d3d3d; color: white; }
        """)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        
        # Left: Future File/Edit menu placeholder
        self.btn_file = QtWidgets.QPushButton("File")
        self.btn_file.setEnabled(False) # Reserved
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_edit.setEnabled(False) # Reserved
        
        layout.addWidget(self.btn_file)
        layout.addWidget(self.btn_edit)
        
        layout.addStretch() # Spacer
        
        # Right: Settings & Actions
        self.btn_refresh = QtWidgets.QPushButton("Refresh Data")
        self.btn_refresh.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_refresh.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        
        self.btn_settings = QtWidgets.QPushButton("Settings")
        self.btn_settings.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_settings.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))
        
        layout.addWidget(self.btn_refresh)
        layout.addWidget(self.btn_settings)

# --- CUSTOM FOOTER ---
class RZFooter(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32) # Locked height
        self.setStyleSheet("""
            RZFooter { background-color: #222; border-top: 1px solid #111; }
            QLabel { color: #888; font-size: 11px; padding: 0 10px; }
            /* Separators */
            QLabel#Sep { border-right: 1px solid #333; padding: 0; margin: 4px 0; }
        """)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Left: Context Hints
        self.lbl_context = QtWidgets.QLabel("LMB: Select | MMB: Pan")
        self.lbl_context.setMinimumWidth(200)
        
        # Center: Last Action
        self.lbl_action = QtWidgets.QLabel("Ready")
        self.lbl_action.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_action.setStyleSheet("color: #ccc; font-weight: bold;")
        
        # Right: Version
        self.lbl_version = QtWidgets.QLabel("RZM v3.1 alpha")
        self.lbl_version.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        # Vertical Separators for style
        sep1 = QtWidgets.QLabel(); sep1.setObjectName("Sep"); sep1.setFixedWidth(1)
        sep2 = QtWidgets.QLabel(); sep2.setObjectName("Sep"); sep2.setFixedWidth(1)

        layout.addWidget(self.lbl_context)
        layout.addWidget(sep1)
        layout.addWidget(self.lbl_action, 1) # Stretch factor 1 makes it take available space
        layout.addWidget(sep2)
        layout.addWidget(self.lbl_version)

    def set_last_action(self, text):
        self.lbl_action.setText(text)


class RZMainWindow(QtWidgets.QMainWindow):
    def __init__(self, context):
        super().__init__()
        self.bl_context = context
        self.setWindowTitle("RZM Editor")
        self.resize(1400, 900)
        
        # --- Infrastructure ---
        self.bridge = RZBridge()
        self.bridge.start()
        self.data_manager = RZDataManager(self.bridge)
        self.rz_context = RZContext(self, self.bridge, self.data_manager)
        self.wm = WindowManager(self.rz_context)
        element_ops.register(self.wm)
        window_ops.register(self.wm)
        # Загрузка хоткеев (ПОСЛЕ регистрации операторов)
        self.wm.load_keymap()

        self.setDockOptions(
            QtWidgets.QMainWindow.AllowNestedDocks | 
            QtWidgets.QMainWindow.AllowTabbedDocks |
            QtWidgets.QMainWindow.AnimatedDocks
        )

        # --- Viewport ---
        self.mode_element = ElementMode(context, self.bridge, self.data_manager)
        self.setCentralWidget(self.mode_element)

        # --- Header & Footer (Professional Look) ---
        self.create_pro_interface()
        
        # --- Docks ---
        self.create_docks()
        self.connect_signals()
        
        # Start
        self.on_refresh()

    def create_pro_interface(self):
        # 1. Header (Menu Widget)
        self.header = RZHeader(self)
        self.setMenuWidget(self.header)
        
        self.header.btn_refresh.clicked.connect(lambda: self.wm.run("wm.refresh_data"))
        self.header.btn_settings.clicked.connect(self.open_settings)

        # 2. Footer (Status Bar Fix)
        self.footer = RZFooter(self)
        
        # Создаем настоящий QStatusBar
        actual_statusbar = QtWidgets.QStatusBar()
        
        # Убираем стандартные отступы и рамки QStatusBar
        actual_statusbar.setContentsMargins(0, 0, 0, 0)
        actual_statusbar.setStyleSheet("QStatusBar::item {border: none; background: transparent;}")
        actual_statusbar.setSizeGripEnabled(False) # Убираем треугольник ресайза справа
        
        # Добавляем наш RZFooter внутрь как виджет, который растягивается (stretch=1)
        actual_statusbar.addWidget(self.footer, 1)
        
        # Теперь тип совпадает
        self.setStatusBar(actual_statusbar)

    def create_docks(self):
        # Hierarchy
        self.dock_hierarchy = QtWidgets.QDockWidget("Hierarchy", self)
        self.dock_hierarchy.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.dock_hierarchy.setObjectName("DockHierarchy")
        self.hierarchy_widget = HierarchyWidget()
        self.hierarchy_widget.bridge = self.bridge
        self.dock_hierarchy.setWidget(self.hierarchy_widget)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dock_hierarchy)

        # Inspector
        self.dock_inspector = QtWidgets.QDockWidget("Properties", self)
        self.dock_inspector.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.dock_inspector.setObjectName("DockInspector")
        self.inspector_widget = InspectorWidget(self.data_manager)
        self.dock_inspector.setWidget(self.inspector_widget)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_inspector)

    def connect_signals(self):
        # ... (существующие сигналы) ...
        self.mode_element.element_selected.connect(self.data_manager.set_selection)
        self.hierarchy_widget.element_selected.connect(self.data_manager.set_selection)
        self.data_manager.selection_changed.connect(self.inspector_widget.set_selection)
        self.data_manager.selection_changed.connect(self.mode_element.select_item_by_id)
        self.data_manager.selection_changed.connect(self.hierarchy_widget.select_element)
        self.data_manager.element_changed.connect(self.inspector_widget.on_element_data_changed)
        self.data_manager.element_changed.connect(self.mode_element.on_data_changed)
        self.data_manager.data_reset.connect(self.on_ui_rebuild)
        self.data_manager.external_update_needed.connect(self.on_refresh)
        
        # --- НОВОЕ: Связь WM -> Footer ---
        # Когда оператор выполнен, обновляем текст в футере
        self.wm.operator_executed.connect(self.on_operator_executed)

    def on_operator_executed(self, op_id, op_label):
        # Обновляем текст в центре футера
        self.footer.set_last_action(f"Done: {op_label}")
        
        # Можно добавить таймер, чтобы сбрасывать текст через 3 секунды, но пока пусть висит
        # QtCore.QTimer.singleShot(3000, lambda: self.footer.set_last_action("Ready"))

    def open_settings(self):
        dlg = SettingsDialog(self.wm, self)
        dlg.exec()

    @QtCore.Slot()
    def on_refresh(self):
        if hasattr(self.bl_context.scene, "rzm"):
             self.mode_element.rebuild_scene()

    @QtCore.Slot()
    def on_ui_rebuild(self):
        elements = self.data_manager.get_all_elements()
        self.hierarchy_widget.rebuild(elements)

    def closeEvent(self, event):
        if self.bridge:
            self.bridge.stop()
        super().closeEvent(event)