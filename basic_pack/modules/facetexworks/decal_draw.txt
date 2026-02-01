// --- decal_draw_optimized.hlsl ---

RWTexture2D<float4> Target : register(u0);      // Лицо
Texture2D<float4> DecalTexture : register(t0);  // Текстура элемента
Buffer<float> ConfigBuffer : register(t1);      // Оффсеты и флаги

Texture1D<float4> IniParams : register(t120);

// Теперь RegionParams - это НЕ размер лица, а координаты и размер ДЕКАЛИ
#define DecalRect IniParams[44]

// x44, y44 - Глобальная позиция начала рисования
#define GlobalOrigin uint2(DecalRect.x, DecalRect.y)
// z44, w44 - Реальный размер картинки
#define DecalSize    uint2(DecalRect.z, DecalRect.w)

SamplerState samLinear {
    Filter = MIN_MAG_MIP_LINEAR;
    AddressU = Clamp;
    AddressV = Clamp;
};

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    // localCoord теперь идет от (0,0) до (Width, Height) самой наклейки
    uint2 localCoord = dispatchThreadID.xy;

    // 1. Проверка на выход за пределы размера ДЕКАЛИ 
    // (так как dispatch запускается блоками по 32, хвост может вылезти)
    if (localCoord.x >= DecalSize.x || localCoord.y >= DecalSize.y)
        return;

    // 2. Читаем доп. настройки из буфера
    // Нам нужны только индексы 4,5 (Offset) и 6,7 (Flags)
    // 0-3 пропускаем, так как взяли их из x44-w44
    float fOffX   = ConfigBuffer[0];
    float fOffY   = ConfigBuffer[1];
    float fMirror = ConfigBuffer[2];
    float fFlip   = ConfigBuffer[3];

    int2 offset = int2(fOffX, fOffY);
    bool mirror = fMirror > 0.5f;
    bool flip   = fFlip > 0.5f;

    // 3. Вычисляем координаты UV для чтения текстуры
    float2 uv = (float2(localCoord) + 0.5f) / float2(DecalSize);

    // Применяем зеркалирование/переворот к UV
    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    // 4. Читаем цвет декали
    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0);

    // Оптимизация: Если пиксель полностью прозрачный, не трогаем память лица
    if (decalColor.a <= 0.001f) 
        return;

    // 5. Вычисляем куда писать на лице
    // Глобальная позиция + Смещение потока + Доп.Оффсет из конфига
    int2 targetPos = GlobalOrigin + localCoord + offset;

    // ЗАЩИТА: Проверяем, не вылезли ли мы за границы текстуры лица (1024x1024)
    // Иначе драйвер может крашнуться или будет артефакт
    uint2 faceDim;
    Target.GetDimensions(faceDim.x, faceDim.y);
    
    if (targetPos.x >= 0 && targetPos.y >= 0 && 
        targetPos.x < (int)faceDim.x && targetPos.y < (int)faceDim.y)
    {
        float4 finalColor = Target[targetPos];
        
        // Blending
        finalColor.rgb = lerp(finalColor.rgb, decalColor.rgb, decalColor.a);
        finalColor.a = max(finalColor.a, decalColor.a);

        Target[targetPos] = finalColor;
    }
}