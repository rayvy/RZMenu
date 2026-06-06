import bpy
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


# ============================================================
# SETTINGS
# ============================================================

UV_NAME = "TEXCOORD.xy"

VALID_TEXTURE_SIZES = (
    128,
    256,
    512,
    1024,
    2048,
    4096,
)

REPORT_TEXT_NAME = "RZM_Texture_Padding_Report"

# Новые изображения сохраняются в PNG рядом с .blend.
# Если .blend ещё не сохранён, используется временная папка ОС.
SAVE_PNG_COPIES = False

# Дополнительно упаковать новые изображения внутрь .blend.
PACK_NEW_IMAGES = False

# При UV за пределами 0..1 операция останавливается.
# Причина: padding не способен сохранить прежнее поведение тайлинга.
ABORT_ON_UV_OUTSIDE_01 = True

# Проверяются только реально подключённые Image Texture ноды:
# Material Output ← ... ← Image Texture.
#
# Отключённые и забытые в стороне ноды игнорируются.
INCLUDE_UNLINKED_DIRECT_IMAGE_NODES = False

# Внутренности Node Group не изменяются намеренно:
# одна группа может использоваться несколькими материалами.
#
# В отчёте появится предупреждение, если группа найдена
# на пути к Material Output.
ABORT_IF_NODE_GROUP_FOUND = False

# Иногда в материале лежит служебная текстура, которую менять нельзя.
# В таком случае добавь сюда имя Image Texture ноды.
IGNORED_IMAGE_NODE_NAMES = {
    # "ShadowRamp",
    # "LookupTable",
}

# Новый холст заполняется прозрачным чёрным.
PAD_RGBA = (0.0, 0.0, 0.0, 0.0)

EPSILON = 1e-6


# ============================================================
# DATA
# ============================================================

@dataclass
class MaterialUsage:
    obj: bpy.types.Object
    slot_index: int
    polygon_indices: list[int] = field(default_factory=list)

    @property
    def face_count(self) -> int:
        return len(self.polygon_indices)


@dataclass
class MeshPlan:
    mesh: bpy.types.Mesh
    object_names: set[str] = field(default_factory=set)
    polygon_indices: set[int] = field(default_factory=set)
    loop_indices: set[int] = field(default_factory=set)


@dataclass
class ImagePlan:
    source_image: bpy.types.Image
    target_width: int
    target_height: int
    output_path: Optional[str] = None

    @property
    def source_width(self) -> int:
        return int(self.source_image.size[0])

    @property
    def source_height(self) -> int:
        return int(self.source_image.size[1])

    @property
    def needs_padding(self) -> bool:
        return (
            self.source_width != self.target_width
            or self.source_height != self.target_height
        )


# ============================================================
# REPORT
# ============================================================

LINES: list[str] = []


def log(text: str = "") -> None:
    LINES.append(text)
    print(text)


def divider(char: str = "-", width: int = 78) -> str:
    return char * width


def save_report() -> None:
    text = "\n".join(LINES)

    report = bpy.data.texts.get(REPORT_TEXT_NAME)

    if report is None:
        report = bpy.data.texts.new(REPORT_TEXT_NAME)

    report.clear()
    report.write(text)


# ============================================================
# ACTIVE MATERIAL
# ============================================================

def get_active_mesh_object() -> bpy.types.Object:
    obj = bpy.context.active_object

    if obj is None:
        raise RuntimeError("Нет активного объекта.")

    if obj.type != "MESH":
        raise RuntimeError(
            f"Активный объект '{obj.name}' имеет тип '{obj.type}', "
            "но ожидается MESH."
        )

    return obj


def get_active_material(
    obj: bpy.types.Object,
) -> bpy.types.Material:
    material = obj.active_material

    if material is None:
        raise RuntimeError(
            f"У активного объекта '{obj.name}' отсутствует активный материал."
        )

    if not material.use_nodes or material.node_tree is None:
        raise RuntimeError(
            f"У материала '{material.name}' отключены ноды."
        )

    return material


# ============================================================
# MATERIAL USAGE
# ============================================================

