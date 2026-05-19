// system_draw.hlsl — System Overlay: cursor + status text slots
// draw = 3, 0  (fullscreen triangle)
//
// Bindings:
//   t120 = IniParams   [99].xy=cursorNorm [99].zw=ScreenRes
//                      [97].x=InputMode(0=KB,1=GP)  [97].y=ApiOk(0=missing,1=ok)
//   t82  = ResourceFont0  (sys_font atlas, 16-col grid)
//   t56  = Slot0 (RZMenu 4.0.2)
//   t57  = Slot1 (Mod Author)
//   t58  = Slot2 (Gamepad/Keyboard status)
//   t59  = Slot3 (Notification 0)
//   t60  = Slot4 (Notification 1)
//   t61  = Slot5 (Notification 2)

Texture1D<float4> IniParams : register(t120);
Texture2D<float4> FontAtlas : register(t82);
Buffer<uint>      Slot0     : register(t56);
Buffer<uint>      Slot1     : register(t57);
Buffer<uint>      Slot2     : register(t58);
Buffer<uint>      Slot3     : register(t59);
Buffer<uint>      Slot4     : register(t60);
Buffer<uint>      Slot5     : register(t61);
SamplerState      Smp       : register(s0);

// --- Font constants ---
static const uint  FONT_COLS  = 16;
static const float TEXT_H_PX  = 15.0;   // rendered text height in screen pixels
static const float  BG_PAD    = 5.0;

// --- Structs ---
struct VSOut {
    float4 position : SV_Position;
    float2 uv       : TEXCOORD0;
};

