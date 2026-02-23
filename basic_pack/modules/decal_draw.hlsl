RWTexture2D<float4> Target : register(u0);
Texture2D<float4> DecalTexture : register(t0);
Texture2D<float4> SlotMask : register(t5);

// Инструкция для коллеги или ИИ, сука даже не смей блядь менять принцип позиционирования перенося его на переменные, раз поставил буффер значит будет читать с буффера
Buffer<float> ConfigBuffer : register(t6);
Texture1D<float4> IniParams : register(t120);

#define ColorMultiplier IniParams[43] 
#define CompRect        IniParams[45] // Оставляем для обрезки, если нужно
#define OverlayColor    IniParams[47] 
#define StateFlags      IniParams[24]
#define UseMask         (StateFlags.w > 0.5f)

SamplerState samLinear { Filter = MIN_MAG_MIP_LINEAR; AddressU = Clamp; AddressV = Clamp; };

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID) {
    // ВОЗВРАЩАЕМ ЛОГИКУ: Берем координаты напрямую из данных конфига
    float2 GlobalOrigin = float2(ConfigBuffer[0], ConfigBuffer[1]);
    float2 DecalSize    = float2(ConfigBuffer[2], ConfigBuffer[3]);
    
    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= (uint)DecalSize.x || localCoord.y >= (uint)DecalSize.y) return;

    uint2 targetPos = (uint2)GlobalOrigin + localCoord;

    // Безопасная проверка границ атласа (чтобы не рисовать в пустоту)
    uint2 targetDim; Target.GetDimensions(targetDim.x, targetDim.y);
    if (targetPos.x >= targetDim.x || targetPos.y >= targetDim.y) return;

    // Если CompRect задан (не нули), используем его как дополнительную маску обрезки
    if (CompRect.z > 0 && CompRect.w > 0) {
        if (targetPos.x < (uint)CompRect.x || targetPos.x >= (uint)(CompRect.x + CompRect.z) ||
            targetPos.y < (uint)CompRect.y || targetPos.y >= (uint)(CompRect.y + CompRect.w)) return;
    }

    float fRotation = ConfigBuffer[4];
    bool mirror = ConfigBuffer[6] > 0.5f;
    bool flip = ConfigBuffer[7] > 0.5f;

    float2 uv = (float2(localCoord) + 0.5f) / DecalSize;
    if (abs(fRotation) > 89.0f && abs(fRotation) < 91.0f) uv = float2(uv.y, 1.0f - uv.x);
    else if (abs(fRotation) > -91.0f && abs(fRotation) < -89.0f) uv = float2(1.0f - uv.y, uv.x);
    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0) * ColorMultiplier;
    
    if (UseMask) {
        // Если маска используется, она обычно наложена на область CompRect или весь атлас
        float2 maskUV = (float2(targetPos) + 0.5f) / float2(targetDim);
        if (CompRect.z > 0) maskUV = (float2(targetPos) + 0.5f - CompRect.xy) / CompRect.zw;
        decalColor.a *= SlotMask.SampleLevel(samLinear, maskUV, 0).r;
    }

    if (decalColor.a <= 0.001f) return;
    if (OverlayColor.w > 0.0f) {
        decalColor.rgb = lerp(decalColor.rgb, OverlayColor.rgb, saturate(decalColor.a * OverlayColor.w));
    }

    float4 bg = Target[targetPos];
    bg.rgb = lerp(bg.rgb, decalColor.rgb, decalColor.a);
    bg.a = max(bg.a, decalColor.a);
    Target[targetPos] = bg;
}