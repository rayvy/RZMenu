# RZMenu/ui/inspector.py
# Точный инспектор. Читает весь rzm-контекст и выводит Elements как иерархию.

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    class QtWidgets: QWidget=object; QVBoxLayout=object; QScrollArea=object; QLabel=object; QFormLayout=object

class RZMInspectorWindow(QtWidgets.QWidget):
    """Окно, которое показывает все rzm-данные в виде иерархического списка."""
    def __init__(self, context):
        super().__init__()
        self.setWindowTitle("RZ Hierarchical Inspector")
        self.resize(500, 700)
        self.context = context
        
        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        
        self.content_widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.main_layout.setAlignment(QtCore.Qt.AlignTop)
        
        self.scroll_area.setWidget(self.content_widget)
        
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.addWidget(self.scroll_area)
        
        self.load_from_blender()

    def add_line(self, text, indent=0, bold=False):
        """Вспомогательная функция для добавления строки с отступом."""
        label = QtWidgets.QLabel('    ' * indent + text)
        if bold:
            label.setStyleSheet("font-weight: bold;")
        self.main_layout.addWidget(label)

    def load_from_blender(self):
        """Считывает все данные и строит иерархическое представление."""
        
        # Очищаем старое содержимое
        while self.main_layout.count():
            child = self.main_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        rzm = self.context.scene.rzm

        # --- 1. Отображаем Config ---
        self.add_line("--- Config ---", bold=True)
        if rzm.config:
            self.add_line(f"Canvas Size: {tuple(rzm.config.canvas_size)}", 1)
        self.add_line(" ") # Отступ

        # --- 2. Отображаем Toggles ---
        self.add_line("--- Toggles ---", bold=True)
        if rzm.toggles:
            for i, toggle in enumerate(rzm.toggles):
                self.add_line(f"[{i}] {toggle.toggle_name}", 1)
        self.add_line(" ")

        # --- 3. Отображаем Elements в виде иерархии ---
        self.add_line("--- Elements (Hierarchy) ---", bold=True)
        
        all_elements = list(rzm.elements)
        elements_by_id = {elem.id: elem for elem in all_elements}
        
        # Рекурсивная функция для отображения элемента и его детей
        def display_element_recursively(element, indent_level):
            # Показываем сам элемент
            parent_info = f" (Parent ID: {element.parent_id})" if element.parent_id != -1 else " (ROOT)"
            self.add_line(f"ID: {element.id} | '{element.element_name}'{parent_info}", indent_level, bold=True)
            self.add_line(f"Class: '{element.elem_class}'", indent_level + 1)
            self.add_line(f"Position: {tuple(element.position)} | Size: {tuple(element.size)}", indent_level + 1)
            
            # Показываем его детей
            children = [e for e in all_elements if e.parent_id == element.id]
            for child in children:
                display_element_recursively(child, indent_level + 1)

        # Находим и запускаем отрисовку для всех корневых элементов
        root_elements = [elem for elem in all_elements if elem.parent_id == -1 or elem.parent_id not in elements_by_id]
        for root in root_elements:
            display_element_recursively(root, 1)
            self.add_line("- " * 20) # Разделитель между деревьями

        print(f"Inspector refreshed. Displayed full rzm context.")

    def closeEvent(self, event):
        event.accept()