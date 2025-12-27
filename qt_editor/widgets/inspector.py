# RZMenu/qt_editor/widgets/inspector.py

from PySide6 import QtWidgets, QtCore, QtGui
from .draggable_spinbox import DraggableSpinBox

class InspectorWidget(QtWidgets.QWidget):
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager 
        self.current_element_id = None
        self._widgets_cache = {} 
        
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        lbl_title = QtWidgets.QLabel("PROPERTIES")
        lbl_title.setAlignment(QtCore.Qt.AlignCenter)
        lbl_title.setStyleSheet("font-weight: bold; color: #888; padding: 10px; background: #2b2b2b;")
        self.main_layout.addWidget(lbl_title)
        
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setStyleSheet("background-color: #222;")
        
        self.content_widget = QtWidgets.QWidget()
        self.scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll)
        
        self.form_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.form_layout.setContentsMargins(10, 10, 10, 10)
        self.form_layout.setSpacing(15)
        self.form_layout.addStretch() 
        
        self.show_empty_state()

    def show_empty_state(self):
        self.current_element_id = None
        self._clear_layout()
        self._widgets_cache = {}
        lbl = QtWidgets.QLabel("No Selection")
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setStyleSheet("color: #555; margin-top: 50px;")
        self.form_layout.insertWidget(0, lbl)

    def set_selection(self, element_id):
        self.current_element_id = element_id
        if element_id is None:
            self.show_empty_state()
            return
        data = self.data_manager.get_data(element_id)
        self._clear_layout()
        self._widgets_cache = {}
        if data: self._build_full_ui(data)
        else: self.show_empty_state()

    def on_element_data_changed(self, element_id):
        if not self.isVisible(): return
        if element_id != self.current_element_id: return
        data = self.data_manager.get_data(element_id)
        if data: self._update_ui_values(data)

    def _update_ui_values(self, data):
        """Обновляет значения виджетов (безопасно)."""
        def safe_update(widget, new_val, getter, setter, transform=lambda x: x):
            try:
                if not widget: return
                if widget.hasFocus(): return
                if isinstance(widget, DraggableSpinBox) and widget._dragging: return
                
                current_val = getter()
                target_val = transform(new_val)
                
                # Приведение типов для сравнения
                if str(current_val) != str(target_val):
                    widget.blockSignals(True)
                    setter(target_val)
                    widget.blockSignals(False)
            except Exception: pass

        for prop_name, widget_obj in self._widgets_cache.items():
            if prop_name not in data: continue
            raw_val = data[prop_name]

            if isinstance(widget_obj, QtWidgets.QLineEdit):
                safe_update(widget_obj, raw_val, widget_obj.text, widget_obj.setText, str)
            
            elif isinstance(widget_obj, QtWidgets.QSpinBox):
                safe_update(widget_obj, raw_val, widget_obj.value, widget_obj.setValue, int)
            
            elif isinstance(widget_obj, QtWidgets.QComboBox):
                safe_update(widget_obj, raw_val, widget_obj.currentText, widget_obj.setCurrentText, str)
            
            elif isinstance(widget_obj, QtWidgets.QCheckBox):
                safe_update(widget_obj, raw_val, widget_obj.isChecked, widget_obj.setChecked, bool)

            elif isinstance(widget_obj, list): # Vectors
                if len(widget_obj) == len(raw_val):
                    for i, w in enumerate(widget_obj):
                        if isinstance(w, QtWidgets.QSpinBox):
                             safe_update(w, raw_val[i], w.value, w.setValue, int)
            
            elif isinstance(widget_obj, QtWidgets.QPushButton) and prop_name == 'color':
                c = QtGui.QColor.fromRgbF(raw_val[0], raw_val[1], raw_val[2], raw_val[3])
                css = f"background-color: {c.name(QtGui.QColor.HexArgb)}; border: 1px solid #555; border-radius: 3px;"
                widget_obj.setStyleSheet(css)

    # --- BUILDERS ---
    def _build_full_ui(self, data):
        self._add_header("General")
        self.add_text_row("Name", data.get('element_name', ''), 'element_name')
        self.add_combo_row("Class", ['CONTAINER', 'GRID_CONTAINER', 'ANCHOR', 'BUTTON', 'SLIDER', 'TEXT'], data.get('elem_class', 'CONTAINER'), 'elem_class')

        # [NEW] Editor Flags
        self._add_header("Editor Flags")
        # Создаем горизонтальный ряд чекбоксов
        flags_row = QtWidgets.QHBoxLayout()
        self.add_flag_box("Hide", data.get('qt_hide', False), 'qt_hide', flags_row)
        self.add_flag_box("Lock Pos", data.get('qt_lock_pos', False), 'qt_lock_pos', flags_row)
        self.add_flag_box("Lock Size", data.get('qt_lock_size', False), 'qt_lock_size', flags_row)
        self.form_layout.addLayout(flags_row)

        self._add_header("Transform (Local)")
        self.add_vec2_row("Position", data.get('position', [0,0]), 'position')
        self.add_vec2_row("Size", data.get('size', [100,100]), 'size')

        self._add_header("Style")
        self.add_color_row("Color", data.get('color', [0,0,0,0]), 'color')

        self._add_header("Content")
        self.add_combo_row("Img Mode", ['SINGLE', 'CONDITIONAL_LIST', 'INDEX_LIST'], data.get('image_mode', 'SINGLE'), 'image_mode')
        self.add_int_row("Image ID", data.get('image_id', -1), 'image_id')
        self.add_text_row("Text ID", data.get('text_id', ''), 'text_id')

        self._add_header("Visibility")
        self.add_combo_row("Mode", ['ALWAYS', 'CONDITIONAL'], data.get('visibility_mode', 'ALWAYS'), 'visibility_mode')
        self.add_text_row("Condition", data.get('visibility_condition', ''), 'visibility_condition')

        self.form_layout.addStretch()

    # --- HELPERS ---
    def _add_header(self, txt):
        lbl = QtWidgets.QLabel(txt.upper())
        lbl.setStyleSheet("color: #dbaa48; font-weight: bold; font-size: 11px; margin-top: 10px;")
        self.form_layout.addWidget(lbl)
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("background-color: #333;")
        self.form_layout.addWidget(line)

    def add_text_row(self, label, val, prop):
        row, field = self._make_row(label, QtWidgets.QLineEdit(str(val)))
        field.editingFinished.connect(lambda: self.update_prop(prop, field.text()))
        self._widgets_cache[prop] = field
        self.form_layout.addLayout(row)

    def add_int_row(self, label, val, prop):
        row, spin = self._make_row(label, DraggableSpinBox()) 
        spin.setValue(int(val))
        spin.editingFinished.connect(lambda: self.update_prop(prop, spin.value()))
        self._widgets_cache[prop] = spin
        self.form_layout.addLayout(row)

    def add_combo_row(self, label, options, val, prop):
        row, combo = self._make_row(label, QtWidgets.QComboBox())
        combo.addItems(options)
        if val in options: combo.setCurrentText(val)
        combo.currentTextChanged.connect(lambda txt: self.update_prop(prop, txt))
        self._widgets_cache[prop] = combo
        self.form_layout.addLayout(row)

    def add_vec2_row(self, label, vals, prop):
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self._make_label(label))
        spins = []
        for i, v in enumerate(vals):
            s = DraggableSpinBox() 
            s.setValue(int(v))
            s.setFixedHeight(22)
            s.editingFinished.connect(lambda p=prop, sp=spins: self.update_prop_vec(p, sp))
            row.addWidget(s)
            spins.append(s)
        self._widgets_cache[prop] = spins
        self.form_layout.addLayout(row)

    def add_color_row(self, label, val, prop):
        btn = QtWidgets.QPushButton()
        btn.setFixedHeight(24)
        c = QtGui.QColor.fromRgbF(val[0], val[1], val[2], val[3])
        btn.setStyleSheet(f"background-color: {c.name(QtGui.QColor.HexArgb)}; border: 1px solid #555;")
        def pick():
            new = QtWidgets.QColorDialog.getColor(c, self, "Color", QtWidgets.QColorDialog.ShowAlphaChannel)
            if new.isValid(): self.update_prop(prop, [new.redF(), new.greenF(), new.blueF(), new.alphaF()])
        btn.clicked.connect(pick)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self._make_label(label))
        row.addWidget(btn)
        self._widgets_cache[prop] = btn
        self.form_layout.addLayout(row)

    def add_flag_box(self, label, val, prop, layout):
        cb = QtWidgets.QCheckBox(label)
        cb.setChecked(bool(val))
        cb.setStyleSheet("color: #ccc;")
        cb.toggled.connect(lambda state: self.update_prop(prop, state))
        self._widgets_cache[prop] = cb
        layout.addWidget(cb)

    def _make_row(self, text, widget):
        row = QtWidgets.QHBoxLayout()
        lbl = self._make_label(text)
        row.addWidget(lbl)
        if not isinstance(widget, DraggableSpinBox):
             widget.setStyleSheet("background: #1e1e1e; border: 1px solid #333; color: #ddd; selection-background-color: #555;")
        row.addWidget(widget)
        return row, widget

    def _make_label(self, text):
        l = QtWidgets.QLabel(text)
        l.setFixedWidth(80)
        l.setStyleSheet("color: #aaa;")
        return l

    def update_prop(self, prop, val):
        if self.current_element_id is not None:
            self.data_manager.update_element_property(self.current_element_id, prop, val)
            
    def update_prop_vec(self, prop, spins):
        val = [s.value() for s in spins]
        self.data_manager.update_element_property(self.current_element_id, prop, val)

    def _clear_layout(self):
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout(): 
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget(): sub.widget().deleteLater()