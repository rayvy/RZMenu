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
    Сравнивает два RGBA float32 кадра через MAE и проверку локальных изменений.
    threshold=0 означает полную идентичность.
    """
    if a.shape != b.shape:
        return False
    # Если порог 0, проверяем массив на прямое соответствие
    if threshold <= 0:
        return np.array_equal(a, b)
    
    diff = np.abs(a - b)
    mae = float(np.mean(diff))
    
    # 1. Глобальная разница (по всему изображению)
    if mae >= threshold:
        return False
        
    # 2. Локальная разница (для малых анимированных областей)
    # Ищем максимальное изменение (RGB или Alpha) для каждого пикселя
    pixel_diff = np.max(diff, axis=-1)
    
    # Считаем пиксели, изменившиеся больше чем на ~25/255 (отсев шума сжатия)
    changed_pixels = np.sum(pixel_diff > 0.1)
    
    # Порог количества пикселей, который считается "движением" (а не шумом).
    # Масштабируется от базового threshold, чтобы уважать пресеты качества (ADAPTIVE, ECONOMY).
    min_changed_pixels = max(int(threshold * 1000), 5)
    min_changed_fraction = int(a.shape[0] * a.shape[1] * threshold * 0.01)
    
    min_pixels = max(min_changed_pixels, min_changed_fraction)
    
    if changed_pixels > min_pixels:
        return False
        
    return True


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
    print(f"[RZM AnimLoader] Начинаем чтение видео: {filepath} (max_frames={max_frames})")
    try:
        for idx, raw_frame in enumerate(iio.imiter(filepath, plugin='pyav', format='rgba')):
            if idx >= max_frames:
                print(f"[RZM AnimLoader] Достигнут лимит кадров ({max_frames}). Остановка чтения.")
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
            
        print(f"[RZM AnimLoader] Успешно прочитано кадров: {len(frames)}")
        if len(frames) == 1:
            print(f"[RZM AnimLoader] ВНИМАНИЕ: Извлечён всего 1 кадр! Либо видео состоит из 1 кадра, либо кодек (ProRes/H265) прервал поток.")
            
    except Exception as e:
        if not frames:
            print(f"[RZM AnimLoader] КРИТИЧЕСКАЯ ОШИБКА кодека при чтении {filepath}: {e}")
            raise IOError(f"Не удалось прочитать видеофайл: {e}")
        # Если хоть что-то прочитали — продолжаем с тем что есть
        print(f"[RZM AnimLoader] ПРЕДУПРЕЖДЕНИЕ: чтение прервано кодеком на кадре {len(frames)}: {e}")

    return frames


# ─── Blender Images ───────────────────────────────────────────────────────────

def frames_to_blender_images(frames: list, base_name: str, colorspace: str = 'sRGB') -> list:
    """
    Конвертирует список кадров в bpy.data.images.
    Именование: "{base_name}_anim_{idx:04d}"

    Существующие изображения с тем же именем ПЕРЕСОЗДАЮТСЯ (для корректного обновления).

    Args:
        frames: список dict с 'pixels', 'size'
        base_name: базовое имя изображения (display_name RZMenuImage)
        colorspace: 'sRGB' или 'Non-Color'. Для SVG рендеров лучше сразу Non-Color.

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
        img.colorspace_settings.name = colorspace

        # Blender ожидает плоский (W*H*4,) float32 в порядке bottom-up.
        # Наши пиксели хранятся top-down (row 0 = top), поэтому переворачиваем по Y.
        # Используем foreach_set для скорости и стабильности.
        flipped = np.ascontiguousarray(np.flipud(pixels), dtype=np.float32)
        img.pixels.foreach_set(flipped.ravel())
        img.update()

        created.append(img)

    return created


# ─── Высокоуровневый API ──────────────────────────────────────────────────────

# ─── ГЛОБАЛЬНАЯ ДЕДУПЛИКАЦИЯ ──────────────────────────────────────────────────

