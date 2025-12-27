#RZMenu/ui/qt_editor.py
import bpy
import functools
import os
import sys
import traceback

# --- ENV SETUP ---
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_API"] = "pyside6"
os.environ["QT_SCALE_FACTOR"] = "1"

# --- QT IMPORT ---
qt_available = False
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QPointF, QRectF, QSizeF
    from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QAction
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QSplitter, QTreeWidget, QTreeWidgetItem, QScrollArea, QFormLayout, 
        QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton, QGroupBox, 
        QColorDialog, QMenu, QInputDialog, QMessageBox
    )
    qt_available = True
except ImportError as e:
    print(f"QT Import Error: {e}")
except Exception as e:
    print(f"QT Critical Error: {e}")
    traceback.print_exc()

# --- EXCEPTION HOOK ---
def qt_excepthook(type, value, tback):
    print("\n[QT EXCEPTION CAUGHT]")
    traceback.print_exception(type, value, tback)
    sys.__excepthook__(type, value, tback)

if qt_available:
    sys.excepthook = qt_excepthook

if not qt_available:
    class QtWidgets:
        class QWidget(object): pass
        class QMainWindow(object): 
            def __init__(self, *args, **kwargs): pass
    class QtCore: Qt = object
    class QtGui: pass
    QMainWindow = object
else:
    QMainWindow = QtWidgets.QMainWindow


# ==========================================
#               COMPONENTS
# ==========================================

if qt_available:
    class CanvasWidget(QtWidgets.QWidget):
        element_selected = QtCore.Signal(int)
        element_moved = QtCore.Signal(int, int, int)
        element_resized = QtCore.Signal(int, int, int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumSize(800, 600)
            self.setMouseTracking(True)
            self.canvas_size = (1920, 1080)
            self.zoom_factor = 0.5
            self.pan_offset = QPointF(0, 0)
            self.elements = []
            self.selected_element_id = -1
            self.drag_mode = None
            self.drag_start_pos = QPointF()
            self.element_start_pos = QPointF()
            self.element_start_size = QSizeF()
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self.show_context_menu)

        def set_canvas_data(self, canvas_size, elements):
            self.canvas_size = canvas_size
            self.elements = elements
            self.update()

        def set_selected_element(self, element_id):
            self.selected_element_id = element_id
            self.update()

        def get_element_at_pos(self, pos):
            for element in reversed(self.elements):
                if 'pos' not in element or 'size' not in element: continue
                rect = QRectF(element['pos'], element['size'])
                if rect.contains(pos):
                    return element['id']
            return -1

        def screen_to_canvas(self, screen_pos):
            canvas_x = (screen_pos.x() - self.pan_offset.x()) / self.zoom_factor
            canvas_y = (screen_pos.y() - self.pan_offset.y()) / self.zoom_factor
            return QPointF(canvas_x, canvas_y)

        def paintEvent(self, event):
            try:
                painter = QPainter(self)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.fillRect(self.rect(), QColor(30, 30, 30))

                painter.save()
                painter.translate(self.pan_offset)
                painter.scale(self.zoom_factor, self.zoom_factor)

                # Grid
                painter.setPen(QPen(QColor(100, 100, 100, 50), 1))
                painter.drawRect(0, 0, self.canvas_size[0], self.canvas_size[1])

                for element in self.elements:
                    self.draw_element(painter, element)

                painter.restore()
            except Exception as e:
                print(f"Paint Error: {e}")

        def draw_element(self, painter, element):
            try:
                pos = element['pos']
                size = element['size']
                color = element.get('color', (0.5, 0.5, 0.5, 1.0))
                name = element.get('name', 'Unknown')
                
                rect = QRectF(pos.x(), pos.y(), size.width(), size.height())
                
                if len(color) >= 3:
                    q_col = QColor.fromRgbF(color[0], color[1], color[2], color[3] if len(color)>3 else 1.0)
                    painter.setBrush(QBrush(q_col))
                else:
                    painter.setBrush(QBrush(Qt.gray))

                if element['id'] == self.selected_element_id:
                    painter.setPen(QPen(QColor(255, 255, 0), 2))
                else:
                    painter.setPen(QPen(Qt.white, 1))

                painter.drawRect(rect)
                
                painter.setPen(QPen(Qt.black, 1))
                painter.drawText(rect, Qt.AlignCenter, name)

            except Exception as e:
                print(f"Error drawing element {element.get('id')}: {e}")

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                # В PySide6 event.position() возвращает QPointF, используем его напрямую
                c_pos = self.screen_to_canvas(event.position())
                eid = self.get_element_at_pos(c_pos)
                
                self.selected_element_id = eid
                self.element_selected.emit(eid)
                
                if eid != -1:
                    elem = next((e for e in self.elements if e['id'] == eid), None)
                    if elem:
                        self.drag_mode = 'move'
                        self.drag_start_pos = c_pos
                        self.element_start_pos = elem['pos']
                
                self.update()
            
            elif event.button() == Qt.MiddleButton:
                self.drag_mode = 'pan'
                self.drag_start_pos = event.position()

        def mouseMoveEvent(self, event):
            # [FIXED] Убраны вызовы .toPointF(), так как переменные уже имеют тип QPointF
            
            if self.drag_mode == 'pan':
                # event.position() -> QPointF
                # self.drag_start_pos -> QPointF
                # delta -> QPointF
                delta = event.position() - self.drag_start_pos
                
                self.pan_offset += delta # Просто складываем
                self.drag_start_pos = event.position()
                self.update()
            
            elif self.drag_mode == 'move' and self.selected_element_id != -1:
                c_pos = self.screen_to_canvas(event.position())
                delta = c_pos - self.drag_start_pos
                
                # self.element_start_pos -> QPointF
                # delta -> QPointF
                new_pos = self.element_start_pos + delta # Просто складываем
                
                self.element_moved.emit(self.selected_element_id, int(new_pos.x()), int(new_pos.y()))

        def mouseReleaseEvent(self, event):
            self.drag_mode = None

        def wheelEvent(self, event):
            zoom = 1.0 + (event.angleDelta().y() / 1200.0)
            self.zoom_factor = max(0.1, min(3.0, self.zoom_factor * zoom))
            self.update()

        def show_context_menu(self, pos):
            menu = QMenu(self)
            menu.addAction("Add Element").triggered.connect(self.request_add_element)
            menu.addAction("Refresh").triggered.connect(lambda: self.parent().parent().parent().load_from_blender())
            menu.exec(self.mapToGlobal(pos))
            
        def request_add_element(self):
            try:
                win = self.window()
                if hasattr(win, "show_add_element_dialog"):
                    win.show_add_element_dialog()
            except: pass

