// Original code made by DiXiao, edited and optimised for Sandevistan effect by Rayvich
RWBuffer<float4> CoordsHistory : register(u0);

cbuffer cb1 : register(b1)
{
  float4 cb1[29];
}

Texture1D<float4> IniParams : register(t120);
#define length              (uint)IniParams[1].x
#define current_frame_index (uint)IniParams[2].x

[numthreads(1, 1, 1)]
void main()
{
  uint write_offset = current_frame_index * 4;
  CoordsHistory[write_offset + 0] = cb1[0];
  CoordsHistory[write_offset + 1] = cb1[1];
  CoordsHistory[write_offset + 2] = cb1[2];
  CoordsHistory[write_offset + 3] = cb1[3];
}