// --- Cursor helpers ---
bool InTri(float2 p, float2 a, float2 b, float2 c) {
    float d0 = (b.x-a.x)*(p.y-a.y) - (b.y-a.y)*(p.x-a.x);
    float d1 = (c.x-b.x)*(p.y-b.y) - (c.y-b.y)*(p.x-b.x);
    float d2 = (a.x-c.x)*(p.y-c.y) - (a.y-c.y)*(p.x-c.x);
    bool has_neg = (d0<0)||(d1<0)||(d2<0);
    bool has_pos = (d0>0)||(d1>0)||(d2>0);
    return !(has_neg && has_pos);
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

    bool showGP = (InputMode > 0.5);

    float2 px = input.uv * ScreenRes;

    // ----------------------------------------------------------------
    // 1. CURSOR (Gamepad mode only)
    // ----------------------------------------------------------------
    if (showGP) {
        float2 d = px - CursorPos;

        // Black fill (arrow + stem)
        if (InTri(d, float2(0,0),      float2(0,-15),   float2(10,-10))    ||
            InTri(d, float2(2.5,-11.5), float2(4,-11.5), float2(8,-18.5))  ||
            InTri(d, float2(2.5,-11.5), float2(8,-18.5), float2(6.5,-18.5)))
            return float4(0,0,0,1);

        // White outline
        if (InTri(d, float2(-1.5,1.5),  float2(-1.5,-17.5), float2(12.5,-11.5)) ||
            InTri(d, float2(1.5,-10.5), float2(5,-10.5),    float2(9,-19.5))     ||
            InTri(d, float2(1.5,-10.5), float2(9,-19.5),    float2(5.5,-19.5)))
            return float4(1,1,1,1);
    }

    // ----------------------------------------------------------------
    // 2. TEXT SLOTS LAYOUT (Horizontal chain, right to left)
    // ----------------------------------------------------------------
    uint atlasW, atlasH;
    FontAtlas.GetDimensions(atlasW, atlasH);
    float cs   = (float)(atlasW / FONT_COLS);
    float rows = (float)(atlasH) / cs;
    float scale = TEXT_H_PX / cs;

    static const float ADV_FRAC = 0.62;
    float charW = cs * scale * ADV_FRAC;
    float totalH = TEXT_H_PX;

    float2 uvCell = 1.0 / float2((float)FONT_COLS, rows);
    float current_right = ScreenRes.x - 20.0;

    // --- SLOT 0 ("RZMenu 4.0.2") ---
    {
        uint len = 0;
        Slot0.GetDimensions(len);
        len = min(len, 32u);
        if (len > 0) {
            float slot_w = charW * (float)len;
            float slot_left = current_right - slot_w;

            // Text
            float2 rel = px - float2(slot_left, 20.0);
            if (rel.x >= 0.0 && rel.x < slot_w && rel.y >= 0.0 && rel.y < totalH) {
                int ci = (int)(rel.x / charW);
                if (ci < (int)len) {
                    uint c = Slot0.Load(ci);
                    float4 txtCol = float4(1.0, 0.6, 0.1, 1.0); // Gold
                    float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS);
                    float2 uvBase = cellUV * uvCell;
                    float2 localUV = float2(frac(rel.x / charW) * ADV_FRAC, 1.0 - (rel.y / totalH));
                    float alpha = FontAtlas.SampleLevel(Smp, uvBase + saturate(localUV) * uvCell, 0).r;
                    if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a);
                }
            }
            // Backdrop
            float2 bgMin = float2(slot_left - BG_PAD, 20.0 - BG_PAD);
            float2 bgMax = float2(current_right + BG_PAD, 20.0 + totalH + BG_PAD);
            if (all(px >= bgMin) && all(px <= bgMax)) {
                float t   = (px.x - bgMin.x) / (bgMax.x - bgMin.x);
                float bgA = lerp(0.70, 0.0, pow(saturate(t), 1.5));
                if (bgA > 0.01) return float4(0.0, 0.0, 0.0, bgA);
            }
            current_right = slot_left - 15.0;
        }
    }

    // --- SLOT 1 (Mod Author) ---
    {
        uint len = 0;
        Slot1.GetDimensions(len);
        len = min(len, 32u);
        if (len > 0) {
            float slot_w = charW * (float)len;
            float slot_left = current_right - slot_w;

            // Text
            float2 rel = px - float2(slot_left, 20.0);
            if (rel.x >= 0.0 && rel.x < slot_w && rel.y >= 0.0 && rel.y < totalH) {
                int ci = (int)(rel.x / charW);
                if (ci < (int)len) {
                    uint c = Slot1.Load(ci);
                    float4 txtCol = float4(0.3, 0.7, 1.0, 1.0); // Cyan
                    float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS);
                    float2 uvBase = cellUV * uvCell;
                    float2 localUV = float2(frac(rel.x / charW) * ADV_FRAC, 1.0 - (rel.y / totalH));
                    float alpha = FontAtlas.SampleLevel(Smp, uvBase + saturate(localUV) * uvCell, 0).r;
                    if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a);
                }
            }
            // Backdrop
            float2 bgMin = float2(slot_left - BG_PAD, 20.0 - BG_PAD);
            float2 bgMax = float2(current_right + BG_PAD, 20.0 + totalH + BG_PAD);
            if (all(px >= bgMin) && all(px <= bgMax)) {
                float t   = (px.x - bgMin.x) / (bgMax.x - bgMin.x);
                float bgA = lerp(0.70, 0.0, pow(saturate(t), 1.5));
                if (bgA > 0.01) return float4(0.0, 0.0, 0.0, bgA);
            }
            current_right = slot_left - 15.0;
        }
    }

    // --- SLOT 2 (Gamepad/Keyboard status) ---
    {
        uint len = 0;
        Slot2.GetDimensions(len);
        len = min(len, 32u);
        if (len > 0) {
            float slot_w = charW * (float)len;
            float slot_left = current_right - slot_w;

            // Text
            float2 rel = px - float2(slot_left, 20.0);
            if (rel.x >= 0.0 && rel.x < slot_w && rel.y >= 0.0 && rel.y < totalH) {
                int ci = (int)(rel.x / charW);
                if (ci < (int)len) {
                    uint c = Slot2.Load(ci);
                    float4 txtCol = float4(1.0, 1.0, 1.0, 1.0);
                    if (c == 71) txtCol = float4(0.35, 1.0, 0.65, 1.0); // Gamepad: Green
                    else if (c == 75) txtCol = float4(0.7, 0.7, 0.7, 1.0); // Keyboard: Gray
                    else txtCol = float4(1.0, 0.35, 0.35, 1.0); // No API: Red

                    float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS);
                    float2 uvBase = cellUV * uvCell;
                    float2 localUV = float2(frac(rel.x / charW) * ADV_FRAC, 1.0 - (rel.y / totalH));
                    float alpha = FontAtlas.SampleLevel(Smp, uvBase + saturate(localUV) * uvCell, 0).r;
                    if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a);
                }
            }
            // Backdrop
            float2 bgMin = float2(slot_left - BG_PAD, 20.0 - BG_PAD);
            float2 bgMax = float2(current_right + BG_PAD, 20.0 + totalH + BG_PAD);
            if (all(px >= bgMin) && all(px <= bgMax)) {
                float t   = (px.x - bgMin.x) / (bgMax.x - bgMin.x);
                float bgA = lerp(0.70, 0.0, pow(saturate(t), 1.5));
                if (bgA > 0.01) return float4(0.0, 0.0, 0.0, bgA);
            }
            current_right = slot_left - 15.0;
        }
    }

    // --- SLOT 3 (Notification 0) ---
    {
        uint len = 0;
        Slot3.GetDimensions(len);
        len = min(len, 32u);
        if (len > 0) {
            float slot_w = charW * (float)len;
            float slot_left = current_right - slot_w;

            // Text
            float2 rel = px - float2(slot_left, 20.0);
            if (rel.x >= 0.0 && rel.x < slot_w && rel.y >= 0.0 && rel.y < totalH) {
                int ci = (int)(rel.x / charW);
                if (ci < (int)len) {
                    uint c = Slot3.Load(ci);
                    float4 txtCol = float4(1.0, 0.8, 0.2, 1.0); // Yellow notice
                    float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS);
                    float2 uvBase = cellUV * uvCell;
                    float2 localUV = float2(frac(rel.x / charW) * ADV_FRAC, 1.0 - (rel.y / totalH));
                    float alpha = FontAtlas.SampleLevel(Smp, uvBase + saturate(localUV) * uvCell, 0).r;
                    if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a);
                }
            }
            // Backdrop
            float2 bgMin = float2(slot_left - BG_PAD, 20.0 - BG_PAD);
            float2 bgMax = float2(current_right + BG_PAD, 20.0 + totalH + BG_PAD);
            if (all(px >= bgMin) && all(px <= bgMax)) {
                float t   = (px.x - bgMin.x) / (bgMax.x - bgMin.x);
                float bgA = lerp(0.70, 0.0, pow(saturate(t), 1.5));
                if (bgA > 0.01) return float4(0.0, 0.0, 0.0, bgA);
            }
            current_right = slot_left - 15.0;
        }
    }

    // --- SLOT 4 (Notification 1) ---
    {
        uint len = 0;
        Slot4.GetDimensions(len);
        len = min(len, 32u);
        if (len > 0) {
            float slot_w = charW * (float)len;
            float slot_left = current_right - slot_w;

            // Text
            float2 rel = px - float2(slot_left, 20.0);
            if (rel.x >= 0.0 && rel.x < slot_w && rel.y >= 0.0 && rel.y < totalH) {
                int ci = (int)(rel.x / charW);
                if (ci < (int)len) {
                    uint c = Slot4.Load(ci);
                    float4 txtCol = float4(0.9, 0.4, 0.9, 1.0); // Pink notice
                    float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS);
                    float2 uvBase = cellUV * uvCell;
                    float2 localUV = float2(frac(rel.x / charW) * ADV_FRAC, 1.0 - (rel.y / totalH));
                    float alpha = FontAtlas.SampleLevel(Smp, uvBase + saturate(localUV) * uvCell, 0).r;
                    if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a);
                }
            }
            // Backdrop
            float2 bgMin = float2(slot_left - BG_PAD, 20.0 - BG_PAD);
            float2 bgMax = float2(current_right + BG_PAD, 20.0 + totalH + BG_PAD);
            if (all(px >= bgMin) && all(px <= bgMax)) {
                float t   = (px.x - bgMin.x) / (bgMax.x - bgMin.x);
                float bgA = lerp(0.70, 0.0, pow(saturate(t), 1.5));
                if (bgA > 0.01) return float4(0.0, 0.0, 0.0, bgA);
            }
            current_right = slot_left - 15.0;
        }
    }

    // --- SLOT 5 (Notification 2) ---
    {
        uint len = 0;
        Slot5.GetDimensions(len);
        len = min(len, 32u);
        if (len > 0) {
            float slot_w = charW * (float)len;
            float slot_left = current_right - slot_w;

            // Text
            float2 rel = px - float2(slot_left, 20.0);
            if (rel.x >= 0.0 && rel.x < slot_w && rel.y >= 0.0 && rel.y < totalH) {
                int ci = (int)(rel.x / charW);
                if (ci < (int)len) {
                    uint c = Slot5.Load(ci);
                    float4 txtCol = float4(0.4, 0.9, 0.4, 1.0); // Light Green notice
                    float2 cellUV = float2((c - 32) % FONT_COLS, (c - 32) / FONT_COLS);
                    float2 uvBase = cellUV * uvCell;
                    float2 localUV = float2(frac(rel.x / charW) * ADV_FRAC, 1.0 - (rel.y / totalH));
                    float alpha = FontAtlas.SampleLevel(Smp, uvBase + saturate(localUV) * uvCell, 0).r;
                    if (alpha >= 0.05) return float4(txtCol.rgb, alpha * txtCol.a);
                }
            }
            // Backdrop
            float2 bgMin = float2(slot_left - BG_PAD, 20.0 - BG_PAD);
            float2 bgMax = float2(current_right + BG_PAD, 20.0 + totalH + BG_PAD);
            if (all(px >= bgMin) && all(px <= bgMax)) {
                float t   = (px.x - bgMin.x) / (bgMax.x - bgMin.x);
                float bgA = lerp(0.70, 0.0, pow(saturate(t), 1.5));
                if (bgA > 0.01) return float4(0.0, 0.0, 0.0, bgA);
            }
            current_right = slot_left - 15.0;
        }
    }

    discard;
    return float4(0,0,0,0);
}
#endif
