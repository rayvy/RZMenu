import bpy
import os
from ..utils.font_utils import find_system_font

class RZM_OT_ExportFonts(bpy.types.Operator):
    bl_idname = "rzm.export_fonts"
    bl_label = "Export Font Atlases"
    bl_description = "Generate font atlases using PIL and save them to the mod export directory"

    def execute(self, context):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            self.report({'ERROR'}, "PIL (Pillow) is not installed. Please install Pillow in Blender's Python environment to generate font atlases.")
            return {'CANCELLED'}

        # Get mod output folder
        scene = context.scene
        rzm = scene.rzm
        game = rzm.game.selection
        
        out_dir = ""
        if game in ['GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'] and hasattr(scene, "xxmi"):
            out_dir = scene.xxmi.destination_path
        elif game == 'WutheringWaves' and hasattr(scene, "wwmi_tools_settings"):
            out_dir = scene.wwmi_tools_settings.mod_output_folder
        elif game == 'ArknightsEndfield' and hasattr(scene, "efmi_tools_settings"):
            out_dir = scene.efmi_tools_settings.mod_output_folder

        if not out_dir:
            self.report({'WARNING'}, "Target mod export directory not found or invalid. Font generation skipped.")
            return {'CANCELLED'}
            
        out_dir = bpy.path.abspath(out_dir)
        
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError as e:
                self.report({'ERROR'}, f"Could not create output directory: {e}")
                return {'CANCELLED'}

        # Force text pack to build the character map cache BEFORE fonts are generated
        try:
            from ..core.text_packer import pack_project_text
            pack_project_text(scene, out_dir)
        except Exception as e:
            self.report({'WARNING'}, f"Failed to pre-pack text for font mapping: {e}")

        # Determine which slots are actually used in the UI
        used_slots = set()
        for elem in rzm.elements:
            if hasattr(elem, 'elem_class') and elem.elem_class in ('TEXT', 'BUTTON') and not getattr(elem, 'disable_export', False):
                used_slots.add(getattr(elem, 'font_slot', 0))
                
        # Also always gen slot 0 as fallback just in case
        used_slots.add(0)

        # Determine output format and extension
        atlas_format = rzm.export_settings.atlas_format
        ext = atlas_format.lower()
        
        created_files = []
        res_dir = os.path.join(out_dir, "res")
        os.makedirs(res_dir, exist_ok=True)

        for i, slot in enumerate(rzm.fonts):
            if i not in used_slots:
                continue
                
            font_path = ""
            if slot.font_source == 'CUSTOM' and slot.custom_path:
                font_path = bpy.path.abspath(slot.custom_path)
            else:
                sys_font_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
                font_path = os.path.join(sys_font_dir, 'arial.ttf')
            
            font_index = getattr(slot, 'font_index', 0)
            
            # Safe mechanism: check file
            if not os.path.exists(font_path) or not os.path.isfile(font_path):
                self.report({'WARNING'}, f"Font not found at {font_path}, falling back to Arial.")
                font_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows') + '\\Fonts\\', 'arial.ttf')
                if not os.path.exists(font_path):
                    self.report({'ERROR'}, f"Arial fallback font not found in Windows/Fonts. Generation failed for slot {i}.")
                    continue

            output_file = os.path.join(res_dir, f"font_atlas_{i}.{ext}")
            try:
                if atlas_format == 'DDS':
                    # Export as temporary PNG first
                    import tempfile
                    temp_png = os.path.join(tempfile.gettempdir(), f"rzm_font_temp_{i}_{os.getpid()}.png")
                    self.create_font_atlas(slot, font_path, temp_png, font_index, Image, ImageDraw, ImageFont)
                    
                    # Convert to DDS
                    from ..core.dds_packer import get_texconv_path
                    texconv = get_texconv_path()
                    if texconv:
                        import subprocess
                        # Use R8G8B8A8_UNORM for fonts! 
                        # BC7 is lossy and corrupts the metadata pixels in the bottom rows.
                        cmd = [texconv, "-f", "R8G8B8A8_UNORM", "-y", "-o", res_dir, temp_png]
                        subprocess.run(cmd, capture_output=True, check=True)
                        
                        # texconv creates <basename_of_temp_png>.dds in res_dir
                        generated_dds = os.path.join(res_dir, os.path.splitext(os.path.basename(temp_png))[0] + ".dds")
                        
                        if os.path.exists(generated_dds):
                            if os.path.exists(output_file):
                                os.remove(output_file)
                            os.rename(generated_dds, output_file)
                            created_files.append(output_file)
                        
                        # Cleanup temp png
                        if os.path.exists(temp_png):
                            os.remove(temp_png)
                    else:
                        self.report({'ERROR'}, "texconv.exe not found. Font DDS export failed.")
                else:
                    # Standard PNG export
                    self.create_font_atlas(slot, font_path, output_file, font_index, Image, ImageDraw, ImageFont)
                    created_files.append(output_file)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to generate atlas for slot {i}: {e}")
                import traceback
                traceback.print_exc()

        if created_files:
            self.report({'INFO'}, f"Successfully exported {len(created_files)} font atlases.")
            
        return {'FINISHED'}

    def create_font_atlas(self, slot, font_path, output_path, font_index=0, Image=None, ImageDraw=None, ImageFont=None):
        cell_size = slot.cell_size
        density = slot.density
        
        grid_size = 16
        
        from ..core.text_packer import RZMTextMapCache
        import math, os
        custom_chars = RZMTextMapCache.custom_chars
                
        base_ascii_len = 96 # 32 to 127 inclusive
        num_chars = base_ascii_len + len(custom_chars)
        rows_glyphs = math.ceil(num_chars / grid_size)
        rows_meta = 1
        
        img_w = int(grid_size * cell_size)
        img_h = int((rows_glyphs + rows_meta) * cell_size)
        meta_y = int(rows_glyphs * cell_size)
        
        atlas = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        
        font_size = int(cell_size * density)
        try:
            # --- Variable Font Support (Pillow 9.1.0+) ---
            variations = {}
            style_lower = slot.font_style_name.lower()
            
            # Common Weight Mapping
            if "thin" in style_lower: variations['wght'] = 100
            elif "extra light" in style_lower: variations['wght'] = 200
            elif "light" in style_lower: variations['wght'] = 300
            elif "medium" in style_lower: variations['wght'] = 500
            elif "semibold" in style_lower: variations['wght'] = 600
            elif "bold" in style_lower: variations['wght'] = 700
            elif "extrabold" in style_lower: variations['wght'] = 800
            elif "black" in style_lower: variations['wght'] = 900
            
            # Slant/Italic
            if "italic" in style_lower or "oblique" in style_lower:
                variations['ital'] = 1.0
            
            font = ImageFont.truetype(font_path, font_size, index=font_index, variations=variations)
        except Exception:
            # Fallback for older Pillow or non-variable fonts
            try:
                font = ImageFont.truetype(font_path, font_size, index=font_index)
            except Exception:
                font = ImageFont.truetype(font_path, font_size, index=0)

        pen_x = int(cell_size * 0.1)
        pen_y = int(cell_size * 0.75)
        
        for i in range(num_chars):
            if i < base_ascii_len:
                char = chr(i + 32)
            else:
                char = custom_chars[i - base_ascii_len]
            
            col = i % grid_size
            row = i // grid_size
            
            temp_img = Image.new("RGBA", (int(cell_size), int(cell_size)), (0, 0, 0, 0))
            draw = ImageDraw.Draw(temp_img)
            draw.text((pen_x, pen_y), char, font=font, fill=(255, 255, 255, 255), anchor="ls")
            
            bbox = temp_img.getbbox()
            advance = font.getlength(char)
            
            if bbox:
                off_x, off_y, right, bottom = bbox
                glyph_w = right - off_x
                glyph_h = bottom - off_y
                atlas.paste(temp_img, (int(col * cell_size), int(row * cell_size)), temp_img)
            else:
                off_x, off_y, glyph_w, glyph_h = 0, 0, 0, 0
                
            d1_r = int(round((advance / (2 * cell_size)) * 255))
            d1_g = int(round((glyph_w / (2 * cell_size)) * 255))
            d1_b = int(round(((off_x / cell_size + 1) / 2) * 255))
            d1_a = int(round(((off_y / cell_size + 1) / 2) * 255))
            
            d2_r = int(round((glyph_h / (2 * cell_size)) * 255))
            d2_g = 0
            d2_b = 0
            d2_a = 255
            
            d1_r, d1_g, d1_b, d1_a = [max(0, min(255, v)) for v in (d1_r, d1_g, d1_b, d1_a)]
            d2_r = max(0, min(255, d2_r))
            
            meta_x = i % img_w
            meta_y_offset = (i // img_w) * 2
            
            atlas.putpixel((meta_x, meta_y + meta_y_offset), (d1_r, d1_g, d1_b, d1_a))
            atlas.putpixel((meta_x, meta_y + meta_y_offset + 1), (d2_r, d2_g, d2_b, d2_a))
            
        atlas.save(output_path)

classes_to_register = [RZM_OT_ExportFonts]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
