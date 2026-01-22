RWTexture2D<float4> Atlas : register(u0);
Texture2D<float4> SourceTexture : register(t0);
Texture2D<float4> MaskTexture : register(t1);
Texture1D<float4> IniParams : register(t120);

// --- Параметры из INI ---
#define RegionParams      IniParams[44]
#define LegacyHSVParams   IniParams[43]
#define BaseHSV           IniParams[56].xyz
#define NewHSV            float3(IniParams[56].w, IniParams[57].xy)

// --- Параметры региона ---
#define TargetOffset      uint2(RegionParams.x, RegionParams.y)
#define RegionDimensions  uint2(RegionParams.z, RegionParams.w)

// --- Флаги режимов ---
#define EnableHSVShiftMode (LegacyHSVParams.w) // Используем .w как флаг для нового режима

// --- Функции конвертации цвета (ваша версия, она хорошая и быстрая) ---
float3 RGBtoHSV(float3 c)
{
    float cmax = max(c.r, max(c.g, c.b));
    float cmin = min(c.r, min(c.g, c.b));
    float delta = cmax - cmin;
    float3 hsv = float3(0.0f, 0.0f, cmax);
    if (cmax > cmin) {
        hsv.y = delta / cmax;
        if (c.r >= cmax) hsv.x = (c.g - c.b) / delta;
        else if (c.g >= cmax) hsv.x = 2.0f + (c.b - c.r) / delta;
        else hsv.x = 4.0f + (c.r - c.g) / delta;
        hsv.x = hsv.x / 6.0f;
        if (hsv.x < 0.0f) hsv.x = hsv.x + 1.0f;
    }
    return hsv;
}

float3 HSVtoRGB(float3 c)
{
    if (c.y <= 0.0f) return float3(c.z, c.z, c.z);
    float hh = c.x;
    if (hh >= 1.0f) hh = 0.0f;
    hh = hh * 6.0f;
    float i = floor(hh);
    float ff = hh - i;
    float p = c.z * (1.0f - c.y);
    float q = c.z * (1.0f - (c.y * ff));
    float t = c.z * (1.0f - (c.y * (1.0f - ff)));
    if (i == 0) return float3(c.z, t, p);
    if (i == 1) return float3(q, c.z, p);
    if (i == 2) return float3(p, c.z, t);
    if (i == 3) return float3(p, q, c.z);
    if (i == 4) return float3(t, p, c.z);
    return float3(c.z, p, q);
}

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= RegionDimensions.x || localCoord.y >= RegionDimensions.y)
        return;

    // Читаем базовый цвет из исходной текстуры
    float4 base_color = SourceTexture.Load(int3(localCoord, 0));
    float3 final_rgb = base_color.rgb;

    // Проверяем, включен ли наш новый режим HSV сдвига
    if (EnableHSVShiftMode > 0.5f)
    {
        // --- НАША НОВАЯ ЛОГИКА ---
        // 1. Вычисляем дельту (сдвиг)
        float3 hsv_offset = NewHSV - BaseHSV;
        
        // 2. Конвертируем текущий пиксель в HSV
        float3 pixelHSV = RGBtoHSV(base_color.rgb);
        
        // 3. Применяем сдвиг
        pixelHSV.x = frac(pixelHSV.x + hsv_offset.x);
        pixelHSV.yz = saturate(pixelHSV.yz + hsv_offset.yz);
        
        // 4. Обновляем final_rgb
        final_rgb = HSVtoRGB(pixelHSV);
    }
    
    // Записываем финальный результат в атлас
    uint2 targetPixelCoord = TargetOffset + localCoord;
    Atlas[targetPixelCoord] = float4(final_rgb, base_color.a);
}