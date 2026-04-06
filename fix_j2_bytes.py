import os

path = 'rztemplate/rz_helper.j2'

# Read as bytes to avoid encoding issues
with open(path, 'rb') as f:
    content = f.read()

# Replace the END tag using bytes
old_tag = b';[META-INFO] [END] [DELETE] [MESH] [{{ obj_name }}]'
new_tag = b'{%- if mesh_tags %}\n    ;[META-INFO] [END] [DELETE] [MESH] [{{ obj_name }}] {{ mesh_tags }}\n    {%- endif %}'

if old_tag in content:
    content = content.replace(old_tag, new_tag)
    print(f"Successfully replaced END tag in {path} (byte-level)")
    # Save the updated bytes
    with open(path, 'wb') as f:
        f.write(content)
else:
    print(f"END tag not found or already fixed in {path} (byte-level)")
    # Just to be sure, let's print a small snippet around where we expect it
    idx = content.find(b'[MESH]')
    if idx != -1:
        print(f"Snippet near [MESH]: {content[idx-20:idx+60]}")