def find_real_material_usages(
    material: bpy.types.Material,
) -> list[MaterialUsage]:
    """
    Находит только объекты, где материал реально назначен полигонам.

    Простое присутствие материала в material_slots недостаточно:
    пустые слоты игнорируются.
    """
    usages: list[MaterialUsage] = []

    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue

        mesh = obj.data

        for slot_index, slot in enumerate(obj.material_slots):
            if slot.material != material:
                continue

            polygon_indices = [
                polygon.index
                for polygon in mesh.polygons
                if polygon.material_index == slot_index
            ]

            if not polygon_indices:
                continue

            usages.append(
                MaterialUsage(
                    obj=obj,
                    slot_index=slot_index,
                    polygon_indices=polygon_indices,
                )
            )

    return usages


def build_mesh_plans(
    usages: list[MaterialUsage],
) -> list[MeshPlan]:
    """
    Объединяет инстансы одного Mesh datablock.

    Если два объекта используют один и тот же Mesh datablock,
    его UV нельзя трансформировать дважды.
    """
    plans_by_pointer: dict[int, MeshPlan] = {}

    for usage in usages:
        mesh = usage.obj.data
        pointer = mesh.as_pointer()

        if pointer not in plans_by_pointer:
            plans_by_pointer[pointer] = MeshPlan(mesh=mesh)

        plan = plans_by_pointer[pointer]
        plan.object_names.add(usage.obj.name)
        plan.polygon_indices.update(usage.polygon_indices)

    for plan in plans_by_pointer.values():
        for polygon_index in plan.polygon_indices:
            polygon = plan.mesh.polygons[polygon_index]
            plan.loop_indices.update(polygon.loop_indices)

    return list(plans_by_pointer.values())


# ============================================================
# TEXTURE NODES
# ============================================================

def collect_reachable_image_nodes(
    material: bpy.types.Material,
) -> tuple[list[bpy.types.Node], list[str]]:
    """
    Идёт назад от Material Output и собирает подключённые
    Image Texture ноды верхнего уровня.

    Внутрь Node Group намеренно не заходит:
    изменение общей группы может затронуть другие материалы.
    """
    tree = material.node_tree

    output_nodes = [
        node
        for node in tree.nodes
        if node.type == "OUTPUT_MATERIAL"
        and getattr(node, "is_active_output", True)
    ]

    if not output_nodes:
        output_nodes = [
            node
            for node in tree.nodes
            if node.type == "OUTPUT_MATERIAL"
        ]

    if not output_nodes:
        raise RuntimeError(
            f"У материала '{material.name}' отсутствует Material Output."
        )

    stack = list(output_nodes)
    visited: set[int] = set()
    image_nodes: list[bpy.types.Node] = []
    group_names: list[str] = []

    while stack:
        node = stack.pop()
        pointer = node.as_pointer()

        if pointer in visited:
            continue

        visited.add(pointer)

        if node.type == "TEX_IMAGE":
            if node.image is not None:
                if node.name not in IGNORED_IMAGE_NODE_NAMES:
                    image_nodes.append(node)

            continue

        if node.type == "GROUP":
            group_names.append(node.name)

            if ABORT_IF_NODE_GROUP_FOUND:
                raise RuntimeError(
                    f"На пути к Material Output найдена Node Group "
                    f"'{node.name}'. Операция остановлена настройкой "
                    "ABORT_IF_NODE_GROUP_FOUND."
                )

            # Не заходим внутрь группы.
            # Но продолжаем искать текстуры, подключённые
            # к её внешним входам.

        for input_socket in node.inputs:
            for link in input_socket.links:
                stack.append(link.from_node)

    if INCLUDE_UNLINKED_DIRECT_IMAGE_NODES:
        for node in tree.nodes:
            if node.type != "TEX_IMAGE":
                continue

            if node.image is None:
                continue

            if node.name in IGNORED_IMAGE_NODE_NAMES:
                continue

            if node not in image_nodes:
                image_nodes.append(node)

    # Дедупликация самих нод.
    unique_nodes: list[bpy.types.Node] = []
    seen_nodes: set[int] = set()

    for node in image_nodes:
        pointer = node.as_pointer()

        if pointer in seen_nodes:
            continue

        seen_nodes.add(pointer)
        unique_nodes.append(node)

    return unique_nodes, sorted(set(group_names))


def collect_unique_images(
    image_nodes: list[bpy.types.Node],
) -> list[bpy.types.Image]:
    images: list[bpy.types.Image] = []
    seen: set[int] = set()

    for node in image_nodes:
        image = node.image

        if image is None:
            continue

        pointer = image.as_pointer()

        if pointer in seen:
            continue

        seen.add(pointer)
        images.append(image)

    return images


