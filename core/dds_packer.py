# RZMenu/core/dds_packer.py
import bpy
import os
import subprocess
import tempfile
import numpy as np

def get_texconv_path():
    """Returns the path to texconv.exe if found in libs/tools or system PATH."""
    addon_dir = os.path.dirname(os.path.dirname(__file__))
    potential_paths = [
        os.path.join(addon_dir, "libs", "texconv.exe"),
        os.path.join(addon_dir, "tools", "texconv.exe"),
        os.path.join(addon_dir, "texconv.exe"),
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            return path
            
    # Fallback to system PATH
    import shutil
    sys_path = shutil.which("texconv.exe")
    if sys_path:
        return sys_path
        
    return None

def pack_to_dds(pixels, width, height, output_path, dds_format='BC7_UNORM'):
    """
    Packs a numpy pixel buffer (RGBA float32) to a DDS file using texconv.exe.
    Returns (bool, message).
    """
    texconv = get_texconv_path()
    if not texconv:
        return False, "texconv.exe not found. Please place it in RZMenu/libs/tools/"

    # 1. Create a temporary PNG/TGA to pass to texconv
    # Blender's image.save_render or numpy->PIL->file
    temp_dir = tempfile.gettempdir()
    temp_input = os.path.join(temp_dir, f"rzm_atlas_temp_{os.getpid()}.tga")
    
    try:
        from PIL import Image
        # Convert float32 [0..1] to uint8 [0..255]
        # Blender pixels are RGBA, scanline by scanline bottom-to-top
        # We need to flip it for standard image libraries
        arr = np.array(pixels).reshape((height, width, 4))
        arr = np.flipud(arr) # Flip Y
        arr = (np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
        
        img = Image.fromarray(arr, 'RGBA')
        img.save(temp_input)
    except Exception as e:
        return False, f"Failed to create temporary image: {str(e)}"

    # 2. Run texconv
    # Command: texconv.exe -f <format> -y -o <out_dir> <temp_input>
    out_dir = os.path.dirname(output_path)
    
    cmd = [
        texconv,
        "-f", dds_format,
        "-m", "1",
        "-y", # overwrite
        "-o", out_dir
    ]

    # If target is sRGB, tell texconv input is also sRGB to avoid "whitening" (double-gamma)
    if "SRGB" in dds_format.upper():
        cmd.append("-srgbi")
    
    cmd.append(temp_input)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Rename temp_input.dds to output_path if needed
        generated_dds = os.path.join(out_dir, os.path.splitext(os.path.basename(temp_input))[0] + ".dds")
        if os.path.exists(generated_dds):
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(generated_dds, output_path)
            
            # Clean up temp input
            if os.path.exists(temp_input):
                os.remove(temp_input)
                
            return True, f"Successfully exported DDS ({dds_format})"
        else:
            return False, "texconv finished but no DDS was generated."
    except subprocess.CalledProcessError as e:
        return False, f"texconv error: {e.stderr}"
    except Exception as e:
        return False, f"Unexpected error during DDS export: {str(e)}"
    finally:
        # Cleanup
        if os.path.exists(temp_input):
            try: os.remove(temp_input)
            except: pass
