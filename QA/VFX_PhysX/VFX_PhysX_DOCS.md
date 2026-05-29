# VFX PhysX — World-Space Motion Trailing System

Экспериментальная система физически корректного шлейфа VFX-партиклов, реагирующих на движение персонажа в мировом пространстве.

---

## Концепция

Стандартные VFX-кривые (`vfx_curve_cs.hlsl`) расставляют партиклы статично вдоль сплайна в локальном пространстве персонажа. При движении персонажа они просто следуют за ним без инерции.

**VFX PhysX** добавляет физическую задержку: кончик сплайна (`path_progress = 1.0`) отстаёт от персонажа на `N` кадров, корень (`path_progress = 0.0`) остаётся закреплённым. Результат — волнообразный шлейф как у Sandevistan.

---

## Архитектура системы

```
[Draw Call персонажа]
        │
        ▼
CustomShaderComputeHairHistory   ← записывает текущую матрицу cb1 (vs-cb1) в кольцевой буфер
        │                          (ouroboros_adaptive_pos.hlsl)
        ▼
CustomShaderWriteHairHistory     ← записывает текущий vb0 (скиннед вертексы) в буфер истории
        │                          (ouroboros_adaptive_vb.hlsl)
        ▼
[Present]
        │
        ▼
CustomShaderRZM_VFX_PromeiaHairB ← читает историю матриц, считает дельту позиции,
                                   смещает партиклы (vfx_curve_physics_cs.hlsl)
```

---

## INI — Полный пример

### 1. Ресурсы истории

```ini
[ResourcePromeiaHairHistoryBuffer]
type = RWBuffer
format = R32G32B32A32_FLOAT
array = 257
; 64 слота * 4 float4 на матрицу = 256, + 1 слот состояния = 257

[ResourcePromeiaHairSkinnedHistory]
type = RWStructuredBuffer
stride = 40
array = 474496
; vertex_count * ring_buffer_length = 7414 * 64
```

### 2. Шейдеры записи истории

```ini
[CustomShaderComputeHairHistory]
cs = ./modules/ouroboros_adaptive_pos.hlsl
cs-u0 = ResourcePromeiaHairHistoryBuffer
cs-cb1 = vs-cb1          ; <-- КЛЮЧЕВОЕ: берём матрицу прямо из дроу колла персонажа
x1 = 64                  ; размер кольцевого буфера (должен совпадать с len в шейдере)
x3 = 0.2                 ; порог движения (не используется в текущей версии)
dispatch = 1, 1, 1
ResourcePromeiaHairHistoryBuffer = cs-u0   ; сохраняем UAV обратно в ресурс

[CustomShaderWriteHairHistory]
cs = ./modules/ouroboros_adaptive_vb.hlsl
cs-t0 = vb0              ; скиннед вертекс буфер из дроу колла
cs-u0 = ResourcePromeiaHairSkinnedHistory
cs-t1 = ResourcePromeiaHairHistoryBuffer
x0 = 7414                ; количество вершин меша
x1 = 64                  ; размер кольцевого буфера
dispatch = 8, 1, 1       ; ceil(7414 / 1024) = 8
ResourcePromeiaHairSkinnedHistory = cs-u0
```

### 3. Запуск в дроу колле персонажа (ОБЯЗАТЕЛЬНО — не в Present!)

```ini
[CommandListTextureOverridePromeiaHairB]
; Гейт: запускаем только один раз за игровой кадр
; (дроу колл вызывается несколько раз: shadow, depth, gbuffer...)
if $RZM_NewFrameHair == 1
    $RZM_NewFrameHair = 0
    run = CustomShaderComputeHairHistory
    run = CustomShaderWriteHairHistory
endif
ib = ResourcePromeiaHairBIB
; ... остальные биндинги текстур ...
```

### 4. Флаг "новый кадр" сбрасывается в Present

```ini
[Present]
$RZM_NewFrameHair = 1    ; взводим флаг — следующий дроу колл запишет историю
$RZM_NewFrameLegs = 1
run = CommandListRZM_VFX_Present
```

### 5. Физический шейдер (заменяет стандартный vfx_curve_cs.hlsl)

