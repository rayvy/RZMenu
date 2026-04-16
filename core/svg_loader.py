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
        
        # Convert QImage to numpy array safely
        # Ensure we use constBits to get a read-only pointer to the data
        ptr = image.constBits()
        # bytesPerLine is crucial if the image is not 32-bit aligned (though RGBA8888 usually is)
        stride = image.bytesPerLine()
        
        # Create a view from the buffer
        # Note: image.bits() returns a buffer that depends on the QImage's lifetime.
        # We immediately copy it with .astype() or np.array()
        raw_data = np.frombuffer(ptr, dtype=np.uint8)
        
        # Reshape considering the stride (bytes per line)
        # ch=4 for RGBA8888
        arr = raw_data.reshape((height, stride // 4, 4))
        # Crop potential padding at the end of scanlines
        if stride // 4 > width:
            arr = arr[:, :width, :]
        
        # Create an owned copy as float32 in [0..1] range
        return arr.astype(np.float32) / 255.0

    except Exception as e:
        print(f"[SVG Loader] Critical error rendering {filepath}: {e}")
        return None

    except Exception as e:
        print(f"[SVG Loader] Critical error rendering {filepath}: {e}")
        return None
