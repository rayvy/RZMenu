# rz_gui_constructor/rzm_atlas.py
import bpy
import numpy as np

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

def create_atlas_pixels(image_dict: dict, atlas_w: int, atlas_h: int, uv_data: dict):
    """
    МЕДЛЕННАЯ ЧАСТЬ: Создает массив пикселей на основе готового layout.
    Возвращает плоский массив пикселей (numpy.ndarray).
    """
    if not image_dict or atlas_w == 0 or atlas_h == 0:
        return np.array([])
        
    print(f"DEBUG EXPORT: Creating {atlas_w}x{atlas_h} pixel buffer.")
    atlas_pixels = np.zeros((atlas_h, atlas_w, 4), dtype=np.float32)

    for name, img in image_dict.items():
        if name not in uv_data: continue
        
        x, y = uv_data[name]['uv_coords']
        w, h = uv_data[name]['uv_size']
        
        img_pixels = np.array(img.pixels[:]).reshape((h, w, 4))
        atlas_pixels[y:y+h, x:x+w] = img_pixels

    print("DEBUG EXPORT: Pixel copy complete.")
    return atlas_pixels.flatten()