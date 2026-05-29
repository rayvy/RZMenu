ini_path = 'G:/XXMI/ZZMI/Mods/Promeia/Promeia.ini'

with open(ini_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix dispatch syntax in recording shaders
content = content.replace("dispatch = 8\n", "dispatch = 8, 1, 1\n")
content = content.replace("dispatch = 27\n", "dispatch = 27, 1, 1\n")

# 2. Fix the overridden CommandListTextureOverridePromeiaHairB block
# Replace the previous buggy if-endif logic
buggy_hair = """if $_last_frame_hair != frame
	$_last_frame_hair = frame
	run = CustomShaderComputeHairHistory
	run = CustomShaderWriteHairHistory
endif"""

correct_hair = """if $RZM_NewFrameHair == 1
	$RZM_NewFrameHair = 0
	run = CustomShaderComputeHairHistory
	run = CustomShaderWriteHairHistory
endif"""

content = content.replace(buggy_hair, correct_hair)

# 3. Fix the overridden CommandListTextureOverridePromeiaLegsA block
buggy_legs = """if $_last_frame_legs != frame
	$_last_frame_legs = frame
	run = CustomShaderComputeLegsHistory
	run = CustomShaderWriteLegsHistory
endif"""

correct_legs = """if $RZM_NewFrameLegs == 1
	$RZM_NewFrameLegs = 0
	run = CustomShaderComputeLegsHistory
	run = CustomShaderWriteLegsHistory
endif"""

content = content.replace(buggy_legs, correct_legs)

# 4. Insert global flag initializers inside the [Present] block
present_match = content.find("[Present]")
if present_match != -1:
    insert_pos = content.find("\n", present_match)
    content = content[:insert_pos+1] + "$RZM_NewFrameHair = 1\n$RZM_NewFrameLegs = 1\n" + content[insert_pos+1:]

with open(ini_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Correct 3DMigoto syntax gates and dispatch formats successfully applied!")
