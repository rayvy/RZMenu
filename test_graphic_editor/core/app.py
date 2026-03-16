import sys
import os

# Add parent directory to sys.path to allow absolute imports within the project if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMainWindow, QDockWidget, QListWidget, QVBoxLayout, QWidget, QStatusBar, QFileDialog, QToolBar, QSlider, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QSize
from managers.context_manager import ContextManager
from managers.input_manager import InputManager
from managers.file_manager import FileManager
from core.canvas import VectorCanvas

class GraphicEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vector Graphic Editor - Standalone")
        self.resize(1200, 800)
        
        # Managers
        self.context = ContextManager()
        self.input_manager = InputManager(self.context)
        self.file_manager = FileManager()
        
        # Central Canvas
        self.canvas = VectorCanvas()
        self.setCentralWidget(self.canvas)
        
        # Toolbar & Menus
        self._create_menus()
        self._create_toolbars()
        
        # Connect signals
        self.input_manager.stroke_updated.connect(self.on_stroke_updated)
        
        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.init_ui()

    def _create_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        
        open_act = file_menu.addAction("&Open...")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_file)
        
        save_act = file_menu.addAction("&Save as...")
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_file)

    def _create_toolbars(self):
        brush_toolbar = QToolBar("Brush Settings")
        brush_toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(brush_toolbar)
        
        # Brush Size
        brush_toolbar.addWidget(QLabel(" Size: "))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 200)
        self.size_slider.setValue(int(self.canvas.brush.size))
        self.size_slider.setFixedWidth(100)
        self.size_slider.valueChanged.connect(self.update_brush_params)
        brush_toolbar.addWidget(self.size_slider)
        
        # Hardness
        brush_toolbar.addWidget(QLabel(" Hardness: "))
        self.hardness_slider = QSlider(Qt.Horizontal)
        self.hardness_slider.setRange(0, 100)
        self.hardness_slider.setValue(int(self.canvas.brush.hardness * 100))
        self.hardness_slider.setFixedWidth(100)
        self.hardness_slider.valueChanged.connect(self.update_brush_params)
        brush_toolbar.addWidget(self.hardness_slider)

    def update_brush_params(self):
        self.canvas.brush.size = float(self.size_slider.value())
        self.canvas.brush.hardness = self.hardness_slider.value() / 100.0
        self.status_bar.showMessage(f"Brush: {self.canvas.brush.size}px, {int(self.canvas.brush.hardness*100)}% hardness")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.bmp *.dds);;All Files (*)")
        if path:
            if path.lower().endswith('.dds'):
                img = self.file_manager.load_dds(path)
                if img:
                    self.canvas.doc.get_active_layer().raster_data = img
                    self.canvas._update_scene()
            else:
                img = QImage(path)
                if not img.isNull():
                    self.canvas.doc.get_active_layer().raster_data = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
                    self.canvas._update_scene()

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "PNG (*.png);;DDS (*.dds)")
        if path:
            img = self.canvas.doc.get_active_layer().raster_data
            if path.lower().endswith('.dds'):
                self.file_manager.save_dds(img, path)
            else:
                img.save(path)

    def on_stroke_updated(self, data):
        """Handle stroke data from input manager."""
        pressure = data.get("pressure", 1.0)
        pos = data.get("pos", (0, 0))
        self.status_bar.showMessage(f"Input: {pos} | Pressure: {pressure:.2f}")

    def init_ui(self):
        # Tools Dock
        tools_dock = QDockWidget("Tools", self)
        tools_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        tools_list = QListWidget()
        tools_list.addItems(["Select", "Pen", "Brush", "Rectangle", "Ellipse"])
        tools_dock.setWidget(tools_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, tools_dock)
        
        # Layers Dock
        layers_dock = QDockWidget("Layers", self)
        layers_list = QListWidget()
        layers_list.addItem("Background")
        layers_dock.setWidget(layers_list)
        self.addDockWidget(Qt.RightDockWidgetArea, layers_dock)
        
        # Inspector Dock
        inspector_dock = QDockWidget("Inspector", self)
        inspector_content = QWidget()
        inspector_layout = QVBoxLayout()
        inspector_content.setLayout(inspector_layout)
        inspector_dock.setWidget(inspector_content)
        self.addDockWidget(Qt.RightDockWidgetArea, inspector_dock)

def main():
    app = QApplication(sys.argv)
    window = GraphicEditorWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
