RWTexture2D<float4> Target : register(u0);
Texture2D<float4> DecalTexture : register(t0);
Texture2D<float4> CompMask : register(t1);
Texture2D<float4> SlotMask : register(t2);
Buffer<float> ConfigBuffer : register(t3);

// БАФФЕР ВАРПИНГА 
StructuredBuffer<float2> WarpBuffer : register(t4);

Texture1D<float4> IniParams : register(t120);

// --- ПАРАМЕТРЫ СИСТЕМЫ ---
#define UseMask    (IniParams[44].w > 0.5f)
#define WarpEnable (IniParams[44].z > 0.5f) 
#define CompRect   IniParams[45]

// --- ПАРАМЕТРЫ ЦВЕТА (Интеграция по примеру второго шейдера) ---
// rgb = Желаемый цвет, w = Множитель (сила применения цвета)
#define ColorData  IniParams[46] 

SamplerState samLinear {
    Filter = MIN_MAG_MIP_LINEAR;
    AddressU = Clamp;
    AddressV = Clamp;
};

// Квадратичное Безье для весов
float3 GetBezierWeights(float t)
{
    float invT = 1.0f - t;
    return float3(invT * invT, 2.0f * t * invT, t * t);
}

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    // 1. Инициализация параметров напрямую (без проверок дебага)
    float2 GlobalOrigin = float2(ConfigBuffer[0], ConfigBuffer[1]);
    float2 DecalSize    = float2(ConfigBuffer[2], ConfigBuffer[3]);
    float fRotation     = ConfigBuffer[4];
    bool mirror         = ConfigBuffer[6] > 0.5f;
    bool flip           = ConfigBuffer[7] > 0.5f;

    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= (uint)DecalSize.x || localCoord.y >= (uint)DecalSize.y) return;

    // 2. Расчет базовых UV
    float2 uvLinear = (float2(localCoord) + 0.5f) / DecalSize;
    float2 uv = uvLinear;

    // --- ЛОГИКА ВАРПИНГА ---
    float2 pixelOffset = float2(0.0f, 0.0f);
    if (WarpEnable)
    {
        float2 warpPoints[9];
        
        [unroll]
        for(int i = 0; i < 9; i++)
        {
            warpPoints[i] = WarpBuffer[i] + IniParams[30 + i].xy;
        }

        float3 wX = GetBezierWeights(uvLinear.x);
        float3 wY = GetBezierWeights(uvLinear.y);

        pixelOffset += warpPoints[0] * wX.x * wY.x; 
        pixelOffset += warpPoints[1] * wX.y * wY.x; 
        pixelOffset += warpPoints[2] * wX.z * wY.x; 
        pixelOffset += warpPoints[3] * wX.x * wY.y; 
        pixelOffset += warpPoints[4] * wX.y * wY.y; 
        pixelOffset += warpPoints[5] * wX.z * wY.y; 
        pixelOffset += warpPoints[6] * wX.x * wY.z; 
        pixelOffset += warpPoints[7] * wX.y * wY.z; 
        pixelOffset += warpPoints[8] * wX.z * wY.z; 
        
        pixelOffset *= DecalSize;
    }

    // 3. Повороты и зеркалирование текстуры
    if (abs(fRotation) > 89.0f && abs(fRotation) < 91.0f) {
        uv = float2(uv.y, 1.0f - uv.x);
    } 
    else if (abs(fRotation) > -91.0f && abs(fRotation) < -89.0f) {
        uv = float2(1.0f - uv.y, uv.x);
    }

    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    if (any(uv < 0.0f) || any(uv > 1.0f)) return;
    
    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0);
    if (decalColor.a <= 0.001f) return;

    // --- МЕХАНИЗМ УПРАВЛЕНИЯ ЦВЕТОМ ---
    if (ColorData.w > 0.0f)
    {
        // Умножаем исходную альфу декали на переданный коэффициент (w)
        float blendFactor = saturate(decalColor.a * ColorData.w);
        
        // Плавно перекрашиваем пиксель декали в заданный цвет (rgb)
        decalColor.rgb = lerp(decalColor.rgb, ColorData.rgb, blendFactor);
    }

    // --- РАСЧЕТ ИТОГОВОЙ ПОЗИЦИИ ---
    float2 absoluteCoord = GlobalOrigin + float2(localCoord) + pixelOffset;

    // 4. Маскировка
    if (UseMask)
    {
        float2 faceUV = (absoluteCoord - CompRect.xy + 0.5f) / CompRect.zw;
        decalColor.a *= SlotMask.SampleLevel(samLinear, faceUV, 0).r;
        
        if (decalColor.a <= 0.001f) return; // Ранний выход после применения маски
    }

    // 5. Запись в таргет
    int2 targetPos = int2(round(absoluteCoord));

    // Проверка границ CompRect (Clipping)
    if (targetPos.x < (int)CompRect.x || targetPos.y < (int)CompRect.y || 
        targetPos.x >= (int)(CompRect.x + CompRect.z) || targetPos.y >= (int)(CompRect.y + CompRect.w)) return;

    uint2 faceDim;
    Target.GetDimensions(faceDim.x, faceDim.y);
    
    if (targetPos.x >= 0 && targetPos.y >= 0 && targetPos.x < (int)faceDim.x && targetPos.y < (int)faceDim.y)
    {
        float4 finalColor = Target[targetPos];
        
        // Итоговый Lerp: если механизм цвета отработал, сюда попадёт уже покрашенный decalColor.rgb
        finalColor.rgb = lerp(finalColor.rgb, decalColor.rgb, decalColor.a);
        finalColor.a = max(finalColor.a, decalColor.a);
        Target[targetPos] = finalColor;
    }
}