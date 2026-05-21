// trace_ps_sandevistan.hlsl
// Custom-colored Sandevistan ghost trail pixel shader
// Optimized with gamma-correct color blending and 4x4 Bayer dither fade-out.

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

cbuffer cb4 : register(b4) { float4 cb4[169]; }
cbuffer cb3 : register(b3) { float4 cb3[41]; }
cbuffer cb2 : register(b2) { float4 cb2[27]; }
cbuffer cb1 : register(b1) { float4 cb1[29]; }
cbuffer cb0 : register(b0) { float4 cb0[205]; }

#define length IniParams[1].x

#define color_start_r IniParams[4].x
#define color_start_g IniParams[4].y
#define color_start_b IniParams[4].z
#define color_start_a IniParams[4].w

#define color_mid_r   IniParams[5].x
#define color_mid_g   IniParams[5].y
#define color_mid_b   IniParams[5].z
#define color_mid_a   IniParams[5].w

#define color_end_r   IniParams[6].x
#define color_end_g   IniParams[6].y
#define color_end_b   IniParams[6].z
#define color_end_a   IniParams[6].w

// 3Dmigoto declarations
#define cmp -
Texture1D<float4> IniParams : register(t120);

void main(
  float4 v0 : TEXCOORD0,
  float4 v1 : TEXCOORD1,
  float4 v2 : TEXCOORD2,
  float4 v3 : SV_POSITION0, // SV_POSITION from VS (usually bound at v9 but in signature it must align)
  // Wait, let's keep the exact signature that was working to avoid layout mismatch.
  // The signature of the working version was:
  // float4 v0 : TEXCOORD0, float4 v1 : TEXCOORD1, float4 v2 : TEXCOORD2, float4 v3 : TEXCOORD3,
  // float4 v4 : TEXCOORD4, float4 v5 : TEXCOORD5, float4 v6 : TXCOORDD6, float4 v7 : TEXCOORD7,
  // float3 v8 : TEXCOORD8, float4 v9 : SV_POSITION0, uint v10 : SV_IsFrontFace0
  // Let's restore that exactly.
  float4 v0_orig : TEXCOORD0,
  float4 v1_orig : TEXCOORD1,
  float4 v2_orig : TEXCOORD2,
  float4 v3_orig : TEXCOORD3,
  float4 v4_orig : TEXCOORD4,
  float4 v5_orig : TEXCOORD5,
  float4 v6_orig : TXCOORDD6,
  float4 v7_orig : TEXCOORD7,
  float3 v8_orig : TEXCOORD8,
  float4 v9_orig : SV_POSITION0,
  uint v10_orig : SV_IsFrontFace0,
  out float4 o0 : SV_Target0,
  out float4 o1 : SV_Target1,
  out float4 o2 : SV_Target2,
  out float4 o3 : SV_Target3)
{
  o1 = 0;
  o0 = 0;
  o2 = 0;
  o3 = 0;

  float instance_id = v7_orig.w;
  float total_clones = length;

  if (instance_id > 0.0)
  {
      // Calculate age factor t from 0.0 (newest clone) to 1.0 (oldest clone)
      float t = (instance_id - 1.0) / max(1.0, total_clones - 2.0);
      t = saturate(t);

      // Interpolate alpha (opacity) along the gradient
      float blended_alpha;
      if (t < 0.5)
      {
          blended_alpha = lerp(color_start_a, color_mid_a, t * 2.0);
      }
      else
      {
          blended_alpha = lerp(color_mid_a, color_end_a, (t - 0.5) * 2.0);
      }
      blended_alpha = saturate(blended_alpha);

      // Dither fade-out using 4x4 Bayer matrix
      float2 pixel_coord = v9_orig.xy;
      uint x = (uint)pixel_coord.x % 4;
      uint y = (uint)pixel_coord.y % 4;
      uint dither_index = y * 4 + x;
      
      float dither_table[16] = {
          0.0000, 0.5000, 0.1250, 0.6250,
          0.7500, 0.2500, 0.8750, 0.3750,
          0.1875, 0.6875, 0.0625, 0.5625,
          0.9375, 0.4375, 0.8125, 0.3125
      };
      
      if (dither_table[dither_index] >= blended_alpha)
      {
          discard;
      }

      // Gamma-correct color blending (interpolation in linear space)
      float3 c_start = pow(max(0.0, float3(color_start_r, color_start_g, color_start_b)), 2.2);
      float3 c_mid   = pow(max(0.0, float3(color_mid_r, color_mid_g, color_mid_b)), 2.2);
      float3 c_end   = pow(max(0.0, float3(color_end_r, color_end_g, color_end_b)), 2.2);
      
      float3 blended_linear;
      if (t < 0.5)
      {
          blended_linear = lerp(c_start, c_mid, t * 2.0);
      }
      else
      {
          blended_linear = lerp(c_mid, c_end, (t - 0.5) * 2.0);
      }
      
      // Convert back to gamma space for display
      o0.xyz = pow(max(0.0, blended_linear), 1.0 / 2.2);
  }
  return;
}