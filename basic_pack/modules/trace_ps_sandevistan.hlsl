// ---- Created with 3Dmigoto v1.3.16 on Fri Aug  8 03:27:02 2025
//c39f59308374f651
Texture2D<float4> t8 : register(t8);

Texture2DArray<float4> t7 : register(t7);

Texture2D<float4> t6 : register(t6);

Texture2D<float4> t5 : register(t5);

Texture2D<float4> t4 : register(t4);

Texture2D<float4> t3 : register(t3);

Texture2D<float4> t2 : register(t2);

struct t1_t {
  float val[32];
};
StructuredBuffer<t1_t> t1 : register(t1);

Texture2DArray<float4> t0 : register(t0);

SamplerState s2_s : register(s2);

SamplerComparisonState s1_s : register(s1);

SamplerState s0_s : register(s0);

cbuffer cb4 : register(b4)
{
  float4 cb4[158];
}

cbuffer cb3 : register(b3)
{
  float4 cb3[41];
}

cbuffer cb2 : register(b2)
{
  float4 cb2[27];
}

cbuffer cb1 : register(b1)
{
  float4 cb1[29];
}

cbuffer cb0 : register(b0)
{
  float4 cb0[198];
}


#define length IniParams[1].x
#define current_frame_index IniParams[2].x

// 3Dmigoto declarations
#define cmp -
Texture1D<float4> IniParams : register(t120);


void main(
  float4 v0 : TEXCOORD0,
  float4 v1 : TEXCOORD1,
  float4 v2 : TEXCOORD2,
  float4 v3 : TEXCOORD3,
  float4 v4 : TEXCOORD4,
  float4 v5 : TEXCOORD5,
  float4 v6 : TXCOORDD6,
  float4 v7 : TEXCOORD7,
  float4 v8 : TEXCOORD8,
  float3 v9 : TEXCOORD9,
  float4 v10 : SV_POSITION0,
  uint v11 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0,
  out float4 o1 : SV_Target1,
  out float4 o2 : SV_Target2,
  out float4 o3 : SV_Target3)
{
  float4 r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12,r13,r14,r15,r16,r17,r18,r19,r20,r21;
  uint4 bitmask, uiDest;
  float4 fDest;
  float instance_id = v7.w;
  o1 = 0;
  o0 = 0;
  o2 = 0;
  o3 = 0;
  if (instance_id > 0.0)
  {
      float total_clones = length;
      float gradient_progress = (instance_id - 2.0) / (total_clones - 2.0);
      
      float3 color_start = float3(0.9, 0.0, 0.1);
      float3 color_mid1 = float3(0.0, 0.0, 0.7);
      float3 color_end = float3(0.0, 0.5, 0.0);
      
      float3 gradient_color;
      if (gradient_progress < 0.5)
      {
          gradient_color = lerp(color_start, color_mid1, gradient_progress * 2.0);
      }
      else
      {
          gradient_color = lerp(color_mid1, color_end, (gradient_progress - 0.5) * 2.0);
      }
      
      o0.xyz = gradient_color*0.1;
      o0.xyz = gradient_color;
  }

if (instance_id > 0.0)
{
    float transparency_level = (instance_id - 1.0) / (length - 1.0);
    transparency_level = transparency_level * 10.2 - 0.2;
    transparency_level = saturate(transparency_level);
    float dither_pattern = fmod(floor(v10.x) + floor(v10.y), 2.0);
    if (dither_pattern < transparency_level)
    {
        discard;
    }
} 
  return;
}