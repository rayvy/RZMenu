# RZMenu/core/svg_loader.py
import numpy as np
from PySide6 import QtGui, QtCore, QtSvg

def _resize_rgba_bilinear(pixels: np.ndarray, width: int, height: int) -> np.ndarray:
    src_h, src_w = pixels.shape[:2]
    if src_w == width and src_h == height:
        return pixels.copy()
    if width <= 0 or height <= 0 or src_w <= 0 or src_h <= 0:
        return None

    x = np.linspace(0, src_w - 1, width, dtype=np.float32)
    y = np.linspace(0, src_h - 1, height, dtype=np.float32)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(x0 + 1, src_w - 1)
    y1 = np.minimum(y0 + 1, src_h - 1)
    wx = (x - x0)[None, :, None]
    wy = (y - y0)[:, None, None]

    top = pixels[y0[:, None], x0[None, :]] * (1.0 - wx) + pixels[y0[:, None], x1[None, :]] * wx
    bottom = pixels[y1[:, None], x0[None, :]] * (1.0 - wx) + pixels[y1[:, None], x1[None, :]] * wx
    return (top * (1.0 - wy) + bottom * wy).astype(np.float32)

def _parse_hex_color(tint_color: str):
    if not tint_color:
        return None
    color = tint_color.strip()
    if color.startswith("#"):
        color = color[1:]
    if len(color) != 6:
        return None
    try:
        return np.array([int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)
    except ValueError:
        return None

def blender_image_to_pixels(bl_image, width: int, height: int, tint_color: str = None) -> np.ndarray:
    """
    Converts a packed Blender image preview into a top-down RGBA array.
    Used as a fallback when an SVG source file is missing but its packed preview
    still exists inside the .blend file.
    """
    if bl_image is None or width <= 0 or height <= 0:
        return None

    try:
        src_w, src_h = [int(v) for v in bl_image.size]
        if src_w <= 0 or src_h <= 0:
            return None

        old_colorspace = bl_image.colorspace_settings.name
        if old_colorspace != 'Non-Color':
            bl_image.colorspace_settings.name = 'Non-Color'

        try:
            raw = np.empty(src_w * src_h * 4, dtype=np.float32)
            bl_image.pixels.foreach_get(raw)
        finally:
            if old_colorspace != 'Non-Color':
                bl_image.colorspace_settings.name = old_colorspace

        # Blender image pixels are bottom-up. Atlas SVG input expects top-down.
        pixels = np.flipud(raw.reshape((src_h, src_w, 4)))
        pixels = _resize_rgba_bilinear(pixels, width, height)
        if pixels is None:
            return None

        rgb = _parse_hex_color(tint_color)
        if rgb is not None:
            pixels[..., :3] = rgb

        return np.clip(pixels, 0.0, 1.0).astype(np.float32)
    except Exception as e:
        print(f"[SVG Loader] Critical error reading Blender preview '{getattr(bl_image, 'name', '<None>')}': {e}")
        return None

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
