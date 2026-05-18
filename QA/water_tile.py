# ============================================================
# Procedural Water Caustics Generator (Voronoi-Based)
# ============================================================

import os
import numpy as np
import imageio.v2 as imageio
from scipy.ndimage import gaussian_filter

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "output_video": "water_caustics_final.mov",

    # --------------------------------------------------------
    # VIDEO SETTINGS
    # --------------------------------------------------------
    "width": 600,
    "height": 200,
    "fps": 30,
    "duration": 1,           # 1 секунда

    # --------------------------------------------------------
    # COLORS & ALPHA
    # --------------------------------------------------------
    # Главные акценты (Почти белые, лазурный оттенок, альфа ~165)
    "main_color_r": 210,
    "main_color_g": 245,
    "main_color_b": 255,
    "main_alpha_target": 165,

    # Полуакценты (Лазурные, прозрачнее, альфа ~70)
    "sub_color_r": 0,
    "sub_color_g": 170,
    "sub_color_b": 220,
    "sub_alpha_target": 70,

    # --------------------------------------------------------
    # CAUSTIC SHAPING (Настройка формы сетки)
    # --------------------------------------------------------
    "num_cells": 18,          # Количество ячеек (масштаб сетки)
    "main_thickness": 5.5,   # Четкость/тонкость основных линий (выше = тоньше)
    "sub_thickness": 3.0,    # Четкость полуакцентов
    "blur_softness": 1.2,    # Легкое размытие краев для сглаживания

    # --------------------------------------------------------
    # ANIMATION / FLOW
    # --------------------------------------------------------
    "flow_speed_x": 0.8,     # Общий сдвиг сетки по горизонтали
    "flow_speed_y": 0.15,    # Сдвиг по вертикали
    "morph_speed": 2.5       # Скорость внутреннего искажения связей сетки
}

# ============================================================
# RESOLVE PATHS
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
output_path = CONFIG["output_video"]
if not os.path.isabs(output_path):
    output_path = os.path.join(SCRIPT_DIR, output_path)

H, W = CONFIG["height"], CONFIG["width"]

# ============================================================
# GENERATE PROCEDURAL POINTS
# ============================================================

np.random.seed(1337) # Стабильный сид
num_p = CONFIG["num_cells"]

# Генерируем случайные базовые центры ячеек и векторы их движения
points_base = np.random.rand(num_p, 2).astype(np.float32)
points_base[:, 0] *= W
points_base[:, 1] *= H

# Случайные направления для морфинга
move_dir_1 = np.random.randn(num_p, 2).astype(np.float32) * 25.0
move_dir_2 = np.random.randn(num_p, 2).astype(np.float32) * 15.0

def get_caustic_layer(t, thickness, morph_shift):
    """
    Генерирует классическую сетку каустики Вороного.
    """
    y, x = np.mgrid[0:H, 0:W]
    
    # Анимируем положение точек во времени
    phase = t * CONFIG["morph_speed"] + morph_shift
    current_points = points_base.copy()
    current_points[:, 0] += np.sin(phase) * move_dir_1[:, 0] + (t * CONFIG["flow_speed_x"] * W * 0.1)
    current_points[:, 1] += np.cos(phase) * move_dir_1[:, 1] + (t * CONFIG["flow_speed_y"] * H * 0.1)
    
    # Зацикливаем координаты точек внутри экрана (тайлинг/граница)
    current_points[:, 0] = current_points[:, 0] % W
    current_points[:, 1] = current_points[:, 1] % H

    # Массив минимальных расстояний
    min_dist1 = np.ones((H, W), dtype=np.float32) * 999999.0
    min_dist2 = np.ones((H, W), dtype=np.float32) * 999999.0

    # Считаем расстояния до ближайших точек (Брутфорс Вороного для GPU-like эффекта на CPU)
    for p in current_points:
        # Учитываем соседние повторения для бесшовности на границах экрана
        for offset_x in [-W, 0, W]:
            for offset_y in [-H, 0, H]:
                dx = x - (p[0] + offset_x)
                dy = y - (p[1] + offset_y)
                dist = dx*dx + dy*dy # Квадрат расстояния (быстрее)
                
                # Маска для обновления первой и второй ближайшей точки
                mask1 = dist < min_dist1
                min_dist2 = np.where(mask1, min_dist1, np.where(dist < min_dist2, dist, min_dist2))
                min_dist1 = np.where(mask1, dist, min_dist1)

    # Магия каустики: разница между вторым и первым расстоянием создает "хребты" сетки воды
    diff = np.sqrt(min_dist2) - np.sqrt(min_dist1)
    
    # Нормализация
    diff = (diff - diff.min()) / (diff.max() - diff.min() + 1e-5)
    
    # Формируем тонкие линии инверсией и степенью
    caustic = 1.0 - diff
    caustic = np.power(caustic, thickness)
    
    if CONFIG["blur_softness"] > 0:
        caustic = gaussian_filter(caustic, sigma=CONFIG["blur_softness"])
        
    return np.clip(caustic, 0, 1)

# ============================================================
# FRAME GENERATION
# ============================================================

total_frames = CONFIG["fps"] * CONFIG["duration"]

writer = imageio.get_writer(
    output_path,
    fps=CONFIG["fps"],
    codec="png",       # Поддерживает альфа-канал
    format="FFMPEG"
)

print(f"Generating caustics to: {output_path}")

for frame in range(total_frames):
    t = frame / CONFIG["fps"]

    # Генерируем два слоя каустики с небольшим фазовым сдвигом
    main_layer = get_caustic_layer(t, CONFIG["main_thickness"], 0.0)
    sub_layer = get_caustic_layer(t, CONFIG["sub_thickness"], 2.5) # Фазовый сдвиг 2.5 для рассинхрона

    # Создаем пустой RGBA массив
    frame_rgba = np.zeros((H, W, 4), dtype=np.float32)

    # 1. Композитим полуакценты (нижний слой)
    alpha_sub = sub_layer * (CONFIG["sub_alpha_target"] / 255.0)
    frame_rgba[..., 0] = (CONFIG["sub_color_r"] / 255.0) * alpha_sub
    frame_rgba[..., 1] = (CONFIG["sub_color_g"] / 255.0) * alpha_sub
    frame_rgba[..., 2] = (CONFIG["sub_color_b"] / 255.0) * alpha_sub
    frame_rgba[..., 3] = alpha_sub

    # 2. Накладываем основные белые акценты (верхний слой через классический Blend)
    alpha_main = main_layer * (CONFIG["main_alpha_target"] / 255.0)
    
    for c in range(3):
        color_target = CONFIG[["main_color_r", "main_color_g", "main_color_b"][c]] / 255.0
        # Стандартный Alpha Blend: Src * Интенсивность + Dst * (1 - Интенсивность)
        frame_rgba[..., c] = color_target * alpha_main + frame_rgba[..., c] * (1.0 - alpha_main)

    # Смешиваем альфу двух слоев
    frame_rgba[..., 3] = np.maximum(frame_rgba[..., 3], alpha_main)

    # В 8-бит формат
    final_frame = (np.clip(frame_rgba, 0, 1) * 255).astype(np.uint8)
    writer.append_data(final_frame)
    
    print(f"Frame {frame+1}/{total_frames}")

writer.close()
print("\nDONE! Saved seamless procedural caustics to:", output_path)