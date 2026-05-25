// rzm_object_detect.hlsl
// RZMenu: Component-level GPU cursor hit detector.
//
// One dispatch processes a whole component ObjectMap:
//
//   gObjectMap[0]     = float4(objectCount, 0, 0, 0)
//   gObjectMap[1 + i] = float4(firstIndex, indexCount, baseVertex, objectID)
//
// If objectID <= 0, firstIndex is used as the output ID.
//
// Expected bindings:
//   cs-t0  = post-skinned vertex buffer, stride 40:
//            float3 position, float3 normal, float4 tangent
//   cs-t1  = index buffer, R32_UINT
//   cs-t2  = component ObjectMap, Buffer<float4>
//   cs-u0  = RWBuffer<float4>, one-element closest-hit accumulator (ResourceRZMDetectID)
//   cs-cb0 = candidate VS cb0
//   cs-cb1 = candidate VS cb1
//
// INI params (via IniParams):
//   x24/y24 = cursor position (pixels or normalized UV)
//   z24/w24 = screen width/height
//
//   x26 = cb0 base row
//   y26 = cb1 base row  (-1 = raw vb0 already world-space)
//   z26 = mode: localMode * 10 + clipMode
//         localMode 0 = raw vb0, 1 = basis cb1, 2 = row-dot cb1
//         clipMode  0 = basis cb0, 1 = row-dot cb0,
//                   2 = basis cb0 + cb0[21].xy viewport offset
//   w26 = hit padding in pixels
//
// Accumulated output (gBestHit[0]):
//   x = closest hit ID   (-1 on miss)
//   y = closest depth
//   z = firstIndex of the winning range
//   w = hit triangle count (debug)
//
// Multiple dispatches may write into the same UAV — closest depth wins.
// Dispatch with exactly one group: dispatch = 1, 1, 1

#define THREADS_PER_GROUP 128u
#define CB0_ROWS          196u
#define CB1_ROWS          29u
#define MAX_OBJECTS       256u

struct VertexAttributes
{
    float3 position;
    float3 normal;
    float4 tangent;
};

StructuredBuffer<VertexAttributes> gVB0        : register(t0);
Buffer<uint>                       gIndexBuffer : register(t1);
Buffer<float4>                     gObjectMap   : register(t2);
RWBuffer<float4>                   gBestHit     : register(u0);

cbuffer cb0 : register(b0) { float4 gCB0[CB0_ROWS]; }
cbuffer cb1 : register(b1) { float4 gCB1[CB1_ROWS]; }

Texture1D<float4> IniParams : register(t120);

#define CURSOR_PARAMS    IniParams[24]
#define CLICK_PARAMS     IniParams[25]
#define TRANSFORM_PARAMS IniParams[26]

groupshared float sBestDepth[THREADS_PER_GROUP];
groupshared float sBestID[THREADS_PER_GROUP];
groupshared float sBestFirstIndex[THREADS_PER_GROUP];
groupshared float sHitCount[THREADS_PER_GROUP];

// ─── Transform helpers ───────────────────────────────────────────────────────

float3 TransformBasisCB1(float3 p, uint baseRow)
{
    return gCB1[baseRow + 0u].xyz * p.x
         + gCB1[baseRow + 1u].xyz * p.y
         + gCB1[baseRow + 2u].xyz * p.z
         + gCB1[baseRow + 3u].xyz;
}

float3 TransformRowDotCB1(float3 p, uint baseRow)
{
    float4 hp = float4(p, 1.0f);
    return float3(
        dot(gCB1[baseRow + 0u], hp),
        dot(gCB1[baseRow + 1u], hp),
        dot(gCB1[baseRow + 2u], hp)
    );
}

float3 ToWorld(float3 p, int cb1Base, uint localMode)
{
    if (localMode == 1u && cb1Base >= 0)
        return TransformBasisCB1(p, (uint)cb1Base);
    if (localMode == 2u && cb1Base >= 0)
        return TransformRowDotCB1(p, (uint)cb1Base);
    return p;
}

float4 ProjectBasisCB0(float3 p, uint baseRow)
{
    return gCB0[baseRow + 0u] * p.x
         + gCB0[baseRow + 1u] * p.y
         + gCB0[baseRow + 2u] * p.z
         + gCB0[baseRow + 3u];
}

