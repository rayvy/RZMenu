import bpy
m = bpy.data.meshes.new('test')
m.vertices.add(10)
a = m.attributes.new(name='test_attr', type='FLOAT_VECTOR', domain='POINT')
print("Len of a.data:", len(a.data))
