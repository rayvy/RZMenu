# Gret Shape Key Utils for RZMenu
# Derived from Gret (GPL v3)
# Original author: Gret contributors
# Adapted for standalone use in RZMenu
#
# USAGE INSTRUCTIONS:
# 1. Manual call (UI):
#    bpy.ops.rz.shape_key_apply_modifiers('INVOKE_DEFAULT')
#    This will open a dialog to select which modifiers to apply.
#
# 2. Automated call (Script):
#    bpy.ops.rz.shape_key_apply_modifiers()
#    By default, it applies all visible viewport modifiers (except Armatures).
#
# 3. Targeted call (Specific Modifiers):
#    mask = [False] * 32
#    mask[0] = True # Apply only the first modifier
#    bpy.ops.rz.shape_key_apply_modifiers(modifier_mask=mask)

import bpy
import bmesh
import numpy as np
from collections import namedtuple, defaultdict
from contextlib import contextmanager
from itertools import zip_longest

# --- HELPERS (Extracted from Gret) ---

def get_layers_recursive(layer):
    yield layer
    for child in layer.children:
        yield from get_layers_recursive(child)

def select_only(context, objs):
    """Ensures only the given object or objects are selected."""
    for obj in context.selected_objects:
        obj.select_set(False)
    
    if not hasattr(objs, "__iter__"):
        objs = (objs,)
        
    for obj in objs:
        try:
            obj.hide_viewport = False
            obj.hide_select = False
            obj.select_set(True)
            context.view_layer.objects.active = obj
        except ReferenceError:
            pass

def get_object_context_override(active_obj, selected_objs=None):
    if selected_objs is None:
        selected_objs = []
    selected_objs = list(selected_objs)
    if active_obj and active_obj not in selected_objs:
        selected_objs.append(active_obj)
    elif not active_obj and selected_objs:
        active_obj = selected_objs[0]
    return {
        'object': active_obj,
        'active_object': active_obj,
        'selected_objects': selected_objs,
        'selected_editable_objects': selected_objs,
    }

def with_object(operator, active_obj, *args, **kwargs):
    """Run operator on a single active object, which will also be the only selected object."""
    with bpy.context.temp_override(**get_object_context_override(active_obj)):
        operator(*args, **kwargs)

def get_modifier_mask(obj, key=None):
    """Return a modifier mask for use with shape_key_apply_modifiers."""
    if callable(key):
        mask = [key(modifier) for modifier in obj.modifiers]
    elif hasattr(key, '__iter__'):
        mask = [bool(el) for el in key]
    else:
        mask = [True] * len(obj.modifiers)
    return mask[:32] + [False] * (32 - len(mask))

def get_dist_sq(a, b):
    """Returns the square distance between two 3D vectors."""
    x, y, z = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return x*x + y*y + z*z

def _select_mesh_elements(collection, select=True, indices=None, key=None):
    values = np.zeros(len(collection), dtype=bool)
    collection.foreach_set('hide', values)

    if select:
        if key is None and indices is None:
            values.fill(True)
        elif key is None:
            values[indices] = True
        elif indices is None:
            values = [bool(key(el)) for el in collection]
        else:
            for index in indices:
                values[index] = bool(key(collection[index]))

    collection.foreach_set('select', values)
    return np.sum(values)

def edit_mesh_elements(obj, type='VERT', indices=None, key=None):
    """Enters edit mode and selects elements of a mesh to be operated on."""
    assert obj.type == 'MESH' and obj.mode == 'OBJECT'
    mesh = obj.data

    select_only(bpy.context, obj)
    num_verts_selected = _select_mesh_elements(mesh.vertices, type == 'VERT', indices, key)
    num_edges_selected = _select_mesh_elements(mesh.edges, type == 'EDGE', indices, key)
    num_faces_selected = _select_mesh_elements(mesh.polygons, type == 'FACE', indices, key)

    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_mode(type=type)

    return (num_verts_selected if type == 'VERT'
        else num_edges_selected if type == 'EDGE'
        else num_faces_selected)

class PropOp(namedtuple('PropOp', 'struct prop_name value')):
    def revert(self, context):
        setattr(self.struct, self.prop_name, self.value)

class CallOp(namedtuple('CallOp', 'func args kwargs')):
    def revert(self, context):
        self.func(*self.args, **self.kwargs)

