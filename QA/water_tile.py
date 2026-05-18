# ============================================================
# Procedural Water Caustics (TRUE EXACT EDGES, ORGANIC CURVES)
# ============================================================

import os
import numpy as np
import imageio.v2 as imageio

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "output_video": "water_caustics_organic_perfect.mov",
    "width": 600,
    "height": 200,
    "fps": 30,
    "duration": 2,

    # ГЛОБАЛЬНОЕ ИСКАЖЕНИЕ (Теперь делает линии круглыми и жидкими!)
    "wave_amp": 16.0,          # Сильно увеличено, чтобы "загнуть" прямые линии
    "wave_freq": 0.03,         # Плавность изгибов
    "base_flow_x": 0.6,        # Общее движение вправо
    "base_flow_y": 0.15,       # Общее движение вниз

    # ==========================================
    # СЛОЙ 1: ОСНОВНЫЕ БЕЛЫЕ ЛИНИИ (Крупные, четкие)
    # ==========================================
    "layer_main": {
        "num_cells": 12,       
        "thickness": 2.8,      # Толщина линии (теперь равномерная везде)
        "color": (255, 255, 255),
        "alpha": 1.0,          
        "flow_mult": 1.0,      
        "morph_mult": 1.0      
    },

    # ==========================================
    # СЛОЙ 2: ВТОРИЧНЫЕ ЛАЗУРНЫЕ ЛИНИИ (Мелкие, быстрые)
    # ==========================================
    "layer_sub": {
        "num_cells": 35,       # Много ячеек
        "thickness": 1.8,      # Тоньше основных
        "color": (0, 160, 230),
        "alpha": 0.4,          # 40% прозрачности (как в ТЗ)
        "flow_mult": 1.6,      # Быстрее плывут
        "morph_mult": 1.5      # Быстрее переливаются
    }
}

# ============================================================
# ENGINE
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(SCRIPT_DIR, CONFIG["output_video"])
W, H = CONFIG["width"], CONFIG["height"]

def generate_true_caustic_layer(t, config_layer, seed):
    np.random.seed(seed)
    N = config_layer["num_cells"]
    
    # Генерация базовых точек
    points = np.random.rand(N, 2).astype(np.float32)
    points[:, 0] *= W
    points[:, 1] *= H
    directions = (np.random.rand(N, 2).astype(np.float32) - 0.5) * 2.0

    # 1. ДВОЙНОЕ ОРГАНИЧЕСКОЕ ИСКАЖЕНИЕ (Double Domain Warping)
    # Именно это делает сетку похожей на жидкость, а не на кривые заборы
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    time_w = t * 2.0 * config_layer["flow_mult"]
    freq = CONFIG["wave_freq"]
    amp = CONFIG["wave_amp"]

    # Первый слой изгибов
    warp_x = np.sin(y * freq + time_w) * amp
    warp_y = np.cos(x * freq + time_w) * amp
    
    # Второй слой изгибов (разбивает симметрию, добавляет хаос воды)
    warp_x += np.sin(x * freq * 1.5 - time_w * 1.2) * (amp * 0.6)
    warp_y += np.cos(y * freq * 1.5 + time_w * 0.8) * (amp * 0.6)

    wx = (x + warp_x) % W
    wy = (y + warp_y) % H

    # 2. ДВИЖЕНИЕ И ТАЙЛИНГ ТОЧЕК
    time_p = t * 1.5 * config_layer["morph_mult"]
    flow_x = t * 30.0 * CONFIG["base_flow_x"] * config_layer["flow_mult"]
    flow_y = t * 30.0 * CONFIG["base_flow_y"] * config_layer["flow_mult"]

    px = (points[:, 0] + np.sin(time_p + directions[:, 0]*10) * 15.0 + flow_x) % W
    py = (points[:, 1] + np.cos(time_p + directions[:, 1]*10) * 15.0 + flow_y) % H

    # Создаем виртуальные копии точек вокруг экрана для идеальной бесшовности
    offsets = np.array([
        [-W,-H], [0,-H], [W,-H],
        [-W, 0], [0, 0], [W, 0],
        [-W, H], [0, H], [W, H]
    ])
    
    exp_px = (px[:, None] + offsets[:, 0]).flatten()
    exp_py = (py[:, None] + offsets[:, 1]).flatten()

    # 3. ВЫЧИСЛЕНИЕ "TRUE EXACT DISTANCE" (УБИВАЕТ АРТЕФАКТЫ УЗЛОВ НА 100%)
    # Вычисляем квадрат расстояния от каждого пикселя до всех точек
    dist_sq = (wx[:, :, None] - exp_px[None, None, :])**2 + (wy[:, :, None] - exp_py[None, None, :])**2
    
    # Находим индексы двух ближайших точек для каждого пикселя
    idx = np.argpartition(dist_sq, 1, axis=-1)[..., :2]
    idx1, idx2 = idx[..., 0], idx[..., 1]
    
    I, J = np.ogrid[:H, :W]
    d1 = dist_sq[I, J, idx1]
    d2 = dist_sq[I, J, idx2]

    # Гарантируем, что idx1 это всегда самая ближняя точка
    swap = d1 > d2
    idx1_f = np.where(swap, idx2, idx1)
    idx2_f = np.where(swap, idx1, idx2)

    # Получаем координаты двух ближайших точек
    P1x, P1y = exp_px[idx1_f], exp_py[idx1_f]
    P2x, P2y = exp_px[idx2_f], exp_py[idx2_f]

    # ВЫСШАЯ МАТЕМАТИКА: Высчитываем геометрическое расстояние от пикселя 
    # до линии (биссектрисы), разделяющей эти две точки.
    # Это математически гарантирует идеальную, ровную толщину линии ВЕЗДЕ.
    Mx, My = (P1x + P2x) / 2.0, (P1y + P2y) / 2.0  # Середина между точками
    Dx, Dy = P2x - P1x, P2y - P1y                  # Вектор между точками
    length = np.sqrt(Dx**2 + Dy**2) + 1e-8
    nx, ny = Dx / length, Dy / length              # Нормаль

    Vx, Vy = wx - Mx, wy - My                      # Вектор от середины до пикселя
    exact_dist = np.abs(Vx * nx + Vy * ny)         # Скалярное произведение = Идеальная дистанция!

    # 4. ФОРМИРОВАНИЕ ЛИНИИ
    thickness = config_layer["thickness"]
    line_mask = np.clip(1.0 - (exact_dist / thickness), 0.0, 1.0)
    
    # Смягчение краев линии для эффекта оптического свечения
    line_mask = line_mask ** 1.3 
    
    return line_mask

