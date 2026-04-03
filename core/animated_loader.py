# RZMenu/core/animated_loader.py
"""
Загрузчик анимированных изображений для RZMenu.
Поддерживает GIF (через Pillow) и MP4/WebM/AVI (через imageio + imageio-ffmpeg).

Главная цель — дедупликация кадров:
  - Визуально идентичные последовательные кадры схлопываются в один.
  - frametime (длительность показа) суммируется у схлопнутых кадров.
  - Итог: минутное видео с 80% статики занимает в атласе в 5 раз меньше места.

Выходной формат кадра (dict):
  {
      'pixels': np.ndarray (H, W, 4), dtype=float32, диапазон [0, 1],
      'frametime': float,   # сколько секунд показывается этот кадр
      'size': (int, int),   # (width, height)
  }
"""

import numpy as np

# Порог схожести для дедупликации (SSIM-приближение через MAE).
# 0.0 = полностью идентичны, 1.0 = совершенно разные.
# 0.04 даёт хорошее соотношение: мелкие вариации сжимаются, крупные изменения сохраняются.
DEDUPE_THRESHOLD = 0.04


# ─── Внутренние утилиты ───────────────────────────────────────────────────────

def _pil_to_float32_rgba(pil_img):
    """Конвертирует PIL Image в float32 RGBA numpy массив (H, W, 4)."""
    if pil_img.mode != 'RGBA':
        pil_img = pil_img.convert('RGBA')
    arr = np.array(pil_img, dtype=np.uint8).astype(np.float32) / 255.0
    return arr  # (H, W, 4)


def _frames_are_similar(a: np.ndarray, b: np.ndarray, threshold: float) -> bool:
    """
    Сравнивает два RGBA float32 кадра через MAE.
    threshold=0 означает полную идентичность.
    """
    if a.shape != b.shape:
        return False
    # Если порог 0, проверяем массив на прямое соответствие
    if threshold <= 0:
        return np.array_equal(a, b)
    
    mae = float(np.mean(np.abs(a - b)))
    return mae < threshold


# ─── Дедупликация ─────────────────────────────────────────────────────────────

def deduplicate_frames(frames: list, threshold: float = DEDUPE_THRESHOLD) -> list:
    """
    Схлопывает визуально идентичные последовательные кадры.
    Frametime схлопнутых кадров суммируется в последний уникальный кадр группы.

    Args:
        frames: список dict с ключами 'pixels', 'frametime', 'size'
        threshold: MAE-порог (0.0–1.0); меньше = строже

    Returns:
        Отфильтрованный список уникальных кадров.
    """
    if not frames:
        return []

    result = [frames[0].copy()]

    for frame in frames[1:]:
        prev = result[-1]
        if _frames_are_similar(prev['pixels'], frame['pixels'], threshold):
            # Кадр идентичен предыдущему — суммируем время, не добавляем новый блок
            result[-1] = {
                'pixels': prev['pixels'],
                'frametime': prev['frametime'] + frame['frametime'],
                'size': prev['size'],
            }
        else:
            result.append(frame.copy())

    return result


# ─── GIF ──────────────────────────────────────────────────────────────────────

