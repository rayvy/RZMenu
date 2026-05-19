// system_draw_svg.hlsl — SVG Mesh pass
// Reads tessellated vertex data from SvgData buffer (t55).
//
// Buffer layout (written by test_svg_compiler_v2.py):
//   float4[0]        = header (keyboard_count, cursor_count, total, 0)
//   float4[1 + i*2]  = (pos.x, pos.y, color.r, color.g)
//   float4[1 + i*2+1]= (color.b, color.a, edge_dist, mesh_type)
//
// mesh_type:
//   0.0 = static keyboard icon — offset by SVG_OFFSET
//   1.0 = cursor icon          — offset by live CursorPos (x99/y99 * ScreenRes)

Texture1D<float4> IniParams : register(t120);
Buffer<float4>    SvgData   : register(t55);

// Top-left screen position of the keyboard SVG icon
static const float2 SVG_OFFSET = float2(20.0, 20.0);

struct VSOut {
    float4 position : SV_Position;
    float4 color    : COLOR0;
    float  edge     : TEXCOORD0;
};

// -----------------------------------------------------------------------
// VERTEX SHADER
// -----------------------------------------------------------------------
#ifdef VERTEX_SHADER
void main(uint vID : SV_VertexID, out VSOut output) {
    float2 ScreenRes = IniParams.Load(int2(99, 0)).zw;
    float2 CursorPos = IniParams.Load(int2(99, 0)).xy * ScreenRes;

    // Header is at index 0, vertices start at index 1, 2 float4s per vertex
    uint base = 1 + vID * 2;
    float4 v0 = SvgData.Load(int(base));
    float4 v1 = SvgData.Load(int(base + 1));

    float2 localPos  = v0.xy;
    float4 color     = float4(v0.z, v0.w, v1.x, v1.y);
    float  edgeDist  = v1.z;
    float  meshType  = v1.w;

    // Static icon: fixed screen offset
    // Cursor icon: follows cursor position
    float2 screenPos;
    if (meshType < 0.5) {
        screenPos = (SVG_OFFSET + localPos) / ScreenRes;
    } else {
        screenPos = (CursorPos + localPos) / ScreenRes;
    }

    // DX NDC: Y flipped (screen top = NDC +1)
    output.position = float4(
         screenPos.x * 2.0 - 1.0,
        -screenPos.y * 2.0 + 1.0,
        0.0, 1.0);
    output.color = color;
    output.edge  = edgeDist;
}
#endif

// -----------------------------------------------------------------------
// PIXEL SHADER
// -----------------------------------------------------------------------
#ifdef PIXEL_SHADER

float4 main(VSOut input) : SV_Target {
    float InputMode = IniParams.Load(int2(97, 0)).x;
    if (InputMode != 1.0) discard;

    // AA edge fade: edge_dist 0.0 (transparent fringe) → 1.0 (opaque fill)
    float alpha = smoothstep(0.0, 0.3, input.edge) * input.color.a;
    if (alpha < 0.01) discard;

    return float4(input.color.rgb, alpha);
}
#endif
