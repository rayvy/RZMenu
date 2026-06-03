struct VertexAttributes {
    float3 position;
    uint normal;
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
StructuredBuffer<VertexAttributes> base : register(t50);
StructuredBuffer<VertexAttributes> shapekey : register(t51);

Texture1D<float4> IniParams : register(t120);
#define key IniParams[88].x
#define ORIG_V_COUNT ((uint)round(IniParams[115].x))

[numthreads(256, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint vertex_count, stride;
    rw_buffer.GetDimensions(vertex_count, stride);
    if (i >= vertex_count) return;
    //RAYVICH EDIT: keep VFX vertices appended after original mesh untouched by native shapes.
    if (i >= ORIG_V_COUNT) return;

    float3 diffPos = shapekey[i].position - base[i].position;
    
    rw_buffer[i].position += diffPos * key;
}
