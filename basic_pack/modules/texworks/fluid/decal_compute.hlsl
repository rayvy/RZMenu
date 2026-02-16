RWBuffer<int2> DecalDataBuffer : register(u0);
Texture1D<float4> IniParams : register(t120);

#define IN_SLOT_ID     (int)IniParams[70].x
#define IN_DECAL_ID    (int)IniParams[70].y

[numthreads(1, 1, 1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
    DecalDataBuffer[IN_SLOT_ID] = int2(IN_SLOT_ID, IN_DECAL_ID-1);
}