// Файл: /modules/atlas_blit_cs.hlsl
// Compute Shader для быстрого копирования (blit) одной текстуры в другую.

#pragma pack_matrix(row_major)

// --- Ресурсы ---

// u0: Выходной атлас, в который мы будем писать. Должен быть UAV (Unordered Access View).
RWTexture2D<float4> Atlas : register(u0);

// t0: Исходная текстура, из которой мы читаем.
Texture2D<float4> SourceTexture : register(t0);

// s0: Сэмплер.
SamplerState s0_s : register(s0);

// b0: Буфер с параметрами.
cbuffer Params : register(b0)
{
    // x, y: позиция в пикселях левого верхнего угла в атласе.
    // z, w: ширина и высота исходной текстуры в пикселях.
    uint4 TargetRect; // (X, Y, Width, Height)
};


// --- Логика шейдера ---

// Запускаем группы потоков размером 8x8. Это хороший баланс для большинства GPU.
[numthreads(8, 8, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    // dispatchThreadID.xy - это глобальные координаты пикселя в выходной текстуре (атласе),
    // который обрабатывает текущий поток.
    uint2 targetPixel = dispatchThreadID.xy;

    // --- Проверка границ ---
    // Убедимся, что текущий поток не вышел за пределы прямоугольника,
    // который мы хотим обновить. Это важно, так как dispatch может запустить
    // потоки для области чуть большей, чем наша текстура (например, 1024x1024 -> dispatch(128,128,1)).
    if (targetPixel.x >= TargetRect.x && targetPixel.x < (TargetRect.x + TargetRect.z) &&
        targetPixel.y >= TargetRect.y && targetPixel.y < (TargetRect.y + TargetRect.w))
    {
        // --- Вычисление координат для чтения ---
        
        // Вычисляем координаты пикселя в ИСХОДНОЙ текстуре.
        // Просто вычитаем смещение.
        uint2 sourcePixel = targetPixel - TargetRect.xy;

        // --- Чтение и запись ---

        // Читаем цвет из исходной текстуры по вычисленным координатам.
        // Используем Load, так как у нас есть точные целочисленные координаты пикселя.
        // Это быстрее, чем преобразование в UV и сэмплирование.
        float4 color = SourceTexture.Load(int3(sourcePixel, 0));

        // Записываем цвет в атлас по координатам текущего потока.
        Atlas[targetPixel] = color;
    }
}