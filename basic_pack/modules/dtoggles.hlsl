
Texture1D<float4> IniParams : register(t120);
SamplerState s0_s : register(s0);
Texture2D<float4> inputTex : register(t69);
#define xval IniParams[50].x

//Custom functions
Texture2D<float4> Mask : register(t12);

float rand3dTo1d(float3 value, float3 dotDir = float3(12.9898, 78.233, 37.719)){
    //make value smaller to avoid artefacts
    float3 smallValue = sin(value);
    //get scalar value from 3d vector
    float random = dot(smallValue, dotDir);
    //make value more random by making it bigger and then taking teh factional part
    random = frac(sin(random) * 143758.5453);
    return random;
}


float3 rand3dTo3d(float3 value){
    float3 randomValues = float3(
        rand3dTo1d(value, float3(12.989, 78.233, 37.719)),
        rand3dTo1d(value, float3(39.346, 11.135, 83.155)),
        rand3dTo1d(value, float3(73.156, 52.235, 9.151))
    );
    return randomValues;
}

float easeIn(float interpolator){
	return interpolator * interpolator;
}

float easeOut(float interpolator){
	return 1 - easeIn(1 - interpolator);
}

float easeInOut(float interpolator){
	float easeInValue = easeIn(interpolator);
	float easeOutValue = easeOut(interpolator);
	return lerp(easeInValue, easeOutValue, interpolator);
}

float perlinNoise(float3 value){
    float3 fraction = frac(value);

    float interpolatorX = easeInOut(fraction.x);
    float interpolatorY = easeInOut(fraction.y);
    float interpolatorZ = easeInOut(fraction.z);

    float cellNoiseZ[2];
    [unroll]
    for(int z = 0; z <= 1; z++){
        float cellNoiseY[2];
        [unroll]
        for(int y = 0; y <= 1; y++){
            float cellNoiseX[2];
            [unroll]
            for(int x = 0; x <= 1; x++){
                float3 cell = floor(value) + float3(x, y, z);
                float3 cellDirection = rand3dTo3d(cell) * 2 - 1;
                float3 compareVector = fraction - float3(x, y, z);
                cellNoiseX[x] = dot(cellDirection, compareVector);
            }
            cellNoiseY[y] = lerp(cellNoiseX[0], cellNoiseX[1], interpolatorX);
        }
        cellNoiseZ[z] = lerp(cellNoiseY[0], cellNoiseY[1], interpolatorY);
    }
    return lerp(cellNoiseZ[0], cellNoiseZ[1], interpolatorZ);
}

// xyz to x convert
float getGrayscaleValue(float3 color, bool r, bool g, bool b) {

    if (r) return color.x;
    if (g) return color.y;
    if (b) return color.z;
    
    if (r && g && !b) return (color.x + color.y) / 3;  // Жёлтый
    if (r && !g && b) return (color.x + color.z) / 3;  // Магента
    if (!r && g && b) return (color.y + color.z) / 3;  // Циан

    if (r && g && b) return (color.x + color.y + color.z) / 3;

    return 0.0;
}

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



#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
	uint width, height;
	float uvmove_mul = 0.1;
	inputTex.GetDimensions(width, height);
	if (!width || !height) discard;
	input.uv.y = 1 - input.uv.y;
	input.uv.y += xval*uvmove_mul;
	input.uv = frac(input.uv);
	result = inputTex.Load(int3(input.uv.xy * float2(width, height), 0));

	float value = 1 - xval;
	if(value > 0.55 && value < 1) {value += 0.05;}
	if(value < 0.45 && value > 0) {value -= 0.1;}

	// float luminance = dot(result, float3(0.299, 0.587, 0.114));
	// float outputRed = step(xval, luminance);
	float3 peperlin = float3(0.241,0.5235,0.853) * 50.0;
	float perlinColor = perlinNoise(peperlin);

	if(value > 0.6){result.x += (1 + value)*0.1;}
	result.x *= value*1;
	result.yz *= value*25;
	if(result.x>1){result.yz = 0;}
	if(result.x<0){result.yz = 0;}
	result.w = 1;
	// result.x = value;
	

	// if(value < 0){result.x = 1;}
	// if(value > 1){result.x = 0;}

	// result.x -= value;
	// result.yzw = float3(0,0,1.0);
}
#endif

RWTexture2D<float4>  tex0 : register(u5);
RWTexture2D<float4>  tex1 : register(u4);
#ifdef COMPUTE_SHADER
[numthreads(32, 32, 1)]
void main(uint3 id : SV_DispatchThreadID)
{
    tex0[id.xy] = tex1.Load(id.xy);
}
#endif