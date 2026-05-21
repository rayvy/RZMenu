import os
import struct
import random

def generate_hoyo_vb(num_particles: int, output_path: str):
    """
    Generates a Hoyoverse-style vertex buffer with 40-byte stride.
    Layout:
      Position: float3 (12 bytes) -> Local quad offsets relative to particle center
      Normal:   float3 (12 bytes) -> Custom parameters: (EyeSide, Phase, SpeedScale)
      Tangent:  float4 (16 bytes) -> Custom parameters: (RandDir.x, RandDir.y, RandDir.z, ParticleScale)
    """
    # Quad local positions for billboard vertices (Bottom-Left, Bottom-Right, Top-Left, Top-Right)
    quad_vertices = [
        (-0.5, -0.5, 0.0), # BL
        ( 0.5, -0.5, 0.0), # BR
        (-0.5,  0.5, 0.0), # TL
        ( 0.5,  0.5, 0.0), # TR
    ]

    with open(output_path, 'wb') as f:
        for i in range(num_particles):
            # EyeSide: -1.0 for Left Eye, 1.0 for Right Eye
            eye_side = -1.0 if i < (num_particles // 2) else 1.0
            
            # Random properties
            phase = random.random()
            speed_scale = random.uniform(0.7, 1.5)
            scale = random.uniform(0.5, 1.2)
            
            # Random unit direction in 3D (normalized)
            theta = random.uniform(0, 2.0 * 3.14159)
            phi = random.uniform(0, 3.14159)
            dir_x = sin_approx(phi) * cos_approx(theta)
            dir_y = cos_approx(phi)
            dir_z = sin_approx(phi) * sin_approx(theta)
            
            for v_idx in range(4):
                local_pos = quad_vertices[v_idx]
                pos_x = local_pos[0] * scale
                pos_y = local_pos[1] * scale
                pos_z = local_pos[2] * scale
                
                data = struct.pack(
                    '<ffffffffff',
                    pos_x, pos_y, pos_z,             # POSITION
                    eye_side, phase, speed_scale,    # NORMAL
                    dir_x, dir_y, dir_z, scale       # TANGENT
                )
                f.write(data)

def generate_efmi_vb(num_particles: int, output_path: str):
    """
    Generates an Endfield-style vertex buffer with 16-byte stride.
    Layout:
      Position: float3 (12 bytes) -> Local quad offsets
      Normal:   uint32 (4 bytes)  -> Packed custom parameters
    """
    quad_vertices = [
        (-0.5, -0.5, 0.0),
        ( 0.5, -0.5, 0.0),
        (-0.5,  0.5, 0.0),
        ( 0.5,  0.5, 0.0),
    ]

    with open(output_path, 'wb') as f:
        for i in range(num_particles):
            eye_side_val = 0 if i < (num_particles // 2) else 255
            phase_val = int(random.random() * 255)
            speed_val = int(random.uniform(0.7, 1.5) / 2.0 * 255)
            scale_val = int(random.uniform(0.5, 1.2) / 2.0 * 255)
            
            # Pack as a single uint32 (little endian)
            packed_normal = (scale_val << 24) | (speed_val << 16) | (phase_val << 8) | eye_side_val
            scale = random.uniform(0.5, 1.2)
            
            for v_idx in range(4):
                local_pos = quad_vertices[v_idx]
                pos_x = local_pos[0] * scale
                pos_y = local_pos[1] * scale
                pos_z = local_pos[2] * scale
                
                data = struct.pack(
                    '<fffI',
                    pos_x, pos_y, pos_z,
                    packed_normal
                )
                f.write(data)

def generate_texcoord_buf(num_particles: int, output_path: str, stride: int, num_uvs: int, include_color: str = None, color_val = (1.0, 1.0, 1.0, 1.0)):
    """
    Generates a Texcoord buffer with custom stride, UV layout count, and color settings.
    Each vertex is packed exactly to `stride` bytes.
    
    UV Layouts are float2 (8 bytes each).
    Color:
      - 'uint32': Packed 4-byte color (e.g. R8G8B8A8)
      - 'float4': 16-byte float4 color (R32G32B32A32)
      - None: No color
    """
    # Quad UVs: Bottom-Left, Bottom-Right, Top-Left, Top-Right
    uv_vertices = [
        (0.0, 1.0), # BL
        (1.0, 1.0), # BR
        (0.0, 0.0), # TL
        (1.0, 0.0), # TR
    ]

    with open(output_path, 'wb') as f:
        for i in range(num_particles):
            for v_idx in range(4):
                buf = bytearray(stride)
                u, v = uv_vertices[v_idx]
                
                # Write UVs
                for uv_idx in range(num_uvs):
                    offset = uv_idx * 8
                    if offset + 8 <= stride:
                        struct.pack_into('<ff', buf, offset, u, v)
                
                # Write optional color
                color_offset = num_uvs * 8
                if include_color == 'uint32' and color_offset + 4 <= stride:
                    # pack color as 4 bytes (R, G, B, A)
                    r, g, b, a = [int(c * 255) if isinstance(c, float) else int(c) for c in color_val]
                    struct.pack_into('<BBBB', buf, color_offset, r, g, b, a)
                elif include_color == 'float4' and color_offset + 16 <= stride:
                    r, g, b, a = [float(c) for c in color_val]
                    struct.pack_into('<ffff', buf, color_offset, r, g, b, a)
                
                f.write(buf)

def generate_blend_buf(num_particles: int, output_path: str, stride: int, bone_index: int):
    """
    Generates a Blend buffer containing BLENDWEIGHT (float4/half4) and BLENDINDICES (uint4/ubyte4).
    Each vertex is packed exactly to `stride` bytes.
    Usually we assign weight=1.0 to the target bone_index (for head/eye rigging).
    """
    with open(output_path, 'wb') as f:
        for i in range(num_particles):
            for v_idx in range(4):
                buf = bytearray(stride)
                
                # Assuming standard Hoyo layouts:
                # Type A: Stride 32 (Float4 Weight + Uint4 Indices)
                if stride == 32:
                    # Weight: 1.0 for the first slot, 0 for others
                    struct.pack_into('<ffff', buf, 0, 1.0, 0.0, 0.0, 0.0)
                    # Indices: bone_index in the first slot, 0 for others
                    struct.pack_into('<IIII', buf, 16, bone_index, 0, 0, 0)
                
                # Type B: Stride 24 (Float4 Weight + Ubyte4 Indices + 4 bytes padding)
                elif stride == 24:
                    struct.pack_into('<ffff', buf, 0, 1.0, 0.0, 0.0, 0.0)
                    struct.pack_into('<BBBB', buf, 16, bone_index, 0, 0, 0)
                
                # Type C: Stride 20 (Float4 Weight + Ubyte4 Indices)
                elif stride == 20:
                    struct.pack_into('<ffff', buf, 0, 1.0, 0.0, 0.0, 0.0)
                    struct.pack_into('<BBBB', buf, 16, bone_index, 0, 0, 0)

                # Type D: Stride 16 (Half4 Weight + Ubyte4 Indices + 4 bytes padding)
                elif stride == 16:
                    # We can use half float representation for weights (0x3c00 is 1.0 in float16)
                    struct.pack_into('<HHHH', buf, 0, 0x3c00, 0, 0, 0)
                    struct.pack_into('<BBBB', buf, 8, bone_index, 0, 0, 0)
                
                else:
                    # Default generic fallback: float4 weight at start, uint32 bone index
                    if stride >= 16:
                        struct.pack_into('<ffff', buf, 0, 1.0, 0.0, 0.0, 0.0)
                    if stride >= 20:
                        struct.pack_into('<I', buf, 16, bone_index)
                
                f.write(buf)

def generate_ib(num_particles: int, output_path: str, use_32bit: bool = False):
    """
    Generates a index buffer for drawing quads.
    For each quad (4 vertices), generates 6 indices (2 triangles).
    """
    fmt = '<I' if use_32bit else '<H'
    with open(output_path, 'wb') as f:
        for i in range(num_particles):
            v0 = 4 * i
            v1 = 4 * i + 1
            v2 = 4 * i + 2
            v3 = 4 * i + 3
            
            # Triangle 1
            f.write(struct.pack(fmt, v0))
            f.write(struct.pack(fmt, v1))
            f.write(struct.pack(fmt, v2))
            
            # Triangle 2
            f.write(struct.pack(fmt, v2))
            f.write(struct.pack(fmt, v1))
            f.write(struct.pack(fmt, v3))

# Math helper functions
def sin_approx(x):
    x = x % (2.0 * 3.14159)
    if x > 3.14159:
        x -= 3.14159
        sign = -1.0
    else:
        sign = 1.0
    return sign * (x - (x**3)/6.0 + (x**5)/120.0 - (x**7)/5040.0)

def cos_approx(x):
    return sin_approx(x + 3.14159 / 2.0)

# ==================== UNIT TESTS ====================
def run_tests():
    print("=== Running Buffer Generator Unit Tests ===")
    
    num_particles = 4  # 16 vertices total
    hoyo_vb_file = "test_hoyo_vb.buf"
    efmi_vb_file = "test_efmi_vb.buf"
    ib_16_file = "test_ib_16.buf"
    tex_16_file = "test_texcoord_16.buf"
    tex_24_file = "test_texcoord_24.buf"
    blend_24_file = "test_blend_24.buf"
    
    # 1. Hoyo VB Generation Test
    generate_hoyo_vb(num_particles, hoyo_vb_file)
    expected_hoyo_bytes = num_particles * 4 * 40
    actual_hoyo_bytes = os.path.getsize(hoyo_vb_file)
    print(f"Hoyo VB size: {actual_hoyo_bytes} bytes (Expected: {expected_hoyo_bytes})")
    assert actual_hoyo_bytes == expected_hoyo_bytes, "Hoyo VB byte length mismatch!"
    
    # 2. EFMI VB Generation Test
    generate_efmi_vb(num_particles, efmi_vb_file)
    expected_efmi_bytes = num_particles * 4 * 16
    actual_efmi_bytes = os.path.getsize(efmi_vb_file)
    print(f"EFMI VB size: {actual_efmi_bytes} bytes (Expected: {expected_efmi_bytes})")
    assert actual_efmi_bytes == expected_efmi_bytes, "EFMI VB byte length mismatch!"
    
    # 3. Texcoord Buffer Stride 16 (2 UVs) Test
    generate_texcoord_buf(num_particles, tex_16_file, stride=16, num_uvs=2)
    expected_tex_16_bytes = num_particles * 4 * 16
    actual_tex_16_bytes = os.path.getsize(tex_16_file)
    print(f"Texcoord 16 size: {actual_tex_16_bytes} bytes (Expected: {expected_tex_16_bytes})")
    assert actual_tex_16_bytes == expected_tex_16_bytes, "Texcoord 16 byte length mismatch!"
    with open(tex_16_file, 'rb') as f:
        # vertex 1 (bottom-right: u=1.0, v=1.0)
        f.read(16) # skip vertex 0
        v1_data = struct.unpack('<ffff', f.read(16))
        print(f"Vertex 1 Texcoord 16 Data: {v1_data}")
        assert v1_data == (1.0, 1.0, 1.0, 1.0), "UV mapping values incorrect!"
        
    # 4. Texcoord Buffer Stride 24 (2 UVs + float4 color) Test
    # Wait, 2 UVs = 16 bytes. float4 color = 16 bytes. Stride = 32.
    # If Stride = 24 with 2 UVs (16 bytes) + uint32 color (4 bytes) + 4 bytes padding:
    generate_texcoord_buf(num_particles, tex_24_file, stride=24, num_uvs=2, include_color='uint32', color_val=(255, 128, 64, 255))
    expected_tex_24_bytes = num_particles * 4 * 24
    actual_tex_24_bytes = os.path.getsize(tex_24_file)
    print(f"Texcoord 24 size: {actual_tex_24_bytes} bytes (Expected: {expected_tex_24_bytes})")
    assert actual_tex_24_bytes == expected_tex_24_bytes, "Texcoord 24 byte length mismatch!"
    with open(tex_24_file, 'rb') as f:
        f.read(24) # skip vertex 0
        # Vertex 1 has UV (1, 1), UV (1, 1), Color (255, 128, 64, 255), then 4 bytes padding (all 0)
        v1_raw = f.read(24)
        v1_uvs = struct.unpack('<ffff', v1_raw[0:16])
        v1_color = struct.unpack('<BBBB', v1_raw[16:20])
        print(f"Vertex 1 Texcoord 24 Data: UVs={v1_uvs}, Color={v1_color}")
        assert v1_uvs == (1.0, 1.0, 1.0, 1.0), "UV values mismatch"
        assert v1_color == (255, 128, 64, 255), "Color values mismatch"
        
    # 5. Blend Buffer Stride 24 Test
    generate_blend_buf(num_particles, blend_24_file, stride=24, bone_index=15)
    expected_blend_24_bytes = num_particles * 4 * 24
    actual_blend_24_bytes = os.path.getsize(blend_24_file)
    print(f"Blend 24 size: {actual_blend_24_bytes} bytes (Expected: {expected_blend_24_bytes})")
    assert actual_blend_24_bytes == expected_blend_24_bytes, "Blend 24 byte length mismatch!"
    with open(blend_24_file, 'rb') as f:
        v0_raw = f.read(24)
        v0_weights = struct.unpack('<ffff', v0_raw[0:16])
        v0_indices = struct.unpack('<BBBB', v0_raw[16:20])
        print(f"Vertex 0 Blend 24 Data: Weights={v0_weights}, Indices={v0_indices}")
        assert v0_weights == (1.0, 0.0, 0.0, 0.0), "Blend weights mismatch"
        assert v0_indices[0] == 15, "Blend indices target bone mismatch"

    # Cleanup test files
    for file in [hoyo_vb_file, efmi_vb_file, ib_16_file, tex_16_file, tex_24_file, blend_24_file]:
        if os.path.exists(file):
            os.remove(file)
            
    print("=== All Tests Passed Successfully! ===")

if __name__ == '__main__':
    # 1. Run unit tests
    run_tests()
    
    # 2. Configurable Generation parameters (Modify here as needed)
    NUM_PARTICLES = 32
    TARGET_BONE_INDEX = 15  # bone index to skin the particles to (e.g. head/eye bone)
    
    # Texcoord Buffer custom configuration:
    TEXCOORD_STRIDE = 24    # Change to 8, 16, 24, 32 etc.
    NUM_UVS = 2             # Number of UV maps (1, 2, or 3)
    COLOR_FORMAT = 'uint32' # 'uint32' (4-byte), 'float4' (16-byte), or None
    COLOR_VALUE = (255, 255, 255, 255) # White color default
    
    # Paths (Will be generated inside the QA directory)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    hoyo_vb_path = os.path.join(script_dir, "eye_particles_Position.buf")
    efmi_vb_path = os.path.join(script_dir, "eye_particles_efmi_vb0.buf")
    texcoord_path = os.path.join(script_dir, "eye_particles_Texcoord.buf")
    blend_path = os.path.join(script_dir, "eye_particles_Blend.buf")
    ib_path = os.path.join(script_dir, "eye_particles.ib")
    
    # Perform output generation
    print(f"\nGenerating particle buffers inside: {script_dir}")
    
    generate_hoyo_vb(NUM_PARTICLES, hoyo_vb_path)
    print(f" -> Generated: {os.path.basename(hoyo_vb_path)} (Hoyo Position VB, stride=40)")
    
    generate_efmi_vb(NUM_PARTICLES, efmi_vb_path)
    print(f" -> Generated: {os.path.basename(efmi_vb_path)} (EFMI VB, stride=16)")
    
    generate_texcoord_buf(NUM_PARTICLES, texcoord_path, stride=TEXCOORD_STRIDE, num_uvs=NUM_UVS, include_color=COLOR_FORMAT, color_val=COLOR_VALUE)
    print(f" -> Generated: {os.path.basename(texcoord_path)} (Texcoord VB, stride={TEXCOORD_STRIDE}, UVs={NUM_UVS}, Color={COLOR_FORMAT})")
    
    # Hoyo character meshes also have a Blend buffer. Let's make one:
    # Stride of blend buffer is usually 24 or 32. Let's default to 24.
    generate_blend_buf(NUM_PARTICLES, blend_path, stride=24, bone_index=TARGET_BONE_INDEX)
    print(f" -> Generated: {os.path.basename(blend_path)} (Blend VB, stride=24, BoneIndex={TARGET_BONE_INDEX})")
    
    generate_ib(NUM_PARTICLES, ib_path, use_32bit=True)
    print(f" -> Generated: {os.path.basename(ib_path)} (Index Buffer, 32-bit uint)")
    
    print("\nGeneration completed successfully!")
