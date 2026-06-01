import ast
import json
import os
import sys


TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATION_DIR = os.path.dirname(TOOL_DIR)
ADDON_DIR = os.path.dirname(TRANSLATION_DIR)
LOCALES_DIR = os.path.join(TRANSLATION_DIR, "locales")

EXCLUDE_DIRS = {
    "libs",
    "translation_tool",
    "__pycache__",
    ".git",
    ".vscode",
    "reserve",
    "!TEST",
    "claude_answer",
    "user_data",
    "scratch",
}

KEYWORDS = {"text", "name", "description", "bl_label", "bl_description"}
METHODS = {"setText", "setWindowTitle", "setTitle", "setToolTip"}


def discover_locale_files():
    if not os.path.isdir(LOCALES_DIR):
        return [], []

    human_files = []
    auto_files = []

    for filename in sorted(os.listdir(LOCALES_DIR)):
        if not filename.endswith(".json"):
            continue
        if filename.endswith("_auto.json"):
            auto_files.append(filename)
        else:
            human_files.append(filename)

    return human_files, auto_files


def locale_base_name(filename):
    if filename.endswith("_auto.json"):
        return filename[:-10]
    return filename[:-5]


def discover_locale_families(human_files, auto_files):
    families = {}

    for filename in human_files + auto_files:
        lang = locale_base_name(filename)
        families.setdefault(lang, {"human": None, "auto": None})
        if filename.endswith("_auto.json"):
            families[lang]["auto"] = filename
        else:
            families[lang]["human"] = filename

    return [families[key] for key in sorted(families)]


def prompt_locale_selection(locale_families):
    if not locale_families:
        return []

    print("Select translation file(s) to analyze:")
    print("  0) All available translation sets")
    for index, family in enumerate(locale_families, start=1):
        parts = []
        if family["human"]:
            parts.append(family["human"])
        if family["auto"]:
            parts.append(family["auto"])
        label = ", ".join(parts) if parts else "<empty>"
        print(f"  {index}) {label}")

    raw = input("Enter numbers separated by commas (default: 0): ").strip()
    if not raw or raw == "0":
        return locale_families

    selected = []
    seen = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            idx = int(token)
        except ValueError:
            continue
        if 1 <= idx <= len(locale_families) and idx not in seen:
            seen.add(idx)
            selected.append(locale_families[idx - 1])

    return selected or locale_families


def extract_strings_from_codebase():
    """Scans RZMenu python files and extracts potential UI strings using AST parsing."""
    found_strings = set()

    for root, dirs, files in os.walk(ADDON_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            if not file.endswith(".py") or file in {"__init__.py", "analyze.py"}:
                continue

            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content, filename=filepath)

                for node in ast.walk(tree):
                    for child in ast.iter_child_nodes(node):
                        child.parent = node

                class UIStringVisitor(ast.NodeVisitor):
                    def visit_Constant(self, node):
                        if isinstance(node.value, str):
                            self.check_val(node.value, node)

                    def visit_Str(self, node):
                        self.check_val(node.s, node)

                    def check_val(self, val, node):
                        val_clean = val.strip()
                        if not val_clean or len(val_clean) < 2:
                            return

                        parent = getattr(node, "parent", None)
                        if parent:
                            if isinstance(parent, ast.keyword) and parent.arg in KEYWORDS:
                                found_strings.add(val_clean)
                            elif isinstance(parent, ast.Assign):
                                for target in parent.targets:
                                    if isinstance(target, ast.Name) and target.id in KEYWORDS:
                                        found_strings.add(val_clean)
                            elif isinstance(parent, ast.Call):
                                if isinstance(parent.func, ast.Attribute) and parent.func.attr in METHODS:
                                    found_strings.add(val_clean)

                UIStringVisitor().visit(tree)
            except Exception as e:
                print(f"Warning: Failed to parse {filepath}: {e}")

    return sorted(found_strings)


def load_json_file(filename):
    filepath = os.path.join(LOCALES_DIR, filename)
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {}


def load_merged_translation_set(family):
    merged = {}
    auto_file = family["auto"]
    human_file = family["human"]

    if auto_file:
        merged.update(load_json_file(auto_file))
    if human_file:
        merged.update(load_json_file(human_file))

    return merged


def analyze_translation_family(family, code_strings):
    merged = load_merged_translation_set(family)
    total = len(code_strings)
    family_name = locale_base_name(family["human"] or family["auto"])

    if total == 0:
        print(f"No source strings found to translate for {family_name}.")
        return

    translated = 0
    missing = []

    for s in code_strings:
        if s in merged:
            translated += 1
        else:
            missing.append(s)

    pct_total = (translated / total) * 100
    pct_missing = 100 - pct_total

    print("=" * 72)
    print(f" TRANSLATION SET: {family_name}")
    print("=" * 72)
    if family["human"]:
        print(f"Human JSON: {family['human']}")
    if family["auto"]:
        print(f"Auto JSON:  {family['auto']}")
    print(f"Source strings:            {total}")
    print(f"Translated in set:         {translated} ({pct_total:.1f}%)")
    print(f"Missing from set:          {len(missing)} ({pct_missing:.1f}%)")
    print("-" * 72)

    if missing:
        print("Missing strings JSON:")
        print(json.dumps({m: "" for m in missing[:50]}, ensure_ascii=False, indent=2))
        if len(missing) > 50:
            print(f"... and {len(missing) - 50} more strings.")
    else:
        print("All strings are covered by the human translation file.")
    print()


def main():
    print("Scanning RZMenu codebase for user-facing UI strings...")
    human_files, auto_files = discover_locale_files()
    locale_families = discover_locale_families(human_files, auto_files)
    code_strings = extract_strings_from_codebase()

    print(f"Scan complete. Found {len(code_strings)} unique UI strings.\n")

    if human_files or auto_files:
        print("Available translation files:")
        for filename in human_files:
            print(f"  - {filename}")
        for filename in auto_files:
            print(f"  - {filename}")
        print()
    else:
        print("No translation files found in locales.\n")

    selected_files = prompt_locale_selection(locale_families)
    print()

    for family in selected_files:
        analyze_translation_family(family, code_strings)


if __name__ == "__main__":
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            import codecs
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    main()
