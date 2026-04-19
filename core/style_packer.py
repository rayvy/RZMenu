import os
import struct

STYLE_SLOT_COUNT = 12

def pack_styles(scene, export_dir):
    """
    Packs RZMenuStyle properties into a binary file `styles.bin`.
    Each style occupies `STYLE_SLOT_COUNT` float4 slots.
    """
    styles = scene.rzm.styles
    style_buffer = bytearray()
    
    # Flags mapping
    BIT_SHADOW      = 1 << 0
    BIT_GLOW        = 1 << 1
    BIT_OUTLINE     = 1 << 2
    BIT_GRAYSCALE   = 1 << 3
    BIT_CHROMATIC   = 1 << 4
    BIT_GRADIENT    = 1 << 5
    BIT_ANIM_RESIZE = 1 << 6
    BIT_ANIM_SHEEN  = 1 << 7
    BIT_ANIM_ROTATE = 1 << 8
    BIT_FN_FIXRATIO = 1 << 9
    BIT_BLUR        = 1 << 10
    BIT_BLUR_MASK   = 1 << 11

    def pack_empty_style(buf):
        # Slot 0 to 11 (12 slots of float4) filled with zeros
        buf.extend(struct.pack('<Ifff', 0, 0.0, 0.0, 0.0)) # Slot 0
        for _ in range(11):
            buf.extend(struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0))

    if len(styles) == 0:
        pack_empty_style(style_buffer)
    else:
        for style in styles:
            flags = 0
            if style.use_shadow: flags |= BIT_SHADOW
            if style.use_glow: flags |= BIT_GLOW
            if style.use_outline: flags |= BIT_OUTLINE
            if style.use_grayscale: flags |= BIT_GRAYSCALE
            if style.use_chromatic: flags |= BIT_CHROMATIC
            if style.use_gradient: flags |= BIT_GRADIENT
            if style.anim_hover_resize: flags |= BIT_ANIM_RESIZE
            if style.anim_hover_sheen: flags |= BIT_ANIM_SHEEN
            if style.anim_rotate: flags |= BIT_ANIM_ROTATE
            if style.fn_fix_ratio: flags |= BIT_FN_FIXRATIO
            if style.use_blur: flags |= BIT_BLUR
            if style.use_blur_mask: flags |= BIT_BLUR_MASK

            # Slot 0: Flags (uint), unused, unused, unused
            style_buffer.extend(struct.pack('<Ifff', flags, 0.0, 0.0, 0.0))
            
            # Slot 1: Shadow - Offset X, Offset Y, Blur, Unused
            style_buffer.extend(struct.pack('<ffff', style.shadow_offset[0], style.shadow_offset[1], style.shadow_blur, 0.0))
            # Slot 2: Shadow Color
            style_buffer.extend(struct.pack('<ffff', *style.shadow_color))
            
            # Slot 3: Glow - Radius, Intensity, Unused, Unused
            style_buffer.extend(struct.pack('<ffff', style.glow_radius, style.glow_intensity, 0.0, 0.0))
            # Slot 4: Glow Color
            style_buffer.extend(struct.pack('<ffff', *style.glow_color))
            
            # Slot 5: Outline - Thickness, Unused, Unused, Unused
            style_buffer.extend(struct.pack('<ffff', style.outline_thickness, 0.0, 0.0, 0.0))
            # Slot 6: Outline Color
            style_buffer.extend(struct.pack('<ffff', *style.outline_color))
            
            # Slot 7: Grayscale Amount, Chromatic Offset, Gradient Angle, Hover Scale Factor
            style_buffer.extend(struct.pack('<ffff', style.grayscale_amount, style.chromatic_offset, style.grad_angle, style.hover_scale_factor))
            
            # Slot 8: Gradient Color 1
            style_buffer.extend(struct.pack('<ffff', *style.grad_color_1))
            # Slot 9: Gradient Color 2
            style_buffer.extend(struct.pack('<ffff', *style.grad_color_2))
            
            # Slot 10: Sheen Speed, Width, Rotate Speed, Blur Strength
            style_buffer.extend(struct.pack('<ffff', style.sheen_speed, style.sheen_width, style.rotate_speed, style.blur_strength))
            # Slot 11: Sheen Color
            style_buffer.extend(struct.pack('<ffff', *style.sheen_color))

    # Save to file
    res_dir = os.path.join(export_dir, "res")
    os.makedirs(res_dir, exist_ok=True)
    
    bin_path = os.path.join(res_dir, "styles.bin")
    with open(bin_path, 'wb') as f:
        f.write(style_buffer)

    return True
