import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

def poll_armature(self, obj):
    return obj is not None and obj.type == "ARMATURE"

def poll_mesh(self, obj):
    return obj is not None and obj.type == "MESH"

def trigger_redraw(self, context):
    try:
        from .harmonizer_utils import tag_view3d_redraw
        tag_view3d_redraw()
    except ImportError:
        pass

def update_object_plan_index(self, context):
    active_obj = context.active_object
    if not active_obj or active_obj.type != 'MESH':
        return
    if active_obj.mode != 'PAINT_WEIGHT':
        return
    plan = context.scene.rzm_weight_plan
    idx = self.object_plan_index
    if 0 <= idx < len(plan):
        item = plan[idx]
        if item.object_name == active_obj.name:
            vg = active_obj.vertex_groups.get(item.original_name)
            if vg:
                active_obj.vertex_groups.active = vg

def update_resolved_name(self, context):
    if self.get("_updating_cluster"):
        return
    if not self.cluster_id:
        return
    self["_updating_cluster"] = True
    for other in context.scene.rzm_weight_plan:
        if other != self and other.cluster_id == self.cluster_id:
            other["_updating_cluster"] = True
            other.resolved_name = self.resolved_name
            other.status = self.status
            other.create_bone = self.create_bone
            other.is_helper = self.is_helper
            other["_updating_cluster"] = False
    self["_updating_cluster"] = False
    
    try:
        from .ops_harmonizer import rebuild_matrix_and_summary
        target_names = {item.object_name for item in context.scene.rzm_weight_plan}
        target_meshes = [bpy.data.objects.get(name) for name in target_names if bpy.data.objects.get(name)]
        rebuild_matrix_and_summary(context.scene, target_meshes)
    except Exception as e:
        print("Error rebuilding matrix in update callback:", e)

class RZMWeightSettings(PropertyGroup):
    target_armature: PointerProperty(name="Таргетная арматура", type=bpy.types.Object, poll=poll_armature)
    reference_mesh: PointerProperty(name="Канонический референс-мэш", type=bpy.types.Object, poll=poll_mesh)

    approved_threshold: FloatProperty(name="Strong", default=0.72, min=0.0, max=1.0, precision=2)
    conflict_threshold: FloatProperty(name="Floor", default=0.34, min=0.0, max=1.0, precision=2)
    unique_margin: FloatProperty(name="Margin", default=0.10, min=0.0, max=1.0, precision=2)
    assignment_margin: FloatProperty(name="Rival", default=0.10, min=0.0, max=1.0, precision=2)
    unknown_cluster_threshold: FloatProperty(name="Merge", default=0.82, min=0.0, max=1.0, precision=2)
    consensus_threshold: FloatProperty(
        name="Consensus",
        description="Минимальная схожесть для объединения групп разных компонентов перед сопоставлением с референсом",
        default=0.85,
        min=0.0,
        max=1.0,
        precision=2,
    )

    create_missing_bones: BoolProperty(name="Создавать недостающие кости", default=True)
    ignore_multiple_toe: BoolProperty(
        name="IgnoreMultipleToe",
        description="Схлопывает Toe-подобные цели в Toes.L / Toes.R",
        default=True,
    )
    show_overlay: BoolProperty(name="Overlay", default=True, update=trigger_redraw)
    overlay_all_components: BoolProperty(name="All components", default=True, update=trigger_redraw)
    overlay_point_size: FloatProperty(name="Dots", default=6.0, min=1.0, max=20.0, update=trigger_redraw)
    matrix_only_incomplete: BoolProperty(name="Only holes", default=False)

    active_tab: EnumProperty(
        items=[
            ("APPROVED", "Approved Matrix", "Канонические кости и компоненты"),
            ("CONFLICT", "Conflict", "Неоднозначные назначения"),
            ("UNKNOWN", "Unknown", "Новые доп. кости"),
            ("IGNORED", "Mask*", "Игнорируемые группы"),
            ("CLUSTERS", "Clusters", "Управление кластерами"),
        ],
        default="APPROVED",
        update=trigger_redraw,
    )

    approved_row_index: IntProperty(default=0, update=trigger_redraw)
    approved_detail_index: IntProperty(default=-1, update=trigger_redraw)
    matrix_editor_object: StringProperty(default="")
    matrix_manual_group_index: IntProperty(name="VG index", default=-1, min=-1)
    conflict_index: IntProperty(default=0, update=trigger_redraw)
    unknown_index: IntProperty(default=0, update=trigger_redraw)
    ignored_index: IntProperty(default=0, update=trigger_redraw)
    object_plan_index: IntProperty(default=0, update=update_object_plan_index)


class RZMWeightPlanItem(PropertyGroup):
    object_name: StringProperty()
    group_index: IntProperty()
    original_name: StringProperty()
    resolved_name: StringProperty(update=update_resolved_name)
    cluster_id: StringProperty(name="Cluster ID")
    status: EnumProperty(items=[("APPROVED", "Approved", ""), ("CONFLICT", "Conflict", ""), ("UNKNOWN", "Unknown", ""), ("IGNORED", "Ignored", "")])
    confidence: FloatProperty(min=0.0, max=1.0)
    margin: FloatProperty(min=0.0, max=1.0)
    nearest_bone: StringProperty()
    nearest_distance: FloatProperty()
    centroid: FloatVectorProperty(size=3, subtype="XYZ")
    radius: FloatProperty(default=0.0)
    bbox_size: FloatVectorProperty(size=3, subtype="XYZ")
    side: StringProperty(default="C")
    create_bone: BoolProperty(default=False)
    is_helper: BoolProperty(default=False, update=update_resolved_name)
    manual_override: BoolProperty(default=False)
    candidate_1: StringProperty()
    candidate_1_score: FloatProperty()
    candidate_2: StringProperty()
    candidate_2_score: FloatProperty()
    candidate_3: StringProperty()
    candidate_3_score: FloatProperty()
    decision_reason: StringProperty()
    conflict_cluster: StringProperty()


class RZMApprovedCell(PropertyGroup):
    object_name: StringProperty()
    display_text: StringProperty()
    plan_index: IntProperty(default=-1)


class RZMApprovedBoneRow(PropertyGroup):
    canonical_name: StringProperty()
    cells: CollectionProperty(type=RZMApprovedCell)


class RZMComponentSummary(PropertyGroup):
    object_name: StringProperty()
    total_groups: IntProperty()
    default_total: IntProperty()
    occupied_default: IntProperty()
    approved: IntProperty()
    conflict: IntProperty()
    unknown: IntProperty()
    ignored: IntProperty()
    duplicate_approved: IntProperty()
    missing_default: IntProperty()


classes_to_register = [
    RZMWeightSettings,
    RZMWeightPlanItem,
    RZMApprovedCell,
    RZMApprovedBoneRow,
    RZMComponentSummary,
]