class SelectionOp(namedtuple('SelectionOp', 'selected_objects active_object collection_hide layer_hide object_hide')):
    def revert(self, context):
        for collection, hs, hv, hr in self.collection_hide:
            try:
                collection.hide_select, collection.hide_viewport, collection.hide_render = hs, hv, hr
            except ReferenceError: pass
        for layer, hv, ex in self.layer_hide:
            try:
                layer.hide_viewport, layer.exclude = hv, ex
            except ReferenceError: pass
        for obj, hs, hv, hr in self.object_hide:
            try:
                obj.hide_select, obj.hide_viewport, obj.hide_render = hs, hv, hr
            except ReferenceError: pass
        select_only(context, self.selected_objects)
        context.view_layer.objects.active = self.active_object

class SaveState:
    def __init__(self, context):
        self.context = context
        self.operations = []

    def revert(self):
        while self.operations:
            op = self.operations.pop()
            op.revert(self.context)

    def mode(self):
        if self.context.active_object:
            self.operations.append(CallOp(bpy.ops.object.mode_set, (self.context.active_object.mode,), {}))

    def prop(self, struct, prop_name, value=None):
        saved_val = getattr(struct, prop_name)
        if value is not None:
            setattr(struct, prop_name, value)
        self.operations.append(PropOp(struct, prop_name, saved_val))

class SaveContext:
    def __init__(self, context, name=""):
        self.save = SaveState(context)
    def __enter__(self):
        return self.save
    def __exit__(self, exc_type, exc_value, traceback):
        self.save.revert()

# --- MAIN LOGIC ---

class ShapeKeyInfo(namedtuple('ShapeKeyInfo', 'coords interpolation mute name slider_max slider_min value vertex_group')):
    """Helper to preserve shape key information and handle vertex count changes."""
    __slots__ = ()
    
    @classmethod
    def from_shape_key(cls, shape_key):
        coords = np.empty(len(shape_key.data) * 3, dtype=np.single)
        shape_key.data.foreach_get('co', coords)
        return cls(
            coords=coords,
            interpolation=shape_key.interpolation,
            mute=shape_key.mute,
            name=shape_key.name,
            slider_max=shape_key.slider_max,
            slider_min=shape_key.slider_min,
            value=shape_key.value,
            vertex_group=shape_key.vertex_group,
        )

    def get_coords_from(self, vertices):
        # Resize the numpy array to match new vertex count after modifiers
        self.coords.resize(len(vertices) * 3, refcheck=False)
        vertices.foreach_get('co', self.coords)

    def put_coords_into(self, vertices):
        vertices.foreach_set('co', self.coords)

def weld_mesh(mesh, weld_map):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    targetmap = {bm.verts[src_idx]: bm.verts[dst_idx] for src_idx, dst_idx in weld_map.items()}
    bmesh.ops.weld_verts(bm, targetmap=targetmap)
    bm.to_mesh(mesh)
    bm.free()

def apply_modifier(modifier):
    try:
        with_object(bpy.ops.object.modifier_apply, modifier.id_data, modifier=modifier.name)
    except RuntimeError:
        print(f"Couldn't apply {modifier.type} modifier {modifier.name}")

class ModifierHandler:
    modifier_type = None
    apply_post = False
    def __init__(self, modifier):
        self.modifier_name = modifier.name
    @classmethod
    def poll(cls, modifier):
        return cls.modifier_type is None or modifier.type == cls.modifier_type
    def apply(self, obj):
        apply_modifier(obj.modifiers[self.modifier_name])

class MirrorModifierHandler(ModifierHandler):
    modifier_type = 'MIRROR'
    def __init__(self, modifier):
        super().__init__(modifier)
        self.merge_dist = modifier.merge_threshold
        self.num_mirrors = sum(modifier.use_axis)
        self.weld_map = None
    @classmethod
    def poll(cls, modifier):
        return super().poll(modifier) and modifier.use_mirror_merge and any(modifier.use_axis)
    def apply(self, obj):
        modifier = obj.modifiers[self.modifier_name]
        modifier.use_mirror_merge = False
        with_object(bpy.ops.object.modifier_apply, obj, modifier=modifier.name)
        if not self.weld_map: self.fill_weld_map(obj)
        weld_mesh(obj.data, self.weld_map)
    def fill_weld_map(self, obj):
        mesh = obj.data
        num_verts = len(mesh.vertices) // (2 ** self.num_mirrors)
        merge_dist_sq = self.merge_dist ** 2
        welds = []
        for n in range(self.num_mirrors):
            num_part_verts = num_verts * (2 ** n)
            new_welds = [(src_idx + num_part_verts, dst_idx + num_part_verts) for src_idx, dst_idx in welds]
            welds.extend(new_welds)
            for vert_idx in range(num_part_verts):
                vert = mesh.vertices[vert_idx]
                other_vert_idx = vert_idx + num_part_verts
                other_vert = mesh.vertices[other_vert_idx]
                if get_dist_sq(vert.co, other_vert.co) <= merge_dist_sq:
                    welds.append((other_vert_idx, vert_idx))
        self.weld_map = weld_map = {}
        weld_map_reverse = defaultdict(list)
        for src_idx, dst_idx in welds:
            dst_idx = weld_map.get(dst_idx, dst_idx)
            weld_map[src_idx] = dst_idx
            for old_idx in weld_map_reverse.get(src_idx, []):
                weld_map[old_idx] = dst_idx
                weld_map_reverse[dst_idx].append(old_idx)
            weld_map_reverse[dst_idx].append(src_idx)

