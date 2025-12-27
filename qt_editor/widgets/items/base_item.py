#RZMenu/qt_editor/widgets/items/base_item.py
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtCore import Qt, QRectF

class RZElementItem(QGraphicsRectItem):
    def __init__(self, data, parent=None):
        # Position is top-left corner
        # Ensure that pos_x, pos_y, width, height are numbers
        x = float(data.get('pos_x', 0))
        y = float(data.get('pos_y', 0))
        width = float(data.get('width', 100))
        height = float(data.get('height', 50))
        super().__init__(x, y, width, height, parent)

        self.data = data
        self.setFlags(QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemIsSelectable)

        self._set_color_by_type(data.get('type', 'Unknown'))
        
        # Text Label
        self.text_label = QGraphicsTextItem(self.data.get('name', ''), self)
        self.text_label.setFont(QFont("Arial", 8))
        self.text_label.setDefaultTextColor(QColor("#eeeeee")) # Set text color
        # Center the text within the item
        text_width = self.text_label.boundingRect().width()
        text_height = self.text_label.boundingRect().height()
        self.text_label.setPos(x + (width / 2) - (text_width / 2), y + (height / 2) - (text_height / 2))

    def _set_color_by_type(self, element_type):
        color = QColor("#555555") # Default Gray
        if element_type == "CONTAINER": # Use uppercase as per Blender's enum convention
            color = QColor("#666666")
        elif element_type == "BUTTON":
            color = QColor("#4772b3") # Blender Blue
        elif element_type == "IMAGE":
            color = QColor("#4CAF50") # Green
        elif element_type == "LABEL":
            color = QColor("#FFC107") # Amber
        
        self.setBrush(QBrush(color))

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(self.brush().color().lighter(120))) # Make it 20% lighter on hover
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._set_color_by_type(self.data.get('type', 'Unknown')) # Reset color on leave
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        print(f"Element Clicked: {self.data.get('name')}") # Debug print on click
        super().mousePressEvent(event)