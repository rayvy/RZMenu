// --- decal_draw_NEW.hlsl ---

RWTexture2D<float4> Target : register(u0);      // Лицо
Texture2D<float4> DecalTexture : register(t0);  // Текстура элемента
Texture2D<float4> CompMask : register(t1);      // Маска компоненты
Texture2D<float4> SlotMask : register(t2);      // Маска слота
Buffer<float> ConfigBuffer : register(t3);      // Оффсеты и флаги

Texture1D<float4> IniParams : register(t120);

// x44 - Номер пасса (0, 1, 2...)
#define PassIndex (uint)IniParams[44].x
// w44 - Флаг использования маски (1.0 = Да, 0.0 = Нет)
#define UseMask (IniParams[44].w > 0.5f)
// xyzw46 - Параметры материала
#define MatParams IniParams[46]
// xyzw45 - Прямоугольник компоненты (PosX, PosY, SizeW, SizeH)
#define CompRect IniParams[45]
// xyzw41, xyzw42 - Дебаг параметры (используются если IniParams[42].z > 0)
#define DebugMode (uint)IniParams[42].z

SamplerState samLinear {
    Filter = MIN_MAG_MIP_LINEAR;
    AddressU = Clamp;
    AddressV = Clamp;
};

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    // 1. Читаем параметры (из дебаг регистров или из буфера)
    bool isDebug = (DebugMode > 0 && (DebugMode - 1) == PassIndex);
    
    float2 GlobalOrigin, DecalSize;
    float fRotation, fDummy;
    bool mirror, flip;
    
    if (isDebug)
    {
        GlobalOrigin = IniParams[41].xy;
        DecalSize    = IniParams[41].zw;
        fRotation    = IniParams[42].x;
        fDummy       = IniParams[42].y;
        mirror       = IniParams[42].z > 0.5f;
        flip         = IniParams[42].w > 0.5f;
    }
    else
    {
        uint base = PassIndex * 8;
        GlobalOrigin = float2(ConfigBuffer[base + 0], ConfigBuffer[base + 1]);
        DecalSize    = float2(ConfigBuffer[base + 2], ConfigBuffer[base + 3]);
        fRotation    = ConfigBuffer[base + 4];
        fDummy       = ConfigBuffer[base + 5];
        mirror       = ConfigBuffer[base + 6] > 0.5f;
        flip         = ConfigBuffer[base + 7] > 0.5f;
    }

    // localCoord идет от (0,0) до (Width, Height) самой наклейки
    uint2 localCoord = dispatchThreadID.xy;

    // 2. Проверка на выход за пределы размера ДЕКАЛИ
    if (localCoord.x >= (uint)DecalSize.x || localCoord.y >= (uint)DecalSize.y)
        return;

    // 3. Вычисляем координаты UV для чтения текстуры
    float2 uv = (float2(localCoord) + 0.5f) / DecalSize;

    // --- НОВЫЙ БЛОК ВРАЩЕНИЯ ---
    if (abs(fRotation) > 0.001f)
    {
        float rad = radians(fRotation);
        float s = sin(rad);
        float c = cos(rad);
        float2 centeredUV = uv - 0.5f;
        uv.x = centeredUV.x * c - centeredUV.y * s + 0.5f;
        uv.y = centeredUV.x * s + centeredUV.y * c + 0.5f;
    }

    // Применяем зеркалирование/переворот к UV
    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    // 4. Читаем цвет декали
    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0);

    // Оптимизация: Если пиксель прозрачный, выходим
    if (decalColor.a <= 0.001f) 
        return;

    // 5. Применяем маски если они есть
    if (UseMask)
    {
        float2 absoluteCoord = GlobalOrigin + localCoord;
        float2 faceUV = (absoluteCoord - CompRect.xy + 0.5f) / CompRect.zw;
        
        float maskVal = 1.0f;
        maskVal *= CompMask.SampleLevel(samLinear, faceUV, 0).r;
        maskVal *= SlotMask.SampleLevel(samLinear, faceUV, 0).r;
        
        decalColor.a *= maskVal;
    }
    
    if (decalColor.a <= 0.001f)
        return;

    // 6. Вычисляем куда писать на целевой текстуре
    int2 targetPos = GlobalOrigin + localCoord;

    // ЗАЩИТА: Проверяем границы
    uint2 faceDim;
    Target.GetDimensions(faceDim.x, faceDim.y);
    
    if (targetPos.x >= 0 && targetPos.y >= 0 && 
        targetPos.x < (int)faceDim.x && targetPos.y < (int)faceDim.y)
    {
        float4 finalColor = Target[targetPos];
        
        // Блендинг
        finalColor.rgb = lerp(finalColor.rgb, decalColor.rgb, decalColor.a);
        finalColor.a = max(finalColor.a, decalColor.a);

        Target[targetPos] = finalColor;
    }
}