# RZMenu/data/constants.py

# Default template text for Mod Info editor.
# Uses {{tag}} syntax resolved by parse_and_replace_tags in meta.j2
DEFAULT_MOD_INFO_TEXT = """; === {{mod_name}} ===
; Author: {{author_name}}
; Character: {{character_name}} — {{outfit_name}}
; Version: {{version_num}}
; Game: {{game_name}}
; Keybind: {{menu_keybind}}
; Requirements: {{requirements}}
; Credits: {{community_respect}}"""

FX_COMMANDS = [
    ('CommandListShaderPreset0', "ShaderPreset-HOVER UPSCALE", "ShaderPres"),
    ('CommandListShaderPreset1', "ShaderPreset-HOVER UPSCALE 3D", "ShaderPres"),
    ('CommandListShaderPreset2', "ShaderPreset-METALLIC HOVER OUTLINE SHINE", "ShaderPres"),
    ('CommandListShaderPreset3', "ShaderPreset-WHITE OUTLINE", "ShaderPres"),
    ('CommandListShaderPreset4', "ShaderPreset-SHADOW SHADER", "ShaderPres"),
    ('CommandListShaderPreset5', "ShaderPreset-CHROMMATIC ABBERATION", "ShaderPres"),
    ('CommandListShaderPreset6', "ShaderPreset-NOTHING", "ShaderPres"),
    ('CommandListShaderPreset7', "ShaderPreset-WHITE OUTLINE2", "ShaderPres"),
    ('CommandListShaderPreset8', "ShaderPreset-Metallic SHINE", "ShaderPres"),
    ('CommandListShaderPreset9', "ShaderPreset-Metallic Sticker ROTATED", "ShaderPres"),
    ('CommandListShaderPreset10', "ShaderPreset-Rotate", "ShaderPres"),
    ('CommandListShaderPreset11', "ShaderPreset-BlurMask", "ShaderPres"),
    
]

FN_COMMANDS = [
    ('CommandListCoreFnFixRatio', "Fix Ratio", "Сохранять пропорции")
]