```ini
[CustomShaderRZM_VFX_PromeiaHairB]
cs = ./modules/vfx_curve_physics_cs.hlsl
cs-u5 = copy ResourcePromeiaHairPosition
cs-t6 = ref ResourcePromeiaHairHistoryBuffer   ; <-- матрица истории
cs-t50 = copy ResourceRZM_CurveData
x98 = time
x115 = 7414
ResourcePromeiaHairPosition = ref cs-u5
dispatch = 155, 1, 1
cs-u5 = null
```

---

## Шейдер — Ключевые параметры (`vfx_curve_physics_cs.hlsl`)

```hlsl
// Регистры:
//   u5  — позиции партиклов (читаем + пишем)
//   t6  — история матриц персонажа (ResourcePromeiaHairHistoryBuffer)
//   t50 — данные кривых (ResourceRZM_CurveData)
//   t120 — IniParams

// Настройки шлейфа (строки ~296-297):
float max_lag_frames = 30.0f;   // сила шлейфа; 5=слабо, 30=умеренно, 55=сильно/дёргано

// Порог телепорта (строка ~311):
if (h3.w < 0.5f || distance(h3.xyz, c3.xyz) > 2.0f)  // snap при > 2 метра/кадр
```

---

## Математика дельта-метода

Вся физика — три шага при чтении:

```hlsl
// 1. Дельта в мировом пространстве
//    c3.xyz = текущая позиция персонажа в мире
//    h3.xyz = позиция K кадров назад
//    c3 - h3 = вектор движения (от прошлого к настоящему = направление вперёд)
float3 world_delta = c3.xyz - h3.xyz;

// 2. Переводим дельту в текущее локальное пространство персонажа
//    c0/c1/c2 = столбцы матрицы вращения (local->world)
//    Транспоз ортонормальной матрицы = её обратная
float3 local_delta = float3(
    dot(world_delta, c0.xyz),
    dot(world_delta, c1.xyz),
    dot(world_delta, c2.xyz)
);

// 3. Смещаем партикл пропорционально его положению на сплайне
//    path_progress=0 (корень) -> нет смещения (закреплён)
//    path_progress=1 (конец)  -> полная дельта (максимальный шлейф)
float3 game_center = RemapCoords(final_center) + local_delta * path_progress;
```

> **Почему это работает при поворотах:** дельта переводится через `c0/c1/c2` **текущего** кадра, поэтому направление всегда правильно относительно текущей ориентации персонажа.

---

## Пространства координат

| Пространство | Где | Ось вверх |
|---|---|---|
| **Blender space** | `CurveData`, входные данные сплайна | Y |
| **Game space** | `rw_buffer.position`, матрица `cb1` | Z |
| **World space** | `cb1[3].xyz` (позиция персонажа) | Z |

Конвертация Blender → Game через `RemapCoords()`:
```hlsl
#define AXIS_MAP_X  -1   // game.x = -blender.x
#define AXIS_MAP_Y   2   // game.y =  blender.z  
#define AXIS_MAP_Z   3   // game.z =  blender.y
```

---

## Известные ограничения / TO-DO для RZM-модуля

- [ ] `len = 64` хардкодено в шейдере — должно читаться из `IniParams` (как в `ouroboros_adaptive_pos.hlsl`)
- [ ] `max_lag_frames` хардкодено — вынести в `IniParams` для горячей настройки без `F10`
- [ ] Snap threshold `2.0f` — вынести в IniParams
- [ ] Поддержка нескольких объектов: у каждого компонента свой `ResourceXxxHistoryBuffer`
- [ ] Интеграция в Jinja2-шаблон: автогенерация блоков записи истории для каждого компонента с `VFX_PhysX = true`
- [ ] Rotation-lag (сейчас только translation): учёт углового вращения матрицы для более реалистичного поведения при поворотах

---

## Вдохновение

- `CustomShader___LEGSSandevistan` — пример записи vb0 истории и матриц в кольцевой буфер
- `ouroboros_adaptive_pos.hlsl` — запись матрицы cb1 в кольцевой буфер
- `ouroboros_adaptive_vb.hlsl` — запись vb0 в кольцевой буфер
- `trace_vs_sandevistan.hlsl` — чтение истории и рендер призраков
