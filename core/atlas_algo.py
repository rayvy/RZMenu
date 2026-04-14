# RZMenu/core/atlas_algo.py (ex rzm_atlas.py)
import bpy
import numpy as np
import struct
import zlib
from pathlib import Path

# 'SRGB'   -> Добавляет чанк sRGB и gAMA (стандарт для Paint.NET/Web, цвета "как есть")
# 'LINEAR' -> Добавляет только gAMA 1.0 (говорит софту, что это линейное пространство)

class PackerNode:
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

# Зазор между элементами атласа в пикселях (предотвращает texture bleeding).
ATLAS_MARGIN = 2

def calculate_atlas_layout(image_sizes_dict: dict, margin: int = ATLAS_MARGIN):
    """
    БЫСТРАЯ ЧАСТЬ: Только рассчитывает геометрию атласа без обработки пикселей.
    Принимает словарь {name: (width, height)}.
    Возвращает (atlas_w, atlas_h), uv_data_dict.

    margin: пикселей зазора между элементами (предотвращает texture bleeding).
    Каждый блок резервирует (w+margin, h+margin) в атласе.
    UV-координаты уже включают отступ margin//2 внутрь, поэтому
    пиксели изображения окружены прозрачной окантовкой со всех сторон.
    """
    if not image_sizes_dict:
        print("DEBUG LAYOUT: No image sizes provided.")
        return (0, 0), {}

    print(f"DEBUG LAYOUT: Calculating layout for {len(image_sizes_dict)} images with margin {margin}.")
    
    images = sorted(image_sizes_dict.items(), key=lambda item: item[1][1], reverse=True)

    # Первый слот с учётом зазора
    first_w, first_h = images[0][1]
    root = PackerNode(w=first_w + margin, h=first_h + margin)
    uv_data = {}

    for name, (w, h) in images:
        pw, ph = w + margin, h + margin  # padded slot размер

        node = root.find_space(pw, ph)
        if node:
            split_node = node.split_node(pw, ph)
            # UV сдвинут на margin//2 внутрь слота — пиксели не касаются краёв
            uv_data[name] = {
                'uv_coords': [split_node.x + margin // 2, split_node.y + margin // 2],
                'uv_size': [w, h]
            }
        else:
            can_grow_down = pw <= root.w
            can_grow_right = ph <= root.h
            should_grow_right = can_grow_right and (root.h >= (root.w + pw))
            should_grow_down = can_grow_down and (root.w >= (root.h + ph))
            if should_grow_right:
                new_root = PackerNode(w=root.w + pw, h=root.h); new_root.used = True; new_root.down = root
                new_root.right = PackerNode(x=root.w, y=0, w=pw, h=root.h); root = new_root
            elif should_grow_down:
                new_root = PackerNode(w=root.w, h=root.h + ph); new_root.used = True
                new_root.down = PackerNode(x=0, y=root.h, w=root.w, h=ph)
                new_root.right = root; root = new_root
            else:
                new_root = PackerNode(w=root.w + pw, h=root.h); new_root.used = True; new_root.down = root
                new_root.right = PackerNode(x=root.w, y=0, w=pw, h=root.h); root = new_root
            node = root.find_space(pw, ph)
            split_node = node.split_node(pw, ph)
            uv_data[name] = {
                'uv_coords': [split_node.x + margin // 2, split_node.y + margin // 2],
                'uv_size': [w, h]
            }

    unpadded_w, unpadded_h = root.w, root.h
    atlas_w = (unpadded_w + 3) & ~3
    atlas_h = (unpadded_h + 3) & ~3
    print(f"DEBUG LAYOUT: Calculated atlas size: {atlas_w}x{atlas_h}")

    return (atlas_w, atlas_h), uv_data

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

def inject_metadata_profile(filepath, profile='LINEAR'):
    """
    Вставляет метаданные (sRGB или gAMA) в зависимости от выбранного профиля.
    НЕ МЕНЯЕТ ПИКСЕЛИ. Работает с бинарным файлом.
    Обеспечивает идентичность пикселей за счет указания профиля движку.
    """
    profile = profile.upper()
    print(f"DEBUG INJECTION: Injecting metadata for profile: {profile}")

    try:
        with open(filepath, 'rb') as f:
            data = f.read()

        if data[:8] != b'\x89PNG\r\n\x1a\n':
            print("ERROR: Not a valid PNG file.")
            return

        # Ищем позицию для вставки (сразу после IHDR)
        # IHDR (13 байт) + CRC (4) + Len (4) + Type (4) = 25 байт.
        # Заголовок файла = 8 байт.
        # 8 + 25 = 33. Вставляем на 33-й байт.
        insert_pos = 33 
        
        chunks_to_add = b''

        if profile == 'SRGB':
            # === ВАРИАНТ 1: SRGB (Как в Paint.NET) ===
            # Вставляем sRGB чанк
            if b'sRGB' not in data:
                # Intent 0 (Perceptual)
                srgb_payload = b'\x00'
                chunks_to_add += create_png_chunk(b'sRGB', srgb_payload)
            
            # Вставляем gAMA чанк (1 / 2.2 = 0.45455)
            if b'gAMA' not in data:
                gama_payload = struct.pack('>I', 45455)
                chunks_to_add += create_png_chunk(b'gAMA', gama_payload)

        elif profile == 'LINEAR':
            # === ВАРИАНТ 2: LINEAR ===
            # sRGB чанк НЕ вставляем (так как это Linear)
            
            # Вставляем gAMA чанк (1.0 = 100000)
            if b'gAMA' not in data:
                gama_payload = struct.pack('>I', 100000)
                chunks_to_add += create_png_chunk(b'gAMA', gama_payload)
        
        else:
            print(f"WARNING: Unknown profile mode '{profile}', skipping injection.")
            return

        # Если есть что добавить - добавляем
        if chunks_to_add:
            new_data = data[:insert_pos] + chunks_to_add + data[insert_pos:]
            with open(filepath, 'wb') as f:
                f.write(new_data)
            print(f"SUCCESS: Injected {profile} chunks.")
        else:
            print("INFO: Relevant metadata already present.")
            
    except Exception as e:
        print(f"Injection Failed: {e}")

def create_atlas_pixels(image_dict: dict, atlas_w: int, atlas_h: int, uv_data: dict, profile='LINEAR'):
    """
    Создает буфер пикселей атласа. 
    Никакая гамма-коррекция не применяется к пикселям. 
    Пиксели всегда идентичны источнику в Blender.
    """
    if not image_dict or atlas_w == 0 or atlas_h == 0:
        return np.array([])
        
    print(f"DEBUG EXPORT: Creating {atlas_w}x{atlas_h} pixel buffer. Profile: {profile}")
    atlas_pixels = np.zeros((atlas_h, atlas_w, 4), dtype=np.float32)

    for name, img in image_dict.items():
        if name not in uv_data: continue
        
        x, y = uv_data[name]['uv_coords']
        w, h = uv_data[name]['uv_size']
        
        if len(img.pixels) > 0:
            try:
                # Blender pixels are in bottom-up order, but our packer/numpy expects top-down
                img_pixels = np.array(img.pixels[:]).reshape((h, w, 4))
                atlas_pixels[y:y+h, x:x+w] = img_pixels
            except:
                pass
    
    return atlas_pixels.flatten()