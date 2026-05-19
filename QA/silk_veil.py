# ============================================================
# Pinned Silk Energy (DYNAMIC DRUNKEN CHAOS, MIN/MAX CONTROL)
# ============================================================

import os
import numpy as np
import imageio.v2 as imageio

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "output_video": "silk_drunken_chaos.mov",
    "width": 385,
    "height": 24,
    "fps": 60,
    "duration": 1.0, 

    "anchor": {
        "color": (255, 255, 255),
        "thickness": 0.5,       
        "alpha": 0.45,
        "waves": 0.0,           
        "amp": 0.0,            
        "speed": 0.5,
        "edge_pinch": 2.0       # 2.0 = плавно выходит из центра
    },

    # ==========================================
    # КРАСНЫЕ ПУЧКИ (ЭКСТРЕМАЛЬНЫЙ ХАОС)
    # ==========================================
    "gold_veil": {
        "count": 6,
        "color": (255, 0, 0), 
        "alpha": 0.9, 
        
        # ТОТАЛЬНЫЙ КОНТРОЛЬ: Границы рандома для каждой линии
        "thickness_min": 0.3,
        "thickness_max": 2.25,
        
        "spread_amp_min": 1.0,
        "spread_amp_max": 8.0,
        
        "wave_complexity_min": 2.0,
        "wave_complexity_max": 24.0,
        
        "speed_min": 2.0,
        "speed_max": 4.0,
        
        # СИЛА УДЕРЖАНИЯ КРАЕВ
        # 0.1 = моментально рвется в хаос от самого края.
        # 1.0 = линейно. 2.0 = плавно.
        "edge_pinch": 0.7,     
        
        "fade_factor": False     
    },

    "micro_veil": {
        "count": 3,
        "color": (255, 255, 255),
        "alpha": 0.25,
        
        "thickness_min": 0.5,
        "thickness_max": 1.0,
        "spread_amp_min": 0.5,
        "spread_amp_max": 2.0,
        "wave_complexity_min": 2.0,
        "wave_complexity_max": 6.0,
        "speed_min": 3.0,
        "speed_max": 4.0,
        
        "edge_pinch": 1.5, # Плавнее, чем красные
        "fade_factor": False
    }
}

# ============================================================
# ENGINE SETUP
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(SCRIPT_DIR, CONFIG["output_video"])
W, H = CONFIG["width"], CONFIG["height"]

Y_grid, X_grid = np.mgrid[0:H, 0:W].astype(np.float32)
NX = X_grid / W

def init_drunken_bundle(cfg_layer, seed):
    np.random.seed(seed)
    N = cfg_layer["count"]
    
    # Базовые параметры линии (выбираются случайно между min и max)
    b_amps = np.random.uniform(cfg_layer["spread_amp_min"], cfg_layer["spread_amp_max"], N)
    b_freqs = np.random.uniform(cfg_layer["wave_complexity_min"], cfg_layer["wave_complexity_max"], N)
    b_thicks = np.random.uniform(cfg_layer["thickness_min"], cfg_layer["thickness_max"], N)
    speeds = np.random.uniform(cfg_layer["speed_min"], cfg_layer["speed_max"], N)
    dirs = np.random.choice([-1.0, 1.0], N)
    
    # Уникальные фазы для ВОЛН МОДУЛЯЦИИ (чтобы каждая линия "пьянела" в своем ритме)
    p_main = np.random.rand(N) * np.pi * 2.0  # Фаза основной волны
    p_wobble_amp = np.random.rand(N) * np.pi * 2.0 # Фаза пульсации амплитуды
    p_wobble_thk = np.random.rand(N) * np.pi * 2.0 # Фаза пульсации толщины
    p_wobble_frq = np.random.rand(N) * np.pi * 2.0 # Фаза сжатия волны (эффект пружины)
    
    return b_amps, b_freqs, b_thicks, speeds, dirs, p_main, p_wobble_amp, p_wobble_thk, p_wobble_frq

# Инициализируем пучки
g_a, g_f, g_t, g_s, g_d, g_pm, g_pa, g_pt, g_pf = init_drunken_bundle(CONFIG["gold_veil"], seed=42)
m_a, m_f, m_t, m_s, m_d, m_pm, m_pa, m_pt, m_pf = init_drunken_bundle(CONFIG["micro_veil"], seed=99)

