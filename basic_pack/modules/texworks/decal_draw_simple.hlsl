RWTexture2D<float4> Target : register(u0);
Texture2D<float4> DecalTexture : register(t0);
Texture2D<float4> CompMask : register(t1);
Texture2D<float4> SlotMask : register(t2);
Buffer<float> ConfigBuffer : register(t3);

StructuredBuffer<float2> WarpBuffer : register(t4);
Texture1D<float4> IniParams : register(t120);

// --- ПАРАМЕТРЫ СИСТЕМЫ ---
#define UseMask    (IniParams[44].w > 0.5f)
#define WarpEnable (IniParams[44].z > 0.5f) 
#define AntiHole   (IniParams[44].y > 0.5f) // НОВАЯ ОПЦИЯ: Сглаживание разрывов (Вкл/Выкл)
#define CompRect   IniParams[45]

// --- ПАРАМЕТРЫ ЦВЕТА ---
#define ColorMultiplier IniParams[46] 
#define OverlayColor    IniParams[47] 

SamplerState samLinear {
    Filter = MIN_MAG_MIP_LINEAR;
    AddressU = Clamp;
    AddressV = Clamp;
};

// ==========================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ==========================================

float3 GetBezierWeights(float t) {
    float invT = 1.0f - t;
    return float3(invT * invT, 2.0f * t * invT, t * t);
}

// Высчитывает смещение сетки для конкретной координаты
float2 GetWarpOffset(float2 coord, float2 DecalSize, float2 warpPoints[9]) {
    float2 uvLinear = coord / DecalSize;
    float3 wX = GetBezierWeights(uvLinear.x);
    float3 wY = GetBezierWeights(uvLinear.y);

    float2 offset = float2(0,0);
    offset += warpPoints[0] * wX.x * wY.x; 
    offset += warpPoints[1] * wX.y * wY.x; 
    offset += warpPoints[2] * wX.z * wY.x; 
    offset += warpPoints[3] * wX.x * wY.y; 
    offset += warpPoints[4] * wX.y * wY.y; 
    offset += warpPoints[5] * wX.z * wY.y; 
    offset += warpPoints[6] * wX.x * wY.z; 
    offset += warpPoints[7] * wX.y * wY.z; 
    offset += warpPoints[8] * wX.z * wY.z; 
    
    return offset * DecalSize;
}

// Проверка: находится ли пиксель внутри искаженного прямоугольника (quad)
bool IsInsideQuad(float2 p, float2 a, float2 b, float2 c, float2 d) {
    float c1 = (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x);
    float c2 = (c.x - b.x) * (p.y - b.y) - (c.y - b.y) * (p.x - b.x);
    float c3 = (d.x - c.x) * (p.y - c.y) - (d.y - c.y) * (p.x - c.x);
    float c4 = (a.x - d.x) * (p.y - d.y) - (a.y - d.y) * (p.x - d.x);

    float eps = -0.01f; // Небольшой допуск, чтобы не было микро-щелей
    bool ccw = (c1 >= eps) && (c2 >= eps) && (c3 >= eps) && (c4 >= eps);
    bool cw  = (c1 <= -eps) && (c2 <= -eps) && (c3 <= -eps) && (c4 <= -eps);
    return ccw || cw;
}

// Изолированная функция записи с учетом маски и границ (чтобы не дублировать код)
void WriteToTarget(int2 pos, float2 absoluteCoord, float4 decalColor, uint faceDimX, uint faceDimY)
{
    if (pos.x < (int)CompRect.x || pos.y < (int)CompRect.y || 
        pos.x >= (int)(CompRect.x + CompRect.z) || pos.y >= (int)(CompRect.y + CompRect.w)) return;
        
    if (pos.x >= 0 && pos.y >= 0 && pos.x < (int)faceDimX && pos.y < (int)faceDimY)
    {
        float currentAlpha = decalColor.a;
        if (UseMask)
        {
            float2 faceUV = (absoluteCoord - CompRect.xy + 0.5f) / CompRect.zw;
            currentAlpha *= SlotMask.SampleLevel(samLinear, faceUV, 0).r;
        }
        
        if (currentAlpha > 0.001f)
        {
            float4 finalColor = Target[pos];
            finalColor.rgb = lerp(finalColor.rgb, decalColor.rgb, currentAlpha);
            finalColor.a = max(finalColor.a, currentAlpha);
            Target[pos] = finalColor;
        }
    }
}