# ============================================================
# IMAGE SIZE SOLVER
# ============================================================

def validate_source_image(image: bpy.types.Image) -> None:
    width, height = map(int, image.size)

    if width <= 0 or height <= 0:
        raise RuntimeError(
            f"Изображение '{image.name}' не загружено "
            "или имеет нулевой размер."
        )

    if image.source == "TILED":
        raise RuntimeError(
            f"Изображение '{image.name}' использует UDIM. "
            "Текущая версия скрипта намеренно не изменяет UDIM-текстуры."
        )

    if width > max(VALID_TEXTURE_SIZES):
        raise RuntimeError(
            f"Ширина изображения '{image.name}' равна {width}. "
            "Она превышает допустимые 4096 пикселей."
        )

    if height > max(VALID_TEXTURE_SIZES):
        raise RuntimeError(
            f"Высота изображения '{image.name}' равна {height}. "
            "Она превышает допустимые 4096 пикселей."
        )


def solve_common_axis_scale(
    sizes: list[int],
    axis_name: str,
) -> tuple[float, list[int]]:
    """
    Находит минимальное общее расширение холста.

    Все изображения материала должны получить одинаковый UV scale.
    Иначе одна UV-развёртка не сможет корректно обслуживать
    одновременно Diffuse, NormalMap и остальные карты.
    """
    if not sizes:
        raise RuntimeError("Передан пустой список размеров.")

    reference_size = sizes[0]
    solutions: list[tuple[float, list[int]]] = []

    for reference_target in VALID_TEXTURE_SIZES:
        if reference_target < reference_size:
            continue

        scale = reference_size / reference_target
        targets: list[int] = []
        valid_solution = True

        for source_size in sizes:
            target_float = source_size / scale
            target_rounded = int(round(target_float))

            if abs(target_float - target_rounded) > EPSILON:
                valid_solution = False
                break

            if target_rounded not in VALID_TEXTURE_SIZES:
                valid_solution = False
                break

            if target_rounded < source_size:
                valid_solution = False
                break

            targets.append(target_rounded)

        if valid_solution:
            solutions.append((scale, targets))

    if not solutions:
        sizes_text = ", ".join(map(str, sizes))

        raise RuntimeError(
            f"Невозможно подобрать единый UV scale по оси {axis_name}.\n"
            f"Размеры текстур по этой оси: {sizes_text}\n"
            "Одна UV-развёртка не может сохранить прежнее отображение "
            "для всех этих изображений одновременно."
        )

    # Чем ближе scale к 1.0, тем меньше лишнего расширения.
    return max(solutions, key=lambda item: item[0])


def build_image_plans(
    images: list[bpy.types.Image],
) -> tuple[list[ImagePlan], float, float]:
    for image in images:
        validate_source_image(image)

    widths = [int(image.size[0]) for image in images]
    heights = [int(image.size[1]) for image in images]

    scale_x, target_widths = solve_common_axis_scale(
        sizes=widths,
        axis_name="X",
    )

    scale_y, target_heights = solve_common_axis_scale(
        sizes=heights,
        axis_name="Y",
    )

    plans = [
        ImagePlan(
            source_image=image,
            target_width=target_width,
            target_height=target_height,
        )
        for image, target_width, target_height
        in zip(images, target_widths, target_heights)
    ]

    return plans, scale_x, scale_y


# ============================================================
# UV CHECK AND BACKUP
# ============================================================

def get_required_uv_layer(
    mesh: bpy.types.Mesh,
) -> bpy.types.MeshUVLoopLayer:
    uv_layer = mesh.uv_layers.get(UV_NAME)

    if uv_layer is None:
        raise RuntimeError(
            f"У меша '{mesh.name}' отсутствует UV-слой '{UV_NAME}'."
        )

    return uv_layer


