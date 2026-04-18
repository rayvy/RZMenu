import re

path = r'c:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\rztemplate\modules\core.j2'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# I need to cleanly repair everything.
# Let's clean up broken lines.
text = re.sub(r'\n \\ = 7\n.*?\nx111 = 0\n', '\n$slot_count = 7\nz111 = $data_offset\nx111 = 0\n', text, flags=re.DOTALL)
text = re.sub(r'\n \\ = 7\n.*?\nx111 = 0\n', '\n$slot_count = 7\nz111 = $data_offset\nx111 = 0\n', text, flags=re.DOTALL)
text = re.sub(r'\\ = 7\nz111 = \\nx111 = 0', '$slot_count = 7\nz111 = $data_offset\nx111 = 0', text)

# For missing increment: $di_count = $di_count + 1 is still there. We just replace that.
text = re.sub(r'(\$di_count = \$di_count \+ 1)', r'$data_offset = $data_offset + $slot_count\n\1', text)

# There may be duplicates if we already put `$data_offset = $data_offset + ` previously, we need to clean them out.
text = re.sub(r'\$data_offset = \$data_offset \+ \$slot_count\n\$data_offset = \$data_offset \+ \$slot_count\n\$di_count = \$di_count \+ 1', r'$data_offset = $data_offset + $slot_count\n$di_count = $di_count + 1', text)


with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