class WeldModifierHandler(ModifierHandler):
    modifier_type = 'WELD'
    def __init__(self, modifier):
        super().__init__(modifier)
        self.merge_dist = modifier.merge_threshold
        self.vertex_group = modifier.vertex_group
        self.invert_vertex_group = modifier.invert_vertex_group
        self.weld_map = None
    @classmethod
    def poll(cls, modifier):
        return super().poll(modifier) and modifier.mode == 'ALL'
    def apply(self, obj):
        modifier = obj.modifiers[self.modifier_name]
        with_object(bpy.ops.object.modifier_remove, obj, modifier=modifier.name)
        if not self.weld_map: self.fill_weld_map(obj)
        weld_mesh(obj.data, self.weld_map)
    def fill_weld_map(self, obj):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        vg = obj.vertex_groups.get(self.vertex_group)
        deform_layer = bm.verts.layers.deform.active
        if deform_layer and vg:
            verts = [v for v in bm.verts if bool(v[deform_layer].get(vg.index, 0.0)) != self.invert_vertex_group]
        else: verts = bm.verts
        targetmap = bmesh.ops.find_doubles(bm, verts=verts, dist=self.merge_dist)['targetmap']
        self.weld_map = {src.index: dst.index for src, dst in targetmap.items()}
        bm.free()

class CollapseDecimateModifierHandler(ModifierHandler):
    modifier_type = 'DECIMATE'
    apply_post = True
    def __init__(self, modifier):
        super().__init__(modifier)
        self.ratio = modifier.ratio
        self.vertex_group = modifier.vertex_group
        self.invert_vertex_group = modifier.invert_vertex_group
        self.vertex_group_factor = modifier.vertex_group_factor
        self.use_symmetry = modifier.use_symmetry
        self.symmetry_axis = modifier.symmetry_axis
    @classmethod
    def poll(cls, modifier):
        return super().poll(modifier) and modifier.decimate_type == 'COLLAPSE'
    def apply(self, obj):
        with SaveContext(bpy.context) as save:
            save.mode()
            save.prop(obj, 'active_shape_key_index', 0)
            save.prop(obj.vertex_groups, 'active_index', obj.vertex_groups.find(self.vertex_group))
            edit_mesh_elements(obj, 'VERT')
            with_object(bpy.ops.mesh.decimate, obj, ratio=self.ratio, use_vertex_group=bool(self.vertex_group),
                vertex_group_factor=self.vertex_group_factor, invert_vertex_group=self.invert_vertex_group,
                use_symmetry=self.use_symmetry, symmetry_axis=self.symmetry_axis)
        with_object(bpy.ops.object.modifier_remove, obj, modifier=self.modifier_name)

modifier_handler_classes = (MirrorModifierHandler, WeldModifierHandler, CollapseDecimateModifierHandler, ModifierHandler)

modifier_icons = {
    'ARRAY': 'MOD_ARRAY', 'BEVEL': 'MOD_BEVEL', 'BOOLEAN': 'MOD_BOOLEAN', 'BUILD': 'MOD_BUILD',
    'DECIMATE': 'MOD_DECIM', 'EDGE_SPLIT': 'MOD_EDGESPLIT', 'NODES': 'NODETREE', 'MASK': 'MOD_MASK',
    'MIRROR': 'MOD_MIRROR', 'MULTIRES': 'MOD_MULTIRES', 'REMESH': 'MOD_REMESH', 'SCREW': 'MOD_SCREW',
    'SKIN': 'MOD_SKIN', 'SOLIDIFY': 'MOD_SOLIDIFY', 'SUBSURF': 'MOD_SUBSURF', 'TRIANGULATE': 'MOD_TRIANGULATE',
    'WELD': 'AUTOMERGE_OFF', 'WIREFRAME': 'MOD_WIREFRAME', 'ARMATURE': 'MOD_ARMATURE',
    'CURVE': 'MOD_CURVE', 'DISPLACE': 'MOD_DISPLACE', 'LATTICE': 'MOD_LATTICE', 'SHRINKWRAP': 'MOD_SHRINKWRAP',
    'SIMPLE_DEFORM': 'MOD_SIMPLEDEFORM', 'SMOOTH': 'MOD_SMOOTH', 'SURFACE_DEFORM': 'MOD_MESHDEFORM',
}

