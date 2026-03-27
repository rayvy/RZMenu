/* 
================================================================================
SHADER: UI COMPOSITOR v3.3 (AUTO-FIT TEXT ADDED)
================================================================================
*/

// --- RESOURCES ---
Texture1D<float4> GlobalParams : register(t120);
Buffer<float4>    PosSizeBuffer : register(t100);
Buffer<float4>    ColorBuffer : register(t101);
Buffer<float4>    TileDataBuffer : register(t102); 
Buffer<uint>      TextPoolBuffer : register(t103);
Buffer<float4>    MirrorBuffer : register(t105);
Buffer<float4>    ClippingBuffer : register(t109);
Buffer<float4>    DrawParamsBuffer : register(t110);

Texture2D<float4> AtlasIcons : register(t80);
Texture2D<float4> AtlasFont : register(t82);
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

// --- FX CONSTANTS ---
static const int FX_OUTLINE = 1;
static const int FX_DROP_SHADOW = 2;
static const int FX_HOVER_SHEEN = 3; 
static const int FX_HOVER_RESIZE = 4;
static const int FX_GRAYSCALE = 5;
static const int FX_HOVER_SHINE = 8; 

static const uint MAX_CHARS = 32;
static const uint FONT_GRID_SIZE = 16;
static const float EXPAND_PX = 30.0; 

// --- UTILS ---