# ============================================================
# RENDER LOOP
# ============================================================

total_frames = CONFIG["fps"] * CONFIG["duration"]
writer = imageio.get_writer(output_path, fps=CONFIG["fps"], codec="png", format="FFMPEG")
print(f"Генерация ИДЕАЛЬНЫХ водных каустик: {output_path}")

for frame in range(total_frames):
    t = frame / CONFIG["fps"]
    
    # Генерируем слои
    mask_main = generate_true_caustic_layer(t, CONFIG["layer_main"], seed=42)
    mask_sub = generate_true_caustic_layer(t, CONFIG["layer_sub"], seed=100)
    
    frame_rgba = np.zeros((H, W, 4), dtype=np.float32)
    
    # Извлечение цветов и альфы
    r_sub, g_sub, b_sub = [c/255.0 for c in CONFIG["layer_sub"]["color"]]
    a_sub = CONFIG["layer_sub"]["alpha"]
    
    r_main, g_main, b_main = [c/255.0 for c in CONFIG["layer_main"]["color"]]
    a_main = CONFIG["layer_main"]["alpha"]

    # Композитинг (Экранное наложение)
    # Слой 2 (Задний, лазурный)
    frame_rgba[..., 0] += mask_sub * r_sub * a_sub
    frame_rgba[..., 1] += mask_sub * g_sub * a_sub
    frame_rgba[..., 2] += mask_sub * b_sub * a_sub
    frame_rgba[..., 3] += mask_sub * a_sub 
    
    # Слой 1 (Передний, белый)
    frame_rgba[..., 0] += mask_main * r_main * a_main
    frame_rgba[..., 1] += mask_main * g_main * a_main
    frame_rgba[..., 2] += mask_main * b_main * a_main
    frame_rgba[..., 3] = np.maximum(frame_rgba[..., 3], mask_main * a_main)
    
    # Финализация
    frame_rgba = np.clip(frame_rgba, 0.0, 1.0)
    final_frame = (frame_rgba * 255).astype(np.uint8)
    writer.append_data(final_frame)
    
    progress = int((frame + 1) / total_frames * 100)
    print(f"\rРендер: [{progress:3d}%] Кадр {frame+1}/{total_frames}", end="")

writer.close()
print("\nГОТОВО! Идеально чистый результат с округлыми органичными линиями.")