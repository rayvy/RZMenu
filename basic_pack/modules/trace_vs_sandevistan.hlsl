// trace_vs_sandevistan.hlsl
// Sandevistan ghost trail vertex shader
// current_frame_index reads from the end of the Coords buffer (t127).
// Uninitialized slots are hidden by checking Coords[slot*4+3].w.

struct t0_t { float val[32]; };
StructuredBuffer<t0_t> t0 : register(t0);

cbuffer cb2 : register(b2) { float4 cb2[25]; }
cbuffer cb1 : register(b1) { float4 cb1[29]; }
cbuffer cb0 : register(b0) { float4 cb0[196]; }

struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};
StructuredBuffer<VertexAttributes> vb0 : register(t1);
Buffer<float4> Coords : register(t127);

#define size                IniParams[0].x
#define length              IniParams[1].x

#define cmp -
Texture1D<float4> IniParams : register(t120);

void main(
  float3 v0 : POSITION0,
  float3 v1 : NORMAL0,
  float4 v2 : TANGENT0,
  float4 v3 : COLOR0,
  float4 v4 : TEXCOORD0,
  float4 v5 : TEXCOORD1,
  float4 v6 : TEXCOORD2,
  float4 v7 : TEXCOORD3,
  float3 v8 : TEXCOORD4,
  uint vertex   : SV_VertexID,
  uint instance : SV_InstanceID,
  out float4 o0 : TEXCOORD0,
  out float4 o1 : TEXCOORD1,
  out float4 o2 : TEXCOORD2,
  out float4 o3 : TEXCOORD3,
  out float4 o4 : TEXCOORD4,
  out float4 o5 : TEXCOORD5,
  out float4 o6 : TXCOORDD6,
  out float4 o7 : TEXCOORD7,
  out float3 o8 : TEXCOORD8,
  out float4 o9 : SV_POSITION0)
{
  o0=0;o1=0;o2=0;o3=0;o4=0;o5=0;o6=0;o7=0;o8=0;o9=0;
  float4 cb1Copy[29] = cb1;

  uint len = (uint)(length + 0.5f);
  uint current_frame_index = (uint)(Coords[len * 4].x + 0.5f);

  if (instance != 0)
  {
    // Integer modulo to prevent fmod precision/reset bugs
    uint history_slot_index = (current_frame_index - instance + len) % len;
    uint history_read_offset = history_slot_index * (uint)(size + 0.5f);

    VertexAttributes model = vb0[vertex + history_read_offset];
    v0.xyz = model.position;
    v1.xyz = model.normal;
    v2.xyzw = model.tangent;

    uint coord_index = history_slot_index;
    cb1Copy[0] = Coords[coord_index * 4 + 0];
    cb1Copy[1] = Coords[coord_index * 4 + 1];
    cb1Copy[2] = Coords[coord_index * 4 + 2];

    float4 coord3 = Coords[coord_index * 4 + 3];
    cb1Copy[3] = coord3;

    // Hide ghost if slot is uninitialized (validity marker .w < 0.5)
    if (coord3.w < 0.5f)
    {
      o9 = float4(0, 0, 0, 0);
      return;
    }
  }

  float4 r0, r1;
  r0.xyz = cb1Copy[1].xyz * v0.yyy;
  r0.xyz = cb1Copy[0].xyz * v0.xxx + r0.xyz;
  r0.xyz = cb1Copy[2].xyz * v0.zzz + r0.xyz;
  r0.xyz = cb1Copy[3].xyz + r0.xyz;
  r1.xyzw = cb0[126].xyzw * r0.yyyy;
  r1.xyzw = cb0[125].xyzw * r0.xxxx + r1.xyzw;
  r1.xyzw = cb0[127].xyzw * r0.zzzz + r1.xyzw;
  o9.xyzw = cb0[128].xyzw + r1.xyzw;
  o7.w = (float)instance;

  // Hide ghost if too close to current character position
  float hide_distance_threshold = 0.2f;
  float3 original_character_pos = cb1[3].xyz;
  float3 current_clone_pos = cb1Copy[3].xyz;
  if (distance(original_character_pos, current_clone_pos) < hide_distance_threshold)
  {
    o9.xyzw = float4(0, 0, 0, 0);
  }
  return;
}
