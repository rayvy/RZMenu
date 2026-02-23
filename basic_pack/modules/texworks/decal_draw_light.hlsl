// ==========================================
// ФАЙЛ: decal_warp_light.hlsl (ЛЕГКИЙ)
// ==========================================
RWTexture2D<float4> Target : register(u0);
Texture2D<float4> DecalTexture : register(t0);
Texture2D<float4> SlotMask : register(t2);
Buffer<float> ConfigBuffer : register(t3);
StructuredBuffer<float2> WarpBuffer : register(t4);
Texture1D<float4> IniParams : register(t120);

// КОНСТАНТЫ
#define UseMask    (IniParams[44].w > 0.5f)
#define WarpEnable (IniParams[44].z > 0.5f) 
#define CompRect   IniParams[45]
#define ColorMul   IniParams[46] 
#define Overlay    IniParams[47] 

SamplerState samLinear { Filter = MIN_MAG_MIP_LINEAR; AddressU = Clamp; AddressV = Clamp; };

// Функция весов Безье (инлайн для скорости)
float3 GetBezierWeights(float t) {
    float invT = 1.0f - t;
    return float3(invT * invT, 2.0f * t * invT, t * t);
}

// Упрощенная функция записи (без проверок, проверки снаружи)
void WritePixel(int2 pos, float4 color, float2 absCoord) {
    // Clipping (Хардкорный клиппинг по ректу)
    if (pos.x < (int)CompRect.x || pos.y < (int)CompRect.y || 
        pos.x >= (int)(CompRect.x + CompRect.z) || pos.y >= (int)(CompRect.y + CompRect.w)) return;

    // Маска
    if (UseMask) {
        float2 faceUV = (absCoord - CompRect.xy + 0.5f) / CompRect.zw;
        color.a *= SlotMask.SampleLevel(samLinear, faceUV, 0).r;
    }

    if (color.a > 0.001f) {
        // Читаем-модифицируем-пишем (без атомиков, надеемся на порядок)
        float4 bg = Target[pos];
        bg.rgb = lerp(bg.rgb, color.rgb, color.a);
        bg.a = max(bg.a, color.a);
        Target[pos] = bg;
    }
}

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    // 1. Setup
    float2 GlobalOrigin = float2(ConfigBuffer[0], ConfigBuffer[1]);
    float2 DecalSize    = float2(ConfigBuffer[2], ConfigBuffer[3]);
    float fRotation     = ConfigBuffer[4];
    bool mirror         = ConfigBuffer[6] > 0.5f;
    bool flip           = ConfigBuffer[7] > 0.5f;

    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= (uint)DecalSize.x || localCoord.y >= (uint)DecalSize.y) return;

    // 2. UV Logic
    float2 uvLinear = (float2(localCoord) + 0.5f) / DecalSize;
    float2 uv = uvLinear;
    
    // Rotation / Mirror
    if (abs(fRotation) > 89.0f && abs(fRotation) < 91.0f) uv = float2(uv.y, 1.0f - uv.x);
    else if (abs(fRotation) > -91.0f && abs(fRotation) < -89.0f) uv = float2(1.0f - uv.y, uv.x);
    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    if (any(uv < 0.0f) || any(uv > 1.0f)) return;

    // 3. Color Logic
    float4 col = DecalTexture.SampleLevel(samLinear, uv, 0);
    col *= ColorMul;
    col.a = saturate(col.a);
    if (col.a <= 0.001f) return;
    if (Overlay.w > 0.0f) col.rgb = lerp(col.rgb, Overlay.rgb, saturate(col.a * Overlay.w));

    // 4. Warp Logic
    float2 pixelOffset = float2(0,0);
    if (WarpEnable) {
        float2 pts[9];
        [unroll] for(int i=0; i<9; i++) pts[i] = WarpBuffer[i] + IniParams[30+i].xy;
        
        float3 wX = GetBezierWeights(uvLinear.x);
        float3 wY = GetBezierWeights(uvLinear.y);
        
        // Ручная развертка матрицы 3x3
        pixelOffset += pts[0]*wX.x*wY.x; pixelOffset += pts[1]*wX.y*wY.x; pixelOffset += pts[2]*wX.z*wY.x;
        pixelOffset += pts[3]*wX.x*wY.y; pixelOffset += pts[4]*wX.y*wY.y; pixelOffset += pts[5]*wX.z*wY.y;
        pixelOffset += pts[6]*wX.x*wY.z; pixelOffset += pts[7]*wX.y*wY.z; pixelOffset += pts[8]*wX.z*wY.z;
        pixelOffset *= DecalSize;
    }

    float2 finalPosExact = GlobalOrigin + float2(localCoord) + pixelOffset;
    int2 targetPos = int2(round(finalPosExact));

    // 5. WRITE STRATEGY (DILATION)
    // Пишем в центральный пиксель
    WritePixel(targetPos, col, finalPosExact);

    // Если включен варп, пишем "страховочные" пиксели справа и снизу, 
    // чтобы закрыть микро-щели при растяжении (дешевый аналог сглаживания)
    if (WarpEnable) {
        // Заполняем "уголок", это закрывает 90% дырок от диагонального растяжения
        WritePixel(targetPos + int2(1, 0), col, finalPosExact + float2(1,0)); 
        WritePixel(targetPos + int2(0, 1), col, finalPosExact + float2(0,1));
    }
}