def deduplicate_global(raw_frames: list, threshold: float = 0.04, double_pass: bool = True) -> tuple:
    """
    Анализирует ВЕСЬ список кадров и находит уникальные.
    
    Args:
        raw_frames: список dict с кадрами (pixels, frametime)
        threshold: порог схожести
        double_pass:
            True: Глобальное слияние (циклические дубликаты в разных частях таймлайна схлопываются).
            False: Только последовательное слияние (соседние дубликаты).
    
    Returns:
        (unique_frames_list, mapping)
    """
    if not raw_frames:
        return [], []

    # --- PASS 1: Temporal (Sequential) Grouping ---
    # Всегда схлопываем идущие подряд похожие кадры.
    temporal_groups = []
    if raw_frames:
        curr = raw_frames[0].copy()
        for i in range(1, len(raw_frames)):
            frame = raw_frames[i]
            if _frames_are_similar(curr['pixels'], frame['pixels'], threshold):
                curr['frametime'] += frame['frametime']
            else:
                temporal_groups.append(curr)
                curr = frame.copy()
        temporal_groups.append(curr)

    if not double_pass:
        # Если Double Pass выключен, temporal_groups и есть наши уникальные кадры
        mapping = []
        for i, group in enumerate(temporal_groups):
            mapping.append({'idx': i, 'duration': group['frametime']})
        return temporal_groups, mapping

    # --- PASS 2: Global Merging (Optional) ---
    unique_frames = []
    group_to_unique = [] # индекс в temporal_groups -> индекс в unique_frames

    for group in temporal_groups:
        found_idx = -1
        # Ищем среди уже накопленных уникальных
        for i, u_frame in enumerate(unique_frames):
            if _frames_are_similar(u_frame['pixels'], group['pixels'], threshold):
                found_idx = i
                break
        
        if found_idx == -1:
            unique_frames.append(group.copy())
            group_to_unique.append(len(unique_frames) - 1)
        else:
            group_to_unique.append(found_idx)

    # Reconstruct mapping
    mapping = []
    for i, u_idx in enumerate(group_to_unique):
        mapping.append({
            'idx': u_idx,
            'duration': temporal_groups[i]['frametime']
        })

    return unique_frames, mapping


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
    import bpy
    filepath = bpy.path.abspath(filepath)
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

    # 3. Применение пресетов (Adaptive Selection & Limits)
    threshold = 0.04
    double_pass = True
    
    if preset == 'ECONOMY':
        # Жесткий лимит: 4 кадра
        limit = 4
        if len(raw_frames) > limit:
            indices = np.linspace(0, len(raw_frames) - 1, limit, dtype=int)
            total_dur = sum(f['frametime'] for f in raw_frames)
            sampled = []
            for idx in indices:
                f = raw_frames[idx].copy()
                f['frametime'] = total_dur / limit
                sampled.append(f)
            raw_frames = sampled
        threshold = 0.06
        double_pass = False # Для экономии нет смысла в сложном поиске циклов

    elif preset == 'ADAPTIVE_LIGHT':
        threshold = 0.04
        double_pass = True
    elif preset == 'ADAPTIVE':
        threshold = 0.02
        double_pass = True
    elif preset == 'ADAPTIVE_HEAVY':
        threshold = 0.005 # Высокое качество
        double_pass = False # Как просил юзер: выключаем для Heavy

    # 4. Дедупликация (Double Pass или Sequential)
    unique_frames, sequence = deduplicate_global(raw_frames, threshold, double_pass)
    
    # 5. Санитария для ECONOMY (если после дедупликации все еще > 4 — берем первые 4)
    if preset == 'ECONOMY' and len(unique_frames) > 4:
        unique_frames = unique_frames[:4]
        for m in sequence:
            if m['idx'] >= 4: m['idx'] = 0

    return unique_frames, sequence


# ─── QT PREVIEW API (In-Memory) ───────────────────────────────────────────────

class VideoReaderCache:
    """Кэш для открытых файлов imageio, чтобы ускорить скраббинг."""
    _instance = None
    
    def __init__(self):
        self.last_path = None
        self.reader = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = VideoReaderCache()
        return cls._instance

    def get_reader(self, filepath):
        import imageio.v3 as iio
        if self.last_path == filepath and self.reader is not None:
            return self.reader
        
        # Закрываем старый
        if self.reader is not None:
            try: self.reader.close()
            except: pass
        
        try:
            self.last_path = filepath
            # В v3 нет долгоживущих ридеров в обычном imread, 
            # но мы можем использовать iio.imopen
            self.reader = iio.imopen(filepath, "r", plugin="pyav")
            return self.reader
        except Exception as e:
            print(f"[RZM] Failed to open video reader for {filepath}: {e}")
            return None

def get_frame_info(filepath: str) -> dict:
    """
    Возвращает метаданные файла для превью-плеера.
    """
    import bpy
    filepath = bpy.path.abspath(filepath)
    cache = VideoReaderCache.get_instance()
    reader = cache.get_reader(filepath)
    if not reader:
        return {'frame_count': 1, 'fps': 24.0, 'duration': 0.0416}
    
    try:
        props = reader.properties()
        count = getattr(props, 'n_frames', 0)
        if count == 0:
             # Fallback: пробуем итерировать или просто 100
             count = 100 
        
        fps = getattr(props, 'fps', 24.0)
        return {
            'frame_count': count,
            'fps': fps,
            'duration': count / max(fps, 0.1)
        }
    except Exception as e:
        print(f"[RZM] Error getting frame info: {e}")
        return {'frame_count': 1, 'fps': 24.0, 'duration': 0.0416}


def get_frame_at(filepath: str, index: int) -> np.ndarray:
    """
    Извлекает ОДИН кадр из файла по индексу с использованием кэша ридера.
    """
    import bpy
    filepath = bpy.path.abspath(filepath)
    cache = VideoReaderCache.get_instance()
    reader = cache.get_reader(filepath)
    if not reader:
        return None
        
    try:
        raw_frame = reader.read(index=index, format="rgba")
        
        # Конвертация в float32 RGBA
        arr = np.array(raw_frame, dtype=np.float32) / 255.0
        
        if arr.ndim == 3 and arr.shape[2] == 3:
            alpha = np.ones((*arr.shape[:2], 1), dtype=np.float32)
            arr = np.concatenate([arr, alpha], axis=2)
            
        return arr
    except Exception as e:
        # Если ошибка при чтении, возможно ридер "протух", сбрасываем
        cache.reader = None
        cache.last_path = None
        # Убираем спам в консоль, так как случайный доступ в pyav иногда может падать на проблемных кадрах GIF
        # print(f"[RZM] Error reading frame {index}: {e}")
        return None
