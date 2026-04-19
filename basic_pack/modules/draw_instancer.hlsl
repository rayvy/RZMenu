/* 
================================================================================
SHADER: UI COMPOSITOR v3.3 (AUTO-FIT TEXT ADDED)
================================================================================
*/

// --- RZMENU FIXED-SLOT PIPELINE CONSTANTS ---
#define BASE_SLOT_COUNT 7

#define SLOT_SHADOW  7
#define SLOT_GLOW    8
#define SLOT_LIVE2D  9

#define BIT_SHADOW  (1u << 0)
#define BIT_GLOW    (1u << 1)
#define BIT_LIVE2D  (1u << 2)

// --- RESOURCES ---
Texture1D<float4> GlobalParams : register(t120);
Buffer<float4>    DataBuffer : register(t100);
Buffer<uint>      IndexBuffer : register(t104);
Buffer<uint>      TextPoolBuffer : register(t103);
Buffer<float4>    ResourceStyleBuffer : register(t105);
Buffer<float4>    BoneBuffer : register(t106);
Buffer<float4>    MeshVertexBuffer : register(t107);
Buffer<float4>    SkinWeightBuffer : register(t108);

Texture2D<float4> AtlasIcons : register(t80);
Texture2D<float4> AtlasFont0 : register(t82);
Texture2D<float4> AtlasFont1 : register(t83);
Texture2D<float4> AtlasFont2 : register(t84);
Texture2D<float4> AtlasFont3 : register(t85);
Texture2D<float4> TexBlurMap : register(t89);
Texture2D<float4> TexBackbuffer : register(t90);
SamplerState      LinearSampler : register(s0);

// --- GLOBAL VARS ---
static float2 ScreenRes = GlobalParams[99].zw;
static float2 CursorPos = GlobalParams[99].xy;
static float  GlobalTime = GlobalParams[98].w;

// --- CONSTANTS ---
static const int MODE_SOLID = 0;
static const int MODE_TEX_OVERLAY = 1;
static const int MODE_TEX_MULTIPLY = 2;
static const int MODE_TEXT = 3;
static const int MODE_NUMBER = 4;
static const int MODE_LIVE2D = 9;

// --- NEW MODES ---
static const int MODE_COLOR_REPLACE = 21; 
static const int MODE_MASKED_BLUR = 9000; 
static const int MODE_BLUR_BG_START = 90;

static const int MODE_HSV = 728386;
static const int MODE_CURSOR = 728387;
static const int MODE_GRADIENT = 728388;

static const int ANIM_ROTATE = 1;
static const int ANIM_HOVER_TURN = 2;
static const int ANIM_DISINTEGRATE = 3; 

// --- STYLE CONSTANTS ---
#define BIT_SHADOW      (1u << 0)
#define BIT_GLOW        (1u << 1)
#define BIT_OUTLINE     (1u << 2)
#define BIT_GRAYSCALE   (1u << 3)
#define BIT_CHROMATIC   (1u << 4)
#define BIT_GRADIENT    (1u << 5)
#define BIT_ANIM_RESIZE (1u << 6)
#define BIT_ANIM_SHEEN  (1u << 7)
#define BIT_ANIM_ROTATE (1u << 8)
#define BIT_FN_FIXRATIO (1u << 9)
#define BIT_BLUR        (1u << 10)
#define BIT_BLUR_MASK   (1u << 11)

static const uint MAX_CHARS = 32;
static const uint MAX_LIVE2D_CELLS = 256;
static const uint FONT_GRID_SIZE = 16;
static const float EXPAND_PX = 30.0; 

// --- UTILS ---

