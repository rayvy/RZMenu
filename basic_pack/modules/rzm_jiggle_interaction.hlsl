// rzm_jiggle_interaction.hlsl
// RZMenu / 3DMigoto / XXMI
//
// Polished single-buffer Null-spring jiggle.
// Adapted from jiggle_physx_by_rayvich_ouroboros_targettrail_v05.hlsl
// by Rayvich for RZMenu ecosystem (per-component auto-generation).
//
// - One persistent Ouroboros RWBuffer<float4> at u6.
// - Detector snapshot is used only to create a grab anchor.
// - During drag, the target is derived from captured cursor delta on the
//   frozen tangent plane. Live raycast is intentionally NOT used.
// - Going outside the body silhouette therefore remains stable.
// - Release uses Verlet-style inertia with a small one-frame release kick.
//
// Bindings:
//   t24 = original vb0, read-only, stride 40
//   t67 = captured detector snapshot
//   u5  = copied vb0 output, RWStructuredBuffer<VertexAttributes>, stride 40
//   u6  = persistent jiggle state, RWBuffer<float4>, 8 entries minimum
//   t120 / IniParams[26] = same transform profile as detector
//
// IniParams:
//   [67].x = captured cursor X, pixels
//   [67].y = captured cursor Y, pixels
//   [67].w = capture active flag, 1 while mouse is held
//
//   [68].x = radius in world units, fallback 0.25
//   [68].y = drag strength, fallback 1.00
//   [68].z = falloff power, fallback 1.50
//   [68].w = screen drag scale, fallback 1.00
//
//   [69].x = current cursor X, pixels
//   [69].y = current cursor Y, pixels
//   [69].z = screen width
//   [69].w = screen height
//
//   [70].x = grab velocity damping, fallback 0.86
//   [70].y = grab spring, fallback 0.176       // ~20% slower than v03
//   [70].z = release velocity damping, fallback 0.96
//   [70].w = release spring, fallback 0.055     // ~20% slower than v03
//
//   [71].x = max offset clamp, fallback radius * 2.0
//   [71].y = one-frame release kick, fallback 1.10
//   [71].z = mouse Y direction, fallback +1.0
//            +1.0 = inverted relative to v03, -1.0 = old direction
//   [71].w = target smoothing/follow, fallback 0.12
//            lower = longer rubber delay, higher = snappier
//
// History layout u6:
//   [0].xyz = current physical offset, world-space
//   [0].w   = state alive flag
//   [1].xyz = previous physical offset, world-space
//   [1].w   = reserved
//   [2].xyz = frozen grab center, world-space
//   [2].w   = captured object ID
//   [3].xyz = frozen grab normal, world-space
//   [3].w   = previous-frame mouse-held flag
//   [4].xyz = filtered/smoothed drag target, world-space
//   [4].w   = reserved
//   [5].xyz = previous filtered target, world-space
//   [5].w   = reserved
//   [6].xyz = raw target debug/history, world-space
//   [6].w   = reserved
//   [7].xyzw = reserved

#define CB1_ROWS 29u

struct VertexAttributes
{
    float3 position;
    float3 normal;
    float4 tangent;
};

StructuredBuffer<VertexAttributes> base_buffer : register(t24);
StructuredBuffer<float4> CapturedDetect        : register(t67);
Buffer<float4> ObjParams                       : register(t68);
RWStructuredBuffer<VertexAttributes> rw_buffer  : register(u5);
RWBuffer<float4> JiggleState                    : register(u6);

cbuffer cb1 : register(b1)
{
    float4 gCB1[CB1_ROWS];
}

Texture1D<float4> IniParams : register(t120);

#define TRANSFORM_PARAMS     IniParams[26]
#define CAPTURED_CURSOR      IniParams[67]
#define JIGGLE_PARAMS        IniParams[68]
#define CURRENT_CURSOR       IniParams[69]
#define PHYS_PARAMS          IniParams[70]
#define POLISH_PARAMS        IniParams[71]
#define JIGGLE_MULTIPLIERS   IniParams[72]
#define JIGGLE_MULT_EXTRA    IniParams[73]

#define DETECT_SLOT_ID       0u
#define DETECT_SLOT_HIT      1u
#define DETECT_SLOT_NORMAL   5u

