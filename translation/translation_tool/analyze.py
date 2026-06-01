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


def prompt_locale_selection(human_files):
    if not human_files:
        return []

    print("Select human translation file(s) to analyze:")
    print("  0) All human translation files")
    for index, filename in enumerate(human_files, start=1):
        print(f"  {index}) {filename}")

    raw = input("Enter numbers separated by commas (default: 0): ").strip()
    if not raw or raw == "0":
        return human_files

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
        if 1 <= idx <= len(human_files) and idx not in seen:
            seen.add(idx)
            selected.append(human_files[idx - 1])

    return selected or human_files


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


def analyze_human_translation(filename, code_strings):
    human = load_json_file(filename)
    total = len(code_strings)

    if total == 0:
        print(f"No source strings found to translate for {filename}.")
        return

    translated = 0
    missing = []

    for s in code_strings:
        if s in human:
            translated += 1
        else:
            missing.append(s)

    pct_total = (translated / total) * 100
    pct_missing = 100 - pct_total

    print("=" * 72)
    print(f" HUMAN TRANSLATION: {filename}")
    print("=" * 72)
    print(f"Source strings:            {total}")
    print(f"Translated in human JSON:  {translated} ({pct_total:.1f}%)")
    print(f"Missing from human JSON:    {len(missing)} ({pct_missing:.1f}%)")
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
    code_strings = extract_strings_from_codebase()

    print(f"Scan complete. Found {len(code_strings)} unique UI strings.\n")

    if human_files:
        print("Available human translation files:")
        for filename in human_files:
            print(f"  - {filename}")
        print()
    else:
        print("No human translation files found in locales.\n")

    if auto_files:
        print("Auto translation files found but ignored by this report:")
        for filename in auto_files:
            print(f"  - {filename}")
        print()

    selected_files = prompt_locale_selection(human_files)
    print()

    for filename in selected_files:
        analyze_human_translation(filename, code_strings)


if __name__ == "__main__":
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            import codecs
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    main()
