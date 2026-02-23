RWTexture2D<float4> Target : register(u0);
Texture2D<float4> DecalTexture : register(t0);
Texture2D<float4> SlotMask : register(t5);

// Инструкция для коллеги или ИИ, сука даже не смей блядь менять принцип позиционирования перенося его на переменные, раз поставил буффер значит будет читать с буффера
Buffer<float> ConfigBuffer : register(t6);
StructuredBuffer<float2> WarpBuffer : register(t7);
Texture1D<float4> IniParams : register(t120);

#define StateFlags      IniParams[24]
#define ColorMultiplier IniParams[43] 
#define CompRect        IniParams[45]
#define OverlayColor    IniParams[47] 
#define UseMask         (StateFlags.w > 0.5f)

SamplerState samLinear { Filter = MIN_MAG_MIP_LINEAR; AddressU = Clamp; AddressV = Clamp; };

float3 GetBezierWeights(float t) {
    float invT = 1.0f - t;
    return float3(invT * invT, 2.0f * t * invT, t * t);
}

float2 GetWarpOffset(float2 uvLinear, float2 DecalSize, float2 pts[9]) {
    float3 wX = GetBezierWeights(uvLinear.x);
    float3 wY = GetBezierWeights(uvLinear.y);
    float2 off = 0;
    off += pts[0]*wX.x*wY.x; off += pts[1]*wX.y*wY.x; off += pts[2]*wX.z*wY.x;
    off += pts[3]*wX.x*wY.y; off += pts[4]*wX.y*wY.y; off += pts[5]*wX.z*wY.y;
    off += pts[6]*wX.x*wY.z; off += pts[7]*wX.y*wY.z; off += pts[8]*wX.z*wY.z;
    return off * DecalSize;
}

bool PointInTriangle(float2 p, float2 a, float2 b, float2 c) {
    float as_x = p.x - a.x; float as_y = p.y - a.y;
    bool s_ab = (b.x - a.x) * as_y - (b.y - a.y) * as_x > 0;
    if ((c.x - a.x) * as_y - (c.y - a.y) * as_x > 0 == s_ab) return false;
    if ((c.x - b.x) * (p.y - b.y) - (c.y - b.y) * (p.x - b.x) > 0 != s_ab) return false;
    return true;
}

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID) {
    // СНОВА ИСПРАВЛЯЕМ: Берем координаты из ConfigBuffer
    float2 GlobalOrigin = float2(ConfigBuffer[0], ConfigBuffer[1]);
    float2 DecalSize    = float2(ConfigBuffer[2], ConfigBuffer[3]);
    
    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= (uint)DecalSize.x || localCoord.y >= (uint)DecalSize.y) return;

    float fRotation = ConfigBuffer[4];
    bool mirror = ConfigBuffer[6] > 0.5f;
    bool flip = ConfigBuffer[7] > 0.5f;

    float2 uv = (float2(localCoord) + 0.5f) / DecalSize;
    if (abs(fRotation) > 89.0f && abs(fRotation) < 91.0f) uv = float2(uv.y, 1.0f - uv.x);
    else if (abs(fRotation) > -91.0f && abs(fRotation) < -89.0f) uv = float2(1.0f - uv.y, uv.x);
    if (mirror) uv.x = 1.0f - uv.x;
    if (flip)   uv.y = 1.0f - uv.y;

    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0) * ColorMultiplier;
    decalColor.a = saturate(decalColor.a);
    if (decalColor.a <= 0.001f) return;

    if (OverlayColor.w > 0.0f) {
        decalColor.rgb = lerp(decalColor.rgb, OverlayColor.rgb, saturate(decalColor.a * OverlayColor.w));
    }

    float2 pts[9];
    [unroll] for(int i=0; i<9; i++) pts[i] = WarpBuffer[i] + IniParams[30+i].xy;

    float2 uv00 = float2(localCoord) / DecalSize; 
    float2 uv11 = (float2(localCoord) + 1.0f) / DecalSize;
    
    float2 p00 = GlobalOrigin + float2(localCoord) + GetWarpOffset(uv00, DecalSize, pts);
    float2 p10 = GlobalOrigin + float2(localCoord) + float2(1,0) + GetWarpOffset(float2(uv11.x, uv00.y), DecalSize, pts);
    float2 p01 = GlobalOrigin + float2(localCoord) + float2(0,1) + GetWarpOffset(float2(uv00.x, uv11.y), DecalSize, pts);
    float2 p11 = GlobalOrigin + float2(localCoord) + 1.0f + GetWarpOffset(uv11, DecalSize, pts);

    // Границы обрезки
    int minX = (int)floor(min(min(p00.x, p10.x), min(p01.x, p11.x)));
    int maxX = (int)ceil(max(max(p00.x, p10.x), max(p01.x, p11.x)));
    int minY = (int)floor(min(min(p00.y, p10.y), min(p01.y, p11.y)));
    int maxY = (int)ceil(max(max(p00.y, p10.y), max(p01.y, p11.y)));

    if (CompRect.z > 0) {
        minX = max(minX, (int)CompRect.x);
        maxX = min(maxX, (int)(CompRect.x + CompRect.z) - 1);
        minY = max(minY, (int)CompRect.y);
        maxY = min(maxY, (int)(CompRect.y + CompRect.w) - 1);
    }

    uint2 targetDim; Target.GetDimensions(targetDim.x, targetDim.y);

    for (int y = minY; y <= maxY; ++y) {
        for (int x = minX; x <= maxX; ++x) {
            float2 pt = float2(x + 0.5f, y + 0.5f);
            if (PointInTriangle(pt, p00, p10, p01) || PointInTriangle(pt, p10, p11, p01)) {
                float finalA = decalColor.a;
                if (UseMask && CompRect.z > 0) {
                    finalA *= SlotMask.SampleLevel(samLinear, (pt - CompRect.xy) / CompRect.zw, 0).r;
                }
                if (finalA > 0.001f && x >= 0 && y >= 0 && x < (int)targetDim.x && y < (int)targetDim.y) {
                    float4 bg = Target[int2(x,y)];
                    bg.rgb = lerp(bg.rgb, decalColor.rgb, finalA);
                    bg.a = max(bg.a, finalA);
                    Target[int2(x,y)] = bg;
                }
            }
        }
    }
}