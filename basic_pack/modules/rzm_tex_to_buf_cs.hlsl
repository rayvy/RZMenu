// Generic Texture2D<float4> -> RWBuffer<float4> copier.
// Bind source texture to cs-t0 and destination buffer to cs-u2.

Texture2D<float4> SourceTex : register(t0);
RWBuffer<float4> DestBuf : register(u2);

[numthreads(256, 1, 1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    uint width;
    uint height;
    SourceTex.GetDimensions(width, height);

    uint destCount;
    DestBuf.GetDimensions(destCount);

    uint count = min(width * height, destCount);
    uint i = tid.x;

    if (i >= count)
        return;

    uint x = i % width;
    uint y = i / width;

    DestBuf[i] = SourceTex.Load(int3(x, y, 0));
}