def validate_uv_range(
    mesh_plans: list[MeshPlan],
) -> None:
    if not ABORT_ON_UV_OUTSIDE_01:
        return

    for plan in mesh_plans:
        uv_layer = get_required_uv_layer(plan.mesh)

        for loop_index in plan.loop_indices:
            uv = uv_layer.data[loop_index].uv

            if (
                uv.x < -EPSILON
                or uv.x > 1.0 + EPSILON
                or uv.y < -EPSILON
                or uv.y > 1.0 + EPSILON
            ):
                objects_text = ", ".join(sorted(plan.object_names))

                raise RuntimeError(
                    f"Найдена UV-координата за пределами 0..1.\n"
                    f"Mesh datablock: {plan.mesh.name}\n"
                    f"Objects: {objects_text}\n"
                    f"Loop index: {loop_index}\n"
                    f"UV: ({uv.x:.8f}, {uv.y:.8f})\n"
                    "Padding не способен надёжно сохранить тайлинг. "
                    "Операция отменена."
                )


def make_unique_uv_layer_name(
    mesh: bpy.types.Mesh,
    base_name: str,
) -> str:
    if mesh.uv_layers.get(base_name) is None:
        return base_name

    index = 1

    while True:
        candidate = f"{base_name}_{index:03d}"

        if mesh.uv_layers.get(candidate) is None:
            return candidate

        index += 1


def backup_uv_layer(
    mesh: bpy.types.Mesh,
    run_id: str,
) -> str:
    return "RZM_DESTRUCTIVE_NO_BACKUP"


def restore_uv_layer(
    mesh: bpy.types.Mesh,
    backup_name: str,
) -> None:
    target_layer = mesh.uv_layers.get(UV_NAME)
    backup_layer = mesh.uv_layers.get(backup_name)

    if target_layer is None or backup_layer is None:
        return

    for target_uv, backup_uv in zip(
        target_layer.data,
        backup_layer.data,
    ):
        target_uv.uv = backup_uv.uv.copy()

    mesh.update()


def apply_uv_transform(
    mesh_plans: list[MeshPlan],
    scale_x: float,
    scale_y: float,
) -> None:
    """
    Верхний левый угол остаётся неподвижным.

    В Blender:
      U_new = U_old * scale_x
      V_new = 1 - (1 - V_old) * scale_y
    """
    for plan in mesh_plans:
        uv_layer = get_required_uv_layer(plan.mesh)

        for loop_index in plan.loop_indices:
            uv = uv_layer.data[loop_index].uv

            uv.x = uv.x * scale_x
            uv.y = 1.0 - (1.0 - uv.y) * scale_y

        plan.mesh.update()


# ============================================================
# PADDED IMAGE CREATION
# ============================================================

def safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]+', "_", name)
    name = name.strip(" .")

    return name or "Texture"


def get_output_directory() -> str:
    if bpy.data.filepath:
        root = os.path.dirname(bpy.data.filepath)
    else:
        root = tempfile.gettempdir()

    output_dir = os.path.join(
        root,
        "RZM_Padded_Textures",
    )

    os.makedirs(output_dir, exist_ok=True)

    return output_dir


def unique_output_path(
    output_dir: str,
    image_name: str,
    target_width: int,
    target_height: int,
    run_id: str,
) -> str:
    filename = (
        f"{safe_filename(image_name)}"
        f"_RZM_PAD_{target_width}x{target_height}"
        f"_{run_id}.png"
    )

    return os.path.join(output_dir, filename)


def copy_image_settings(
    source: bpy.types.Image,
    target: bpy.types.Image,
) -> None:
    try:
        target.colorspace_settings.name = (
            source.colorspace_settings.name
        )
    except Exception:
        pass

    try:
        target.alpha_mode = source.alpha_mode
    except Exception:
        pass

    try:
        target.use_fake_user = source.use_fake_user
    except Exception:
        pass


