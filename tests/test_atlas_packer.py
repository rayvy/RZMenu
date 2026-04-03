# RZMenu/tests/test_atlas_packer.py
import unittest
import numpy as np
from ..core.atlas_algo import calculate_atlas_layout
from ..core.animated_loader import deduplicate_frames

class TestAtlasPacker(unittest.TestCase):
    
    def test_margin_spacing(self):
        """Проверка, что упаковщик учитывает ATLAS_MARGIN=2."""
        # Два изображения 10x10. С учетом марджина 2px с каждой стороны (итого 4px между ними),
        # они должны занять больше места, чем просто 20x10.
        sizes = {
            "img1": (10, 10),
            "img2": (10, 10)
        }
        
        (atlas_w, atlas_h), uv_data = calculate_atlas_layout(sizes)
        
        # С марджином 2:
        # img1 занимает слот (10+2, 10+2) = 12x12
        # img2 занимает слот (10+2, 10+2) = 12x12
        # В простейшем случае они будут стоять рядом: 24x12
        self.assertGreaterEqual(atlas_w, 20)
        self.assertGreaterEqual(atlas_h, 10)
        
        # Проверяем UV координаты первого изображения
        # Координаты слота (0, 0), но UV должны быть смещены на марджин 1/2 (т.е. на 1px)
        # при условии что мы считаем UV от центра пикселя или края.
        # В нашей реализации: uv_coords = (x + margin/2, y + margin/2)
        uv1 = uv_data["img1"]["uv_coords"]
        self.assertEqual(uv1, (1, 1)) # 0 + 2/2 = 1
        
        # Размер UV должен быть ровно 10x10
        self.assertEqual(uv_data["img1"]["uv_size"], (10, 10))

    def test_deduplication(self):
        """Проверка схлопывания идентичных кадров."""
        # Создаем 3 кадра: 1 и 2 одинаковые, 3 другой
        frame_a = {
            'pixels': np.ones((4, 4, 4), dtype=np.float32),
            'frametime': 0.1,
            'size': (4, 4)
        }
        frame_b = {
            'pixels': np.ones((4, 4, 4), dtype=np.float32), # ТАКОЙ ЖЕ
            'frametime': 0.1,
            'size': (4, 4)
        }
        frame_c = {
            'pixels': np.zeros((4, 4, 4), dtype=np.float32), # ДРУГОЙ
            'frametime': 0.1,
            'size': (4, 4)
        }
        
        frames = [frame_a, frame_b, frame_c]
        unique = deduplicate_frames(frames, threshold=0.01)
        
        # Должно остаться 2 кадра
        self.assertEqual(len(unique), 2)
        # У первого кадра время должно стать 0.2
        self.assertAlmostEqual(unique[0]['frametime'], 0.2)
        # Второй кадр (исходный 3-й) должен остаться 0.1
        self.assertAlmostEqual(unique[1]['frametime'], 0.1)

if __name__ == '__main__':
    unittest.main()
