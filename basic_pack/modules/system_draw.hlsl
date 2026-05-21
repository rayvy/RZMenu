// system_draw.hlsl — System Overlay: cursor + advanced status/notification slots
// draw = 3, 0  (fullscreen triangle)

Texture1D<float4> IniParams : register(t120);
Texture2D<float4> FontAtlas : register(t82);
Buffer<uint>      SlotTitle : register(t56); // CharacterName + OutfitName (L size)
Buffer<uint>      SlotAuthor: register(t57); // AuthorName (M size)
Buffer<uint>      SlotBy    : register(t62); // "by " (S size)
Buffer<uint>      SlotPowered : register(t63); // "powered RZMenu 4.0.2" (S size)
Buffer<uint>      Slot2     : register(t58); // Mode (ButtonMode / MouseMode) (M size)
Buffer<uint>      Slot3     : register(t59); // Notice 0
Buffer<uint>      Slot4     : register(t60); // Notice 1
Buffer<uint>      Slot5     : register(t61); // Notice 2
SamplerState      Smp       : register(s0);

// --- Constants ---
static const uint  FONT_COLS  = 16;
static const float  BG_PAD    = 5.0;

// --- Structs ---
struct VSOut {
    float4 position : SV_Position;
    float2 uv       : TEXCOORD0;
};

struct CharMetrics {
    float advance; float glyphW; float glyphH; float offX; float offY;
};

