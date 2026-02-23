RWTexture2D<float4> Target : register(u0);
Texture2D<float4> DecalTexture : register(t0);
Texture2D<float4> CompMask : register(t1);
Texture2D<float4> SlotMask : register(t2);
Buffer<float> ConfigBuffer : register(t3);

// БАФФЕР ВАРПИНГА 
StructuredBuffer<float2> WarpBuffer : register(t4);

Texture1D<float4> IniParams : register(t120);

// --- ПАРАМЕТРЫ СИСТЕМЫ ---
// Мы больше не используем PassIndex для смещения в буферах, так как ресурсы разделены
#define UseMask (IniParams[44].w > 0.5f)
#define WarpEnable (IniParams[44].z > 0.5f) 
#define CompRect IniParams[45]

// --- ДЕБАГ РЕЖИМ ---
// z - Режим (0=Выкл, 1=Pass0, 2=Pass1...)
#define DebugMode (uint)IniParams[42].z

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
    // 1. Инициализация параметров
    float2 GlobalOrigin, DecalSize;
    float fRotation, fDummy;
    bool mirror, flip;
    
    // Определяем, включен ли дебаг для текущего вызова (координаты)
    // PassIndex берем из x44 только для идентификации дебага
    uint currentPass = (uint)IniParams[44].x;
    bool isDebug = (DebugMode > 0 && (DebugMode - 1) == currentPass);

    if (isDebug)
    {
        GlobalOrigin = IniParams[41].xy; 
        DecalSize    = IniParams[41].zw; 
        fRotation    = IniParams[42].x;  
        mirror       = IniParams[42].y > 0.5f; 
        flip         = IniParams[42].w > 0.5f;
    }
    else
    {
        // Читаем из начала конфига (так как пассы теперь в разных вызовах)
        GlobalOrigin = float2(ConfigBuffer[0], ConfigBuffer[1]);
        DecalSize    = float2(ConfigBuffer[2], ConfigBuffer[3]);
        fRotation    = ConfigBuffer[4];
        mirror       = ConfigBuffer[6] > 0.5f;
        flip         = ConfigBuffer[7] > 0.5f;
    }

    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= (uint)DecalSize.x || localCoord.y >= (uint)DecalSize.y) return;

    // 2. Расчет базовых UV
    float2 uvLinear = (float2(localCoord) + 0.5f) / DecalSize;
    float2 uv = uvLinear;

    // --- ЛОГИКА ВАРПИНГА (ВСЕГДА ВКЛЮЧЕННЫЙ ОФФСЕТ 30-38) ---
    float2 pixelOffset = float2(0.0f, 0.0f);
    if (WarpEnable)
    {
        float2 warpPoints[9];
        
        // Суммируем данные: Значение из Буфера + Твои ползунки (30-38)
        // Это позволяет "подправлять" результат скрипта вручную
        [unroll]
        for(int i = 0; i < 9; i++)
        {
            // Читаем из t4 (всегда с 0, так как буферы пассов разделены в INI)
            float2 bufferVal = WarpBuffer[i];
            float2 manualTweak = IniParams[30 + i].xy;
            warpPoints[i] = bufferVal + manualTweak;
        }

        float3 wX = GetBezierWeights(uvLinear.x);
        float3 wY = GetBezierWeights(uvLinear.y);

        // Применяем веса сетки 3x3
        pixelOffset += warpPoints[0] * wX.x * wY.x; // TL
        pixelOffset += warpPoints[1] * wX.y * wY.x; // TM
        pixelOffset += warpPoints[2] * wX.z * wY.x; // TR
        pixelOffset += warpPoints[3] * wX.x * wY.y; // ML
        pixelOffset += warpPoints[4] * wX.y * wY.y; // C
        pixelOffset += warpPoints[5] * wX.z * wY.y; // MR
        pixelOffset += warpPoints[6] * wX.x * wY.z; // BL
        pixelOffset += warpPoints[7] * wX.y * wY.z; // BM
        pixelOffset += warpPoints[8] * wX.z * wY.z; // BR
        
        pixelOffset *= DecalSize;
    }

    // 3. Повороты и зеркалирование текстуры
    if (abs(fRotation) > 89.0f && abs(fRotation) < 91.0f)
    {
        float2 oldUV = uv;
        uv.x = oldUV.y;       
        uv.y = 1.0f - oldUV.x; 
    }
    else if (abs(fRotation) > -91.0f && abs(fRotation) < -89.0f)
    {
        float2 oldUV = uv;
        uv.x = 1.0f - oldUV.y;
        uv.y = oldUV.x;
    }

    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    if (any(uv < 0.0f) || any(uv > 1.0f)) return;
    
    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0);
    
    // --- ЦВЕТНЫЕ МАРКЕРЫ (ТОЛЬКО В РЕЖИМЕ ДЕБАГА КООРДИНАТ) ---
    if (isDebug)
    {
        float2 markerPos[9] = {
            float2(0,0), float2(0.5,0), float2(1,0),
            float2(0,0.5), float2(0.5,0.5), float2(1,0.5),
            float2(0,1), float2(0.5,1), float2(1,1)
        };
        float3 markerColors[9] = {
            float3(1,0,0), float3(0,1,0), float3(0,0,1),   // TL: Красный, TM: Зеленый, TR: Синий
            float3(1,1,0), float3(0,1,1), float3(1,0,1),   // ML: Желтый,  C: Циан,    MR: Маджента
            float3(1,1,1), float3(1,0.5,0), float3(0.5,0.5,0.5) // BL: Белый,   BM: Оранж,   BR: Серый
        };

        [unroll]
        for(int j = 0; j < 9; j++)
        {
            float2 dist = abs(uvLinear - markerPos[j]) * DecalSize;
            if(all(dist < 4.0f)) decalColor = float4(markerColors[j], 1.0f);
        }
    }

    if (decalColor.a <= 0.001f) return;

    // --- РАСЧЕТ ИТОГОВОЙ ПОЗИЦИИ ---
    float2 absoluteCoord = GlobalOrigin + float2(localCoord) + pixelOffset;

    // 4. Маскировка
    if (UseMask)
    {
        float2 faceUV = (absoluteCoord - CompRect.xy + 0.5f) / CompRect.zw;
        decalColor.a *= SlotMask.SampleLevel(samLinear, faceUV, 0).r;
    }

    if (decalColor.a <= 0.001f) return;

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
        finalColor.rgb = lerp(finalColor.rgb, decalColor.rgb, decalColor.a);
        finalColor.a = max(finalColor.a, decalColor.a);
        Target[targetPos] = finalColor;
    }
}