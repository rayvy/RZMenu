// system_draw.hlsl — System Overlay: cursor + input info panel
// draw = 3, 0  (fullscreen triangle)

Texture1D<float4> IniParams : register(t120);
Texture2D<float4> FontAtlas : register(t82);
Buffer<uint>      SlotHint  : register(t63); // Hint (S size)
Buffer<uint>      SlotHint2 : register(t64); // Hint 2 (RCtrl)
Buffer<float4>    DebugBuffer0 : register(t65);
Buffer<float4>    DebugBuffer1 : register(t66);
Buffer<float4>    DebugBuffer2 : register(t67);
Buffer<float4>    DebugBuffer3 : register(t68);
Buffer<uint>      Slot2     : register(t58); // Mode (ButtonMode / MouseMode) (L size)
SamplerState      Smp       : register(s0);

// --- Constants ---
static const uint  FONT_COLS  = 16;

// --- Structs ---
struct VSOut {
    float4 position : SV_Position;
    float2 uv       : TEXCOORD0;
};

struct CharMetrics {
    float advance; float glyphW; float glyphH; float offX; float offY;
};

// --- Signed Distance Field for Rounded Box ---
float sdRoundBox(float2 p, float2 size, float r) {
    float2 d = abs(p) - size + r;
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
}

// --- Cursor helper ---
bool InTri(float2 p, float2 a, float2 b, float2 c) {
    float d0 = (b.x-a.x)*(p.y-a.y) - (b.y-a.y)*(p.x-a.x);
    float d1 = (c.x-b.x)*(p.y-b.y) - (c.y-b.y)*(p.x-b.x);
    float d2 = (a.x-c.x)*(p.y-c.y) - (a.y-c.y)*(p.x-c.x);
    return !(((d0<0.0)||(d1<0.0)||(d2<0.0)) && ((d0>0.0)||(d1>0.0)||(d2>0.0)));
}

// --- Font Metrics Loader ---
CharMetrics FetchCharMetrics(uint c) {
    CharMetrics m = (CharMetrics)0;
    if (c < 32) c = 32;
    uint w = 0, h = 0;
    FontAtlas.GetDimensions(w, h);
    if (w == 0 || h == 0) return m;

    float cs = (float)(w / FONT_COLS);
    uint idx = c - 32;
    uint metaY = h - (uint)cs;

    int3 p1 = int3(idx % w, metaY + (idx/w)*2, 0);
    int3 p2 = int3(idx % w, metaY + (idx/w)*2 + 1, 0);

    float4 d1 = FontAtlas.Load(p1);
    float4 d2 = FontAtlas.Load(p2);

    m.advance = d1.r*2.0*cs;
    m.glyphW  = d1.g*2.0*cs;
    m.offX    = (d1.b*2.0-1.0)*cs;
    m.offY    = (d1.a*2.0-1.0)*cs;
    m.glyphH  = d2.r*2.0*cs;
    return m;
}

// --- Text Width Helpers ---
float GetTextWidth(Buffer<uint> buf, uint len, out float firstOff) {
    firstOff = 0.0;
    if (len == 0) return 0.0;

    firstOff = FetchCharMetrics(buf.Load(0)).offX;
    float totalW = 0.0;
    for (uint k = 0; k < len - 1; ++k) {
        totalW += FetchCharMetrics(buf.Load(k)).advance;
    }
    CharMetrics last = FetchCharMetrics(buf.Load(len - 1));
    totalW += last.offX + last.glyphW - firstOff;
    return totalW;
}

float GetDynamicTextWidth(uint chars[24], uint len, out float firstOff) {
    firstOff = 0.0;
    if (len == 0) return 0.0;

    firstOff = FetchCharMetrics(chars[0]).offX;
    float totalW = 0.0;
    for (uint k = 0; k < len - 1; ++k) {
        totalW += FetchCharMetrics(chars[k]).advance;
    }
    CharMetrics last = FetchCharMetrics(chars[len - 1]);
    totalW += last.offX + last.glyphW - firstOff;
    return totalW;
}

// -----------------------------------------------------------------------
// VERTEX SHADER
// -----------------------------------------------------------------------
#ifdef VERTEX_SHADER
void main(uint vID : SV_VertexID, out VSOut o) {
    float2 uv = (vID == 1) ? float2(2,0) : (vID == 2) ? float2(0,2) : float2(0,0);
    o.uv       = uv;
    o.position = float4(uv * 2.0 - 1.0, 0.0, 1.0);
}
#endif

