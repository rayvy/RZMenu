# RZMenu/core/svg_loader.py
import numpy as np
from PySide6 import QtGui, QtCore, QtSvg

def render_svg_to_pixels(filepath: str, width: int, height: int, tint_color: str = None) -> np.ndarray:
    """
    Renders an SVG file to a numpy RGBA array (float32, [0..1]).
    
    Args:
        filepath: Path to the .svg file.
        width: Target width in pixels.
        height: Target height in pixels.
        tint_color: Optional hex color (e.g. "#FF0000") to tint the entire SVG.
        
    Returns:
        numpy.ndarray of shape (height, width, 4) in float32.
    """
    try:
        svg_data = None
        if tint_color:
            import re
            with open(filepath, 'r', encoding='utf-8') as f:
                svg_data = f.read()
            
            # Simple tinting: inject fill into <svg> tag if not present, or replace currentColor
            if 'currentColor' in svg_data:
                svg_data = svg_data.replace('currentColor', tint_color)
            else:
                svg_data = re.sub(r'<svg([^>]*)>', rf'<svg\1 fill="{tint_color}">', svg_data)
        
        renderer = QtSvg.QSvgRenderer()
        if svg_data:
            renderer.load(QtCore.QByteArray(svg_data.encode('utf-8')))
        else:
            renderer.load(filepath)
            
        if not renderer.isValid():
            print(f"[SVG Loader] Error: Invalid SVG file at {filepath}")
            return None

        # Create QImage and render
        image = QtGui.QImage(width, height, QtGui.QImage.Format_RGBA8888)
        image.fill(QtCore.Qt.transparent)
        
        painter = QtGui.QPainter(image)
        renderer.render(painter)
        painter.end()
        
        # Convert QImage to numpy array
        # QImage format is RGBA8888, which is [R, G, B, A] bytes
        ptr = image.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))
        
        # Normalize to float32 [0..1] as expected by our atlas packer
        return arr.astype(np.float32) / 255.0

    except Exception as e:
        print(f"[SVG Loader] Critical error rendering {filepath}: {e}")
        return None
