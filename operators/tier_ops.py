# RZMenu/operators/tier_ops.py
"""
Operators and UIList for managing global Tier Definitions.
Tier definitions live in AddonPreferences (not .rzm) so they survive file reloads
and are personal to the artist — not embedded in the mod package.
"""
import bpy


def get_prefs(context):
    addon_name = __package__.split(".")[0] if "." in __package__ else __package__
    prefs = context.preferences.addons.get(addon_name)
    return prefs.preferences if prefs else None


# ─── UIList ───────────────────────────────────────────────────────────────────

class RZM_UL_TierDefinitions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "tier_color", text="", emboss=True)
            row.prop(item, "tier_id", text="", emboss=False)
            row.label(text=f"  {item.display_name}")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.tier_id, icon='BOOKMARKS')

class RZM_UL_Contacts(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "contact_type", text="", emboss=False)
            row.prop(item, "contact_value", text="")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.contact_type, icon='CONTACT')

class RZM_UL_BuildProfiles(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.name, icon='PACKAGE')
            row.label(text=f" ({item.active_tiers})")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon='PACKAGE')


# ─── Tier Definition CRUD ─────────────────────────────────────────────────────

class RZM_OT_AddTierDefinition(bpy.types.Operator):
    """Add a new tier definition"""
    bl_idname = "rzm.add_tier_definition"
    bl_label = "Add Tier"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = get_prefs(context)
        if not prefs:
            self.report({'ERROR'}, "Could not access AddonPreferences")
            return {'CANCELLED'}
        existing_ids = {t.tier_id for t in prefs.tier_definitions}
        n = len(prefs.tier_definitions) + 1
        new_id = f"Tier{n}"
        while new_id in existing_ids:
            n += 1
            new_id = f"Tier{n}"
        t = prefs.tier_definitions.add()
        t.tier_id = new_id
        t.display_name = f"Tier {n}"
        prefs.tier_definitions_index = len(prefs.tier_definitions) - 1
        prefs.save_to_profile(prefs.active_profile_index)
        return {'FINISHED'}


class RZM_OT_RemoveTierDefinition(bpy.types.Operator):
    """Remove the selected tier definition"""
    bl_idname = "rzm.remove_tier_definition"
    bl_label = "Remove Tier"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = get_prefs(context)
        if not prefs:
            return {'CANCELLED'}
        idx = prefs.tier_definitions_index
        if 0 <= idx < len(prefs.tier_definitions):
            prefs.tier_definitions.remove(idx)
            prefs.tier_definitions_index = max(0, idx - 1)
            prefs.save_to_profile(prefs.active_profile_index)
        return {'FINISHED'}


class RZM_OT_ResetTierDefinitions(bpy.types.Operator):
    """Reset tier definitions to built-in defaults"""
    bl_idname = "rzm.reset_tier_definitions"
    bl_label = "Reset Tiers to Default"
    bl_description = "Clear all tier definitions and populate with sensible defaults"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        prefs = get_prefs(context)
        if not prefs:
            return {'CANCELLED'}
        prefs.tier_definitions.clear()
        prefs.ensure_default_tiers()
        prefs.tier_definitions_index = 0
        prefs.save_to_profile(prefs.active_profile_index)
        self.report({'INFO'}, "Tier definitions reset to defaults.")
        return {'FINISHED'}

# ─── Contact CRUD ─────────────────────────────────────────────────────────────

class RZM_OT_AddContact(bpy.types.Operator):
    """Add a new contact entry"""
    bl_idname = "rzm.add_contact"
    bl_label = "Add Contact"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = get_prefs(context)
        if prefs:
            prefs.contacts.add()
            prefs.contacts_index = len(prefs.contacts) - 1
            prefs.save_to_profile(prefs.active_profile_index)
        return {'FINISHED'}

class RZM_OT_RemoveContact(bpy.types.Operator):
    """Remove the selected contact entry"""
    bl_idname = "rzm.remove_contact"
    bl_label = "Remove Contact"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = get_prefs(context)
        if prefs and 0 <= prefs.contacts_index < len(prefs.contacts):
            prefs.contacts.remove(prefs.contacts_index)
            prefs.contacts_index = max(0, prefs.contacts_index - 1)
            prefs.save_to_profile(prefs.active_profile_index)
        return {'FINISHED'}

# ─── Build Profile CRUD ───────────────────────────────────────────────────────

class RZM_OT_AddBuildProfile(bpy.types.Operator):
    """Add a new batch build profile"""
    bl_idname = "rzm.add_build_profile"
    bl_label = "Add Build Profile"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = get_prefs(context)
        if prefs:
            p = prefs.build_profiles.add()
            p.name = f"Build Profile {len(prefs.build_profiles)}"
            prefs.build_profiles_index = len(prefs.build_profiles) - 1
            prefs.save_to_profile(prefs.active_profile_index)
        return {'FINISHED'}

class RZM_OT_RemoveBuildProfile(bpy.types.Operator):
    """Remove the selected build profile"""
    bl_idname = "rzm.remove_build_profile"
    bl_label = "Remove Build Profile"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = get_prefs(context)
        if prefs and 0 <= prefs.build_profiles_index < len(prefs.build_profiles):
            prefs.build_profiles.remove(prefs.build_profiles_index)
            prefs.build_profiles_index = max(0, prefs.build_profiles_index - 1)
            prefs.save_to_profile(prefs.active_profile_index)
        return {'FINISHED'}


# ─── Shape Tier Operators ─────────────────────────────────────────────────────

