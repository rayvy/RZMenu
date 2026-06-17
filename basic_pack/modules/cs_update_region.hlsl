// RZMenu
// Made by: Rayvich

RWTexture2D<float4> Atlas : register(u0);
Texture2D<float4> SourceTexture : register(t0);
Texture2D<float4> MorphTexture : register(t1);
Texture2D<float4> MaskTexture : register(t5);
Texture1D<float4> IniParams : register(t120);

#define StateFlags      IniParams[24]
#define HSVParams       IniParams[43]
#define RegionParams    IniParams[44]
#define SourceParams    IniParams[45]

#define MorphFactor     StateFlags.x
#define EnableMask      StateFlags.w  // w24
#define HueShift        HSVParams.x   // x43
#define SaturationShift HSVParams.y   // y43
#define ValueShift      HSVParams.z   // z43
#define HSVStrength     HSVParams.w   // w43

#define TargetOffset      uint2(RegionParams.x, RegionParams.y)
#define RegionDimensions  uint2(RegionParams.z, RegionParams.w)
#define SourceOffset      uint2(SourceParams.x, SourceParams.y)

float3 RGBtoHSV(float3 c) {
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

float3 HSVtoRGB(float3 c) {
    if (c.y <= 0.0f) return float3(c.z, c.z, c.z);
    float hh = c.x * 6.0f;
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
void main(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= RegionDimensions.x || localCoord.y >= RegionDimensions.y) return;

    // 1. Координаты
    int3 readPos = int3(SourceOffset + localCoord, 0);

    // 2. Получаем маску (Глобальный коэффициент)
    float mask = 1.0f;
    if (EnableMask > 0.5f) {
        mask = MaskTexture.Load(int3(localCoord, 0)).r;
    }

    // Если маска в этой точке мертвая (0), и мы ничего не меняем — 
    // всё равно нужно прочитать базу, чтобы не затереть атлас пустотой
    float4 base = SourceTexture.Load(readPos);
    
    // Если маска совсем нулевая, просто выходим (оптимизация), 
    // но только если шейдер не должен перезаписывать базу. 
    // В твоем случае лучше дойти до конца, чтобы база обновилась в атласе.
    if (mask <= 0.0001f && MorphFactor <= 0.0001f) {
        Atlas[TargetOffset + localCoord] = base;
        return;
    }

    // 3. Морфинг (смешивание текстур)
    float4 morph = MorphTexture.Load(readPos);
    float4 combined = lerp(base, morph, saturate(MorphFactor));

    // 4. HSV (расчитываем всегда, но применяем через lerp с маской)
    float3 hsv_logic = combined.rgb;
    
    // Считаем HSV только если есть смысл (сила > 0)
    if (saturate(HSVStrength) > 0.001f) {
        float3 hsv = RGBtoHSV(combined.rgb);
        hsv.x = frac(hsv.x + HueShift);
        hsv.y = saturate(hsv.y + SaturationShift);
        hsv.z = saturate(hsv.z + ValueShift);
        
        float3 hsv_rgb = HSVtoRGB(hsv);
        // Смешиваем результат HSV с "combined" по маске и интенсивности
        hsv_logic = lerp(combined.rgb, hsv_rgb, mask * saturate(HSVStrength));
    }

    // 5. Финальный результат
    // Маска также может влиять на то, насколько "combined" (морфинг) перекрывает базу
    float3 final_rgb = lerp(base.rgb, hsv_logic, mask);
    
    Atlas[TargetOffset + localCoord] = float4(final_rgb, combined.a);
}