ini_path = 'G:/XXMI/ZZMI/Mods/Promeia/Promeia.ini'

with open(ini_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace hair recording with frame gate
hair_target = """run = CustomShaderComputeHairHistory
run = CustomShaderWriteHairHistory"""

hair_replacement = """if $_last_frame_hair != frame
	$_last_frame_hair = frame
	run = CustomShaderComputeHairHistory
	run = CustomShaderWriteHairHistory
endif"""

content = content.replace(hair_target, hair_replacement)

# Replace legs recording with frame gate
legs_target = """run = CustomShaderComputeLegsHistory
run = CustomShaderWriteLegsHistory"""

legs_replacement = """if $_last_frame_legs != frame
	$_last_frame_legs = frame
	run = CustomShaderComputeLegsHistory
	run = CustomShaderWriteLegsHistory
endif"""

content = content.replace(legs_target, legs_replacement)

with open(ini_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Frame gates added successfully to Promeia.ini!")