class RZM_OT_AddShapeTier(bpy.types.Operator):
    """Add a tier to the selected shape"""
    bl_idname = "rzm.add_shape_tier"
    bl_label = "Add Shape Tier"
    bl_options = {'REGISTER', 'UNDO'}
    shape_index: bpy.props.IntProperty()
    tier_id: bpy.props.StringProperty()

    def execute(self, context):
        shapes = context.scene.rzm.shapes
        if not (0 <= self.shape_index < len(shapes)):
            return {'CANCELLED'}
        shape = shapes[self.shape_index]
        if not any(t.tier_id == self.tier_id for t in shape.export_tiers):
            t = shape.export_tiers.add()
            t.tier_id = self.tier_id
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class RZM_OT_RemoveShapeTier(bpy.types.Operator):
    """Remove a tier from the selected shape"""
    bl_idname = "rzm.remove_shape_tier"
    bl_label = "Remove Shape Tier"
    bl_options = {'REGISTER', 'UNDO'}
    shape_index: bpy.props.IntProperty()
    tier_id: bpy.props.StringProperty()

    def execute(self, context):
        shapes = context.scene.rzm.shapes
        if not (0 <= self.shape_index < len(shapes)):
            return {'CANCELLED'}
        shape = shapes[self.shape_index]
        for i, t in enumerate(shape.export_tiers):
            if t.tier_id == self.tier_id:
                shape.export_tiers.remove(i)
                break
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


# ─── Value Tier Operators ─────────────────────────────────────────────────────

class RZM_OT_AddValueTier(bpy.types.Operator):
    """Add a tier to the selected $value variable"""
    bl_idname = "rzm.add_value_tier"
    bl_label = "Add Value Tier"
    bl_options = {'REGISTER', 'UNDO'}
    value_index: bpy.props.IntProperty()
    tier_id: bpy.props.StringProperty()

    def execute(self, context):
        values = context.scene.rzm.rzm_values
        if not (0 <= self.value_index < len(values)):
            return {'CANCELLED'}
        val = values[self.value_index]
        if not any(t.tier_id == self.tier_id for t in val.export_tiers):
            t = val.export_tiers.add()
            t.tier_id = self.tier_id
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class RZM_OT_RemoveValueTier(bpy.types.Operator):
    """Remove a tier from the selected $value variable"""
    bl_idname = "rzm.remove_value_tier"
    bl_label = "Remove Value Tier"
    bl_options = {'REGISTER', 'UNDO'}
    value_index: bpy.props.IntProperty()
    tier_id: bpy.props.StringProperty()

    def execute(self, context):
        values = context.scene.rzm.rzm_values
        if not (0 <= self.value_index < len(values)):
            return {'CANCELLED'}
        val = values[self.value_index]
        for i, t in enumerate(val.export_tiers):
            if t.tier_id == self.tier_id:
                val.export_tiers.remove(i)
                break
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


# ─── Object Tier Operators ────────────────────────────────────────────────────

class RZM_OT_AddObjectTier(bpy.types.Operator):
    """Add a Mod Producer tier filter to the active object"""
    bl_idname = "rzm.add_object_tier"
    bl_label = "Add Object Tier"
    bl_options = {'REGISTER', 'UNDO'}
    tier_id: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}
        if not any(t.tier_id == self.tier_id for t in obj.rzm_tier_list):
            t = obj.rzm_tier_list.add()
            t.tier_id = self.tier_id
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class RZM_OT_RemoveObjectTier(bpy.types.Operator):
    """Remove a Mod Producer tier filter from the active object"""
    bl_idname = "rzm.remove_object_tier"
    bl_label = "Remove Object Tier"
    bl_options = {'REGISTER', 'UNDO'}
    tier_id: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}
        for i, t in enumerate(obj.rzm_tier_list):
            if t.tier_id == self.tier_id:
                obj.rzm_tier_list.remove(i)
                break
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


# ─── Helper: public API ───────────────────────────────────────────────────────

def get_tier_ids(context) -> list:
    """Returns a list of all tier IDs from AddonPreferences."""
    prefs = get_prefs(context)
    if not prefs:
        return []
    return [t.tier_id for t in prefs.tier_definitions]


def get_entity_tier_ids(entity) -> list:
    """Get list of tier_ids from an entity's export_tiers CollectionProperty."""
    return [t.tier_id for t in getattr(entity, 'export_tiers', [])]


def element_passes_tier_filter(element, active_tiers: set) -> bool:
    """
    Returns True if element should be included in the current Mod Producer build.
    - If element.disable_export is True → always excluded
    - If element.export_tiers is empty → always included (no tier restriction)
    - Otherwise → include only if ANY of its tiers are in active_tiers
    """
    if getattr(element, 'disable_export', False):
        return False
    tiers = get_entity_tier_ids(element)
    if not tiers:
        return True
    return bool(set(tiers) & active_tiers)


classes_to_register = [
    RZM_UL_TierDefinitions,
    RZM_UL_Contacts,
    RZM_UL_BuildProfiles,
    RZM_OT_AddTierDefinition,
    RZM_OT_RemoveTierDefinition,
    RZM_OT_ResetTierDefinitions,
    RZM_OT_AddContact,
    RZM_OT_RemoveContact,
    RZM_OT_AddBuildProfile,
    RZM_OT_RemoveBuildProfile,
    RZM_OT_AddShapeTier,
    RZM_OT_RemoveShapeTier,
    RZM_OT_AddValueTier,
    RZM_OT_RemoveValueTier,
    RZM_OT_AddObjectTier,
    RZM_OT_RemoveObjectTier,
]
