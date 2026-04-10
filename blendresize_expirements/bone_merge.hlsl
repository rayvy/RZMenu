Buffer<float4> SourceSkeleton : register(t55);

RWBuffer<float4> DestinationSkeleton : register(u6);

#define Offset IniParams[0].x
#define Count IniParams[0].y
Texture1D<float4> IniParams : register(t120);

#ifdef COMPUTE_SHADER

// [numthreads(1,1,1)]
// void main(uint3 ThreadId : SV_DispatchThreadID)
// {
//     uint index = ThreadId.x;
//     DestinationSkeleton[Offset + index] = SourceSkeleton[index];
// }

[numthreads(1,1,1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
	uint i = ThreadId.x;
    if (i >= Count) {
        return;
    }

    if (any(SourceSkeleton[i] != 0 || SourceSkeleton[i+1] != 0 || SourceSkeleton[i+2] != 0)){
    i *= 3;
    int vg_offset = Offset * 3 + i;
    DestinationSkeleton[vg_offset] = SourceSkeleton[i];
    DestinationSkeleton[vg_offset+1] = SourceSkeleton[i+1];
    DestinationSkeleton[vg_offset+2] = SourceSkeleton[i+2];
    }
}

#endif