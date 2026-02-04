# RZMenu/core/atlas_algo.py (ex rzm_atlas.py)
import bpy
import numpy as np
import struct
import zlib
from pathlib import Path

class PackerNode:
    # ... (класс PackerNode остается без изменений) ...
    def __init__(self, x=0, y=0, w=0, h=0): self.x, self.y, self.w, self.h, self.down, self.right, self.used = x, y, w, h, None, None, False
    def find_space(self, w, h):
        if self.used:
            node = self.right.find_space(w, h) if self.right else None
            if node: return node
            return self.down.find_space(w, h) if self.down else None
        elif w <= self.w and h <= self.h: return self
        else: return None
    def split_node(self, w, h):
        self.used = True
        self.right = PackerNode(x=self.x + w, y=self.y, w=self.w - w, h=h)
        self.down = PackerNode(x=self.x, y=self.y + h, w=self.w, h=self.h - h)
        return self

def calculate_atlas_layout(image_sizes_dict: dict):
    """
    БЫСТРАЯ ЧАСТЬ: Только рассчитывает геометрию атласа без обработки пикселей.
    Принимает словарь {name: (width, height)}.
    Возвращает (atlas_w, atlas_h), uv_data_dict.
    """
    if not image_sizes_dict:
        print("DEBUG LAYOUT: No image sizes provided.")
        return (0, 0), {}

    print(f"DEBUG LAYOUT: Calculating layout for {len(image_sizes_dict)} images.")
    
    images = sorted(image_sizes_dict.items(), key=lambda item: item[1][1], reverse=True)
    
    root_w, root_h = images[0][1]
    root = PackerNode(w=root_w, h=root_h)
    uv_data = {}

    for name, (w, h) in images:
        node = root.find_space(w, h)
        if node:
            split_node = node.split_node(w, h)
            uv_data[name] = {'uv_coords': [split_node.x, split_node.y], 'uv_size': [w, h]}
        else:
            can_grow_down = w <= root.w; can_grow_right = h <= root.h
            should_grow_right = can_grow_right and (root.h >= (root.w + w))
            should_grow_down = can_grow_down and (root.w >= (root.h + h))
            if should_grow_right:
                new_root = PackerNode(w=root.w + w, h=root.h); new_root.used = True; new_root.down = root
                new_root.right = PackerNode(x=root.w, y=0, w=w, h=root.h); root = new_root
            elif should_grow_down:
                new_root = PackerNode(w=root.w, h=root.h + h); new_root.used = True; new_root.down = PackerNode(x=0, y=root.h, w=root.w, h=h)
                new_root.right = root; root = new_root
            else:
                new_root = PackerNode(w=root.w + w, h=root.h); new_root.used = True; new_root.down = root
                new_root.right = PackerNode(x=root.w, y=0, w=w, h=root.h); root = new_root
            node = root.find_space(w, h)
            split_node = node.split_node(w, h)
            uv_data[name] = {'uv_coords': [split_node.x, split_node.y], 'uv_size': [w, h]}

    unpadded_w, unpadded_h = root.w, root.h
    atlas_w = (unpadded_w + 3) & ~3
    atlas_h = (unpadded_h + 3) & ~3
    print(f"DEBUG LAYOUT: Calculated atlas size: {atlas_w}x{atlas_h}")
    
    return (atlas_w, atlas_h), uv_data

def apply_gamma_correction(atlas_pixels, width, height):
    """
    Применяет гамма-коррекцию 1/2.2 к RGB каналам, не трогая Alpha.
    Это делает "белесые" линейные пиксели сочными (sRGB).
    """
    print("DEBUG: Applying mathematical Gamma 2.2 correction...")
    
    # Решейп в 3D массив (H, W, 4)
    buffer = atlas_pixels.reshape((height, width, 4))
    
    # Разделяем каналы
    rgb = buffer[:, :, :3]
    alpha = buffer[:, :, 3:]
    
    # Защита от NaN и вылетов
    rgb = np.clip(rgb, 0.0, 1.0)
    
    # === ГЛАВНАЯ МАГИЯ ===
    # Paint.NET использует простую гамму 2.2 (gAMA 45455)
    # Формула: Color_New = Color_Old ^ (1 / 2.2)
    # rgb_corrected = np.power(rgb, 1.0 / 2.2)
    
    # Собираем обратно
    # buffer[:, :, :3] = rgb_corrected
    
    return buffer.flatten()

# --- ЧАСТЬ 2: РАБОТА С ФАЙЛОМ (ИНЪЕКЦИЯ ЧАНКОВ) ---
def inject_paintnet_metadata(filepath):
    """
    Вставляет чанки sRGB и gAMA, чтобы файл был бинарно идентичен Paint.NET
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read()

        if data[:8] != b'\x89PNG\r\n\x1a\n':
            return

        # Ищем позицию для вставки (после IHDR)
        # IHDR всегда 13 байт данных + 12 байт обвязки = 25 байт.
        # Заголовок файла 8 байт. Итого IHDR кончается на 33 байте.
        insert_pos = 33 
        
        # --- Подготовка чанка sRGB ---
        # Intent 0 (Perceptual)
        srgb_payload = b'\x00'
        srgb_chunk = create_png_chunk(b'sRGB', srgb_payload)
        
        # --- Подготовка чанка gAMA ---
        # Value 0.45455 * 100000 = 45455
        gama_payload = struct.pack('>I', 45455)
        gama_chunk = create_png_chunk(b'gAMA', gama_payload)
        
        # Вставляем данные, если их еще нет
        if b'sRGB' not in data:
            data = data[:insert_pos] + srgb_chunk + gama_chunk + data[insert_pos:]
            
            with open(filepath, 'wb') as f:
                f.write(data)
            print("SUCCESS: Injected sRGB + gAMA chunks.")
        else:
            print("INFO: Metadata already present.")
            
    except Exception as e:
        print(f"Injection Failed: {e}")

def create_png_chunk(type_bytes, data_bytes):
    length = len(data_bytes)
    # CRC считается от Type + Data
    crc = zlib.crc32(type_bytes + data_bytes) & 0xffffffff
    return struct.pack('>I', length) + type_bytes + data_bytes + struct.pack('>I', crc)


# --- ЧАСТЬ 3: ГЕНЕРАЦИЯ ---
def create_atlas_pixels(image_dict: dict, atlas_w: int, atlas_h: int, uv_data: dict):
    if not image_dict or atlas_w == 0 or atlas_h == 0:
        return np.array([])
        
    print(f"DEBUG EXPORT: Creating {atlas_w}x{atlas_h} pixel buffer.")
    atlas_pixels = np.zeros((atlas_h, atlas_w, 4), dtype=np.float32)

    for name, img in image_dict.items():
        if name not in uv_data: continue
        
        x, y = uv_data[name]['uv_coords']
        w, h = uv_data[name]['uv_size']
        
        if len(img.pixels) > 0:
            try:
                img_pixels = np.array(img.pixels[:]).reshape((h, w, 4))
                atlas_pixels[y:y+h, x:x+w] = img_pixels
            except:
                pass
    
    # ПРИМЕНЯЕМ ГАММУ СРАЗУ ПОСЛЕ СБОРКИ
    atlas_pixels_flat = apply_gamma_correction(atlas_pixels, atlas_w, atlas_h)
    
    return atlas_pixels_flat