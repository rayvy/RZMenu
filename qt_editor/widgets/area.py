# RZMenu/qt_editor/widgets/area.py
"""
RZAreaWidget - A container widget that allows dynamic panel type switching.
Similar to Blender's area system where each area can display any editor type.
Supports splitting and closing areas dynamically.
"""
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.widgets import RZPanelWidget
from .lib.theme import get_current_theme
from .panel_base import RZEditorPanel
from .panel_factory import PanelFactory
from ..utils.icons import IconManager

class RZAreaHeader(QtWidgets.QFrame):
    """
    Header bar for RZAreaWidget containing the panel type selector and area menu.
    """
    panel_type_changed = QtCore.Signal(str)
    split_vertical_requested = QtCore.Signal()
    split_horizontal_requested = QtCore.Signal()
    close_requested = QtCore.Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RZAreaHeader")
        self.setFixedHeight(22) # Slim height
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)
        
        # Panel type selector
        self.combo_type = QtWidgets.QComboBox()
        self.combo_type.setObjectName("AreaTypeSelector")
        self.combo_type.setMinimumWidth(80)
        self.combo_type.setFixedHeight(18)
        self._populate_panel_types()
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.combo_type)
        
        layout.addStretch()
        
        # Area menu button
        im = IconManager.get_instance()
        self.btn_menu = QtWidgets.QPushButton(im.get_icon("circle_3dots"), "")
        self.btn_menu.setObjectName("AreaMenuButton")
        self.btn_menu.setFixedSize(14, 14)
        self.btn_menu.setIconSize(QtCore.QSize(12, 12))
        self.btn_menu.setToolTip("Area Options")
        self.btn_menu.clicked.connect(self._show_area_menu)
        layout.addWidget(self.btn_menu)
        
        # Opacity Effect for Stealth UI
        self._opacity = QtWidgets.QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.4) # Very subtle by default
        self.setGraphicsEffect(self._opacity)
        
        self.apply_theme()

    def enterEvent(self, event):
        self._opacity.setOpacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._opacity.setOpacity(0.4)
        super().leaveEvent(event)
    
    def _populate_panel_types(self):
        self.combo_type.blockSignals(True)
        self.combo_type.clear()
        panels = PanelFactory.get_available_panels()
        for panel_info in panels:
            self.combo_type.addItem(panel_info["name"], userData=panel_info["id"])
        self.combo_type.blockSignals(False)
    
    def _on_type_changed(self, index: int):
        if index < 0: return
        panel_id = self.combo_type.itemData(index)
        if panel_id: self.panel_type_changed.emit(panel_id)
    
    def _show_area_menu(self):
        im = IconManager.get_instance()
        menu = QtWidgets.QMenu(self)
        
        act_split_v = menu.addAction(im.get_icon("down_doublearrow"), "Split Vertical")
        act_split_v.triggered.connect(self.split_vertical_requested.emit)
        
        act_split_h = menu.addAction(im.get_icon("right_doublearrow"), "Split Horizontal")
        act_split_h.triggered.connect(self.split_horizontal_requested.emit)
        
        menu.addSeparator()
        
        act_close = menu.addAction(im.get_icon("circle_x"), "Close Area")
        act_close.triggered.connect(self.close_requested.emit)
        
        menu.exec(self.btn_menu.mapToGlobal(QtCore.QPoint(0, self.btn_menu.height())))
    
    def set_current_type(self, panel_id: str):
        self.combo_type.blockSignals(True)
        for i in range(self.combo_type.count()):
            if self.combo_type.itemData(i) == panel_id:
                self.combo_type.setCurrentIndex(i)
                break
        self.combo_type.blockSignals(False)
    
    def apply_theme(self):
        theme = get_current_theme()
        r_sm = theme.get("radius_sm", "4px")
        
        self.setStyleSheet(f"""
            #RZAreaHeader {{
                background-color: {theme.get('bg_area_header', '#333842')};
                border: none;
                border-bottom: 1px solid {theme.get('border_main', '#2A2E35')};
            }}
            #AreaTypeSelector {{
                border-radius: {r_sm};
                font-weight: 600;
                font-size: 9px;
                background-color: transparent;
                border: none;
                color: {theme.get('text_dim', '#888')};
            }}
            #AreaTypeSelector:hover {{
                color: {theme.get('text_main', '#EEE')};
            }}
            #AreaTypeSelector::drop-down {{
                border: none;
                width: 0px;
            }}
            #AreaMenuButton {{
                background-color: transparent;
                border: none;
                border-radius: {r_sm};
                opacity: 0.6;
            }}
            #AreaMenuButton:hover {{
                background-color: rgba(255, 255, 255, 20);
                opacity: 1.0;
            }}
        """)


