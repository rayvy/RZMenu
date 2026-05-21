// ouroboros_adaptive_pos.hlsl
// GPU-only position recorder — records and advances index on every timer tick.
// Always writing allows the trail to collapse/disappear when the character stops.

RWBuffer<float4> CoordsHistory : register(u0);

cbuffer cb1 : register(b1)
{
    float4 cb1[29];
}

Texture1D<float4> IniParams : register(t120);
#define length_val  (uint)(IniParams[1].x + 0.5f)

[numthreads(1, 1, 1)]
void main()
{
    uint len = length_val;
    uint state_offset = len * 4;

    // Read state from the end of the buffer
    float4 state = CoordsHistory[state_offset];
    uint current_index = (uint)(state.x + 0.5f);
    current_index = current_index % len;

    // Always write the 4x4 transform matrix
    uint base = current_index * 4;
    CoordsHistory[base + 0] = cb1[0];
    CoordsHistory[base + 1] = cb1[1];
    CoordsHistory[base + 2] = cb1[2];
    CoordsHistory[base + 3] = float4(cb1[3].xyz, 1.0f); // .w = 1.0f (validity marker)

    uint next_index = (current_index + 1) % len;

    // Always advance index, set did_write = 1.0, save write slot
    CoordsHistory[state_offset] = float4(
        (float)next_index,    // .x = new current_index for VS
        1.0f,                 // .y = did_write (always true to collapse trail on stop)
        (float)current_index, // .z = slot we just wrote to
        0.0f
    );
}
