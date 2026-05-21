// ouroboros_adaptive_vb.hlsl
// Adaptive VB recorder — reads write flag from the end of CoordsHistory buffer.
// If did_write == 0, all threads exit early (zero GPU cost).

struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

RWStructuredBuffer<VertexAttributes> rw_buffer     : register(u0);
StructuredBuffer<VertexAttributes>   base_buffer   : register(t0);
Buffer<float4>                       CoordsHistory : register(t1);

Texture1D<float4> IniParams : register(t120);
#define buffer_size  (uint)(IniParams[0].x + 0.5f)  // vertex count
#define buffer_total (uint)(IniParams[1].x + 0.5f)  // ring length

[numthreads(1024, 1, 1)]
void main(uint3 thread : SV_DispatchThreadID)
{
    uint len = buffer_total;
    uint state_offset = len * 4;

    // Read state from the end of CoordsHistory
    float4 state = CoordsHistory[state_offset];
    
    // state.y is did_write flag
    if (state.y < 0.5f) return;

    // state.z is the slot we just wrote to in adaptive_pos
    uint write_slot = (uint)(state.z + 0.5f);

    // Safety bounds check
    write_slot = write_slot % len;

    if (thread.x >= buffer_size) return;
    rw_buffer[thread.x + buffer_size * write_slot] = base_buffer[thread.x];
}
