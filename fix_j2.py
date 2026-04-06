import os

path = 'rztemplate/rz_helper.j2'

# Robust reading with fallback encoding
try:
    with open(path, 'rb') as f:
        content = f.read().decode('utf-8')
except UnicodeDecodeError:
    with open(path, 'rb') as f:
        content = f.read().decode('cp1251')

# Replace the END tag
old_tag = ';[META-INFO] [END] [DELETE] [MESH] [{{ obj_name }}]'
new_tag = '{%- if mesh_tags %}\n    ;[META-INFO] [END] [DELETE] [MESH] [{{ obj_name }}] {{ mesh_tags }}\n    {%- endif %}'

if old_tag in content:
    content = content.replace(old_tag, new_tag)
    print(f"Successfully replaced END tag in {path}")
else:
    print(f"END tag not found or already fixed in {path}")

# Write back as UTF-8
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
