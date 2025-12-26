//VB Recorder (replacing from oldest to newest) 
//SinsOfSeven, Rayvich
struct VertexAttributes { // byte_struct
  float3 position; // 0 + 12 = 12
  float3 normal; //  12 + 12 = 24
  float4 tangent; // 24 + 16 = 40
};
RWStructuredBuffer<VertexAttributes> rw_buffer : register(u0);
StructuredBuffer<VertexAttributes> base_buffer : register(t0);
Texture1D<float4> IniParams : register(t120);
// Might want to move these to x,y,z
// Iniparams[0].x IniParams[0].y IniParams[0].z
#define  buffer_size (uint)IniParams[0].x
#define buffer_total (uint)IniParams[1].x
#define buffer_index (uint)IniParams[2].x

[numthreads(1024, 1, 1)]
void main(uint3 thread : SV_DispatchThreadID) {
  // Early Return (Safety)
  if(thread.x >= buffer_size || buffer_index >= buffer_total) return;  
  rw_buffer[thread.x + buffer_size * buffer_index] = base_buffer[thread.x];
}