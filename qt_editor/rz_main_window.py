from PySide6 import QtWidgets, QtCore, QtGui
from .modes.element_mode import ElementMode
from .widgets.inspector import InspectorWidget
from .rz_bridge import RZBridge

# Заглушки для будущих режимов
class ShaderMode(QtWidgets.QLabel): pass
class VariableMode(QtWidgets.QLabel): pass

class RZMainWindow(QtWidgets.QMainWindow):
    def __init__(self, context):
        super().__init__()
        self.bl_context = context
        self.setWindowTitle("RZMenu Architect")
        self.resize(1200, 800)
        
        # 1. Запускаем Мост (Bridge)
        # Он должен жить столько же, сколько окно
        self.bridge = RZBridge()
        self.bridge.start()
        
        # --- CENTRAL WIDGET ---
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        
        # Корневой Layout (Вертикальный): Шапка -> Рабочая зона -> Подвал
        self.root_layout = QtWidgets.QVBoxLayout(main_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        
        # ===========================
        # 1. HEADER (Top Bar)
        # ===========================
        self.top_bar = QtWidgets.QFrame()
        self.top_bar.setObjectName("TopBar")
        self.top_bar.setFixedHeight(40)
        top_layout = QtWidgets.QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(10, 0, 10, 0)
        
        self.lbl_title = QtWidgets.QLabel("RZMenu Architect")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #888; font-size: 14px;")
        
        self.btn_refresh = QtWidgets.QPushButton("Refresh Data")
        self.btn_refresh.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.on_refresh)
        
        top_layout.addWidget(self.lbl_title)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_refresh)
        
        # ===========================
        # 2. MIDDLE AREA (Horizontal)
        # Здесь живут Stack (Канвас) и Inspector
        # ===========================
        middle_widget = QtWidgets.QWidget()
        middle_layout = QtWidgets.QHBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        
        # A. Stack (Слева, растягивается)
        self.stack = QtWidgets.QStackedWidget()
        
        # Создаем режимы (Передаем bridge в ElementMode!)
        self.mode_element = ElementMode(context, self.bridge)
        
        self.mode_shader = ShaderMode("Shader Mode (Coming Soon)")
        self.mode_shader.setAlignment(QtCore.Qt.AlignCenter)
        self.mode_var = VariableMode("Variable Mode (Coming Soon)")
        self.mode_var.setAlignment(QtCore.Qt.AlignCenter)
        
        self.stack.addWidget(self.mode_element)
        self.stack.addWidget(self.mode_shader)
        self.stack.addWidget(self.mode_var)
        
        # B. Inspector (Справа, фиксированный)
        self.inspector = InspectorWidget(self.bridge)
        self.inspector.setFixedWidth(300)
        # Добавляем стиль для границы слева
        self.inspector.setStyleSheet("background-color: #222; border-left: 1px solid #3d3d3d;")
        
        # Добавляем в среднюю зону
        middle_layout.addWidget(self.stack, 1) # stretch=1
        middle_layout.addWidget(self.inspector, 0) # stretch=0 (fixed)
        
        # ===========================
        # 3. FOOTER (Bottom Bar)
        # ===========================
        self.bottom_bar = QtWidgets.QFrame()
        self.bottom_bar.setObjectName("BottomBar")
        self.bottom_bar.setFixedHeight(35)
        bot_layout = QtWidgets.QHBoxLayout(self.bottom_bar)
        bot_layout.setContentsMargins(0, 0, 0, 0)
        bot_layout.setSpacing(0)
        
        self.btn_tab_elem = self.create_tab_btn("Element Mode", 0)
        self.btn_tab_shad = self.create_tab_btn("Shader Mode", 1)
        self.btn_tab_vars = self.create_tab_btn("Variables", 2)
        
        # Радио-группа для кнопок
        self.tab_group = QtWidgets.QButtonGroup(self)
        self.tab_group.addButton(self.btn_tab_elem)
        self.tab_group.addButton(self.btn_tab_shad)
        self.tab_group.addButton(self.btn_tab_vars)
        self.btn_tab_elem.setChecked(True)
        
        bot_layout.addWidget(self.btn_tab_elem)
        bot_layout.addWidget(self.btn_tab_shad)
        bot_layout.addWidget(self.btn_tab_vars)
        bot_layout.addStretch()
        
        # ===========================
        # FINAL ASSEMBLY
        # ===========================
        self.root_layout.addWidget(self.top_bar)
        self.root_layout.addWidget(middle_widget) # Вставляем среднюю зону
        self.root_layout.addWidget(self.bottom_bar)
        
        # ===========================
        # LOGIC CONNECTIONS
        # ===========================
        # Связываем выделение в Канвасе с Инспектором
        self.mode_element.element_selected.connect(self.inspector.set_selection)
        
        # Первый запуск
        self.on_refresh()

    def create_tab_btn(self, text, index):
        btn = QtWidgets.QPushButton(text)
        btn.setObjectName("ModeTab")
        btn.setCheckable(True)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        # Смена режима
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(index))
        # Скрываем/показываем инспектор в зависимости от режима (опционально)
        # Например, в ShaderMode инспектор может быть не нужен.
        # Пока оставим как есть.
        return btn

    def on_refresh(self):
        """Обновление данных из Blender."""
        if self.stack.currentWidget() == self.mode_element:
            self.mode_element.rebuild_scene()

    def closeEvent(self, event):
        """Остановка моста при закрытии окна."""
        if self.bridge:
            self.bridge.stop()
        super().closeEvent(event)