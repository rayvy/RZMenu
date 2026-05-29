# RZMenu/operators/profile_ops.py
import bpy

class RZM_OT_AddArtistProfile(bpy.types.Operator):
    bl_idname = "rzm.add_artist_profile"
    bl_label = "Add Artist Profile"
    bl_description = "Create a new empty artist profile"
    bl_options = {'UNDO'}
    
    new_name: bpy.props.StringProperty(name="Profile Name", default="New Profile")
    
    def execute(self, context):
        from .tier_ops import get_prefs
        prefs = get_prefs(context)
        if not prefs:
            self.report({'ERROR'}, "Could not find addon preferences.")
            return {'CANCELLED'}
            
        # Сохраняем текущий активный профиль перед добавлением нового
        prefs.save_to_profile(prefs.active_profile_index)
        
        # Добавляем новый профиль
        new_prof = prefs.artist_profiles.add()
        new_prof.name = self.new_name
        new_prof.author_name = "New Author"
        
        # Задаем дефолтные тиры для нового профиля
        defaults = [
            ("Tier0", "Public (Free)", (0.35, 0.65, 0.35)),
            ("Tier1", "Tier 1",        (0.35, 0.55, 0.80)),
            ("Tier2", "Tier 2",        (0.75, 0.60, 0.20)),
            ("TierPremium", "Premium",  (0.80, 0.35, 0.60)),
        ]
        for tid, dname, col in defaults:
            t = new_prof.tier_definitions.add()
            t.tier_id = tid
            t.display_name = dname
            t.tier_color = col
            
        # Переключаемся на новый профиль
        prefs.active_profile_index = len(prefs.artist_profiles) - 1
        
        self.report({'INFO'}, f"Profile '{self.new_name}' created.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class RZM_OT_DuplicateArtistProfile(bpy.types.Operator):
    bl_idname = "rzm.duplicate_artist_profile"
    bl_label = "Duplicate Active Profile"
    bl_description = "Duplicate the active profile settings to a new profile"
    bl_options = {'UNDO'}
    
    new_name: bpy.props.StringProperty(name="Profile Name", default="New Profile Copy")
    
    def execute(self, context):
        from .tier_ops import get_prefs
        prefs = get_prefs(context)
        if not prefs:
            return {'CANCELLED'}
            
        # Сначала сохраняем текущие значения в активный профиль
        idx = prefs.active_profile_index
        prefs.save_to_profile(idx)
        
        if not (0 <= idx < len(prefs.artist_profiles)):
            self.report({'ERROR'}, "Active profile index out of bounds.")
            return {'CANCELLED'}
            
        source_prof = prefs.artist_profiles[idx]
        
        # Добавляем новый профиль
        new_prof = prefs.artist_profiles.add()
        new_prof.name = self.new_name
        new_prof.author_name = source_prof.author_name
        new_prof.pre_description = source_prof.pre_description
        new_prof.post_description = source_prof.post_description
        new_prof.batch_build_path = source_prof.batch_build_path
        
        # Копируем контакты
        for c in source_prof.contacts:
            new_c = new_prof.contacts.add()
            new_c.contact_type = c.contact_type
            new_c.contact_value = c.contact_value
        new_prof.contacts_index = source_prof.contacts_index
        
        # Копируем тиры
        for t in source_prof.tier_definitions:
            new_t = new_prof.tier_definitions.add()
            new_t.tier_id = t.tier_id
            new_t.display_name = t.display_name
            new_t.tier_color = t.tier_color
            new_t.parent_tier_id = t.parent_tier_id
        new_prof.tier_definitions_index = source_prof.tier_definitions_index

        # Копируем сборочные профили
        for bp in source_prof.build_profiles:
            new_bp = new_prof.build_profiles.add()
            new_bp.name = bp.name
            new_bp.active_tiers = bp.active_tiers
            new_bp.zip_output = bp.zip_output
        new_prof.build_profiles_index = source_prof.build_profiles_index
        
        # Переключаемся на новый профиль
        prefs.active_profile_index = len(prefs.artist_profiles) - 1
        
        self.report({'INFO'}, f"Profile duplicated as '{self.new_name}'.")
        return {'FINISHED'}
        
    def invoke(self, context, event):
        from .tier_ops import get_prefs
        prefs = get_prefs(context)
        if prefs and 0 <= prefs.active_profile_index < len(prefs.artist_profiles):
            self.new_name = f"{prefs.artist_profiles[prefs.active_profile_index].name} Copy"
        return context.window_manager.invoke_props_dialog(self)

class RZM_OT_RemoveArtistProfile(bpy.types.Operator):
    bl_idname = "rzm.remove_artist_profile"
    bl_label = "Remove Active Profile"
    bl_description = "Delete the active profile"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        from .tier_ops import get_prefs
        prefs = get_prefs(context)
        return prefs and len(prefs.artist_profiles) > 1
        
    def execute(self, context):
        from .tier_ops import get_prefs
        from RZMenu.data import p_settings
        prefs = get_prefs(context)
        if not prefs:
            return {'CANCELLED'}
            
        idx = prefs.active_profile_index
        if not (0 <= idx < len(prefs.artist_profiles)):
            return {'CANCELLED'}
            
        name = prefs.artist_profiles[idx].name
        
        # Безопасно обновляем коллекции и индексы под флагом
        p_settings._updating_profile = True
        try:
            # Удаляем профиль
            prefs.artist_profiles.remove(idx)
            
            # Корректируем активный индекс
            new_idx = max(0, idx - 1)
            
            prefs.last_active_profile_index = new_idx
            prefs.active_profile_index = new_idx
        finally:
            p_settings._updating_profile = False
            
        # Загружаем настройки из нового профиля
        prefs.load_from_profile(new_idx)
        
        self.report({'INFO'}, f"Profile '{name}' removed.")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AddArtistProfile,
    RZM_OT_DuplicateArtistProfile,
    RZM_OT_RemoveArtistProfile,
]