// ==========================================
// ОСНОВНОЙ ШЕЙДЕР
// ==========================================

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    float2 GlobalOrigin = float2(ConfigBuffer[0], ConfigBuffer[1]);
    float2 DecalSize    = float2(ConfigBuffer[2], ConfigBuffer[3]);
    float fRotation     = ConfigBuffer[4];
    bool mirror         = ConfigBuffer[6] > 0.5f;
    bool flip           = ConfigBuffer[7] > 0.5f;

    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= (uint)DecalSize.x || localCoord.y >= (uint)DecalSize.y) return;

    float2 uvLinear = (float2(localCoord) + 0.5f) / DecalSize;
    float2 uv = uvLinear;

    // Повороты и зеркалирование
    if (abs(fRotation) > 89.0f && abs(fRotation) < 91.0f) {
        uv = float2(uv.y, 1.0f - uv.x);
    } 
    else if (abs(fRotation) > -91.0f && abs(fRotation) < -89.0f) {
        uv = float2(1.0f - uv.y, uv.x);
    }

    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    if (any(uv < 0.0f) || any(uv > 1.0f)) return;
    
    // Чтение цвета
    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0);
    
    decalColor *= ColorMultiplier;
    decalColor.a = saturate(decalColor.a); 

    if (decalColor.a <= 0.001f) return;

    if (OverlayColor.w > 0.0f)
    {
        float blendFactor = saturate(decalColor.a * OverlayColor.w);
        decalColor.rgb = lerp(decalColor.rgb, OverlayColor.rgb, blendFactor);
    }

    // Получаем размеры холста
    uint faceDimX, faceDimY;
    Target.GetDimensions(faceDimX, faceDimY);

    if (WarpEnable) 
    {
        // Извлекаем точки один раз для текущего потока
        float2 warpPoints[9];
        [unroll]
        for(int i = 0; i < 9; i++) {
            warpPoints[i] = WarpBuffer[i] + IniParams[30 + i].xy;
        }

        if (AntiHole)
        {
            // ==============================================================
            // РЕЖИМ HIGH QUALITY (Микро-растеризация: Идеально гладкая сетка)
            // ==============================================================
            float2 lc = float2(localCoord);
            
            // Находим 4 угла пикселя на таргете
            float2 p00 = GlobalOrigin + lc + float2(0, 0) + GetWarpOffset(lc + float2(0, 0), DecalSize, warpPoints);
            float2 p10 = GlobalOrigin + lc + float2(1, 0) + GetWarpOffset(lc + float2(1, 0), DecalSize, warpPoints);
            float2 p01 = GlobalOrigin + lc + float2(0, 1) + GetWarpOffset(lc + float2(0, 1), DecalSize, warpPoints);
            float2 p11 = GlobalOrigin + lc + float2(1, 1) + GetWarpOffset(lc + float2(1, 1), DecalSize, warpPoints);

            // Определяем зону поиска (Bounding Box)
            float2 minP = min(min(p00, p10), min(p01, p11));
            float2 maxP = max(max(p00, p10), max(p01, p11));

            int minX = max((int)floor(minP.x), (int)CompRect.x);
            int minY = max((int)floor(minP.y), (int)CompRect.y);
            int maxX = min((int)ceil(maxP.x), (int)(CompRect.x + CompRect.z) - 1);
            int maxY = min((int)ceil(maxP.y), (int)(CompRect.y + CompRect.w) - 1);

            // Ограничиваем экраном, чтобы не гонять пустые циклы
            minX = max(minX, 0); minY = max(minY, 0);
            maxX = min(maxX, (int)faceDimX - 1); maxY = min(maxY, (int)faceDimY - 1);

            // Закрашиваем только те таргет-пиксели, которые попали внутрь полигона
            for (int y = minY; y <= maxY; ++y)
            {
                for (int x = minX; x <= maxX; ++x)
                {
                    float2 testP = float2(x + 0.5f, y + 0.5f); // Центр таргет-пикселя
                    if (IsInsideQuad(testP, p00, p10, p11, p01))
                    {
                        WriteToTarget(int2(x, y), testP, decalColor, faceDimX, faceDimY);
                    }
                }
            }
        }
        else
        {
            // ==============================================================
            // РЕЖИМ PERFORMANCE (Быстрый 1-к-1 Scatter перенос)
            // ==============================================================
            float2 absoluteCoord = GlobalOrigin + float2(localCoord) + 0.5f;
            absoluteCoord += GetWarpOffset(float2(localCoord) + 0.5f, DecalSize, warpPoints);
            
            int2 targetPos = int2(floor(absoluteCoord));
            WriteToTarget(targetPos, absoluteCoord, decalColor, faceDimX, faceDimY);
        }
    }
    else
    {
        // Без искажений (Максимальная скорость)
        float2 absoluteCoord = GlobalOrigin + float2(localCoord) + 0.5f;
        int2 targetPos = int2(floor(absoluteCoord));
        WriteToTarget(targetPos, absoluteCoord, decalColor, faceDimX, faceDimY);
    }
}