if qt_available:
    class QTEditorWindow(QMainWindow):
        def __init__(self, context):
            super().__init__()
            self.context = context
            self.setWindowTitle("RZMenu QT Editor (Stable)")
            self.resize(1200, 800)
            self.elements_data = []
            self.canvas_size = (1920, 1080)

            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)

            self.canvas = CanvasWidget(self)
            layout.addWidget(self.canvas)

            btn_layout = QHBoxLayout()
            refresh_btn = QPushButton("Refresh Data")
            refresh_btn.clicked.connect(self.load_from_blender)
            add_btn = QPushButton("Add Element")
            add_btn.clicked.connect(self.show_add_element_dialog)
            
            btn_layout.addWidget(refresh_btn)
            btn_layout.addWidget(add_btn)
            layout.addLayout(btn_layout)

            self.canvas.element_moved.connect(self.on_elem_moved)
            self.load_from_blender()

        def load_from_blender(self):
            print("\n--- Loading from Blender ---")
            try:
                rzm = self.context.scene.rzm
                self.elements_data = []
                
                for i, elem in enumerate(rzm.elements):
                    try:
                        pos = tuple(elem.position)
                        size = tuple(elem.size)
                        color = tuple(elem.color)
                        
                        d = {
                            'id': elem.id,
                            'name': elem.element_name,
                            'class': elem.elem_class,
                            'pos': QPointF(pos[0], pos[1]),
                            'size': QSizeF(size[0], size[1]),
                            'position': pos,
                            'color': color
                        }
                        self.elements_data.append(d)
                    except Exception as e:
                        print(f"Error loading element index {i}: {e}")
                        # traceback.print_exc()

                self.canvas.set_canvas_data(self.canvas_size, self.elements_data)
                print(f"Successfully loaded {len(self.elements_data)} elements.")
                
            except Exception as e:
                print(f"CRITICAL LOAD ERROR: {e}")
                QMessageBox.critical(self, "Load Error", f"Failed to load data:\n{e}")

        def on_elem_moved(self, eid, x, y):
            for e in self.elements_data:
                if e['id'] == eid:
                    e['pos'] = QPointF(x, y)
                    e['position'] = (x, y)
                    break
            self.canvas.update()
            self.schedule_update(eid, 'position', (x, y))

        def schedule_update(self, eid, prop, val):
            if self.context:
                func = functools.partial(self._blender_update, eid, prop, val)
                bpy.app.timers.register(func, first_interval=0.01)

        def _blender_update(self, eid, prop, val):
            try:
                found = False
                for el in self.context.scene.rzm.elements:
                    if el.id == eid:
                        setattr(el, prop, val)
                        found = True
                        break
                if not found:
                    print(f"Warning: Element ID {eid} not found.")
            except Exception as e:
                print(f"Update Error: {e}")
            return None

        def show_add_element_dialog(self):
            classes = ['CONTAINER', 'BUTTON', 'TEXT', 'IMAGE']
            item, ok = QInputDialog.getItem(self, "Add Element", "Class:", classes, 0, False)
            
            if ok and item:
                self.context.scene.rzm.element_to_add_class = item
                
                def run_op():
                    print("Executing Add Element Operator...")
                    try:
                        self.context.scene.rzm_active_element_index = -1 
                        bpy.ops.rzm.add_element()
                        self.load_from_blender()
                    except Exception as e:
                        print(f"Operator Fail: {e}")
                    return None
                
                bpy.app.timers.register(run_op, first_interval=0.1)

# --- LAUNCHER ---
qt_editor_window = None

def launch_qt_editor(context):
    global qt_editor_window
    
    if not qt_available:
        print("Launcher: Qt not available.")
        return None

    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    
    if qt_editor_window:
        try:
            qt_editor_window.close()
        except: pass

    try:
        qt_editor_window = QTEditorWindow(context)
        qt_editor_window.show()
        return qt_editor_window
    except Exception as e:
        print(f"Launcher Crash: {e}")
        traceback.print_exc()
        return None