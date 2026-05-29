import re

ini_path = 'G:/XXMI/ZZMI/Mods/Promeia/Promeia.ini'

with open(ini_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update [CommandListTextureOverridePromeiaHairB]
# Insert recording commands at the start of the list
hair_match = re.search(r'\[CommandListTextureOverridePromeiaHairB\]', content)
if hair_match:
    insert_pos = hair_match.end()
    # Find next newline to insert after it
    next_nl = content.find('\n', insert_pos)
    content = content[:next_nl+1] + "run = CustomShaderComputeHairHistory\nrun = CustomShaderWriteHairHistory\n" + content[next_nl+1:]

# 2. Update [CommandListTextureOverridePromeiaLegsA]
legs_match = re.search(r'\[CommandListTextureOverridePromeiaLegsA\]', content)
if legs_match:
    insert_pos = legs_match.end()
    next_nl = content.find('\n', insert_pos)
    content = content[:next_nl+1] + "run = CustomShaderComputeLegsHistory\nrun = CustomShaderWriteLegsHistory\n" + content[next_nl+1:]

# 3. Update [CustomShaderRZM_VFX_PromeiaHairB]
# Replace cs-u6 line with cs-t6 reference
content = re.sub(
    r'(\[CustomShaderRZM_VFX_PromeiaHairB\][\s\S]*?cs-u6\s*=\s*[^\n]*)',
    r'[CustomShaderRZM_VFX_PromeiaHairB]\ncs = ./modules/vfx_curve_physics_cs.hlsl\ncs-u5 = copy ResourcePromeiaHairPosition\ncs-t6 = ref ResourcePromeiaHairHistoryBuffer',
    content
)

# 4. Update [CustomShaderRZM_VFX_PromeiaLegsA]
content = re.sub(
    r'(\[CustomShaderRZM_VFX_PromeiaLegsA\][\s\S]*?cs-u6\s*=\s*[^\n]*)',
    r'[CustomShaderRZM_VFX_PromeiaLegsA]\n; TEST: VFX Curves Associated:\n;   - Curve name: "TestNurbs.001"\n;     * Type: 0\n;     * Start Size: 1.0\n;     * End Size: 1.0\n;     * Cycle Duration: 3.0\n;     * Dispersion Scale: 1.0\n;     * Phase Randomness: 1.0\n;     * Position Randomness: 0.0\n;     * Spline Type: NURBS\n;     * Control Points (NURBS/Poly):\n;       Point 0: (-0.0967, 0.0495, 0.2068) | Radius: 0.0000\n;       Point 1: (-0.2046, 0.0980, 0.3064) | Radius: 1.0000\n;       Point 2: (-0.1322, -0.1528, 0.3329) | Radius: 1.0000\n;       Point 3: (0.0296, 0.0082, 0.4216) | Radius: 1.0000\n;       Point 4: (-0.0509, 0.1153, 0.5162) | Radius: 1.0000\n;       Point 5: (-0.2479, 0.2459, 0.6516) | Radius: 13.1997\ncs = ./modules/vfx_curve_physics_cs.hlsl\ncs-u5 = copy ResourcePromeiaLegsPosition\ncs-t6 = ref ResourcePromeiaLegsHistoryBuffer',
    content
)

# 5. Define recording custom shaders and resources at the end of the file
new_blocks = """

; --- Motion History Recording Shaders and Resources ---

[CustomShaderComputeHairHistory]
cs = ./modules/ouroboros_adaptive_pos.hlsl
cs-u0 = ResourcePromeiaHairHistoryBuffer
cs-cb1 = vs-cb1
x1 = 64
x3 = 0.2
dispatch = 1, 1, 1
ResourcePromeiaHairHistoryBuffer = cs-u0

[CustomShaderWriteHairHistory]
cs = ./modules/ouroboros_adaptive_vb.hlsl
cs-t0 = vb0
cs-u0 = ResourcePromeiaHairSkinnedHistory
cs-t1 = ResourcePromeiaHairHistoryBuffer
x0 = 7414
x1 = 64
dispatch = 8
ResourcePromeiaHairSkinnedHistory = cs-u0

[CustomShaderComputeLegsHistory]
cs = ./modules/ouroboros_adaptive_pos.hlsl
cs-u0 = ResourcePromeiaLegsHistoryBuffer
cs-cb1 = vs-cb1
x1 = 64
x3 = 0.2
dispatch = 1, 1, 1
ResourcePromeiaLegsHistoryBuffer = cs-u0

[CustomShaderWriteLegsHistory]
cs = ./modules/ouroboros_adaptive_vb.hlsl
cs-t0 = vb0
cs-u0 = ResourcePromeiaLegsSkinnedHistory
cs-t1 = ResourcePromeiaLegsHistoryBuffer
x0 = 26917
x1 = 64
dispatch = 27
ResourcePromeiaLegsSkinnedHistory = cs-u0

[ResourcePromeiaHairHistoryBuffer]
type = RWBuffer
format = R32G32B32A32_FLOAT
array = 257

[ResourcePromeiaLegsHistoryBuffer]
type = RWBuffer
format = R32G32B32A32_FLOAT
array = 257

[ResourcePromeiaHairSkinnedHistory]
type = RWStructuredBuffer
stride = 40
array = 474496

[ResourcePromeiaLegsSkinnedHistory]
type = RWStructuredBuffer
stride = 40
array = 1722688
"""

# Append to the end of the file
content += new_blocks

with open(ini_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Promeia.ini successfully patched with World-space history recording and bindings!")
