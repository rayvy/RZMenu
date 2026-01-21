# RZMenu/qt_editor/utils/image_cache.py

import bpy
import numpy as np
from PySide6 import QtGui

class ImageCache:
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._cache = {} # {image_id: QPixmap}

    def clear(self):
        """Очистка кэша перед обновлением."""
        self._cache.clear()

    def pre_cache_image(self, image_id):
        """
        Принудительно загружает картинку в кэш.
        Вызывать из основного потока (rebuild_scene).
        """
        if image_id == -1:  # Only skip invalid IDs, not 0
            return

        if image_id in self._cache:
            return

        # 1. Поиск RZMenuImage по ID
        target_rz_img = None
        scene = bpy.context.scene
        
        if hasattr(scene, "rzm") and hasattr(scene.rzm, "images"):
            for img in scene.rzm.images:
                if img.id == image_id:
                    target_rz_img = img
                    break
        
        if not target_rz_img:
            # print(f"ImageCache: ID {image_id} not found in RZM images.")
            self._cache[image_id] = None
            return

        bl_image = target_rz_img.image_pointer
        if not bl_image:
            # print(f"ImageCache: ID {image_id} has no image_pointer.")
            self._cache[image_id] = None
            return

        width = bl_image.size[0]
        height = bl_image.size[1]

        print(f"[ImageCache] Processing image ID {image_id}: {width}x{height}, aspect ratio: {width/height if height > 0 else 'invalid'}")

        if width <= 0 or height <= 0:
            print(f"[ImageCache] Invalid dimensions for image ID {image_id}: {width}x{height}")
            return

        try:
            # 2. Чтение пикселей (Самый безопасный метод)
            # Копируем пиксели в numpy массив float32 (0.0 - 1.0)
            # Используем slice [:], это создает копию списка, безопасно для памяти
            raw_pixels = np.array(bl_image.pixels[:], dtype=np.float32)
            
            # Конвертация в 0-255 uint8
            pixels_uint8 = (raw_pixels * 255).astype(np.uint8)
            
            # Решейп (Высота, Ширина, RGBA)
            # Blender хранит как плоский массив
            expected_len = width * height * 4
            if len(pixels_uint8) != expected_len:
                print(f"ImageCache Error: Size mismatch for ID {image_id}. Exp: {expected_len}, Got: {len(pixels_uint8)}")
                return

            pixels_reshaped = pixels_uint8.reshape((height, width, 4))
            
            # 3. Переворот (Blender Y-up -> Qt Y-down)
            pixels_flipped = np.flipud(pixels_reshaped)
            
            # 4. Создание QImage
            # np.require гарантирует C-contiguous массив, чтобы Qt не ругался
            final_buffer = np.require(pixels_flipped, requirements=['C'])

            h, w, ch = final_buffer.shape
            bytes_per_line = ch * w

            print(f"[ImageCache] Creating QImage: {w}x{h}, channels: {ch}, bytes_per_line: {bytes_per_line}")

            q_image = QtGui.QImage(
                final_buffer.data,
                w,
                h,
                bytes_per_line,
                QtGui.QImage.Format_RGBA8888
            ).copy() # Делаем глубокую копию, чтобы отвязаться от numpy

            print(f"[ImageCache] QImage created: isNull={q_image.isNull()}, size={q_image.size()}")

            # 5. Сохраняем в кэш
            pixmap = QtGui.QPixmap.fromImage(q_image)
            print(f"[ImageCache] QPixmap created: isNull={pixmap.isNull()}, size={pixmap.size()}")

            self._cache[image_id] = pixmap
            print(f"[ImageCache] Successfully cached image ID {image_id} ({w}x{h})")

        except Exception as e:
            print(f"RZMenu Image Cache Critical Error on ID {image_id}: {e}")
            import traceback
            traceback.print_exc()
            self._cache[image_id] = None

    def get_pixmap(self, image_id):
        """Возвращает картинку из кэша. Не лезет в Blender."""
        pixmap = self._cache.get(image_id, None)
        if pixmap is not None:
            print(f"[ImageCache] get_pixmap({image_id}): {'Valid pixmap' if not pixmap.isNull() else 'Null pixmap'} {pixmap.width()}x{pixmap.height()}")
        else:
            print(f"[ImageCache] get_pixmap({image_id}): No pixmap in cache")
        return pixmap