def create_padded_image(
    plan: ImagePlan,
    output_dir: str,
    run_id: str,
) -> bpy.types.Image:
    source = plan.source_image

    source_width = plan.source_width
    source_height = plan.source_height

    target_width = plan.target_width
    target_height = plan.target_height

    source_pixels = np.empty(
        source_width * source_height * 4,
        dtype=np.float32,
    )

    source.pixels.foreach_get(source_pixels)

    source_pixels = source_pixels.reshape(
        (source_height, source_width, 4)
    )

    target_pixels = np.empty(
        (target_height, target_width, 4),
        dtype=np.float32,
    )

    target_pixels[:, :, 0] = PAD_RGBA[0]
    target_pixels[:, :, 1] = PAD_RGBA[1]
    target_pixels[:, :, 2] = PAD_RGBA[2]
    target_pixels[:, :, 3] = PAD_RGBA[3]

    # Blender хранит строки пикселей снизу вверх.
    # Чтобы визуально сохранить левый верхний угол,
    # кладём исходник в верхнюю часть нового буфера.
    row_start = target_height - source_height
    row_end = target_height

    target_pixels[
        row_start:row_end,
        0:source_width,
        :,
    ] = source_pixels

    source.scale(target_width, target_height)
    source.pixels.foreach_set(target_pixels.reshape(-1))
    source.update()
    source["rzm_source_size_before_padding"] = f"{source_width}x{source_height}"
    source["rzm_target_size_after_padding"] = f"{target_width}x{target_height}"
    source["rzm_last_padding_run"] = run_id

    filepath = bpy.path.abspath(source.filepath_raw or source.filepath)
    if not filepath:
        filepath = unique_output_path(
            output_dir=output_dir,
            image_name=source.name,
            target_width=target_width,
            target_height=target_height,
            run_id=run_id,
        )
        source.filepath_raw = filepath
        source.filepath = filepath
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    source.file_format = "PNG"
    source.save()
    plan.output_path = filepath

    return source


# ============================================================
# MATERIAL NODE REPLACEMENT
# ============================================================

def replace_node_images(
    image_nodes: list[bpy.types.Node],
    image_plans: list[ImagePlan],
) -> list[tuple[bpy.types.Node, bpy.types.Image]]:
    replacement_by_pointer: dict[int, bpy.types.Image] = {}

    for plan in image_plans:
        replacement = plan.source_image

        replacement_by_pointer[
            plan.source_image.as_pointer()
        ] = replacement

    original_assignments: list[
        tuple[bpy.types.Node, bpy.types.Image]
    ] = []

    for node in image_nodes:
        source_image = node.image

        if source_image is None:
            continue

        replacement = replacement_by_pointer.get(
            source_image.as_pointer()
        )

        if replacement is None:
            continue

        original_assignments.append(
            (node, source_image)
        )

        node.image = replacement

    return original_assignments


def restore_node_images(
    original_assignments: list[
        tuple[bpy.types.Node, bpy.types.Image]
    ],
) -> None:
    for node, original_image in original_assignments:
        node.image = original_image


# ============================================================
# MAIN
# ============================================================

