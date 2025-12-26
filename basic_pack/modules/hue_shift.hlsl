
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


float3 RGBtoHSV(float3 c)
{
    float4 K = float4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    float4 p = lerp(float4(c.bg, K.wz), float4(c.gb, K.xy), step(c.b, c.g));
    float4 q = lerp(float4(p.xyw, c.r), float4(c.r, p.yzx), step(p.x, c.r));

    float d = q.x - min(q.w, q.y);
    float e = 1e-10;
    return float3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

float3 HSVtoRGB(float3 c)
{
    float4 K = float4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    float3 p = abs(frac(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * lerp(K.xxx, saturate(p - 1.0), c.y);
}

Texture2D<float4> tex : register(t0);
#define colorshift IniParams[72].x

#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
	uint width, height;
	tex.GetDimensions(width, height);
	if (!width || !height) discard;
	input.uv.y = 1 - input.uv.y;
	result = tex.Load(int3(input.uv.xy * float2(width, height), 0));
    result.w = 1;

    // float hueShiftAmount = 0.9; // 0.0 - 1.0 (1.0 = полный круг)
    float hueShiftAmount = colorshift.x;
    float3 hsv = RGBtoHSV(result.rgb);
    hsv.x = frac(hsv.x + hueShiftAmount); // сдвигаем оттенок
    result.xyz = HSVtoRGB(hsv.rgb);
}
#endif

RWTexture2D<float4>  tex0 : register(u5);
RWTexture2D<float4>  tex1 : register(u4);
#ifdef COMPUTE_SHADER
[numthreads(32, 32, 1)]
void main(uint3 id : SV_DispatchThreadID)
{
    tex0[id.xy] = tex1.Load(id.xy);
	// tex0[id.xy].xyz = result.xyz;
}
#endif