class RZAreaWidget(RZPanelWidget):
    """
    Container widget that hosts an RZEditorPanel with a header for type switching.
    Supports splitting into multiple areas and closing.
    """
    
    panel_changed = QtCore.Signal(str, object)
    
    def __init__(self, initial_panel_id: str = None, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RZAreaWidget")
        self.setMinimumSize(QtCore.QSize(100, 100))
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        self._current_panel: RZEditorPanel = None
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.header = RZAreaHeader(self)
        self.header.panel_type_changed.connect(self.change_panel)
        self.header.split_vertical_requested.connect(lambda: self.split_area(QtCore.Qt.Vertical))
        self.header.split_horizontal_requested.connect(lambda: self.split_area(QtCore.Qt.Horizontal))
        self.header.close_requested.connect(self.close_area)
        main_layout.addWidget(self.header)
        
        self.content_container = QtWidgets.QWidget()
        self.content_container.setObjectName("RZAreaContent")
        self.content_layout = QtWidgets.QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        main_layout.addWidget(self.content_container, stretch=1)
        
        if initial_panel_id:
            self.set_panel_type(initial_panel_id)
        
        self.apply_theme()
    
    def set_panel_type(self, panel_id: str):
        if self._current_panel and self._current_panel.PANEL_ID == panel_id:
            return
        self.change_panel(panel_id)
        self.header.set_current_type(panel_id)
    
    def change_panel(self, panel_id: str):
        if self._current_panel:
            self._current_panel.on_deactivate()
            self.content_layout.removeWidget(self._current_panel)
            self._current_panel.deleteLater()
            self._current_panel = None
        
        if not PanelFactory.is_registered(panel_id):
            self._create_placeholder(panel_id, "Not Registered")
            return

        try:
            self._current_panel = PanelFactory.create_panel(panel_id, parent=self.content_container)
            if self._current_panel:
                self.content_layout.addWidget(self._current_panel)
                self._current_panel.on_activate()
                self.panel_changed.emit(panel_id, self._current_panel)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._create_placeholder(panel_id, f"Setup Error: {e}")
    
    def _create_placeholder(self, panel_id: str, reason: str = ""):
        msg = f"Panel '{panel_id}' unavailable\n{reason}"
        placeholder = QtWidgets.QLabel(msg)
        placeholder.setAlignment(QtCore.Qt.AlignCenter)
        placeholder.setStyleSheet("color: #888; font-style: italic;")
        self.content_layout.addWidget(placeholder)
    
    def get_current_panel(self) -> RZEditorPanel:
        return self._current_panel
    
    def get_current_panel_id(self) -> str:
        return self._current_panel.PANEL_ID if self._current_panel else ""
    
    def split_area(self, orientation: QtCore.Qt.Orientation):
        parent = self.parent()
        if not isinstance(parent, QtWidgets.QSplitter): return
        
        parent_splitter = parent
        current_panel_id = self.get_current_panel_id() or "OUTLINER"
        my_index = parent_splitter.indexOf(self)
        old_sizes = parent_splitter.sizes()
        my_size = old_sizes[my_index] if my_index < len(old_sizes) else 200
        
        new_splitter = QtWidgets.QSplitter(orientation)
        new_splitter.setChildrenCollapsible(False)
        
        area1 = RZAreaWidget(initial_panel_id=current_panel_id)
        area2 = RZAreaWidget(initial_panel_id=current_panel_id)
        new_splitter.addWidget(area1)
        new_splitter.addWidget(area2)
        
        half_size = my_size // 2
        new_splitter.setSizes([half_size, half_size])
        parent_splitter.insertWidget(my_index, new_splitter)
        
        if self._current_panel: self._current_panel.on_deactivate()
        self.setParent(None)
        self.deleteLater()
        
        new_sizes = old_sizes.copy()
        new_sizes[my_index] = my_size
        parent_splitter.setSizes(new_sizes)
    
    def close_area(self):
        parent = self.parent()
        if not isinstance(parent, QtWidgets.QSplitter): return
        
        parent_splitter = parent
        grandparent = parent_splitter.parent()
        is_nested = isinstance(grandparent, QtWidgets.QSplitter)
        
        if parent_splitter.count() <= 1 and not is_nested: return
        
        if self._current_panel: self._current_panel.on_deactivate()
        my_index = parent_splitter.indexOf(self)
        old_sizes = parent_splitter.sizes()
        self.setParent(None)
        self.deleteLater()
        
        if parent_splitter.count() == 1 and is_nested:
            remaining_widget = parent_splitter.widget(0)
            if remaining_widget:
                grandparent_splitter = grandparent
                splitter_index = grandparent_splitter.indexOf(parent_splitter)
                remaining_widget.setParent(None)
                grandparent_splitter.insertWidget(splitter_index, remaining_widget)
                parent_splitter.setParent(None)
                parent_splitter.deleteLater()
        else:
            if old_sizes and my_index < len(old_sizes):
                freed_size = old_sizes[my_index]
                new_sizes = [s for i, s in enumerate(old_sizes) if i != my_index]
                if new_sizes:
                    distribute_to = min(my_index, len(new_sizes) - 1)
                    new_sizes[distribute_to] += freed_size
                    parent_splitter.setSizes(new_sizes)
    
    def apply_theme(self):
        theme = get_current_theme()
        r_md = theme.get('radius_md', '8px')
        self.setStyleSheet(f"""
            #RZAreaWidget {{
                background-color: {theme.get('bg_panel', '#2C313A')};
                border: 1px solid {theme.get('border_main', '#3A404A')};
                border-radius: 4px;
            }}
            #RZAreaContent {{ background-color: transparent; }}
        """)
        if hasattr(self, 'header'): self.header.apply_theme()
    
    def update_theme_styles(self):
        self.apply_theme()
        if self._current_panel and hasattr(self._current_panel, 'update_theme_styles'):
            self._current_panel.update_theme_styles()

