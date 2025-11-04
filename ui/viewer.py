# rz_gui_constructor/ui/viewer.py
# "Железобетонная" версия. Рисует иерархию. Устойчива к ошибкам и версиям.

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    # Заглушки, чтобы Blender не ругался
    class QtWidgets: QWidget = object; QVBoxLayout = object
    class QtCore: Qt = object; QRect = object; QPoint = object; QSize = object
    class QtGui: QPainter = object; QColor = object

class ViewerCanvas(QtWidgets.QWidget):
    """Виджет, который умеет рисовать переданные ему визуальные элементы."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.elements_to_draw = []

    def set_data(self, elements):
        self.elements_to_draw = elements
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(45, 45, 45))

        for elem in self.elements_to_draw:
            painter.setBrush(elem["color"])
            painter.setPen(QtCore.Qt.NoPen)
            rect = QtCore.QRect(elem["absolute_pos"], elem["size"])
            painter.drawRect(rect)
        
        painter.end()


class RZMViewerWindow(QtWidgets.QWidget):
    """Главное окно-просмотрщик."""
    def __init__(self, context):
        super().__init__()
        self.setWindowTitle("RZ Constructor Viewer (Concrete)")
        self.resize(1280, 720) # Размер по умолчанию
        self.context = context
        
        self.canvas = ViewerCanvas(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        
        self.load_from_blender()

    def load_from_blender(self):
        """
        Считывает иерархию из Blender и вычисляет абсолютные координаты для отрисовки.
        """
        blender_elements = self.context.scene.rzm.elements
        
        # 1. Быстрый доступ к элементам по их тегу
        elements_by_tag = {elem.tag: elem for elem in blender_elements if elem.tag}

        # 2. Кэш для хранения уже вычисленных абсолютных позиций
        position_cache = {}

        def get_absolute_position(element):
            """Рекурсивно вычисляет абсолютную позицию элемента."""
            if element.tag in position_cache:
                return position_cache[element.tag]

            # Используем getattr для безопасности
            local_pos = getattr(element, 'position', (0, 0))
            parent_tag = getattr(element, 'parent_tag', '')

            # Базовый случай: элемент верхнего уровня или его родитель не найден
            if not parent_tag or parent_tag not in elements_by_tag:
                abs_pos = QtCore.QPoint(local_pos[0], local_pos[1])
                position_cache[element.tag] = abs_pos
                return abs_pos

            # Рекурсивный случай: позиция родителя + своя относительная позиция
            parent = elements_by_tag[parent_tag]
            parent_abs_pos = get_absolute_position(parent)
            abs_pos = parent_abs_pos + QtCore.QPoint(local_pos[0], local_pos[1])
            
            if element.tag:
                position_cache[element.tag] = abs_pos
            return abs_pos

        # 3. Готовим финальный список элементов для отрисовки
        drawable_elements = []
        for elem in blender_elements:
            # Безопасно получаем данные
            size = getattr(elem, 'size', (0, 0))
            color = getattr(elem, 'color', (0.5, 0.5, 0.5, 1.0)) # Серый, если цвета нет

            drawable_elements.append({
                "absolute_pos": get_absolute_position(elem),
                "size": QtCore.QSize(size[0], size[1]),
                "color": QtGui.QColor.fromRgbF(*color)
            })
        
        # 4. Передаем данные на холст
        self.canvas.set_data(drawable_elements)
        print(f"Viewer refreshed. Rendered {len(drawable_elements)} hierarchical elements.")
        
    def closeEvent(self, event):
        event.accept()