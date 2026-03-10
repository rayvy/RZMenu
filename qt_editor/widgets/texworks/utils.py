# RZMenu/qt_editor/widgets/texworks/utils.py

import os
import bpy
import numpy as np
from PySide6 import QtGui, QtCore

# Simple memory cache for thumbnails
_thumbnail_cache = {} # {filepath_or_key: QPixmap}

def get_mod_base_path():
    """Returns the custom path from export settings."""
    try:
        return bpy.context.scene.rzm.export_settings.custom_path
    except:
        return ""

def scan_textures(base_path, subfolder="Textures", recursive=False):
    """Scans for images in the mod folder."""
    target_dir = os.path.join(base_path, subfolder)
    print(f"RZMenu: Scanning directory: {target_dir}")
    if not os.path.exists(target_dir):
        print(f"RZMenu: Directory not found: {target_dir}")
        return []
        
    results = []
    exts = ('.dds', '.png', '.jpg', '.jpeg', '.tga', '.bmp', '.hlsl') # hlsl just in case? No, only images
    img_exts = ('.dds', '.png', '.jpg', '.jpeg', '.tga', '.bmp')
    
    if recursive:
        for root, dirs, files in os.walk(target_dir):
            for f in files:
                if f.lower().endswith(img_exts):
                    results.append(os.path.join(root, f))
    else:
        for f in os.listdir(target_dir):
            if f.lower().endswith(img_exts):
                results.append(os.path.join(target_dir, f))
                
    return results

def get_dds_format(filepath):
    """Minimal DDS header parser for DXGI formats."""
    if not filepath.lower().endswith('.dds'):
        return "Standard"
        
    try:
        with open(filepath, 'rb') as f:
            header = f.read(148)
            if len(header) < 128: return "Unknown"
            magic = header[0:4]
            if magic != b'DDS ': return "Not DDS"
            fourcc = header[84:88]
            
            if fourcc == b'DX10':
                dxgi = int.from_bytes(header[128:132], 'little')
                dxgi_map = {
                    98: "BC7 (UNORM)", 99: "BC7 (SRGB)",
                    83: "BC5 (Red-Green)", 80: "BC4 (Red)",
                    71: "BC3 (DXT5)", 77: "BC3 (SNORM)",
                    61: "BC2 (DXT3)", 71: "BC1 (DXT1)"
                }
                return dxgi_map.get(dxgi, f"DXGI:{dxgi}")
            
            if fourcc == b'DXT1': return "BC1 (DXT1)"
            if fourcc == b'DXT3': return "BC2 (DXT3)"
            if fourcc == b'DXT5': return "BC3 (DXT5)"
            if fourcc == b'ATI2': return "BC5 (ATI2)"
            return fourcc.decode('ascii', errors='ignore').strip()
    except:
        return "Error"

def load_texture_to_pixmap(filepath, max_size=128):
    """Loads a texture through Blender pixels and returns a QPixmap thumbnail."""
    if not filepath or not os.path.exists(filepath):
        return get_placeholder_pixmap("EMPTY", max_size)
    
    # Check cache
    mtime = os.path.getmtime(filepath)
    cache_key = f"{filepath}_{mtime}_{max_size}"
    if cache_key in _thumbnail_cache:
        return _thumbnail_cache[cache_key]

    try:
        bl_img = bpy.data.images.load(filepath, check_existing=True)
        if not bl_img: return get_placeholder_pixmap("ERROR", max_size)
        
        w, h = bl_img.size
        if w <= 0 or h <= 0: return get_placeholder_pixmap("EMPTY", max_size)
        
        num_pixels = w * h * 4
        raw_pixels = np.empty(num_pixels, dtype=np.float32)
        bl_img.pixels.foreach_get(raw_pixels)
        
        pixels_uint8 = (raw_pixels * 255).astype(np.uint8)
        pixels_reshaped = pixels_uint8.reshape((h, w, 4))
        pixels_flipped = np.flipud(pixels_reshaped)
        
        final_buffer = np.require(pixels_flipped, requirements=['C'])
        q_image = QtGui.QImage(final_buffer.data, w, h, 4 * w, QtGui.QImage.Format_RGBA8888).copy()
        
        pix = QtGui.QPixmap.fromImage(q_image)
        scaled_pix = pix.scaled(max_size, max_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        
        _thumbnail_cache[cache_key] = scaled_pix
        return scaled_pix
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return get_placeholder_pixmap("ERROR", max_size)

def get_placeholder_pixmap(ptype, size=128, format_id=None):
    """Generates a placeholder image for virtual or missing textures."""
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.black)
    
    painter = QtGui.QPainter(pix)
    
    if ptype == "VIRTUAL":
        # Draw 4 colored squares
        is_bc5 = format_id == 'DXGI_FORMAT_R8G8_TYPELESS'
        
        if is_bc5:
            # Yellow shades for BC5
            colors = [QtGui.QColor(255, 255, 0), QtGui.QColor(200, 200, 0), 
                      QtGui.QColor(150, 150, 0), QtGui.QColor(100, 100, 0)]
        else:
            # Grey/Blue shades for others
            colors = [QtGui.QColor(60, 60, 80), QtGui.QColor(80, 80, 100), 
                      QtGui.QColor(100, 100, 120), QtGui.QColor(120, 120, 140)]
        
        hs = size // 2
        painter.fillRect(0, 0, hs, hs, colors[0])
        painter.fillRect(hs, 0, hs, hs, colors[1])
        painter.fillRect(0, hs, hs, hs, colors[2])
        painter.fillRect(hs, hs, hs, hs, colors[3])
    
    elif ptype == "ERROR":
        painter.setPen(QtGui.QPen(QtCore.Qt.red, 2))
        painter.drawLine(0, 0, size, size)
        painter.drawLine(size, 0, 0, size)
        
    painter.end()
    return pix

def get_total_block_preview(block, size=256):
    """Composites backdrop and components into one preview."""
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.black)
    painter = QtGui.QPainter(pix)
    
    # 1. Backdrop
    if block.backdrop_enabled:
        b_pix = load_texture_to_pixmap(get_resource_path(block.backdrop_resource_name), size)
        if b_pix: painter.drawPixmap(0, 0, b_pix)
    
    # 2. Components (Reverse order for layering? Or normal?)
    for comp in block.components:
        c_pix = load_texture_to_pixmap(get_resource_path(comp.base_resource_name), size)
        if c_pix:
            # Simple alpha blending for now
            painter.setOpacity(0.7) # Placeholder for better blending
            painter.drawPixmap(0, 0, c_pix)
            
    painter.end()
    return pix

def get_resource_path(resource_name):
    """Helper to get path from resource name."""
    rzm = bpy.context.scene.rzm
    res = next((r for r in rzm.tw_resources if r.name == resource_name), None)
    if res and res.type == 'ON_DISK':
        base = get_mod_base_path()
        path = res.path
        if not path: return ""

        # Try 1: Exact path or Absolute
        if os.path.isabs(path) and os.path.exists(path):
            return path
        
        # Try 2: Relative to Mod Root
        if base:
            p2 = os.path.join(base, path)
            if os.path.exists(p2): return p2
            
            # Try 3: Relative to ModRoot/Textures (Common usage)
            p3 = os.path.join(base, "Textures", path)
            if os.path.exists(p3): return p3

        # Try 4: In current working directory or fallbacks?
        if os.path.exists(path): return path
        
    return ""
