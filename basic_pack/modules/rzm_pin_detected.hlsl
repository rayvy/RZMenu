// rzm_pin_detected.hlsl
// RZMenu: Pins the closest hovered object ID detected during the frame
//         and resets the per-frame accumulator for the next frame.
//
// Expected bindings:
//   cs-u0 = ResourceRZMDetectID,       RWBuffer<float4>  (frame accumulator)
//   cs-u1 = ResourceRZMPinnedDetectID, RWBuffer<float>   (pinned R32_FLOAT for store)
//
// Accumulator layout (ResourceRZMDetectID[0]):
//   x = best hit ID  (-1 on miss)
//   y = best depth
//   z = firstIndex of winning range (debug)
//   w = hit triangle count (debug)
//
// After running:
//   ResourceRZMPinnedDetectID[0] = best.x (used by INI store -> $Detected)
//   ResourceRZMDetectID[0]       = float4(-1, HUGE, 0, 0)  (reset for next frame)

RWBuffer<float4> gAccumulated : register(u0);
RWBuffer<float>  gPinnedID    : register(u1);

static const float kHugeDepth = 3.402823e+38f;

[numthreads(1, 1, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    float4 best    = gAccumulated[0];
    bool   invalid = best.x < 0.0f || best.y > 1e30f;

    gPinnedID[0]    = invalid ? -1.0f : best.x;
    gAccumulated[0] = float4(-1.0f, kHugeDepth, 0.0f, 0.0f);
}
