RWTexture2D<float4> Atlas : register(u0);
// Используем Buffer<float2> для корректного чтения из-за особенностей вашего движка
Buffer<int2> DecalDataBuffer : register(t1); 
Texture2D<float4> MultiMaskTexture : register(t2);
Texture2D<float4> atlas_slot_60 : register(t60);
Texture2D<float4> atlas_slot_61 : register(t61);
Texture2D<float4> atlas_slot_62 : register(t62);
// ... и так далее для всех слотов

Texture1D<float4> IniParams : register(t120);
#define RegionParams    IniParams[44]
#define TargetOffset      uint2(RegionParams.x, RegionParams.y)
#define RegionDimensions  uint2(RegionParams.z, RegionParams.w)

// --- НОВЫЕ ПАРАМЕТРЫ ---
// Глобальное смещение в пикселях.
static const int2 GlobalPixelOffset = int2(0, 0); 
// Глобальный масштаб. (1.0, 1.0) - без изменений. 
// (2.0, 2.0) - в два раза больше. (0.5, 0.5) - в два раза меньше.
static const float2 GlobalScale = float2(1.0f, 1.0f); 

/*
// ПРИМЕЧАНИЕ: Если вы захотите передавать эти параметры извне,
// раскомментируйте эти строки и закомментируйте static const выше:
#define GlobalPixelOffset int2(IniParams[71].x, IniParams[71].y)
#define GlobalScale       float2(IniParams[71].z, IniParams[71].w)
*/

[numthreads(32, 32, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    uint2 localCoord = dispatchThreadID.xy;

    if (localCoord.x >= RegionDimensions.x || localCoord.y >= RegionDimensions.y)
        return;
    
    uint2 targetPixelCoord = TargetOffset + localCoord;
    float4 finalColor = Atlas[targetPixelCoord];
    float4 maskColor = MultiMaskTexture.Load(int3(localCoord, 0));
   
    for (int i = 0; i <= 0; i++) // Убедитесь, что это число соответствует вашим слотам
    {
        // Читаем float2 и сразу кастуем в int
        float2 data = DecalDataBuffer[i];
        int slotID = (int)data.x;
        int decalIndex = (int)data.y;

        if (decalIndex < 0) {
            continue;
        }

        int2 decalPosition, decalSize; 
        float2 tileGrid;
        bool mirror, flip;
        int atlasIndex;

        switch (slotID) {
            case 0: decalPosition=int2(768, 672); decalSize=int2(512, 256); tileGrid=float2(4,2); mirror=false; flip=false; atlasIndex=60; break;
            case 1: decalPosition=int2(100, 150); decalSize=int2(200, 150); tileGrid=float2(4,2); mirror=false; flip=false; atlasIndex=61; break;
            case 2: decalPosition=int2(500, 800); decalSize=int2(256, 128); tileGrid=float2(2,2); mirror=true;  flip=false; atlasIndex=61; break;
            default: decalPosition=int2(0,0); decalSize=int2(0,0); tileGrid=float2(1,1); mirror=false; flip=false; atlasIndex=60; break;
        }

        // --- НОВАЯ ЛОГИКА ГЛОБАЛЬНОГО МАСШТАБИРОВАНИЯ ---
        // 1. Применяем глобальный масштаб к размеру декали.
        float2 scaledDecalSize = (float2)decalSize * GlobalScale;

        // 2. Вычисляем смещение позиции. Это нужно, чтобы масштабирование происходило
        //    от центра декали, а не от ее левого верхнего угла.
        float2 positionCorrection = ((float2)decalSize - scaledDecalSize) * 0.5f;

        // 3. Применяем все коррекции: смещение от масштаба и глобальное смещение.
        int2 correctedDecalPosition = decalPosition + (int2)positionCorrection + GlobalPixelOffset;
        
        // --- КОНЕЦ НОВОЙ ЛОГИКИ ---

        int2 relativeCoord = (int2)localCoord - correctedDecalPosition;
        
        // ИЗМЕНЕНИЕ: Границы проверки теперь используют новый, масштабированный размер.
        if (all(relativeCoord >= 0) && all(relativeCoord < (int2)ceil(scaledDecalSize)))
        {
            uint2 texSize;
            switch(atlasIndex)
            {
                case 60: atlas_slot_60.GetDimensions(texSize.x, texSize.y); break;
                case 61: atlas_slot_61.GetDimensions(texSize.x, texSize.y); break;
                default: texSize = uint2(1,1); break;
            }

            float2 tileSizeInPixels = float2(texSize) / tileGrid;

            // ИЗМЕНЕНИЕ: Расчет UV теперь тоже использует масштабированный размер.
            float2 localDecalUV = (float2(relativeCoord) + 0.5f) / scaledDecalSize;

            localDecalUV.y = 1.0f - localDecalUV.y;
            if(mirror) { localDecalUV.y = 1.0f - localDecalUV.y; }
            if(flip)   { localDecalUV.x = 1.0f - localDecalUV.x; }

            float2 pixelCoordInTile = localDecalUV * tileSizeInPixels;

            float f_decalIndex = (float)decalIndex;
            float tileY = floor(f_decalIndex / tileGrid.x);
            float tileX = f_decalIndex - tileY * tileGrid.x;
            float2 tileOffsetInPixels = float2(tileX, tileY) * tileSizeInPixels;

            int2 finalAtlasCoord = int2(tileOffsetInPixels + pixelCoordInTile);

            float4 decalColor = float4(0,0,0,0);
            switch(atlasIndex)
            {
                case 60: decalColor = atlas_slot_60.Load(int3(finalAtlasCoord, 0)); break;
                case 61: decalColor = atlas_slot_61.Load(int3(finalAtlasCoord, 0)); break;
            }
            
            finalColor.rgb = lerp(finalColor.rgb, decalColor.rgb, decalColor.a);
            finalColor.a = max(finalColor.a, decalColor.a);
        }
    }
    Atlas[targetPixelCoord] = finalColor;
}