def load_gif(filepath: str, max_frames: int = 64) -> list:
    """
    Читает GIF через Pillow и возвращает список кадров с frametime.
    Кадры конвертируются в float32 RGBA.

    Args:
        filepath: путь к .gif файлу
        max_frames: максимум кадров до дедупликации (не ограничивает уникальные)

    Returns:
        Список dict: [{'pixels': ndarray, 'frametime': float, 'size': (w, h)}, ...]

    Raises:
        ImportError: если Pillow не установлен
        IOError: если файл не является GIF или не может быть прочитан
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError(
            "Pillow не установлен. Установите его через Deps Manager."
        )

    try:
        gif = Image.open(filepath)
    except Exception as e:
        raise IOError(f"Не удалось открыть GIF: {e}")

    if not hasattr(gif, 'n_frames'):
        raise IOError(f"Файл не является анимированным GIF: {filepath}")

    frames = []
    frame_idx = 0
    try:
        while frame_idx < min(gif.n_frames, max_frames):
            gif.seek(frame_idx)

            # duration в миллисекундах, fallback 100ms если не указан
            duration_ms = gif.info.get('duration', 100)
            # Минимум 16ms (~60fps), защита от нулевых значений
            duration_ms = max(duration_ms, 16)
            frametime = duration_ms / 1000.0

            pixels = _pil_to_float32_rgba(gif.copy())
            w, h = gif.size

            frames.append({
                'pixels': pixels,
                'frametime': frametime,
                'size': (w, h),
            })
            frame_idx += 1
    except EOFError:
        pass  # Нормальный конец GIF

    return frames


# ─── Видео (MP4 / WebM / AVI) ─────────────────────────────────────────────────

def load_video(filepath: str, max_frames: int = 64) -> list:
    """
    Читает видео через imageio + imageio-ffmpeg и возвращает список кадров.
    Требует установки imageio и imageio-ffmpeg через Deps Manager.

    Args:
        filepath: путь к видео (.mp4, .webm, .avi, .mov, ...)
        max_frames: максимум кадров до дедупликации

    Returns:
        Список dict: [{'pixels': ndarray, 'frametime': float, 'size': (w, h)}, ...]

    Raises:
        ImportError: если imageio или imageio-ffmpeg не установлены
    """
    try:
        import imageio.v3 as iio
    except ImportError:
        raise ImportError(
            "imageio не установлен.\n"
            "Установите imageio и imageio-ffmpeg через Deps Manager."
        )

    try:
        # Читаем метаданные для получения FPS
        props = iio.improps(filepath, plugin='pyav')
        fps = getattr(props, 'fps', None) or 24.0
        frametime = 1.0 / max(fps, 0.1)
    except Exception:
        frametime = 1.0 / 24.0  # fallback: 24fps

    frames = []
    try:
        for idx, raw_frame in enumerate(iio.imiter(filepath, plugin='pyav')):
            if idx >= max_frames:
                break

            # raw_frame: uint8 RGB или RGBA (H, W, 3|4)
            arr = np.array(raw_frame, dtype=np.float32) / 255.0

            # Конвертируем RGB → RGBA если нужно
            if arr.ndim == 3 and arr.shape[2] == 3:
                alpha = np.ones((*arr.shape[:2], 1), dtype=np.float32)
                arr = np.concatenate([arr, alpha], axis=2)

            h, w = arr.shape[:2]
            frames.append({
                'pixels': arr,
                'frametime': frametime,
                'size': (w, h),
            })
    except Exception as e:
        if not frames:
            raise IOError(f"Не удалось прочитать видеофайл: {e}")
        # Если хоть что-то прочитали — продолжаем с тем что есть
        print(f"[RZM AnimLoader] Предупреждение: чтение видео прервано на кадре {len(frames)}: {e}")

    return frames


# ─── Blender Images ───────────────────────────────────────────────────────────

def frames_to_blender_images(frames: list, base_name: str) -> list:
    """
    Конвертирует список кадров в bpy.data.images.
    Именование: "{base_name}_anim_{idx:04d}"

    Существующие изображения с тем же именем ПЕРЕСОЗДАЮТСЯ (для корректного обновления).

    Args:
        frames: список dict с 'pixels', 'size'
        base_name: базовое имя изображения (display_name RZMenuImage)

    Returns:
        Список созданных bpy.data.Image.
    """
    import bpy

    created = []
    for idx, frame in enumerate(frames):
        name = f"{base_name}_anim_{idx:04d}"
        w, h = frame['size']
        pixels = frame['pixels']  # (H, W, 4) float32

        # Удаляем существующее если есть
        existing = bpy.data.images.get(name)
        if existing:
            bpy.data.images.remove(existing)

        img = bpy.data.images.new(name=name, width=w, height=h, alpha=True)
        img.file_format = 'PNG'

        # Blender ожидает плоский (W*H*4,) float32 в порядке bottom-up.
        # Наши пиксели хранятся top-down (row 0 = top), поэтому переворачиваем по Y.
        flipped = np.flipud(pixels).flatten().tolist()
        img.pixels[:] = flipped

        created.append(img)

    return created


# ─── Высокоуровневый API ──────────────────────────────────────────────────────

# ─── ГЛОБАЛЬНАЯ ДЕДУПЛИКАЦИЯ ──────────────────────────────────────────────────

def deduplicate_global(raw_frames: list, threshold: float = 0.04) -> tuple:
    """
    Анализирует ВЕСЬ список кадров и находит уникальные.
    Возвращает (unique_frames_list, sequence_mapping).
    
    sequence_mapping: список индексов в unique_frames_list.
    """
    if not raw_frames:
        return [], []

    unique_frames = []
    sequence = []

    for frame in raw_frames:
        found_idx = -1
        # Ищем среди уже найденных уникальных
        for i, u_frame in enumerate(unique_frames):
            if _frames_are_similar(u_frame['pixels'], frame['pixels'], threshold):
                found_idx = i
                break
        
        if found_idx == -1:
            # Новый уникальный кадр
            unique_frames.append(frame.copy())
            sequence.append(len(unique_frames) - 1)
        else:
            # Повтор существующего — просто добавляем индекс в последовательность
            sequence.append(found_idx)

    # После того как построили индексы, нужно "схлопнуть" идущие подряд 
    # одинаковые индексы в один с суммарной длительностью.
    collapsed_sequence = []
    if sequence:
        curr_idx = sequence[0]
        curr_dur = raw_frames[0]['frametime']
        
        for i in range(1, len(sequence)):
            next_idx = sequence[i]
            next_dur = raw_frames[i]['frametime']
            if next_idx == curr_idx:
                curr_dur += next_dur
            else:
                collapsed_sequence.append({'idx': curr_idx, 'duration': curr_dur})
                curr_idx = next_idx
                curr_dur = next_dur
        
        collapsed_sequence.append({'idx': curr_idx, 'duration': curr_dur})

    return unique_frames, collapsed_sequence


# ─── Высокоуровневый API ──────────────────────────────────────────────────────

def load_animated_advanced(filepath: str, 
                           preset: str = 'ADAPTIVE', 
                           start_frame: int = 0, 
                           end_frame: int = 0, 
                           max_source_frames: int = 256) -> tuple:
    """
    Основная функция для Update Atlas Layout.
    Извлекает кадры, применяет пресет и возвращает данные для упаковки.
    
    Args:
        preset: ECONOMY, ECONOMY_PLUS, ADAPTIVE, ADAPTIVE_PLUS, EXTREME
        
    Returns:
        (unique_frames, sequence)
    """
    ext = filepath.lower().rsplit('.', 1)[-1] if '.' in filepath else ''
    
    # 1. Читаем сырые кадры
    if ext == 'gif':
        raw_frames = load_gif(filepath, max_source_frames)
    elif ext in ('mp4', 'webm', 'avi', 'mov', 'mkv'):
        raw_frames = load_video(filepath, max_source_frames)
    else:
        raise ValueError(f"Format .{ext} not supported")

    if not raw_frames:
        raise ValueError("No frames found")

    # 2. Обрезка (Trim)
    # Если end_frame = 0, берем до конца
    if end_frame <= 0 or end_frame > len(raw_frames):
        end_frame = len(raw_frames)
    start_frame = max(0, min(start_frame, end_frame - 1))
    
    raw_frames = raw_frames[start_frame:end_frame]

    # 3. Применение пресетов (Frame Selection)
    threshold = 0.04 # Adaptive default
    
    if preset == 'EXTREME':
        threshold = 0.0001
    elif preset == 'ADAPTIVE_PLUS':
        threshold = 0.02
    elif preset == 'ADAPTIVE':
        threshold = 0.04
    elif preset.startswith('ECONOMY'):
        # Для экономики СНАЧАЛА делаем даунсэмплинг, потом дедупликацию
        limit = 8 if preset == 'ECONOMY' else 16
        if len(raw_frames) > limit:
            indices = np.linspace(0, len(raw_frames) - 1, limit, dtype=int)
            # При даунсэмплинге нужно перераспределить длительность, чтобы итоговое время не поменялось
            total_dur = sum(f['frametime'] for f in raw_frames)
            sampled_frames = []
            for idx in indices:
                f = raw_frames[idx].copy()
                f['frametime'] = total_dur / limit
                sampled_frames.append(f)
            raw_frames = sampled_frames
        threshold = 0.05 # Чуть грубее для экономики

    # 4. Глобальная дедупликация
    unique_frames, sequence = deduplicate_global(raw_frames, threshold)
    
    return unique_frames, sequence
