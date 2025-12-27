# RZMenu/qt_editor/rz_main_window.py

from PySide6 import QtWidgets, QtCore, QtGui
from .modes.element_mode import ElementMode
from .widgets.inspector import InspectorWidget
from .widgets.hierarchy import HierarchyWidget
from .rz_bridge import RZBridge
from .rz_data_manager import RZDataManager

class ShaderMode(QtWidgets.QLabel): pass
class VariableMode(QtWidgets.QLabel): pass

class RZMainWindow(QtWidgets.QMainWindow):
    def __init__(self, context):
        super().__init__()
        self.bl_context = context
        self.setWindowTitle("RZMenu Architect")
        self.resize(1200, 800)
        
        # 1. Start Bridge & Data Manager
        self.bridge = RZBridge()
        self.bridge.start()
        self.data_manager = RZDataManager(self.bridge)
        
        # --- UI SETUP ---
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        self.root_layout = QtWidgets.QVBoxLayout(main_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        
        # TOP BAR
        self.top_bar = QtWidgets.QFrame()
        self.top_bar.setFixedHeight(40)
        top_layout = QtWidgets.QHBoxLayout(self.top_bar)
        
        self.lbl_title = QtWidgets.QLabel("RZMenu Architect")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #888;")
        self.btn_refresh = QtWidgets.QPushButton("Refresh Data")
        self.btn_refresh.clicked.connect(self.on_refresh)
        
        top_layout.addWidget(self.lbl_title)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_refresh)
        
        # MIDDLE AREA
        middle_widget = QtWidgets.QWidget()
        middle_layout = QtWidgets.QHBoxLayout(middle_widget)
        
        # Hierarchy
        self.hierarchy = HierarchyWidget()
        self.hierarchy.bridge = self.bridge
        self.hierarchy.setFixedWidth(250)
        
        # Stack
        self.stack = QtWidgets.QStackedWidget()
        self.mode_element = ElementMode(context, self.bridge, self.data_manager)
        self.stack.addWidget(self.mode_element)
        self.stack.addWidget(QtWidgets.QLabel("Shader Mode"))
        self.stack.addWidget(QtWidgets.QLabel("Variables"))
        
        # Inspector
        self.inspector = InspectorWidget(self.data_manager)
        self.inspector.setFixedWidth(300)
        
        middle_layout.addWidget(self.hierarchy, 0)
        middle_layout.addWidget(self.stack, 1)
        middle_layout.addWidget(self.inspector, 0)
        
        # BOTTOM BAR
        self.bottom_bar = QtWidgets.QFrame()
        self.bottom_bar.setFixedHeight(35)
        bot_layout = QtWidgets.QHBoxLayout(self.bottom_bar)
        
        self.btn_elem = QtWidgets.QPushButton("Element Mode")
        self.btn_elem.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        bot_layout.addWidget(self.btn_elem)
        bot_layout.addStretch()
        
        self.root_layout.addWidget(self.top_bar)
        self.root_layout.addWidget(middle_widget)
        self.root_layout.addWidget(self.bottom_bar)
        
        # --- CONNECTIONS ---
        
        # 1. Selection
        self.mode_element.element_selected.connect(self.data_manager.set_selection)
        self.hierarchy.element_selected.connect(self.data_manager.set_selection)
        
        self.data_manager.selection_changed.connect(self.inspector.set_selection)
        self.data_manager.selection_changed.connect(self.mode_element.select_item_by_id)
        self.data_manager.selection_changed.connect(self.hierarchy.select_element)

        # 2. Data Changes (Realtime)
        self.data_manager.element_changed.connect(self.inspector.on_element_data_changed)
        self.data_manager.element_changed.connect(self.mode_element.on_data_changed)
        
        # 3. Structure Changes (CRITICAL FIX FOR LOOP)
        # Если Менеджер получил новые данные (от on_refresh), обновляем UI (Иерархию)
        self.data_manager.data_reset.connect(self.on_ui_rebuild)
        
        # Если Блендер сообщил об изменении, запускаем on_refresh
        self.data_manager.external_update_needed.connect(self.on_refresh)

        # Start
        self.on_refresh()

    @QtCore.Slot()
    def changeEvent(self, event):
        """
        Автоматический рефреш данных, когда окно становится активным.
        Это убирает необходимость нажимать кнопку Refresh вручную после правок в Блендере.
        """
        if event.type() == QtCore.QEvent.ActivationChange:
            if self.isActiveWindow():
                # Проверяем, жив ли мост
                if self.bridge:
                    # Можно добавить небольшую задержку или проверку флагов, 
                    # чтобы не спамить, если переключение идет слишком часто.
                    # Но пока прямой вызов безопасен благодаря DataManager.
                    print("Window activated: Auto-syncing...")
                    self.on_refresh()
        
        super().changeEvent(event)

    def on_refresh(self):
        """Запрашивает данные у Блендера."""
        # ElementMode.rebuild_scene() вытащит данные и положит их в DataManager.
        # Это вызовет data_manager.load_initial_data -> data_reset -> on_ui_rebuild
        if hasattr(self.bl_context.scene, "rzm"):
             self.mode_element.rebuild_scene()

    @QtCore.Slot()
    def on_ui_rebuild(self):
        """Перестраивает Иерархию на основе данных в Менеджере."""
        elements = self.data_manager.get_all_elements()
        self.hierarchy.rebuild(elements)

    def closeEvent(self, event):
        if self.bridge:
            self.bridge.stop()
        super().closeEvent(event)