
Texture1D<float4> IniParams : register(t120);
SamplerState s0_s : register(s0);

struct vs2ps {
	float4 pos : SV_Position0;
	float2 uv : TEXCOORD1;
};
struct PS_INPUT
{
    float4 pos : SV_POSITION;  // позиция на экране
    float2 uv  : TEXCOORD0;    // координаты текстуры
    float4 color : COLOR0;     // цвет (опционально)
};

static const float2 SIZE = float2(1.0, 1.0);
static const float2 OFFSET = float2(0.0, 0.0);
#ifdef VERTEX_SHADER
void main(
		out vs2ps output,
		uint vertex : SV_VertexID)
{
	float2 BaseCoord,Offset;
	Offset.x = OFFSET.x*2-1;
	Offset.y = (1-OFFSET.y)*2-1;
	BaseCoord.xy = float2((2*SIZE.x),(2*(-SIZE.y)));
	// Not using vertex buffers so manufacture our own coordinates.
	switch(vertex) {
		case 0:
			output.pos.xy = float2(BaseCoord.x+Offset.x, BaseCoord.y+Offset.y);
			output.uv = float2(1,0);
			break;
		case 1:
			output.pos.xy = float2(BaseCoord.x+Offset.x, 0+Offset.y);
			output.uv = float2(1,1);
			break;
		case 2:
			output.pos.xy = float2(0+Offset.x, BaseCoord.y+Offset.y);
			output.uv = float2(0,0);
			break;
		case 3:
			output.pos.xy = float2(0+Offset.x, 0+Offset.y);
			output.uv = float2(0,1);
			break;
		default:
			output.pos.xy = 0;
			output.uv = float2(0,0);
			break;
	};
	output.pos.zw = float2(0, 1);
}
#endif

Texture2D<float4> tex : register(t40);
Texture2D<float4> tex_overlay : register(t41);
#define value IniParams[88].x

#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
    uint width, height;
    tex.GetDimensions(width, height);
    tex_overlay.GetDimensions(width, height);
    if (!width || !height) discard;

    input.uv.y = 1 - input.uv.y;

    float2 pixelCoord = input.uv.xy * float2(width, height);
    float4 baseColor   = tex.Load(int3(pixelCoord, 0));
    float4 overlay     = tex_overlay.Load(int3(pixelCoord, 0));

    float blendAmount = saturate(value);
	result.rgb = lerp(baseColor.rgb, overlay.rgb, blendAmount);
	result.a   = baseColor.a;
}
#endif
