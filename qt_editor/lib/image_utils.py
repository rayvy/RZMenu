# RZMenu/qt_editor/lib/image_utils.py

import os
import bpy
import numpy as np
from PySide6 import QtGui, QtCore

# Simple memory cache for thumbnails and metadata
_thumbnail_cache = {} # {cache_key: {"pixmap": QPixmap, "colorspace": str}}

# Centralized filename registry: {filename: absolute_path}
_filename_registry = {}
_blender_lock = QtCore.QMutex() # Serialize Blender API calls from threads

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
    exts = ('.dds', '.png', '.jpg', '.jpeg', '.tga', '.bmp', '.hlsl')
    img_exts = ('.dds', '.png', '.jpg', '.jpeg', '.tga', '.bmp')
    
    if recursive:
        for root, dirs, files in os.walk(target_dir):
            for f in files:
                if f.lower().endswith(img_exts):
                    full_path = os.path.join(root, f)
                    results.append(full_path)
                    # Register by filename for central lookup
                    _filename_registry[f.lower()] = full_path
    else:
        for f in os.listdir(target_dir):
            if f.lower().endswith(img_exts):
                full_path = os.path.join(target_dir, f)
                results.append(full_path)
                _filename_registry[f.lower()] = full_path
                
    return results

def get_dds_format(filepath):
    """Minimal DDS header parser for DXGI formats."""
    if not filepath.lower().endswith('.dds'):
        # For non-DDS, return uppercase extension (e.g., PNG, TGA)
        _, ext = os.path.splitext(filepath)
        if ext:
            return ext[1:].upper()
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
                    61: "BC2 (DXT3)", 71: "BC1 (DXT1)",
                    87: "B8G8R8A8 (UNORM)"
                }
                return dxgi_map.get(dxgi, f"DXGI:{dxgi}")
            
            if fourcc == b'DXT1': return "BC1 (DXT1)"
            if fourcc == b'DXT3': return "BC2 (DXT3)"
            if fourcc == b'DXT5': return "BC3 (DXT5)"
            if fourcc == b'ATI2': return "BC5 (ATI2)"
            
            decoded = fourcc.decode('ascii', errors='ignore').strip()
            if not decoded:
                return "Uncompressed/RAW"
            return decoded
    except Exception as e:
        print(f"DDS read error: {e}")
        return "Error"

def load_texture_data(filepath, max_size=128):
    """Loads a texture via Blender and returns its cached info dict (pixmap, colorspace)."""
    # Resolve path first!
    filepath = resolve_path(filepath)
    
    if not filepath or not os.path.exists(filepath):
        return {"pixmap": get_placeholder_pixmap("EMPTY", max_size), "colorspace": "Unknown"}
    
    # Check cache
    mtime = os.path.getmtime(filepath)
    cache_key = f"{filepath}_{mtime}_{max_size}"
    if cache_key in _thumbnail_cache:
        return _thumbnail_cache[cache_key]

    colorspace = "Unknown"
    
    try:
        # Load through blender to support DDS and extract reliable colorspace
        bl_img = bpy.data.images.load(filepath, check_existing=True)
        if not bl_img: 
            return {"pixmap": get_placeholder_pixmap("ERROR", max_size), "colorspace": colorspace}
        
        # Grab colorspace
        colorspace = bl_img.colorspace_settings.name
        
        w, h = bl_img.size
        if w <= 0 or h <= 0: 
            return {"pixmap": get_placeholder_pixmap("EMPTY", max_size), "colorspace": colorspace}
        
        num_pixels = w * h * 4
        raw_pixels = np.empty(num_pixels, dtype=np.float32)
        bl_img.pixels.foreach_get(raw_pixels)
        
        pixels_uint8 = (raw_pixels * 255).astype(np.uint8)
        pixels_reshaped = pixels_uint8.reshape((h, w, 4))
        pixels_flipped = np.flipud(pixels_reshaped) # Blender's origin is bottom-left
        
        final_buffer = np.require(pixels_flipped, requirements=['C'])
        q_image = QtGui.QImage(final_buffer.data, w, h, 4 * w, QtGui.QImage.Format_RGBA8888).copy()
        
        pix = QtGui.QPixmap.fromImage(q_image)
        scaled_pix = pix.scaled(max_size, max_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        
        data = {"pixmap": scaled_pix, "colorspace": colorspace}
        _thumbnail_cache[cache_key] = data
        return data
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {"pixmap": get_placeholder_pixmap("ERROR", max_size), "colorspace": colorspace}

def load_texture_to_pixmap(filepath, max_size=128):
    """Legacy wrapper to just get the pixmap."""
    return load_texture_data(filepath, max_size)["pixmap"]

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

def get_total_block_preview(layers, canvas_res=(2048, 2048), size=256):
    """
    Composites multiple layers into one preview.
    layers: list of {"rect": (x,y,w,h), "path": str, "is_decal": bool, "opacity": float}
    """
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pix)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    
    # Fill background with a dark mesh-like pattern or just dark gray
    painter.fillRect(0, 0, size, size, QtGui.QColor(25, 27, 32))
    
    cw, ch = canvas_res
    if cw <= 0: cw = 2048
    if ch <= 0: ch = 2048
    
    scale_x = size / cw
    scale_y = size / ch
    
    for layer in layers:
        rx, ry, rw, rh = layer.get("rect", (0, 0, cw, ch))
        path = layer.get("path", "")
        opacity = layer.get("opacity", 1.0)
        
        # Scale to preview size
        px = rx * scale_x
        py = (ch - ry - rh) * scale_y # Flip Y for preview
        pw = rw * scale_x
        ph = rh * scale_y
        
        painter.setOpacity(opacity)
        
        if path:
            # Try to get from cache or load tiny version
            # Note: For atlas preview, we use a slightly larger thumb if possible
            img_data = load_texture_data(path, max_size=128)
            l_pix = img_data.get("pixmap")
            if l_pix:
                painter.drawPixmap(QtCore.QRectF(px, py, pw, ph), l_pix, QtCore.QRectF(l_pix.rect()))
            else:
                painter.fillRect(QtCore.QRectF(px, py, pw, ph), QtGui.QColor(60, 60, 70, 100))
        else:
            # Schematic rect
            color = QtGui.QColor(80, 120, 200, 100) if not layer.get("is_decal") else QtGui.QColor(200, 100, 100, 100)
            painter.fillRect(QtCore.QRectF(px, py, pw, ph), color)
            
        # Draw border
        painter.setOpacity(1.0)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 40), 1))
        painter.drawRect(QtCore.QRectF(px, py, pw, ph))

    painter.end()
    return pix