def run() -> None:
    LINES.clear()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    active_obj = get_active_mesh_object()
    previous_mode = active_obj.mode

    if previous_mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    created_images: list[bpy.types.Image] = []
    created_files: list[str] = []
    uv_backups: list[tuple[bpy.types.Mesh, str]] = []
    original_node_assignments: list[
        tuple[bpy.types.Node, bpy.types.Image]
    ] = []

    try:
        active_material = get_active_material(active_obj)

        usages = find_real_material_usages(active_material)

        if not usages:
            raise RuntimeError(
                f"Материал '{active_material.name}' "
                "не назначен ни одной грани сцены."
            )

        mesh_plans = build_mesh_plans(usages)

        image_nodes, group_names = collect_reachable_image_nodes(
            active_material
        )

        if not image_nodes:
            raise RuntimeError(
                f"В материале '{active_material.name}' "
                "не найдено подключённых Image Texture нод."
            )

        images = collect_unique_images(image_nodes)

        if not images:
            raise RuntimeError(
                "Не найдено изображений для обработки."
            )

        image_plans, scale_x, scale_y = build_image_plans(
            images
        )

        validate_uv_range(mesh_plans)

        log(divider("="))
        log("RZM TEXTURE PADDING")
        log(divider("="))
        log(f"Active object:    {active_obj.name}")
        log(f"Active material:  {active_material.name}")
        log(f"Required UV:      {UV_NAME}")
        log(f"Run ID:           {run_id}")
        log()
        log(f"UV scale X:       {scale_x:.12f}")
        log(f"UV scale Y:       {scale_y:.12f}")
        log()

        if group_names:
            log("WARNING: Node Groups found on material path:")

            for group_name in group_names:
                log(f"  - {group_name}")

            log(
                "Their internal textures were not modified "
                "to avoid changing shared node groups."
            )
            log()

        log(divider())
        log("REAL MATERIAL USAGES")
        log(divider())

        for usage in usages:
            log(
                f"{usage.obj.name}: "
                f"slot {usage.slot_index}, "
                f"{usage.face_count} assigned faces"
            )

        log()
        log(divider())
        log("IMAGE PLAN")
        log(divider())

        needs_any_padding = False

        for plan in image_plans:
            log(
                f"{plan.source_image.name}: "
                f"{plan.source_width}x{plan.source_height} "
                f"→ {plan.target_width}x{plan.target_height}"
            )

            if plan.needs_padding:
                needs_any_padding = True

        if not needs_any_padding:
            log()
            log("Все текстуры уже имеют допустимый размер.")
            log("UV и изображения не изменены.")
            log(divider("="))

            save_report()
            return

        output_dir = get_output_directory()

        log()
        log(f"Output directory: {output_dir}")
        log()
        log(divider())
        log("CREATING PADDED IMAGES")
        log(divider())

        for plan in image_plans:
            if not plan.needs_padding:
                continue

            padded = create_padded_image(
                plan=plan,
                output_dir=output_dir,
                run_id=run_id,
            )

            # Destructive mode: the source image was edited in place, so there is
            # no temporary Blender image to track or remove on errors.

            if plan.output_path:
                pass

            log(
                f"Updated: {padded.name} "
                f"({plan.target_width}x{plan.target_height})"
            )

            if plan.output_path:
                log(f"Saved:   {plan.output_path}")

        log()
        log(divider())
        log("BACKING UP UV LAYERS")
        log(divider())

        for plan in mesh_plans:
            backup_name = backup_uv_layer(
                mesh=plan.mesh,
                run_id=run_id,
            )

            plan.backup_uv_name = backup_name
            uv_backups.append(
                (plan.mesh, backup_name)
            )

            objects_text = ", ".join(
                sorted(plan.object_names)
            )

            log(
                f"{plan.mesh.name}: "
                f"{UV_NAME} → {backup_name}"
            )
            log(f"  Objects: {objects_text}")
            log(
                f"  Affected polygons: "
                f"{len(plan.polygon_indices)}"
            )
            log(
                f"  Affected UV loops: "
                f"{len(plan.loop_indices)}"
            )

        log()
        log(divider())
        log("APPLYING UV TRANSFORM")
        log(divider())

        apply_uv_transform(
            mesh_plans=mesh_plans,
            scale_x=scale_x,
            scale_y=scale_y,
        )

        log(
            "UV transformed with top-left anchor "
            "(visual texture position preserved)."
        )

        log()
        log(divider())
        log("REPLACING MATERIAL TEXTURES")
        log(divider())

        original_node_assignments = replace_node_images(
            image_nodes=image_nodes,
            image_plans=image_plans,
        )

        for node, original_image in original_node_assignments:
            replacement_name = (
                node.image.name
                if node.image is not None
                else "<None>"
            )

            log(
                f"{node.name}: "
                f"{original_image.name} → {replacement_name}"
            )

        active_material["rzm_last_padding_run"] = run_id
        active_material["rzm_uv_scale_x"] = scale_x
        active_material["rzm_uv_scale_y"] = scale_y

        log()
        log(divider("="))
        log("SUCCESS")
        log(divider("="))
        log(
            f"Objects using active material: {len(usages)}"
        )
        log(
            f"Unique Mesh datablocks changed: {len(mesh_plans)}"
        )
        log(
            f"Unique textures inspected: {len(image_plans)}"
        )
        log(
            f"New padded textures created: {len(created_images)}"
        )
        log()
        log(
            "Original textures remain untouched. "
            "UV backups remain inside each modified mesh."
        )
        log(divider("="))

        save_report()

    except Exception as error:
        log()
        log(divider("="))
        log("ERROR: ROLLING BACK")
        log(divider("="))
        log(f"{type(error).__name__}: {error}")

        restore_node_images(original_node_assignments)

        for mesh, backup_name in uv_backups:
            restore_uv_layer(
                mesh=mesh,
                backup_name=backup_name,
            )

        for image in created_images:
            try:
                bpy.data.images.remove(image)
            except Exception:
                pass

        for filepath in created_files:
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
            except Exception:
                pass

        log()
        log("Rollback finished.")
        log("Original images and UV coordinates restored.")
        log(divider("="))

        save_report()

        raise

    finally:
        if (
            previous_mode == "EDIT"
            and bpy.context.active_object == active_obj
        ):
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except Exception:
                pass


# ============================================================
# RUN
# ============================================================

run()
