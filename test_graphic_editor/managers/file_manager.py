import json
import os
from PySide6.QtGui import QImage

class FileManager:
    """Handles document I/O operations."""
    def __init__(self):
        pass

    def save_project(self, path, data):
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Project saved to {path}")

    def load_project(self, path):
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return json.load(f)

    def load_dds(self, path):
        """Loads a DDS file and returns a QImage."""
        from PIL import Image
        try:
            pil_img = Image.open(path)
            if pil_img.mode != 'RGBA':
                pil_img = pil_img.convert('RGBA')
            
            data = pil_img.tobytes("raw", "RGBA")
            qimage = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGBA8888)
            return qimage.copy() # Return a copy to ensure data persists
        except Exception as e:
            print(f"Error loading DDS: {e}")
            return None

    def save_dds(self, qimage: QImage, path):
        """Saves a QImage as a DDS file."""
        from PIL import Image
        buffer = qimage.bits()
        pil_img = Image.frombuffer("RGBA", (qimage.width(), qimage.height()), buffer, "raw", "RGBA", 0, 1)
        try:
            pil_img.save(path, format="DDS")
            return True
        except Exception as e:
            print(f"Error saving DDS: {e}")
            return False

    def export_image(self, scene, path, format="PNG"):
        # Logic to render scene to QImage and save
        pass