def collect_block_preview_data(block):
    """
    Safely extracts layout data from a Blender Block object for the previewer.
    Must be called from main thread.
    """
    data = {
        "res": (2048, 2048), # Default
        "layers": []
    }
    
    # 1. Backdrop
    if block.backdrop_enabled:
        path = get_resource_path(block.backdrop_resource_name)
        data["layers"].append({"rect": list(block.backdrop_rect), "path": path, "is_decal": False, "opacity": 1.0})
    
    # 2. Components & Slots
    for comp in block.components:
        comp_path = get_resource_path(comp.base_resource_name)
        data["layers"].append({"rect": list(comp.rect), "path": comp_path, "is_decal": False, "opacity": 0.8})
        
        for slot in comp.slots:
            if not slot.active: continue
            # Slots currently don't have a direct resource linked in the property group,
            # they seem to be UV regions for decals.
            data["layers"].append({"rect": list(slot.rect), "path": "", "is_decal": True, "opacity": 0.9})
            
    return data

def resolve_path(path):
    """Tries to locate a file on disk using multiple strategies and the registry."""
    if not path: return ""
    
    # Try 1: Exact path or Absolute
    if os.path.isabs(path) and os.path.exists(path):
        return path
    
    # Try 2: Relative to Mod Root
    base = get_mod_base_path()
    if base:
        p2 = os.path.join(base, path)
        if os.path.exists(p2): return p2
        
        # Try 3: Relative to ModRoot/Textures (Common usage)
        p3 = os.path.join(base, "Textures", path)
        if os.path.exists(p3): return p3

    # Try 4: In current working directory or fallbacks
    if os.path.exists(path): return path
    
    # Try 5: Check Filename Registry (Fallback for simple filenames)
    fname = os.path.basename(path).lower()
    if fname in _filename_registry:
        reg_path = _filename_registry[fname]
        if os.path.exists(reg_path):
            return reg_path
            
    return ""

def get_resource_path(resource_name):
    """Helper to get exact absolute path from resource name."""
    rzm = bpy.context.scene.rzm
    res = next((r for r in rzm.tw_resources if r.name == resource_name), None)
    if res and res.type == 'ON_DISK':
        return resolve_path(res.path)
    return ""

class ThumbnailWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        finished = QtCore.Signal(dict)

    def __init__(self, path, max_size):
        super().__init__()
        self.path = path
        self.max_size = max_size
        self.signals = self.Signals()

    def run(self):
        try:
            # Blender API is not thread-safe. Serialize access.
            _blender_lock.lock()
            try:
                data = load_texture_data(self.path, self.max_size)
            finally:
                _blender_lock.unlock()
            self.signals.finished.emit(data)
        except Exception as e:
            print(f"[AsyncImageLoader] Error: {e}")
            self.signals.finished.emit({"pixmap": get_placeholder_pixmap("EMPTY", self.max_size), "colorspace": "Error"})

class AsyncImageLoader(QtCore.QObject):
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AsyncImageLoader()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.pool = QtCore.QThreadPool.globalInstance()
        self.active_requests = {} # {widget_id: path}

    def load_async(self, path, max_size, callback):
        """Loads a texture in background and calls callback(data)."""
        # 1. Check Cache first
        resolved = resolve_path(path)
        if resolved in _thumbnail_cache:
            callback(_thumbnail_cache[resolved])
            return

        # 2. Start Background Task
        worker = ThumbnailWorker(resolved, max_size)
        worker.signals.finished.connect(callback)
        self.pool.start(worker)