float3 HsvToRgb(float3 c) {
    float4 K = float4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    float3 p = abs(frac(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * lerp(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// --- LIVE2D SKINNING ---

float2 ApplyLive2DSkinning(uint vID, uint iID, uint base_idx, float2 size) {
    uint cellIdx = vID / 6;
    // Найти element mesh offset из DataBuffer (8-й слот, x)
    uint meshOffset = asuint(DataBuffer[base_idx + 7].x);
    uint vBase = meshOffset + cellIdx;
    uint wBase = vBase * 2; // 2 float4 на вершину в SkinWeightBuffer
    
    // Читаем rest position и UV для этой вершины
    float4 meshData = MeshVertexBuffer[vBase];
    float2 restPos = meshData.xy; // В координатах 0-1 относительно элемента
    
    // Читаем skinning weights
    float4 skin0 = SkinWeightBuffer[wBase + 0]; // [b0, w0, b1, w1]
    float4 skin1 = SkinWeightBuffer[wBase + 1]; // [b2, w2, b3, w3]
    
    float2 deformed = float2(0, 0);
    bool anyWeight = false;

    [unroll]
    for (int i = 0; i < 4; i++) {
        float boneId = (i < 2) ? skin0[i*2] : skin1[(i-2)*2];
        float weight = (i < 2) ? skin0[i*2+1] : skin1[(i-2)*2+1];
        
        if (boneId >= 0 && weight > 0.001) {
            int bi = (int)boneId * 3;
            float4 bm0 = BoneBuffer[bi + 0]; // (wx, wy, cos, sin)
            float4 bm1 = BoneBuffer[bi + 1]; // (sx, sy, parentID, flags)
            float4 bm2 = BoneBuffer[bi + 2]; // (pivotX, pivotY, restX, restY)
            
            // 1. Координата относительно "покоя" кости
            float2 local = restPos - bm2.zw; 
            // 2. Относительно пивота
            local -= bm2.xy;
            
            // 3. Масштаб и вращение
            float2 s = local * bm1.xy;
            float2 r = float2(
                s.x * bm0.z - s.y * bm0.w,
                s.x * bm0.w + s.y * bm0.z
            );
            
            // 4. Мировая позиция кости + пивот + вращенная дельта
            deformed += (bm0.xy + bm2.xy + r) * weight;
            anyWeight = true;
        }
    }
    
    return anyWeight ? deformed : restPos;
}

// --- STRUCTURES ---

struct VertexOutput {
    float4 position : SV_Position;
    float4 color : COLOR0;
    float4 atlasRect : TEXCOORD0;  
    float2 contentUV : TEXCOORD1;  
    float4 objectRect : TEXCOORD3; 
    float4 clipRect : TEXCOORD4;
    int    drawMode : TEXCOORD5;
    float  animType : TEXCOORD6;
    float  styleId : TEXCOORD7;
    float4 extraData : TEXCOORD8; 
    float    mirrorMode : TEXCOORD9;
};

struct CharMetrics {
    float advance; float glyphW; float glyphH; float offX; float offY;
};

CharMetrics FetchCharMetrics(uint c, uint fontSlot) {
    CharMetrics m = (CharMetrics)0;
    if (c < 32) c = 32;
    uint w = 0, h = 0; 
    
    if (fontSlot == 1) AtlasFont1.GetDimensions(w, h);
    else if (fontSlot == 2) AtlasFont2.GetDimensions(w, h);
    else if (fontSlot == 3) AtlasFont3.GetDimensions(w, h);
    else AtlasFont0.GetDimensions(w, h);

    if (w == 0 || h == 0) return m;

    float cs = (float)(w / FONT_GRID_SIZE);
    uint idx = c - 32;
    uint metaY = h - (uint)cs;
    
    int3 p1 = int3(idx % w, metaY + (idx/w)*2, 0);
    int3 p2 = int3(idx % w, metaY + (idx/w)*2 + 1, 0);
    float4 d1 = float4(0,0,0,0);
    float4 d2 = float4(0,0,0,0);
    
    if (fontSlot == 1) { d1 = AtlasFont1.Load(p1); d2 = AtlasFont1.Load(p2); }
    else if (fontSlot == 2) { d1 = AtlasFont2.Load(p1); d2 = AtlasFont2.Load(p2); }
    else if (fontSlot == 3) { d1 = AtlasFont3.Load(p1); d2 = AtlasFont3.Load(p2); }
    else { d1 = AtlasFont0.Load(p1); d2 = AtlasFont0.Load(p2); }
    
    m.advance = d1.r*2*cs; m.glyphW = d1.g*2*cs; m.offX = (d1.b*2-1)*cs; m.offY = (d1.a*2-1)*cs; m.glyphH = d2.r*2*cs;
    return m;
}

void ParseNumber(float val, int prec, inout uint buf[MAX_CHARS], inout uint cnt) {
    float p10 = pow(10.0, (float)prec);
    val = round(val * p10) / p10;
    if (val < 0.0) { if (cnt < MAX_CHARS) buf[cnt++] = '-'; val = -val; }
    val += 1e-7; uint ip = (uint)val;
    if (ip == 0) { if (cnt < MAX_CHARS) buf[cnt++] = '0'; }
    else {
        uint tmp = ip; uint d[10]; uint dc = 0;
        while(tmp > 0 && dc < 10) { d[dc++] = tmp % 10; tmp /= 10; }
        for(uint i=0; i<dc; ++i) if(cnt < MAX_CHARS) buf[cnt++] = '0' + d[dc-1-i];
    }
    if (prec > 0) {
        if (cnt < MAX_CHARS) buf[cnt++] = '.';
        float fp = val - (float)ip;
        for(int i=0; i<prec; ++i) { fp*=10; uint digit=(uint)fp; if(digit>9) digit=9; if(cnt<MAX_CHARS) buf[cnt++]='0'+digit; fp-=(float)digit; }
    }
}

// --- VERTEX SHADER ---

float4 ComputeLayout(int mode, uint vID, float4 tile, uint fontSlot, inout float2 pos, inout float2 size) {
    if (mode == MODE_TEXT || mode == MODE_NUMBER) {
        uint chars[MAX_CHARS]; uint count = 0;
        if (mode == MODE_TEXT) {
            uint off = (uint)tile.x; count = min((uint)tile.y, MAX_CHARS);
            for(uint i=0; i<count; ++i) chars[i] = TextPoolBuffer[off+i];
        } else ParseNumber(tile.x, clamp((int)tile.y,0,9), chars, count);

        uint w = 0, h = 0; 
        if (fontSlot == 1) AtlasFont1.GetDimensions(w, h);
        else if (fontSlot == 2) AtlasFont2.GetDimensions(w, h);
        else if (fontSlot == 3) AtlasFont3.GetDimensions(w, h);
        else AtlasFont0.GetDimensions(w, h);
        
        float cs = 1.0;
        if (w > 0) cs = (float)(w/16);
        float scale = (size.y * ScreenRes.y) / cs;
        
        float totalW = 0, firstOff = 0;
        if (count > 0) {
            firstOff = FetchCharMetrics(chars[0], fontSlot).offX;
            for(uint k=0; k<count-1; ++k) totalW += FetchCharMetrics(chars[k], fontSlot).advance;
            CharMetrics last = FetchCharMetrics(chars[count-1], fontSlot);
            totalW += last.offX + last.glyphW - firstOff;
        }

        // --- AUTO-FIT LOGIC (SQUISH) ---
        float inputLimitWidth = size.x * ScreenRes.x; // Лимит ширины из $sizeX
        float currentTextWidth = totalW * scale;      // Реальная ширина текста
        float squeeze = 1.0;

        int align = (int)tile.z;
        bool isFree = align >= 3;
        if (isFree) align -= 3;

        // Если задан лимит (> 1px) И текст шире лимита -> сжимаем (только если не FREE mode)
        if (!isFree && inputLimitWidth > 1.0 && currentTextWidth > inputLimitWidth) {
            squeeze = inputLimitWidth / currentTextWidth;
        }
        // -------------------------------
        
        float shift = 0;
        if (align == 1) shift = (firstOff*2.0 + totalW)*0.5;
        if (align == 2) shift = firstOff + totalW;
        
        float2 basePos = pos;
        // Применяем squeeze к сдвигу выравнивания
        basePos.x -= (shift / ScreenRes.x) * scale * squeeze;
        
        uint idx = vID / 6;
        uint code = (idx < count) ? chars[idx] : ' ';
        
        float curX = 0;
        for(uint i=0; i<idx; ++i) curX += FetchCharMetrics(chars[i], fontSlot).advance;
        CharMetrics m = FetchCharMetrics(code, fontSlot);
        CharMetrics ref = FetchCharMetrics('A', fontSlot);
        
        float baseAdj = (ref.offY + ref.glyphH + (128.0/7.5) - (m.offY + m.glyphH));
        pos.y = basePos.y + (baseAdj / ScreenRes.y) * scale;
        
        // Применяем squeeze к позиции буквы (уменьшаем расстояние между буквами)
        pos.x = basePos.x + ((curX + m.offX) / ScreenRes.x) * scale * squeeze;
        
        // Применяем squeeze к ширине самой буквы (сплющиваем букву)
        size.x = (m.glyphW / ScreenRes.x) * scale * squeeze;
        size.y = (m.glyphH / ScreenRes.y) * scale;
        
        float2 uvCell = 1.0 / float2(16.0, (float)(h / cs));
        float2 uvStart = float2((code-32)%16, (code-32)/16) * uvCell;
        return float4(
            uvStart + float2(m.offX, m.offY)/cs*uvCell, 
            float2(m.glyphW, m.glyphH)/cs*uvCell 
        );
    } 
    else if (mode >= MODE_TEX_OVERLAY) { 
        uint w, h; AtlasIcons.GetDimensions(w, h);
        float2 dim = float2(max(1, w), max(1, h));
        return float4(tile.xy / dim, tile.zw / dim);
    }
    return float4(0,0,1,1);
}

float2 ApplyAnimation(float type, uint styleFlags, int styleBaseIdx, float2 pos, float2 size, float2 uv) {
    float2 center = pos + size * 0.5;
    float2 local = uv - 0.5;
    
    if (type == ANIM_HOVER_TURN) {
        float2 dir = CursorPos - center;
        dir.y *= ScreenRes.y/ScreenRes.x;
        float dist = length(dir);
        float2 tilt = (dist > 0.001 ? normalize(dir) : float2(0,0)) * pow(saturate(1.0 - dist/0.1), 2) * 0.1;
        local -= tilt * dot(local, tilt); 
        return center + local * size;
    }
    if (styleFlags & BIT_ANIM_ROTATE) {
        float speed = ResourceStyleBuffer[styleBaseIdx + 10].z;
        if (speed == 0.0) speed = 1.0;
        float a = 6.28 * GlobalTime * speed;
        float s = sin(a), c = cos(a);
        return center + mul(float2x2(c, -s, s, c), local) * size;
    }
    return pos + uv * size;
}

#ifdef VERTEX_SHADER
void main(uint vID : SV_VertexID, uint iID : SV_InstanceID, out VertexOutput output) {
    output = (VertexOutput)0;
    
    uint base_idx = IndexBuffer[iID];
    
    float4 header = DataBuffer[base_idx + 0];
    uint flags = asuint(header.x);

    float4 params = DataBuffer[base_idx + 6];
    output.drawMode = (int)params.w;
    output.animType = params.x;
    output.styleId = params.y;
    output.color = DataBuffer[base_idx + 2];
    output.clipRect = DataBuffer[base_idx + 5];
    
    float4 tileData = DataBuffer[base_idx + 3];
    float4 mirrorData = DataBuffer[base_idx + 4];
    
    output.extraData.x = tileData.x;
    output.extraData.y = mirrorData.y; // fontSlot passed through G channel
    output.mirrorMode = (int)mirrorData.x;

    float2 pos = DataBuffer[base_idx + 1].xy;
    float2 size = DataBuffer[base_idx + 1].zw;

    bool isText = (output.drawMode == MODE_TEXT || output.drawMode == MODE_NUMBER);
    bool isLive2D = (output.drawMode == MODE_LIVE2D);

    if (!isText && !isLive2D && vID >= 6) { output.position = 0; return; }
    if (isText && (vID/6) >= MAX_CHARS) { output.position = 0; return; }
    if (isLive2D && (vID/6) >= MAX_LIVE2D_CELLS) { output.position = 0; return; }

    uint styleFlags = 0;
    int styleBaseIdx = -1;
    if (output.styleId >= 0) {
        styleBaseIdx = (int)output.styleId * 12;
        styleFlags = asuint(ResourceStyleBuffer[styleBaseIdx + 0].x);

    }

    if (styleFlags & BIT_ANIM_RESIZE) {
        float scaleFactor = ResourceStyleBuffer[styleBaseIdx + 7].w;
        if (scaleFactor <= 0.01) scaleFactor = 1.125;
        float2 c = pos + size * 0.5;
        float2 d = CursorPos - c; d.x *= ScreenRes.x/ScreenRes.y;
        float prox = 1.0 - pow(1.0 - saturate(1.0 - length(d)/0.008), 2);
        float s = 1.0 + ((scaleFactor - 1.0) * prox);
        pos = c - size*s*0.5; size *= s;
    }
    output.objectRect = float4(pos, size);

    float2 quadUv;
    uint lID = vID % 6;
    if (lID == 0 || lID == 3) quadUv = float2(0,0);
    else if (lID == 1 || lID == 5) quadUv = float2(1,1);
    else if (lID == 2) quadUv = float2(0,1);
    else quadUv = float2(1,0);

    if (isLive2D) {
        float2 skinPos = ApplyLive2DSkinning(vID, iID, base_idx, size);
        // Live2D возвращает координаты в нормализованном пространстве экрана или элемента?
        // Будем считать что в координатах экрана (0-1), как и обычный pos
        pos = skinPos;
        output.atlasRect = float4(MeshVertexBuffer[asuint(DataBuffer[base_idx+7].x) + (vID/6)].zw, 1, 1); 
        // В Live2D режиме atlasRect.xy — это UV из буфера меша
    } else {
        output.atlasRect = ComputeLayout(output.drawMode, vID, tileData, (uint)output.extraData.y, pos, size);
    }

    bool allowExpand = (output.drawMode < MODE_BLUR_BG_START && output.drawMode != MODE_MASKED_BLUR);
    float2 expandVec = allowExpand ? (EXPAND_PX / ScreenRes) : float2(0,0);
    
    float2 expandedPos = pos - expandVec;
    float2 expandedSize = size + expandVec * 2.0;

    output.contentUV = (quadUv * expandedSize - expandVec) / size;

    if (isText) {
        output.contentUV.y = 1.0 - output.contentUV.y;
    }

    float2 finalPos = ApplyAnimation(output.animType, styleFlags, styleBaseIdx, expandedPos, expandedSize, quadUv);
    float rotationTurns = mirrorData.w;
    if (rotationTurns != 0.0) {
        // Конвертируем обороты (0.0 - 1.0) в радианы
        float a = rotationTurns * 6.2831853;
        float s = sin(a), c = cos(a);
        
        // Центр вращения (оригинальный центр элемента)
        float2 center = pos + size * 0.5;
        
        // Смещаем координату в 0 относительно центра
        float2 p = finalPos - center;
        
        // Корректируем aspect ratio экрана, чтобы квадрат оставался квадратом при повороте
        p.x *= ScreenRes.x / ScreenRes.y;
        
        // Вращаем 2D вектор
        float2 rotated;
        rotated.x = p.x * c - p.y * s;
        rotated.y = p.x * s + p.y * c;
        
        // Возвращаем aspect ratio обратно
        rotated.x *= ScreenRes.y / ScreenRes.x;
        
        finalPos = center + rotated;
    }
    output.position = float4(finalPos * 2.0 - 1.0, 0.5, 1.0);
}
#endif

// --- PIXEL SHADER v3.3 (Smart Blur) ---

#ifdef PIXEL_SHADER

float Random(float2 uv)
{
    return frac(sin(dot(uv, float2(12.9898, 78.233))) * 43758.5453);
}

float2 GetRandomNoise(float2 uv, float seed) {
    float n1 = Random(uv + float2(seed, seed));
    float n2 = Random(uv - float2(seed, seed) + 0.15);
    return float2(n1, n2) - 0.5; 
}

float4 main(VertexOutput input) : SV_Target0 {
    // 1. Clipping
    if (input.clipRect.z > 0) {
        float2 cMin = float2(input.clipRect.x, ScreenRes.y - input.clipRect.y - input.clipRect.w);
        float2 cMax = cMin + input.clipRect.zw;
        if (any(input.position.xy < cMin) || any(input.position.xy > cMax)) discard;
    }

    // 2. Procedural Modes
    if (input.drawMode == MODE_HSV) return float4(HsvToRgb(float3(input.extraData.x, input.contentUV.x, 1-input.contentUV.y)), input.color.a);
    if (input.drawMode == MODE_CURSOR) return length(input.contentUV * 2.0 - 1.0) > 1.0 ? 0 : input.color;
    if (input.drawMode == MODE_GRADIENT) return float4(HsvToRgb(float3(input.contentUV.x, 1, 1)), input.color.a);

    // UNIFIED SAMPLING
    float4 rawTexture = float4(1, 1, 1, 1);
    
    bool isBlurBg = (input.drawMode >= MODE_BLUR_BG_START && input.drawMode <= 99);
    bool insideBounds = (input.contentUV.x >= 0.0 && input.contentUV.x <= 1.0 && 
                         input.contentUV.y >= 0.0 && input.contentUV.y <= 1.0);

    if (!insideBounds && !isBlurBg) {
        rawTexture = float4(0, 0, 0, 0); 
    } 
    else if (input.drawMode != MODE_SOLID && !isBlurBg) {
        if (input.drawMode == MODE_TEXT || input.drawMode == MODE_NUMBER) {
            float2 uv = input.atlasRect.xy + input.contentUV * input.atlasRect.zw;
            uint fontSlot = (uint)input.extraData.y;
            if (fontSlot == 1) rawTexture = AtlasFont1.Sample(LinearSampler, uv);
            else if (fontSlot == 2) rawTexture = AtlasFont2.Sample(LinearSampler, uv);
            else if (fontSlot == 3) rawTexture = AtlasFont3.Sample(LinearSampler, uv);
            else rawTexture = AtlasFont0.Sample(LinearSampler, uv);
        } else {
            float2 finalUV = input.contentUV;
            
            // Надежное извлечение режима зеркалирования (спасает от потери точности)
            int mMode = (int)round(input.mirrorMode); 
            
            if (mMode == 1 || mMode == 3) finalUV.x = 1.0 - finalUV.x;
            if (mMode == 2 || mMode == 3) finalUV.y = 1.0 - finalUV.y;
            
            // Используем новое имя переменной (uvSample), чтобы не было конфликтов
            float2 uvSample = input.atlasRect.xy + finalUV * input.atlasRect.zw;
            rawTexture = AtlasIcons.Sample(LinearSampler, float2(uvSample.x, 1.0 - uvSample.y));
        }
    }

    uint styleFlags = 0;
    int baseIdx = -1;
    if (input.styleId >= 0) {
        baseIdx = (int)input.styleId * 12;
        styleFlags = asuint(ResourceStyleBuffer[baseIdx + 0].x);

    }

    // 3. Shadow Layer
    float4 shadowLayer = float4(0,0,0,0);
    if ((styleFlags & BIT_SHADOW) && input.drawMode != MODE_MASKED_BLUR && !isBlurBg) {
        if (rawTexture.a > 0.0) {
            float4 shadowColor = ResourceStyleBuffer[baseIdx + 2];
            shadowLayer = float4(shadowColor.rgb, rawTexture.a * shadowColor.a * input.color.a);
        }
    }

    // 4. Object Logic
    float4 objectLayer = float4(0,0,0,0);

    if (insideBounds || isBlurBg) {
        
        // --- SMART BLUR LOGIC ---
        if (input.drawMode == MODE_MASKED_BLUR || isBlurBg || (styleFlags & BIT_BLUR)) {
            
            float targetStrength = 0.0;
            float layerOpacity = 0.0;
            
            if (isBlurBg) {
                targetStrength = 0.5 + (float)(input.drawMode - 90) * 0.6;
                layerOpacity = input.color.a;
            }
            else if (input.drawMode == MODE_MASKED_BLUR) {
                float maskVal = rawTexture.r; 
                targetStrength = maskVal * 8.25; 
                layerOpacity = maskVal; 
            }
            else if (styleFlags & BIT_BLUR) {
                float strength = ResourceStyleBuffer[baseIdx + 10].w;
                float maskVal = (styleFlags & BIT_BLUR_MASK) ? rawTexture.r : 1.0;
                targetStrength = strength * maskVal;
                layerOpacity = maskVal * input.color.a;
            }

            if (layerOpacity > 0.001) {
                float3 blurredColor = float3(0,0,0);
                float2 uv = input.position.xy / ScreenRes;
                float correctedOpacity = 1.0 - pow(max(0.0, 1.0 - layerOpacity), 4.0);
                float3 boost = 1.0 + (1.0 - correctedOpacity) * 0.2; 
                float4 sampleColor = TexBackbuffer.Sample(LinearSampler, uv);
                blurredColor = sampleColor.rgb * boost;
                objectLayer = float4(blurredColor, correctedOpacity);
            }
        }
        else if (input.drawMode == MODE_COLOR_REPLACE) {
            float maxC = max(rawTexture.r, max(rawTexture.g, rawTexture.b));
            float minC = min(rawTexture.r, min(rawTexture.g, rawTexture.b));
            float texSat = maxC - minC; 
            float texLuma = dot(rawTexture.rgb, float3(0.299, 0.587, 0.114));
            float inputLuma = dot(input.color.rgb, float3(0.299, 0.587, 0.114));
            float3 retargetedColor = input.color.rgb * (texLuma / max(0.01, inputLuma));
            float mixFactor = saturate(texSat * 10.0);
            float3 finalRGB = lerp(rawTexture.rgb, retargetedColor, mixFactor);
            objectLayer = float4(finalRGB, rawTexture.a * input.color.a);
        }
        else if (input.drawMode == MODE_SOLID) {
            objectLayer = input.color;
        }
        else if (input.drawMode == MODE_TEX_MULTIPLY) { 
            objectLayer = rawTexture * input.color;
        }
        else if (input.drawMode == MODE_TEX_OVERLAY) { 
            objectLayer = rawTexture;
        }
        else { // Text/Number
            objectLayer = float4(input.color.rgb, rawTexture.r * input.color.a); 
        }

        if ((styleFlags & BIT_GRAYSCALE) && !isBlurBg && input.drawMode != MODE_MASKED_BLUR) {
            float amount = ResourceStyleBuffer[baseIdx + 7].x;
            float g = dot(objectLayer.rgb, float3(0.3, 0.59, 0.11));
            objectLayer.rgb = lerp(objectLayer.rgb, float3(g,g,g), amount);
        }
        
        if ((styleFlags & BIT_GRADIENT) && !isBlurBg && input.drawMode != MODE_MASKED_BLUR && objectLayer.a > 0.0) {
            float4 grad1 = ResourceStyleBuffer[baseIdx + 8];
            float4 grad2 = ResourceStyleBuffer[baseIdx + 9];
            float angle = ResourceStyleBuffer[baseIdx + 7].z * (3.14159 / 180.0);
            float2 dir = float2(cos(angle), sin(angle));
            float t = saturate(dot(input.contentUV - 0.5, dir) + 0.5);
            float4 gCol = lerp(grad1, grad2, t);
            objectLayer.rgb = lerp(objectLayer.rgb, gCol.rgb, gCol.a);
        }
    }

    // 5. Outline Effect
    if ((styleFlags & BIT_OUTLINE) && !isBlurBg && input.drawMode != MODE_MASKED_BLUR) {
         float thickness = ResourceStyleBuffer[baseIdx + 5].x;
         if (thickness <= 0.0) thickness = 1.0;
         float4 outlineCol = ResourceStyleBuffer[baseIdx + 6];
         float2 px = thickness / (input.objectRect.zw * ScreenRes);
         float2 uvBase = input.atlasRect.xy; 
         float2 uvSz = input.atlasRect.zw;
         float a = 0;
         float2 offs[4] = { float2(px.x,0), float2(-px.x,0), float2(0,px.y), float2(0,-px.y) };
         
         int mMode = (int)round(input.mirrorMode);

         [unroll]
         for(int k=0; k<4; k++) {
             float2 cUV = input.contentUV + offs[k];
             if(cUV.x>0 && cUV.x<1 && cUV.y>0 && cUV.y<1) {
                 
                 // ПРИМЕНЯЕМ ЗЕРКАЛИРОВАНИЕ ДЛЯ ОБВОДКИ
                 float2 outlineUV = cUV;
                 if (input.drawMode != MODE_TEXT && input.drawMode != MODE_NUMBER) {
                     if (mMode == 1 || mMode == 3) outlineUV.x = 1.0 - outlineUV.x;
                     if (mMode == 2 || mMode == 3) outlineUV.y = 1.0 - outlineUV.y;
                 }

                 float2 fUV = uvBase + outlineUV * uvSz;
                 
                 if(input.drawMode == MODE_TEXT || input.drawMode == MODE_NUMBER) {
                     uint fontSlot = (uint)input.extraData.y;
                     if (fontSlot == 1) a += AtlasFont1.Sample(LinearSampler, fUV).r;
                     else if (fontSlot == 2) a += AtlasFont2.Sample(LinearSampler, fUV).r;
                     else if (fontSlot == 3) a += AtlasFont3.Sample(LinearSampler, fUV).r;
                     else a += AtlasFont0.Sample(LinearSampler, fUV).r;
                 }
                 else 
                     a += AtlasIcons.Sample(LinearSampler, float2(fUV.x, 1.0-fUV.y)).a;
             }
         }
         if (a > 0.0 && objectLayer.a < 0.9) objectLayer = float4(outlineCol.rgb, outlineCol.a);
    }

    // 6. HIGHLIGHT EFFECTS
    if (objectLayer.a > 0.01) 
    {
        if ((styleFlags & BIT_ANIM_SHEEN)) {
            float speed = ResourceStyleBuffer[baseIdx + 10].x;
            if (speed == 0.0) speed = 1.0;
            float sheenWidth = ResourceStyleBuffer[baseIdx + 10].y;
            if (sheenWidth == 0.0) sheenWidth = 0.2;
            float4 sheenCol = ResourceStyleBuffer[baseIdx + 11];

            float val = (input.contentUV.x + input.contentUV.y * 0.5) * 2.0; 
            float sheenPos = frac(val - GlobalTime * speed * 0.5);
            float sheen = smoothstep(0.5 - sheenWidth, 0.5, sheenPos) * (1.0 - smoothstep(0.5, 0.5 + sheenWidth, sheenPos));
            sheen = pow(sheen, 3.0); 
            objectLayer.rgb += sheenCol.rgb * sheen * sheenCol.a * objectLayer.a;
        }
    }

    // 7. Final Blend
    float4 finalColor;
    finalColor.a = objectLayer.a + shadowLayer.a * (1.0 - objectLayer.a);
    if (finalColor.a > 0.0) {
        finalColor.rgb = (objectLayer.rgb * objectLayer.a + shadowLayer.rgb * shadowLayer.a * (1.0 - objectLayer.a)) / finalColor.a;
    } else {
        finalColor = float4(0, 0, 0, 0);
    }

    if (finalColor.a < 0.01) discard;
    return finalColor;
}
#endif