RWTexture2D<float4> Target : register(u0);
Texture2D<float4> SlotMask : register(t5);
Texture1D<float4> IniParams : register(t120);

#define StateFlags      IniParams[24]
#define HSVParams       IniParams[43]
#define RegionParams    IniParams[44]
#define CompRect        IniParams[45]

#define EnableMask      StateFlags.w
#define HueShift        HSVParams.x
#define SaturationShift HSVParams.y
#define ValueShift      HSVParams.z
#define HSVStrength     HSVParams.w

SamplerState samLinear { Filter = MIN_MAG_MIP_LINEAR; AddressU = Clamp; AddressV = Clamp; };

// --- Математика HSV (без изменений, она рабочая) ---
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
    uint2 TargetOffset = uint2(RegionParams.x, RegionParams.y);
    uint2 RegionDim = uint2(RegionParams.z, RegionParams.w);

    if (localCoord.x >= RegionDim.x || localCoord.y >= RegionDim.y) return;

    uint2 targetPos = TargetOffset + localCoord;
    float4 combined = Target[targetPos];
    
    float mask = 1.0f;
    if (EnableMask > 0.5f) {
        float2 maskUV;
        // ЕСЛИ задан CompRect (x45), используем его координаты
        if (CompRect.z > 0.001f && CompRect.w > 0.001f) {
            maskUV = (float2(targetPos) + 0.5f - CompRect.xy) / CompRect.zw;
        } 
        // ИНАЧЕ просто растягиваем маску по размеру текущего региона (x44)
        else {
            maskUV = (float2(localCoord) + 0.5f) / float2(RegionDim);
        }
        mask = SlotMask.SampleLevel(samLinear, maskUV, 0).r;
    }

    if (mask <= 0.001f) return; // Ничего не делаем, если маска пустая

    float3 hsv = RGBtoHSV(combined.rgb);
    hsv.x = frac(hsv.x + HueShift);
    hsv.y = saturate(hsv.y + SaturationShift);
    hsv.z = saturate(hsv.z + ValueShift);
    
    float3 shifted_rgb = HSVtoRGB(hsv);
    float3 final_rgb = lerp(combined.rgb, shifted_rgb, mask * saturate(HSVStrength));
    
    Target[targetPos] = float4(final_rgb, combined.a);
}