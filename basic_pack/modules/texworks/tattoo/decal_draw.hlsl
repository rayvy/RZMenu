RWTexture2D<float4> Atlas : register(u0);
Buffer<float2> DecalDataBuffer : register(t1);
Texture2D<float4> MultiMaskTexture : register(t2);
Texture2D<float4> atlas_slot_60 : register(t60);
Texture2D<float4> atlas_slot_61 : register(t61);
// Добавил слот 62 на всякий случай, как в твоем switch
Texture2D<float4> atlas_slot_62 : register(t62);
Texture2D<float4> atlas_slot_63 : register(t63);
Texture2D<float4> atlas_slot_64 : register(t64);
Texture2D<float4> atlas_slot_65 : register(t65);
Texture2D<float4> atlas_slot_66 : register(t66);
Texture2D<float4> atlas_slot_67 : register(t67);
Texture2D<float4> atlas_slot_68 : register(t68);
Texture2D<float4> atlas_slot_69 : register(t69);

Texture1D<float4> IniParams : register(t120);
#define RegionParams    IniParams[44]
#define TargetOffset      uint2(RegionParams.x, RegionParams.y)
#define RegionDimensions  uint2(RegionParams.z, RegionParams.w)

// --- НОВЫЕ СТРОКИ ДЛЯ ТОЧНОГО ПОВОРОТА ---
// 1. Определяем константу PI для максимальной точности.
static const float PI = 3.1415926535f;

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    uint2 localCoord = dispatchThreadID.xy;

    if (localCoord.x >= RegionDimensions.x || localCoord.y >= RegionDimensions.y)
        return;
    
    uint2 targetPixelCoord = TargetOffset + localCoord;
    float4 finalColor = Atlas[targetPixelCoord];
    float4 maskColor = MultiMaskTexture.Load(int3(localCoord, 0));
   
    for (int i = 0; i <= 6; i++) // У тебя было 5, оставляю так же
    {
        float2 data = DecalDataBuffer[i];
        int slotID = (int)data.x;
        int decalIndex = (int)data.y;

        if (decalIndex < -1) {
            continue;
        }

        float2 decalCenter, decalSize, tileGrid;
        float decalAngle; // Эта переменная теперь будет в ГРАДУСАХ
        bool mirror, flip;
        int atlasIndex;
        float constsizePubic = 0.29;
        // В этом блоке теперь можно использовать привычные градусы
        switch (slotID) {
            case 0: decalCenter=float2(0.196043,0.155);decalSize=float2(0.141224,0.141224);decalAngle=0.0;tileGrid=float2(4,2);mirror=true;flip=false;atlasIndex=60;break;
            case 1: decalCenter=float2(0.6975,0.071274);decalSize=float2(constsizePubic*1.175,constsizePubic);decalAngle=90.0;tileGrid=float2(4,2);mirror=true;flip=true;atlasIndex=60;break; // Пример: 45 градусов
            case 2: decalCenter=float2(0.143446,0.418294);decalSize=float2(0.105525,0.105525);decalAngle=0;tileGrid=float2(4,2);mirror=true;flip=false;atlasIndex=61;break;
            case 3: decalCenter=float2(0.248973,0.418294);decalSize=float2(0.105525,0.105525);decalAngle=0.0;tileGrid=float2(4,2);mirror=true;flip=true;atlasIndex=61;break; // Пример: -90 градусов
            case 4: decalCenter=float2(0.503097,0.155186);decalSize=float2(0.141224,0.141224);decalAngle=0.0;tileGrid=float2(4,2);mirror=true;flip=false;atlasIndex=62;break;
            case 5: decalCenter=float2(0.644324,0.155186);decalSize=float2(0.141224,0.141224);decalAngle=0.0;tileGrid=float2(4,2);mirror=true;flip=false;atlasIndex=62;break; // Пример: 180 градусов
            case 6: decalCenter=float2(0.573711,0.177686);decalSize=float2(0.282451,0.186225);decalAngle=0;tileGrid=float2(2,2);mirror=true;flip=false;atlasIndex=63;break;
            default: decalCenter=float2(0.0,0.0);decalSize=float2(0.0,0.0);decalAngle=0.0;tileGrid=float2(0,0);mirror=true;flip=false;atlasIndex=60;break;
        }

        // --- Обратное преобразование координат ---
        float2 targetUV = (float2(localCoord) + 0.5f) / float2(RegionDimensions);
        targetUV.y = 1.0f - targetUV.y;
        float2 centeredPos = targetUV - decalCenter;
        
        // --- НОВЫЕ СТРОКИ ДЛЯ ТОЧНОГО ПОВОРОТА ---
        // 2. Конвертируем градусы в радианы
        float decalAngleRad = decalAngle * (PI / 180.0f);
        
        // 3. Используем радианы для вычислений
        float s = sin(-decalAngleRad), c = cos(-decalAngleRad);
        // --- КОНЕЦ НОВЫХ СТРОК ---

        float2 rotatedPos;
        rotatedPos.x = centeredPos.x * c - centeredPos.y * s;
        rotatedPos.y = centeredPos.x * s + centeredPos.y * c;
        float2 decalUV = rotatedPos / decalSize + 0.5f;

        if (all(decalUV >= 0) && all(decalUV <= 1))
        {
            float2 finalDecalUV = decalUV;
            finalDecalUV.x = 1.0f - finalDecalUV.x;
            if(mirror) { finalDecalUV.y = 1.0f - finalDecalUV.y; }
            if(flip)   { finalDecalUV.x = 1.0f - finalDecalUV.x; }

            float f_decalIndex = (float)decalIndex;
            float tileY = floor(f_decalIndex / tileGrid.x);
            float tileX = f_decalIndex - tileY * tileGrid.x;
            float2 tileSize = 1.0f / tileGrid;
            float2 tileOffset = float2(tileX, tileY) * tileSize;
            finalDecalUV = finalDecalUV * tileSize + tileOffset;

            float4 decalColor = float4(0,0,0,0);
            uint2 texSize;
            
            switch(atlasIndex)
            {
                case 60: atlas_slot_60.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_60.Load(int3(finalDecalUV * texSize, 0)); break;
                case 61: atlas_slot_61.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_61.Load(int3(finalDecalUV * texSize, 0)); break;
                case 62: atlas_slot_62.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_62.Load(int3(finalDecalUV * texSize, 0)); break;
                case 63: atlas_slot_63.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_63.Load(int3(finalDecalUV * texSize, 0)); break;
                case 64: atlas_slot_64.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_64.Load(int3(finalDecalUV * texSize, 0)); break;
                // case 65: atlas_slot_65.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_65.Load(int3(finalDecalUV * texSize, 0)); break;
                // case 66: atlas_slot_66.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_66.Load(int3(finalDecalUV * texSize, 0)); break;
                // case 67: atlas_slot_67.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_67.Load(int3(finalDecalUV * texSize, 0)); break;
                // case 68: atlas_slot_68.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_68.Load(int3(finalDecalUV * texSize, 0)); break;
                // case 69: atlas_slot_69.GetDimensions(texSize.x, texSize.y); decalColor = atlas_slot_69.Load(int3(finalDecalUV * texSize, 0)); break;
            }
            switch (slotID)
            {
                case 1: decalColor.a *= maskColor.r; break;
                default: break;
            }
            
            finalColor.rgb = lerp(finalColor.rgb, decalColor.rgb, decalColor.a);
            finalColor.a = max(finalColor.a, decalColor.a);
        }
    }
    Atlas[targetPixelCoord] = finalColor;
}