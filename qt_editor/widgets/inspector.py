# RZMenu/qt_editor/widgets/inspector.py
from PySide6 import QtWidgets, QtCore, QtGui
from .base import RZDraggableNumber

class RZCollapsibleGroup(QtWidgets.QWidget):
    """Виджет-группа со сворачиваемым содержимым"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.toggle_btn = QtWidgets.QToolButton()
        self.toggle_btn.setText(f"▼ {title}")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.setStyleSheet("QToolButton { border: none; font-weight: bold; color: #ccc; text-align: left; background: #333; padding: 4px; }")
        self.toggle_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.toggle_btn.clicked.connect(self.on_toggle)
        
        self.layout.addWidget(self.toggle_btn)

        self.content_area = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QFormLayout(self.content_area)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.layout.addWidget(self.content_area)

    def on_toggle(self):
        checked = self.toggle_btn.isChecked()
        self.toggle_btn.setText(f"{'▼' if checked else '▶'} {self.toggle_btn.text()[2:]}")
        self.content_area.setVisible(checked)

    def add_row(self, label, widget):
        self.content_layout.addRow(label, widget)


class RZColorButton(QtWidgets.QPushButton):
    """Кнопка для выбора цвета"""
    colorChanged = QtCore.Signal(list) # [r, g, b, a]

    def __init__(self):
        super().__init__()
        self.setFlat(True)
        self.setAutoFillBackground(True)
        self.setMinimumHeight(20)
        self._current_color = [1.0, 1.0, 1.0, 1.0]
        self.clicked.connect(self._pick_color)
        self.update_style()

    def set_color(self, rgba):
        self._current_color = rgba
        self.update_style()

    def update_style(self):
        r, g, b, _ = [int(c * 255) for c in self._current_color]
        # Показываем цвет фона кнопки, текст контрастный
        text_col = "black" if (r*0.299 + g*0.587 + b*0.114) > 186 else "white"
        self.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #555; border-radius: 3px;")

    def _pick_color(self):
        # MOCK: В реальности здесь QtWidgets.QColorDialog
        print("[MOCK] Opening Color Dialog...")
        # Для теста просто инвертируем цвет или ставим рандом
        import random
        new_color = [random.random(), random.random(), random.random(), 1.0]
        self.set_color(new_color)
        self.colorChanged.emit(new_color)


class RZMInspectorPanel(QtWidgets.QWidget):
    property_changed = QtCore.Signal(str, object, object)

    def __init__(self):
        super().__init__()
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Хедер
        self.lbl_info = QtWidgets.QLabel("No Selection")
        self.lbl_info.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_info.setStyleSheet("font-weight: bold; color: #888; padding: 5px; background: #222;")
        main_layout.addWidget(self.lbl_info)

        # Скролл зона
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        main_layout.addWidget(scroll)

        self.container = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.container)
        scroll.setWidget(self.container)

        self._init_ui()
        
        # State storage
        self.has_data = False
        self._block_signals = False
        
        # Spacer
        self.layout.addStretch()

    def _init_ui(self):
        # --- GROUP: MAIN ---
        self.grp_main = RZCollapsibleGroup("Main")
        self.layout.addWidget(self.grp_main)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.editingFinished.connect(lambda: self.emit_change('name', self.name_edit.text()))
        self.grp_main.add_row("Name:", self.name_edit)

        # Class Type
        self.cb_class = QtWidgets.QComboBox()
        self.cb_class.addItems(["CONTAINER", "GRID_CONTAINER", "BUTTON", "SLIDER", "TEXT", "ANCHOR"])
        self.cb_class.currentTextChanged.connect(lambda t: self.emit_change('class_type', t))
        self.grp_main.add_row("Type:", self.cb_class)

        # --- GROUP: TRANSFORM ---
        self.grp_trans = RZCollapsibleGroup("Transform")
        self.layout.addWidget(self.grp_trans)

        # Pos
        self.pos_x = RZDraggableNumber(is_int=True)
        self.pos_y = RZDraggableNumber(is_int=True)
        self.pos_x.value_changed.connect(lambda v: self.emit_change('pos_x', int(v)))
        self.pos_y.value_changed.connect(lambda v: self.emit_change('pos_y', int(v)))
        
        row_pos = QtWidgets.QHBoxLayout()
        row_pos.addWidget(QtWidgets.QLabel("X:"))
        row_pos.addWidget(self.pos_x)
        row_pos.addWidget(QtWidgets.QLabel("Y:"))
        row_pos.addWidget(self.pos_y)
        self.grp_trans.add_row("Position:", row_pos)

        # Size
        self.size_w = RZDraggableNumber(is_int=True)
        self.size_h = RZDraggableNumber(is_int=True)
        self.size_w.value_changed.connect(lambda v: self.emit_change('width', int(v)))
        self.size_h.value_changed.connect(lambda v: self.emit_change('height', int(v)))

        row_size = QtWidgets.QHBoxLayout()
        row_size.addWidget(QtWidgets.QLabel("W:"))
        row_size.addWidget(self.size_w)
        row_size.addWidget(QtWidgets.QLabel("H:"))
        row_size.addWidget(self.size_h)
        self.grp_trans.add_row("Size:", row_size)

        # --- GROUP: STYLE ---
        self.grp_style = RZCollapsibleGroup("Style")
        self.layout.addWidget(self.grp_style)

        self.color_btn = RZColorButton()
        self.color_btn.colorChanged.connect(lambda c: self.emit_change('color', c))
        self.grp_style.add_row("Color:", self.color_btn)

        # --- GROUP: CONTENT ---
        self.grp_content = RZCollapsibleGroup("Content")
        self.layout.addWidget(self.grp_content)

        self.text_id_edit = QtWidgets.QLineEdit()
        self.text_id_edit.setPlaceholderText("Text Key ID...")
        self.text_id_edit.editingFinished.connect(lambda: self.emit_change('text_id', self.text_id_edit.text()))
        self.grp_content.add_row("Text ID:", self.text_id_edit)

        self.img_id_edit = QtWidgets.QLineEdit()
        self.img_id_edit.setPlaceholderText("Image Key ID...")
        self.img_id_edit.editingFinished.connect(lambda: self.emit_change('image_id', self.img_id_edit.text()))
        self.grp_content.add_row("Image ID:", self.img_id_edit)

        # --- GROUP: SETTINGS ---
        self.grp_settings = RZCollapsibleGroup("Settings")
        self.layout.addWidget(self.grp_settings)

        self.chk_hide = QtWidgets.QCheckBox("Is Hidden")
        self.chk_hide.toggled.connect(lambda v: self.emit_change('is_hidden', v))
        self.grp_settings.add_row("", self.chk_hide)

        self.chk_lock = QtWidgets.QCheckBox("Lock Transformation")
        self.chk_lock.toggled.connect(lambda v: self.emit_change('is_locked', v))
        self.grp_settings.add_row("", self.chk_lock)


    def emit_change(self, key, val, idx=None):
        if self.has_data and not self._block_signals:
            self.property_changed.emit(key, val, idx)

    def update_ui(self, props):
        """
        props structure expected:
        {
            'exists': bool,
            'id': int,
            'name': str,
            'class_type': str,
            'pos_x': int, 'pos_y': int,
            'width': int, 'height': int,
            'color': [r,g,b,a],
            'text_id': str,
            'image_id': str,
            'is_hidden': bool,
            'is_locked': bool,
            'is_multi': bool, ...
        }
        """
        self._block_signals = True
        
        if props and props.get('exists'):
            self.has_data = True
            self.container.setEnabled(True)
            
            # Заголовок
            count = len(props.get('selected_ids', []))
            if props.get('is_multi'):
                self.lbl_info.setText(f"Multi-Edit ({count} items)")
                self.name_edit.setPlaceholderText("Mixed Names...")
                self.name_edit.clear()
            else:
                self.lbl_info.setText(f"ID: {props['id']} ({props['class_type']})")
                self.name_edit.setText(props.get('name', ''))

            # Данные (берем от активного или последнего)
            # Если ключа нет в словаре, используем дефолт
            self.cb_class.setCurrentText(props.get('class_type', 'CONTAINER'))
            
            self.pos_x.set_value_from_backend(props.get('pos_x', 0))
            self.pos_y.set_value_from_backend(props.get('pos_y', 0))
            self.size_w.set_value_from_backend(props.get('width', 100))
            self.size_h.set_value_from_backend(props.get('height', 100))
            
            color = props.get('color', [0.5, 0.5, 0.5, 1.0])
            self.color_btn.set_color(color)

            self.text_id_edit.setText(props.get('text_id', ''))
            self.img_id_edit.setText(props.get('image_id', ''))

            self.chk_hide.setChecked(props.get('is_hidden', False))
            self.chk_lock.setChecked(props.get('is_locked', False))

        else:
            self.has_data = False
            self.container.setEnabled(False)
            self.lbl_info.setText("No Selection")
            self.name_edit.clear()
        
        self._block_signals = False