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

    @classmethod
    def get_instance(cls):
        return cls.instance()

    def get_image_resolution(self, image_id):
        """Returns (width, height) of the cached image or (0, 0) if not found."""
        pix = self._cache.get(image_id)
        if pix and not pix.isNull():
            return (pix.width(), pix.height())
        return (0, 0)

    def __init__(self):
        self._cache = {} # {image_id: QPixmap}
        self._anim_cache = {} # {name_frame: QPixmap}
        self._fit_modes = {} # {image_id: fit_mode}

    def clear(self):
        """Очистка кэша перед обновлением."""
        self._cache.clear()
        self._anim_cache.clear()
        self._fit_modes.clear()

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
            
        self._fit_modes[image_id] = getattr(target_rz_img, 'fit_mode', 'FILL')

        bl_image = target_rz_img.image_pointer
        if not bl_image:
            # print(f"ImageCache: ID {image_id} has no image_pointer.")
            self._cache[image_id] = None
            return

        width = bl_image.size[0]
        height = bl_image.size[1]

        if width <= 0 or height <= 0:
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

            q_image = QtGui.QImage(
                final_buffer.data,
                w,
                h,
                bytes_per_line,
                QtGui.QImage.Format_RGBA8888
            ).copy() # Делаем глубокую копию, чтобы отвязаться от numpy

            # 5. Сохраняем в кэш
            self._cache[image_id] = QtGui.QPixmap.fromImage(q_image)

        except Exception as e:
            print(f"RZMenu Image Cache Critical Error on ID {image_id}: {e}")
            import traceback
            traceback.print_exc()
            self._cache[image_id] = None

    def get_pixmap(self, image_id):
        """Возвращает картинку из кэша. Не лезет в Blender."""
        return self._cache.get(image_id, None)

    def get_fit_mode(self, image_id):
        return self._fit_modes.get(image_id, 'FILL')

    def get_anim_frame(self, base_name, frame_idx):
        """Достает запеченный кадр анимации из Blender и кэширует его."""
        key = f"{base_name}_anim_{frame_idx:04d}"
        if key in self._anim_cache:
            return self._anim_cache[key]
            
        # Если нет в кэше, пробуем достать из Blender
        bl_img = bpy.data.images.get(key)
        if not bl_img: return None
        
        try:
            width, height = bl_img.size
            if width <= 0 or height <= 0: return None
            
            raw_pixels = np.array(bl_img.pixels[:], dtype=np.float32)
            pixels_uint8 = (raw_pixels * 255).astype(np.uint8)
            pixels_reshaped = pixels_uint8.reshape((height, width, 4))
            pixels_flipped = np.flipud(pixels_reshaped)
            
            final_buffer = np.require(pixels_flipped, requirements=['C'])
            q_image = QtGui.QImage(final_buffer.data, width, height, width*4, QtGui.QImage.Format_RGBA8888).copy()
            
            pix = QtGui.QPixmap.fromImage(q_image)
            self._anim_cache[key] = pix
            return pix
        except:
            return None