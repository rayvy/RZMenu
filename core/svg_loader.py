# RZMenu/core/svg_loader.py
import numpy as np
from PySide6 import QtGui, QtCore, QtSvg

def render_svg_to_pixels(filepath: str, width: int, height: int, tint_color: str = None, scale: float = 1.0, offset: tuple = (0, 0)) -> np.ndarray:
    """
    Renders an SVG file to a numpy RGBA array (float32, [0..1]) with scale and offset.
    
    Args:
        filepath: Path to the .svg file.
        width: Target width in pixels (buffer size).
        height: Target height in pixels (buffer size).
        tint_color: Optional hex color (e.g. "#FF0000") to tint the entire SVG.
        scale: Scale multiplier (relative to buffer size).
        offset: (X, Y) pixel offset relative to center.
        
    Returns:
        numpy.ndarray of shape (height, width, 4) in float32.
    """
    try:
        renderer = QtSvg.QSvgRenderer(filepath)
            
        if not renderer.isValid():
            print(f"[SVG Loader] Error: Invalid SVG file at {filepath}")
            return None

        # Create QImage and render
        image = QtGui.QImage(width, height, QtGui.QImage.Format_RGBA8888)
        image.fill(QtCore.Qt.transparent)
        
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        
        # Calculate target rect
        # Center of the buffer:
        sw, sh = width * scale, height * scale
        target_rect = QtCore.QRectF(
            (width - sw) / 2.0 + offset[0],
            (height - sh) / 2.0 + offset[1],
            sw, sh
        )
        
        renderer.render(painter, target_rect)
        
        if tint_color:
            # Apply tint using SourceIn composition
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
            painter.fillRect(image.rect(), QtGui.QColor(tint_color))
            
        painter.end()
        
        # Convert QImage to numpy array
        ptr = image.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))
        
        return arr.astype(np.float32) / 255.0

    except Exception as e:
        print(f"[SVG Loader] Critical error rendering {filepath}: {e}")
        return None

    except Exception as e:
        print(f"[SVG Loader] Critical error rendering {filepath}: {e}")
        return None