float4 ProjectRowDotCB0(float3 p, uint baseRow)
{
    float4 hp = float4(p, 1.0f);
    return float4(
        dot(gCB0[baseRow + 0u], hp),
        dot(gCB0[baseRow + 1u], hp),
        dot(gCB0[baseRow + 2u], hp),
        dot(gCB0[baseRow + 3u], hp)
    );
}

float4 ToClip(float3 worldPos, uint cb0Base, uint clipMode)
{
    if (clipMode == 1u)
        return ProjectRowDotCB0(worldPos, cb0Base);

    float4 clip = ProjectBasisCB0(worldPos, cb0Base);
    if (clipMode == 2u)
        clip.xy += gCB0[21u].xy * clip.w;
    return clip;
}

bool ClipToScreenUV(float4 clipPos, out float2 uv, out float depth)
{
    uv    = float2(0.0f, 0.0f);
    depth = 3.402823e+38f;

    if (clipPos.w <= 1e-5f)
        return false;

    float2 ndc = clipPos.xy / clipPos.w;
    uv    = float2(ndc.x * 0.5f + 0.5f, 0.5f - ndc.y * 0.5f);
    depth = clipPos.z / clipPos.w;

    return all(abs(ndc) < float2(1000.0f, 1000.0f)) && abs(depth) < 1000.0f;
}

// ─── Cursor helpers ──────────────────────────────────────────────────────────

float2 CursorUV()
{
    float2 screenRes = max(CURSOR_PARAMS.zw, float2(1.0f, 1.0f));
    float2 cursor    = CURSOR_PARAMS.xy;
    if (cursor.x > 1.0f || cursor.y > 1.0f)
        cursor /= screenRes;
    return saturate(cursor);
}

float Cross2(float2 a, float2 b)
{
    return a.x * b.y - a.y * b.x;
}

bool PointInTriangle(float2 p, float2 a, float2 b, float2 c)
{
    float e0 = Cross2(b - a, p - a);
    float e1 = Cross2(c - b, p - b);
    float e2 = Cross2(a - c, p - c);
    bool hasNeg = (e0 < 0.0f) || (e1 < 0.0f) || (e2 < 0.0f);
    bool hasPos = (e0 > 0.0f) || (e1 > 0.0f) || (e2 > 0.0f);
    return !(hasNeg && hasPos);
}

float DistSqPointSegment(float2 p, float2 a, float2 b)
{
    float2 ab    = b - a;
    float  denom = max(dot(ab, ab), 1e-10f);
    float  t     = saturate(dot(p - a, ab) / denom);
    float2 d     = p - (a + ab * t);
    return dot(d, d);
}

bool CursorHitsTriangle(float2 cursor, float2 a, float2 b, float2 c, float padUV)
{
    float2 pad = float2(padUV, padUV);
    float2 mn  = min(a, min(b, c)) - pad;
    float2 mx  = max(a, max(b, c)) + pad;

    if (any(cursor < mn) || any(cursor > mx))
        return false;

    if (PointInTriangle(cursor, a, b, c))
        return true;

    float padSq = padUV * padUV;
    float d0 = DistSqPointSegment(cursor, a, b);
    float d1 = DistSqPointSegment(cursor, b, c);
    float d2 = DistSqPointSegment(cursor, c, a);
    return min(d0, min(d1, d2)) <= padSq;
}

// ─── Per-object triangle test ────────────────────────────────────────────────

void TestTriangleRange(
    uint  tid,
    uint  firstIndex,
    uint  indexCount,
    uint  baseVertex,
    float objectID,
    uint  cb0Base,
    int   cb1Base,
    uint  localMode,
    uint  clipMode,
    float2 cursor,
    float  padUV,
    inout float bestDepth,
    inout float bestID,
    inout float bestFirstIndex,
    inout float hitCount)
{
    uint triangleCount = indexCount / 3u;

    [loop]
    for (uint tri = tid; tri < triangleCount; tri += THREADS_PER_GROUP)
    {
        uint indexBase = firstIndex + tri * 3u;
        uint i0 = gIndexBuffer[indexBase + 0u] + baseVertex;
        uint i1 = gIndexBuffer[indexBase + 1u] + baseVertex;
        uint i2 = gIndexBuffer[indexBase + 2u] + baseVertex;

        float3 w0 = ToWorld(gVB0[i0].position, cb1Base, localMode);
        float3 w1 = ToWorld(gVB0[i1].position, cb1Base, localMode);
        float3 w2 = ToWorld(gVB0[i2].position, cb1Base, localMode);

        float2 s0, s1, s2;
        float  d0, d1, d2;
        bool ok0 = ClipToScreenUV(ToClip(w0, cb0Base, clipMode), s0, d0);
        bool ok1 = ClipToScreenUV(ToClip(w1, cb0Base, clipMode), s1, d1);
        bool ok2 = ClipToScreenUV(ToClip(w2, cb0Base, clipMode), s2, d2);

        if (ok0 && ok1 && ok2 && CursorHitsTriangle(cursor, s0, s1, s2, padUV))
        {
            hitCount += 1.0f;
            float triDepth = min(d0, min(d1, d2));
            if (triDepth < bestDepth)
            {
                bestDepth      = triDepth;
                bestID         = objectID;
                bestFirstIndex = (float)firstIndex;
            }
        }
    }
}