// -----------------------------------------------------------------------
// PIXEL SHADER
// -----------------------------------------------------------------------
#ifdef PIXEL_SHADER
float4 main(VSOut input) : SV_Target {
    float2 ScreenRes = IniParams.Load(int2(99,0)).zw;
    if (ScreenRes.x <= 0.0 || ScreenRes.y <= 0.0) {
        ScreenRes = float2(1920.0, 1080.0);
    }
    float2 CursorPos = IniParams.Load(int2(99,0)).xy * ScreenRes;
    float  InputMode = IniParams.Load(int2(97,0)).x;
    float  IsCaptured = IniParams.Load(int2(97,0)).y;
    float  HoveredID = IniParams.Load(int2(97,0)).z;
    float  NavArrows = IniParams.Load(int2(97,0)).w;

    bool showGP = (InputMode > 0.5);
    float2 px = input.uv * ScreenRes;

    // ----------------------------------------------------------------
    // 1. CURSOR (Gamepad/Button mode only)
    // ----------------------------------------------------------------
    if (showGP) {
        float2 d = px - CursorPos;
        if (InTri(d, float2(0,0),      float2(0,-15),   float2(10,-10))    ||
            InTri(d, float2(2.5,-11.5), float2(4,-11.5), float2(8,-18.5))  ||
            InTri(d, float2(2.5,-11.5), float2(8,-18.5), float2(6.5,-18.5)))
            return float4(0,0,0,1);

        if (InTri(d, float2(-1.5,1.5),  float2(-1.5,-17.5), float2(12.5,-11.5)) ||
            InTri(d, float2(1.5,-10.5), float2(5,-10.5),    float2(9,-19.5))     ||
            InTri(d, float2(1.5,-10.5), float2(9,-19.5),    float2(5.5,-19.5)))
            return float4(1,1,1,1);
    }

    // ----------------------------------------------------------------
    // 2. PANEL DIMENSIONS & METRICS
    // ----------------------------------------------------------------
    uint atlasW, atlasH;
    FontAtlas.GetDimensions(atlasW, atlasH);
    float cs = (float)(atlasW / FONT_COLS);
    float rows = (float)(atlasH) / cs;
    float2 uvCell = 1.0 / float2((float)FONT_COLS, rows);

    // Font Scales (L, M, S) using absolute pixel heights for stability
    float scale_L = 32.0 / cs; // Mode text (32px)
    float scale_M = 20.0 / cs; // Hint text / Coordinates (20px)
    float scale_S = 16.0 / cs; // Unused (16px)

    // Panel layout definitions (Bottom-right aligned, Y increases upwards)
    float PANEL_W = 350.0;
    float PANEL_H = 150.0;
    float2 panel_min = float2(ScreenRes.x - 20.0 - PANEL_W, 20.0);
    float2 panel_max = float2(ScreenRes.x - 20.0, 20.0 + PANEL_H);

    // D-pad center
    float2 ac = float2(panel_min.x + 45.0, panel_min.y + 75.0);

    // Text positions
    float mode_x = panel_min.x + 95.0;
    float mode_y = panel_min.y + 98.0;

    float hint_x = panel_min.x + 95.0;
    float hint_y = panel_min.y + 72.0;
    float hint2_y = panel_min.y + 48.0;

    float sep_y = panel_min.y + 36.0;

    float coord_x = panel_min.x + 95.0;
    float coord_y = panel_min.y + 6.0;

    // Buffer dimensions
    uint len_mode = 0; Slot2.GetDimensions(len_mode);
    uint len_hint = 0; SlotHint.GetDimensions(len_hint);
    uint len_hint2 = 0; SlotHint2.GetDimensions(len_hint2);

    // ----------------------------------------------------------------
    // 3. TEXT RENDERING PASS (Highest Priority)
    // ----------------------------------------------------------------

    #define DRAW_TEXT_LINE(buf, len, x_start, y_start, scale_val, txtCol) \
    { \
        float firstOff = 0.0; \
        float width_val = GetTextWidth(buf, len, firstOff) * scale_val; \
        float2 rel = px - float2(x_start, y_start); \
        CharMetrics refChar = FetchCharMetrics(65); \
        float H_ref = refChar.offY + refChar.glyphH + 17.06667; \
        float localY = H_ref - (rel.y / scale_val); \
        if (localY >= 0.0 && localY < cs) { \
            float text_x = rel.x / scale_val + firstOff; \
            float accum_x = 0.0; \
            for (uint ci = 0; ci < len; ++ci) { \
                uint c = buf.Load(ci); \
                CharMetrics m = FetchCharMetrics(c); \
                float glyph_left = accum_x + m.offX; \
                float glyph_right = glyph_left + m.glyphW; \
                if (text_x >= glyph_left && text_x < glyph_right) { \
                    if (localY >= m.offY && localY < (m.offY + m.glyphH)) { \
                        float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS); \
                        float2 uvBase = cellUV * uvCell; \
                        float2 localUV = float2( \
                            m.offX + (text_x - glyph_left), \
                            localY \
                        ) / cs; \
                        float2 uv = uvBase + localUV * uvCell; \
                        float alpha = FontAtlas.SampleLevel(Smp, uv, 0).r; \
                        if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a); \
                    } \
                } \
                accum_x += m.advance; \
            } \
        } \
    }

    #define DRAW_DYNAMIC_TEXT(chars, len, x_start, y_start, scale_val, txtCol) \
    { \
        float firstOff = 0.0; \
        float width_val = GetDynamicTextWidth(chars, len, firstOff) * scale_val; \
        float2 rel = px - float2(x_start, y_start); \
        CharMetrics refChar = FetchCharMetrics(65); \
        float H_ref = refChar.offY + refChar.glyphH + 17.06667; \
        float localY = H_ref - (rel.y / scale_val); \
        if (localY >= 0.0 && localY < cs) { \
            float text_x = rel.x / scale_val + firstOff; \
            float accum_x = 0.0; \
            for (uint ci = 0; ci < len; ++ci) { \
                uint c = chars[ci]; \
                CharMetrics m = FetchCharMetrics(c); \
                float glyph_left = accum_x + m.offX; \
                float glyph_right = glyph_left + m.glyphW; \
                if (text_x >= glyph_left && text_x < glyph_right) { \
                    if (localY >= m.offY && localY < (m.offY + m.glyphH)) { \
                        float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS); \
                        float2 uvBase = cellUV * uvCell; \
                        float2 localUV = float2( \
                            m.offX + (text_x - glyph_left), \
                            localY \
                        ) / cs; \
                        float2 uv = uvBase + localUV * uvCell; \
                        float alpha = FontAtlas.SampleLevel(Smp, uv, 0).r; \
                        if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a); \
                    } \
                } \
                accum_x += m.advance; \
            } \
        } \
    }

    // A. Mode Text (ButtonMode / MouseMode) - Solid Bright White
    DRAW_TEXT_LINE(Slot2, len_mode, mode_x, mode_y, scale_L, float4(1.0, 1.0, 1.0, 1.0))

    // B. Switch Mode Hint ("RShift - switch mode") - Solid Amber/Gold, No Transparency
    DRAW_TEXT_LINE(SlotHint, len_hint, hint_x, hint_y, scale_M, float4(1.0, 0.8, 0.2, 1.0))

    // B2. Capture Element Hint ("RCtrl - capture element") - Solid Amber/Gold, No Transparency
    DRAW_TEXT_LINE(SlotHint2, len_hint2, hint_x, hint2_y, scale_M, float4(1.0, 0.8, 0.2, 1.0))

    // C. Coordinates Text ("x [cx]   y [cy]")
    uint coord_chars[24];
    uint coord_len = 0;
    coord_chars[coord_len++] = 120; // 'x'
    coord_chars[coord_len++] = 32;  // ' '

    int tempX = (int)CursorPos.x;
    if (tempX < 0) tempX = 0;
    int dX4 = (tempX / 10000) % 10;
    int dX3 = (tempX / 1000) % 10;
    int dX2 = (tempX / 100) % 10;
    int dX1 = (tempX / 10) % 10;
    int dX0 = tempX % 10;

    bool started = false;
    if (dX4 > 0) { coord_chars[coord_len++] = 48 + dX4; started = true; }
    if (dX3 > 0 || started) { coord_chars[coord_len++] = 48 + dX3; started = true; }
    if (dX2 > 0 || started) { coord_chars[coord_len++] = 48 + dX2; started = true; }
    if (dX1 > 0 || started) { coord_chars[coord_len++] = 48 + dX1; started = true; }
    coord_chars[coord_len++] = 48 + dX0;

    coord_chars[coord_len++] = 32;  // ' '
    coord_chars[coord_len++] = 32;  // ' '
    coord_chars[coord_len++] = 32;  // ' '
    coord_chars[coord_len++] = 121; // 'y'
    coord_chars[coord_len++] = 32;  // ' '

    int tempY = (int)CursorPos.y;
    if (tempY < 0) tempY = 0;
    int dY4 = (tempY / 10000) % 10;
    int dY3 = (tempY / 1000) % 10;
    int dY2 = (tempY / 100) % 10;
    int dY1 = (tempY / 10) % 10;
    int dY0 = tempY % 10;

    started = false;
    if (dY4 > 0) { coord_chars[coord_len++] = 48 + dY4; started = true; }
    if (dY3 > 0 || started) { coord_chars[coord_len++] = 48 + dY3; started = true; }
    if (dY2 > 0 || started) { coord_chars[coord_len++] = 48 + dY2; started = true; }
    if (dY1 > 0 || started) { coord_chars[coord_len++] = 48 + dY1; started = true; }
    coord_chars[coord_len++] = 48 + dY0;

    DRAW_DYNAMIC_TEXT(coord_chars, coord_len, coord_x, coord_y, scale_M, float4(0.7, 0.7, 0.7, 1.0))
    
    // ----------------------------------------------------------------
    // 4. GRAPHICS / INTERACTION ELEMENTS RENDERING PASS
    // ----------------------------------------------------------------

    // A. Status Block Controls (D-pad Arrows - Large & Spaced Out)
    int bits = (int)(NavArrows + 0.5);
    bool pressUp    = (bits & 1) != 0;
    bool pressDown  = (bits & 2) != 0;
    bool pressLeft  = (bits & 4) != 0;
    bool pressRight = (bits & 8) != 0;

    // Up Arrow
    if (InTri(px - ac, float2(0, 30.0), float2(-12.0, 17.0), float2(12.0, 17.0))) {
        return pressUp ? float4(0.3, 0.75, 1.0, 1.0) : float4(0.4, 0.4, 0.43, 1.0);
    }
    // Down Arrow
    if (InTri(px - ac, float2(0, -30.0), float2(-12.0, -17.0), float2(12.0, -17.0))) {
        return pressDown ? float4(0.3, 0.75, 1.0, 1.0) : float4(0.4, 0.4, 0.43, 1.0);
    }
    // Left Arrow
    if (InTri(px - ac, float2(-30.0, 0), float2(-17.0, -12.0), float2(-17.0, 12.0))) {
        return pressLeft ? float4(0.3, 0.75, 1.0, 1.0) : float4(0.4, 0.4, 0.43, 1.0);
    }
    // Right Arrow
    if (InTri(px - ac, float2(30.0, 0), float2(17.0, -12.0), float2(17.0, 12.0))) {
        return pressRight ? float4(0.3, 0.75, 1.0, 1.0) : float4(0.4, 0.4, 0.43, 1.0);
    }

    // Capture indicator dot inside the D-pad center
    float dist_circle = length(px - ac);
    if (dist_circle <= 8.0) {
        return (IsCaptured > 0.5) ? float4(0.95, 0.2, 0.2, 1.0) : float4(0.2, 0.6, 1.0, 1.0); // Red (captured) / Blue (active/idle)
    }
    if (dist_circle <= 9.0 && dist_circle > 8.0) {
        return float4(0.0, 0.0, 0.0, 0.9); // sharp border ring
    }

    // ----------------------------------------------------------------
    // 5. BACKDROP PANELS & LINES RENDERING PASS
    // ----------------------------------------------------------------
    
    // Separator line under the text
    if (px.x >= panel_min.x + 95.0 && px.x <= panel_max.x - 15.0 && abs(px.y - sep_y) <= 0.8) {
        return float4(0.25, 0.25, 0.28, 0.8);
    }

    // Panel backdrop using rounded box SDF with a sleek border (No red/garbage borders)
    float2 panel_center = (panel_min + panel_max) * 0.5;
    float2 panel_half_size = (panel_max - panel_min) * 0.5;
    float corner_radius = 10.0;
    float border_t = 1.0;
    float dist = sdRoundBox(px - panel_center, panel_half_size, corner_radius);
    
    if (dist <= 0.0) {
        if (dist >= -border_t) {
            return float4(0.2, 0.2, 0.22, 0.9); // sleek dark-grey border
        }
        return float4(0.01, 0.01, 0.015, 0.92); // very dark, elegant solid backdrop
    }

    discard;
    return float4(0,0,0,0);
}
#endif
