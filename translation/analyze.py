#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RZMenu Translation Tool
=======================
Desktop utility for translators of the RZMenu Blender add-on.

What it does
------------
* Finds the RZMenu project root and works with translation/locales/*.json.
* Scans add-on source files for translatable strings.
* Separates human translations, auto translations and effective translations.
* Provides tabs for overview, editing, missing keys, search, contributors,
  settings and logs.
* Stores translator attribution in a sidecar metadata file without changing the
  structure of existing locale JSON files.
* Writes JSON atomically and creates a backup before replacing an existing file.

Dependencies
------------
Required: Python 3.10+ with tkinter (usually bundled with regular Python builds).
Optional: deep-translator==1.11.4 for automatic translation.

If optional dependencies are missing, the app starts in safe mode and offers to
install the exact supported version. Manual editing, scanning and JSON saving
remain available. If tkinter itself is unavailable, a readable message is shown
instead of a traceback.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

APP_NAME = "RZMenu Translation Tool"
APP_VERSION = "1.0.0"
OPTIONAL_TRANSLATOR_PACKAGE = "deep-translator==1.11.4"
SUPPORTED_LOCALES = ("ru", "zh_CN")
LAYER_HUMAN = "human"
LAYER_AUTO = "auto"
META_FILENAME = ".rzmenu_translation_meta.json"
SETTINGS_FILENAME = ".rzmenu_translation_tool.json"

TRANSLATION_CALL_NAMES = {
    "_", "tr", "translate", "translation", "i18n", "gettext", "pgettext", "t"
}
UI_KEYWORDS = {"text", "label", "description", "name", "message", "title"}
CODE_SUFFIXES = {".py"}
SKIP_DIRS = {".git", ".idea", ".vscode", "__pycache__", "locales", "node_modules", ".venv", "venv"}

PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
DECORATIVE_RE = re.compile(r"^[\s\-–—_=+*~.•·⋅|/\\:;,.!?…\[\](){}<>]+$")

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
except Exception as tkinter_error:  # pragma: no cover - environment dependent
    tk = None  # type: ignore[assignment]
    filedialog = messagebox = simpledialog = ttk = None  # type: ignore[assignment]
    TKINTER_IMPORT_ERROR = tkinter_error
else:
    TKINTER_IMPORT_ERROR = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_message(title: str, text: str) -> None:
    """Best-effort readable error without depending on tkinter."""
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
            return
    except Exception:
        pass
    print(f"{title}\n{'=' * len(title)}\n{text}", file=sys.stderr)


def is_decorative_or_empty(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    if stripped in {"--", "...", "…", "-", "—", "___", "***", "===", "|", "/"}:
        return True
    if DECORATIVE_RE.fullmatch(stripped):
        return True
    return False


def placeholders(value: str) -> tuple[str, ...]:
    return tuple(PLACEHOLDER_RE.findall(value))


def validate_placeholders(source: str, translated: str) -> tuple[bool, str]:
    src = sorted(placeholders(source))
    dst = sorted(placeholders(translated))
    if src == dst:
        return True, ""
    return False, f"Placeholders differ. Source: {src or 'none'}; translation: {dst or 'none'}"


def load_json_dict(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    result: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ValueError(f"Non-string key in {path}: {key!r}")
        if not isinstance(value, str):
            raise ValueError(f"Non-string translation for key {key!r} in {path}")
        result[key] = value
    return result


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Pretty JSON save with backup and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def load_settings_file() -> dict[str, Any]:
    path = Path.home() / SETTINGS_FILENAME
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            return raw if isinstance(raw, dict) else {}
    except Exception:
        pass
    return {}


def save_settings_file(settings: dict[str, Any]) -> None:
    atomic_write_json(Path.home() / SETTINGS_FILENAME, settings)


@dataclass
class ProjectPaths:
    root: Path

    @property
    def locales_dir(self) -> Path:
        return self.root / "translation" / "locales"

    @property
    def analyzer(self) -> Path:
        return self.root / "translation" / "translation_tool" / "analyze.py"

    @property
    def translation_init(self) -> Path:
        return self.root / "translation" / "__init__.py"

    @property
    def meta_path(self) -> Path:
        return self.locales_dir / META_FILENAME

    def locale_path(self, locale: str, layer: str) -> Path:
        suffix = "_auto" if layer == LAYER_AUTO else ""
        return self.locales_dir / f"{locale}{suffix}.json"

    def missing_parts(self) -> list[str]:
        missing: list[str] = []
        if not self.root.exists():
            missing.append(f"project root: {self.root}")
            return missing
        if not self.locales_dir.exists():
            missing.append(f"locales directory: {self.locales_dir}")
        if not self.analyzer.exists():
            missing.append(f"analyzer: {self.analyzer}")
        if not self.translation_init.exists():
            missing.append(f"translation package file: {self.translation_init}")
        return missing

    def locale_file_report(self) -> list[str]:
        report: list[str] = []
        for locale in SUPPORTED_LOCALES:
            for layer in (LAYER_HUMAN, LAYER_AUTO):
                path = self.locale_path(locale, layer)
                if not path.exists():
                    report.append(str(path))
        return report


def discover_project_root(explicit: Optional[str] = None) -> Optional[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    script = Path(__file__).resolve()
    candidates.extend([
        script.parent,
        script.parent.parent,
        script.parent.parent.parent,
        Path.cwd(),
        Path.cwd() / "RZMenu",
    ])
    seen: set[str] = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except Exception:
            continue
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if (candidate / "translation" / "locales").exists():
            return candidate
    return None


@dataclass
class SourceRef:
    relative_path: str
    line: int
    context: str
    kind: str

    def compact(self) -> str:
        return f"{self.relative_path}:{self.line} [{self.kind}]"


@dataclass
class ScanEntry:
    key: str
    refs: list[SourceRef] = field(default_factory=list)

    def add_ref(self, ref: SourceRef) -> None:
        marker = (ref.relative_path, ref.line, ref.kind)
        existing = {(item.relative_path, item.line, item.kind) for item in self.refs}
        if marker not in existing:
            self.refs.append(ref)


class TranslationScanner:
    def __init__(self, root: Path, include_ui_literals: bool, logger: Callable[[str], None]) -> None:
        self.root = root
        self.include_ui_literals = include_ui_literals
        self.log = logger

    def _should_skip(self, path: Path) -> bool:
        relative = path.relative_to(self.root)
        return any(part in SKIP_DIRS or part == "translation_tool" for part in relative.parts)

    def scan(self) -> dict[str, ScanEntry]:
        entries: dict[str, ScanEntry] = {}
        python_files = [
            path for path in self.root.rglob("*.py")
            if path.is_file() and not self._should_skip(path)
        ]
        self.log(f"Scanning {len(python_files)} Python files under {self.root}")
        for path in python_files:
            self._scan_python(path, entries)
        self.log(f"Scanner found {len(entries)} translatable source strings")
        return dict(sorted(entries.items(), key=lambda item: item[0].lower()))

    def _scan_python(self, path: Path, entries: dict[str, ScanEntry]) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as exc:
            self.log(f"Skipped unreadable file {path}: {exc}")
            return

        lines = text.splitlines()
        relative = str(path.relative_to(self.root))
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            self.log(f"AST parse failed for {relative}:{exc.lineno}; regex fallback enabled")
            self._regex_fallback(text, lines, relative, entries)
            return

        scanner = _AstStringCollector(self.include_ui_literals)
        scanner.visit(tree)
        for key, line, kind in scanner.items:
            if is_decorative_or_empty(key):
                continue
            context = lines[line - 1].strip() if 0 < line <= len(lines) else ""
            entries.setdefault(key, ScanEntry(key)).add_ref(SourceRef(relative, line, context, kind))

    def _regex_fallback(self, text: str, lines: list[str], relative: str, entries: dict[str, ScanEntry]) -> None:
        pattern = re.compile(r"(?:_|tr|translate|translation|i18n|gettext|pgettext|t)\(\s*(['\"])(.*?)\1", re.DOTALL)
        for match in pattern.finditer(text):
            key = match.group(2)
            if is_decorative_or_empty(key):
                continue
            line = text.count("\n", 0, match.start()) + 1
            context = lines[line - 1].strip() if 0 < line <= len(lines) else ""
            entries.setdefault(key, ScanEntry(key)).add_ref(SourceRef(relative, line, context, "regex fallback"))


class _AstStringCollector(ast.NodeVisitor):
    def __init__(self, include_ui_literals: bool) -> None:
        self.include_ui_literals = include_ui_literals
        self.items: list[tuple[str, int, str]] = []

    @staticmethod
    def _func_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    @staticmethod
    def _string(node: ast.AST) -> Optional[str]:
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    def visit_Call(self, node: ast.Call) -> Any:
        name = self._func_name(node.func)
        if name in TRANSLATION_CALL_NAMES and node.args:
            value = self._string(node.args[0])
            if value is not None:
                self.items.append((value, getattr(node, "lineno", 1), f"{name}(...)"))
        if self.include_ui_literals:
            for keyword in node.keywords:
                if keyword.arg in UI_KEYWORDS:
                    value = self._string(keyword.value)
                    if value is not None:
                        self.items.append((value, getattr(keyword.value, "lineno", getattr(node, "lineno", 1)), f"keyword {keyword.arg}="))
        self.generic_visit(node)


class MetadataStore:
    def __init__(self, path: Path, logger: Callable[[str], None]) -> None:
        self.path = path
        self.log = logger
        self.data: dict[str, Any] = {"schema_version": 1, "entries": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                self.data = raw
                self.data.setdefault("schema_version", 1)
                self.data.setdefault("entries", {})
        except Exception as exc:
            self.log(f"Metadata load warning: {exc}. Existing metadata file was left untouched.")

    def save(self) -> None:
        atomic_write_json(self.path, self.data)

    def get(self, locale: str, layer: str, key: str) -> dict[str, str]:
        entries = self.data.setdefault("entries", {})
        return dict(entries.get(locale, {}).get(layer, {}).get(key, {}))

    def set(self, locale: str, layer: str, key: str, metadata: dict[str, str]) -> None:
        entries = self.data.setdefault("entries", {})
        entries.setdefault(locale, {}).setdefault(layer, {})[key] = metadata

    def delete(self, locale: str, layer: str, key: str) -> None:
        try:
            del self.data["entries"][locale][layer][key]
        except KeyError:
            pass

    def contributor_rows(self) -> list[dict[str, Any]]:
        aggregate: dict[tuple[str, str], dict[str, Any]] = {}
        entries = self.data.get("entries", {})
        for locale, locale_data in entries.items():
            if not isinstance(locale_data, dict):
                continue
            for layer, layer_data in locale_data.items():
                if not isinstance(layer_data, dict):
                    continue
                for _key, meta in layer_data.items():
                    if not isinstance(meta, dict):
                        continue
                    name = str(meta.get("translator_name") or "Unknown")
                    translator_locale = str(meta.get("translator_locale") or "")
                    bucket = aggregate.setdefault((name, translator_locale), {
                        "name": name,
                        "translator_locale": translator_locale,
                        "locales": set(),
                        "human": 0,
                        "auto": 0,
                        "total": 0,
                    })
                    bucket["locales"].add(locale)
                    bucket[layer if layer in {"human", "auto"} else "auto"] += 1
                    bucket["total"] += 1
        rows: list[dict[str, Any]] = []
        for row in aggregate.values():
            row["locales"] = ", ".join(sorted(row["locales"]))
            rows.append(row)
        return sorted(rows, key=lambda item: (-item["total"], item["name"].lower()))


class TranslationStore:
    def __init__(self, paths: ProjectPaths, logger: Callable[[str], None]) -> None:
        self.paths = paths
        self.log = logger
        self.data: dict[str, dict[str, dict[str, str]]] = {}
        self.meta = MetadataStore(paths.meta_path, logger)
        self.load_all()

    def load_all(self) -> None:
        loaded: dict[str, dict[str, dict[str, str]]] = {}
        for locale in SUPPORTED_LOCALES:
            loaded[locale] = {}
            for layer in (LAYER_HUMAN, LAYER_AUTO):
                path = self.paths.locale_path(locale, layer)
                try:
                    loaded[locale][layer] = load_json_dict(path)
                    self.log(f"Loaded {len(loaded[locale][layer])} keys from {path.name}")
                except Exception as exc:
                    self.log(f"Could not read {path}: {exc}")
                    loaded[locale][layer] = {}
        self.data = loaded

    def save_layer(self, locale: str, layer: str) -> None:
        path = self.paths.locale_path(locale, layer)
        atomic_write_json(path, self.data[locale][layer])
        self.meta.save()
        self.log(f"Saved {len(self.data[locale][layer])} keys to {path}")

    def layer(self, locale: str, layer: str) -> dict[str, str]:
        return self.data.setdefault(locale, {}).setdefault(layer, {})

    def effective(self, locale: str) -> dict[str, str]:
        result = dict(self.layer(locale, LAYER_AUTO))
        result.update(self.layer(locale, LAYER_HUMAN))
        return result


class OptionalTranslator:
    def __init__(self, logger: Callable[[str], None]) -> None:
        self.log = logger
        self.available = False
        self.import_error = ""
        self.GoogleTranslator: Any = None
        self.detect()

    def detect(self) -> bool:
        try:
            from deep_translator import GoogleTranslator  # type: ignore
            self.GoogleTranslator = GoogleTranslator
            self.available = True
            self.import_error = ""
            self.log("Optional translator detected: deep-translator")
        except Exception as exc:
            self.GoogleTranslator = None
            self.available = False
            self.import_error = str(exc)
            self.log("Optional translator is unavailable; safe mode remains active")
        return self.available

    def install(self) -> tuple[bool, str]:
        command = [sys.executable, "-m", "pip", "install", OPTIONAL_TRANSLATOR_PACKAGE]
        self.log("Running safe dependency install: " + " ".join(command))
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=240)
        except Exception as exc:
            return False, str(exc)
        output = (completed.stdout + "\n" + completed.stderr).strip()
        self.log(output[-4000:] if output else "pip returned no text output")
        if completed.returncode != 0:
            return False, output or f"pip exited with code {completed.returncode}"
        return self.detect(), output

    def translate(self, text: str, locale: str) -> str:
        if not self.available:
            raise RuntimeError("Auto translation is unavailable in safe mode")
        if is_decorative_or_empty(text):
            return text
        target = {"ru": "ru", "zh_CN": "zh-CN"}.get(locale, locale)
        token_map: dict[str, str] = {}
        protected = text
        for index, item in enumerate(placeholders(text)):
            token = f"__RZMENU_PH_{index}__"
            token_map[token] = item
            protected = protected.replace(item, token, 1)
        translator = self.GoogleTranslator(source="auto", target=target)
        translated = translator.translate(protected)
        for token, item in token_map.items():
            if token not in translated:
                raise ValueError(f"Translator damaged placeholder token {token}")
            translated = translated.replace(token, item)
        ok, reason = validate_placeholders(text, translated)
        if not ok:
            raise ValueError(reason)
        return translated


class RZMenuTranslationApp:
    def __init__(self, root: tk.Tk) -> None:  # type: ignore[name-defined]
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1500x920")
        self.root.minsize(1120, 720)

        self.settings = load_settings_file()
        self.project_paths: Optional[ProjectPaths] = None
        self.store: Optional[TranslationStore] = None
        self.scan_entries: dict[str, ScanEntry] = {}
        self.log_lines: list[str] = []
        self.current_locale = tk.StringVar(value=self.settings.get("locale", "ru"))
        self.include_ui_literals = tk.BooleanVar(value=bool(self.settings.get("include_ui_literals", True)))
        self.default_translator_name = tk.StringVar(value=self.settings.get("translator_name", os.environ.get("USERNAME") or os.environ.get("USER") or "Translator"))
        self.default_translator_locale = tk.StringVar(value=self.settings.get("translator_locale", ""))
        self.search_var = tk.StringVar()
        self.layer_filter_vars: dict[str, tk.StringVar] = {
            LAYER_HUMAN: tk.StringVar(value="all"),
            LAYER_AUTO: tk.StringVar(value="all"),
        }
        self.editor_widgets: dict[str, dict[str, Any]] = {}
        self.layer_trees: dict[str, ttk.Treeview] = {}
        self.selected_key_by_layer: dict[str, str] = {}
        self.translator = OptionalTranslator(self.log)
        self._build_ui()
        self._install_exception_hook()
        self._initialize_project()
        self.root.after(350, self._offer_optional_dependency_if_needed)

    def _install_exception_hook(self) -> None:
        def handler(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
            details = "".join(traceback.format_exception(exc_type, exc, tb))
            self.log("Unhandled error:\n" + details)
            messagebox.showerror(APP_NAME, "An unexpected error occurred. Your files were not intentionally modified.\n\nDetails were copied to the Logs tab.")
        sys.excepthook = handler

    def log(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {text}"
        self.log_lines.append(line)
        widget = getattr(self, "logs_text", None)
        if widget is not None:
            widget.configure(state="normal")
            widget.insert("end", line + "\n")
            widget.see("end")
            widget.configure(state="disabled")

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista" if os.name == "nt" else "clam")
        except Exception:
            pass
        style.configure("Heading.TLabel", font=("TkDefaultFont", 14, "bold"))
        style.configure("CardValue.TLabel", font=("TkDefaultFont", 18, "bold"))

        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text=APP_NAME, style="Heading.TLabel").pack(side="left")
        self.root_label = ttk.Label(top, text="No project selected")
        self.root_label.pack(side="left", padx=(18, 8))
        ttk.Button(top, text="Choose Project Root", command=self.choose_project_root).pack(side="right")
        ttk.Button(top, text="Rescan", command=self.rescan).pack(side="right", padx=(0, 8))
        ttk.Label(top, text="Locale:").pack(side="right", padx=(0, 4))
        self.locale_combo = ttk.Combobox(top, textvariable=self.current_locale, values=SUPPORTED_LOCALES, state="readonly", width=9)
        self.locale_combo.pack(side="right", padx=(0, 12))
        self.locale_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_all())

        self.safe_mode_banner = ttk.Frame(self.root, padding=(10, 6))
        self.safe_mode_text = ttk.Label(self.safe_mode_banner, text="")
        self.safe_mode_text.pack(side="left")
        self.safe_mode_install = ttk.Button(self.safe_mode_banner, text="Install auto translator", command=self.install_optional_dependency)
        self.safe_mode_install.pack(side="right")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.tabs: dict[str, ttk.Frame] = {}
        for name in ("Overview", "Human Translation", "Auto Translation", "Missing Keys", "Search", "Contributors", "Settings", "Logs"):
            frame = ttk.Frame(self.notebook, padding=10)
            self.tabs[name] = frame
            self.notebook.add(frame, text=name)

        self._build_overview_tab()
        self._build_layer_tab(LAYER_HUMAN, "Human Translation")
        self._build_layer_tab(LAYER_AUTO, "Auto Translation")
        self._build_missing_tab()
        self._build_search_tab()
        self._build_contributors_tab()
        self._build_settings_tab()
        self._build_logs_tab()

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 4)).pack(fill="x", side="bottom")

    def _build_overview_tab(self) -> None:
        tab = self.tabs["Overview"]
        ttk.Label(tab, text="Translation coverage", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Human translations override auto translations. Decorative separators are excluded from required coverage.").pack(anchor="w", pady=(2, 10))
        cards = ttk.Frame(tab)
        cards.pack(fill="x")
        self.overview_values: dict[str, tk.StringVar] = {}
        for index, (key, title) in enumerate([
            ("total", "Source strings"),
            ("effective", "Effectively translated"),
            ("missing", "Missing"),
            ("human", "Human"),
            ("auto_only", "Auto only"),
            ("human_only", "Human only"),
        ]):
            card = ttk.LabelFrame(cards, text=title, padding=12)
            card.grid(row=0, column=index, sticky="nsew", padx=4)
            cards.columnconfigure(index, weight=1)
            var = tk.StringVar(value="0")
            self.overview_values[key] = var
            ttk.Label(card, textvariable=var, style="CardValue.TLabel").pack()
        self.coverage_label = ttk.Label(tab, text="Coverage: 0%")
        self.coverage_label.pack(anchor="w", pady=(18, 4))
        self.coverage_progress = ttk.Progressbar(tab, orient="horizontal", mode="determinate", maximum=100)
        self.coverage_progress.pack(fill="x")
        self.overview_hint = ttk.Label(tab, text="Choose a valid RZMenu project root to begin.")
        self.overview_hint.pack(anchor="w", pady=(16, 0))

    def _build_layer_tab(self, layer: str, tab_name: str) -> None:
        tab = self.tabs[tab_name]
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="Filter:").pack(side="left")
        entry = ttk.Entry(toolbar, textvariable=self.search_var, width=40)
        entry.pack(side="left", padx=(4, 8))
        entry.bind("<KeyRelease>", lambda _event, current=layer: self.refresh_layer_tree(current))
        ttk.Label(toolbar, text="Status:").pack(side="left")
        combo = ttk.Combobox(toolbar, textvariable=self.layer_filter_vars[layer], values=("all", "translated", "missing", "invalid placeholders"), state="readonly", width=20)
        combo.pack(side="left", padx=(4, 8))
        combo.bind("<<ComboboxSelected>>", lambda _event, current=layer: self.refresh_layer_tree(current))
        ttk.Button(toolbar, text="Bulk paste TSV", command=lambda current=layer: self.bulk_paste(current)).pack(side="right")
        ttk.Button(toolbar, text="Save layer", command=lambda current=layer: self.save_layer(current)).pack(side="right", padx=(0, 8))

        pane = ttk.Panedwindow(tab, orient="horizontal")
        pane.pack(fill="both", expand=True)
        table_frame = ttk.Frame(pane)
        editor_frame = ttk.LabelFrame(pane, text="String editor", padding=10)
        pane.add(table_frame, weight=3)
        pane.add(editor_frame, weight=2)

        columns = ("status", "key", "translation", "translator", "source")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        self.layer_trees[layer] = tree
        widths = {"status": 120, "key": 330, "translation": 360, "translator": 130, "source": 210}
        for column in columns:
            tree.heading(column, text=column.replace("_", " ").title())
            tree.column(column, width=widths[column], stretch=column in {"key", "translation", "source"})
        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        xbar = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        tree.bind("<<TreeviewSelect>>", lambda _event, current=layer: self.on_layer_select(current))

        widgets: dict[str, Any] = {}
        ttk.Label(editor_frame, text="Key").pack(anchor="w")
        widgets["key"] = ttk.Entry(editor_frame, state="readonly")
        widgets["key"].pack(fill="x", pady=(2, 8))
        ttk.Label(editor_frame, text="Translation").pack(anchor="w")
        widgets["translation"] = tk.Text(editor_frame, height=7, wrap="word")
        widgets["translation"].pack(fill="x", pady=(2, 8))
        ttk.Label(editor_frame, text="Context and source locations").pack(anchor="w")
        widgets["context"] = tk.Text(editor_frame, height=10, wrap="word", state="disabled")
        widgets["context"].pack(fill="both", expand=True, pady=(2, 8))
        meta = ttk.Frame(editor_frame)
        meta.pack(fill="x")
        widgets["translator_name"] = tk.StringVar()
        widgets["translator_locale"] = tk.StringVar()
        widgets["translation_source"] = tk.StringVar()
        for row, (title, key) in enumerate([
            ("Translator", "translator_name"),
            ("Translator locale", "translator_locale"),
            ("Source", "translation_source"),
        ]):
            ttk.Label(meta, text=title).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(meta, textvariable=widgets[key]).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=2)
        meta.columnconfigure(1, weight=1)
        widgets["placeholder"] = ttk.Label(editor_frame, text="")
        widgets["placeholder"].pack(anchor="w", pady=(8, 4))
        buttons = ttk.Frame(editor_frame)
        buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(buttons, text="Save selected string", command=lambda current=layer: self.save_selected(current)).pack(side="left")
        ttk.Button(buttons, text="Delete translation", command=lambda current=layer: self.delete_selected(current)).pack(side="left", padx=(8, 0))
        self.editor_widgets[layer] = widgets

    def _build_missing_tab(self) -> None:
        tab = self.tabs["Missing Keys"]
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="Keys without an effective translation. Select several rows for batch actions.").pack(side="left")
        self.auto_translate_button = ttk.Button(toolbar, text="Auto translate selected", command=self.auto_translate_missing_selected)
        self.auto_translate_button.pack(side="right")
        ttk.Button(toolbar, text="Create blank human entries", command=self.create_blank_human_entries).pack(side="right", padx=(0, 8))
        columns = ("key", "context", "source")
        self.missing_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="extended")
        for column, width in (("key", 420), ("context", 620), ("source", 320)):
            self.missing_tree.heading(column, text=column.title())
            self.missing_tree.column(column, width=width, stretch=True)
        ybar = ttk.Scrollbar(tab, orient="vertical", command=self.missing_tree.yview)
        self.missing_tree.configure(yscrollcommand=ybar.set)
        self.missing_tree.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")

    def _build_search_tab(self) -> None:
        tab = self.tabs["Search"]
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="Search across source keys, effective translations and context:").pack(side="left")
        self.global_search_var = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.global_search_var, width=54)
        entry.pack(side="left", padx=(8, 0))
        entry.bind("<KeyRelease>", lambda _event: self.refresh_search_tree())
        columns = ("key", "effective", "layer", "source")
        self.search_tree = ttk.Treeview(tab, columns=columns, show="headings")
        for column, width in (("key", 430), ("effective", 520), ("layer", 120), ("source", 320)):
            self.search_tree.heading(column, text=column.title())
            self.search_tree.column(column, width=width, stretch=True)
        self.search_tree.pack(fill="both", expand=True)

    def _build_contributors_tab(self) -> None:
        tab = self.tabs["Contributors"]
        ttk.Label(tab, text="Translator hall of fame", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Every saved line is a brick in the localization cathedral. Attribution is stored separately so locale JSON stays clean.").pack(anchor="w", pady=(2, 10))
        self.champion_label = ttk.Label(tab, text="No contributions recorded yet.")
        self.champion_label.pack(anchor="w", pady=(0, 8))
        columns = ("name", "translator_locale", "project_locales", "human", "auto", "total")
        self.contributors_tree = ttk.Treeview(tab, columns=columns, show="headings")
        headings = {
            "name": "Contributor",
            "translator_locale": "Contributor locale",
            "project_locales": "Translation locales",
            "human": "Human lines",
            "auto": "Auto lines",
            "total": "Total",
        }
        for column in columns:
            self.contributors_tree.heading(column, text=headings[column])
            self.contributors_tree.column(column, width=180, stretch=True)
        self.contributors_tree.pack(fill="both", expand=True)

    def _build_settings_tab(self) -> None:
        tab = self.tabs["Settings"]
        grid = ttk.Frame(tab)
        grid.pack(fill="x", anchor="n")
        self.settings_root_var = tk.StringVar()
        self.analyzer_path_var = tk.StringVar()
        rows = [
            ("Project root", self.settings_root_var),
            ("Expected analyzer", self.analyzer_path_var),
            ("Default translator name", self.default_translator_name),
            ("Translator locale", self.default_translator_locale),
        ]
        for row, (label, variable) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(grid, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=5)
        ttk.Button(grid, text="Browse", command=self.choose_project_root).grid(row=0, column=2, pady=5)
        grid.columnconfigure(1, weight=1)
        ttk.Checkbutton(grid, text="Also scan common Blender UI keyword strings (text=, label=, description=, name=)", variable=self.include_ui_literals).grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 4))
        ttk.Button(grid, text="Save settings", command=self.save_settings).grid(row=5, column=0, sticky="w", pady=(14, 0))
        ttk.Button(grid, text="Install / repair optional auto translator", command=self.install_optional_dependency).grid(row=5, column=1, sticky="w", pady=(14, 0))
        self.dependency_status = ttk.Label(grid, text="")
        self.dependency_status.grid(row=6, column=0, columnspan=3, sticky="w", pady=(16, 0))
        ttk.Label(grid, text="Locale files are kept in translation/locales. Attribution uses a sidecar .rzmenu_translation_meta.json file and never changes locale JSON key format.", wraplength=1000).grid(row=7, column=0, columnspan=3, sticky="w", pady=(16, 0))

    def _build_logs_tab(self) -> None:
        tab = self.tabs["Logs"]
        self.logs_text = tk.Text(tab, wrap="none", state="disabled")
        self.logs_text.pack(fill="both", expand=True)
        if self.log_lines:
            self.logs_text.configure(state="normal")
            self.logs_text.insert("end", "\n".join(self.log_lines) + "\n")
            self.logs_text.configure(state="disabled")

    def _initialize_project(self) -> None:
        explicit = str(self.settings.get("project_root", "")) or None
        root = discover_project_root(explicit)
        if root is None:
            self.log("Could not auto-detect RZMenu root")
            self.root.after(100, self._ask_for_project_root)
            return
        self.set_project_root(root)

    def _ask_for_project_root(self) -> None:
        messagebox.showwarning(
            APP_NAME,
            "RZMenu project root was not found automatically.\n\nPlease choose the RZMenu folder. It should contain translation/locales and translation/translation_tool/analyze.py.",
        )
        self.choose_project_root()

    def choose_project_root(self) -> None:
        initial = self.settings_root_var.get() or str(Path.cwd())
        selected = filedialog.askdirectory(title="Choose RZMenu project root", initialdir=initial)
        if selected:
            self.set_project_root(Path(selected))

    def set_project_root(self, root: Path) -> None:
        root = root.expanduser().resolve()
        paths = ProjectPaths(root)
        missing = paths.missing_parts()
        if missing:
            answer = messagebox.askyesno(
                APP_NAME,
                "The selected folder does not fully match the expected RZMenu structure.\n\nMissing:\n- " + "\n- ".join(missing) + "\n\nContinue in partial mode? Missing locale JSON files can be created safely when you save.",
            )
            if not answer:
                return
        self.project_paths = paths
        self.store = TranslationStore(paths, self.log)
        self.root_label.configure(text=str(root))
        self.settings_root_var.set(str(root))
        self.analyzer_path_var.set(str(paths.analyzer))
        self.settings["project_root"] = str(root)
        save_settings_file(self.settings)
        missing_locale_files = paths.locale_file_report()
        if missing_locale_files:
            self.log("Locale files absent and available for safe creation on save: " + ", ".join(missing_locale_files))
        self.rescan()

    def _offer_optional_dependency_if_needed(self) -> None:
        self.refresh_dependency_ui()
        if self.translator.available:
            return
        if bool(self.settings.get("dependency_prompted", False)):
            return
        self.settings["dependency_prompted"] = True
        save_settings_file(self.settings)
        answer = messagebox.askyesnocancel(
            APP_NAME,
            f"Optional auto translation dependency is missing:\n\n{OPTIONAL_TRANSLATOR_PACKAGE}\n\nYes: install the supported version with pip.\nNo: continue in safe mode with manual editing.\nCancel: close the application safely.",
        )
        if answer is True:
            self.install_optional_dependency()
        elif answer is None:
            self.root.destroy()

    def refresh_dependency_ui(self) -> None:
        if self.translator.available:
            self.safe_mode_banner.pack_forget()
            text = f"Auto translator ready: {OPTIONAL_TRANSLATOR_PACKAGE}"
            self.auto_translate_button.configure(state="normal")
        else:
            self.safe_mode_text.configure(text="Safe mode: manual translation works; automatic translation is disabled until the optional package is installed.")
            self.safe_mode_banner.pack(fill="x", before=self.notebook)
            text = f"Safe mode. Missing optional package: {OPTIONAL_TRANSLATOR_PACKAGE}"
            self.auto_translate_button.configure(state="disabled")
        self.dependency_status.configure(text=text)

    def install_optional_dependency(self) -> None:
        confirmed = messagebox.askyesno(
            APP_NAME,
            f"Install {OPTIONAL_TRANSLATOR_PACKAGE} using this Python interpreter?\n\n{sys.executable}\n\nThis runs pip only for the pinned package version.",
        )
        if not confirmed:
            return
        self.status_var.set("Installing optional translator...")
        self.root.update_idletasks()
        ok, details = self.translator.install()
        self.refresh_dependency_ui()
        self.status_var.set("Ready")
        if ok:
            messagebox.showinfo(APP_NAME, "Optional auto translator installed successfully.")
        else:
            messagebox.showwarning(APP_NAME, "Installation was not completed. The app remains usable in safe mode.\n\nSee the Logs tab for details.\n\n" + details[-1200:])

    def save_settings(self) -> None:
        self.settings.update({
            "project_root": self.settings_root_var.get(),
            "locale": self.current_locale.get(),
            "include_ui_literals": self.include_ui_literals.get(),
            "translator_name": self.default_translator_name.get().strip(),
            "translator_locale": self.default_translator_locale.get().strip(),
        })
        save_settings_file(self.settings)
        self.log("Settings saved")
        messagebox.showinfo(APP_NAME, "Settings saved.")

    def rescan(self) -> None:
        if not self.project_paths or not self.store:
            return
        self.status_var.set("Scanning source strings...")
        self.root.update_idletasks()
        scanner = TranslationScanner(self.project_paths.root, self.include_ui_literals.get(), self.log)
        self.scan_entries = scanner.scan()
        self.refresh_all()
        self.status_var.set(f"Ready. Found {len(self.scan_entries)} source strings.")

    def all_source_keys(self) -> list[str]:
        return sorted(self.scan_entries, key=str.lower)

    def stats(self) -> dict[str, int]:
        if not self.store:
            return {key: 0 for key in ("total", "effective", "missing", "human", "auto_only", "human_only")}
        locale = self.current_locale.get()
        keys = set(self.scan_entries)
        human = self.store.layer(locale, LAYER_HUMAN)
        auto = self.store.layer(locale, LAYER_AUTO)
        effective = self.store.effective(locale)
        translated_keys = {key for key in keys if effective.get(key, "").strip()}
        return {
            "total": len(keys),
            "effective": len(translated_keys),
            "missing": len(keys - translated_keys),
            "human": len({key for key in keys if human.get(key, "").strip()}),
            "auto_only": len({key for key in keys if auto.get(key, "").strip() and not human.get(key, "").strip()}),
            "human_only": len({key for key in keys if human.get(key, "").strip() and not auto.get(key, "").strip()}),
        }

    def refresh_all(self) -> None:
        if not self.store:
            return
        self.settings["locale"] = self.current_locale.get()
        save_settings_file(self.settings)
        self.refresh_overview()
        self.refresh_layer_tree(LAYER_HUMAN)
        self.refresh_layer_tree(LAYER_AUTO)
        self.refresh_missing_tree()
        self.refresh_search_tree()
        self.refresh_contributors()
        self.refresh_dependency_ui()

    def refresh_overview(self) -> None:
        stats = self.stats()
        for key, var in self.overview_values.items():
            var.set(str(stats[key]))
        coverage = (stats["effective"] / stats["total"] * 100.0) if stats["total"] else 0.0
        self.coverage_progress["value"] = coverage
        self.coverage_label.configure(text=f"Coverage: {coverage:.1f}%")
        if stats["total"] == 0:
            hint = "No translatable source strings were found. Check the selected root or disable strict scanning assumptions by enabling Blender UI keyword scanning in Settings."
        elif stats["missing"]:
            hint = f"{stats['missing']} lines are still waiting for a translator. The Missing Keys tab is the fastest place to tame them."
        else:
            hint = "All scanned strings have an effective translation. The coverage dragon has been fed. 🐉"
        self.overview_hint.configure(text=hint)

    def translation_status(self, key: str, layer: str, value: str) -> str:
        if not value.strip():
            return "missing"
        ok, _reason = validate_placeholders(key, value)
        return "translated" if ok else "invalid placeholders"

    def _matches_layer_filter(self, key: str, value: str, layer: str) -> bool:
        query = self.search_var.get().strip().lower()
        if query and query not in key.lower() and query not in value.lower():
            return False
        wanted = self.layer_filter_vars[layer].get()
        return wanted == "all" or self.translation_status(key, layer, value) == wanted

    def refresh_layer_tree(self, layer: str) -> None:
        if not self.store:
            return
        tree = self.layer_trees[layer]
        tree.delete(*tree.get_children())
        locale = self.current_locale.get()
        values = self.store.layer(locale, layer)
        keys = sorted(set(self.scan_entries) | set(values), key=str.lower)
        for key in keys:
            value = values.get(key, "")
            if not self._matches_layer_filter(key, value, layer):
                continue
            meta = self.store.meta.get(locale, layer, key)
            source = self.scan_entries[key].refs[0].compact() if key in self.scan_entries and self.scan_entries[key].refs else "not found in scan"
            tree.insert("", "end", iid=key, values=(self.translation_status(key, layer, value), key, value, meta.get("translator_name", ""), source))

    def on_layer_select(self, layer: str) -> None:
        tree = self.layer_trees[layer]
        selection = tree.selection()
        if not selection or not self.store:
            return
        key = selection[0]
        self.selected_key_by_layer[layer] = key
        locale = self.current_locale.get()
        value = self.store.layer(locale, layer).get(key, "")
        meta = self.store.meta.get(locale, layer, key)
        widgets = self.editor_widgets[layer]
        key_entry: ttk.Entry = widgets["key"]
        key_entry.configure(state="normal")
        key_entry.delete(0, "end")
        key_entry.insert(0, key)
        key_entry.configure(state="readonly")
        text: tk.Text = widgets["translation"]
        text.delete("1.0", "end")
        text.insert("1.0", value)
        context: tk.Text = widgets["context"]
        context.configure(state="normal")
        context.delete("1.0", "end")
        refs = self.scan_entries.get(key, ScanEntry(key)).refs
        if refs:
            context.insert("1.0", "\n\n".join(f"{ref.compact()}\n{ref.context}" for ref in refs))
        else:
            context.insert("1.0", "This key exists in JSON but was not found by the current source scan.")
        context.configure(state="disabled")
        widgets["translator_name"].set(meta.get("translator_name", self.default_translator_name.get() if layer == LAYER_HUMAN else "Auto Translator"))
        widgets["translator_locale"].set(meta.get("translator_locale", self.default_translator_locale.get()))
        widgets["translation_source"].set(meta.get("translation_source", "manual" if layer == LAYER_HUMAN else OPTIONAL_TRANSLATOR_PACKAGE))
        ok, reason = validate_placeholders(key, value)
        widgets["placeholder"].configure(text="Placeholders: OK" if ok else reason)

    def save_selected(self, layer: str) -> None:
        if not self.store:
            return
        key = self.selected_key_by_layer.get(layer)
        if not key:
            messagebox.showinfo(APP_NAME, "Select a row first.")
            return
        widgets = self.editor_widgets[layer]
        value = widgets["translation"].get("1.0", "end-1c")
        ok, reason = validate_placeholders(key, value)
        if not ok and not messagebox.askyesno(APP_NAME, reason + "\n\nSave anyway? This may break runtime formatting."):
            return
        locale = self.current_locale.get()
        self.store.layer(locale, layer)[key] = value
        self.store.meta.set(locale, layer, key, {
            "translator_name": widgets["translator_name"].get().strip() or ("Auto Translator" if layer == LAYER_AUTO else "Unknown"),
            "translator_locale": widgets["translator_locale"].get().strip(),
            "translation_source": widgets["translation_source"].get().strip() or ("manual" if layer == LAYER_HUMAN else OPTIONAL_TRANSLATOR_PACKAGE),
            "last_modified": utc_now_iso(),
        })
        self.store.save_layer(locale, layer)
        self.refresh_all()

    def delete_selected(self, layer: str) -> None:
        if not self.store:
            return
        key = self.selected_key_by_layer.get(layer)
        if not key:
            messagebox.showinfo(APP_NAME, "Select a row first.")
            return
        if not messagebox.askyesno(APP_NAME, f"Delete the {layer} translation for:\n\n{key}"):
            return
        locale = self.current_locale.get()
        self.store.layer(locale, layer).pop(key, None)
        self.store.meta.delete(locale, layer, key)
        self.store.save_layer(locale, layer)
        self.refresh_all()

    def save_layer(self, layer: str) -> None:
        if not self.store:
            return
        self.store.save_layer(self.current_locale.get(), layer)
        messagebox.showinfo(APP_NAME, f"Saved {layer} translations.")

    def bulk_paste(self, layer: str) -> None:
        if not self.store:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Bulk paste TSV into {layer}")
        dialog.geometry("900x560")
        ttk.Label(dialog, text="Paste one line per entry: key<TAB>translation. Existing keys are updated; new keys are allowed. Placeholder mismatches are rejected.", wraplength=860).pack(anchor="w", padx=10, pady=(10, 6))
        text = tk.Text(dialog, wrap="none")
        text.pack(fill="both", expand=True, padx=10, pady=6)

        def apply() -> None:
            locale = self.current_locale.get()
            changed = 0
            errors: list[str] = []
            for number, line in enumerate(text.get("1.0", "end-1c").splitlines(), start=1):
                if not line.strip():
                    continue
                if "\t" not in line:
                    errors.append(f"Line {number}: expected a TAB separator")
                    continue
                key, value = line.split("\t", 1)
                ok, reason = validate_placeholders(key, value)
                if not ok:
                    errors.append(f"Line {number}: {reason}")
                    continue
                self.store.layer(locale, layer)[key] = value
                self.store.meta.set(locale, layer, key, {
                    "translator_name": self.default_translator_name.get().strip() or "Unknown",
                    "translator_locale": self.default_translator_locale.get().strip(),
                    "translation_source": "bulk TSV paste" if layer == LAYER_HUMAN else "bulk TSV paste into auto layer",
                    "last_modified": utc_now_iso(),
                })
                changed += 1
            if changed:
                self.store.save_layer(locale, layer)
                self.refresh_all()
            if errors:
                messagebox.showwarning(APP_NAME, f"Applied {changed} entries.\n\nRejected lines:\n" + "\n".join(errors[:20]))
            else:
                messagebox.showinfo(APP_NAME, f"Applied {changed} entries.")
                dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Apply", command=apply).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=(8, 0))

    def missing_keys(self) -> list[str]:
        if not self.store:
            return []
        effective = self.store.effective(self.current_locale.get())
        return [key for key in self.all_source_keys() if not effective.get(key, "").strip()]

    def refresh_missing_tree(self) -> None:
        self.missing_tree.delete(*self.missing_tree.get_children())
        for key in self.missing_keys():
            refs = self.scan_entries[key].refs
            context = refs[0].context if refs else ""
            source = refs[0].compact() if refs else ""
            self.missing_tree.insert("", "end", iid=key, values=(key, context, source))

    def create_blank_human_entries(self) -> None:
        if not self.store:
            return
        keys = list(self.missing_tree.selection()) or self.missing_keys()
        if not keys:
            messagebox.showinfo(APP_NAME, "There are no missing keys to create.")
            return
        locale = self.current_locale.get()
        human = self.store.layer(locale, LAYER_HUMAN)
        for key in keys:
            human.setdefault(key, "")
        self.store.save_layer(locale, LAYER_HUMAN)
        self.refresh_all()
        self.notebook.select(self.tabs["Human Translation"])

    def auto_translate_missing_selected(self) -> None:
        if not self.store:
            return
        if not self.translator.available:
            messagebox.showwarning(APP_NAME, "Auto translation is unavailable in safe mode. Install the optional package from Settings or use manual editing.")
            return
        keys = list(self.missing_tree.selection())
        if not keys:
            messagebox.showinfo(APP_NAME, "Select one or more missing keys first.")
            return
        locale = self.current_locale.get()
        auto = self.store.layer(locale, LAYER_AUTO)
        failures: list[str] = []
        self.status_var.set(f"Auto translating {len(keys)} keys...")
        self.root.update_idletasks()
        for index, key in enumerate(keys, start=1):
            try:
                auto[key] = self.translator.translate(key, locale)
                self.store.meta.set(locale, LAYER_AUTO, key, {
                    "translator_name": "Auto Translator",
                    "translator_locale": "machine",
                    "translation_source": OPTIONAL_TRANSLATOR_PACKAGE,
                    "last_modified": utc_now_iso(),
                })
                self.status_var.set(f"Auto translated {index}/{len(keys)}")
                self.root.update_idletasks()
            except Exception as exc:
                failures.append(f"{key}: {exc}")
                self.log(f"Auto translation failed for {key!r}: {exc}")
        self.store.save_layer(locale, LAYER_AUTO)
        self.refresh_all()
        self.status_var.set("Ready")
        if failures:
            messagebox.showwarning(APP_NAME, f"Translated {len(keys) - len(failures)} of {len(keys)} keys.\n\nFailures:\n" + "\n".join(failures[:12]))
        else:
            messagebox.showinfo(APP_NAME, f"Translated {len(keys)} keys into the auto layer.")

    def refresh_search_tree(self) -> None:
        self.search_tree.delete(*self.search_tree.get_children())
        if not self.store:
            return
        locale = self.current_locale.get()
        human = self.store.layer(locale, LAYER_HUMAN)
        auto = self.store.layer(locale, LAYER_AUTO)
        effective = self.store.effective(locale)
        query = self.global_search_var.get().strip().lower()
        keys = sorted(set(self.scan_entries) | set(effective), key=str.lower)
        for key in keys:
            refs = self.scan_entries.get(key, ScanEntry(key)).refs
            source = refs[0].compact() if refs else "not found in scan"
            context = " ".join(ref.context for ref in refs)
            translation = effective.get(key, "")
            haystack = " ".join((key, translation, context, source)).lower()
            if query and query not in haystack:
                continue
            layer = "human" if key in human and human.get(key, "").strip() else "auto" if key in auto and auto.get(key, "").strip() else "missing"
            self.search_tree.insert("", "end", values=(key, translation, layer, source))

    def refresh_contributors(self) -> None:
        self.contributors_tree.delete(*self.contributors_tree.get_children())
        if not self.store:
            return
        rows = self.store.meta.contributor_rows()
        for row in rows:
            self.contributors_tree.insert("", "end", values=(row["name"], row["translator_locale"], row["locales"], row["human"], row["auto"], row["total"]))
        if rows:
            winner = rows[0]
            self.champion_label.configure(text=f"Top contributor: {winner['name']} with {winner['total']} attributed lines. Crown polished, keyboard battle-tested. 👑")
        else:
            self.champion_label.configure(text="No contributions recorded yet. Save a translated line to place the first brick.")


def main() -> int:
    if tk is None:
        safe_message(
            APP_NAME,
            "tkinter could not be imported, so the desktop interface cannot start.\n\n"
            "Install a regular Python build with tkinter support, then run this file again.\n\n"
            f"Technical detail: {TKINTER_IMPORT_ERROR}",
        )
        return 2
    try:
        root = tk.Tk()
        RZMenuTranslationApp(root)
        root.mainloop()
        return 0
    except Exception as exc:
        safe_message(
            APP_NAME,
            "The application could not start safely. No intentional file changes were made.\n\n"
            f"Reason: {exc}\n\n"
            "Run the file from a terminal for additional details if needed.",
        )
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