// ─── Main ────────────────────────────────────────────────────────────────────

[numthreads(THREADS_PER_GROUP, 1, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID,
          uint3 groupThreadID    : SV_GroupThreadID)
{
    uint tid = groupThreadID.x;

    uint  cb0Base      = (uint)max(TRANSFORM_PARAMS.x, 0.0f);
    int   cb1Base      = (int)TRANSFORM_PARAMS.y;
    uint  mode         = (uint)max(TRANSFORM_PARAMS.z, 0.0f);
    float hitPadPixels = max(TRANSFORM_PARAMS.w, 0.0f);

    uint localMode = mode / 10u;
    uint clipMode  = mode - localMode * 10u;

    float bestDepth      = 3.402823e+38f;
    float bestID         = -1.0f;
    float bestFirstIndex = 0.0f;
    float hitCount       = 0.0f;

    uint objectCount = (uint)min(max(gObjectMap[0u].x, 0.0f), (float)MAX_OBJECTS);
    float2 cursor    = CursorUV();
    float2 screenRes = max(CURSOR_PARAMS.zw, float2(1.0f, 1.0f));
    float  padUV     = hitPadPixels / max(screenRes.x, screenRes.y);

    bool isClicked = (CLICK_PARAMS.x > 0.0f);

    if (cb0Base + 3u < CB0_ROWS)
    {
        [loop]
        for (uint objectIndex = 0u; objectIndex < objectCount; objectIndex++)
        {
            float4 entry     = gObjectMap[1u + objectIndex];
            uint firstIndex  = (uint)max(entry.x, 0.0f);
            uint indexCount  = (uint)max(entry.y, 0.0f);
            float objectMode = entry.z;
            float objectID   = entry.w > 0.0f ? entry.w : (float)firstIndex;

            bool isHoverType   = (objectMode <= 3.0f);
            bool isClickType   = (objectMode >= 4.0f && objectMode <= 6.0f);
            bool shouldProcess = isHoverType || (isClickType && isClicked);

            if (shouldProcess && indexCount >= 3u)
            {
                TestTriangleRange(
                    tid,
                    firstIndex, indexCount, 0u, objectID,
                    cb0Base, cb1Base, localMode, clipMode,
                    cursor, padUV,
                    bestDepth, bestID, bestFirstIndex, hitCount);
            }
        }
    }

    sBestDepth[tid]      = bestDepth;
    sBestID[tid]         = bestID;
    sBestFirstIndex[tid] = bestFirstIndex;
    sHitCount[tid]       = hitCount;
    GroupMemoryBarrierWithGroupSync();

    for (uint stride = THREADS_PER_GROUP / 2u; stride > 0u; stride >>= 1u)
    {
        if (tid < stride)
        {
            sHitCount[tid] += sHitCount[tid + stride];
            if (sBestDepth[tid + stride] < sBestDepth[tid])
            {
                sBestDepth[tid]      = sBestDepth[tid + stride];
                sBestID[tid]         = sBestID[tid + stride];
                sBestFirstIndex[tid] = sBestFirstIndex[tid + stride];
            }
        }
        GroupMemoryBarrierWithGroupSync();
    }

    if (tid == 0u && sBestID[0] >= 0.0f)
    {
        float4 previous      = gBestHit[0];
        bool previousInvalid = previous.x < 0.0f || previous.y > 1e30f;

        if (previousInvalid || sBestDepth[0] < previous.y)
        {
            gBestHit[0] = float4(sBestID[0], sBestDepth[0], sBestFirstIndex[0], sHitCount[0]);
        }
    }
}
