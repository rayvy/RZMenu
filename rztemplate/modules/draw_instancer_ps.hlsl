// draw_instancer_ps.hlsl - RZMenu Main Pixel Shader
struct VS_OUTPUT {
    float4 pos : SV_POSITION;
    float2 uv : TEXCOORD0;
    float4 color : COLOR0;
    float4 style_params : TEXCOORD1;
};

// Buffers
Buffer<float4> ResourceStyleBuffer : register(t105);

float4 main(VS_OUTPUT input) : SV_Target {
    // Basic color rendering. 
    // style_params.x can be used to index into ResourceStyleBuffer for advanced effects.
    return input.color;
}
