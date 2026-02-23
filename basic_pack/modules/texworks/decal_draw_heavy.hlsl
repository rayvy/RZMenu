// ==========================================
// ФАЙЛ: decal_warp_heavy.hlsl (ТЯЖЕЛЫЙ - GUARANTEED)
// ==========================================
RWTexture2D<float4> Target : register(u0);
Texture2D<float4> DecalTexture : register(t0);
Texture2D<float4> SlotMask : register(t2);
Buffer<float> ConfigBuffer : register(t3);
StructuredBuffer<float2> WarpBuffer : register(t4);
Texture1D<float4> IniParams : register(t120);

#define UseMask    (IniParams[44].w > 0.5f)
#define WarpEnable (IniParams[44].z > 0.5f) 
#define CompRect   IniParams[45]
#define ColorMul   IniParams[46] 
#define Overlay    IniParams[47] 

SamplerState samLinear { Filter = MIN_MAG_MIP_LINEAR; AddressU = Clamp; AddressV = Clamp; };

float3 GetBezierWeights(float t) {
    float invT = 1.0f - t;
    return float3(invT * invT, 2.0f * t * invT, t * t);
}

// Функция получения смещения для произвольной координаты (u,v)
float2 GetWarpOffset(float2 uvLinear, float2 DecalSize, float2 pts[9]) {
    float3 wX = GetBezierWeights(uvLinear.x);
    float3 wY = GetBezierWeights(uvLinear.y);
    float2 off = float2(0,0);
    off += pts[0]*wX.x*wY.x; off += pts[1]*wX.y*wY.x; off += pts[2]*wX.z*wY.x;
    off += pts[3]*wX.x*wY.y; off += pts[4]*wX.y*wY.y; off += pts[5]*wX.z*wY.y;
    off += pts[6]*wX.x*wY.z; off += pts[7]*wX.y*wY.z; off += pts[8]*wX.z*wY.z;
    return off * DecalSize;
}

// Проверка: точка P внутри треугольника ABC?
bool PointInTriangle(float2 p, float2 a, float2 b, float2 c) {
    float as_x = p.x - a.x; float as_y = p.y - a.y;
    bool s_ab = (b.x - a.x) * as_y - (b.y - a.y) * as_x > 0;
    if ((c.x - a.x) * as_y - (c.y - a.y) * as_x > 0 == s_ab) return false;
    if ((c.x - b.x) * (p.y - b.y) - (c.y - b.y) * (p.x - b.x) > 0 != s_ab) return false;
    return true;
}

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

    // 1. Подготовка UV и Цвета
    float2 uvLinear = (float2(localCoord) + 0.5f) / DecalSize;
    float2 uv = uvLinear;

    if (abs(fRotation) > 89.0f && abs(fRotation) < 91.0f) uv = float2(uv.y, 1.0f - uv.x);
    else if (abs(fRotation) > -91.0f && abs(fRotation) < -89.0f) uv = float2(1.0f - uv.y, uv.x);
    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    if (any(uv < 0.0f) || any(uv > 1.0f)) return;

    float4 col = DecalTexture.SampleLevel(samLinear, uv, 0);
    col *= ColorMul;
    col.a = saturate(col.a);
    if (col.a <= 0.001f) return;
    if (Overlay.w > 0.0f) col.rgb = lerp(col.rgb, Overlay.rgb, saturate(col.a * Overlay.w));

    // 2. Логика Геометрии
    if (!WarpEnable) {
        // Обычный режим (быстро)
        float2 absPos = GlobalOrigin + float2(localCoord) + 0.5f;
        int2 tPos = int2(floor(absPos));
        
        if (tPos.x >= (int)CompRect.x && tPos.y >= (int)CompRect.y && 
            tPos.x < (int)(CompRect.x+CompRect.z) && tPos.y < (int)(CompRect.y+CompRect.w)) 
        {
            if (UseMask) col.a *= SlotMask.SampleLevel(samLinear, (absPos - CompRect.xy)/CompRect.zw, 0).r;
            if (col.a > 0.001f) {
                float4 bg = Target[tPos];
                bg.rgb = lerp(bg.rgb, col.rgb, col.a);
                bg.a = max(bg.a, col.a);
                Target[tPos] = bg;
            }
        }
    }
    else 
    {
        // ТЯЖЕЛЫЙ РЕЖИМ: ПОСТРОЕНИЕ КВАДА (RASTERIZATION)
        float2 pts[9];
        [unroll] for(int i=0; i<9; i++) pts[i] = WarpBuffer[i] + IniParams[30+i].xy;

        // Считаем углы "текущего пикселя" в пространстве UV
        float2 uv00 = float2(localCoord) / DecalSize; 
        float2 uv11 = float2(localCoord + uint2(1,1)) / DecalSize;
        float2 uv10 = float2(uv11.x, uv00.y);
        float2 uv01 = float2(uv00.x, uv11.y);

        // Трансформируем 4 угла в экранные координаты
        // Добавляем GlobalOrigin и localCoord смещения к результату варпа
        float2 p00 = GlobalOrigin + float2(localCoord) + float2(0,0) + GetWarpOffset(uv00, DecalSize, pts);
        float2 p10 = GlobalOrigin + float2(localCoord) + float2(1,0) + GetWarpOffset(uv10, DecalSize, pts);
        float2 p01 = GlobalOrigin + float2(localCoord) + float2(0,1) + GetWarpOffset(uv01, DecalSize, pts);
        float2 p11 = GlobalOrigin + float2(localCoord) + float2(1,1) + GetWarpOffset(uv11, DecalSize, pts);

        // Bounding Box
        float2 minP = min(min(p00, p10), min(p01, p11));
        float2 maxP = max(max(p00, p10), max(p01, p11));

        int minX = max((int)floor(minP.x), (int)CompRect.x);
        int minY = max((int)floor(minP.y), (int)CompRect.y);
        int maxX = min((int)ceil(maxP.x), (int)(CompRect.x + CompRect.z) - 1);
        int maxY = min((int)ceil(maxP.y), (int)(CompRect.y + CompRect.w) - 1);

        // Растеризация внутри Bounding Box
        // Делим квад на два треугольника: T1(p00, p10, p01) и T2(p10, p11, p01)
        for (int y = minY; y <= maxY; ++y) {
            for (int x = minX; x <= maxX; ++x) {
                float2 pt = float2(x + 0.5f, y + 0.5f);
                
                // Простая проверка принадлежности пикселя к трансформированному кваду
                // Если точка внутри любого из двух треугольников - пишем цвет
                if (PointInTriangle(pt, p00, p10, p01) || PointInTriangle(pt, p10, p11, p01)) 
                {
                    float currentAlpha = col.a;
                    if (UseMask) {
                        float2 fUV = (pt - CompRect.xy) / CompRect.zw;
                        currentAlpha *= SlotMask.SampleLevel(samLinear, fUV, 0).r;
                    }

                    if (currentAlpha > 0.001f) {
                        int2 tPos = int2(x,y);
                        float4 bg = Target[tPos];
                        bg.rgb = lerp(bg.rgb, col.rgb, currentAlpha);
                        bg.a = max(bg.a, currentAlpha);
                        Target[tPos] = bg;
                    }
                }
            }
        }
    }
}