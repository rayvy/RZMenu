# ============================================================
# Procedural Water Caustics - SINGLE LAYER FAST VERSION
# (Alpha RGBA, Seamless Looping, Exact Math, Optimized)
# ============================================================

import os
import numpy as np
import imageio.v2 as imageio

# ============================================================
# CONFIG
# ============================================================
#"width": 230,
#"height": 48,
CONFIG = {
    "output_video": "WATERsingle_layerXX.mov",
    "width": 20,
    "height": 272,
    "fps": 24,
    
    # --------------------------------------------------------
    # НАСТРОЙКИ ВРЕМЕНИ И СКОРОСТИ
    # --------------------------------------------------------
    "duration": 0.5,           # Длительность цикла в секундах
    "global_speed": 0.5,       # Общий множитель скорости

    # --------------------------------------------------------
    # ГЛОБАЛЬНОЕ ИСКАЖЕНИЕ (Имитация преломления)
    # --------------------------------------------------------
    "wave_amp": 16.0,          
    "wave_freq": 0.07,         
    "base_flow_x": 0.3,        
    "base_flow_y": 0.15,       

    # --------------------------------------------------------
    # НАСТРОЙКИ ЛИНИЙ (Единственный слой)
    # --------------------------------------------------------
    "cells_x": 8,         
    "cells_y": 4,          
    "thickness": 0.5,      
    "color": (255, 255, 255),
    "alpha": 0.8,         
    "flow_mult": 1.0,      
    "morph_mult": 1.0      
}

# ============================================================
# ENGINE
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(SCRIPT_DIR, CONFIG["output_video"])
W, H = CONFIG["width"], CONFIG["height"]

def get_base_points(seed):
    Nx, Ny = CONFIG["cells_x"], CONFIG["cells_y"]
    N_total = Nx * Ny
    cell_w, cell_h = W / Nx, H / Ny

    grid_x, grid_y = np.meshgrid(np.arange(Nx), np.arange(Ny))
    base_x = (grid_x.flatten() * cell_w + cell_w * 0.5).astype(np.float32)
    base_y = (grid_y.flatten() * cell_h + cell_h * 0.5).astype(np.float32)

    np.random.seed(seed)
    jitter_x = (np.random.rand(N_total).astype(np.float32) - 0.5) * cell_w * 0.85
    jitter_y = (np.random.rand(N_total).astype(np.float32) - 0.5) * cell_h * 0.85

    points_x = base_x + jitter_x
    points_y = base_y + jitter_y
    directions = (np.random.rand(N_total, 2).astype(np.float32) - 0.5) * 2.0
    
    return points_x, points_y, directions

def calculate_caustics_at_time(t_real, points_x, points_y, directions):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    
    t = t_real * CONFIG["global_speed"]
    
    time_w = t * 2.0 * CONFIG["flow_mult"]
    freq = CONFIG["wave_freq"]
    amp = CONFIG["wave_amp"]

    warp_x = np.sin(y * freq + time_w) * amp + np.sin(x * freq * 1.5 - time_w * 1.2) * (amp * 0.6)
    warp_y = np.cos(x * freq + time_w) * amp + np.cos(y * freq * 1.5 + time_w * 0.8) * (amp * 0.6)

    wx = (x + warp_x) % W
    wy = (y + warp_y) % H

    time_p = t * 1.5 * CONFIG["morph_mult"]
    flow_x = t * 30.0 * CONFIG["base_flow_x"] * CONFIG["flow_mult"]
    flow_y = t * 30.0 * CONFIG["base_flow_y"] * CONFIG["flow_mult"]

    px = (points_x + np.sin(time_p + directions[:, 0]*10) * 15.0 + flow_x) % W
    py = (points_y + np.cos(time_p + directions[:, 1]*10) * 15.0 + flow_y) % H

    offsets = np.array([[-W,-H], [0,-H], [W,-H], [-W,0], [0,0], [W,0], [-W,H], [0,H], [W,H]])
    exp_px = (px[:, None] + offsets[:, 0]).flatten()
    exp_py = (py[:, None] + offsets[:, 1]).flatten()

    dist_sq = (wx[:, :, None] - exp_px[None, None, :])**2 + (wy[:, :, None] - exp_py[None, None, :])**2
    idx = np.argpartition(dist_sq, 1, axis=-1)[..., :2]
    
    idx1, idx2 = idx[..., 0], idx[..., 1]
    I, J = np.ogrid[:H, :W]
    d1 = dist_sq[I, J, idx1]
    d2 = dist_sq[I, J, idx2]

    swap = d1 > d2
    idx1_f = np.where(swap, idx2, idx1)
    idx2_f = np.where(swap, idx1, idx2)

    P1x, P1y = exp_px[idx1_f], exp_py[idx1_f]
    P2x, P2y = exp_px[idx2_f], exp_py[idx2_f]

    Mx, My = (P1x + P2x) / 2.0, (P1y + P2y) / 2.0
    Dx, Dy = P2x - P1x, P2y - P1y
    length = np.sqrt(Dx**2 + Dy**2) + 1e-8
    nx, ny = Dx / length, Dy / length

    Vx, Vy = wx - Mx, wy - My
    exact_dist = np.abs(Vx * nx + Vy * ny)

    thickness = CONFIG["thickness"]
    line_mask = np.clip(1.0 - (exact_dist / thickness), 0.0, 1.0)
    return line_mask ** 1.3

def get_looped_layer(t_current, duration, seed):
    px, py, dirs = get_base_points(seed)
    
    # Кроссфейд для зацикливания
    mask_A = calculate_caustics_at_time(t_current, px, py, dirs)
    mask_B = calculate_caustics_at_time(t_current - duration, px, py, dirs)
    
    progress = t_current / duration
    return mask_A * (1.0 - progress) + mask_B * progress

# ============================================================
# RENDER LOOP
# ============================================================

total_frames = int(CONFIG["fps"] * CONFIG["duration"])
duration = float(CONFIG["duration"])

writer = imageio.get_writer(
    output_path,
    fps=CONFIG["fps"],
    format="FFMPEG",
    codec="png",
    pixelformat="rgba",
    output_params=["-vcodec", "png"]
)

print(f"Рендер БЫСТРОЙ версии (1 слой, зациклен, с альфой): {output_path}")

r, g, b = [c/255.0 for c in CONFIG["color"]]
a = CONFIG["alpha"]

for frame in range(total_frames):
    t = frame / CONFIG["fps"]
    
    # Генерируем единственный слой
    mask = get_looped_layer(t, duration, seed=42)
    
    frame_rgba = np.zeros((H, W, 4), dtype=np.float32)
    
    # Композитинг одного слоя
    frame_rgba[..., 0] = mask * r * a
    frame_rgba[..., 1] = mask * g * a
    frame_rgba[..., 2] = mask * b * a
    frame_rgba[..., 3] = mask * a 
    
    frame_rgba = np.clip(frame_rgba, 0.0, 1.0)
    final_frame = (frame_rgba * 255).astype(np.uint8)
    
    writer.append_data(final_frame)
    
    progress_pct = int((frame + 1) / total_frames * 100)
    print(f"\rРендер: [{progress_pct:3d}%] Кадр {frame+1}/{total_frames}", end="")

writer.close()
print("\nГОТОВО! Оптимизированный рендер завершен.")