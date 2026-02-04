// Файл: /modules/facetexworks/decal_draw_composite.hlsl

RWTexture2D<float4> TargetDiffuse : register(u0);  
RWTexture2D<float4> TargetMaterial : register(u1); 

Texture2D<float4> DecalTexture : register(t0);
Buffer<float> ConfigBuffer : register(t1);

Texture1D<float4> IniParams : register(t120);

// ГЕОМЕТРИЯ ДЕКАЛИ (x44...w44)
#define DecalRect    IniParams[44]
#define GlobalOrigin uint2(DecalRect.x, DecalRect.y)
#define DecalSize    uint2(DecalRect.z, DecalRect.w)

// НАСТРОЙКИ ЦВЕТА МАТЕРИАЛА (x45...w45)
#define MaterialData IniParams[45]

// РАЗМЕРЫ ХОЛСТОВ (x46...w46) - НОВОЕ
// x = Размер Diffuse (1024), y = Размер Material (256)
#define CanvasSizes IniParams[46] 

SamplerState samLinear { Filter = MIN_MAG_MIP_LINEAR; AddressU = Clamp; AddressV = Clamp; };

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    // --- 1. Работа с текстурой Декали (произвольный размер) ---
    uint2 localCoord = dispatchThreadID.xy;
    if (localCoord.x >= DecalSize.x || localCoord.y >= DecalSize.y) return;

    // Читаем конфиг
    float fOffX = ConfigBuffer[4]; float fOffY = ConfigBuffer[5];
    float fMirror = ConfigBuffer[6]; float fFlip = ConfigBuffer[7];
    int2 offset = int2(fOffX, fOffY);
    
    // UV
    float2 uv = (float2(localCoord) + 0.5f) / float2(DecalSize);
    if (fMirror > 0.5f) uv.x = 1.0f - uv.x;
    if (fFlip > 0.5f)   uv.y = 1.0f - uv.y;

    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0);
    if (decalColor.a <= 0.001f) return;

    // --- 2. Запись в DIFFUSE (Базовое разрешение, например 1024) ---
    // Используем явно переданный размер из x46 для проверок границ
    int diffuseSize = (int)CanvasSizes.x; 
    
    int2 targetPos = GlobalOrigin + localCoord + offset;

    // Проверка границ на основе переменной
    if (targetPos.x >= 0 && targetPos.y >= 0 && targetPos.x < diffuseSize && targetPos.y < diffuseSize)
    {
        float4 finalColor = TargetDiffuse[targetPos];
        finalColor.rgb = lerp(finalColor.rgb, decalColor.rgb, decalColor.a);
        finalColor.a = max(finalColor.a, decalColor.a);
        TargetDiffuse[targetPos] = finalColor;
    }

    // --- 3. Ретрансляция в MATERIAL (Масштабируемое разрешение, например 256) ---
    if (MaterialData.w > 0.0f)
    {
        float materialSize = CanvasSizes.y;
        float scaleFactor = materialSize / CanvasSizes.x;
        int2 matPos = int2(floor((float2(targetPos) * scaleFactor) + 0.01f));

        if (matPos.x >= 0 && matPos.y >= 0 && matPos.x < (int)materialSize && matPos.y < (int)materialSize)
        {
            float4 currentMat = TargetMaterial[matPos];
            
            // ЛОГИКА УСИЛЕНИЯ:
            // Умножаем исходную альфу (0.0-1.0) на твой коэффициент (например, 5.0)
            float rawFactor = decalColor.a * MaterialData.w;
            
            // Обязательно делаем saturate (обрезаем всё, что больше 1.0),
            // иначе lerp начнет выдавать кислотные цвета при пересвете.
            float blendFactor = saturate(rawFactor);

            // Смешиваем
            currentMat.rgb = lerp(currentMat.rgb, MaterialData.rgb, blendFactor);
            
            TargetMaterial[matPos] = currentMat;
        }
    }
}