# QA/test_ini_segment_validation.py
# Tests for segmented INI/RZM export validation.

from pathlib import Path
import contextlib
import importlib.util
import io
import sys
import traceback
from types import SimpleNamespace


def _find_addon_root() -> Path:
    candidates = []

    file_name = globals().get("__file__")
    if file_name and not str(file_name).startswith("<"):
        candidates.append(Path(file_name).resolve())

    candidates.append(Path.cwd().resolve())

    try:
        import bpy

        text = getattr(getattr(bpy.context, "space_data", None), "text", None)
        text_path = getattr(text, "filepath", None)
        if text_path:
            candidates.append(Path(text_path).resolve())

        scripts_addons = bpy.utils.user_resource("SCRIPTS", path="addons")
        if scripts_addons:
            candidates.append(Path(scripts_addons).resolve() / "RZMenu")
    except Exception:
        pass

    for candidate in candidates:
        for root in [candidate, *candidate.parents]:
            if (root / "rztemplate").is_dir() and (root / "core" / "ini_validation.py").is_file():
                return root

    raise RuntimeError("Could not find RZMenu addon root for INI validation test.")


def _load_ini_validation(root: Path):
    module_path = root / "core" / "ini_validation.py"
    spec = importlib.util.spec_from_file_location("rzm_ini_validation", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load validation module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ROOT = _find_addon_root()
LIBS = ROOT / "libs"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(LIBS) not in sys.path:
    sys.path.insert(0, str(LIBS))

_ini_validation = _load_ini_validation(ROOT)
extract_ini_sections = _ini_validation.extract_ini_sections
validate_export_cache = _ini_validation.validate_export_cache
validate_ini_text = _ini_validation.validate_ini_text
_namespace_hash = None


def _load_namespace_hash():
    global _namespace_hash
    if _namespace_hash is None:
        module_path = ROOT / "core" / "namespace_hash.py"
        spec = importlib.util.spec_from_file_location("rzm_namespace_hash", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load namespace module: {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _namespace_hash = module
    return _namespace_hash


def _issue_codes(result):
    return {issue.code for issue in result.issues}


def test_valid_segmented_ini_fragment_passes():
    text = """
;[META-INFO] [START] [RZM-SEGMENT] [MENU_CORE]
[Constants]
global $active = 0

[Present]
run = CommandListRZMain

;[META-INFO] [END] [RZM-SEGMENT] [MENU_CORE]
""".strip()

    result = validate_ini_text(text, segment="menu_core")
    assert result.ok, result.issues
    assert [section.name for section in extract_ini_sections(text)] == [
        "Constants",
        "Present",
    ]


def test_duplicate_non_appendable_sections_fail():
    text = """
[CommandListRZMain]
run = CommandListA

[Constants]
global $a = 0

[Constants]
global $b = 0

[CommandListRZMain]
run = CommandListB
""".strip()

    result = validate_ini_text(text, segment="dup_check")
    assert not result.ok
    assert "duplicate_section" in _issue_codes(result)


def test_unbalanced_meta_info_fails():
    text = """
;[META-INFO] [START] [RZM-SEGMENT] [SHAPES]
[CommandListShape]
run = CustomShaderComputeShapes
;[META-INFO] [END] [RZM-SEGMENT] [WEIGHTS]
""".strip()

    result = validate_ini_text(text, segment="meta_check")
    assert not result.ok
    assert "meta_tag_mismatch" in _issue_codes(result)


def test_rendered_ini_must_not_keep_jinja_or_placeholder():
    text = """
[Constants]
global $broken = {{ unresolved }}
;[RZM-QUICK-UPDATE-PLACEHOLDER]
""".strip()

    result = validate_ini_text(text, segment="rendered_final")
    assert not result.ok
    assert "unresolved_template_marker" in _issue_codes(result)
    assert "quick_update_placeholder" in _issue_codes(result)


def test_export_cache_with_vertex_maps_passes_strict_shape_mode():
    cache = {
        "source": "xxmi",
        "mod_name": "Hero",
        "timestamp": 1.0,
        "components": {
            "Body": {
                "n_verts": 6,
                "objects": [
                    {
                        "name": "BodyMesh",
                        "vb_offset": 0,
                        "vb_count": 3,
                        "vertex_map": [0, 1, 2],
                    },
                    {
                        "name": "SleeveMesh",
                        "vb_offset": 3,
                        "vb_count": 3,
                        "vertex_map": [3, 4, 5],
                    },
                ],
            }
        },
    }

    result = validate_export_cache(cache, require_vertex_maps=True)
    assert result.ok, result.issues


def test_export_cache_requires_vertex_maps_for_shape_segments():
    cache = {
        "source": "efmi",
        "components": {
            "Component0": {
                "n_verts": 4,
                "objects": [
                    {
                        "name": "MeshA",
                        "vb_offset": 0,
                        "vb_count": 4,
                        "vertex_map": None,
                    }
                ],
            }
        },
    }

    result = validate_export_cache(cache, require_vertex_maps=True)
    assert not result.ok
    assert "object_vertex_map_missing" in _issue_codes(result)


def test_export_cache_rejects_overflow_and_overlap():
    cache = {
        "source": "xxmi",
        "components": {
            "Body": {
                "n_verts": 5,
                "objects": [
                    {
                        "name": "A",
                        "vb_offset": 0,
                        "vb_count": 4,
                        "vertex_map": [0, 1, 2, 3],
                    },
                    {
                        "name": "B",
                        "vb_offset": 3,
                        "vb_count": 4,
                        "vertex_map": [3, 4, 5, 6],
                    },
                ],
            }
        },
    }

    result = validate_export_cache(cache)
    assert not result.ok
    codes = _issue_codes(result)
    assert "object_range_overflow" in codes
    assert "object_range_overlap" in codes


def test_all_rztemplate_jinja_files_parse():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(ROOT / "rztemplate")))
    templates = sorted((ROOT / "rztemplate").rglob("*.j2"))
    assert templates, "Expected RZM jinja templates to exist."

    for template_path in templates:
        rel = template_path.relative_to(ROOT / "rztemplate").as_posix()
        source, _, _ = env.loader.get_source(env, rel)
        env.parse(source)


def test_rz_uni_keeps_mod_block_contract_for_native_export_patch():
    source = (ROOT / "rztemplate" / "rz_uni.j2").read_text(encoding="utf-8")

    assert source.count(";[META-INFO] [START] [MOD-BLOCK]") == 1
    assert source.count(";[META-INFO] [END] [MOD-BLOCK]") == 1
    assert ";[RZM-QUICK-UPDATE-PLACEHOLDER]" in source
    assert "{% block hoyo_main %}" in source


def test_namespace_hash_is_stable_for_same_project():
    ns_mod = _load_namespace_hash()
    a = ns_mod.build_namespace(
        character_name="YiXuan",
        author_name="Rayvich",
        skin_name="Demonic",
        project_seed="ABCDEF0123456789",
        os_name="Windows",
        user_name="Rayvy",
    )
    b = ns_mod.build_namespace(
        character_name="YiXuan",
        author_name="Rayvich",
        skin_name="Demonic",
        project_seed="ABCDEF0123456789",
        os_name="Windows",
        user_name="Rayvy",
    )
    assert a.full == b.full
    assert a.full.startswith("RAYI")
    assert len(a.base8) == 4
    assert len(a.skin4) == 2
    assert len(a.hash12) == 6
    assert len(a.namespace) == 10


def test_namespace_skin_changes_only_suffix():
    ns_mod = _load_namespace_hash()
    base = {
        "character_name": "YiXuan",
        "author_name": "Rayvich",
        "project_seed": "ABCDEF0123456789",
        "os_name": "Windows",
        "user_name": "Rayvy",
    }
    demonic = ns_mod.build_namespace(skin_name="Demonic", **base)
    lewdic = ns_mod.build_namespace(skin_name="Lewdic", **base)
    assert demonic.base8 == lewdic.base8
    assert demonic.skin4 != lewdic.skin4
    assert demonic.namespace != lewdic.namespace


def test_namespace_project_seed_changes_base():
    ns_mod = _load_namespace_hash()
    a = ns_mod.build_namespace(
        character_name="YiXuan",
        author_name="Rayvich",
        skin_name="Demonic",
        project_seed="PROJECT_A",
        os_name="Windows",
        user_name="Rayvy",
    )
    b = ns_mod.build_namespace(
        character_name="YiXuan",
        author_name="Rayvich",
        skin_name="Demonic",
        project_seed="PROJECT_B",
        os_name="Windows",
        user_name="Rayvy",
    )
    assert a.base8 != b.base8
    assert a.skin4 == b.skin4


def test_namespace_author_initial_prefix():
    ns_mod = _load_namespace_hash()
    ns = ns_mod.build_namespace(
        character_name="Velina",
        author_name="Rayvich",
        skin_name="Default",
        project_seed="PROJECT_A",
        os_name="Windows",
        user_name="Rayvy",
    )
    assert ns.namespace.startswith("RAVE")
    assert ns.full == ns.namespace


def test_namespace_xxmi_character_prefers_dump_folder():
    ns_mod = _load_namespace_hash()
    context = SimpleNamespace(
        scene=SimpleNamespace(
            xxmi=SimpleNamespace(dump_path=r"G:\XXMI\ZZMI\gui_collect-1.3.0\Extracted\Velina"),
            rzm=SimpleNamespace(
                game=SimpleNamespace(selection="ZenlessZoneZero", name="ZenlessZoneZero"),
                meta_data=SimpleNamespace(character_name="Fluorite"),
            ),
        )
    )
    assert ns_mod.resolve_character_name(context, export_cache={"mod_name": "RayvichYiXuan"}) == "Velina"


TESTS = [
    test_valid_segmented_ini_fragment_passes,
    test_duplicate_non_appendable_sections_fail,
    test_unbalanced_meta_info_fails,
    test_rendered_ini_must_not_keep_jinja_or_placeholder,
    test_export_cache_with_vertex_maps_passes_strict_shape_mode,
    test_export_cache_requires_vertex_maps_for_shape_segments,
    test_export_cache_rejects_overflow_and_overlap,
    test_all_rztemplate_jinja_files_parse,
    test_rz_uni_keeps_mod_block_contract_for_native_export_patch,
    test_namespace_hash_is_stable_for_same_project,
    test_namespace_skin_changes_only_suffix,
    test_namespace_project_seed_changes_base,
    test_namespace_author_initial_prefix,
    test_namespace_xxmi_character_prefers_dump_folder,
]


if __name__ == "__main__":
    output = []
    passed = 0
    failed = 0
    for fn in TESTS:
        output.append(f"\n--- {fn.__name__} ---")
        try:
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                fn()
            captured_text = capture.getvalue().strip()
            if captured_text:
                output.append(captured_text)
            output.append("[PASS]")
            passed += 1
        except Exception as ex:
            output.append(f"[FAIL] {ex}")
            output.append(traceback.format_exc())
            failed += 1
    output.append(f"\n{'=' * 50}")
    output.append(f"Results: {passed} passed, {failed} failed / {len(TESTS)} total")
    summary = "\n".join(output)
    print(summary)

    try:
        import bpy

        text_name = "RZM_INI_SEGMENT_VALIDATION_RESULT"
        text_block = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
        text_block.clear()
        text_block.write(summary + "\n")

        screen = getattr(bpy.context, "screen", None)
        if screen:
            for area in screen.areas:
                if area.type == "TEXT_EDITOR":
                    area.spaces.active.text = text_block
                    break

        title = "RZM INI validation OK" if failed == 0 else "RZM INI validation FAILED"
        icon = "CHECKMARK" if failed == 0 else "ERROR"
        popup_lines = [
            f"Results: {passed} passed, {failed} failed / {len(TESTS)} total",
            f"Full log: Text block '{text_name}'",
        ]

        def draw_popup(self, _context):
            for line in popup_lines:
                self.layout.label(text=line)

        bpy.context.window_manager.popup_menu(draw_popup, title=title, icon=icon)
    except Exception:
        pass

    if failed:
        raise SystemExit(1)
