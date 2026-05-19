Texture1D<float4> IniParams : register(t120);

// Helper to retrieve values from IniParams
float GetIniParam(int index, int component) {
    return IniParams.Load(int2(index, 0))[component];
}

struct VertexOutput {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

#ifdef VERTEX_SHADER
void main(uint vID : SV_VertexID, out VertexOutput output) {
    // Generate a single full-screen triangle covering [-1, 3] in NDC
    float2 uv = float2(0.0, 0.0);
    if (vID == 0) uv = float2(0.0, 0.0);
    else if (vID == 1) uv = float2(2.0, 0.0);
    else if (vID == 2) uv = float2(0.0, 2.0);

    output.uv = uv;
    output.position = float4(uv * 2.0 - 1.0, 0.0, 1.0);
}
#endif

#ifdef PIXEL_SHADER
// 3x5 Pixel Font Glyph Data
uint GetGlyphBits(uint c) {
    if (c == 'G') return 31567;
    if (c == 'A') return 23535;
    if (c == 'M') return 23421;
    if (c == 'E') return 29647;
    if (c == 'P') return 5103;
    if (c == 'D') return 15211;
    if (c == 'O') return 31599;
    if (c == 'N') return 23421;
    if (c == 'B') return 15083;
    if (c == 'L') return 29257;
    return 0; // Space or other
}

// Get character of "GAMEPAD MODE ENABLED" (length 20)
uint GetStringChar(int charIdx) {
    uint s[20] = { 'G', 'A', 'M', 'E', 'P', 'A', 'D', ' ', 'M', 'O', 'D', 'E', ' ', 'E', 'N', 'A', 'B', 'L', 'E', 'D' };
    return charIdx < 20 ? s[charIdx] : 0;
}

// Sample Glyph Bits at local coordinate
bool SampleGlyph(uint ascii, int2 localCoord) {
    if (localCoord.x < 0 || localCoord.x >= 3 || localCoord.y < 0 || localCoord.y >= 5) {
        return false;
    }
    uint bits = GetGlyphBits(ascii);
    uint bitIndex = localCoord.y * 3 + localCoord.x;
    return (bits & (1u << bitIndex)) != 0;
}

// Barycentric triangle test
bool IsInsideTriangle(float2 d, float2 v0, float2 v1, float2 v2) {
    float s3 = (v0.x - v2.x) * (d.y - v2.y) - (v0.y - v2.y) * (d.x - v2.x);
    float s1 = (v1.x - v0.x) * (d.y - v0.y) - (v1.y - v0.y) * (d.x - v0.x);
    float s2 = (v2.x - v1.x) * (d.y - v1.y) - (v2.y - v1.y) * (d.x - v1.x);
    return (s3 >= 0 && s1 >= 0 && s2 >= 0) || (s3 <= 0 && s1 <= 0 && s2 <= 0);
}

float4 main(VertexOutput input) : SV_Target {
    // Read screen resolution and cursor position
    float2 ScreenRes = IniParams.Load(int2(99, 0)).zw;
    float2 CursorPos = IniParams.Load(int2(99, 0)).xy * ScreenRes;
    float InputMode = IniParams.Load(int2(97, 0)).x;

    // Strict requirement: Only display when gamepad mode is active
    if (InputMode != 1.0) {
        discard;
    }

    float2 pixelPos = input.uv * ScreenRes;

    // --- CURSOR DRAWING ---
    // Hardcoded cursor coordinates (as a resource directly inside the shader)
    float2 d = pixelPos - CursorPos;
    
    // Black pointer triangle
    float2 v0 = float2(0, 0);
    float2 v1 = float2(0, -15);
    float2 v2 = float2(10, -10);

    // White outline triangle
    float2 w0 = float2(-1.5, 1.5);
    float2 w1 = float2(-1.5, -17.5);
    float2 w2 = float2(12.5, -11.5);

    // Stem black quad
    float2 s0 = float2(2.5, -11.5);
    float2 s1 = float2(4.0, -11.5);
    float2 s2 = float2(8.0, -18.5);
    float2 s3 = float2(6.5, -18.5);

    // Stem white outline quad
    float2 sw0 = float2(1.5, -10.5);
    float2 sw1 = float2(5.0, -10.5);
    float2 sw2 = float2(9.0, -19.5);
    float2 sw3 = float2(5.5, -19.5);

    bool drawCursorBlack = IsInsideTriangle(d, v0, v1, v2) || 
                          IsInsideTriangle(d, s0, s1, s2) || 
                          IsInsideTriangle(d, s0, s2, s3);
                          
    bool drawCursorWhite = IsInsideTriangle(d, w0, w1, w2) || 
                          IsInsideTriangle(d, sw0, sw1, sw2) || 
                          IsInsideTriangle(d, sw0, sw2, sw3);

    if (drawCursorBlack) {
        return float4(0.0, 0.0, 0.0, 1.0);
    }
    if (drawCursorWhite) {
        return float4(1.0, 1.0, 1.0, 1.0);
    }

    // --- TEXT DRAWING (GAMEPAD MODE ENABLED) ---
    // Bottom-right corner alignment
    // Characters are 3x5 pixels. Scale is 2.5. Total height = 12.5 pixels. Width per char = 10 pixels.
    // Total string width = 20 * 10 = 200 pixels.
    // Start drawing at X = ScreenRes.x - 220, Y = 20 (from bottom).
    float scale = 2.5;
    float2 textStart = float2(ScreenRes.x - 220.0, 20.0);
    float2 localTextPos = pixelPos - textStart;

    if (localTextPos.x >= 0.0 && localTextPos.x < 20.0 * 4.0 * scale && 
        localTextPos.y >= 0.0 && localTextPos.y < 5.0 * scale) {
        
        int charIdx = (int)(localTextPos.x / (4.0 * scale));
        float2 charLocal = localTextPos - float2(charIdx * 4.0 * scale, 0.0);

        if (charLocal.x < 3.0 * scale) {
            // Sample glyph
            int2 glyphCoord = int2(charLocal.x / scale, 4.0 - charLocal.y / scale);
            uint ascii = GetStringChar(charIdx);
            
            if (SampleGlyph(ascii, glyphCoord)) {
                // Return beautiful cyber green text
                return float4(0.0, 1.0, 0.5, 1.0);
            }
        }
    }

    discard;
    return float4(0, 0, 0, 0);
}
#endif