// --- Cursor helper ---
bool InTri(float2 p, float2 a, float2 b, float2 c) {
    float d0 = (b.x-a.x)*(p.y-a.y) - (b.y-a.y)*(p.x-a.x);
    float d1 = (c.x-b.x)*(p.y-b.y) - (c.y-b.y)*(p.x-b.x);
    float d2 = (a.x-c.x)*(p.y-c.y) - (a.y-c.y)*(p.x-c.x);
    return !(((d0<0)||(d1<0)||(d2<0)) && ((d0>0)||(d1>0)||(d2>0)));
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

// --- Text Width Helper ---
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
    float  IsGamepadEditing = IniParams.Load(int2(97,0)).y;
    float  HoveredID = IniParams.Load(int2(97,0)).z;
    float  NavArrows = IniParams.Load(int2(97,0)).w;
    float  Time = IniParams.Load(int2(98,0)).x;

    float  Notice0Time = IniParams.Load(int2(96,0)).x;
    float  Notice1Time = IniParams.Load(int2(96,0)).y;
    float  Notice2Time = IniParams.Load(int2(96,0)).z;

    bool showGP = (InputMode > 0.5);
    float2 px = input.uv * ScreenRes;

    // ----------------------------------------------------------------
    // 1. CURSOR (Gamepad mode only)
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
    // 2. METRICS & SCALING (Screen height proportional)
    // ----------------------------------------------------------------
    uint atlasW, atlasH;
    FontAtlas.GetDimensions(atlasW, atlasH);
    float cs = (float)(atlasW / FONT_COLS);
    float rows = (float)(atlasH) / cs;
    float2 uvCell = 1.0 / float2((float)FONT_COLS, rows);

    // Font Sizes (L, M, S)
    float H_L = 0.020 * ScreenRes.y;
    float H_M = 0.016 * ScreenRes.y;
    float H_S = 0.012 * ScreenRes.y;

    float scale_L = H_L / cs;
    float scale_M = H_M / cs;
    float scale_S = H_S / cs;

    float right_edge = ScreenRes.x - 20.0;

    // Length of main block slots
    uint len_title = 0; SlotTitle.GetDimensions(len_title);
    uint len_author = 0; SlotAuthor.GetDimensions(len_author);
    uint len_by = 0; SlotBy.GetDimensions(len_by);
    uint len_powered = 0; SlotPowered.GetDimensions(len_powered);
    uint len_mode = 0; Slot2.GetDimensions(len_mode);

    // Calculate horizontal offsets for main block
    float firstOff_title = 0.0;
    float width_title = GetTextWidth(SlotTitle, len_title, firstOff_title) * scale_L;
    float left_L = right_edge - width_title;

    float firstOff_powered = 0.0;
    float width_powered = GetTextWidth(SlotPowered, len_powered, firstOff_powered) * scale_S;
    float left_powered = right_edge - width_powered;

    float firstOff_author = 0.0;
    float width_author = GetTextWidth(SlotAuthor, len_author, firstOff_author) * scale_M;
    float left_author = left_powered - 8.0 - width_author;

    float firstOff_by = 0.0;
    float width_by = GetTextWidth(SlotBy, len_by, firstOff_by) * scale_S;
    float left_by = left_author - 4.0 - width_by;

    float main_left = min(left_L, left_by);

    // ----------------------------------------------------------------
    // 3. TEXT RENDERING PASS (Highest Priority)
    // ----------------------------------------------------------------

    // Macro for proportional text rendering
    #define DRAW_TEXT_LINE(buf, len, x_start, y_start, scale_val, txtCol, globalAlpha) \
    { \
        float firstOff = 0.0; \
        float width_val = GetTextWidth(buf, len, firstOff) * scale_val; \
        float2 rel = px - float2(x_start, y_start); \
        if (rel.y >= 0.0 && rel.y < (cs * scale_val)) { \
            float text_x = rel.x / scale_val + firstOff; \
            float accum_x = 0.0; \
            for (uint ci = 0; ci < len; ++ci) { \
                uint c = buf.Load(ci); \
                CharMetrics m = FetchCharMetrics(c); \
                float glyph_left = accum_x + m.offX; \
                float glyph_right = glyph_left + m.glyphW; \
                if (text_x >= glyph_left && text_x < glyph_right) { \
                    float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS); \
                    float2 uvBase = cellUV * uvCell; \
                    float2 localUV = float2( \
                        (m.offX + (text_x - glyph_left)), \
                        (m.offY + m.glyphH - (rel.y / scale_val)) \
                    ) / cs; \
                    float2 uv = uvBase + saturate(localUV) * uvCell; \
                    float alpha = FontAtlas.SampleLevel(Smp, uv, 0).r; \
                    if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a * globalAlpha); \
                } \
                accum_x += m.advance; \
            } \
        } \
    }

    // A. Main Block - Line 1 (SlotTitle)
    DRAW_TEXT_LINE(SlotTitle, len_title, left_L, 20.0 + H_S + 5.0, scale_L, float4(0.95, 0.95, 0.95, 1.0), 1.0)

    // B. Main Block - Line 2 (SlotBy + SlotAuthor + SlotPowered)
    DRAW_TEXT_LINE(SlotBy, len_by, left_by, 20.0, scale_S, float4(0.65, 0.65, 0.65, 1.0), 1.0)
    DRAW_TEXT_LINE(SlotAuthor, len_author, left_author, 20.0, scale_M, float4(0.3, 0.7, 1.0, 1.0), 1.0)
    DRAW_TEXT_LINE(SlotPowered, len_powered, left_powered, 20.0, scale_S, float4(1.0, 0.6, 0.1, 1.0), 1.0)

    // C. Status Block Mode Text
    float status_right = main_left - 15.0;
    float STATUS_W = 160.0;
    float status_left = status_right - STATUS_W;
    float status_y = 20.0 + (H_S + 5.0 + H_L) / 2.0 - H_M / 2.0;

    DRAW_TEXT_LINE(Slot2, len_mode, status_left + 65.0, status_y, scale_M, float4(0.85, 0.85, 0.85, 1.0), 1.0)

    // D. Notifications Text
    float BOX_W = 280.0;
    float BOX_H = 40.0;

    // Notice 0
    float age0 = Time - Notice0Time;
    if (Notice0Time > 0.0 && age0 >= 0.0 && age0 < 4.0) {
        float x_left = lerp(ScreenRes.x, ScreenRes.x - BOX_W - 20.0, saturate(age0 / 0.4) * saturate(age0 / 0.4) * (3.0 - 2.0 * saturate(age0 / 0.4)));
        float y_bottom = 20.0 + H_S + 5.0 + H_L + BG_PAD + 15.0 + 0.0 * (BOX_H + 10.0);
        uint len_n0 = 0; Slot3.GetDimensions(len_n0);
        DRAW_TEXT_LINE(Slot3, len_n0, x_left + 15.0, y_bottom + (BOX_H - H_S) / 2.0, scale_S, float4(0.95, 0.95, 0.95, 1.0), saturate((4.0 - age0) / 1.0))
    }

    // Notice 1
    float age1 = Time - Notice1Time;
    if (Notice1Time > 0.0 && age1 >= 0.0 && age1 < 4.0) {
        float x_left = lerp(ScreenRes.x, ScreenRes.x - BOX_W - 20.0, saturate(age1 / 0.4) * saturate(age1 / 0.4) * (3.0 - 2.0 * saturate(age1 / 0.4)));
        float y_bottom = 20.0 + H_S + 5.0 + H_L + BG_PAD + 15.0 + 1.0 * (BOX_H + 10.0);
        uint len_n1 = 0; Slot4.GetDimensions(len_n1);
        DRAW_TEXT_LINE(Slot4, len_n1, x_left + 15.0, y_bottom + (BOX_H - H_S) / 2.0, scale_S, float4(0.95, 0.95, 0.95, 1.0), saturate((4.0 - age1) / 1.0))
    }

    // Notice 2
    float age2 = Time - Notice2Time;
    if (Notice2Time > 0.0 && age2 >= 0.0 && age2 < 4.0) {
        float x_left = lerp(ScreenRes.x, ScreenRes.x - BOX_W - 20.0, saturate(age2 / 0.4) * saturate(age2 / 0.4) * (3.0 - 2.0 * saturate(age2 / 0.4)));
        float y_bottom = 20.0 + H_S + 5.0 + H_L + BG_PAD + 15.0 + 2.0 * (BOX_H + 10.0);
        uint len_n2 = 0; Slot5.GetDimensions(len_n2);
        DRAW_TEXT_LINE(Slot5, len_n2, x_left + 15.0, y_bottom + (BOX_H - H_S) / 2.0, scale_S, float4(0.95, 0.95, 0.95, 1.0), saturate((4.0 - age2) / 1.0))
    }

    // ----------------------------------------------------------------
    // 4. GRAPHICS / INTERACTION ELEMENTS RENDERING PASS
    // ----------------------------------------------------------------

    // A. Status Block Controls (D-pad + Capture circle)
    float2 ac = float2(status_left + 25.0, 20.0 + (H_S + 5.0 + H_L) / 2.0);
    int bits = (int)(NavArrows + 0.5);
    bool pressUp    = (bits & 1) != 0;
    bool pressDown  = (bits & 2) != 0;
    bool pressLeft  = (bits & 4) != 0;
    bool pressRight = (bits & 8) != 0;

    // Up Arrow
    if (InTri(px - ac, float2(0, 9), float2(-4.5, 4), float2(4.5, 4))) {
        return pressUp ? float4(1.0, 0.8, 0.2, 1.0) : float4(0.4, 0.4, 0.4, 1.0);
    }
    // Down Arrow
    if (InTri(px - ac, float2(0, -9), float2(-4.5, -4), float2(4.5, -4))) {
        return pressDown ? float4(1.0, 0.8, 0.2, 1.0) : float4(0.4, 0.4, 0.4, 1.0);
    }
    // Left Arrow
    if (InTri(px - ac, float2(-9, 0), float2(-4, -4.5), float2(-4, 4.5))) {
        return pressLeft ? float4(1.0, 0.8, 0.2, 1.0) : float4(0.4, 0.4, 0.4, 1.0);
    }
    // Right Arrow
    if (InTri(px - ac, float2(9, 0), float2(4, -4.5), float2(4, 4.5))) {
        return pressRight ? float4(1.0, 0.8, 0.2, 1.0) : float4(0.4, 0.4, 0.4, 1.0);
    }

    // Capture indicator circle
    float2 cc = float2(status_left + 50.0, 20.0 + (H_S + 5.0 + H_L) / 2.0);
    if (length(px - cc) <= 4.0) {
        if (showGP) {
            return (HoveredID >= 0.0) ? float4(1.0, 0.2, 0.2, 1.0) : float4(0.2, 0.6, 1.0, 1.0); // Red (captured) / Blue (floating)
        }
        return float4(0.4, 0.4, 0.4, 1.0);
    }

    // ----------------------------------------------------------------
    // 5. BACKDROP PANELS RENDERING PASS
    // ----------------------------------------------------------------
    float y_top_limit = 20.0 + H_S + 5.0 + H_L + BG_PAD;

    // A. Main Block Panel (Gradient black)
    if (px.x >= main_left - BG_PAD && px.x <= right_edge + BG_PAD && px.y >= 20.0 - BG_PAD && px.y <= y_top_limit) {
        float t = (px.x - (main_left - BG_PAD)) / ((right_edge + BG_PAD) - (main_left - BG_PAD));
        float bgA = lerp(0.75, 0.15, pow(saturate(t), 1.5));
        return float4(0.0, 0.0, 0.0, bgA);
    }

    // B. Status Block Panel
    if (px.x >= status_left && px.x <= status_right && px.y >= 20.0 - BG_PAD && px.y <= y_top_limit) {
        return float4(0.0, 0.0, 0.0, 0.6);
    }

    // C. Notification Panels & Life lines
    // Notice 0 Box
    if (Notice0Time > 0.0 && age0 >= 0.0 && age0 < 4.0) {
        float x_left = lerp(ScreenRes.x, ScreenRes.x - BOX_W - 20.0, saturate(age0 / 0.4) * saturate(age0 / 0.4) * (3.0 - 2.0 * saturate(age0 / 0.4)));
        float y_bottom = 20.0 + H_S + 5.0 + H_L + BG_PAD + 15.0 + 0.0 * (BOX_H + 10.0);
        float globalAlpha = saturate((4.0 - age0) / 1.0);

        // Life progress line (white bottom strip)
        if (px.x >= x_left && px.x <= x_left + saturate((4.0 - age0) / 4.0) * BOX_W && px.y >= y_bottom && px.y <= y_bottom + 2.0) {
            return float4(1.0, 1.0, 1.0, 0.9 * globalAlpha);
        }
        // Gradient box
        if (px.x >= x_left && px.x <= x_left + BOX_W && px.y >= y_bottom && px.y <= y_bottom + BOX_H) {
            float t = (px.x - x_left) / BOX_W;
            float bgA = lerp(0.80, 0.20, pow(saturate(t), 1.5)) * globalAlpha;
            return float4(0.0, 0.0, 0.0, bgA);
        }
    }

    // Notice 1 Box
    if (Notice1Time > 0.0 && age1 >= 0.0 && age1 < 4.0) {
        float x_left = lerp(ScreenRes.x, ScreenRes.x - BOX_W - 20.0, saturate(age1 / 0.4) * saturate(age1 / 0.4) * (3.0 - 2.0 * saturate(age1 / 0.4)));
        float y_bottom = 20.0 + H_S + 5.0 + H_L + BG_PAD + 15.0 + 1.0 * (BOX_H + 10.0);
        float globalAlpha = saturate((4.0 - age1) / 1.0);

        // Life progress line (white bottom strip)
        if (px.x >= x_left && px.x <= x_left + saturate((4.0 - age1) / 4.0) * BOX_W && px.y >= y_bottom && px.y <= y_bottom + 2.0) {
            return float4(1.0, 1.0, 1.0, 0.9 * globalAlpha);
        }
        // Gradient box
        if (px.x >= x_left && px.x <= x_left + BOX_W && px.y >= y_bottom && px.y <= y_bottom + BOX_H) {
            float t = (px.x - x_left) / BOX_W;
            float bgA = lerp(0.80, 0.20, pow(saturate(t), 1.5)) * globalAlpha;
            return float4(0.0, 0.0, 0.0, bgA);
        }
    }

    // Notice 2 Box
    if (Notice2Time > 0.0 && age2 >= 0.0 && age2 < 4.0) {
        float x_left = lerp(ScreenRes.x, ScreenRes.x - BOX_W - 20.0, saturate(age2 / 0.4) * saturate(age2 / 0.4) * (3.0 - 2.0 * saturate(age2 / 0.4)));
        float y_bottom = 20.0 + H_S + 5.0 + H_L + BG_PAD + 15.0 + 2.0 * (BOX_H + 10.0);
        float globalAlpha = saturate((4.0 - age2) / 1.0);

        // Life progress line (white bottom strip)
        if (px.x >= x_left && px.x <= x_left + saturate((4.0 - age2) / 4.0) * BOX_W && px.y >= y_bottom && px.y <= y_bottom + 2.0) {
            return float4(1.0, 1.0, 1.0, 0.9 * globalAlpha);
        }
        // Gradient box
        if (px.x >= x_left && px.x <= x_left + BOX_W && px.y >= y_bottom && px.y <= y_bottom + BOX_H) {
            float t = (px.x - x_left) / BOX_W;
            float bgA = lerp(0.80, 0.20, pow(saturate(t), 1.5)) * globalAlpha;
            return float4(0.0, 0.0, 0.0, bgA);
        }
    }

    discard;
    return float4(0,0,0,0);
}
#endif