float SafePositive(float value, float fallback)
{
    return value > 0.0 ? value : fallback;
}

float SafeNonZero(float value, float fallback)
{
    return abs(value) > 0.00000001 ? value : fallback;
}

float3 SafeNormalize(float3 v, float3 fallback)
{
    float lenSq = dot(v, v);
    if (lenSq <= 0.00000001)
        return fallback;

    return v * rsqrt(lenSq);
}

float4 ReadCaptured(uint slot, float4 fallback)
{
    uint count;
    uint stride;
    CapturedDetect.GetDimensions(count, stride);

    if (slot >= count)
        return fallback;

    return CapturedDetect[slot];
}

float4 ReadState(uint slot, float4 fallback)
{
    uint count;
    JiggleState.GetDimensions(count);

    if (slot >= count)
        return fallback;

    return JiggleState[slot];
}

// ============================================================
// SAME LOCAL -> WORLD LANGUAGE AS DETECTOR
// ============================================================

float3 TransformBasisCB1(float3 p, uint baseRow)
{
    return gCB1[baseRow + 0u].xyz * p.x
         + gCB1[baseRow + 1u].xyz * p.y
         + gCB1[baseRow + 2u].xyz * p.z
         + gCB1[baseRow + 3u].xyz;
}

float3 TransformRowDotCB1(float3 p, uint baseRow)
{
    float4 hp = float4(p, 1.0);
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

// ============================================================
// WORLD VECTOR -> LOCAL VECTOR
// Output buffer still stores original vb0-space.
// ============================================================

float3 WorldVectorToLocalBasis(float3 v, uint baseRow)
{
    float3 c0 = gCB1[baseRow + 0u].xyz;
    float3 c1 = gCB1[baseRow + 1u].xyz;
    float3 c2 = gCB1[baseRow + 2u].xyz;

    float det = dot(c0, cross(c1, c2));
    if (abs(det) <= 0.00000001)
        return v;

    return float3(
        dot(v, cross(c1, c2)),
        dot(v, cross(c2, c0)),
        dot(v, cross(c0, c1))
    ) / det;
}

float3 WorldVectorToLocalRowDot(float3 v, uint baseRow)
{
    float3 r0 = gCB1[baseRow + 0u].xyz;
    float3 r1 = gCB1[baseRow + 1u].xyz;
    float3 r2 = gCB1[baseRow + 2u].xyz;

    float det = dot(r0, cross(r1, r2));
    if (abs(det) <= 0.00000001)
        return v;

    return float3(
        dot(cross(r1, r2), v),
        dot(cross(r2, r0), v),
        dot(cross(r0, r1), v)
    ) / det;
}

float3 WorldVectorToLocal(float3 v, int cb1Base, uint localMode)
{
    if (localMode == 1u && cb1Base >= 0)
        return WorldVectorToLocalBasis(v, (uint)cb1Base);

    if (localMode == 2u && cb1Base >= 0)
        return WorldVectorToLocalRowDot(v, (uint)cb1Base);

    return v;
}

// ============================================================
// BLENDER-LIKE FROZEN-ANCHOR CURSOR DRAG
// ============================================================

void BuildBasisFromNormal(float3 normalWorld, out float3 rightWorld, out float3 upWorld)
{
    float3 n = SafeNormalize(normalWorld, float3(0.0, 0.0, 1.0));
    float3 helper = abs(n.y) < 0.95
        ? float3(0.0, 1.0, 0.0)
        : float3(1.0, 0.0, 0.0);

    rightWorld = SafeNormalize(cross(helper, n), float3(1.0, 0.0, 0.0));
    upWorld    = SafeNormalize(cross(n, rightWorld), float3(0.0, 1.0, 0.0));
}

float2 GetScreenDragNormalized(float mouseYDirection)
{
    float2 screenSize = max(CURRENT_CURSOR.zw, float2(1.0, 1.0));
    float screenReference = max(min(screenSize.x, screenSize.y), 1.0);
    float2 deltaPx = CURRENT_CURSOR.xy - CAPTURED_CURSOR.xy;

    float mouseXDirection = -1.0;

    return float2(
        deltaPx.x / screenReference * mouseXDirection,
        deltaPx.y / screenReference * mouseYDirection
    );
}

float3 BuildFrozenAnchorScreenDrag(float3 capturedNormalWorld, float dragScale, float mouseYDirection)
{
    float3 rightWorld;
    float3 upWorld;
    BuildBasisFromNormal(capturedNormalWorld, rightWorld, upWorld);

    float2 delta = GetScreenDragNormalized(mouseYDirection) * dragScale;
    return rightWorld * delta.x + upWorld * delta.y;
}

float ComputeRubberInfluence(float dist, float radius, float falloffPower)
{
    if (dist >= radius)
        return 0.0;

    float x = 1.0 - saturate(dist / max(radius, 0.000001));

    // Smoothstep twice: soft edge, rounded center, no linear rubber plank.
    float s = x * x * (3.0 - 2.0 * x);
    s = s * s * (3.0 - 2.0 * s);

    return pow(s, falloffPower);
}

float3 ClampVectorLength(float3 v, float maxLen)
{
    float lenSq = dot(v, v);
    float maxSq = maxLen * maxLen;

    if (lenSq > maxSq && lenSq > 0.00000001)
        return v * (maxLen * rsqrt(lenSq));

    return v;
}

void ComputeNextPhysics(
    bool captureActive,
    bool hasCapturedID,
    float capturedID,
    float3 capturedCenterWorld,
    float3 capturedNormalWorld,
    float radius,
    float strength,
    float dragScale,
    float grabDamping,
    float grabSpring,
    float releaseDamping,
    float releaseSpring,
    float releaseKick,
    float maxOffset,
    float targetFollow,
    float mouseYDirection,
    out float4 outCurrent,
    out float4 outPrevious,
    out float4 outCenter,
    out float4 outNormal,
    out float4 outTarget,
    out float4 outPrevTarget,
    out float4 outRawTarget)
{
    float4 stateCurrent  = ReadState(0u, float4(0.0, 0.0, 0.0, 0.0));
    float4 statePrevious = ReadState(1u, float4(0.0, 0.0, 0.0, 0.0));
    float4 stateCenter   = ReadState(2u, float4(0.0, 0.0, 0.0, -1.0));
    float4 stateNormal   = ReadState(3u, float4(0.0, 0.0, 1.0, 0.0));
    float4 stateTarget   = ReadState(4u, float4(0.0, 0.0, 0.0, 0.0));
    float4 statePrevTgt  = ReadState(5u, float4(0.0, 0.0, 0.0, 0.0));

    bool stateAlive = stateCurrent.w > 0.5;
    bool wasCaptureActive = stateNormal.w > 0.5;
    bool pressedThisFrame = captureActive && !wasCaptureActive;
    bool sameObject = hasCapturedID && abs(stateCenter.w - capturedID) < 0.5;

    // Re-anchor on every fresh click, including a fresh click on the same ID.
    bool newCapture = captureActive && (pressedThisFrame || !stateAlive || !sameObject);

    float3 centerWorld = stateAlive ? stateCenter.xyz : capturedCenterWorld;
    float3 normalWorld = stateAlive ? stateNormal.xyz : capturedNormalWorld;
    float objectID = stateAlive ? stateCenter.w : capturedID;

    float3 currentOffset = stateAlive ? stateCurrent.xyz : float3(0.0, 0.0, 0.0);
    float3 previousOffset = stateAlive ? statePrevious.xyz : float3(0.0, 0.0, 0.0);
    float3 filteredTarget = stateAlive ? stateTarget.xyz : float3(0.0, 0.0, 0.0);
    float3 previousTarget = stateAlive ? statePrevTgt.xyz : float3(0.0, 0.0, 0.0);

    if (newCapture)
    {
        centerWorld = capturedCenterWorld;
        normalWorld = capturedNormalWorld;
        objectID = capturedID;
        currentOffset = float3(0.0, 0.0, 0.0);
        previousOffset = float3(0.0, 0.0, 0.0);
        filteredTarget = float3(0.0, 0.0, 0.0);
        previousTarget = float3(0.0, 0.0, 0.0);
    }

    float3 rawTargetOffset = float3(0.0, 0.0, 0.0);
    float spring = releaseSpring;
    float damping = releaseDamping;
    float currentTargetFollow = targetFollow;

    if (captureActive && hasCapturedID)
    {
        // Tangent plane drag.
        rawTargetOffset = BuildFrozenAnchorScreenDrag(normalWorld, dragScale, mouseYDirection) * strength;
        spring = grabSpring;
        damping = grabDamping;
    }
    else
    {
        currentTargetFollow = targetFollow * 0.55;
    }

    float3 targetVelocity = filteredTarget - previousTarget;
    previousTarget = filteredTarget;
    filteredTarget = filteredTarget + targetVelocity * 0.35 + (rawTargetOffset - filteredTarget) * currentTargetFollow;
    filteredTarget = ClampVectorLength(filteredTarget, maxOffset);

    float3 targetOffset = filteredTarget;

    float3 velocity = currentOffset - previousOffset;

    if (!captureActive && wasCaptureActive)
        velocity *= releaseKick;

    velocity *= damping;

    float3 acceleration = (targetOffset - currentOffset) * spring;
    float3 nextOffset = currentOffset + velocity + acceleration;
    nextOffset = ClampVectorLength(nextOffset, maxOffset);

    float3 nextVelocity = nextOffset - currentOffset;

    bool stillAlive = captureActive
        || dot(nextOffset, nextOffset) > 0.00000025
        || dot(nextVelocity, nextVelocity) > 0.00000025;

    if (!stillAlive)
    {
        nextOffset = float3(0.0, 0.0, 0.0);
        currentOffset = float3(0.0, 0.0, 0.0);
        filteredTarget = float3(0.0, 0.0, 0.0);
        previousTarget = float3(0.0, 0.0, 0.0);
        rawTargetOffset = float3(0.0, 0.0, 0.0);
        objectID = -1.0;
    }

    outCurrent  = float4(nextOffset, stillAlive ? 1.0 : 0.0);
    outPrevious = float4(currentOffset, 0.0);
    outCenter   = float4(centerWorld, objectID);
    outNormal   = float4(normalWorld, captureActive ? 1.0 : 0.0);
    outTarget   = float4(filteredTarget, 0.0);
    outPrevTarget = float4(previousTarget, 0.0);
    outRawTarget = float4(rawTargetOffset, 0.0);
}

// ============================================================
// MAIN
// ============================================================

[numthreads(256, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;

    uint vertexCount;
    uint vertexStride;
    rw_buffer.GetDimensions(vertexCount, vertexStride);

    float capturedID = ReadCaptured(DETECT_SLOT_ID, float4(-1.0, 0.0, 0.0, 0.0)).x;
    bool hasCapturedID = capturedID >= 0.0;
    bool captureActive = CAPTURED_CURSOR.w > 0.5 && hasCapturedID;

    int cb1Base = (int)TRANSFORM_PARAMS.y;
    uint mode = (uint)max(TRANSFORM_PARAMS.z, 0.0);
    uint localMode = mode / 10u;

    float4 stateCurrent  = ReadState(0u, float4(0.0, 0.0, 0.0, 0.0));
    float4 stateCenter   = ReadState(2u, float4(0.0, 0.0, 0.0, -1.0));
    bool stateAlive = stateCurrent.w > 0.5;
    float objectID = stateAlive ? stateCenter.w : capturedID;

    // Default parameters from IniParams/fallbacks
    float radius       = SafePositive(JIGGLE_PARAMS.x, 0.25);
    float strength     = SafeNonZero(JIGGLE_PARAMS.y, 1.0);
    float falloffPower = SafePositive(JIGGLE_PARAMS.z, 1.5);
    float dragScale    = SafePositive(JIGGLE_PARAMS.w, 1.0);

    float grabDamping    = saturate(SafePositive(PHYS_PARAMS.x, 0.86));
    float grabSpring     = SafePositive(PHYS_PARAMS.y, 0.176);
    float releaseDamping = saturate(SafePositive(PHYS_PARAMS.z, 0.96));
    float releaseSpring  = SafePositive(PHYS_PARAMS.w, 0.055);

    float maxOffset  = SafePositive(POLISH_PARAMS.x, radius * 2.0);
    float releaseKick = SafePositive(POLISH_PARAMS.y, 1.18);
    float targetFollow = saturate(SafePositive(POLISH_PARAMS.w, 0.12));
    float mouseYDirection = SafeNonZero(POLISH_PARAMS.z, 1.0);

    // Override from ObjParams if found
    uint paramCount = 0;
    ObjParams.GetDimensions(paramCount);
    uint objCount = paramCount / 4u;

    for (uint o = 0; o < objCount; ++o)
    {
        float4 r0 = ObjParams[o * 4u + 0u];
        if (abs(r0.x - objectID) < 0.5)
        {
            radius       = r0.y;
            strength     = r0.z;
            falloffPower = r0.w;

            float4 r1 = ObjParams[o * 4u + 1u];
            dragScale    = r1.x;
            grabDamping  = r1.y;
            grabSpring   = r1.z;
            releaseDamping = r1.w;

            float4 r2 = ObjParams[o * 4u + 2u];
            releaseSpring = r2.x;
            releaseKick  = r2.y;
            maxOffset    = r2.z;
            targetFollow = r2.w;

            float4 r3 = ObjParams[o * 4u + 3u];
            mouseYDirection = r3.x;
            break;
        }
    }

    // Read global multipliers
    float mult_radius    = JIGGLE_MULTIPLIERS.y;
    float mult_strength  = JIGGLE_MULTIPLIERS.z;
    float mult_spring    = JIGGLE_MULTIPLIERS.w;
    float mult_damping   = JIGGLE_MULT_EXTRA.x;

    // Fallback to 1.0 if completely undefined/unpopulated (all zero)
    if (mult_radius == 0.0 && mult_strength == 0.0 && mult_spring == 0.0 && mult_damping == 0.0)
    {
        mult_radius = 1.0;
        mult_strength = 1.0;
        mult_spring = 1.0;
        mult_damping = 1.0;
    }

    // Apply multipliers
    radius         *= mult_radius;
    strength       *= mult_strength;
    grabSpring     *= mult_spring;
    releaseSpring  *= mult_spring;
    grabDamping    = saturate(grabDamping * mult_damping);
    releaseDamping = saturate(releaseDamping * mult_damping);
    maxOffset      *= mult_radius;

    float3 capturedCenterWorld = ReadCaptured(
        DETECT_SLOT_HIT,
        float4(0.0, 0.0, 0.0, 0.0)
    ).xyz;

    float3 capturedNormalWorld = ReadCaptured(
        DETECT_SLOT_NORMAL,
        float4(0.0, 0.0, 1.0, 0.0)
    ).xyz;

    capturedNormalWorld = SafeNormalize(capturedNormalWorld, float3(0.0, 0.0, 1.0));

    float4 nextCurrent;
    float4 nextPrevious;
    float4 nextCenter;
    float4 nextNormal;
    float4 nextTarget;
    float4 nextPrevTarget;
    float4 nextRawTarget;

    ComputeNextPhysics(
        captureActive,
        hasCapturedID,
        capturedID,
        capturedCenterWorld,
        capturedNormalWorld,
        radius,
        strength,
        dragScale,
        grabDamping,
        grabSpring,
        releaseDamping,
        releaseSpring,
        releaseKick,
        maxOffset,
        targetFollow,
        mouseYDirection,
        nextCurrent,
        nextPrevious,
        nextCenter,
        nextNormal,
        nextTarget,
        nextPrevTarget,
        nextRawTarget
    );

    // Ouroboros update: one tiny persistent buffer. No ping-pong.
    if (i == 0u)
    {
        JiggleState[0u] = nextCurrent;
        JiggleState[1u] = nextPrevious;
        JiggleState[2u] = nextCenter;
        JiggleState[3u] = nextNormal;
        JiggleState[4u] = nextTarget;
        JiggleState[5u] = nextPrevTarget;
        JiggleState[6u] = nextRawTarget;
        JiggleState[7u] = float4(0.0, 0.0, 0.0, 0.0);
    }

    if (i >= vertexCount)
        return;

    VertexAttributes v = base_buffer[i];

    if (nextCurrent.w < 0.5)
    {
        rw_buffer[i] = v;
        return;
    }

    float3 worldPos = ToWorld(v.position, cb1Base, localMode);
    float dist = distance(worldPos, nextCenter.xyz);
    
    float influence = ComputeRubberInfluence(dist, radius, falloffPower);

    if (influence > 0.0)
    {
        float3 offsetWorld = nextCurrent.xyz * influence;
        float3 offsetLocal = WorldVectorToLocal(offsetWorld, cb1Base, localMode);
        v.position += offsetLocal;
    }

    rw_buffer[i] = v;
}
