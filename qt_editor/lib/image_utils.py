# RZMenu/qt_editor/lib/image_utils.py

import os
import bpy
import numpy as np
from PySide6 import QtGui, QtCore

# Simple memory cache for thumbnails
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
                    full_path = os.path.join(root, f).replace('\\', '/')
                    results.append(full_path)
                    _filename_registry[f.lower()] = full_path
    else:
        for f in os.listdir(target_dir):
            if f.lower().endswith(img_exts):
                full_path = os.path.join(target_dir, f).replace('\\', '/')
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
    
    try:
        mtime = os.path.getmtime(filepath)
        size = os.path.getsize(filepath)
        cache_key = f"{filepath}_{mtime}_{max_size}"
        
        if cache_key in _thumbnail_cache:
            return _thumbnail_cache[cache_key]
        
        # Check metadata cache for format/colorspace info
        # (REMOVED CACHE)
        colorspace = "Unknown" # Default if not loaded from Blender yet
        
        # Load through blender to support DDS and extract reliable colorspace
        bl_img = bpy.data.images.load(filepath, check_existing=True)
        if not bl_img: 
            return {"pixmap": get_placeholder_pixmap("ERROR", max_size), "colorspace": colorspace}
        
        # Grab/Update colorspace
        colorspace = bl_img.colorspace_settings.name
        
        # Load pixels
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
    
    elif ptype == "LOADING":
        painter.fillRect(0, 0, size, size, QtGui.QColor(35, 37, 42))
        painter.setPen(QtGui.QPen(QtGui.QColor(80, 80, 100), 2))
        font = painter.font(); font.setPointSize(size // 3); painter.setFont(font)
        painter.drawText(pix.rect(), QtCore.Qt.AlignCenter, "?")
        
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
        py = ry * scale_y  # 0,0 is Top-Left, no flip needed now
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
            
        painter.setOpacity(1.0)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 40), 1))
        painter.drawRect(QtCore.QRectF(px, py, pw, ph))
        
        # Draw "Pass" indicator if any
        pass_idx = layer.get("pass_idx", 0)
        if pass_idx > 0:
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 180), 1))
            font = painter.font(); font.setPointSize(min(10, max(6, int(ph/4)))); painter.setFont(font)
            painter.drawText(QtCore.QRectF(px + 2, py + 2, pw - 4, ph - 4), QtCore.Qt.AlignRight | QtCore.Qt.AlignTop, str(pass_idx + 1))

    painter.end()
    return pix

def collect_block_preview_data(block):
    """
    Safely extracts layout data from a Blender Block object for the previewer.
    Must be called from main thread.
    """
    rzm = bpy.context.scene.rzm
    res_name = block.resource_name
    canvas_res = (2048, 2048)
    
    # Try to find the output resource to get its resolution
    out_res = next((r for r in rzm.tw_resources if r.name == res_name), None)
    if out_res:
        canvas_res = (out_res.resolution[0], out_res.resolution[1])
    
    data = {
        "res": canvas_res,
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
        
        if comp.tex_morph_enabled:
            morph_path = get_resource_path(comp.tex_morph_resource_name)
            data["layers"].append({"rect": list(comp.rect), "path": morph_path, "is_decal": False, "opacity": 0.4}) # Blend
        
        for slot in comp.slots:
            if not slot.active: continue
            slot_path = "" # TexWorksSlot has no direct resource_name
            
            # Pass 0
            data["layers"].append({"rect": list(slot.rect), "path": slot_path, "is_decal": True, "opacity": 0.9, "pass_idx": 0})
            
            # Pass 1 (Multi-pass)
            if slot.multi_pass_mode != 'NONE':
                # Pass 1 usually uses the same texture as Pass 0 in many cases, 
                # or a dedicated decal if we add that later.
                data["layers"].append({"rect": list(slot.multi_pass_rect), "path": slot_path, "is_decal": True, "opacity": 0.6, "pass_idx": 1})
            
    return data

_resolved_path_cache = {} # {path_input: resolved_abspath}

def resolve_path(path):
    """Tries to locate a file on disk using multiple strategies and the registry."""
    if not path: return ""
    
    # 0. Check resolution cache
    if path in _resolved_path_cache:
        cached = _resolved_path_cache[path]
        # Quick validation (once per session or periodically)
        return cached

    # 1. Exact path or Absolute
    if os.path.isabs(path) and os.path.exists(path):
        _resolved_path_cache[path] = path
        return path
    
    # ... previous logic ...
    res_path = _do_resolve_path(path)
    _resolved_path_cache[path] = res_path
    return res_path

def _do_resolve_path(path):
    # Try 2: Relative to Mod Root
    base = get_mod_base_path()
    if base:
        p2 = os.path.join(base, path).replace('\\', '/')
        if os.path.exists(p2): return p2
        
        p3 = os.path.join(base, "Textures", path).replace('\\', '/')
        if os.path.exists(p3): return p3

    # Try 4: Check if simple filename exists in registry
    fname = os.path.basename(path).lower()
    if fname in _filename_registry:
        return _filename_registry[fname]

    if os.path.exists(path): return path
    return ""

_res_name_cache = {} # {name: abspath}

def get_resource_path(resource_name):
    """Helper to get exact absolute path from resource name."""
    if not resource_name: return ""
    if resource_name in _res_name_cache:
        return _res_name_cache[resource_name]
        
    rzm = bpy.context.scene.rzm
    res = next((r for r in rzm.tw_resources if r.name == resource_name), None)
    if res and res.path:
        path = resolve_path(res.path)
        _res_name_cache[resource_name] = path
        return path
    return ""

class AtlasWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        finished = QtCore.Signal(QtGui.QPixmap)

    def __init__(self, layers, canvas_res, size):
        super().__init__()
        self.layers = layers
        self.canvas_res = canvas_res
        self.size = size
        self.signals = self.Signals()

    def run(self):
        try:
            # We need the lock because get_total_block_preview calls load_texture_data
            _blender_lock.lock()
            try:
                pix = get_total_block_preview(self.layers, self.canvas_res, self.size)
            finally:
                _blender_lock.unlock()
            self.signals.finished.emit(pix)
        except Exception as e:
            print(f"[AtlasWorker] Error: {e}")
            empty = QtGui.QPixmap(self.size, self.size)
            empty.fill(QtCore.Qt.black)
            self.signals.finished.emit(empty)

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
        # 1. Quick check in memory caches (non-blocking)
        if path in _resolved_path_cache:
            resolved = _resolved_path_cache[path]
            # Verify it's in thumbnail cache too
            cache_key = f"{resolved}_{getattr(self, '_dummy_mtime', 0)}_{max_size}" 
            # Actually, load_texture_data uses a better cache_key. 
            # For now, if it's already in _thumbnail_cache with any key, it's fast.
            # But simpler: just use the worker if not 100% sure.
            pass

        # 2. Start Background Task (Worker will handle resolve_path internally)
        worker = ThumbnailWorker(path, max_size)
        worker.signals.finished.connect(callback)
        self.pool.start(worker)

    def load_atlas_async(self, layers, canvas_res, size, callback):
        """Renders an atlas in background and calls callback(pixmap)."""
        worker = AtlasWorker(layers, canvas_res, size)
        worker.signals.finished.connect(callback)
        self.pool.start(worker)