ignored_modifier_types = frozenset(('CLOTH', 'COLLISION', 'DYNAMIC_PAINT', 'EXPLODE', 'FLUID', 'OCEAN', 'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SOFT_BODY'))

class RZM_OT_shape_key_apply_modifiers(bpy.types.Operator):
    """Applies viewport modifiers while preserving shape keys (Gret Standalone)"""
    bl_idname = "rz.shape_key_apply_modifiers"
    bl_label = "Apply Modifiers with Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    modifier_mask: bpy.props.BoolVectorProperty(size=32, default=[True] * 32)
    modifier_info = []

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.object and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select modifiers to apply:")
        col = layout.column(align=True)
        for i, (m_type, m_name) in enumerate(self.modifier_info):
            if m_type in ignored_modifier_types: continue
            icon = modifier_icons.get(m_type, 'BLANK1')
            col.prop(self, 'modifier_mask', index=i, icon=icon, text=m_name)

    def invoke(self, context, event):
        obj = context.object
        self.modifier_info = [(mod.type, mod.name) for mod in obj.modifiers]
        def should_apply(mod): return mod.show_viewport and mod.type not in ignored_modifier_types and mod.type != 'ARMATURE'
        self.modifier_mask = get_modifier_mask(obj, should_apply)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.active_object
        if not any(self.modifier_mask[:len(obj.modifiers)]): return {'FINISHED'}
        if obj.data.users > 1: obj.data = obj.data.copy()

        num_keys = len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0
        if not num_keys:
            for mod, mask in zip(obj.modifiers[:], self.modifier_mask):
                if mask: apply_modifier(mod)
            return {'FINISHED'}

        mesh_copy = obj.data.copy()
        sk_infos = [ShapeKeyInfo.from_shape_key(sk) for sk in obj.data.shape_keys.key_blocks]
        saved_idx = obj.active_shape_key_index
        saved_show = obj.show_only_shape_key

        sk_objs = []
        for info in sk_infos:
            new_obj = obj.copy()
            new_obj.data = obj.data.copy()
            sk_objs.append(new_obj)

        obj.shape_key_clear()
        handlers, post_handlers = [], []
        for mod, mask in zip(obj.modifiers[:], self.modifier_mask):
            if mask:
                for cls in modifier_handler_classes:
                    if cls.poll(mod):
                        h = cls(mod)
                        if h.apply_post: post_handlers.append(h)
                        else: h.apply(obj); handlers.append(h)
                        break

        for info, sk_obj in zip(sk_infos, sk_objs):
            sk_mesh = sk_obj.data
            sk_obj.shape_key_clear()
            info.put_coords_into(sk_mesh.vertices)
            for h in handlers: h.apply(sk_obj)
            info.get_coords_from(sk_mesh.vertices)
            bpy.data.objects.remove(sk_obj); bpy.data.meshes.remove(sk_mesh)

        for info in sk_infos:
            sk = obj.shape_key_add(name=info.name)
            sk.interpolation, sk.mute, sk.slider_max, sk.slider_min, sk.value, sk.vertex_group = \
                info.interpolation, info.mute, info.slider_max, info.slider_min, info.value, info.vertex_group
            if len(sk.data) * 3 != len(info.coords): continue
            sk.data.foreach_set('co', info.coords)

        for h in post_handlers: h.apply(obj)
        if mesh_copy.shape_keys and mesh_copy.shape_keys.animation_data:
            if not obj.data.shape_keys.animation_data: obj.data.shape_keys.animation_data_create()
            for fc in mesh_copy.shape_keys.animation_data.drivers:
                obj.data.shape_keys.animation_data.drivers.from_existing(src_driver=fc)

        obj.show_only_shape_key, obj.active_shape_key_index = saved_show, saved_idx
        bpy.data.meshes.remove(mesh_copy)
        try: context.view_layer.update()
        except: pass
        return {'FINISHED'}

def register():
    bpy.utils.register_class(RZM_OT_shape_key_apply_modifiers)

def unregister():
    bpy.utils.unregister_class(RZM_OT_shape_key_apply_modifiers)

classes_to_register = [RZM_OT_shape_key_apply_modifiers]
