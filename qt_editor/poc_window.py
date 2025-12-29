# RZMenu/qt_editor/poc_window.py
import bpy
import sys
import datetime
from PySide6 import QtWidgets, QtCore, QtGui

# Глобальная ссылка на окно, чтобы сборщик мусора не удалил его
_qt_window = None

class RZMPoCWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RZMenu Editor (History Aware)")
        self.resize(700, 400)
        
        # Основной лейаут
        main_layout = QtWidgets.QHBoxLayout(self)
        
        # Сплиттер (Разделитель)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- ЛЕВАЯ ПАНЕЛЬ (INFO / LOG) ---
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_info = QtWidgets.QLabel("Event Log:")
        lbl_info.setStyleSheet("font-weight: bold; color: #aaa;")
        left_layout.addWidget(lbl_info)
        
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background: #222; color: #0f0; font-family: Monospace; font-size: 11px;")
        left_layout.addWidget(self.log_view)
        
        splitter.addWidget(left_widget)
        
        # --- ПРАВАЯ ПАНЕЛЬ (CONTROLS) ---
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # -- Блок Undo/Redo Кнопок (для мыши) --
        undo_layout = QtWidgets.QHBoxLayout()
        btn_undo = QtWidgets.QPushButton("<< UNDO (Ctrl+Z)")
        btn_redo = QtWidgets.QPushButton("REDO (Ctrl+Sh+Z) >>")
        
        # Стилизация под Blender
        btn_undo.setStyleSheet("background: #442222; color: #eba6a6;")
        btn_redo.setStyleSheet("background: #223322; color: #a6eba6;")
        
        btn_undo.clicked.connect(self.trigger_blender_undo)
        btn_redo.clicked.connect(self.trigger_blender_redo)
        
        undo_layout.addWidget(btn_undo)
        undo_layout.addWidget(btn_redo)
        right_layout.addLayout(undo_layout)
        
        # Разделитель
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        right_layout.addWidget(sep)
        
        # -- Список элементов --
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        right_layout.addWidget(self.list_widget)
        
        # -- Поля значений --
        form_layout = QtWidgets.QFormLayout()
        self.spin_x = QtWidgets.QSpinBox()
        self.spin_x.setRange(-9999, 9999)
        self.spin_y = QtWidgets.QSpinBox()
        self.spin_y.setRange(-9999, 9999)
        
        form_layout.addRow("Pos X:", self.spin_x)
        form_layout.addRow("Pos Y:", self.spin_y)
        right_layout.addLayout(form_layout)
        
        splitter.addWidget(right_widget)
        
        # Настройка пропорций (30% лево, 70% право)
        splitter.setSizes([200, 500])

        # --- SIGNALS ---
        # Важно: используем editingFinished (Enter или потеря фокуса),
        # а не valueChanged, чтобы не спамить историю при прокрутке.
        self.spin_x.editingFinished.connect(self.send_to_blender)
        self.spin_y.editingFinished.connect(self.send_to_blender)
        
        self.current_id = -1
        self.sync_with_blender()
        self.log_message("Window Initialized. Ready.")

    # --- KEY EVENTS (HOTKEYS FIX) ---
    def keyPressEvent(self, event):
        """Перехват нажатий клавиш для работы Ctrl+Z внутри окна"""
        key = event.key()
        mod = event.modifiers()
        
        if key == QtCore.Qt.Key_Z and (mod & QtCore.Qt.ControlModifier):
            if mod & QtCore.Qt.ShiftModifier:
                # Ctrl + Shift + Z -> Redo
                self.trigger_blender_redo()
            else:
                # Ctrl + Z -> Undo
                self.trigger_blender_undo()
            
            # Принимаем событие, чтобы Qt не пытался сделать Undo внутри текстового поля
            event.accept()
            return

        super().keyPressEvent(event)

    def log_message(self, msg):
        """Добавляет сообщение в левую панель"""
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{time_str}] {msg}")
        # Автоскролл вниз
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # --- BLENDER ACTIONS ---

    def trigger_blender_undo(self):
        self.log_message("CMD: Requesting Global Undo...")
        # Используем таймер, чтобы выполнить это в главном потоке Blender безопасно
        bpy.app.timers.register(lambda: bpy.ops.ed.undo(), first_interval=0.001)

    def trigger_blender_redo(self):
        self.log_message("CMD: Requesting Global Redo...")
        bpy.app.timers.register(lambda: bpy.ops.ed.redo(), first_interval=0.001)

    # --- SYNC LOGIC ---

    def sync_with_blender(self, source="Init"):
        """Чтение данных из RZM (вызывается при Undo/Redo)"""
        if source != "Init":
            self.log_message(f"SYNC: Update triggered by {source}")
        
        # Блокируем сигналы, чтобы обновление UI не вызывало обратную запись в Blender
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        
        current_row = self.list_widget.currentRow()
        self.list_widget.clear()
        
        # Читаем "Правду" из Блендера
        try:
            elements = bpy.context.scene.rzm.elements
            for elem in elements:
                item = QtWidgets.QListWidgetItem(f"ID {elem.id}: {elem.element_name}")
                item.setData(QtCore.Qt.UserRole, elem.id)
                self.list_widget.addItem(item)
                
            # Восстанавливаем выделение, если ID все еще существует
            found_current = False
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(QtCore.Qt.UserRole) == self.current_id:
                    self.list_widget.setCurrentRow(i)
                    self.update_spinboxes_from_id(self.current_id)
                    found_current = True
                    break
            
            if not found_current and self.list_widget.count() > 0:
                self.current_id = -1
                
        except Exception as e:
            self.log_message(f"ERROR Sync: {e}")
        
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)

    def update_spinboxes_from_id(self, elem_id):
        elements = bpy.context.scene.rzm.elements
        target = next((e for e in elements if e.id == elem_id), None)
        if target:
            self.spin_x.setValue(target.position[0])
            self.spin_y.setValue(target.position[1])

    def on_item_clicked(self, item):
        self.current_id = item.data(QtCore.Qt.UserRole)
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.update_spinboxes_from_id(self.current_id)
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)

    def send_to_blender(self):
        """Запись данных в Blender и создание Undo Step"""
        if self.current_id == -1: return
        
        val_x = self.spin_x.value()
        val_y = self.spin_y.value()
        
        self.log_message(f"OP: Move ID {self.current_id} -> ({val_x}, {val_y})")
        
        try:
            # 1. Находим элемент и меняем данные напрямую
            elements = bpy.context.scene.rzm.elements
            target = next((e for e in elements if e.id == self.current_id), None)
            
            if target:
                # Проверяем, изменилось ли значение, чтобы не спамить историю просто так
                if target.position[0] != val_x or target.position[1] != val_y:
                    target.position[0] = val_x
                    target.position[1] = val_y
                    
                    # 2. ГЛАВНОЕ: Сообщаем Блендеру, что это действие нужно запомнить
                    # "undo_push" фиксирует текущее состояние как новую точку возврата
                    bpy.ops.ed.undo_push(message=f"RZM Move Element {self.current_id}")
                    self.log_message("-> Undo Push Created")
            else:
                self.log_message("Error: Element not found during update")

        except Exception as e:
            self.log_message(f"OP FAILED: {e}")

def show_window():
    global _qt_window
    # Важно: всегда используем существующий инстанс QApplication или создаем новый, если его нет
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    
    if _qt_window is None:
        _qt_window = RZMPoCWindow()
    
    _qt_window.show()
    # Первичная синхронизация
    _qt_window.sync_with_blender()