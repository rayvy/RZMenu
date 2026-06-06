import bpy
import bmesh


def _iter_selected_uv_loops(bm, uv_layer):
    use_sync = bool(getattr(bpy.context.scene.tool_settings, "use_uv_select_sync", False))
    for face in bm.faces:
        if not face.select and use_sync:
            continue
        for loop in face.loops:
            luv = loop[uv_layer]
            selected = bool(loop.vert.select or face.select) if use_sync else bool(getattr(luv, "select", False))
            if selected:
                yield luv


class RZM_OT_TwaaFillUvToSquare(bpy.types.Operator):
    bl_idname = "rzm.twaa_fill_uv_to_square"
    bl_label = "Fill To Square"
    bl_description = "Scale selected UVs into the 0..1 square without rotation"
    bl_options = {'REGISTER', 'UNDO'}

    preserve_aspect: bpy.props.BoolProperty(
        name="Preserve Aspect",
        description="Fit inside the square with uniform scale instead of stretching both axes",
        default=False,
    )
    padding: bpy.props.FloatProperty(
        name="Padding",
        description="Inset from the 0..1 square border",
        default=0.0,
        min=0.0,
        max=0.49,
        precision=4,
    )

    @classmethod
    def poll(cls, context):
        return bool(context.object and context.object.type == "MESH" and context.object.mode == "EDIT")

    def execute(self, context):
        obj = context.object
        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        uv_layer = bm.loops.layers.uv.active
        if uv_layer is None:
            self.report({'ERROR'}, "Active mesh has no UV layer")
            return {'CANCELLED'}

        loops = list(_iter_selected_uv_loops(bm, uv_layer))
        if not loops:
            self.report({'WARNING'}, "No selected UVs")
            return {'CANCELLED'}

        min_u = min(float(loop.uv.x) for loop in loops)
        max_u = max(float(loop.uv.x) for loop in loops)
        min_v = min(float(loop.uv.y) for loop in loops)
        max_v = max(float(loop.uv.y) for loop in loops)
        span_u = max_u - min_u
        span_v = max_v - min_v
        if span_u <= 1.0e-12 or span_v <= 1.0e-12:
            self.report({'ERROR'}, "Selected UV bounds are degenerate")
            return {'CANCELLED'}

        pad = max(0.0, min(0.49, float(self.padding)))
        target_min = pad
        target_size = max(1.0e-8, 1.0 - pad * 2.0)

        if self.preserve_aspect:
            scale = target_size / max(span_u, span_v)
            out_w = span_u * scale
            out_h = span_v * scale
            off_u = target_min + (target_size - out_w) * 0.5
            off_v = target_min + (target_size - out_h) * 0.5
            for loop in loops:
                loop.uv.x = off_u + (float(loop.uv.x) - min_u) * scale
                loop.uv.y = off_v + (float(loop.uv.y) - min_v) * scale
        else:
            scale_u = target_size / span_u
            scale_v = target_size / span_v
            for loop in loops:
                loop.uv.x = target_min + (float(loop.uv.x) - min_u) * scale_u
                loop.uv.y = target_min + (float(loop.uv.y) - min_v) * scale_v

        bmesh.update_edit_mesh(mesh)
        self.report({'INFO'}, f"Filled {len(loops)} UV loop(s) to square")
        return {'FINISHED'}


def draw_uv_menu(self, _context):
    self.layout.separator()
    self.layout.operator(RZM_OT_TwaaFillUvToSquare.bl_idname, text="Fill To Square")


classes_to_register = [
    RZM_OT_TwaaFillUvToSquare,
]


def register_menus():
    menu = getattr(bpy.types, "IMAGE_MT_uvs", None)
    if menu:
        try:
            menu.append(draw_uv_menu)
        except Exception:
            pass


def unregister_menus():
    menu = getattr(bpy.types, "IMAGE_MT_uvs", None)
    if menu:
        try:
            menu.remove(draw_uv_menu)
        except Exception:
            pass