def render_frame_at_time(time_in_seconds):
    frame_rgba = np.zeros((H, W, 4), dtype=np.float32)
    time_rad = (time_in_seconds / CONFIG["duration"]) * np.pi * 2.0
    
    # --------------------------------------------------------
    # 1. ЯКОРЬ
    # --------------------------------------------------------
    a_cfg = CONFIG["anchor"]
    env_anchor = np.sin(NX * np.pi) ** a_cfg["edge_pinch"]
    anchor_y = (H / 2.0) + (np.sin(NX * a_cfg["waves"] * np.pi + time_rad * a_cfg["speed"]) * a_cfg["amp"] * env_anchor)
    
    dist_anchor = np.abs(Y_grid - anchor_y)
    v_thick_a = max(a_cfg["thickness"], 1.0)
    op_mult_a = min(a_cfg["thickness"], 1.0)
    
    mask_anchor = (np.clip(1.0 - (dist_anchor / v_thick_a), 0.0, 1.0) ** 1.2) * op_mult_a
    anc_r, anc_g, anc_b = [c/255.0 for c in a_cfg["color"]]

    # --------------------------------------------------------
    # 2. ФУНКЦИЯ ДИНАМИЧЕСКИХ ПУЧКОВ ("С БОДУНА")
    # --------------------------------------------------------
    def generate_drunken_bundle(cfg, b_amps, b_freqs, b_thicks, speeds, dirs, p_main, p_amp, p_thk, p_frq):
        mask_total = np.zeros((H, W), dtype=np.float32)
        
        # Генерируем Envelope на основе настройки слоя
        envelope = np.sin(NX * np.pi) ** cfg["edge_pinch"]
        
        for i in range(cfg["count"]):
            # МАГИЯ 1: Динамическая толщина (Толстеет и худеет вдоль линии)
            # sin дает от -1 до 1. Превращаем в множитель от 0.2 до 1.0
            thick_mod = (np.sin(NX * 4.0 - time_rad * 1.5 + p_thk[i]) * 0.4) + 0.6
            current_thick = b_thicks[i] * thick_mod
            
            v_thick = np.maximum(current_thick, 1.0)
            op_mult = np.minimum(current_thick, 1.0)
            
            # МАГИЯ 2: Динамическая амплитуда (То взлетает, то успокаивается)
            amp_mod = (np.sin(NX * 3.0 + time_rad * 2.0 + p_amp[i]) * 0.45) + 0.55
            current_amp = b_amps[i] * amp_mod
            
            # МАГИЯ 3: Искажение пространства (Frequency/Phase Warping)
            # Это заставляет волну "сжиматься" и "растягиваться" как пружину
            phase_warp = np.sin(NX * 5.0 - time_rad * 1.0 + p_frq[i]) * 1.5
            
            # Итоговая сумасшедшая волна
            wave = np.sin(NX * b_freqs[i] * np.pi + time_rad * speeds[i] * dirs[i] + phase_warp + p_main[i])
            
            # Применяем огибающую (Envelope) к отклонению от якоря
            veil_y = anchor_y + (wave * current_amp * envelope)
            
            dist = np.abs(Y_grid - veil_y)
            base_mask = (np.clip(1.0 - (dist / v_thick), 0.0, 1.0) ** 1.5) * op_mult
            
            if cfg.get("fade_factor", False):
                deviation = np.abs(veil_y - anchor_y)
                fade = np.clip(1.0 - (deviation / (current_amp * 0.95 + 0.001)), 0.0, 1.0)
                base_mask *= (fade ** 1.5)
                
            mask_total += base_mask
        return mask_total

    mask_gold = generate_drunken_bundle(CONFIG["gold_veil"], g_a, g_f, g_t, g_s, g_d, g_pm, g_pa, g_pt, g_pf)
    mask_micro = generate_drunken_bundle(CONFIG["micro_veil"], m_a, m_f, m_t, m_s, m_d, m_pm, m_pa, m_pt, m_pf)

    # --------------------------------------------------------
    # 3. КОМПОЗИТИНГ
    # --------------------------------------------------------
    def add_layer(mask, cfg):
        r, g, b = [c/255.0 for c in cfg["color"]]
        alpha = cfg["alpha"]
        frame_rgba[..., 0] += mask * r * alpha
        frame_rgba[..., 1] += mask * g * alpha
        frame_rgba[..., 2] += mask * b * alpha
        frame_rgba[..., 3] += mask * alpha

    add_layer(mask_gold, CONFIG["gold_veil"])
    add_layer(mask_micro, CONFIG["micro_veil"])
    
    frame_rgba[..., 0] += mask_anchor * anc_r * a_cfg["alpha"]
    frame_rgba[..., 1] += mask_anchor * anc_g * a_cfg["alpha"]
    frame_rgba[..., 2] += mask_anchor * anc_b * a_cfg["alpha"]
    frame_rgba[..., 3] = np.maximum(frame_rgba[..., 3], mask_anchor * a_cfg["alpha"])

    return np.clip(frame_rgba, 0.0, 1.0)

# ============================================================
# SEAMLESS LOOP RENDERING
# ============================================================

total_frames = int(CONFIG["fps"] * CONFIG["duration"])
duration = CONFIG["duration"]

writer = imageio.get_writer(
    output_path, fps=CONFIG["fps"], format="FFMPEG",
    codec="png", pixelformat="rgba", output_params=["-vcodec", "png"]
)

print(f"Рендер Энергии (Живой Хаос, MIN/MAX Конфиг): {output_path}")

for frame in range(total_frames):
    t = frame / CONFIG["fps"]
    
    frame_A = render_frame_at_time(t)
    frame_B = render_frame_at_time(t - duration)
    
    progress = t / duration 
    mix_factor = progress * progress * (3.0 - 2.0 * progress)
    
    final_rgba = frame_A * (1.0 - mix_factor) + frame_B * mix_factor
    
    final_frame = (final_rgba * 255).astype(np.uint8)
    writer.append_data(final_frame)
    
    progress_pct = int((frame + 1) / total_frames * 100)
    print(f"\rРендер: [{progress_pct:3d}%] Кадр {frame+1}/{total_frames}", end="")

writer.close()
print("\nГОТОВО! Эффект пьяной линии с тотальным контролем через конфиг сохранен.")