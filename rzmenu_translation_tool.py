#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RZMenu Translation Tool
Single-file desktop translation manager for RZMenu.

Place this file in the root of the RZMenu repository and run:
    python rzmenu_translation_tool.py

Required dependency:
    pip install PySide6

Optional automatic translation:
    pip install deep-translator

Optional Ray Chan thank-you image:
    translation/assets/ray_chan_kiss.png
"""
from __future__ import annotations

import ast
import copy
import ctypes
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

APP_NAME = "RZMenu Translation Tool"
APP_VERSION = "1.0.0"
META_FILENAME = "_translation_meta.json"
DRAFT_DIRNAME = ".translation_drafts"
PACKAGE_EXTENSION = ".tfraychan"
PACKAGE_FORMAT = "rzmenu_translation_for_ray_chan"
PACKAGE_VERSION = 1
DRAFT_FORMAT = "rzmenu_translation_draft"
DRAFT_VERSION = 1
DEFAULT_TRANSLATOR = "Anonymous"
AUTOSAVE_DELAY_MS = 550
AUTO_SAVE_BATCH = 15
LONG_TEXT_THRESHOLD = 80
LEGACY_META_FILENAME = ".rzmenu_translation_meta.json"
SEARCH_DEBOUNCE_MS = 260
TABLE_RENDER_BATCH = 120
FILTERS = ["All strings", "Missing", "Translated", "Auto-only", "Human", "Draft", "Placeholders", "Long strings"]
BLENDER_LOCALES = [
    ("ar_EG", "Arabic"),
    ("bg_BG", "Bulgarian"),
    ("ca_AD", "Catalan"),
    ("cs_CZ", "Czech"),
    ("de_DE", "German"),
    ("el_GR", "Greek"),
    ("es", "Spanish"),
    ("eu_EU", "Basque"),
    ("fa_IR", "Persian"),
    ("fi_FI", "Finnish"),
    ("fr_FR", "French"),
    ("he_IL", "Hebrew"),
    ("hi_IN", "Hindi"),
    ("hr_HR", "Croatian"),
    ("hu_HU", "Hungarian"),
    ("id_ID", "Indonesian"),
    ("it_IT", "Italian"),
    ("ja_JP", "Japanese"),
    ("ko_KR", "Korean"),
    ("nl_NL", "Dutch"),
    ("pl_PL", "Polish"),
    ("pt_BR", "Portuguese, Brazil"),
    ("pt_PT", "Portuguese, Portugal"),
    ("ro_RO", "Romanian"),
    ("ru", "Russian"),
    ("sk_SK", "Slovak"),
    ("sr_RS", "Serbian"),
    ("sv_SE", "Swedish"),
    ("th_TH", "Thai"),
    ("tr_TR", "Turkish"),
    ("uk_UA", "Ukrainian"),
    ("vi_VN", "Vietnamese"),
    ("zh_CN", "Chinese, Simplified"),
    ("zh_TW", "Chinese, Traditional"),
]


def _show_dependency_error(message: str) -> None:
    """Display a readable dependency error even when Qt is not installed."""
    full = f"{APP_NAME}\n\n{message}"
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(0, full, APP_NAME, 0x10)
            return
        except Exception:
            pass
    print(full, file=sys.stderr)


def _ensure_pyside6() -> bool:
    if importlib.util.find_spec("PySide6") is not None:
        return True

    message = (
        "PySide6 is not installed.\n\n"
        "This application needs PySide6 for the graphical interface.\n"
        "Install it now?\n\n"
        "Command:\n"
        f"    {sys.executable} -m pip install PySide6"
    )
    print(f"{APP_NAME}\n\n{message}", file=sys.stderr)

    if not sys.stdin.isatty():
        return False

    try:
        answer = input("Install PySide6 now? [Y/n]: ").strip().lower()
    except EOFError:
        return False

    if answer not in {"", "y", "yes"}:
        return False

    print("Installing PySide6...", file=sys.stderr)
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6"])
    except Exception as exc:
        print(f"PySide6 installation failed: {exc}", file=sys.stderr)
        return False

    return importlib.util.find_spec("PySide6") is not None


if not _ensure_pyside6():
    _show_dependency_error(
        "PySide6 is required to run the graphical interface.\n\n"
        "Install it with:\n"
        f"    {sys.executable} -m pip install PySide6\n\n"
        "The application has not changed any project files."
    )
    raise SystemExit(1)


try:
    from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
    from PySide6.QtGui import QAction, QIcon, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QSplitter,
        QStyle,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    _show_dependency_error("PySide6 could not be imported even after installation.")
    raise SystemExit(1)

try:
    from deep_translator import GoogleTranslator

    DEEP_TRANSLATOR_AVAILABLE = True
except ImportError:
    GoogleTranslator = None  # type: ignore[assignment]
    DEEP_TRANSLATOR_AVAILABLE = False


# ----------------------------- General helpers -----------------------------


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def safe_filename_part(value: str) -> str:
    value = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    return value.strip("._") or DEFAULT_TRANSLATOR


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            try:
                with backup.open("r", encoding="utf-8") as handle:
                    return json.load(handle)
            except Exception:
                pass
        raise RuntimeError(f"Could not read JSON file:\n{path}\n\n{exc}") from exc


def validate_flat_string_dict(data: Any, label: str) -> dict[str, str]:
    if not isinstance(data, dict):
        raise RuntimeError(f"{label} must contain a JSON object.")
    result: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise RuntimeError(
                f"{label} must remain a flat string-to-string dictionary.\n"
                f"Invalid entry: {key!r}: {value!r}"
            )
        result[key] = value
    return result


def is_auxiliary_json(path: Path) -> bool:
    return path.name in {META_FILENAME, LEGACY_META_FILENAME} or path.name.endswith((".bak", ".tmp"))


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON through a verified temp file, preserving one .bak copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        with temp_path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        backup_path = path.with_suffix(path.suffix + ".bak")
        if path.exists():
            shutil.copy2(path, backup_path)
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def atomic_write_json_set(files: dict[Path, Any]) -> None:
    """Write several related JSON files as one best-effort transaction.

    Every temporary file is validated first. Existing files receive one .bak copy.
    If a replacement fails midway, already replaced files are restored from backups.
    """
    prepared: dict[Path, Path] = {}
    existed: dict[Path, bool] = {}
    replaced: list[Path] = []
    try:
        for path, data in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            existed[path] = path.exists()
            fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
            temp_path = Path(name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            with temp_path.open("r", encoding="utf-8") as handle:
                json.load(handle)
            prepared[path] = temp_path

        for path in files:
            backup = path.with_suffix(path.suffix + ".bak")
            if path.exists():
                shutil.copy2(path, backup)

        for path, temp_path in prepared.items():
            os.replace(temp_path, path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            backup = path.with_suffix(path.suffix + ".bak")
            try:
                if backup.exists():
                    shutil.copy2(backup, path)
                elif not existed.get(path, False):
                    path.unlink(missing_ok=True)
            except Exception:
                pass
        raise
    finally:
        for temp_path in prepared.values():
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass


def find_project_root() -> Path:
    """Find the nearest repository containing translation/locales."""
    script_dir = Path(__file__).resolve().parent
    cwd = Path.cwd().resolve()
    candidates: list[Path] = []

    def add_candidate(path: Path) -> None:
        path = path.resolve()
        if path not in candidates:
            candidates.append(path)

    add_candidate(script_dir)
    add_candidate(cwd)
    for base in (script_dir, cwd):
        add_candidate(base / "RZMenu")
        for parent in base.parents:
            add_candidate(parent)
            add_candidate(parent / "RZMenu")

    for candidate in candidates:
        if (candidate / "translation" / "locales").is_dir():
            return candidate
    raise RuntimeError(
        "RZMenu repository root was not found.\n\n"
        "Place this script in the repository root. The expected structure is:\n"
        "RZMenu/\n"
        "  rzmenu_translation_tool.py\n"
        "  translation/\n"
        "    locales/\n"
        "    __init__.py"
    )


def is_decorative_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in {"--", "...", "…", "-", "_", "="}:
        return True
    return bool(re.fullmatch(r"[\s\-_=~.*•·…|/\\]+", stripped))


PLACEHOLDER_RE = re.compile(
    r"(\{[^{}]+\}|%(?:\([^)]+\))?[#0\- +]?(?:\d+|\*)?(?:\.\d+)?[diouxXeEfFgGcrs%]|\\n|\\t)"
)


def protect_placeholders(text: str) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = f"__RZM_PLACEHOLDER_{len(mapping)}__"
        mapping[token] = match.group(0)
        return token

    return PLACEHOLDER_RE.sub(replace, text), mapping


def restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    restored = text
    for token, value in mapping.items():
        if token not in restored:
            raise RuntimeError(f"Automatic translation damaged placeholder {value!r}.")
        restored = restored.replace(token, value)
    return restored


def normalize_google_locale(locale: str) -> str:
    special = {
        "zh_CN": "zh-CN",
        "zh_TW": "zh-TW",
        "pt_BR": "pt",
        "pt_PT": "pt",
    }
    return special.get(locale, locale.replace("_", "-"))


# ------------------------------ Source scanner -----------------------------


@dataclass
class Occurrence:
    file: str
    line: int
    context: str
    ui_type: str


@dataclass
class SourceEntry:
    text: str
    occurrences: list[Occurrence] = field(default_factory=list)

    @property
    def location(self) -> str:
        if not self.occurrences:
            return "Locale file"
        first = self.occurrences[0]
        suffix = f" (+{len(self.occurrences) - 1})" if len(self.occurrences) > 1 else ""
        return f"{first.file}:{first.line}{suffix}"

    @property
    def context(self) -> str:
        if not self.occurrences:
            return "Referenced by an existing locale file."
        return "\n\n".join(
            f"{occ.file}:{occ.line} · {occ.ui_type}\n{occ.context}" for occ in self.occurrences[:8]
        )


class SourceScanner:
    IGNORED_DIRS = {
        ".git",
        ".github",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "build",
        "dist",
        "locales",
        DRAFT_DIRNAME,
    }
    TRANSLATION_CALLS = {"_", "tr", "translate", "gettext", "pgettext"}
    TEXT_KEYWORDS = {"text"}

    def __init__(self, root: Path) -> None:
        self.root = root

    def scan(self, existing_keys: Iterable[str]) -> dict[str, SourceEntry]:
        entries: dict[str, SourceEntry] = {key: SourceEntry(key) for key in existing_keys}
        for py_file in self.root.rglob("*.py"):
            if any(part in self.IGNORED_DIRS for part in py_file.parts):
                continue
            if py_file.resolve() == Path(__file__).resolve():
                continue
            self._scan_file(py_file, entries)
        return entries

    def _scan_file(self, path: Path, entries: dict[str, SourceEntry]) -> None:
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except Exception:
            return
        lines = text.splitlines()
        rel = str(path.relative_to(self.root)).replace("\\", "/")

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = self._call_name(node.func)
            found: list[tuple[str, str]] = []

            if call_name in self.TRANSLATION_CALLS and node.args:
                literal = self._literal_string(node.args[0])
                if literal is not None:
                    found.append((literal, call_name or "translation call"))

            for keyword in node.keywords:
                if keyword.arg in self.TEXT_KEYWORDS:
                    literal = self._literal_string(keyword.value)
                    if literal is not None:
                        found.append((literal, f"{call_name or 'call'} · text"))

            if not found:
                continue
            line_no = getattr(node, "lineno", 0) or 0
            context = lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""
            for literal, ui_type in found:
                if not literal.strip() or is_decorative_text(literal):
                    continue
                entry = entries.setdefault(literal, SourceEntry(literal))
                occ = Occurrence(rel, line_no, context, ui_type)
                if not any((x.file, x.line, x.context, x.ui_type) == (occ.file, occ.line, occ.context, occ.ui_type) for x in entry.occurrences):
                    entry.occurrences.append(occ)

    @staticmethod
    def _literal_string(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    @staticmethod
    def _call_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None


# ----------------------------- Repository model ----------------------------


@dataclass
class RowRecord:
    key: str
    source: SourceEntry
    human: str
    auto: str
    draft: Optional[dict[str, Any]]
    author: str
    search_blob: str = ""

    @property
    def effective(self) -> str:
        if self.draft is not None:
            new_value = str(self.draft.get("new_value", ""))
            # Deleting a human override immediately reveals the machine fallback.
            return new_value if new_value else self.auto
        if self.human:
            return self.human
        return self.auto

    @property
    def status(self) -> str:
        if self.draft is not None:
            return "draft"
        if self.human:
            return "human"
        if self.auto:
            return "auto-only"
        return "missing"


class Repository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.translation_dir = root / "translation"
        self.locales_dir = self.translation_dir / "locales"
        self.drafts_dir = self.translation_dir / DRAFT_DIRNAME
        self.meta_path = self.locales_dir / META_FILENAME
        self.meta = self._load_meta()
        self.locale = ""
        self.human: dict[str, str] = {}
        self.auto: dict[str, str] = {}
        self.draft: dict[str, Any] = {}
        self.sources: dict[str, SourceEntry] = {}
        self._row_cache: Optional[list[RowRecord]] = None
        self.scan_sources()

    def _load_meta(self) -> dict[str, Any]:
        default = {"version": 1, "last_translator_name": DEFAULT_TRANSLATOR, "entries": {}}
        data = read_json(self.meta_path, default)
        if not isinstance(data, dict):
            raise RuntimeError(f"{META_FILENAME} must contain a JSON object.")
        data.setdefault("version", 1)
        data.setdefault("last_translator_name", DEFAULT_TRANSLATOR)
        data.setdefault("entries", {})
        return data

    def save_meta(self) -> None:
        atomic_write_json(self.meta_path, self.meta)

    def available_locales(self) -> list[str]:
        locales: set[str] = set()
        self.locales_dir.mkdir(parents=True, exist_ok=True)
        for path in self.locales_dir.glob("*.json"):
            if is_auxiliary_json(path):
                continue
            stem = path.stem
            locale = stem[:-5] if stem.endswith("_auto") else stem
            if locale and not locale.startswith("_"):
                locales.add(locale)
        if not locales:
            locales.add("ru")
        return sorted(locales, key=str.casefold)

    def human_path(self, locale: Optional[str] = None) -> Path:
        return self.locales_dir / f"{locale or self.locale}.json"

    def auto_path(self, locale: Optional[str] = None) -> Path:
        return self.locales_dir / f"{locale or self.locale}_auto.json"

    def draft_path(self, locale: Optional[str] = None) -> Path:
        return self.drafts_dir / f"{locale or self.locale}.json"

    def load_locale(self, locale: str) -> None:
        self.locale = locale
        self.human = validate_flat_string_dict(read_json(self.human_path(), {}), self.human_path().name)
        self.auto = validate_flat_string_dict(read_json(self.auto_path(), {}), self.auto_path().name)
        self.draft = self._load_draft(locale)
        self.invalidate_rows()

    def scan_sources(self) -> None:
        all_keys: set[str] = set()
        for path in self.locales_dir.glob("*.json"):
            if is_auxiliary_json(path):
                continue
            try:
                all_keys.update(validate_flat_string_dict(read_json(path, {}), path.name).keys())
            except RuntimeError:
                continue
        self.sources = SourceScanner(self.root).scan(all_keys)
        self.invalidate_rows()

    def invalidate_rows(self) -> None:
        self._row_cache = None

    def _load_draft(self, locale: str) -> dict[str, Any]:
        default = {
            "format": DRAFT_FORMAT,
            "version": DRAFT_VERSION,
            "target_locale": locale,
            "translator_name": self.meta.get("last_translator_name", DEFAULT_TRANSLATOR),
            "created_at": now_iso(),
            "last_modified": now_iso(),
            "changes": {},
        }
        path = self.draft_path(locale)
        data = read_json(path, default)
        if not isinstance(data, dict) or data.get("format") != DRAFT_FORMAT:
            raise RuntimeError(f"Invalid draft file:\n{path}")
        data.setdefault("changes", {})
        data.setdefault("translator_name", DEFAULT_TRANSLATOR)
        return data

    def save_draft(self) -> None:
        if not self.locale:
            return
        self.draft["last_modified"] = now_iso()
        atomic_write_json(self.draft_path(), self.draft)

    def set_translator_name(self, name: str) -> None:
        name = name.strip() or DEFAULT_TRANSLATOR
        self.meta["last_translator_name"] = name
        if self.locale:
            self.draft["translator_name"] = name
        self.save_meta()
        if self.locale:
            self.save_draft()

    @property
    def translator_name(self) -> str:
        return str(self.draft.get("translator_name") or self.meta.get("last_translator_name") or DEFAULT_TRANSLATOR)

    def edit_translation(self, key: str, new_value: str) -> None:
        changes = self.draft.setdefault("changes", {})
        current_human = self.human.get(key, "")
        existing = changes.get(key)
        base_value = existing.get("base_value", current_human) if isinstance(existing, dict) else current_human
        if new_value == base_value:
            changes.pop(key, None)
            self.save_draft()
            return
        if not new_value:
            action = "delete"
        elif base_value:
            action = "edit"
        else:
            action = "create"
        changes[key] = {
            "base_value": base_value,
            "new_value": new_value,
            "action": action,
            "modified_at": now_iso(),
        }
        self.save_draft()
        self.invalidate_rows()

    def rows(self) -> list[RowRecord]:
        if self._row_cache is not None:
            return self._row_cache
        all_keys = set(self.sources) | set(self.human) | set(self.auto) | set(self.draft.get("changes", {}))
        result: list[RowRecord] = []
        for key in sorted(all_keys, key=str.casefold):
            draft_change = self.draft.get("changes", {}).get(key)
            author = self.current_author(key)
            result.append(
                RowRecord(
                    key=key,
                    source=self.sources.get(key, SourceEntry(key)),
                    human=self.human.get(key, ""),
                    auto=self.auto.get(key, ""),
                    draft=draft_change if isinstance(draft_change, dict) else None,
                    author=author,
                )
            )
        for record in result:
            record.search_blob = "\n".join(
                [
                    record.key,
                    record.effective,
                    record.author,
                    record.source.location,
                    record.source.context,
                ]
            ).casefold()
        self._row_cache = result
        return result

    def current_author(self, key: str, locale: Optional[str] = None) -> str:
        locale = locale or self.locale
        entry = self.meta.get("entries", {}).get(locale, {}).get(key, {})
        current = entry.get("current", {}) if isinstance(entry, dict) else {}
        return str(current.get("translator_name", ""))

    def _append_history(
        self,
        locale: str,
        key: str,
        old_value: str,
        new_value: str,
        action: str,
        translator_name: str,
        source: str,
        imported_from_package: bool = False,
    ) -> None:
        locale_entries = self.meta.setdefault("entries", {}).setdefault(locale, {})
        entry = locale_entries.setdefault(key, {"current": {}, "history": []})
        timestamp = now_iso()
        revision = {
            "translator_name": translator_name,
            "target_locale": locale,
            "translation_source": source,
            "timestamp": timestamp,
            "action": action,
            "old_value": old_value,
            "new_value": new_value,
        }
        if imported_from_package:
            revision["imported_from_package"] = True
        entry.setdefault("history", []).append(revision)
        if new_value:
            entry["current"] = {
                "translator_name": translator_name,
                "target_locale": locale,
                "translation_source": source,
                "last_modified": timestamp,
            }
        else:
            entry["current"] = {}

    def apply_current_draft(self) -> tuple[int, int]:
        changes = self.draft.get("changes", {})
        if not changes:
            return 0, 0
        new_human = dict(self.human)
        changed = 0
        skipped = 0
        translator = self.translator_name
        pending_history: list[tuple[str, str, str, str]] = []
        for key, change in changes.items():
            if not isinstance(change, dict):
                continue
            old = new_human.get(key, "")
            new = str(change.get("new_value", ""))
            action = str(change.get("action", "edit"))
            if old == new:
                skipped += 1
                continue
            if new:
                new_human[key] = new
            else:
                new_human.pop(key, None)
            pending_history.append((key, old, new, action))
            changed += 1

        previous_meta = copy.deepcopy(self.meta)
        for key, old, new, action in pending_history:
            self._append_history(self.locale, key, old, new, action, translator, "human")
        try:
            atomic_write_json_set({self.human_path(): new_human, self.meta_path: self.meta})
        except Exception:
            self.meta = previous_meta
            raise
        self.human = new_human
        self.draft["last_applied_at"] = now_iso()
        self.save_draft()
        self.invalidate_rows()
        return changed, skipped

    def clear_draft(self) -> None:
        self.draft["changes"] = {}
        self.draft.pop("last_applied_at", None)
        self.save_draft()
        self.invalidate_rows()

    def archive_current_draft(self) -> Optional[Path]:
        if not self.locale or not self.draft.get("changes"):
            return None
        archive_dir = self.drafts_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"{self.locale}_{timestamp}.json"
        atomic_write_json(archive_path, self.draft)
        return archive_path

    def start_new_draft(self) -> Optional[Path]:
        archived = self.archive_current_draft()
        self.clear_draft()
        return archived

    def delete_current_draft(self) -> None:
        self.clear_draft()
        try:
            self.draft_path().unlink(missing_ok=True)
        except Exception:
            pass

    def draft_options(self) -> list[tuple[str, Path]]:
        options: list[tuple[str, Path]] = []
        current = self.draft_path()
        changes = len(self.draft.get("changes", {}))
        if current.exists() and changes:
            modified = self.draft.get("last_modified", "?")
            options.append((f"Current draft - {changes} changes - {modified}", current))

        archive_dir = self.drafts_dir / "archive"
        if archive_dir.is_dir():
            archived = sorted(
                archive_dir.glob(f"{self.locale}_*.json"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            for path in archived:
                try:
                    data = read_json(path, {})
                    changes = len(data.get("changes", {})) if isinstance(data, dict) else 0
                    modified = data.get("last_modified", "?") if isinstance(data, dict) else "?"
                except Exception:
                    changes = 0
                    modified = "?"
                options.append((f"{path.stem} - {changes} changes - {modified}", path))
        return options

    def restore_draft(self, path: Path) -> None:
        data = read_json(path, {})
        if not isinstance(data, dict) or data.get("format") != DRAFT_FORMAT:
            raise RuntimeError(f"Invalid draft file:\n{path}")
        if data.get("target_locale") != self.locale:
            raise RuntimeError(f"Draft locale does not match current locale: {data.get('target_locale')!r}")
        data.setdefault("changes", {})
        data.setdefault("translator_name", DEFAULT_TRANSLATOR)
        self.draft = data
        self.save_draft()
        self.invalidate_rows()

    def package_payload(self) -> dict[str, Any]:
        changes = self.draft.get("changes", {})
        if not changes:
            raise RuntimeError("There are no draft changes to package.")
        return {
            "format": PACKAGE_FORMAT,
            "version": PACKAGE_VERSION,
            "target_locale": self.locale,
            "translator_name": self.translator_name,
            "packaged_at": now_iso(),
            "changes": copy.deepcopy(changes),
        }

    def write_package(self, path: Path) -> int:
        payload = self.package_payload()
        atomic_write_json(path, payload)
        return len(payload["changes"])

    def read_package(self, path: Path) -> dict[str, Any]:
        data = read_json(path, {})
        if not isinstance(data, dict):
            raise RuntimeError("Translation package must contain a JSON object.")
        if data.get("format") != PACKAGE_FORMAT:
            raise RuntimeError("This is not an RZMenu Translation for Ray Chan package.")
        if data.get("version") != PACKAGE_VERSION:
            raise RuntimeError(f"Unsupported package version: {data.get('version')!r}")
        if not isinstance(data.get("target_locale"), str) or not data.get("target_locale"):
            raise RuntimeError("Package has no target locale.")
        if not isinstance(data.get("changes"), dict):
            raise RuntimeError("Package has no valid changes dictionary.")
        return data

    def package_conflicts(self, package: dict[str, Any]) -> list[dict[str, str]]:
        locale = str(package["target_locale"])
        current = validate_flat_string_dict(read_json(self.human_path(locale), {}), f"{locale}.json")
        conflicts: list[dict[str, str]] = []
        for key, change in package["changes"].items():
            if not isinstance(key, str) or not isinstance(change, dict):
                continue
            base = str(change.get("base_value", ""))
            incoming = str(change.get("new_value", ""))
            existing = current.get(key, "")
            if existing != base and existing != incoming:
                conflicts.append({"key": key, "current": existing, "incoming": incoming, "base": base})
        return conflicts

    def apply_package(self, package: dict[str, Any], decisions: dict[str, bool]) -> tuple[int, int]:
        locale = str(package["target_locale"])
        translator = str(package.get("translator_name") or DEFAULT_TRANSLATOR)
        path = self.human_path(locale)
        human = validate_flat_string_dict(read_json(path, {}), path.name)
        applied = 0
        kept = 0
        pending: list[tuple[str, str, str, str]] = []
        for key, change in package["changes"].items():
            if not isinstance(key, str) or not isinstance(change, dict):
                continue
            current = human.get(key, "")
            incoming = str(change.get("new_value", ""))
            if key in decisions and not decisions[key]:
                kept += 1
                continue
            if current == incoming:
                continue
            action = str(change.get("action", "edit"))
            if incoming:
                human[key] = incoming
            else:
                human.pop(key, None)
            pending.append((key, current, incoming, action))
            applied += 1
        previous_meta = copy.deepcopy(self.meta)
        for key, old, new, action in pending:
            self._append_history(locale, key, old, new, action, translator, "human", imported_from_package=True)
        try:
            atomic_write_json_set({path: human, self.meta_path: self.meta})
        except Exception:
            self.meta = previous_meta
            raise
        if locale == self.locale:
            self.human = human
            self.invalidate_rows()
        return applied, kept

    def contributor_stats(self) -> list[dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}
        for locale, locale_entries in self.meta.get("entries", {}).items():
            if not isinstance(locale_entries, dict):
                continue
            for entry in locale_entries.values():
                if not isinstance(entry, dict):
                    continue
                current = entry.get("current", {})
                if isinstance(current, dict) and current.get("translator_name"):
                    name = str(current["translator_name"])
                    record = stats.setdefault(name, {"name": name, "active": 0, "edits": 0, "locales": set()})
                    record["active"] += 1
                    record["locales"].add(locale)
                for revision in entry.get("history", []):
                    if isinstance(revision, dict) and revision.get("translator_name"):
                        name = str(revision["translator_name"])
                        record = stats.setdefault(name, {"name": name, "active": 0, "edits": 0, "locales": set()})
                        record["edits"] += 1
                        record["locales"].add(locale)
        return sorted(stats.values(), key=lambda item: (-item["active"], -item["edits"], item["name"].casefold()))

    def history_for(self, key: str) -> list[dict[str, Any]]:
        entry = self.meta.get("entries", {}).get(self.locale, {}).get(key, {})
        history = entry.get("history", []) if isinstance(entry, dict) else []
        return list(reversed(history)) if isinstance(history, list) else []


# ---------------------------- Automatic translator ------------------------


class AutoTranslateWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(dict, int, list)
    failed = Signal(str)

    def __init__(self, target_locale: str, source_keys: list[str], auto_path: Path, initial_auto: dict[str, str]) -> None:
        super().__init__()
        self.target_locale = target_locale
        self.source_keys = source_keys
        self.auto_path = auto_path
        self.auto = dict(initial_auto)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if GoogleTranslator is None:
            self.failed.emit("deep-translator is not installed.")
            return
        try:
            translator = GoogleTranslator(source="auto", target=normalize_google_locale(self.target_locale))
            errors: list[str] = []
            completed = 0
            total = len(self.source_keys)
            dirty = 0
            for index, key in enumerate(self.source_keys, start=1):
                if self._cancelled:
                    break
                self.progress.emit(index - 1, total, key)
                try:
                    protected, mapping = protect_placeholders(key)
                    translated = translator.translate(protected)
                    if not isinstance(translated, str):
                        raise RuntimeError("Translator returned an empty response.")
                    translated = restore_placeholders(translated, mapping)
                    self.auto[key] = translated
                    completed += 1
                    dirty += 1
                    if dirty >= AUTO_SAVE_BATCH:
                        atomic_write_json(self.auto_path, self.auto)
                        dirty = 0
                except Exception as exc:
                    errors.append(f"{key}: {exc}")
            if dirty:
                atomic_write_json(self.auto_path, self.auto)
            self.progress.emit(total, total, "Done")
            self.finished.emit(self.auto, completed, errors)
        except Exception as exc:
            self.failed.emit(str(exc))


# --------------------------------- Dialogs ---------------------------------


class ConflictDialog(QDialog):
    def __init__(self, conflicts: list[dict[str, str]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Translation conflicts")
        self.resize(980, 520)
        layout = QVBoxLayout(self)
        label = QLabel(
            "Some strings changed after the package was created. Choose which version should survive."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.table = QTableWidget(len(conflicts), 4)
        self.table.setHorizontalHeaderLabels(["Source", "Current repository", "Incoming package", "Decision"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._combos: dict[str, QComboBox] = {}
        for row, conflict in enumerate(conflicts):
            self.table.setItem(row, 0, QTableWidgetItem(conflict["key"]))
            self.table.setItem(row, 1, QTableWidgetItem(conflict["current"]))
            self.table.setItem(row, 2, QTableWidgetItem(conflict["incoming"]))
            combo = QComboBox()
            combo.addItem("Keep current", False)
            combo.addItem("Accept incoming", True)
            self.table.setCellWidget(row, 3, combo)
            self._combos[conflict["key"]] = combo
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def decisions(self) -> dict[str, bool]:
        return {key: bool(combo.currentData()) for key, combo in self._combos.items()}


class ContributorsDialog(QDialog):
    def __init__(self, stats: list[dict[str, Any]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Contributors")
        self.resize(620, 420)
        layout = QVBoxLayout(self)
        title = QLabel("🌟 Contributors")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        subtitle = QLabel("Current translations and edit history. Quality control with a tiny victory board.")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        table = QTableWidget(len(stats), 4)
        table.setHorizontalHeaderLabels(["Translator", "Active translations", "Total edits", "Locales"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for row, record in enumerate(stats):
            table.setItem(row, 0, QTableWidgetItem(str(record["name"])))
            table.setItem(row, 1, QTableWidgetItem(str(record["active"])))
            table.setItem(row, 2, QTableWidgetItem(str(record["edits"])))
            table.setItem(row, 3, QTableWidgetItem(", ".join(sorted(record["locales"]))))
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class ThankYouDialog(QDialog):
    def __init__(self, root: Path, package_path: Path, locale: str, changes_count: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.package_path = package_path
        self.setWindowTitle("Translation packaged!")
        self.resize(520, 460)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_path = self._find_image(root)
        if image_path:
            pixmap = QPixmap(str(image_path))
            if not pixmap.isNull():
                image_label.setPixmap(pixmap.scaled(360, 230, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if image_label.pixmap() is None:
            image_label.setText("💋📦")
            image_label.setObjectName("kissFallback")
        layout.addWidget(image_label)

        title = QLabel("Translation packaged!")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        text = QLabel(
            "Ray Chan appreciates your contribution 💋\n\n"
            "Your translation is ready. Send the .tfraychan file to Ray Chan through Discord DM.\n\n"
            f"Language: {locale}\nChanged strings: {changes_count}"
        )
        text.setAlignment(Qt.AlignCenter)
        text.setWordWrap(True)
        layout.addWidget(text)

        row = QHBoxLayout()
        open_button = QPushButton("Open file location")
        close_button = QPushButton("Close")
        open_button.clicked.connect(self.open_location)
        close_button.clicked.connect(self.accept)
        row.addWidget(open_button)
        row.addWidget(close_button)
        layout.addLayout(row)

    @staticmethod
    def _find_image(root: Path) -> Optional[Path]:
        candidates = [
            root / "translation" / "assets" / "ray_chan_kiss.png",
            root / "translation" / "assets" / "raychan_kiss.png",
            root / "assets" / "ray_chan_kiss.png",
            root / "assets" / "raychan_kiss.png",
        ]
        direct = next((path for path in candidates if path.is_file()), None)
        if direct is not None:
            return direct
        for pattern in ("*ray*chan*kiss*.png", "*raychan*kiss*.png"):
            found = next(root.rglob(pattern), None)
            if found is not None and found.is_file():
                return found
        return None

    def open_location(self) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(self.package_path.parent))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{self.package_path.parent}"')
            else:
                os.system(f'xdg-open "{self.package_path.parent}"')
        except Exception as exc:
            QMessageBox.warning(self, "Could not open folder", str(exc))


class AddLocaleDialog(QDialog):
    def __init__(self, existing_locales: Iterable[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Language")
        self.resize(520, 520)
        self.selected_locale = ""
        self._existing = set(existing_locales)

        layout = QVBoxLayout(self)
        title = QLabel("Add translation language")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search language or Blender locale code...")
        self.search.textChanged.connect(self.populate)
        layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.accept_selected)
        layout.addWidget(self.list_widget, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.populate()

    def populate(self) -> None:
        query = self.search.text().strip().casefold()
        self.list_widget.clear()
        for code, name in BLENDER_LOCALES:
            label = f"{name} ({code})"
            if query and query not in label.casefold() and query not in code.casefold():
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, code)
            if code in self._existing:
                item.setText(f"{label}  already added")
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def accept_selected(self, item: Optional[QListWidgetItem] = None) -> None:
        if item is not None:
            self.list_widget.setCurrentItem(item)
        item = self.list_widget.currentItem()
        if item is None or not item.flags() & Qt.ItemIsEnabled:
            return
        self.selected_locale = str(item.data(Qt.UserRole))
        self.accept()


# ---------------------------------- UI -------------------------------------


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository) -> None:
        super().__init__()
        self.repo = repo
        self._refreshing_table = False
        self._current_rows: list[RowRecord] = []
        self._current_rows_by_key: dict[str, RowRecord] = {}
        self._render_generation = 0
        self._render_row = 0
        self._filter_name = "All strings"
        self._auto_thread: Optional[QThread] = None
        self._auto_worker: Optional[AutoTranslateWorker] = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.refresh_table)
        self.setWindowTitle(f"{APP_NAME} · {repo.root.name}")
        self.resize(1480, 860)
        self.setMinimumSize(1020, 680)
        self._build_ui()
        self._load_initial_locale()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("RZMenu Translation Tool")
        title.setObjectName("appTitle")
        subtitle = QLabel("Human translations on top, automatic translations underneath, tiny blame trail included.")
        subtitle.setObjectName("muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        header.addWidget(QLabel("Language"))
        self.locale_combo = QComboBox()
        self.locale_combo.setMinimumWidth(120)
        self.locale_combo.currentTextChanged.connect(self.on_locale_changed)
        header.addWidget(self.locale_combo)
        add_locale_button = QPushButton("+")
        add_locale_button.setFixedWidth(34)
        add_locale_button.setToolTip("Create a new translation language")
        add_locale_button.clicked.connect(self.add_locale)
        header.addWidget(add_locale_button)

        header.addWidget(QLabel("Translator"))
        self.translator_edit = QLineEdit()
        self.translator_edit.setPlaceholderText(DEFAULT_TRANSLATOR)
        self.translator_edit.setMinimumWidth(170)
        self.translator_edit.editingFinished.connect(self.on_translator_changed)
        header.addWidget(self.translator_edit)

        contributors = QPushButton("Contributors")
        contributors.clicked.connect(self.show_contributors)
        header.addWidget(contributors)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self.manual_tab = QWidget()
        self.auto_tab = QWidget()
        self.tabs.addTab(self.manual_tab, "Manual Translation")
        self.tabs.addTab(self.auto_tab, "Auto Translation")
        self._build_manual_tab()
        self._build_auto_tab()

        footer = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("muted")
        footer.addWidget(self.status_label)
        footer.addStretch(1)

        self.apply_button = QPushButton("Apply Translation")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.clicked.connect(self.apply_translation)
        footer.addWidget(self.apply_button)

        self.package_button = QPushButton("Package for Ray Chan 💌")
        self.package_button.clicked.connect(self.package_translation)
        self.package_button.setToolTip("Package your draft into a .tfraychan file and send it to Ray Chan through Discord DM.")
        footer.addWidget(self.package_button)

        self.unpack_button = QPushButton("Unpackage Translation")
        self.unpack_button.clicked.connect(self.unpackage_translation)
        self.unpack_button.setToolTip("This button is only for Ray Chan. Unpackage a translation file and apply it to the repository.")
        footer.addWidget(self.unpack_button)
        outer.addLayout(footer)

    def _build_manual_tab(self) -> None:
        layout = QVBoxLayout(self.manual_tab)
        controls = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search source text, translation, author or file...")
        self.search_edit.textChanged.connect(self.schedule_table_refresh)
        controls.addWidget(self.search_edit, 1)
        refresh_button = QPushButton("↻")
        refresh_button.setObjectName("iconButton")
        refresh_button.setFixedWidth(40)
        refresh_button.setToolTip("Refresh project strings")
        refresh_button.clicked.connect(self.refresh_project)
        controls.addWidget(refresh_button)
        layout.addLayout(controls)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("summary")
        layout.addWidget(self.summary_label)

        self.draft_banner = QFrame()
        self.draft_banner.setObjectName("draftBanner")
        draft_layout = QHBoxLayout(self.draft_banner)
        draft_layout.setContentsMargins(10, 8, 10, 8)
        self.draft_label = QLabel()
        self.draft_label.setObjectName("muted")
        draft_layout.addWidget(self.draft_label, 1)
        self.draft_combo = QComboBox()
        self.draft_combo.setMinimumWidth(260)
        draft_layout.addWidget(self.draft_combo)
        self.restore_draft_button = QPushButton("Restore")
        self.restore_draft_button.clicked.connect(self.restore_selected_draft)
        draft_layout.addWidget(self.restore_draft_button)
        self.keep_draft_button = QPushButton("Keep editing")
        self.keep_draft_button.clicked.connect(self.hide_draft_banner)
        draft_layout.addWidget(self.keep_draft_button)
        self.new_draft_button = QPushButton("New draft")
        self.new_draft_button.clicked.connect(self.start_new_draft)
        draft_layout.addWidget(self.new_draft_button)
        self.delete_draft_button = QPushButton("Delete draft")
        self.delete_draft_button.clicked.connect(self.delete_draft)
        draft_layout.addWidget(self.delete_draft_button)
        self.draft_banner.hide()
        layout.addWidget(self.draft_banner)

        filter_row = QHBoxLayout()
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        for index, name in enumerate(FILTERS):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setObjectName("filterChip")
            self.filter_group.addButton(button, index)
            filter_row.addWidget(button)
            if name == self._filter_name:
                button.setChecked(True)
        self.filter_group.idClicked.connect(self.on_filter_clicked)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        splitter = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Status", "Source text", "Translation", "Author", "Location"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.itemChanged.connect(self.on_table_item_changed)
        self.table.itemSelectionChanged.connect(self.update_details)
        splitter.addWidget(self.table)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_title = QLabel("Selected string")
        details_title.setObjectName("sectionTitle")
        details_layout.addWidget(details_title)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Select a row to inspect context and translation history.")
        details_layout.addWidget(self.details_text, 1)
        self.restore_button = QPushButton("Restore previous human value")
        self.restore_button.clicked.connect(self.restore_previous)
        details_layout.addWidget(self.restore_button)
        splitter.addWidget(details)
        splitter.setSizes([1000, 380])
        layout.addWidget(splitter, 1)

    def _build_auto_tab(self) -> None:
        layout = QVBoxLayout(self.auto_tab)
        group = QGroupBox("Automatic translation")
        group_layout = QVBoxLayout(group)
        info = QLabel(
            "Machine translations fill only the *_auto.json layer. Manual corrections remain separate and always win."
        )
        info.setWordWrap(True)
        group_layout.addWidget(info)
        self.auto_dependency_label = QLabel()
        self.auto_dependency_label.setWordWrap(True)
        group_layout.addWidget(self.auto_dependency_label)
        self.auto_summary_label = QLabel()
        self.auto_summary_label.setObjectName("summary")
        group_layout.addWidget(self.auto_summary_label)
        row = QHBoxLayout()
        self.auto_translate_button = QPushButton("Translate missing strings")
        self.auto_translate_button.setObjectName("primaryButton")
        self.auto_translate_button.clicked.connect(self.start_auto_translation)
        row.addWidget(self.auto_translate_button)
        self.auto_cancel_button = QPushButton("Cancel")
        self.auto_cancel_button.clicked.connect(self.cancel_auto_translation)
        self.auto_cancel_button.setEnabled(False)
        row.addWidget(self.auto_cancel_button)
        row.addStretch(1)
        group_layout.addLayout(row)
        self.auto_progress_label = QLabel("Idle")
        self.auto_progress_label.setObjectName("muted")
        group_layout.addWidget(self.auto_progress_label)
        layout.addWidget(group)
        layout.addStretch(1)

    def _load_initial_locale(self) -> None:
        locales = self.repo.available_locales()
        self.locale_combo.blockSignals(True)
        self.locale_combo.clear()
        self.locale_combo.addItems(locales)
        self.locale_combo.blockSignals(False)
        self.repo.load_locale(locales[0])
        self.translator_edit.setText(self.repo.translator_name)
        self.update_draft_banner()
        self.refresh_table()
        self.refresh_auto_panel()
        self.status_label.setText(f"Project root: {self.repo.root}")

    def add_locale(self) -> None:
        dialog = AddLocaleDialog(self.repo.available_locales(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        locale = dialog.selected_locale
        if not locale:
            return
        locales = self.repo.available_locales()
        if locale not in locales:
            locales.append(locale)
            locales.sort(key=str.casefold)
        self.locale_combo.blockSignals(True)
        self.locale_combo.clear()
        self.locale_combo.addItems(locales)
        self.locale_combo.setCurrentText(locale)
        self.locale_combo.blockSignals(False)
        try:
            self.repo.load_locale(locale)
            self.translator_edit.setText(self.repo.translator_name)
            self.update_draft_banner()
            self.refresh_table()
            self.refresh_auto_panel()
            self.status_label.setText(f"New language draft: {locale}")
        except Exception as exc:
            self.show_error("Could not create language draft", exc)

    def confirm_existing_draft(self) -> None:
        self.update_draft_banner()

    def update_draft_banner(self) -> None:
        changes = self.repo.draft.get("changes", {})
        options = self.repo.draft_options()
        if not changes and not options:
            self.draft_banner.hide()
            return
        self.draft_combo.blockSignals(True)
        self.draft_combo.clear()
        for label, path in options:
            self.draft_combo.addItem(label, str(path))
        self.draft_combo.blockSignals(False)
        self.draft_combo.setVisible(bool(options))
        self.restore_draft_button.setVisible(bool(options))
        self.draft_label.setText(
            f"Draft for {self.repo.locale}: {len(changes)} changes, "
            f"last saved {self.repo.draft.get('last_modified', '?')}"
        )
        self.draft_banner.show()

    def hide_draft_banner(self) -> None:
        self.draft_banner.hide()

    def restore_selected_draft(self) -> None:
        path_text = self.draft_combo.currentData()
        if not path_text:
            return
        try:
            self.repo.restore_draft(Path(str(path_text)))
            self.update_draft_banner()
            self.refresh_table()
            self.status_label.setText("Draft restored.")
        except Exception as exc:
            self.show_error("Could not restore draft", exc)

    def start_new_draft(self) -> None:
        archived = self.repo.start_new_draft()
        self.update_draft_banner()
        self.refresh_table()
        suffix = f" Archived previous draft to {archived.name}." if archived else ""
        self.status_label.setText(f"New empty draft created.{suffix}")

    def delete_draft(self) -> None:
        self.repo.delete_current_draft()
        self.update_draft_banner()
        self.refresh_table()
        self.status_label.setText("Draft deleted.")

    def on_locale_changed(self, locale: str) -> None:
        if not locale:
            return
        try:
            self.set_busy(True, f"Loading {locale}...")
            self.repo.load_locale(locale)
            self.translator_edit.setText(self.repo.translator_name)
            self.update_draft_banner()
            self.refresh_table()
            self.refresh_auto_panel()
            self.status_label.setText(f"Loaded {locale}")
        except Exception as exc:
            self.show_error("Could not load locale", exc)
        finally:
            self.set_busy(False)

    def on_translator_changed(self) -> None:
        try:
            self.repo.set_translator_name(self.translator_edit.text())
            self.translator_edit.setText(self.repo.translator_name)
            self.status_label.setText(f"Translator: {self.repo.translator_name}")
        except Exception as exc:
            self.show_error("Could not save translator name", exc)

    def schedule_table_refresh(self) -> None:
        self.status_label.setText("Filtering...")
        self._search_timer.start()

    def on_filter_clicked(self, button_id: int) -> None:
        if 0 <= button_id < len(FILTERS):
            self._filter_name = FILTERS[button_id]
            self.schedule_table_refresh()

    def filtered_rows(self) -> list[RowRecord]:
        query = self.search_edit.text().strip().casefold()
        filter_name = self._filter_name
        rows = self.repo.rows()
        result: list[RowRecord] = []
        for record in rows:
            if query and query not in record.search_blob:
                continue
            status = record.status
            if filter_name == "Missing" and status != "missing":
                continue
            if filter_name == "Translated" and status == "missing":
                continue
            if filter_name == "Auto-only" and status != "auto-only":
                continue
            if filter_name == "Human" and not record.human:
                continue
            if filter_name == "Draft" and record.draft is None:
                continue
            if filter_name == "Placeholders" and not PLACEHOLDER_RE.search(record.key):
                continue
            if filter_name == "Long strings" and len(record.key) < LONG_TEXT_THRESHOLD:
                continue
            result.append(record)
        return result

    def refresh_table(self) -> None:
        if not self.repo.locale:
            return
        self._search_timer.stop()
        self._render_generation += 1
        generation = self._render_generation
        self._refreshing_table = True
        rows = self.filtered_rows()
        self._current_rows = rows
        self._current_rows_by_key = {record.key: record for record in rows}
        self._render_row = 0
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(rows))
        self.status_label.setText(f"Rendering {len(rows)} rows...")
        QTimer.singleShot(0, lambda: self._render_table_batch(generation))

    def _render_table_batch(self, generation: int) -> None:
        if generation != self._render_generation:
            return

        end = min(self._render_row + TABLE_RENDER_BATCH, len(self._current_rows))
        for row in range(self._render_row, end):
            record = self._current_rows[row]
            status_item = QTableWidgetItem(record.status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            source_item = QTableWidgetItem(record.key)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            translation_item = QTableWidgetItem(record.effective)
            translation_item.setData(Qt.UserRole, record.key)
            author_item = QTableWidgetItem(record.author)
            author_item.setFlags(author_item.flags() & ~Qt.ItemIsEditable)
            location_item = QTableWidgetItem(record.source.location)
            location_item.setFlags(location_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, status_item)
            self.table.setItem(row, 1, source_item)
            self.table.setItem(row, 2, translation_item)
            self.table.setItem(row, 3, author_item)
            self.table.setItem(row, 4, location_item)

        self._render_row = end
        if self._render_row < len(self._current_rows):
            QTimer.singleShot(0, lambda: self._render_table_batch(generation))
            return

        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)
        self._refreshing_table = False
        self.update_summary()
        self.update_details()
        if self._current_rows:
            self.status_label.setText(f"Ready. Showing {len(self._current_rows)} rows.")
        else:
            self.status_label.setText("No rows match the current search and filter.")

    def update_summary(self) -> None:
        rows = self.repo.rows()
        total = len(rows)
        missing = sum(row.status == "missing" for row in rows)
        auto_only = sum(row.status == "auto-only" for row in rows)
        human = sum(bool(row.human) for row in rows)
        drafts = len(self.repo.draft.get("changes", {}))
        translated = total - missing
        coverage = round((translated / total) * 100, 1) if total else 0.0
        self.summary_label.setText(
            f"Total: {total}   ·   Translated: {translated}   ·   Missing: {missing}   ·   "
            f"Auto-only: {auto_only}   ·   Human: {human}   ·   Draft changes: {drafts}   ·   Coverage: {coverage}%"
        )
        self.apply_button.setEnabled(bool(drafts))
        self.package_button.setEnabled(bool(drafts))

    def on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._refreshing_table or item.column() != 2:
            return
        key = item.data(Qt.UserRole)
        if not isinstance(key, str):
            return
        try:
            self.repo.edit_translation(key, item.text())
            self.status_label.setText("Draft autosaved")
            self.refresh_table()
            self.refresh_auto_panel()
        except Exception as exc:
            self.show_error("Could not autosave draft", exc)

    def update_details(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            self.details_text.clear()
            self.restore_button.setEnabled(False)
            return
        row = selected[0].row()
        source_item = self.table.item(row, 1)
        if source_item is None:
            return
        key = source_item.text()
        record = self._current_rows_by_key.get(key)
        if record is None:
            return
        history = self.repo.history_for(key)
        history_lines: list[str] = []
        for revision in history[:20]:
            history_lines.append(
                f"{revision.get('timestamp', '?')} · {revision.get('translator_name', '?')} · {revision.get('action', '?')}\n"
                f"  {revision.get('old_value', '')!r} → {revision.get('new_value', '')!r}"
            )
        draft_text = ""
        if record.draft is not None:
            draft_text = (
                "\n\nDRAFT CHANGE\n"
                f"Action: {record.draft.get('action', '?')}\n"
                f"Base human value: {record.draft.get('base_value', '')!r}\n"
                f"Draft value: {record.draft.get('new_value', '')!r}"
            )
        text = (
            f"SOURCE\n{record.key}\n\n"
            f"STATUS\n{record.status}\n\n"
            f"CURRENT HUMAN VALUE\n{record.human or '—'}\n\n"
            f"CURRENT AUTO VALUE\n{record.auto or '—'}\n\n"
            f"AUTHOR\n{record.author or '—'}\n\n"
            f"CONTEXT\n{record.source.context}"
            f"{draft_text}\n\n"
            "HISTORY\n"
            + ("\n\n".join(history_lines) if history_lines else "No recorded history yet.")
        )
        self.details_text.setPlainText(text)
        self.restore_button.setEnabled(bool(history))

    def selected_key(self) -> Optional[str]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        source_item = self.table.item(selected[0].row(), 1)
        return source_item.text() if source_item else None

    def restore_previous(self) -> None:
        key = self.selected_key()
        if not key:
            return
        history = self.repo.history_for(key)
        if not history:
            return
        previous_value = str(history[0].get("old_value", ""))
        try:
            self.repo.edit_translation(key, previous_value)
            change = self.repo.draft.get("changes", {}).get(key)
            if isinstance(change, dict):
                change["action"] = "restore"
                self.repo.save_draft()
            self.refresh_table()
            self.status_label.setText("Previous value restored into draft")
        except Exception as exc:
            self.show_error("Could not restore previous value", exc)

    def refresh_project(self) -> None:
        try:
            self.set_busy(True, "Refreshing project strings...")
            current = self.repo.locale
            self.repo.meta = self.repo._load_meta()
            self.repo.scan_sources()
            self.repo.load_locale(current)
            locales = self.repo.available_locales()
            self.locale_combo.blockSignals(True)
            self.locale_combo.clear()
            self.locale_combo.addItems(locales)
            self.locale_combo.setCurrentText(current)
            self.locale_combo.blockSignals(False)
            self.refresh_table()
            self.refresh_auto_panel()
            self.status_label.setText("Project refreshed")
        except Exception as exc:
            self.show_error("Could not refresh project", exc)
        finally:
            self.set_busy(False)

    def apply_translation(self) -> None:
        if not self.repo.draft.get("changes"):
            QMessageBox.information(self, "Nothing to apply", "The draft contains no changes.")
            return
        answer = QMessageBox.question(
            self,
            "Apply translation",
            "Apply the current draft to the local repository?\n\n"
            "The draft will remain available for packaging afterwards.",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.set_busy(True, "Applying draft...")
            changed, skipped = self.repo.apply_current_draft()
            self.update_draft_banner()
            self.refresh_table()
            self.refresh_auto_panel()
            self.status_label.setText(f"Applied. Changed strings: {changed}. Already identical: {skipped}.")
        except Exception as exc:
            self.show_error("Could not apply translation", exc)
        finally:
            self.set_busy(False)

    def package_translation(self) -> None:
        try:
            date = dt.date.today().isoformat()
            suggested = (
                f"RZMenu_Translation_{safe_filename_part(self.repo.locale)}_"
                f"{safe_filename_part(self.repo.translator_name)}_{date}{PACKAGE_EXTENSION}"
            )
            path_text, _ = QFileDialog.getSaveFileName(
                self,
                "Package translation for Ray Chan",
                str(self.repo.root / suggested),
                f"Translation for Ray Chan (*{PACKAGE_EXTENSION})",
            )
            if not path_text:
                return
            path = Path(path_text)
            if path.suffix.lower() != PACKAGE_EXTENSION:
                path = Path(str(path) + PACKAGE_EXTENSION)
            count = self.repo.write_package(path)
            ThankYouDialog(self.repo.root, path, self.repo.locale, count, self).exec()
        except Exception as exc:
            self.show_error("Could not package translation", exc)

    def unpackage_translation(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "Unpackage translation",
            str(self.repo.root),
            f"Translation for Ray Chan (*{PACKAGE_EXTENSION})",
        )
        if not path_text:
            return
        try:
            package = self.repo.read_package(Path(path_text))
            conflicts = self.repo.package_conflicts(package)
            overview = (
                f"Author: {package.get('translator_name', DEFAULT_TRANSLATOR)}\n"
                f"Language: {package['target_locale']}\n"
                f"Created: {package.get('packaged_at', '?')}\n"
                f"Changed strings: {len(package['changes'])}\n"
                f"Conflicts: {len(conflicts)}\n\n"
                "Apply this package to the repository?"
            )
            if QMessageBox.question(self, "Translation package", overview) != QMessageBox.Yes:
                return
            decisions: dict[str, bool] = {}
            if conflicts:
                dialog = ConflictDialog(conflicts, self)
                if dialog.exec() != QDialog.Accepted:
                    return
                decisions = dialog.decisions()
            applied, kept = self.repo.apply_package(package, decisions)
            target_locale = str(package["target_locale"])
            locales = self.repo.available_locales()
            self.locale_combo.blockSignals(True)
            self.locale_combo.clear()
            self.locale_combo.addItems(locales)
            self.locale_combo.setCurrentText(target_locale)
            self.locale_combo.blockSignals(False)
            self.repo.load_locale(target_locale)
            self.refresh_table()
            self.refresh_auto_panel()
            QMessageBox.information(
                self,
                "Translation unpackaged",
                f"Package applied successfully.\n\nApplied changes: {applied}\nKept current values: {kept}",
            )
        except Exception as exc:
            self.show_error("Could not unpackage translation", exc)

    def show_contributors(self) -> None:
        ContributorsDialog(self.repo.contributor_stats(), self).exec()

    def refresh_auto_panel(self) -> None:
        if DEEP_TRANSLATOR_AVAILABLE:
            self.auto_dependency_label.setText("Optional dependency detected: deep-translator is ready.")
            self.auto_translate_button.setEnabled(self._auto_thread is None)
        else:
            self.auto_dependency_label.setText(
                "Automatic translation is disabled because the optional dependency is missing.\n"
                "Install it with:  pip install deep-translator"
            )
            self.auto_translate_button.setEnabled(False)
        rows = self.repo.rows()
        eligible = [row for row in rows if not row.human and not row.auto and not is_decorative_text(row.key)]
        ignored = [row for row in rows if not row.human and not row.auto and is_decorative_text(row.key)]
        self.auto_summary_label.setText(
            f"Missing strings ready for automatic translation: {len(eligible)}\n"
            f"Ignored decorative strings: {len(ignored)}\n"
            f"Existing machine translations: {len(self.repo.auto)}"
        )

    def start_auto_translation(self) -> None:
        if not DEEP_TRANSLATOR_AVAILABLE:
            return
        keys = [
            row.key
            for row in self.repo.rows()
            if not row.human and not row.auto and not is_decorative_text(row.key)
        ]
        if not keys:
            QMessageBox.information(self, "Nothing to translate", "There are no missing strings eligible for automatic translation.")
            return
        answer = QMessageBox.question(
            self,
            "Automatic translation",
            f"Translate {len(keys)} missing strings into {self.repo.locale}?\n\n"
            "Results will be written only to the *_auto.json layer.",
        )
        if answer != QMessageBox.Yes:
            return
        self._auto_thread = QThread(self)
        self._auto_worker = AutoTranslateWorker(self.repo.locale, keys, self.repo.auto_path(), self.repo.auto)
        self._auto_worker.moveToThread(self._auto_thread)
        self._auto_thread.started.connect(self._auto_worker.run)
        self._auto_worker.progress.connect(self.on_auto_progress)
        self._auto_worker.finished.connect(self.on_auto_finished)
        self._auto_worker.failed.connect(self.on_auto_failed)
        self._auto_worker.finished.connect(self._auto_thread.quit)
        self._auto_worker.failed.connect(self._auto_thread.quit)
        self._auto_thread.finished.connect(self.cleanup_auto_thread)
        self.auto_translate_button.setEnabled(False)
        self.auto_cancel_button.setEnabled(True)
        self._auto_thread.start()

    def cancel_auto_translation(self) -> None:
        if self._auto_worker is not None:
            self._auto_worker.cancel()
            self.auto_progress_label.setText("Cancelling after the current string...")

    def on_auto_progress(self, completed: int, total: int, current: str) -> None:
        preview = current.replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:97] + "..."
        self.auto_progress_label.setText(f"{completed}/{total} · {preview}")

    def on_auto_finished(self, auto: dict, completed: int, errors: list) -> None:
        self.repo.auto = validate_flat_string_dict(auto, self.repo.auto_path().name)
        self.repo.invalidate_rows()
        self.refresh_table()
        self.refresh_auto_panel()
        message = f"Automatic translation completed.\n\nTranslated strings: {completed}\nErrors: {len(errors)}"
        if errors:
            message += "\n\nFirst errors:\n" + "\n".join(errors[:8])
        QMessageBox.information(self, "Automatic translation", message)

    def on_auto_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Automatic translation failed", message)

    def cleanup_auto_thread(self) -> None:
        self.auto_cancel_button.setEnabled(False)
        self._auto_worker = None
        if self._auto_thread is not None:
            self._auto_thread.deleteLater()
        self._auto_thread = None
        self.refresh_auto_panel()

    def show_error(self, title: str, exc: Exception) -> None:
        QMessageBox.critical(self, title, str(exc))
        self.status_label.setText(title)

    def set_busy(self, busy: bool, message: str = "") -> None:
        if busy:
            if message:
                self.status_label.setText(message)
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            if self.repo.locale:
                self.repo.save_draft()
        except Exception as exc:
            QMessageBox.warning(self, "Draft save failed", str(exc))
        if self._auto_worker is not None:
            self._auto_worker.cancel()
        event.accept()


DARK_STYLESHEET = """
QWidget {
    background: #15171b;
    color: #e8e9ec;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}
QMainWindow, QDialog { background: #15171b; }
QLabel#appTitle { font-size: 19pt; font-weight: 700; color: #ffffff; }
QLabel#dialogTitle { font-size: 16pt; font-weight: 700; color: #ffffff; }
QLabel#sectionTitle { font-size: 12pt; font-weight: 700; color: #ffffff; }
QLabel#muted { color: #9ca3af; }
QLabel#summary { color: #cfd4dc; padding: 5px 2px; }
QLabel#kissFallback { font-size: 54pt; padding: 24px; }
QFrame#draftBanner {
    background: #20252d;
    border: 1px solid #3c4655;
    border-radius: 7px;
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: #202329;
    border: 1px solid #343944;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #6d4aff;
    selection-color: #ffffff;
}
QTableWidget { gridline-color: #30343d; padding: 0; alternate-background-color: #1b1e23; }
QTableWidget::item { padding: 6px 5px; }
QHeaderView::section {
    background: #262a31;
    color: #d8dbe2;
    border: 0;
    border-right: 1px solid #343944;
    border-bottom: 1px solid #343944;
    padding: 7px;
    font-weight: 600;
}
QPushButton {
    background: #292e37;
    border: 1px solid #3a414d;
    border-radius: 7px;
    padding: 7px 12px;
}
QPushButton:hover { background: #333a46; }
QPushButton:pressed { background: #222730; }
QPushButton:disabled { color: #707782; background: #202329; border-color: #2b3038; }
QPushButton#primaryButton { background: #6547d9; border-color: #795cff; color: white; font-weight: 700; }
QPushButton#primaryButton:hover { background: #7556ed; }
QPushButton#iconButton { font-size: 13pt; font-weight: 700; padding: 4px 8px; }
QPushButton#filterChip {
    color: #cfd4dc;
    background: #1d2128;
    border-color: #303743;
    padding: 5px 10px;
}
QPushButton#filterChip:checked {
    color: #ffffff;
    background: #3b4352;
    border-color: #6d7c96;
}
QTabWidget::pane { border: 1px solid #303640; border-radius: 7px; top: -1px; }
QTabBar::tab { background: #202329; padding: 9px 14px; margin-right: 3px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #303541; color: white; }
QGroupBox { border: 1px solid #303640; border-radius: 8px; margin-top: 11px; padding-top: 10px; font-weight: 700; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QSplitter::handle { background: #303640; width: 2px; }
QToolTip { background: #262a31; color: #ffffff; border: 1px solid #4a5260; padding: 5px; }
"""


def exception_hook(exc_type, exc_value, exc_tb) -> None:
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        QMessageBox.critical(None, "Unexpected error", f"{exc_value}\n\nTechnical details:\n{details[-3500:]}")
    except Exception:
        print(details, file=sys.stderr)


def main() -> int:
    sys.excepthook = exception_hook
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    try:
        root = find_project_root()
        repo = Repository(root)
        window = MainWindow(repo)
        window.show()
        return app.exec()
    except Exception as exc:
        QMessageBox.critical(None, APP_NAME, str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