float3 HsvToRgb(float3 c) {
    float4 K = float4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    float3 p = abs(frac(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * lerp(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
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
    float  fxType : TEXCOORD7;
    float4 extraData : TEXCOORD8; 
    float    mirrorMode : TEXCOORD9;
};

struct CharMetrics {
    float advance; float glyphW; float glyphH; float offX; float offY;
};

CharMetrics FetchCharMetrics(uint c) {
    CharMetrics m = (CharMetrics)0;
    if (c < 32 || c >= 127) c = 32;
    uint w, h; AtlasFont.GetDimensions(w, h);
    float cs = (float)(w / FONT_GRID_SIZE);
    uint idx = c - 32;
    uint metaH = h / (uint)cs - 6; 
    uint metaY = (h / (uint)cs - metaH) * (uint)cs;
    float4 d1 = AtlasFont.Load(int3(idx % w, metaY + (idx/w)*2, 0));
    float4 d2 = AtlasFont.Load(int3(idx % w, metaY + (idx/w)*2 + 1, 0));
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

float4 ComputeLayout(int mode, uint vID, float4 tile, inout float2 pos, inout float2 size) {
    if (mode == MODE_TEXT || mode == MODE_NUMBER) {
        uint chars[MAX_CHARS]; uint count = 0;
        if (mode == MODE_TEXT) {
            uint off = (uint)tile.x; count = min((uint)tile.y, MAX_CHARS);
            for(uint i=0; i<count; ++i) chars[i] = TextPoolBuffer[off+i];
        } else ParseNumber(tile.x, clamp((int)tile.y,0,9), chars, count);

        uint w, h; AtlasFont.GetDimensions(w, h);
        float cs = (float)(w/16);
        float scale = (size.y * ScreenRes.y) / cs;
        
        float totalW = 0, firstOff = 0;
        if (count > 0) {
            firstOff = FetchCharMetrics(chars[0]).offX;
            for(uint k=0; k<count-1; ++k) totalW += FetchCharMetrics(chars[k]).advance;
            CharMetrics last = FetchCharMetrics(chars[count-1]);
            totalW += last.offX + last.glyphW - firstOff;
        }

        // --- AUTO-FIT LOGIC (SQUISH) ---
        float inputLimitWidth = size.x * ScreenRes.x; // Лимит ширины из $sizeX
        float currentTextWidth = totalW * scale;      // Реальная ширина текста
        float squeeze = 1.0;

        // Если задан лимит (> 1px) И текст шире лимита -> сжимаем
        if (inputLimitWidth > 1.0 && currentTextWidth > inputLimitWidth) {
            squeeze = inputLimitWidth / currentTextWidth;
        }
        // -------------------------------
        
        float shift = 0;
        int align = (int)tile.z;
        if (align == 1) shift = (firstOff*2.0 + totalW)*0.5;
        if (align == 2) shift = firstOff + totalW;
        
        float2 basePos = pos;
        // Применяем squeeze к сдвигу выравнивания
        basePos.x -= (shift / ScreenRes.x) * scale * squeeze;
        
        uint idx = vID / 6;
        uint code = (idx < count) ? chars[idx] : ' ';
        
        float curX = 0;
        for(uint i=0; i<idx; ++i) curX += FetchCharMetrics(chars[i]).advance;
        CharMetrics m = FetchCharMetrics(code);
        CharMetrics ref = FetchCharMetrics('A');
        
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

float2 ApplyAnimation(float type, float2 pos, float2 size, float2 uv) {
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
    if (type == ANIM_ROTATE) {
        float a = 6.28 * GlobalTime;
        float s = sin(a), c = cos(a);
        return center + mul(float2x2(c, -s, s, c), local) * size;
    }
    return pos + uv * size;
}

#ifdef VERTEX_SHADER
void main(uint vID : SV_VertexID, uint iID : SV_InstanceID, out VertexOutput output) {
    output = (VertexOutput)0;
    float4 params = DrawParamsBuffer[iID];
    output.drawMode = (int)params.w;
    output.animType = params.x;
    output.fxType = params.y;
    output.color = ColorBuffer[iID];
    output.clipRect = ClippingBuffer[iID];
    output.extraData.x = TileDataBuffer[iID].x;
    output.mirrorMode = (int)MirrorBuffer[iID].x;

    float2 pos = PosSizeBuffer[iID].xy;
    float2 size = PosSizeBuffer[iID].zw;

    if (output.drawMode != MODE_TEXT && output.drawMode != MODE_NUMBER && vID >= 6) { output.position = 0; return; }
    if ((output.drawMode == MODE_TEXT || output.drawMode == MODE_NUMBER) && (vID/6) >= MAX_CHARS) { output.position = 0; return; }

    if (output.fxType == FX_HOVER_RESIZE) {
        float2 c = pos + size * 0.5;
        float2 d = CursorPos - c; d.x *= ScreenRes.x/ScreenRes.y;
        float prox = 1.0 - pow(1.0 - saturate(1.0 - length(d)/0.008), 2);
        float s = 1.0 + (0.125 * prox);
        pos = c - size*s*0.5; size *= s;
    }
    output.objectRect = float4(pos, size);

    float2 quadUv;
    uint lID = vID % 6;
    if (lID == 0 || lID == 3) quadUv = float2(0,0);
    else if (lID == 1 || lID == 5) quadUv = float2(1,1);
    else if (lID == 2) quadUv = float2(0,1);
    else quadUv = float2(1,0);

    output.atlasRect = ComputeLayout(output.drawMode, vID, TileDataBuffer[iID], pos, size);

    bool allowExpand = (output.drawMode < MODE_BLUR_BG_START && output.drawMode != MODE_MASKED_BLUR);
    float2 expandVec = allowExpand ? (EXPAND_PX / ScreenRes) : float2(0,0);
    
    float2 expandedPos = pos - expandVec;
    float2 expandedSize = size + expandVec * 2.0;

    output.contentUV = (quadUv * expandedSize - expandVec) / size;

    if (output.drawMode == MODE_TEXT || output.drawMode == MODE_NUMBER) {
        output.contentUV.y = 1.0 - output.contentUV.y;
    }

    float2 finalPos = ApplyAnimation(output.animType, expandedPos, expandedSize, quadUv);
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
            rawTexture = AtlasFont.Sample(LinearSampler, uv);
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

    // 3. Shadow Layer
    float4 shadowLayer = float4(0,0,0,0);
    if (input.fxType == FX_DROP_SHADOW && input.drawMode != MODE_MASKED_BLUR && !isBlurBg) {
        if (rawTexture.a > 0.0) {
            shadowLayer = float4(0, 0, 0, rawTexture.a * 0.5 * input.color.a);
        }
    }

    // 4. Object Logic
    float4 objectLayer = float4(0,0,0,0);

    if (insideBounds || isBlurBg) {
        
        // --- SMART BLUR LOGIC ---
        if (input.drawMode == MODE_MASKED_BLUR || isBlurBg) {
            
            float targetStrength = 0.0;
            float layerOpacity = 0.0;
            
            if (input.drawMode == MODE_MASKED_BLUR) {
                float maskVal = rawTexture.r; 
                targetStrength = maskVal * 8.25; 
                layerOpacity = maskVal; 
            } 
            else {
                targetStrength = 0.5 + (float)(input.drawMode - 90) * 0.6;
                layerOpacity = input.color.a;
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

        if (input.fxType == FX_GRAYSCALE && !isBlurBg && input.drawMode != MODE_MASKED_BLUR) {
            float g = dot(objectLayer.rgb, float3(0.3, 0.59, 0.11));
            objectLayer.rgb = float3(g,g,g);
        }
    }

    // 5. Outline Effect
    if (input.fxType == FX_OUTLINE && !isBlurBg && input.drawMode != MODE_MASKED_BLUR) {
         float2 px = 1.0 / (input.objectRect.zw * ScreenRes);
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
                 
                 if(input.drawMode == MODE_TEXT || input.drawMode == MODE_NUMBER) 
                     a += AtlasFont.Sample(LinearSampler, fUV).r;
                 else 
                     a += AtlasIcons.Sample(LinearSampler, float2(fUV.x, 1.0-fUV.y)).a;
             }
         }
         if (a > 0.0 && objectLayer.a < 0.9) objectLayer = float4(0,0,0,1);
    }

    // 6. HIGHLIGHT EFFECTS
    if (objectLayer.a > 0.01) 
    {
        if (input.fxType == FX_HOVER_SHEEN) {
            float speed = 2.5;
            float val = (input.contentUV.x + input.contentUV.y * 0.5) * 2.0; 
            float sheenPos = frac(val - GlobalTime * speed * 0.5);
            float sheen = smoothstep(0.4, 0.5, sheenPos) * (1.0 - smoothstep(0.5, 0.6, sheenPos));
            sheen = pow(sheen, 3.0); 
            objectLayer.rgb += float3(1.0, 1.0, 1.0) * sheen * 0.8 * objectLayer.a;
        }
        if (input.fxType == FX_HOVER_SHINE) {
            float2 object_pos = input.objectRect.xy;
            float2 object_size = input.objectRect.zw;
            float2 cursor_relative_to_object = (CursorPos - object_pos) / object_size;
            float2 shine_dir = normalize(float2(1.0, -1.0));
            float2 local_uv = input.contentUV - 0.5;
            float projection = dot(local_uv, shine_dir);
            float shine_pos = (cursor_relative_to_object.x - 0.5) * 1.2;
            const float stripe_width = 0.15;
            float intensity = pow(saturate(1.0 - abs(projection - shine_pos) / stripe_width), 3.0);
            objectLayer.rgb += float3(1.0, 1.0, 1.0) * intensity * 0.7 * objectLayer.a;
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