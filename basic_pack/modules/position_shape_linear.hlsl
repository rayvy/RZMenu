// **** CYCLIC ANIMATION SHADER ****
// Contributors: Zlevir

// Based on shapekey shader by Cybertron, SinsOfSeven

struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

struct SparseDelta {
    uint vertex_id;
    float3 delta;
    float3 padding1;
    float3 padding2;
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
StructuredBuffer<SparseDelta> shapekey : register(t51);

Texture1D<float4> IniParams : register(t120);
#define key IniParams[88].x
#define ORIG_V_COUNT ((uint)round(IniParams[115].x))

[numthreads(1024, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint sparse_count, stride;
    shapekey.GetDimensions(sparse_count, stride);
    if (i >= sparse_count) return;

    SparseDelta entry = shapekey[i];
    uint vertex_id = entry.vertex_id;

    uint vertex_count, rw_stride;
    rw_buffer.GetDimensions(vertex_count, rw_stride);
    if (vertex_id >= vertex_count) return;
    //RAYVICH EDIT: keep VFX vertices appended after original mesh untouched by native shapes.
    if (vertex_id >= ORIG_V_COUNT) return;

    rw_buffer[vertex_id].position += entry.delta * key;
}
